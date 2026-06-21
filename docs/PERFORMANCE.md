# Performance Baseline - Knowledge Base Management System

## Overview

This document defines performance targets, measurement methodologies, and optimization strategies for the Knowledge Base system. All measurements are taken on the reference hardware configuration.

### Reference Hardware

| Component | Specification |
|-----------|--------------|
| CPU | 4 cores, 2.5 GHz+ |
| Memory | 8 GB (16 GB with local LLM) |
| Storage | SSD, 20 GB free |
| Network | Localhost for MVP |
| GPU | Optional (for local LLM acceleration) |

---

## 1. Performance Targets

### Frontend (Next.js)

| Metric | MVP Target | Production Target | Measurement |
|--------|-----------|-------------------|-------------|
| First Contentful Paint (FCP) | < 1.0s | < 500ms | Lighthouse |
| Largest Contentful Paint (LCP) | < 1.5s | < 800ms | Lighthouse |
| Time to Interactive (TTI) | < 2.0s | < 1.2s | Lighthouse |
| Cumulative Layout Shift (CLS) | < 0.1 | < 0.05 | Lighthouse |
| Editor input latency | < 50ms | < 30ms | Performance API |
| Document list render | < 200ms | < 100ms | React Profiler |
| Bundle size (initial) | < 300 KB gzipped | < 200 KB gzipped | `next build` analysis |
| Editor bundle (lazy) | < 500 KB gzipped | < 350 KB gzipped | Dynamic import |

### Backend (FastAPI)

| Metric | MVP Target | Production Target | Measurement |
|--------|-----------|-------------------|-------------|
| Health check | < 5ms | < 2ms | HTTP response time |
| Login | < 100ms | < 50ms | Server logs |
| Document CRUD | < 50ms | < 20ms | Server logs |
| Document list (50 items) | < 100ms | < 50ms | Server logs |
| Full-text search | < 200ms | < 80ms | Server logs |
| AI first token | < 1.5s | < 800ms | Custom instrumentation |
| AI full response (1000 tokens) | < 8s | < 4s | Custom instrumentation |
| RAG query (with retrieval) | < 3s | < 1.5s | Server logs |
| Pandoc export (10 pages) | < 10s | < 5s | Task timer |
| LaTeX compile (10 pages) | < 30s | < 15s | Task timer |

### Database (SQLite MVP / PostgreSQL Production)

| Metric | MVP Target (SQLite) | Production (PostgreSQL) |
|--------|--------------------|-------------------------|
| Simple SELECT | < 5ms | < 2ms |
| JOIN query | < 10ms | < 5ms |
| FTS5 search | < 50ms | < 20ms |
| Vector similarity (top-10) | < 100ms | < 30ms (pgvector HNSW) |
| INSERT | < 5ms | < 3ms |
| Concurrent reads | 10+ (WAL mode) | 100+ |

---

## 2. Resource Usage Targets

| Resource | MVP Limit | Production Limit |
|----------|-----------|-----------------|
| Backend memory | < 512 MB | < 256 MB |
| Frontend memory (Chrome) | < 256 MB | < 128 MB |
| Backend CPU (idle) | < 5% | < 2% |
| Backend CPU (AI request) | < 80% | < 60% |
| Database file size (1000 docs) | < 100 MB | < 50 MB (PostgreSQL) |
| Disk I/O (writes) | < 10 ops/sec | < 5 ops/sec |

---

## 3. Optimization Strategies

### Frontend Optimizations

1. **Code Splitting**: TipTap editor is dynamically imported via `next/dynamic` to avoid loading it on non-editor pages
2. **React Server Components**: Document list uses RSC for server-side rendering, reducing client-side JS
3. **Lazy Loading**: KaTeX CSS and math rendering loaded only when math blocks are present
4. **Debounced Saves**: Auto-save debounced to 1.5s to batch rapid edits into single API calls
5. **Optimistic Updates**: UI updates immediately while save happens in background
6. **Virtual Scrolling**: Document list uses virtual scrolling for 1000+ documents (future)
7. **Image Optimization**: `next/image` for automatic format conversion and responsive sizing

### Backend Optimizations

1. **Async I/O**: All database queries and HTTP calls use `async`/`await` to avoid blocking
2. **Connection Pooling**: SQLAlchemy engine with `pool_size=20, max_overflow=10`
3. **SQLite WAL Mode**: Write-Ahead Logging enables concurrent readers with single writer
4. **LRU Cache**: `functools.lru_cache` for configuration and frequently-accessed data
5. **Embedding Model Singleton**: BGE-M3 model loaded once at startup, reused across requests
6. **Streaming Responses**: AI responses streamed token-by-token to reduce perceived latency
7. **Background Tasks**: Heavy operations (export, embedding) run as background tasks

### Database Optimizations

1. **Indexes**: Composite indexes on frequently-queried columns (user_id + status, user_id + updated_at)
2. **FTS5 Virtual Table**: Full-text search using SQLite FTS5 for sub-50ms text search
3. **Prepared Statements**: SQLAlchemy compiles queries once, reuses execution plans
4. **Batch Operations**: Bulk inserts for embeddings and document versions
5. **WAL Checkpoint**: Periodic WAL checkpoint to prevent unbounded log growth

### AI-Specific Optimizations

1. **Model Routing**: Simple queries routed to smaller/faster models, complex queries to full LLM
2. **Prompt Caching**: Identical prompts cached in memory to avoid redundant API calls
3. **Context Window Management**: Only relevant context (500 tokens around selection) passed to edit operations
4. **Streaming**: All AI responses streamed to minimize time-to-first-token
5. **Embedding Batch**: Documents embedded in batches of 32 for GPU efficiency

---

## 4. Monitoring & Measurement

### Frontend Metrics Collection

```typescript
// Use Next.js built-in web vitals reporting
// next.config.ts -> experimental.webVitalsAttribution = true
export function reportWebVitals(metric) {
  // Send to analytics endpoint or log
  console.log(metric.name, metric.value);
}
```

### Backend Metrics Collection

```python
import time
import logging

logger = logging.getLogger("performance")

async def timed_endpoint(func, *args, **kwargs):
    start = time.perf_counter()
    result = await func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    logger.info(f"{func.__name__}: {elapsed:.3f}s")
    return result
```

### Performance Testing Tools

| Tool | Use Case |
|------|----------|
| Lighthouse | Frontend page load metrics |
| `ab` (Apache Bench) | API endpoint throughput |
| Chrome DevTools Memory | Frontend memory profiling |
| `memory_profiler` (Python) | Backend memory analysis |
| `pytest-benchmark` | Unit test performance regression |

---

## 5. Scalability Path

### SQLite → PostgreSQL Migration

When the system needs to support multiple concurrent users:

1. Switch from SQLite to PostgreSQL + pgvector
2. Replace `aiosqlite` with `asyncpg`
3. Add connection pooling via `psycopg_pool`
4. Create HNSW index for vector similarity search
5. Enable PostgreSQL full-text search (tsvector + GIN index)

### Single Process → Multi-Process

When CPU-bound operations (LaTeX compilation, embedding) become bottlenecks:

1. Run multiple `uvicorn` workers (`--workers 4`)
2. Move embedding generation to a dedicated worker process
3. Add Redis for shared caching and task queue
4. Use ARQ for reliable background task processing

### Local → Cloud LLM

When API costs or latency become concerns:

1. Deploy local models via vLLM for cost optimization
2. Implement request routing: simple queries → local, complex → cloud
3. Cache common responses to reduce API calls
4. Use model quantization (GGUF) for local inference efficiency
