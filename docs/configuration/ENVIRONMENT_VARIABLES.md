# 环境变量参考

> Knowledge Base 后端所有环境变量的完整列表

## 配置方式

环境变量可以通过以下方式设置:

1. **`.env` 文件** (推荐): 在 `backend/` 目录下创建 `.env` 文件
2. **系统环境变量**: 通过 `export` 命令或系统环境变量设置
3. **Docker**: 通过 `docker-compose.yml` 的 `environment` 或 `env_file` 配置

## 完整变量列表

### 应用基础配置

| 变量名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `APP_NAME` | string | `Knowledge Base` | 否 | 应用名称 |
| `DEBUG` | bool | `false` | 否 | 调试模式, 开启后启用 API 文档 |

### 数据库配置

| 变量名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `DATABASE_URL` | string | `sqlite+aiosqlite:///./data/knowledge.db` | 否 | 数据库连接字符串 |

### JWT 认证配置

| 变量名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `JWT_SECRET_KEY` | string | 无 | **是** | JWT 签名密钥, 至少 32 字符 |
| `JWT_ALGORITHM` | string | `HS256` | 否 | JWT 签名算法 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | int | `15` | 否 | Access Token 有效期 (分钟) |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | int | `7` | 否 | Refresh Token 有效期 (天) |

### LLM 服务商配置

| 变量名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `LLM_PROVIDER` | string | `openai` | 否 | LLM 服务商 (`openai`, `anthropic`, `ollama`) |
| `OPENAI_API_KEY` | string | `""` | 否 | OpenAI API 密钥 |
| `ANTHROPIC_API_KEY` | string | `""` | 否 | Anthropic API 密钥 |
| `OLLAMA_BASE_URL` | string | `http://localhost:11434` | 否 | Ollama 服务地址 |
| `LLM_MODEL` | string | `gpt-4o` | 否 | 默认使用的模型名称 |

### 嵌入模型配置

| 变量名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `EMBEDDING_MODEL` | string | `BAAI/bge-m3` | 否 | HuggingFace 嵌入模型名称 |
| `EMBEDDING_DIMENSION` | int | `1024` | 否 | 嵌入向量维度 |

### 安全配置

| 变量名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `MAX_UPLOAD_SIZE_MB` | int | `10` | 否 | 文件上传大小限制 (MB) |
| `ADMIN_INITIAL_PASSWORD` | string | `""` | 否 | 管理员初始密码, 空则随机生成 |
| `INTERNAL_API_SECRET` | string | `""` | 否 | 内部 API 调用密钥 |

### CORS 配置

| 变量名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `CORS_ORIGINS` | string | `http://localhost:3000` | 否 | CORS 允许源 (逗号分隔) |

### 速率限制

| 变量名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `RATE_LIMIT_DEFAULT` | string | `100/minute` | 否 | 默认 API 速率限制 |
| `RATE_LIMIT_AI` | string | `10/minute` | 否 | AI 接口速率限制 |

---

## .env 文件模板

以下是一个完整的 `.env` 文件模板, 可根据需要修改:

```env
# ============================================
# Knowledge Base 后端配置
# ============================================

# -- 应用 --
APP_NAME=Knowledge Base
DEBUG=false

# -- 数据库 --
DATABASE_URL=sqlite+aiosqlite:///./data/knowledge.db

# -- JWT 认证 (必须设置!) --
# 生成密钥: python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_SECRET_KEY=your-strong-secret-key-at-least-32-chars-long
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# -- LLM 服务商 --
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=gpt-4o

# -- 嵌入模型 --
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024

# -- 安全 --
MAX_UPLOAD_SIZE_MB=10
ADMIN_INITIAL_PASSWORD=
INTERNAL_API_SECRET=

# -- CORS --
CORS_ORIGINS=http://localhost:3000

# -- 速率限制 --
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_AI=10/minute
```

---

## 前端环境变量

前端环境变量配置在 `frontend/.env.local` 中:

| 变量名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `NEXT_PUBLIC_BACKEND_URL` | string | `http://localhost:8000` | 后端 API 地址 (客户端使用) |

> **注意**: 以 `NEXT_PUBLIC_` 开头的变量会暴露给客户端代码, 不要在其中放置敏感信息。

---

## 优先级说明

环境变量的加载优先级 (从高到低):

1. 系统环境变量
2. `.env` 文件中的值
3. 代码中的默认值

这意味着系统环境变量会覆盖 `.env` 文件中的同名变量。
