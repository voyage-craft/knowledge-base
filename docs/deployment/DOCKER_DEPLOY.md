# Docker 部署指南

> 使用 Docker 容器化部署 Knowledge Base 系统, 适用于服务器和生产环境

## 前置条件

| 依赖 | 版本要求 |
|------|----------|
| Docker | 20.10+ |
| Docker Compose | 2.0+ |

## 快速部署 (Docker Compose)

### 1. 准备配置文件

在项目根目录创建 `.env` 文件:

```env
# JWT 密钥 (必须设置, 至少 32 个字符)
JWT_SECRET_KEY=your-strong-secret-key-at-least-32-chars-long

# 调试模式 (生产环境请设为 false)
DEBUG=false

# CORS 允许的源 (按实际域名修改)
CORS_ORIGINS=https://your-domain.com

# LLM 服务商配置
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key
```

> **生成安全密钥**:
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(48))"
> ```

### 2. 使用现有 docker-compose.yml

项目已包含 `docker-compose.yml`, 内容如下:

```yaml
version: "3.8"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - backend-data:/app/data
    env_file:
      - ./backend/.env
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///./data/knowledge.db
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - NEXT_PUBLIC_BACKEND_URL=http://backend:8000
    ports:
      - "3000:3000"
    env_file:
      - ./frontend/.env.local
    environment:
      - BACKEND_URL=http://backend:8000
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  backend-data:
```

### 3. 启动服务

```bash
# 构建并启动所有服务
docker compose up -d --build

# 查看日志
docker compose logs -f

# 查看服务状态
docker compose ps
```

### 4. 访问系统

- **前端**: http://localhost:3000
- **后端 API**: http://localhost:8000
- **API 文档** (仅 DEBUG 模式): http://localhost:8000/api/docs

默认登录: `admin` / `admin123`

---

## Dockerfile 详解

### 后端 Dockerfile

位于 `backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim AS base

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 8000

# 使用 uvicorn 运行
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### 前端 Dockerfile

位于 `frontend/Dockerfile`, 使用多阶段构建:

```dockerfile
FROM node:20-alpine AS base

# 安装依赖
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# 构建
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_BACKEND_URL
ENV NEXT_PUBLIC_BACKEND_URL=${NEXT_PUBLIC_BACKEND_URL}
RUN npm run build

# 生产运行
FROM base AS runner
WORKDIR /app
ENV NODE_ENV production
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV PORT 3000
ENV HOSTNAME "0.0.0.0"
CMD ["node", "server.js"]
```

---

## 环境变量参考

### 后端环境变量

| 变量 | 说明 | 默认值 | 必填 |
|------|------|--------|------|
| `JWT_SECRET_KEY` | JWT 签名密钥 (至少 32 字符) | 无 | 是 |
| `JWT_ALGORITHM` | JWT 签名算法 | `HS256` | 否 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 过期时间 (分钟) | `15` | 否 |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh Token 过期时间 (天) | `7` | 否 |
| `DEBUG` | 调试模式 | `false` | 否 |
| `DATABASE_URL` | 数据库连接字符串 | `sqlite+aiosqlite:///./data/knowledge.db` | 否 |
| `CORS_ORIGINS` | CORS 允许的源 (逗号分隔) | `http://localhost:3000` | 否 |
| `LLM_PROVIDER` | LLM 服务商 | `openai` | 否 |
| `OPENAI_API_KEY` | OpenAI API Key | 空 | 否 |
| `ANTHROPIC_API_KEY` | Anthropic API Key | 空 | 否 |
| `OLLAMA_BASE_URL` | Ollama 服务地址 | `http://localhost:11434` | 否 |
| `RATE_LIMIT_DEFAULT` | 默认速率限制 | `100/minute` | 否 |
| `RATE_LIMIT_AI` | AI 接口速率限制 | `10/minute` | 否 |
| `MAX_UPLOAD_SIZE_MB` | 最大上传文件大小 (MB) | `10` | 否 |

### 前端环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `NEXT_PUBLIC_BACKEND_URL` | 后端 API 地址 | `http://localhost:8000` |
| `BACKEND_URL` | 后端内部通信地址 (SSR) | `http://backend:8000` |

---

## 数据持久化

### 卷挂载

```yaml
volumes:
  backend-data:        # 数据库文件 (knowledge.db)
```

数据存储在 Docker 命名卷 `backend-data` 中, 包含:

- `knowledge.db` -- SQLite 数据库文件
- 上传的文档文件

### 绑定挂载 (可选)

如需将数据目录绑定到宿主机:

```yaml
services:
  backend:
    volumes:
      - ./data:/app/data     # 绑定挂载到宿主机 ./data 目录
```

> **注意**: 使用绑定挂载时, 确保宿主机目录有正确的读写权限。

### 备份数据

```bash
# 备份数据库
docker compose exec backend cp /app/data/knowledge.db /app/data/knowledge.db.bak
docker cp $(docker compose ps -q backend):/app/data/knowledge.db.bak ./backup/

# 或使用卷直接备份
docker run --rm -v $(docker volume inspect knowledge-base_backend-data --format '{{ .Mountpoint }}'):/source -v $(pwd)/backup:/backup alpine tar czf /backup/kb-data-$(date +%Y%m%d).tar.gz -C /source .
```

---

## 生产环境部署建议

### 使用反向代理

推荐使用 Nginx 作为反向代理:

```nginx
server {
    listen 443 ssl;
    server_name kb.your-domain.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # 前端
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 20M;
    }

    # MCP SSE
    location /mcp/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;        # SSE 需要关闭缓冲
        proxy_cache off;
    }
}
```

### 资源限制

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "2.0"
        reservations:
          memory: 512M
          cpus: "0.5"
```

---

## 常用命令

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 重新构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f backend
docker compose logs -f frontend

# 进入后端容器
docker compose exec backend bash

# 重启单个服务
docker compose restart backend

# 清理未使用的镜像
docker compose down --rmi local
```

## 故障排查

### 容器启动失败

```bash
# 查看容器状态
docker compose ps -a

# 查看详细日志
docker compose logs backend --tail=100

# 检查环境变量是否正确传入
docker compose exec backend env | grep JWT
```

### 数据库损坏

```bash
# 进入容器检查数据库
docker compose exec backend sqlite3 /app/data/knowledge.db ".tables"

# 如数据卷损坏, 删除卷重建 (会丢失所有数据!)
docker compose down -v
docker compose up -d --build
```
