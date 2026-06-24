# LLM 服务商配置

> 配置和切换 Knowledge Base 的大语言模型服务商

## 支持的服务商

Knowledge Base 支持多种 LLM 服务商, 涵盖国际和国内主流模型:

| 服务商 | 协议 | 说明 |
|--------|------|------|
| OpenAI | OpenAI API | GPT-4o, GPT-4, GPT-3.5 等 |
| Anthropic | Anthropic API | Claude 3.5, Claude 3 等 |
| Ollama | OpenAI 兼容 | 本地部署开源模型 |
| DeepSeek | OpenAI 兼容 | DeepSeek-V3, DeepSeek-Coder |
| Qwen (通义千问) | OpenAI 兼容 | Qwen-Max, Qwen-Plus, Qwen-Turbo |
| Zhipu (智谱) | OpenAI 兼容 | GLM-4, GLM-4-Flash 等 |
| Moonshot (月之暗面) | OpenAI 兼容 | Moonshot-v1-8k, Moonshot-v1-32k |
| Baichuan (百川) | OpenAI 兼容 | Baichuan4, Baichuan3-Turbo |
| Yi (零一万物) | OpenAI 兼容 | Yi-Large, Yi-Medium |

> 所有支持 OpenAI 兼容协议的服务商都可以通过 "API 路由" 功能进行统一管理和负载均衡。

---

## 配置方式

### 方式一: 环境变量 (基础配置)

在 `backend/.env` 中设置:

```env
# 选择服务商
LLM_PROVIDER=openai

# 对应的 API Key
OPENAI_API_KEY=sk-your-api-key
ANTHROPIC_API_KEY=sk-ant-your-api-key
OLLAMA_BASE_URL=http://localhost:11434

# 默认模型
LLM_MODEL=gpt-4o
```

### 方式二: Web 界面 (推荐)

通过 "设置 -> 系统配置" 界面动态配置:

1. 以管理员身份登录
2. 进入 "设置" -> "系统配置"
3. 找到 "LLM 配置" 部分
4. 选择服务商并填写 API Key
5. 选择默认模型
6. 保存配置

[截图占位]

### 方式三: API 路由 (高级配置)

通过 "设置 -> API 路由" 可以配置多个端点, 实现负载均衡和故障转移。详见 [API 路由配置](./API_ROUTES.md)。

---

## 各服务商详细配置

### OpenAI

| 配置项 | 值 |
|--------|-----|
| 服务商 | `openai` |
| API Key | 从 https://platform.openai.com/api-keys 获取 |
| Base URL | `https://api.openai.com/v1` (默认) |
| 推荐模型 | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo` |

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-key
LLM_MODEL=gpt-4o
```

**性能建议**:
- 日常使用推荐 `gpt-4o-mini`, 性价比最高
- 复杂分析任务使用 `gpt-4o`
- 简单任务 (如打标签) 使用 `gpt-4o-mini` 即可

### Anthropic

| 配置项 | 值 |
|--------|-----|
| 服务商 | `anthropic` |
| API Key | 从 https://console.anthropic.com/ 获取 |
| Base URL | `https://api.anthropic.com` (默认) |
| 推荐模型 | `claude-sonnet-4-20250514`, `claude-3-5-sonnet-20241022` |

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
LLM_MODEL=claude-sonnet-4-20250514
```

**性能建议**:
- 长文档处理推荐 Claude, 上下文窗口大
- 翻译和润色任务效果出色
- API 调用成本相对较高

### Ollama (本地部署)

| 配置项 | 值 |
|--------|-----|
| 服务商 | `ollama` |
| API Key | 不需要 |
| Base URL | `http://localhost:11434` |
| 推荐模型 | `qwen2.5`, `llama3`, `deepseek-coder-v2` |

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5
```

**安装 Ollama**:

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# 拉取模型
ollama pull qwen2.5
ollama pull llama3
```

**性能建议**:
- 完全离线运行, 数据隐私有保障
- 需要足够的 GPU 显存 (建议 8GB+)
- 模型质量与云端模型有一定差距

### DeepSeek

| 配置项 | 值 |
|--------|-----|
| 服务商 | `deepseek` |
| Base URL | `https://api.deepseek.com/v1` |
| 推荐模型 | `deepseek-chat`, `deepseek-coder` |

通过 API 路由配置:

| 字段 | 值 |
|------|-----|
| 名称 | DeepSeek |
| 协议 | `openai` (兼容) |
| Base URL | `https://api.deepseek.com/v1` |
| API Key | 从 https://platform.deepseek.com/ 获取 |

**性能建议**:
- 性价比极高, 国内访问稳定
- `deepseek-chat` 适合通用任务
- `deepseek-coder` 适合代码相关任务

### Qwen (通义千问)

| 配置项 | 值 |
|--------|-----|
| Base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 推荐模型 | `qwen-max`, `qwen-plus`, `qwen-turbo` |

通过 API 路由配置:

| 字段 | 值 |
|------|-----|
| 名称 | 通义千问 |
| 协议 | `openai` (兼容) |
| Base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| API Key | 阿里云 DashScope API Key |

**性能建议**:
- 中文理解和生成能力出色
- `qwen-turbo` 速度快, 适合简单任务
- `qwen-max` 质量最高, 适合复杂分析

### Zhipu (智谱清言)

| 配置项 | 值 |
|--------|-----|
| Base URL | `https://open.bigmodel.cn/api/paas/v4` |
| 推荐模型 | `glm-4-plus`, `glm-4`, `glm-4-flash` |

通过 API 路由配置:

| 字段 | 值 |
|------|-----|
| 名称 | 智谱清言 |
| 协议 | `openai` (兼容) |
| Base URL | `https://open.bigmodel.cn/api/paas/v4` |
| API Key | 从 https://open.bigmodel.cn/ 获取 |

**性能建议**:
- `glm-4-flash` 免费额度充足, 适合开发测试
- 中文能力较好

### Moonshot (月之暗面 / Kimi)

| 配置项 | 值 |
|--------|-----|
| Base URL | `https://api.moonshot.cn/v1` |
| 推荐模型 | `moonshot-v1-8k`, `moonshot-v1-32k`, `moonshot-v1-128k` |

通过 API 路由配置:

| 字段 | 值 |
|------|-----|
| 名称 | Moonshot |
| 协议 | `openai` (兼容) |
| Base URL | `https://api.moonshot.cn/v1` |
| API Key | 从 https://platform.moonshot.cn/ 获取 |

**性能建议**:
- 超长上下文是最大优势 (最高 128k)
- 适合处理长文档的分析和摘要

### Baichuan (百川)

| 配置项 | 值 |
|--------|-----|
| Base URL | `https://api.baichuan-ai.com/v1` |
| 推荐模型 | `Baichuan4`, `Baichuan3-Turbo` |

通过 API 路由配置:

| 字段 | 值 |
|------|-----|
| 名称 | 百川 |
| 协议 | `openai` (兼容) |
| Base URL | `https://api.baichuan-ai.com/v1` |
| API Key | 从 https://platform.baichuan-ai.com/ 获取 |

### Yi (零一万物)

| 配置项 | 值 |
|--------|-----|
| Base URL | `https://api.lingyiwanwu.com/v1` |
| 推荐模型 | `yi-large`, `yi-medium`, `yi-spark` |

通过 API 路由配置:

| 字段 | 值 |
|------|-----|
| 名称 | 零一万物 |
| 协议 | `openai` (兼容) |
| Base URL | `https://api.lingyiwanwu.com/v1` |
| API Key | 从 https://platform.lingyiwanwu.com/ 获取 |

---

## 嵌入模型配置

Knowledge Base 的语义搜索功能依赖嵌入模型:

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| 嵌入模型 | `EMBEDDING_MODEL` | `BAAI/bge-m3` | HuggingFace 模型名称 |
| 嵌入维度 | `EMBEDDING_DIMENSION` | `1024` | 向量维度 |

嵌入模型在首次使用 RAG 搜索时自动下载和加载 (懒加载), 不会影响系统启动速度。

> **注意**: 嵌入模型运行在本地, 需要安装 `ai` 依赖: `pip install -e ".[ai]"`

---

## 性能优化建议

### 选择合适的模型

| 场景 | 推荐模型 | 说明 |
|------|----------|------|
| 日常文档处理 | `gpt-4o-mini`, `qwen-plus` | 性价比高 |
| 深度分析 | `gpt-4o`, `claude-sonnet-4-20250514` | 质量最高 |
| 批量标签生成 | `gpt-4o-mini`, `glm-4-flash` | 成本低速度快 |
| 长文档摘要 | `moonshot-v1-128k` | 超长上下文 |
| 离线/隐私场景 | Ollama + `qwen2.5` | 完全本地 |

### 降低 API 成本

1. 简单任务使用便宜模型, 通过 API 路由按模型分配端点
2. 合理设置速率限制避免突发大量请求
3. 使用 `gpt-4o-mini` 等经济型模型处理批量任务
4. 配置故障转移, 当一个服务商出现问题时自动切换
