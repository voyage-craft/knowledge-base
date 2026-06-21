# 📚 Knowledge Base — AI 驱动的知识管理系统

<p align="center">
  <strong>智能文档管理 · AI 对话 · RAG 检索 · 知识图谱 · 工作流自动化 · MCP 协议</strong>
</p>

---

## ✨ 核心功能

### 📝 文档管理
- **富文本编辑器** — 基于 TipTap v3，支持标题、列表、代码块、图片、表格、任务列表
- **版本控制** — 每次编辑自动保存快照，支持版本对比和回滚
- **文件夹 & 标签** — 多层级文件夹组织，灵活的标签分类系统
- **批量导入** — 支持 Markdown、DOCX、PDF、LaTeX、TXT 格式，保留结构化格式
- **多格式导出** — 导出为 Markdown、HTML、LaTeX、DOCX

### 🤖 AI 能力
- **智能对话** — 基于知识库内容的 RAG 增强对话，支持上下文引用
- **文本编辑** — 6 种 AI 操作：润色、扩展、压缩、中英翻译、语法修正
- **文档生成** — 根据需求描述自动生成结构化文档
- **智能分析** — 自动摘要、关键词提取、标签推荐、质量评分
- **知识图谱** — 自动提取实体关系，可视化知识网络

### 🔌 API 路由系统
- **多端点管理** — 支持同时配置多个 AI 提供商端点
- **智能调度** — 基于健康评分的自动路由，优先级排序
- **故障转移** — 端点失败自动切换，渐进式冻结恢复
- **协议适配** — 自动探测 Chat Completions / Responses API
- **连接池** — HTTP 客户端缓存复用，减少连接开销

### 🔧 工作流引擎
- **可视化编辑** — ReactFlow 拖拽式工作流设计
- **15 种节点类型** — 文档源、AI 处理、条件分支、循环、人工审批、导出
- **12 个预设模板** — 一键创建常用工作流
- **定时执行** — Cron 表达式定时调度
- **V2 引擎** — DAG 执行、并行分支、逐节点追踪

### 🔗 MCP 协议支持
- **15 个工具** — 搜索、读取、创建、更新、删除、分析文档
- **5 个资源** — 文档列表、文件夹、标签、统计
- **5 个提示模板** — 文档审查、主题总结、文档对比
- **双传输模式** — SSE（远程）+ Stdio（本地 Claude Desktop）
- **Tool Calling** — AI 聊天自动调用 MCP 工具

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 16)                  │
│  React 19 · TipTap v3 · ReactFlow · shadcn/ui · AI SDK  │
├─────────────────────────────────────────────────────────┤
│                    Backend (FastAPI)                       │
│  SQLAlchemy · Pydantic · JWT Auth · Rate Limiting         │
├──────────────┬──────────────┬───────────────────────────┤
│   SQLite     │  AI Router   │      MCP Server            │
│   + WAL      │  Multi-EP    │   SSE + Stdio Transport    │
│              │  Failover    │   15 Tools · 5 Resources   │
└──────────────┴──────────────┴───────────────────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS |
| 编辑器 | TipTap v3 · ProseMirror |
| 工作流 | ReactFlow · DAG 引擎 |
| UI 组件 | shadcn/ui · Radix UI · Lucide Icons |
| AI SDK | Vercel AI SDK · @ai-sdk/openai · @ai-sdk/anthropic |
| 后端 | FastAPI · SQLAlchemy 2.0 · Pydantic v2 |
| 数据库 | SQLite (WAL mode) · 可迁移至 PostgreSQL |
| 认证 | JWT (PyJWT) · bcrypt |
| AI 模型 | OpenAI · Anthropic · 智谱 GLM · 通义千问 · DeepSeek · 小米 MIMO · Moonshot |
| MCP | mcp Python SDK · SSE + Stdio 传输 |

---

## 🚀 快速开始

### 环境要求

- **Python** 3.11+
- **Node.js** 18+
- **npm** 9+

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/knowledge-base.git
cd knowledge-base
```

### 2. 配置环境变量

```bash
# 后端
cp backend/.env.example backend/.env

# 前端
cp frontend/.env.example frontend/.env.local
```

**必须配置的变量：**

```bash
# 生成 JWT 密钥（两端必须一致）
python -c "import secrets; print(secrets.token_urlsafe(48))"

# backend/.env
JWT_SECRET_KEY=<生成的密钥>
ADMIN_INITIAL_PASSWORD=<你的管理员密码>

# frontend/.env.local
JWT_SECRET_KEY=<与后端相同的密钥>
BACKEND_URL=http://localhost:8000
```

### 3. 启动后端

```bash
cd backend
pip install -e .
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

首次启动会：
- 自动创建数据库和表
- 生成管理员账号（密码见终端输出或 `.env` 中的 `ADMIN_INITIAL_PASSWORD`）
- 预加载嵌入模型（如已安装 sentence-transformers）

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000，使用管理员账号登录。

### 5. Docker 部署（可选）

```bash
# 配置环境变量后
docker-compose up -d --build
```

---

## 🔌 MCP 配置

### Claude Desktop / Cursor / Windsurf（Stdio 传输）

在 MCP 客户端配置文件中添加：

```json
{
  "mcpServers": {
    "knowledge-base": {
      "command": "python",
      "args": ["-m", "app.mcp.stdio_server"],
      "cwd": "/path/to/knowledge-base/backend"
    }
  }
}
```

配置文件位置：
- **Claude Desktop**: `~/.claude/claude_desktop_config.json`
- **Cursor**: `.cursor/mcp.json`
- **Windsurf**: `.windsurf/mcp.json`

### 远程 SSE 传输

```bash
# 获取 JWT token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'

# 连接 MCP SSE
# URL: http://localhost:8000/mcp/sse
# Header: Authorization: Bearer <token>
```

### MCP 工具列表

| 工具 | 功能 | 示例 |
|------|------|------|
| `search_documents` | 语义搜索知识库 | "搜索关于机器学习的文档" |
| `read_document` | 读取指定文档 | "读取文档 #42" |
| `create_document` | 创建新文档 | "创建一份 Python 教程" |
| `update_document` | 更新文档内容 | "更新文档 #42 的摘要" |
| `analyze_document` | AI 深度分析 | "分析文档 #42 的质量" |
| `search_knowledge_graph` | 知识图谱搜索 | "搜索与 AI 相关的实体" |

### MCP 资源

| 资源 | 说明 |
|------|------|
| `kb://documents` | 所有已发布文档列表 |
| `kb://documents/{id}` | 指定文档的完整内容 |
| `kb://folders` | 文件夹层级结构 |
| `kb://tags` | 标签及文档数量 |
| `kb://stats` | 知识库统计数据 |

### MCP 提示模板

| 提示 | 用途 |
|------|------|
| `review_document` | 文档审查（准确性、完整性、可读性） |
| `summarize_topic` | 跨文档主题总结 |
| `compare_documents` | 两篇文档对比分析 |
| `write_from_requirements` | 按需求创建文档 |
| `organize_knowledge_base` | 知识库整理建议 |

---

## 📡 API 文档

启动后端后访问：
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

### 主要 API 模块

| 模块 | 路径前缀 | 功能 |
|------|----------|------|
| 认证 | `/api/auth` | 登录、注册、Token 刷新 |
| 文档 | `/api/documents` | CRUD、批量操作、版本管理、导入导出 |
| AI | `/api/ai` | 聊天、编辑、生成、分析 |
| 设置 | `/api/settings` | 系统配置、LLM 配置、提示词管理 |
| 文件夹 | `/api/folders` | 文件夹 CRUD |
| 标签 | `/api/tags` | 标签 CRUD、文档标签管理 |
| 知识图谱 | `/api/graph` | 图谱构建、查询、可视化 |
| 导入 | `/api/import` | 批量文件导入、AI 分析 |
| RAG | `/api/rag` | 嵌入生成、语义搜索 |
| 工作流 | `/api/workflows` | 工作流 CRUD、执行、调度 |
| API 路由 | `/api/api-routes` | 多端点管理、健康监控 |
| 管理 | `/api/admin` | 用户管理 |
| 提示词 | `/api/prompts` | 自定义提示词模板 |
| 评论 | `/api/comments` | 文档评论、审批 |

---

## 🌐 支持的 AI 提供商

| 提供商 | 协议 | 默认地址 |
|--------|------|----------|
| OpenAI | Chat Completions / Responses | https://api.openai.com/v1 |
| Anthropic | Messages | https://api.anthropic.com |
| 智谱 AI (GLM) | Chat Completions | https://open.bigmodel.cn/api/paas/v4 |
| 通义千问 (Qwen) | Chat Completions | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| DeepSeek | Chat Completions | https://api.deepseek.com/v1 |
| 小米 MIMO | Chat Completions | https://api.xiaomi.com/v1 |
| 硅基流动 (SiliconFlow) | Chat Completions | https://api.siliconflow.cn/v1 |
| 月之暗面 (Moonshot) | Chat Completions | https://api.moonshot.cn/v1 |
| Ollama (本地) | Chat Completions | http://localhost:11434/v1 |

配置方式：**设置 → API 路由 → 快速添加端点**

---

## 📁 项目结构

```
knowledge-base/
├── backend/
│   ├── app/
│   │   ├── api/              # API 路由
│   │   │   ├── auth.py       # 认证
│   │   │   ├── documents.py  # 文档 CRUD
│   │   │   ├── ai.py         # AI 功能
│   │   │   ├── settings.py   # 系统设置
│   │   │   ├── api_routes.py # API 路由管理
│   │   │   └── ...
│   │   ├── core/             # 核心模块
│   │   │   ├── config.py     # 配置管理
│   │   │   ├── database.py   # 数据库连接
│   │   │   └── security.py   # JWT/密码
│   │   ├── models/           # SQLAlchemy 模型
│   │   ├── schemas/          # Pydantic 模式
│   │   ├── services/         # 业务逻辑
│   │   │   ├── api_router.py # 智能路由
│   │   │   ├── llm_service.py# LLM 服务
│   │   │   ├── workflow/     # 工作流引擎
│   │   │   └── ...
│   │   └── mcp/              # MCP 服务器
│   │       ├── server.py     # MCP 入口
│   │       ├── tools/        # MCP 工具
│   │       ├── resources.py  # MCP 资源
│   │       └── prompts.py    # MCP 提示
│   ├── tests/                # 测试套件
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js 页面
│   │   │   ├── (auth)/       # 登录页
│   │   │   ├── (main)/       # 主界面
│   │   │   └── api/          # API 代理路由
│   │   ├── components/       # React 组件
│   │   │   ├── settings/     # 设置页面组件
│   │   │   ├── workflows/    # 工作流编辑器
│   │   │   └── ui/           # 基础 UI 组件
│   │   └── lib/              # 工具库
│   │       ├── api-client.ts # API 客户端
│   │       └── ai-server-utils.ts
│   ├── next.config.ts
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## ⚙️ 环境变量参考

### 后端 (`backend/.env`)

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `JWT_SECRET_KEY` | ✅ | — | JWT 签名密钥，至少 32 字符 |
| `DATABASE_URL` | ❌ | `sqlite+aiosqlite:///./data/knowledge.db` | 数据库连接串 |
| `DEBUG` | ❌ | `false` | 调试模式 |
| `ADMIN_INITIAL_PASSWORD` | ❌ | 自动生成 | 初始管理员密码 |
| `CORS_ORIGINS` | ❌ | `http://localhost:3000` | CORS 源（逗号分隔） |
| `INTERNAL_API_SECRET` | ❌ | `kb-internal-secret-change-me` | 内部 API 密钥 |
| `LLM_PROVIDER` | ❌ | `openai` | 默认 LLM 提供商 |
| `LLM_MODEL` | ❌ | `gpt-4o` | 默认模型 |
| `OPENAI_API_KEY` | ❌ | — | OpenAI API Key |
| `ANTHROPIC_API_KEY` | ❌ | — | Anthropic API Key |
| `OLLAMA_BASE_URL` | ❌ | `http://localhost:11434` | Ollama 地址 |

### 前端 (`frontend/.env.local`)

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `BACKEND_URL` | ✅ | `http://localhost:8000` | 后端 API 地址 |
| `JWT_SECRET_KEY` | ✅ | — | 必须与后端一致 |

---

## 🧪 测试

```bash
# 后端测试
cd backend
python -m pytest tests/ -v

# 前端类型检查
cd frontend
npx tsc --noEmit
```

---

## 📄 许可证

MIT License

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request
