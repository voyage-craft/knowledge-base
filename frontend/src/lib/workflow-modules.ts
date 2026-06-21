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
  configFields?: { key: string; label: string; type: "text" | "select" | "textarea"; options?: { value: string; label: string }[]; placeholder?: string }[]
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
  },
  {
    type: "expand",
    label: "内容扩展",
    description: "补充更多细节和示例",
    category: "process",
    icon: "Expand",
    color: "bg-indigo-500",
  },
  {
    type: "compress",
    label: "精简压缩",
    description: "压缩到原文约50%长度",
    category: "process",
    icon: "Minimize2",
    color: "bg-purple-500",
  },
  {
    type: "translate_zh",
    label: "翻译为中文",
    description: "将文本翻译为中文",
    category: "process",
    icon: "Languages",
    color: "bg-teal-500",
  },
  {
    type: "translate_en",
    label: "翻译为英文",
    description: "将文本翻译为英文",
    category: "process",
    icon: "Languages",
    color: "bg-cyan-500",
  },
  {
    type: "fix",
    label: "修正语法",
    description: "修正语法、拼写和标点",
    category: "process",
    icon: "Wrench",
    color: "bg-amber-500",
  },
  {
    type: "summarize",
    label: "生成摘要",
    description: "为文档生成简洁摘要",
    category: "process",
    icon: "FileText",
    color: "bg-sky-500",
  },
  {
    type: "keywords",
    label: "提取关键词",
    description: "提取5-8个核心关键词",
    category: "process",
    icon: "Key",
    color: "bg-orange-500",
  },
  {
    type: "auto_tag",
    label: "自动打标签",
    description: "将关键词作为文档标签",
    category: "process",
    icon: "Tags",
    color: "bg-rose-500",
  },
  {
    type: "standardize",
    label: "标准化分析",
    description: "分析结构并提出改进建议",
    category: "process",
    icon: "ClipboardCheck",
    color: "bg-violet-500",
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
