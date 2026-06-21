# API 文档

本文档描述 Knowledge Base 系统的所有 REST API 端点。

## 基础信息

- **Base URL**: `http://localhost:8000`
- **认证方式**: JWT Bearer Token（除登录和健康检查外）
- **请求格式**: JSON
- **响应格式**: JSON

### 认证

所有需要认证的端点需要在请求头中携带：

```
Authorization: Bearer <access_token>
```

Token 通过 `/api/auth/login` 获取，有效期 15 分钟，可通过 `/api/auth/refresh` 刷新。

### 错误响应格式

```json
{
  "success": false,
  "code": "AUTH_1001",
  "message": "错误描述",
  "details": [],
  "request_id": "uuid"
}
```

### 通用错误码

| 错误码 | HTTP 状态 | 说明 |
|--------|-----------|------|
| `AUTH_1001` | 401 | 用户名或密码错误 |
| `AUTH_1002` | 401 | Token 已过期 |
| `AUTH_1003` | 401 | Token 无效 |
| `AUTH_1004` | 403 | 账号已禁用 |
| `AUTH_1005` | 403 | 权限不足 |
| `VAL_3001` | 422 | 参数验证失败 |
| `RES_2001` | 404 | 资源不存在 |
| `SYS_9001` | 500 | 服务器内部错误 |

---

## 认证模块 `/api/auth`

### POST `/api/auth/login`

用户登录，返回 JWT Token。

**请求体**:
```json
{
  "username": "admin",
  "password": "your_password"
}
```

**成功响应** (200):
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**错误响应**:
- 401: 用户名或密码错误
- 422: 参数验证失败（密码少于 6 位等）

---

### POST `/api/auth/refresh`

刷新 Access Token。

**请求体**:
```json
{
  "refresh_token": "eyJ..."
}
```

**成功响应** (200):
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

---

### GET `/api/auth/me`

获取当前用户信息。需要认证。

**成功响应** (200):
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@localhost",
  "is_admin": true
}
```

---

### POST `/api/auth/change-password`

修改密码。需要认证。

**请求体**:
```json
{
  "current_password": "old_password",
  "new_password": "new_password_123"
}
```

---

## 文档模块 `/api/documents`

### GET `/api/documents`

获取文档列表。需要认证。

**查询参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | int | 20 | 每页数量 |
| `offset` | int | 0 | 偏移量 |
| `status` | string | — | 筛选状态 (draft/published/archived) |
| `folder_id` | int | — | 筛选文件夹 |
| `tag` | string | — | 筛选标签 |
| `search` | string | — | 搜索关键词 |

**成功响应** (200):
```json
{
  "documents": [
    {
      "id": 1,
      "title": "文档标题",
      "status": "published",
      "folder_id": null,
      "version": 3,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-02T00:00:00Z",
      "tags": [{"id": 1, "name": "Python", "color": "#3B82F6"}]
    }
  ],
  "total": 100,
  "offset": 0,
  "limit": 20
}
```

---

### POST `/api/documents`

创建文档。需要认证。

**请求体**:
```json
{
  "title": "新文档",
  "content_json": {"type": "doc", "content": [...]},
  "folder_id": null
}
```

---

### GET `/api/documents/{doc_id}`

获取单个文档详情。需要认证。

---

### PUT `/api/documents/{doc_id}`

更新文档。需要认证。自动创建版本快照。

**请求体**:
```json
{
  "title": "更新后的标题",
  "content_json": {"type": "doc", "content": [...]},
  "folder_id": 2
}
```

---

### DELETE `/api/documents/{doc_id}`

软删除文档。需要认证。

---

### GET `/api/documents/{doc_id}/export`

导出文档。

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `format` | string | `markdown` / `html` / `latex` / `docx` |

---

## AI 模块 `/api/ai`

### POST `/api/ai/chat/stream`

AI 对话（SSE 流式）。需要认证。支持 MCP Tool Calling。

**请求体**:
```json
{
  "messages": [
    {"role": "user", "content": "帮我搜索关于 Python 的文档"}
  ],
  "system": "你是知识库助手"
}
```

**响应**: SSE 流，包含以下事件类型：
```
data: {"text": "正在搜索..."}
data: {"tool_call": {"name": "search_documents", "status": "calling"}}
data: {"tool_call": {"name": "search_documents", "status": "complete", "result": "{...}"}}
data: {"text": "找到了 3 篇相关文档..."}
data: [DONE]
```

---

### POST `/api/ai/edit/stream`

AI 文本编辑（SSE 流式）。需要认证。

**请求体**:
```json
{
  "text": "要编辑的文本",
  "operation": "polish",
  "context": "可选的上下文"
}
```

**支持的操作**:
| 操作 | 说明 |
|------|------|
| `polish` | 润色 |
| `expand` | 扩展 |
| `compress` | 压缩 |
| `translate_zh` | 翻译为中文 |
| `translate_en` | 翻译为英文 |
| `fix` | 修正语法 |

---

### POST `/api/ai/generate`

AI 文档生成。需要认证。

**请求体**:
```json
{
  "requirements": "编写一份 Python 入门教程",
  "title": "Python 基础教程",
  "document_type": "tutorial",
  "language": "zh",
  "max_sections": 8,
  "target_length": "medium",
  "folder_id": null,
  "tags": ["Python", "教程"]
}
```

**成功响应** (200):
```json
{
  "document_id": 42,
  "title": "Python 基础教程",
  "content_json": {"type": "doc", "content": [...]},
  "sections_generated": 8
}
```

---

## 设置模块 `/api/settings`

### GET `/api/settings/system`

获取系统设置。需要管理员权限。

### PUT `/api/settings/system`

更新系统设置。需要管理员权限。

**请求体**:
```json
{
  "settings": {
    "app_name": "我的知识库",
    "llm_provider": "mimo",
    "llm_model": "mimo-v2.5-pro",
    "openai_api_key": "sk-...",
    "openai_base_url": "https://api.xiaomi.com/v1"
  }
}
```

### POST `/api/settings/test-llm`

测试 LLM 连接。需要管理员权限。

**请求体**:
```json
{
  "provider": "mimo",
  "model": "mimo-v2.5-pro",
  "api_key": "sk-...",
  "base_url": "https://api.xiaomi.com/v1"
}
```

---

## API 路由模块 `/api/api-routes`

### GET `/api/api-routes/providers`

获取供应商模板列表。需要认证。

### POST `/api/api-routes/endpoints`

创建 API 端点。需要管理员权限。

**请求体**:
```json
{
  "name": "小米 MIMO",
  "provider": "mimo",
  "base_url": "https://api.xiaomi.com/v1",
  "api_key": "sk-...",
  "protocol": "openai",
  "supported_models": ["mimo-v2.5-pro", "mimo-v2.5-flash"],
  "priority": 100,
  "protocol_mode": "auto"
}
```

### POST `/api/api-routes/endpoints/{id}/test`

测试端点连接。需要管理员权限。

### GET `/api/api-routes/health`

获取端点健康状态。需要认证。

### GET `/api/api-routes/resolve`

解析最佳端点。需要认证。

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | string | 模型名称 |

---

## 工作流模块 `/api/workflows`

### GET `/api/workflows/templates`

获取预设模板列表。需要认证。

### POST `/api/workflows`

创建工作流。需要认证。

**请求体**:
```json
{
  "name": "文档标准化流程",
  "description": "自动分析、润色、打标签",
  "config_json": {
    "nodes": [...],
    "edges": [...]
  }
}
```

### POST `/api/workflows/execute`

执行工作流。需要认证。

**请求体**:
```json
{
  "workflow_id": 1,
  "input_data": {"document_ids": [1, 2, 3]}
}
```

---

## 提示词模板 `/api/prompts`

### GET `/api/prompts/templates`

获取提示词模板列表。需要认证。

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `category` | string | `edit` / `workflow` / `chat` / `generate` / `custom` |

### POST `/api/prompts/templates`

创建提示词模板。需要认证。

**请求体**:
```json
{
  "name": "技术文档润色",
  "description": "润色技术文档，保持专业性",
  "category": "edit",
  "system_prompt": "你是一个专业的技术文档编辑...",
  "input_variables": ["text", "language"],
  "output_format": "text"
}
```

### POST `/api/prompts/templates/{id}/execute`

执行提示词模板。需要认证。

**请求体**:
```json
{
  "variables": {"language": "中文"},
  "input_text": "要处理的文本"
}
```

---

## MCP 协议

### SSE 传输

```
URL: http://localhost:8000/mcp/sse
认证: Authorization: Bearer <jwt_token>
```

### Stdio 传输

```bash
python -m app.mcp.stdio_server
```

### MCP 工具

| 工具名 | 参数 | 说明 |
|--------|------|------|
| `search_documents` | `query`, `top_k`, `search_type` | 搜索文档 |
| `read_document` | `document_id` | 读取文档 |
| `list_documents` | `folder_id`, `tag_name`, `status`, `limit` | 列出文档 |
| `create_document` | `title`, `content_markdown`, `folder_id`, `tags`, `status` | 创建文档 |
| `update_document` | `document_id`, `title`, `content_markdown` | 更新文档 |
| `delete_document` | `document_id`, `permanent` | 删除/归档文档 |
| `move_document` | `document_id`, `folder_id`, `status` | 移动文档 |
| `manage_tags` | `document_id`, `add_tags`, `remove_tags` | 管理标签 |
| `summarize_document` | `document_id` | AI 摘要 |
| `analyze_document` | `document_id` | AI 分析 |
| `search_knowledge_graph` | `query`, `depth` | 知识图谱搜索 |
| `get_document_versions` | `document_id` | 版本历史 |
| `get_folder_tree` | — | 文件夹树 |
| `list_folders` | — | 文件夹列表 |
| `list_tags` | — | 标签列表 |

### MCP 资源

| URI | 说明 |
|-----|------|
| `kb://documents` | 已发布文档列表 |
| `kb://documents/{id}` | 指定文档内容 |
| `kb://folders` | 文件夹列表 |
| `kb://tags` | 标签列表 |
| `kb://stats` | 统计概览 |

### MCP 提示

| 名称 | 参数 | 说明 |
|------|------|------|
| `review_document` | `document_id` | 文档审查提示 |
| `summarize_topic` | `topic` | 主题总结提示 |
| `compare_documents` | `document_id_1`, `document_id_2` | 文档对比提示 |
| `write_from_requirements` | `requirements` | 按需求写作提示 |
| `organize_knowledge_base` | — | 知识库整理提示 |
