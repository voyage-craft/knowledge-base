"""Built-in API provider templates."""

from dataclasses import dataclass, field


@dataclass
class ProviderTemplate:
    key: str
    name: str
    description: str
    base_url: str
    protocol: str  # "openai" or "anthropic"
    models: list[str] = field(default_factory=list)
    color: str = "bg-slate-500"
    icon: str = "Server"


PROVIDER_TEMPLATES: list[ProviderTemplate] = [
    ProviderTemplate(
        key="glm",
        name="智谱 AI (GLM)",
        description="智谱清言大模型，支持 GLM-4 系列",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        protocol="openai",
        models=["glm-4-plus", "glm-4-flash", "glm-4-long", "glm-4-air", "glm-4-airx", "glm-4v-plus"],
        color="bg-blue-600",
        icon="Zap",
    ),
    ProviderTemplate(
        key="qwen",
        name="通义千问 (Qwen)",
        description="阿里云大模型，兼容 OpenAI 协议",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        protocol="openai",
        models=["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long", "qwen-vl-max", "qwen-vl-plus"],
        color="bg-orange-500",
        icon="Cloud",
    ),
    ProviderTemplate(
        key="deepseek",
        name="DeepSeek",
        description="深度求索，高性价比推理模型",
        base_url="https://api.deepseek.com/v1",
        protocol="openai",
        models=["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
        color="bg-indigo-600",
        icon="Search",
    ),
    ProviderTemplate(
        key="mimo",
        name="小米 MIMO",
        description="小米大模型推理引擎",
        base_url="https://api.xiaomi.com/v1",
        protocol="openai",
        models=["mimo-v2.5-pro", "mimo-v2.5-flash", "mimo-v1"],
        color="bg-green-600",
        icon="Smartphone",
    ),
    ProviderTemplate(
        key="siliconflow",
        name="硅基流动 (SiliconFlow)",
        description="多模型聚合平台，支持多种开源模型",
        base_url="https://api.siliconflow.cn/v1",
        protocol="openai",
        models=[
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
            "Qwen/Qwen2.5-72B-Instruct",
            "meta-llama/Llama-3.3-70B-Instruct",
            "Pro/deepseek-ai/DeepSeek-V3",
            "Pro/deepseek-ai/DeepSeek-R1",
        ],
        color="bg-purple-600",
        icon="Cpu",
    ),
    ProviderTemplate(
        key="moonshot",
        name="月之暗面 (Moonshot)",
        description="Kimi 大模型 API",
        base_url="https://api.moonshot.cn/v1",
        protocol="openai",
        models=["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        color="bg-slate-800",
        icon="Moon",
    ),
    ProviderTemplate(
        key="openai",
        name="OpenAI",
        description="GPT-4o / o1 / o3 系列",
        base_url="https://api.openai.com/v1",
        protocol="openai",
        models=["gpt-4o", "gpt-4o-mini", "o1", "o1-mini", "o3-mini"],
        color="bg-emerald-600",
        icon="Brain",
    ),
    ProviderTemplate(
        key="anthropic",
        name="Anthropic",
        description="Claude 系列模型",
        base_url="https://api.anthropic.com",
        protocol="anthropic",
        models=["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-3-5-sonnet-20241022"],
        color="bg-amber-700",
        icon="MessageSquare",
    ),
    ProviderTemplate(
        key="ollama",
        name="Ollama (本地)",
        description="本地部署的开源模型",
        base_url="http://localhost:11434/v1",
        protocol="openai",
        models=["llama3.1", "qwen2.5", "mistral-nemo", "gemma2", "phi3"],
        color="bg-gray-600",
        icon="HardDrive",
    ),
]


def get_template(key: str) -> ProviderTemplate | None:
    for t in PROVIDER_TEMPLATES:
        if t.key == key:
            return t
    return None


def get_all_templates() -> list[dict]:
    return [
        {
            "key": t.key,
            "name": t.name,
            "description": t.description,
            "base_url": t.base_url,
            "protocol": t.protocol,
            "models": t.models,
            "color": t.color,
            "icon": t.icon,
        }
        for t in PROVIDER_TEMPLATES
    ]
