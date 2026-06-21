# Test Plan - Knowledge Base Management System

## Overview

This document defines the comprehensive test strategy for the Knowledge Base system, covering unit tests, integration tests, and end-to-end tests across frontend and backend.

---

## 1. Test Pyramid

```
              ┌──────────┐
              │   E2E    │  5-10 critical flows (Playwright)
              ├──────────┤
              │Integration│  API + DB + AI Mock (pytest + Vitest)
              ├──────────┤
              │   Unit   │  Pure logic functions (pytest + Vitest)
              └──────────┘
```

### Coverage Targets

| Layer | MVP Target | Production Target |
|-------|-----------|-------------------|
| Backend unit tests | > 80% | > 90% |
| Backend integration | > 70% | > 80% |
| Frontend unit tests | > 60% | > 75% |
| E2E critical flows | 5 flows | 15 flows |

---

## 2. Backend Tests (pytest)

### Running Tests

```bash
cd backend
uv run pytest tests/ -v                    # All tests
uv run pytest tests/ -v --cov=app          # With coverage
uv run pytest tests/test_auth.py -v        # Specific file
uv run pytest -k "login" -v               # By keyword
```

### Test Files

| File | Scope | Test Count |
|------|-------|-----------|
| `tests/test_health.py` | Health check endpoint | 1 |
| `tests/test_auth.py` | Login, JWT, authorization | 4 |
| `tests/test_documents.py` | Document CRUD, search, pagination | 6 |
| `tests/test_ai.py` | AI service, structured extraction | (Phase 2) |
| `tests/test_export.py` | Export pipeline, format conversion | (Phase 2) |
| `tests/test_rag.py` | RAG retrieval, embedding, chunking | (Phase 2) |
| `tests/test_security.py` | Input validation, injection prevention | (Phase 2) |

### Test Cases

#### Authentication (test_auth.py) - 4 tests, ALL PASSING

| ID | Case | Input | Expected |
|----|------|-------|----------|
| AUTH-01 | Login success | admin/admin123 | 200 + access_token + refresh_token |
| AUTH-02 | Wrong password | admin/wrongpassword | 401 |
| AUTH-03 | Nonexistent user | nobody/test123 | 401 |
| AUTH-04 | No token | GET /api/documents | 401 |

#### Document CRUD (test_documents.py) - 6 tests, ALL PASSING

| ID | Case | Input | Expected |
|----|------|-------|----------|
| DOC-01 | Create document | title: "Test Document" | 201 + document data |
| DOC-02 | List documents | 3 created docs | 200 + total=3 |
| DOC-03 | Update document | title change + content | 200 + version=2 |
| DOC-04 | Delete document | DELETE endpoint | 200 + excluded from list |
| DOC-05 | Search documents | search="Python" | 200 + 2 matches |
| DOC-06 | Empty title rejected | title: "" | 422 validation error |

#### AI Service (test_ai.py) - PLANNED

| ID | Case | Input | Expected |
|----|------|-------|----------|
| AI-01 | Stream generation | Topic + messages | SSE stream, non-empty result |
| AI-02 | Edit - polish | Selected text | Improved text, same meaning |
| AI-03 | Edit - expand | Short text | Longer text with details |
| AI-04 | Edit - compress | Long text | ~50% shorter text |
| AI-05 | Edit - translate ZH | English text | Chinese translation |
| AI-06 | Edit - translate EN | Chinese text | English translation |
| AI-07 | LLM timeout | Mock slow response | 504 + friendly error |
| AI-08 | LLM malformed response | Mock bad JSON | Graceful degradation |
| AI-09 | Empty selection | No text selected | 400 Bad Request |
| AI-10 | Extract summary | Long document | Summary <= 200 chars |
| AI-11 | Extract keywords | Technical doc | 3-8 keywords |
| AI-12 | Extract outline | Structured doc | Hierarchical outline |

#### RAG (test_rag.py) - PLANNED

| ID | Case | Input | Expected |
|----|------|-------|----------|
| RAG-01 | Chunking correctness | 5000-char document | Chunks <= 512 tokens, overlap ~50 |
| RAG-02 | Embedding dimension | Any text | 1024-dim vector |
| RAG-03 | Vector similarity | Query + 10 docs | Top-K sorted by similarity |
| RAG-04 | Hybrid search | Keyword query | Better than vector-only |
| RAG-05 | Corrective evaluation | Low-relevance results | Query rewrite triggered |
| RAG-06 | Empty knowledge base | Any query | "No relevant content" |
| RAG-07 | New doc indexed | Add document | Immediately searchable |
| RAG-08 | Cross-document Q&A | Multi-source query | Answer cites sources |

#### Export (test_export.py) - PLANNED

| ID | Case | Input | Expected |
|----|------|-------|----------|
| EXP-01 | Markdown -> DOCX | MD content | Valid .docx file |
| EXP-02 | Markdown -> HTML | MD content | Valid HTML with styles |
| EXP-03 | Markdown -> EPUB | MD content | Valid .epub file |
| EXP-04 | Task status tracking | Export job | pending -> processing -> completed |
| EXP-05 | Failed export retry | Simulated failure | Auto-retry once |
| EXP-06 | Concurrent limit | 5 simultaneous exports | Max 3 parallel |
| EXP-07 | Large document | >100 pages | Complete < 60s |
| EXP-08 | LaTeX not available | PDF request | "Environment not ready" error |
| EXP-09 | Template selection | Different templates | Different output formatting |

#### Security (test_security.py) - PLANNED

| ID | Case | Input | Expected |
|----|------|-------|----------|
| SEC-01 | LaTeX injection | \input{secret.tex} | Rejected |
| SEC-02 | XSS prevention | `<script>alert(1)</script>` | Escaped in response |
| SEC-03 | SQL injection | `'; DROP TABLE users;--` | No SQL execution |
| SEC-04 | Rate limiting | 200 rapid requests | 429 after limit |
| SEC-05 | CORS whitelist | Request from evil.com | Blocked |
| SEC-06 | File type check | Upload .exe file | Rejected |
| SEC-07 | File size limit | 15 MB file | Rejected |

---

## 3. Frontend Tests (Vitest)

### Running Tests

```bash
cd frontend
npx vitest run                    # All tests
npx vitest run --coverage         # With coverage
npx vitest --ui                   # Interactive UI
```

### Test Files (PLANNED)

| File | Scope | Test Count |
|------|-------|-----------|
| `__tests__/lib/auth.test.ts` | JWT verification, token creation | 4 |
| `__tests__/lib/utils.test.ts` | cn() utility | 3 |
| `__tests__/components/editor.test.tsx` | Editor rendering, toolbar | 7 |
| `__tests__/components/documents.test.tsx` | Document list, search | 5 |
| `__tests__/pages/login.test.tsx` | Login form, error handling | 4 |

### Test Cases

#### Editor Component - PLANNED

| ID | Case | Expected |
|----|------|----------|
| EDIT-01 | Editor renders | TipTap instance created |
| EDIT-02 | KaTeX math rendering | Inline/block formulas displayed |
| EDIT-03 | Slash menu trigger | `/` shows command list |
| EDIT-04 | AI button click | Triggers AI request |
| EDIT-05 | Auto-save trigger | Save request 1.5s after typing stops |
| EDIT-06 | Keyboard shortcuts | Ctrl+S, Ctrl+/ respond |
| EDIT-07 | Content recovery | Last saved content restored on reload |

#### Document Management - PLANNED

| ID | Case | Expected |
|----|------|----------|
| DM-01 | Document list loads | All documents displayed |
| DM-02 | Search filtering | List filters as user types |
| DM-03 | Folder expand/collapse | Sub-documents show/hide |
| DM-04 | New document | Creates and redirects to editor |
| DM-05 | Delete confirmation | Confirmation dialog, soft delete |

---

## 4. E2E Tests (Playwright)

### Setup (Phase 3)

```bash
cd frontend
npx playwright install
npx playwright test
```

### Critical Flow Tests

| ID | Flow | Steps |
|----|------|-------|
| E2E-01 | Document lifecycle | Login -> Create -> Edit -> AI Generate -> Save -> Export -> Delete |
| E2E-02 | RAG Q&A flow | Login -> Import doc -> Wait for index -> Ask question -> Verify source citation |
| E2E-03 | AI editing flow | Login -> Open doc -> Select text -> AI Polish -> Verify replacement |
| E2E-04 | Search flow | Login -> Create 5 docs -> Search keyword -> Verify filtered results |
| E2E-05 | Auth flow | Visit /documents -> Redirect to login -> Login -> Redirect to /documents |

---

## 5. Test Data Management

### Fixtures

- `conftest.py` provides `async_client` fixture with auto DB setup/teardown
- Admin user is auto-created in test setup
- Each test gets a clean database state

### Mock Strategy

| Component | Mock Approach |
|-----------|--------------|
| LLM APIs | `unittest.mock.AsyncMock` returning predefined responses |
| Embedding model | Mock `encode()` to return random vectors of correct dimension |
| File system | `tempfile.TemporaryDirectory` for export tests |
| Database | In-memory SQLite or dedicated test database |
| External services | `httpx.MockTransport` for HTTP calls |

---

## 6. CI/CD Integration

### GitHub Actions Workflow (Planned)

```yaml
name: Tests
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: cd backend && uv sync
      - run: cd backend && uv run pytest tests/ -v --cov=app --cov-report=xml
  
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - run: cd frontend && pnpm install
      - run: cd frontend && pnpm build
      - run: cd frontend && npx vitest run --coverage
  
  e2e:
    needs: [backend, frontend]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npx playwright test
```

---

## 7. Test Execution Summary

### Current Status (MVP)

| Category | Tests | Passing | Status |
|----------|-------|---------|--------|
| Backend Health | 1 | 1 | PASS |
| Backend Auth | 4 | 4 | PASS |
| Backend Documents | 6 | 6 | PASS |
| **Total** | **11** | **11** | **ALL PASS** |

### Planned Additions

| Phase | Tests Added | Total Tests |
|-------|------------|-------------|
| Phase 2 (AI) | +12 | 23 |
| Phase 3 (RAG) | +8 | 31 |
| Phase 4 (Export) | +9 | 40 |
| Phase 5 (Security) | +7 | 47 |
| Phase 6 (Frontend) | +23 | 70 |
| Phase 7 (E2E) | +5 | 75 |
