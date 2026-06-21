# Security Policy - Knowledge Base Management System

## Overview

This document outlines the security architecture, policies, and best practices for the Knowledge Base Management System.

---

## 1. Authentication & Authorization

### JWT Authentication

The system uses HS256 JWT tokens for API authentication with the following configuration:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Algorithm | HS256 | Symmetric, suitable for single-service deployment |
| Access Token TTL | 15 minutes | Limits exposure window if token is compromised |
| Refresh Token TTL | 7 days | Balances convenience with security |
| Secret Key | 256-bit minimum | Must be changed in production |

### Token Storage

- **Access token**: Stored as `httpOnly` cookie (not accessible via JavaScript)
- **Refresh token**: Stored as `httpOnly` cookie with `Secure` flag in production
- Both cookies use `SameSite=Lax` to prevent CSRF attacks

### Password Security

- Passwords are hashed using bcrypt (cost factor 12)
- Minimum password length: 6 characters (MVP), recommended 8+ for production
- `passlib` library handles hashing with automatic algorithm detection

### Single-User Mode

The system operates in single-user mode by default. An admin account (`admin`/`admin123`) is auto-created on first startup. **This default password MUST be changed before any production deployment.**

---

## 2. Input Validation & Sanitization

### API Input Validation

All API inputs are validated using Pydantic v2 with strict mode:

- String fields enforce `min_length` and `max_length` constraints
- Integer fields enforce range limits (`ge`, `le`)
- JSON content is validated against expected schemas
- Unknown fields are rejected by default

### LaTeX Content Sanitization

LaTeX content is scanned for dangerous commands before compilation:

```
Blocked commands: \input, \include, \write18, \ShellEscape, \immediate,
\openout, \special, \pdfoutput, \pdffilemoddate, \pdffilesize,
\pdfmdfivesum, \pdfcreationdate, \pdfmatch, \pdfstrcmp, \pdffiledump
```

### XSS Prevention

- All document content is stored as JSON (TipTap format) and rendered via React's built-in escaping
- `dangerouslySetInnerHTML` is never used for user-generated content
- API responses use `Content-Type: application/json`

### SQL Injection Prevention

- All database queries use SQLAlchemy ORM with parameterized queries
- Raw SQL is never used with user input
- Drizzle ORM on the frontend also uses parameterized queries

---

## 3. LaTeX Compilation Sandbox

LaTeX compilation is the highest-risk operation in the system. The following controls are implemented:

### Compilation Restrictions

| Control | Implementation |
|---------|---------------|
| Shell escape disabled | `-no-shell-escape` flag passed to xelatex/pdflatex |
| File output restricted | `openout_any=p` environment variable |
| Output directory locked | `TEXMFOUTPUT` set to compilation temp directory |
| Compilation timeout | 120 seconds max, process killed on timeout |
| Directory whitelist | Compilation only in designated sandbox directories |

### Docker Isolation (Production)

In production deployments, LaTeX compilation runs in an ephemeral Docker container with:

- CPU limit: 2 cores
- Memory limit: 1GB
- No network access
- Read-only root filesystem
- Temporary `/tmp` for compilation output

### Windows Development

On Windows (no Docker), compilation relies on:

- Subprocess resource limits via `asyncio.wait_for` timeout
- Environment variable restrictions (`openout_any`, `TEXMFOUTPUT`)
- Dedicated sandbox directory with restricted write permissions

---

## 4. Rate Limiting

Rate limiting is enforced via `slowapi` middleware:

| Endpoint Group | Limit | Window |
|---------------|-------|--------|
| Global default | 100 requests | Per minute per IP |
| AI endpoints | 10 requests | Per minute per IP |
| Login endpoint | 5 requests | Per minute per IP |
| Export endpoints | 3 requests | Per minute per IP |

Rate limit headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`) are included in responses.

---

## 5. CORS Policy

### Development

```
allow_origins = ["http://localhost:3000"]
allow_credentials = True
allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
allow_headers = ["Authorization", "Content-Type"]
max_age = 600
```

### Production

- Replace `localhost` with the actual frontend domain
- Never use `allow_origins = ["*"]` in production
- Consider using a reverse proxy (Caddy/Nginx) for additional CORS control

---

## 6. File Upload Security

### Restrictions

| Control | Value |
|---------|-------|
| Max file size | 10 MB |
| Allowed MIME types | `image/png`, `image/jpeg`, `image/gif`, `image/webp`, `application/pdf` |
| Storage path | Randomized UUID-based filenames |
| Upload directory | Isolated from compilation sandbox |

### Validation

- MIME type is checked via file header inspection (not just extension)
- File size is validated before processing
- Uploaded files are stored with randomized names to prevent path traversal

---

## 7. Dependency Security

### Monitoring

- **npm**: Run `npm audit` regularly; configure Dependabot for automated updates
- **pip**: Run `pip audit` regularly; use `uv lock` for deterministic builds
- Review security advisories for: Next.js, FastAPI, TipTap, SQLAlchemy, PyJWT

### Known Constraints

- `better-sqlite3` requires native compilation (node-gyp); ensure VS2022 Build Tools are installed
- `bcrypt` is pinned to `>=4.0.0,<4.1.0` for `passlib` compatibility
- `sentence-transformers` downloads models on first use; ensure network access or pre-cache models

---

## 8. Production Deployment Checklist

Before deploying to production:

- [ ] Change `JWT_SECRET_KEY` to a strong random value (256+ bits)
- [ ] Change admin default password
- [ ] Set `DEBUG=false`
- [ ] Configure HTTPS (via Caddy auto-SSL or reverse proxy)
- [ ] Update CORS origins to production domain
- [ ] Set `RATE_LIMIT_DEFAULT` appropriate for expected traffic
- [ ] Migrate from SQLite to PostgreSQL + pgvector
- [ ] Install TeX Live for PDF export capability
- [ ] Set up automated backups for the database
- [ ] Configure log aggregation and alerting
- [ ] Run `npm audit` and `pip audit` to check for vulnerabilities
- [ ] Enable Docker sandbox for LaTeX compilation

---

## 9. Incident Response

### Security Event Logging

All authentication events (login success/failure, token refresh, unauthorized access) are logged with:

- Timestamp
- Source IP
- User ID (if available)
- Event type and outcome
- User-Agent string

### Response Procedure

1. **Detection**: Monitor logs for anomalous patterns (brute force, unusual access patterns)
2. **Containment**: Revoke affected tokens, block source IPs
3. **Investigation**: Review logs, identify scope of compromise
4. **Remediation**: Patch vulnerability, rotate secrets
5. **Communication**: Notify affected users if data was exposed
