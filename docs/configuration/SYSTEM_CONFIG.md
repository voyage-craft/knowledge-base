# 系统配置参考

> Knowledge Base 系统所有配置项的完整说明

## 配置方式

Knowledge Base 支持两种配置方式:

1. **环境变量 / `.env` 文件**: 用于启动时的基础配置
2. **Web 界面设置**: 运行时通过 "设置 -> 系统配置" 动态修改, 存储在数据库 `system_settings` 表中

## 核心系统设置

### JWT 认证配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| JWT 密钥 | `JWT_SECRET_KEY` | **必填** | JWT 签名密钥, 至少 32 字符 |
| 签名算法 | `JWT_ALGORITHM` | `HS256` | JWT 签名算法 |
| Access Token 过期 | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access Token 有效期 (分钟) |
| Refresh Token 过期 | `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh Token 有效期 (天) |

#### 生成安全的 JWT 密钥

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

#### 弱密钥检测

系统内置了弱密钥检测, 以下值会被拒绝:

- `dev-secret-change-in-production`
- `secret`
- `change-me`
- `your-secret-key`
- `jwt-secret`

且密钥长度少于 32 个字符也会被拒绝。

### 调试模式

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| 调试模式 | `DEBUG` | `false` | 开启后启用 API 文档和详细日志 |

调试模式开启后:

- Swagger API 文档可在 `/api/docs` 访问
- ReDoc 文档可在 `/api/redoc` 访问
- 日志输出更加详细

> **警告**: 生产环境请务必关闭调试模式, 避免暴露 API 文档。

### CORS 配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| 允许源 | `CORS_ORIGINS` | `http://localhost:3000` | 允许跨域请求的源 (逗号分隔) |

配置示例:

```env
# 单个源
CORS_ORIGINS=http://localhost:3000

# 多个源
CORS_ORIGINS=http://localhost:3000,https://kb.your-domain.com

# 开发环境允许所有本地端口
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:8080
```

CORS 中间件配置:

| 设置 | 值 |
|------|-----|
| allow_credentials | `true` |
| allow_methods | `GET, POST, PUT, DELETE, OPTIONS` |
| allow_headers | `Authorization, Content-Type` |
| max_age | `600` 秒 |

### 速率限制

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| 默认限制 | `RATE_LIMIT_DEFAULT` | `100/minute` | 通用 API 请求速率限制 |
| AI 接口限制 | `RATE_LIMIT_AI` | `10/minute` | AI 相关接口的速率限制 |

速率限制基于客户端 IP 地址, 使用 `slowapi` 中间件实现。

速率限制格式: `<次数>/<时间单位>`

| 时间单位 | 示例 |
|----------|------|
| second | `10/second` |
| minute | `100/minute` |
| hour | `1000/hour` |
| day | `10000/day` |

### 安全配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| 最大上传大小 | `MAX_UPLOAD_SIZE_MB` | `10` | 文件上传大小限制 (MB) |
| 管理员初始密码 | `ADMIN_INITIAL_PASSWORD` | 空 (随机生成) | 首次启动时的管理员密码 |
| 内部 API 密钥 | `INTERNAL_API_SECRET` | 空 | 服务端间调用的密钥 |

### 数据库配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| 数据库 URL | `DATABASE_URL` | `sqlite+aiosqlite:///./data/knowledge.db` | 数据库连接字符串 |

默认使用 SQLite, 数据库文件自动创建在 `backend/data/knowledge.db`。

### LLM 配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| LLM 服务商 | `LLM_PROVIDER` | `openai` | LLM 服务提供商 |
| OpenAI Key | `OPENAI_API_KEY` | 空 | OpenAI API 密钥 |
| Anthropic Key | `ANTHROPIC_API_KEY` | 空 | Anthropic API 密钥 |
| Ollama 地址 | `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 服务地址 |
| 默认模型 | `LLM_MODEL` | `gpt-4o` | 默认使用的模型名称 |
| 嵌入模型 | `EMBEDDING_MODEL` | `BAAI/bge-m3` | 文本嵌入模型 |
| 嵌入维度 | `EMBEDDING_DIMENSION` | `1024` | 嵌入向量维度 |

详细的 LLM 配置请参阅 [LLM 服务商配置](./LLM_PROVIDERS.md)。

---

## 安全响应头

系统自动添加以下安全响应头:

| 响应头 | 值 | 说明 |
|--------|-----|------|
| `X-Request-ID` | UUID | 请求追踪 ID |
| `X-Process-Time` | 秒数 | 请求处理耗时 |
| `X-Content-Type-Options` | `nosniff` | 防止 MIME 类型嗅探 |
| `X-Frame-Options` | `DENY` | 禁止 iframe 嵌套 |
| `X-XSS-Protection` | `0` | XSS 过滤 (现代浏览器不需要) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Referrer 策略 |
| `Permissions-Policy` | 限制设备 API | 禁止地理位置、麦克风、摄像头 |
| `Strict-Transport-Security` | HSTS | 强制 HTTPS |

---

## 中间件栈

系统按以下顺序加载中间件:

1. **自定义 HTTP 中间件** -- 请求 ID、安全响应头、性能监控
2. **GZip 压缩** -- 响应体 > 1000 字节时自动压缩
3. **CORS** -- 跨域资源共享
4. **SlowAPI** -- 速率限制

---

## Web 界面系统配置

除了环境变量, 还可以在 Web 界面中动态修改部分系统设置:

1. 登录管理员账号
2. 进入 "设置" -> "系统配置"
3. 修改配置项并保存

[截图占位]

Web 界面配置存储在数据库 `system_settings` 表中, 运行时修改即时生效, 无需重启服务。
