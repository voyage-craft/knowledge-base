# Knowledge Base 文档中心

> AI 知识库管理系统 -- 完整文档索引

欢迎来到 Knowledge Base 项目文档。本文档涵盖部署、配置、MCP 集成和插件开发等全部内容。

[截图占位]

---

## 快速导航

### 部署指南

| 文档 | 说明 |
|------|------|
| [快速开始](./deployment/QUICK_START.md) | 5 分钟内完成本地环境搭建并运行项目 |
| [Electron 桌面端安装](./deployment/ELECTRON_INSTALL.md) | 桌面客户端安装与配置指南 |
| [Docker 部署](./deployment/DOCKER_DEPLOY.md) | 使用 Docker 容器化部署到服务器 |
| [开发者环境搭建](./deployment/DEV_SETUP.md) | 面向开发者的完整开发环境配置 |

### 配置参考

| 文档 | 说明 |
|------|------|
| [系统配置](./configuration/SYSTEM_CONFIG.md) | 系统设置项详细说明 |
| [LLM 服务商配置](./configuration/LLM_PROVIDERS.md) | 大语言模型接入与切换指南 |
| [API 路由配置](./configuration/API_ROUTES.md) | API 路由规则、负载均衡与故障转移 |
| [环境变量参考](./configuration/ENVIRONMENT_VARIABLES.md) | 所有环境变量完整列表 |

### MCP 集成

| 文档 | 说明 |
|------|------|
| [MCP 概述](./mcp/MCP_OVERVIEW.md) | MCP 协议架构与可用工具 |
| [Claude Desktop 配置](./mcp/MCP_CLAUDE_DESKTOP.md) | 在 Claude Desktop 中接入知识库 |
| [Cursor IDE 配置](./mcp/MCP_CURSOR.md) | 在 Cursor 编辑器中接入知识库 |
| [Windsurf 配置](./mcp/MCP_WINDSURF.md) | 在 Windsurf 中接入知识库 |
| [OpenAI Codex 配置](./mcp/MCP_CODEX.md) | 在 OpenAI Codex / ChatGPT 中接入知识库 |
| [MCP 故障排查](./mcp/MCP_TROUBLESHOOTING.md) | 常见问题与解决方案 |

### 插件系统

| 文档 | 说明 |
|------|------|
| [插件规范](./plugins/PLUGIN_SPEC.md) | plugin.json 清单格式与开发规范 |
| [内置插件参考](./plugins/BUILTIN_PLUGINS.md) | 22 个内置插件的功能与配置说明 |
| [创建自定义插件](./plugins/CREATE_PLUGIN.md) | 从零开始开发并打包分发插件 |

---

## 项目架构概览

```
knowledge-base/
  backend/          # FastAPI 后端 (Python 3.11+)
    app/
      api/          # REST API 路由
      core/         # 核心配置、安全、数据库
      mcp/          # MCP 服务端 (SSE + Stdio)
      models/       # SQLAlchemy 数据模型
      schemas/      # Pydantic 请求/响应模型
      services/     # 业务逻辑层
    plugins/
      builtin/      # 22 个内置工作流插件
      third_party/  # 用户安装的第三方插件
  frontend/         # Next.js 前端 (React 19 + TypeScript)
  electron/         # Electron 桌面端封装
  docs/             # 本文档目录
```

## 技术栈

- **后端**: Python 3.11+, FastAPI, SQLAlchemy, aiosqlite, PyJWT
- **前端**: Next.js 16, React 19, TypeScript 5, Tailwind CSS 4, TipTap 编辑器
- **AI**: OpenAI / Anthropic / Ollama 等多 LLM 服务商, sentence-transformers 嵌入
- **桌面端**: Electron
- **数据库**: SQLite (自动创建, 无需手动配置)
- **协议**: MCP (Model Context Protocol) -- SSE 与 Stdio 双传输

## 版本信息

当前系统版本: **0.2.0** | 插件 API 版本: **1.0**
