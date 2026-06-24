# MCP 概述

> Model Context Protocol -- 让 AI 编辑器直接访问和操作知识库

## 什么是 MCP?

MCP (Model Context Protocol) 是一种开放协议, 允许 AI 应用程序 (如 Claude Desktop、Cursor、Windsurf 等) 安全地访问外部工具和数据源。

通过 MCP, 你可以:

- 在 AI 编辑器中直接**搜索知识库文档**
- 让 AI **读取和分析**知识库中的文档
- 通过 AI **创建和编辑**知识库文档
- 探索**知识图谱**中的实体和关系
- 管理**文件夹和标签**

## 架构

Knowledge Base 的 MCP 服务支持两种传输方式:

### SSE 传输 (Server-Sent Events)

```
AI 客户端 --HTTP/SSE--> Knowledge Base Server (/mcp/sse)
```

- 挂载在 FastAPI 应用的 `/mcp` 路径下
- 需要 Bearer Token 认证
- 适合远程服务器部署
- 支持多客户端同时连接

### Stdio 传输 (Standard Input/Output)

```
AI 客户端 --stdin/stdout--> python -m app.mcp.stdio_server
```

- 通过子进程方式运行
- 不需要单独的服务器
- 适合本地开发环境
- 由 AI 客户端直接启动和管理

## 可用工具

Knowledge Base MCP 提供以下工具:

### 文档搜索

| 工具 | 说明 |
|------|------|
| `search_documents` | 搜索知识库文档, 支持语义搜索和关键词搜索 |

**参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 搜索查询文本 |
| `top_k` | int | 否 | 返回结果数量 (1-20, 默认 5) |
| `search_type` | string | 否 | `semantic` (语义) 或 `keyword` (关键词) |

### 文档读取

| 工具 | 说明 |
|------|------|
| `read_document` | 按 ID 读取文档完整内容 |
| `list_documents` | 列出文档, 可按文件夹/标签筛选 |

### 文档管理

| 工具 | 说明 |
|------|------|
| `create_document` | 创建新文档 (Markdown 格式, 默认为草稿) |
| `update_document` | 更新文档标题或内容 (自动创建版本快照) |
| `delete_document` | 删除或归档文档 |
| `move_document` | 移动文档到其他文件夹或更改状态 |
| `manage_tags` | 添加或移除文档标签 |

### AI 分析

| 工具 | 说明 |
|------|------|
| `summarize_document` | 使用 AI 为文档生成摘要和关键词 |

### 知识图谱

| 工具 | 说明 |
|------|------|
| `search_knowledge_graph` | 搜索知识图谱中的实体和关系 |

**参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 搜索查询 |
| `depth` | int | 否 | 遍历深度 (1-4, 默认 2) |

### 文件夹和标签

| 工具 | 说明 |
|------|------|
| `list_folders` | 列出所有文件夹 |
| `list_tags` | 列出所有标签及文档数量 |

---

## 认证

### SSE 传输模式

SSE 模式要求所有请求携带 Bearer Token:

```
Authorization: Bearer <JWT_TOKEN>
```

获取 Token:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

响应中的 `access_token` 即为 Bearer Token。

### Stdio 传输模式

Stdio 模式由 AI 客户端直接启动子进程, 无需额外的认证步骤。

---

## 客户端配置指南

选择你的 AI 客户端, 查看对应的配置教程:

| 客户端 | 文档 |
|--------|------|
| Claude Desktop | [MCP Claude Desktop 配置](./MCP_CLAUDE_DESKTOP.md) |
| Cursor IDE | [MCP Cursor 配置](./MCP_CURSOR.md) |
| Windsurf | [MCP Windsurf 配置](./MCP_WINDSURF.md) |
| OpenAI Codex / ChatGPT | [MCP Codex 配置](./MCP_CODEX.md) |

遇到问题? 查看 [MCP 故障排查](./MCP_TROUBLESHOOTING.md)。

---

## 使用示例

### 示例: 搜索并阅读文档

在 Claude Desktop 中:

> "搜索知识库中关于'项目架构'的文档, 然后阅读排名第一的文档并给我一个摘要"

Claude 会自动调用:
1. `search_documents(query="项目架构")` -- 搜索
2. `read_document(document_id=<结果ID>)` -- 阅读
3. 生成摘要返回给你

### 示例: 创建文档

> "根据我们刚才讨论的内容, 创建一篇新的知识库文档, 标题为'技术方案', 放在'技术文档'文件夹下, 打上'方案'标签"

Claude 会调用:
1. `list_folders()` -- 找到文件夹 ID
2. `create_document(title="技术方案", content_markdown="...", folder_id=<ID>, tags=["方案"])` -- 创建文档
