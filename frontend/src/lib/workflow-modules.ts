/**
 * Workflow module definitions for the visual editor.
 *
 * Each module represents a processing step that can be added to a workflow.
 * The engine maps `type` to backend processing logic.
 */

export interface WorkflowModule {
  type: string
  label: string
  description: string
  category: "input" | "process" | "output"
  icon: string  // lucide icon name
  color: string // tailwind color class
  configurable?: boolean
  configFields?: { key: string; label: string; type: "text" | "select" | "textarea"; options?: { value: string; label: string }[]; placeholder?: string; default?: string; advanced?: boolean }[]
}

export const WORKFLOW_MODULES: WorkflowModule[] = [
  // ── Input ──
  {
    type: "source",
    label: "文档来源",
    description: "选择要处理的文档范围",
    category: "input",
    icon: "FolderOpen",
    color: "bg-emerald-500",
    configurable: true,
    configFields: [
      {
        key: "filter",
        label: "筛选方式",
        type: "select",
        options: [
          { value: "all", label: "全部文档" },
          { value: "folder", label: "按文件夹" },
          { value: "tag", label: "按标签" },
          { value: "status", label: "按状态" },
        ],
      },
    ],
  },

  // ── Process ──
  {
    type: "polish",
    label: "AI 润色",
    description: "改善文本清晰度和流畅性",
    category: "process",
    icon: "Sparkles",
    color: "bg-blue-500",
    configurable: true,
    configFields: [
      {
        key: "style",
        label: "润色风格",
        type: "select",
        options: [
          { value: "academic", label: "academic" },
          { value: "casual", label: "casual" },
          { value: "formal", label: "formal" },
          { value: "creative", label: "creative" },
        ],
        default: "academic",
      },
      {
        key: "custom_prompt",
        label: "自定义提示词",
        type: "textarea",
        placeholder: "可选：覆盖默认润色提示词",
        advanced: true,
      },
      {
        key: "max_tokens",
        label: "最大 Token 数",
        type: "select",
        options: [
          { value: "1024", label: "1024" },
          { value: "2048", label: "2048" },
          { value: "4096", label: "4096" },
        ],
        default: "4096",
        advanced: true,
      },
      {
        key: "temperature",
        label: "创造性",
        type: "select",
        options: [
          { value: "0.1", label: "0.1" },
          { value: "0.3", label: "0.3" },
          { value: "0.5", label: "0.5" },
          { value: "0.7", label: "0.7" },
        ],
        default: "0.3",
        advanced: true,
      },
    ],
  },
  {
    type: "expand",
    label: "内容扩展",
    description: "补充更多细节和示例",
    category: "process",
    icon: "Expand",
    color: "bg-indigo-500",
    configurable: true,
    configFields: [
      {
        key: "expansion_ratio",
        label: "扩展比例",
        type: "select",
        options: [
          { value: "1.5x", label: "1.5x" },
          { value: "2x", label: "2x" },
          { value: "3x", label: "3x" },
        ],
        default: "2x",
      },
      {
        key: "focus_area",
        label: "重点方向",
        type: "text",
        placeholder: "可选：指定扩展重点",
      },
      {
        key: "custom_prompt",
        label: "自定义提示词",
        type: "textarea",
        placeholder: "可选：覆盖默认扩展提示词",
        advanced: true,
      },
    ],
  },
  {
    type: "compress",
    label: "精简压缩",
    description: "压缩到原文约50%长度",
    category: "process",
    icon: "Minimize2",
    color: "bg-purple-500",
    configurable: true,
    configFields: [
      {
        key: "target_ratio",
        label: "压缩比例",
        type: "select",
        options: [
          { value: "50%", label: "50%" },
          { value: "30%", label: "30%" },
          { value: "20%", label: "20%" },
        ],
        default: "50%",
      },
      {
        key: "preserve_key_points",
        label: "保留要点",
        type: "select",
        options: [
          { value: "true", label: "true" },
          { value: "false", label: "false" },
        ],
        default: "true",
      },
      {
        key: "custom_prompt",
        label: "自定义提示词",
        type: "textarea",
        placeholder: "可选：覆盖默认压缩提示词",
        advanced: true,
      },
    ],
  },
  {
    type: "translate_zh",
    label: "翻译为中文",
    description: "将文本翻译为中文",
    category: "process",
    icon: "Languages",
    color: "bg-teal-500",
    configurable: true,
    configFields: [
      {
        key: "formality",
        label: "正式程度",
        type: "select",
        options: [
          { value: "formal", label: "formal" },
          { value: "neutral", label: "neutral" },
          { value: "informal", label: "informal" },
        ],
        default: "neutral",
      },
      {
        key: "domain",
        label: "领域",
        type: "select",
        options: [
          { value: "general", label: "general" },
          { value: "technical", label: "technical" },
          { value: "legal", label: "legal" },
          { value: "medical", label: "medical" },
        ],
        default: "general",
      },
      {
        key: "glossary",
        label: "术语表",
        type: "textarea",
        placeholder: "每行一个：原文=译文",
        advanced: true,
      },
    ],
  },
  {
    type: "translate_en",
    label: "翻译为英文",
    description: "Translate to English",
    category: "process",
    icon: "Languages",
    color: "bg-cyan-500",
    configurable: true,
    configFields: [
      {
        key: "formality",
        label: "正式程度",
        type: "select",
        options: [
          { value: "formal", label: "formal" },
          { value: "neutral", label: "neutral" },
          { value: "informal", label: "informal" },
        ],
        default: "neutral",
      },
      {
        key: "domain",
        label: "领域",
        type: "select",
        options: [
          { value: "general", label: "general" },
          { value: "technical", label: "technical" },
          { value: "legal", label: "legal" },
          { value: "medical", label: "medical" },
        ],
        default: "general",
      },
      {
        key: "glossary",
        label: "术语表",
        type: "textarea",
        placeholder: "每行一个：原文=译文",
        advanced: true,
      },
    ],
  },
  {
    type: "fix",
    label: "修正语法",
    description: "修正语法、拼写和标点",
    category: "process",
    icon: "Wrench",
    color: "bg-amber-500",
    configurable: true,
    configFields: [
      {
        key: "fix_scope",
        label: "修复范围",
        type: "select",
        options: [
          { value: "grammar", label: "grammar" },
          { value: "spelling", label: "spelling" },
          { value: "style", label: "style" },
          { value: "all", label: "all" },
        ],
        default: "all",
      },
      {
        key: "strictness",
        label: "严格程度",
        type: "select",
        options: [
          { value: "low", label: "low" },
          { value: "medium", label: "medium" },
          { value: "high", label: "high" },
        ],
        default: "medium",
      },
    ],
  },
  {
    type: "summarize",
    label: "生成摘要",
    description: "为文档生成简洁摘要",
    category: "process",
    icon: "FileText",
    color: "bg-sky-500",
    configurable: true,
    configFields: [
      {
        key: "summary_length",
        label: "摘要长度",
        type: "select",
        options: [
          { value: "short", label: "short" },
          { value: "medium", label: "medium" },
          { value: "long", label: "long" },
        ],
        default: "medium",
      },
      {
        key: "format",
        label: "输出格式",
        type: "select",
        options: [
          { value: "paragraph", label: "paragraph" },
          { value: "bullets", label: "bullets" },
          { value: "structured", label: "structured" },
        ],
        default: "paragraph",
      },
      {
        key: "custom_prompt",
        label: "自定义提示词",
        type: "textarea",
        placeholder: "可选：覆盖默认摘要提示词",
        advanced: true,
      },
    ],
  },
  {
    type: "keywords",
    label: "提取关键词",
    description: "提取5-8个核心关键词",
    category: "process",
    icon: "Key",
    color: "bg-orange-500",
    configurable: true,
    configFields: [
      {
        key: "max_keywords",
        label: "最大数量",
        type: "select",
        options: [
          { value: "5", label: "5" },
          { value: "10", label: "10" },
          { value: "15", label: "15" },
          { value: "20", label: "20" },
        ],
        default: "10",
      },
      {
        key: "include_phrases",
        label: "包含短语",
        type: "select",
        options: [
          { value: "true", label: "true" },
          { value: "false", label: "false" },
        ],
        default: "true",
      },
    ],
  },
  {
    type: "auto_tag",
    label: "自动打标签",
    description: "将关键词作为文档标签",
    category: "process",
    icon: "Tags",
    color: "bg-rose-500",
    configurable: true,
    configFields: [
      {
        key: "max_tags",
        label: "最大标签数",
        type: "select",
        options: [
          { value: "3", label: "3" },
          { value: "5", label: "5" },
          { value: "8", label: "8" },
        ],
        default: "5",
      },
      {
        key: "create_new_tags",
        label: "允许新建标签",
        type: "select",
        options: [
          { value: "true", label: "true" },
          { value: "false", label: "false" },
        ],
        default: "true",
      },
      {
        key: "tag_source",
        label: "标签来源",
        type: "select",
        options: [
          { value: "keywords", label: "keywords" },
          { value: "ai_generated", label: "ai_generated" },
        ],
        default: "keywords",
      },
    ],
  },
  {
    type: "standardize",
    label: "标准化分析",
    description: "分析结构并提出改进建议",
    category: "process",
    icon: "ClipboardCheck",
    color: "bg-violet-500",
    configurable: true,
    configFields: [
      {
        key: "analysis_depth",
        label: "分析深度",
        type: "select",
        options: [
          { value: "basic", label: "basic" },
          { value: "detailed", label: "detailed" },
          { value: "comprehensive", label: "comprehensive" },
        ],
        default: "detailed",
      },
      {
        key: "custom_categories",
        label: "自定义分类",
        type: "textarea",
        placeholder: "每行一个分类名称",
        advanced: true,
      },
    ],
  },
  {
    type: "custom_prompt",
    label: "自定义提示词",
    description: "使用自定义提示词处理文本",
    category: "process",
    icon: "MessageSquare",
    color: "bg-pink-500",
    configurable: true,
    configFields: [
      {
        key: "prompt",
        label: "提示词",
        type: "textarea",
        placeholder: "输入自定义系统提示词...",
      },
    ],
  },
  {
    type: "ai_analyze",
    label: "AI 深度分析",
    description: "质量评分、问题检测、改进建议",
    category: "process",
    icon: "Brain",
    color: "bg-fuchsia-500",
    configurable: true,
    configFields: [
      {
        key: "analysis_type",
        label: "分析类型",
        type: "select",
        options: [
          { value: "structure_analysis", label: "structure_analysis" },
          { value: "toc_extraction", label: "toc_extraction" },
          { value: "quality_assessment", label: "quality_assessment" },
          { value: "academic_structure", label: "academic_structure" },
        ],
        default: "structure_analysis",
      },
      {
        key: "output_field",
        label: "输出字段名",
        type: "text",
        placeholder: "analysis_result",
      },
      {
        key: "custom_prompt",
        label: "自定义提示词",
        type: "textarea",
        placeholder: "可选：覆盖默认分析提示词",
        advanced: true,
      },
    ],
  },
  {
    type: "format_convert",
    label: "格式转换",
    description: "文档格式转换 (MD/HTML/LaTeX/DOCX)",
    category: "process",
    icon: "RefreshCw",
    color: "bg-lime-500",
    configurable: true,
    configFields: [
      {
        key: "target_format",
        label: "目标格式",
        type: "select",
        options: [
          { value: "markdown", label: "Markdown" },
          { value: "html", label: "HTML" },
          { value: "latex", label: "LaTeX" },
          { value: "docx", label: "DOCX" },
        ],
      },
    ],
  },
  {
    type: "condition",
    label: "条件分支",
    description: "根据条件选择不同的处理路径",
    category: "process",
    icon: "GitBranch",
    color: "bg-yellow-500",
    configurable: true,
    configFields: [
      {
        key: "field",
        label: "判断字段",
        type: "select",
        options: [
          { value: "status", label: "文档状态" },
          { value: "tag", label: "包含标签" },
          { value: "length", label: "文本长度" },
        ],
      },
      {
        key: "operator",
        label: "运算符",
        type: "select",
        options: [
          { value: "equals", label: "等于" },
          { value: "contains", label: "包含" },
          { value: "gt", label: "大于" },
          { value: "lt", label: "小于" },
        ],
      },
      {
        key: "value",
        label: "值",
        type: "text",
        placeholder: "比较值",
      },
    ],
  },
  {
    type: "loop",
    label: "循环处理",
    description: "对集合中的每个元素重复执行",
    category: "process",
    icon: "Repeat",
    color: "bg-teal-600",
    configurable: true,
    configFields: [
      {
        key: "items_field",
        label: "遍历字段",
        type: "select",
        options: [
          { value: "documents", label: "文档列表" },
          { value: "tags", label: "标签列表" },
          { value: "chunks", label: "文本块列表" },
        ],
      },
      {
        key: "max_iterations",
        label: "最大迭代次数",
        type: "text",
        placeholder: "10",
      },
    ],
  },
  {
    type: "approval",
    label: "人工审批",
    description: "暂停工作流等待人工审批",
    category: "process",
    icon: "UserCheck",
    color: "bg-amber-600",
    configurable: true,
    configFields: [
      {
        key: "approval_message",
        label: "审批提示",
        type: "textarea",
        placeholder: "请审批此步骤的处理结果...",
      },
      {
        key: "auto_approve_after",
        label: "自动审批(小时)",
        type: "text",
        placeholder: "留空则不自动审批",
      },
    ],
  },

  // ── Metadata & Embedding ──
  {
    type: "rename",
    label: "智能重命名",
    description: "AI 分析内容，自动生成更好的标题",
    category: "process",
    icon: "PenLine",
    color: "bg-cyan-600",
    configurable: true,
    configFields: [
      {
        key: "style",
        label: "命名风格",
        type: "select",
        options: [
          { value: "descriptive", label: "描述性" },
          { value: "concise", label: "简洁" },
          { value: "academic", label: "学术风格" },
          { value: "keyword_prefix", label: "关键词前缀" },
          { value: "question", label: "问题形式" },
        ],
      },
      {
        key: "max_length",
        label: "最大长度",
        type: "text",
        placeholder: "80",
      },
      {
        key: "auto_apply",
        label: "自动应用",
        type: "select",
        options: [
          { value: "false", label: "否（仅建议）" },
          { value: "true", label: "是（自动重命名）" },
        ],
      },
    ],
  },
  {
    type: "set_metadata",
    label: "设置元数据",
    description: "修改文档状态、文件夹、标签",
    category: "process",
    icon: "Tags",
    color: "bg-teal-600",
    configurable: true,
    configFields: [
      {
        key: "status",
        label: "文档状态",
        type: "select",
        options: [
          { value: "", label: "不修改" },
          { value: "draft", label: "草稿" },
          { value: "published", label: "已发布" },
          { value: "archived", label: "归档" },
        ],
      },
      {
        key: "add_tags",
        label: "添加标签 (逗号分隔)",
        type: "text",
        placeholder: "标签1, 标签2",
      },
      {
        key: "remove_tags",
        label: "移除标签 (逗号分隔)",
        type: "text",
        placeholder: "旧标签1, 旧标签2",
      },
    ],
  },
  {
    type: "embedding",
    label: "生成嵌入",
    description: "为文档生成向量嵌入，用于语义搜索",
    category: "process",
    icon: "Database",
    color: "bg-violet-600",
    configurable: true,
    configFields: [
      {
        key: "force_rebuild",
        label: "强制重建",
        type: "select",
        options: [
          { value: "false", label: "否（跳过已有嵌入）" },
          { value: "true", label: "是（删除旧嵌入重新生成）" },
        ],
      },
    ],
  },

  // ── Output ──
  {
    type: "save",
    label: "保存文档",
    description: "保存处理后的文档",
    category: "output",
    icon: "Save",
    color: "bg-green-600",
    configurable: true,
    configFields: [
      {
        key: "mode",
        label: "保存模式",
        type: "select",
        options: [
          { value: "overwrite", label: "覆盖原文档" },
          { value: "new", label: "创建新文档" },
        ],
      },
    ],
  },
  {
    type: "export",
    label: "导出文档",
    description: "导出为指定格式文件",
    category: "output",
    icon: "Download",
    color: "bg-emerald-600",
    configurable: true,
    configFields: [
      {
        key: "format",
        label: "导出格式",
        type: "select",
        options: [
          { value: "markdown", label: "Markdown (.md)" },
          { value: "html", label: "HTML (.html)" },
          { value: "latex", label: "LaTeX (.tex)" },
          { value: "docx", label: "Word (.docx)" },
          { value: "pdf", label: "PDF (.pdf)" },
        ],
      },
    ],
  },
]

export function getModuleByType(type: string): WorkflowModule | undefined {
  return WORKFLOW_MODULES.find(m => m.type === type)
}

export const MODULE_CATEGORIES = [
  { key: "input", label: "输入" },
  { key: "process", label: "处理" },
  { key: "output", label: "输出" },
] as const

// ── Dynamic Plugin Loading ──

import { useState, useEffect } from "react"
import { apiTry } from "@/lib/api-client"

interface PluginManifestResponse {
  id: string
  plugin_id: string
  name: string
  version: string
  description: string
  category: string
  icon: string
  color: string
  node_type: string
  configurable: boolean
  config_schema: {
    fields: {
      key: string
      label: string
      type: string
      options?: string[]
      default?: string
      placeholder?: string
      advanced?: boolean
    }[]
  } | null
  is_active: boolean
  error: string | null
}

/**
 * Convert a plugin manifest config_schema to WorkflowModule configFields format.
 * The API returns options as string[] but the frontend expects { value, label }[].
 */
function convertConfigFields(schema: PluginManifestResponse["config_schema"]): WorkflowModule["configFields"] {
  if (!schema?.fields) return undefined
  return schema.fields.map(f => ({
    key: f.key,
    label: f.label,
    type: f.type as "text" | "select" | "textarea",
    options: f.options?.map(o => ({ value: o, label: o })),
    default: f.default,
    placeholder: f.placeholder,
    advanced: f.advanced,
  }))
}

/**
 * Hook that loads workflow modules from the plugin API with static fallback.
 * Third-party plugins appear as additional modules after the built-in ones.
 */
export function useWorkflowModules() {
  const [modules, setModules] = useState<WorkflowModule[]>(WORKFLOW_MODULES)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function fetchPlugins() {
      setLoading(true)
      const [data] = await apiTry<{ plugins: PluginManifestResponse[]; total: number }>("/api/plugins")

      if (cancelled || !data?.plugins) {
        setLoading(false)
        return
      }

      // Build a map of active plugins by node_type
      const activePlugins = data.plugins.filter(p => p.is_active && !p.error)
      const pluginMap = new Map(activePlugins.map(p => [p.node_type, p]))

      // Merge: start with static modules, override config from API
      const merged = WORKFLOW_MODULES.map(mod => {
        const plugin = pluginMap.get(mod.type)
        if (!plugin) return mod

        // API provides richer config_schema — use it if available
        const apiFields = convertConfigFields(plugin.config_schema)
        return {
          ...mod,
          configurable: plugin.configurable ?? mod.configurable,
          configFields: apiFields ?? mod.configFields,
        }
      })

      // Append third-party plugins not in the static list
      const existingTypes = new Set(WORKFLOW_MODULES.map(m => m.type))
      for (const plugin of activePlugins) {
        if (existingTypes.has(plugin.node_type)) continue
        merged.push({
          type: plugin.node_type,
          label: plugin.name,
          description: plugin.description,
          category: plugin.category as "input" | "process" | "output",
          icon: plugin.icon || "Puzzle",
          color: plugin.color || "bg-gray-500",
          configurable: plugin.configurable,
          configFields: convertConfigFields(plugin.config_schema),
        })
      }

      setModules(merged)
      setLoading(false)
    }

    fetchPlugins()
    return () => { cancelled = true }
  }, [])

  return {
    modules,
    loading,
    getModuleByType: (type: string) => modules.find(m => m.type === type),
  }
}
