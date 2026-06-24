# API 路由配置

> API 路由规则系统 -- 智能分发、负载均衡、故障转移

## 概述

Knowledge Base 内置了一套智能 API 路由系统, 可以将 LLM 请求分发到不同的服务端点。该系统支持:

- **多端点管理**: 配置多个 LLM API 端点
- **智能路由**: 按模型名称自动匹配最合适的端点
- **负载均衡**: 基于优先级的请求分发
- **故障转移**: 端点异常时自动切换到备用端点
- **熔断保护**: 连续错误后自动冻结端点, 防止雪崩
- **健康追踪**: 实时监控每个端点的状态

[截图占位]

## 核心概念

### API 端点 (Endpoint)

端点是一个 LLM API 服务的连接配置:

| 字段 | 说明 | 示例 |
|------|------|------|
| name | 端点名称 | "OpenAI 主力" |
| provider | 服务商名称 | "openai" |
| base_url | API 地址 | `https://api.openai.com/v1` |
| api_key | API 密钥 | `sk-...` |
| protocol | 协议类型 | `openai` 或 `anthropic` |
| supported_models | 支持的模型列表 | `["gpt-4o", "gpt-4o-mini"]` |
| priority | 优先级 (越小越高) | `100` |
| timeout_ms | 超时时间 (毫秒) | `60000` |
| protocol_mode | 协议模式 | `auto`, `completions`, `responses` |

### 路由规则 (Rule)

路由规则将模型名称映射到具体端点:

| 字段 | 说明 | 示例 |
|------|------|------|
| model_id | 模型标识符 | `gpt-4o` |
| endpoint_id | 目标端点 ID | `1` |
| is_locked | 是否锁定 (不允许自动切换) | `false` |
| priority | 优先级 | `100` |
| max_requests_per_minute | 每分钟最大请求数 | `null` (不限制) |

## 配置操作

### 通过 Web 界面

1. 以管理员身份登录
2. 进入 "设置" -> "API 路由"
3. 点击 "添加端点" 配置新的 API 端点
4. 点击 "添加规则" 将模型绑定到端点

[截图占位]

### 通过 API

#### 创建端点

```http
POST /api/api-routes/endpoints
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "DeepSeek 端点",
  "provider": "deepseek",
  "base_url": "https://api.deepseek.com/v1",
  "api_key": "sk-your-deepseek-key",
  "protocol": "openai",
  "supported_models": ["deepseek-chat", "deepseek-coder"],
  "priority": 50,
  "timeout_ms": 60000,
  "protocol_mode": "auto"
}
```

#### 创建路由规则

```http
POST /api/api-routes/rules
Content-Type: application/json
Authorization: Bearer <token>

{
  "model_id": "deepseek-chat",
  "endpoint_id": 2,
  "is_locked": false,
  "priority": 100,
  "max_requests_per_minute": 30
}
```

#### 锁定模型到特定端点

```http
POST /api/api-routes/rules/lock
Content-Type: application/json
Authorization: Bearer <token>

{
  "model_id": "gpt-4o",
  "endpoint_id": 1
}
```

---

## 协议类型

### OpenAI 兼容协议

大部分国内外 LLM 服务商都兼容 OpenAI 的 API 格式:

| 服务商 | Base URL |
|--------|----------|
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 智谱清言 | `https://open.bigmodel.cn/api/paas/v4` |
| Moonshot | `https://api.moonshot.cn/v1` |
| 百川 | `https://api.baichuan-ai.com/v1` |
| 零一万物 | `https://api.lingyiwanwu.com/v1` |
| Ollama | `http://localhost:11434/v1` |

使用 `AsyncOpenAI` 客户端进行通信。

### Anthropic 协议

| 服务商 | Base URL |
|--------|----------|
| Anthropic | `https://api.anthropic.com` |

使用 `AsyncAnthropic` 客户端进行通信。

### 协议模式 (protocol_mode)

| 模式 | 说明 |
|------|------|
| `auto` | 自动检测协议 (推荐) |
| `completions` | 使用 `/chat/completions` 端点 |
| `responses` | 使用 OpenAI Responses API |

---

## 负载均衡

系统基于优先级进行请求分发:

1. 按 `priority` 值从小到大排序端点 (值越小优先级越高)
2. 优先使用高优先级端点
3. 高优先级端点不可用时, 自动降级到低优先级端点

### 配置示例: 主力 + 备用

```
端点 A: OpenAI 主力 (priority=10)
端点 B: DeepSeek 备用 (priority=100)
```

当 OpenAI 端点正常时, 所有请求发往 A; 当 A 出现问题时自动切换到 B。

### 配置示例: 按模型分配

```
规则 1: gpt-4o -> OpenAI 端点 (priority=10)
规则 2: deepseek-chat -> DeepSeek 端点 (priority=10)
规则 3: qwen-max -> 通义千问端点 (priority=10)
```

不同模型的请求自动路由到对应端点。

---

## 故障转移与熔断

### 端点健康状态

| 状态 | 说明 |
|------|------|
| healthy | 正常, 可以接受请求 |
| degraded | 降级, 连续 3 次错误后进入 |
| frozen | 冻结, 连续 5 次错误后进入, 暂停使用 |

### 渐进式冻结

当端点连续出错时, 系统会按以下时间逐步冻结:

| 冻结次数 | 冻结时长 |
|----------|----------|
| 第 1 次 | 2 分钟 |
| 第 2 次 | 10 分钟 |
| 第 3 次 | 30 分钟 |
| 第 4 次及以后 | 2 小时 |

冻结期过后, 端点自动恢复为 healthy 状态。

### 端点阈值

| 参数 | 值 | 说明 |
|------|-----|------|
| `CONSECUTIVE_ERROR_DEGRADED` | 3 | 连续错误次数达到此值时进入降级 |
| `CONSECUTIVE_ERROR_FREEZE` | 5 | 连续错误次数达到此值时进入冻结 |
| `MAX_CLIENT_CACHE_SIZE` | 50 | 客户端 LRU 缓存上限 |

---

## 速率限制

### 端点级速率限制

通过路由规则的 `max_requests_per_minute` 字段限制单个端点的请求频率:

```json
{
  "model_id": "gpt-4o",
  "endpoint_id": 1,
  "max_requests_per_minute": 30
}
```

### 全局限速

通过环境变量设置:

```env
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_AI=10/minute
```

---

## 服务商模板

系统内置了服务商配置模板, 可以在 Web 界面快速添加常见服务商:

通过 `GET /api/api-routes/templates` 获取所有可用模板。

常见模板包括: OpenAI, Anthropic, DeepSeek, 通义千问, 智谱清言, Moonshot 等。

---

## 最佳实践

1. **至少配置两个端点**: 一个主力, 一个备用, 确保服务高可用
2. **合理使用优先级**: 将性价比最高的端点设为最高优先级
3. **设置超时时间**: 根据服务商响应速度调整 `timeout_ms`
4. **不要锁定所有模型**: 保留自动切换能力, 只在特殊需求时锁定
5. **监控端点状态**: 定期检查端点健康状态, 及时处理 frozen 端点
