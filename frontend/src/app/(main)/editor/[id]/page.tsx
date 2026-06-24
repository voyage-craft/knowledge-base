"use client"

import { useEffect, useCallback, useRef, useState, memo } from "react"
import { useParams, useRouter } from "next/navigation"
import { EditorContent } from "@tiptap/react"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Bold, Italic, Underline as UnderlineIcon, Strikethrough, Code,
  Heading1, Heading2, Heading3, List, ListOrdered, Quote,
  Minus, Highlighter, CheckSquare, AlignLeft, AlignCenter,
  AlignRight, Undo, Redo, ArrowLeft, Save, Sparkles, Download, Clock,
} from "lucide-react"

import "katex/dist/katex.min.css"
import { toast } from "sonner"
import { VersionHistory } from "@/components/editor/VersionHistory"
import { StandardizePanel } from "@/components/editor/StandardizePanel"
import { apiTry, apiFetchBlob } from "@/lib/api-client"
import { useKnowledgeEditor } from "@/lib/use-knowledge-editor"

const ToolbarButton = memo(function ToolbarButton({
  onClick, isActive, children, title,
}: {
  onClick: () => void; isActive?: boolean; children: React.ReactNode; title?: string;
}) {
  return (
    <Button
      variant={isActive ? "secondary" : "ghost"}
      size="icon"
      className="h-8 w-8"
      onClick={onClick}
      title={title}
    >
      {children}
    </Button>
  )
})

export default function EditorPage() {
  const params = useParams()
  const router = useRouter()
  const docId = params.id as string
  const [title, setTitle] = useState("")
  const [saveStatus, setSaveStatus] = useState<"saved" | "saving" | "unsaved">("saved")
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const saveFnRef = useRef<() => void>(() => {})
  const isLoadingRef = useRef(false) // Guard: suppress onUpdate during setContent
  const lastSavedRef = useRef<{ title: string; content: string }>({ title: "", content: "" }) // Track last saved state
  const [versionHistoryOpen, setVersionHistoryOpen] = useState(false)
  const [standardizeOpen, setStandardizeOpen] = useState(false)

  const editor = useKnowledgeEditor({
    placeholder: "开始写作，或输入 / 使用命令...",
    onUpdate: (ed) => {
      // Suppress saves during programmatic setContent (initial load)
      if (isLoadingRef.current) return

      // Check if content actually changed from last saved state
      const currentContent = JSON.stringify(ed.getJSON())
      if (currentContent === lastSavedRef.current.content) {
        // Content reverted to last saved state (e.g., undo) — no save needed
        setSaveStatus("saved")
        if (saveTimeoutRef.current) {
          clearTimeout(saveTimeoutRef.current)
          saveTimeoutRef.current = null
        }
        return
      }

      setSaveStatus("unsaved")
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
      saveTimeoutRef.current = setTimeout(() => saveFnRef.current(), 1500)
    },
  })

  const saveDocument = useCallback(async () => {
    if (!editor) return

    const currentContent = JSON.stringify(editor.getJSON())
    const currentTitle = title

    // Skip save if nothing changed
    if (currentTitle === lastSavedRef.current.title && currentContent === lastSavedRef.current.content) {
      setSaveStatus("saved")
      return
    }

    setSaveStatus("saving")
    const [, err] = await apiTry(`/api/documents/${docId}`, {
      method: "PUT",
      body: JSON.stringify({ title: currentTitle, content_json: editor.getJSON() }),
    })
    if (!err) {
      lastSavedRef.current = { title: currentTitle, content: currentContent }
      setSaveStatus("saved")
    } else {
      setSaveStatus("unsaved")
    }
  }, [editor, docId, title])

  const runAIOperation = useCallback(async (operation: string) => {
    if (!editor) return
    const selectedText = editor.state.doc.textBetween(
      editor.state.selection.from,
      editor.state.selection.to,
      "\n",
    )
    const text = selectedText || editor.state.doc.textBetween(0, editor.state.doc.content.size, "\n")

    if (!text.trim()) {
      toast.error("请先输入或选择文本内容")
      return
    }

    // Confirm when replacing entire document (no selection)
    if (!selectedText) {
      if (!confirm("未选中文本，AI 将替换整个文档内容。确定继续吗？")) return
    }

    const context = selectedText ? "User has selected specific text to edit." : "Edit the entire document text."

    const operationLabels: Record<string, string> = {
      polish: "正在润色文本...",
      expand: "正在扩展内容...",
      compress: "正在压缩文本...",
      translate_zh: "正在翻译为中文...",
      translate_en: "正在翻译为英文...",
      fix: "正在修正语法...",
    }
    toast.info(operationLabels[operation] || "AI 处理中...")

    try {
      const res = await fetch("/api/ai/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, operation, context }),
      })

      if (!res.ok) {
        toast.error("AI 服务不可用，请检查配置")
        return
      }

      // Read the streamed text response
      const reader = res.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let result = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        result += decoder.decode(value, { stream: true })
      }

      if (result) {
        if (selectedText) {
          editor.chain().focus().insertContent(result).run()
        } else {
          editor.chain().focus().selectAll().insertContent(result).run()
        }
        toast.success("AI 操作完成")
      } else {
        toast.error("AI 未返回结果")
      }
    } catch {
      toast.error("AI 操作失败")
    }
  }, [editor])

  useEffect(() => { saveFnRef.current = saveDocument }, [saveDocument])

  // Warn on browser close when unsaved
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (saveStatus === "unsaved") {
        e.preventDefault()
        e.returnValue = ""
      }
    }
    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => window.removeEventListener("beforeunload", handleBeforeUnload)
  }, [saveStatus])

  // Flush pending save on unmount ONLY (empty deps = runs cleanup once on unmount)
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
        saveTimeoutRef.current = null
        // Fire-and-forget save on unmount
        saveFnRef.current()
      }
    }
  }, [])

  useEffect(() => {
    async function loadDocument() {
      const [doc] = await apiTry<{ title: string; content_json: unknown }>(`/api/documents/${docId}`)
      if (!doc) return
      setTitle(doc.title || "无标题")
      if (doc.content_json) {
        let content: unknown = doc.content_json
        if (typeof doc.content_json === "string") {
          try {
            content = JSON.parse(doc.content_json)
          } catch {
            toast.error("文档内容解析失败")
            return
          }
        }
        // Suppress onUpdate during setContent to prevent unnecessary save
        isLoadingRef.current = true
        editor?.commands.setContent(content as object)
        isLoadingRef.current = false
      }
      // Record initial state as "last saved" to prevent unnecessary saves
      lastSavedRef.current = {
        title: doc.title || "无标题",
        content: JSON.stringify(editor?.getJSON() || {}),
      }
      setSaveStatus("saved")
    }
    if (editor) loadDocument()
  }, [docId, editor])

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault()
        saveFnRef.current()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  const handleExport = useCallback(async (format: string) => {
    try {
      const { blob } = await apiFetchBlob(`/api/documents/${docId}/export?format=${format}`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      const extMap: Record<string, string> = { markdown: "md", html: "html", latex: "tex", docx: "docx" }
      a.download = `${title || "document"}.${extMap[format] || format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error("导出失败")
    }
  }, [docId, title])

  const handleVersionRestore = useCallback((contentJson: unknown) => {
    if (!editor || !contentJson) return
    if (!confirm("确定要恢复到此版本吗？当前内容将被替换。")) return
    // Suppress onUpdate during setContent to prevent redundant save
    isLoadingRef.current = true
    editor.commands.setContent(contentJson as object)
    isLoadingRef.current = false
    setSaveStatus("unsaved")
    // Save immediately with the restored content
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current)
      saveTimeoutRef.current = null
    }
    saveFnRef.current()
  }, [editor])

  // Stable toolbar callbacks to preserve ToolbarButton memoization
  const toggleBold = useCallback(() => editor?.chain().focus().toggleBold().run(), [editor])
  const toggleItalic = useCallback(() => editor?.chain().focus().toggleItalic().run(), [editor])
  const toggleUnderline = useCallback(() => editor?.chain().focus().toggleUnderline().run(), [editor])
  const toggleStrike = useCallback(() => editor?.chain().focus().toggleStrike().run(), [editor])
  const toggleCode = useCallback(() => editor?.chain().focus().toggleCode().run(), [editor])
  const toggleHighlight = useCallback(() => editor?.chain().focus().toggleHighlight().run(), [editor])
  const toggleHeading1 = useCallback(() => editor?.chain().focus().toggleHeading({ level: 1 }).run(), [editor])
  const toggleHeading2 = useCallback(() => editor?.chain().focus().toggleHeading({ level: 2 }).run(), [editor])
  const toggleHeading3 = useCallback(() => editor?.chain().focus().toggleHeading({ level: 3 }).run(), [editor])
  const toggleBulletList = useCallback(() => editor?.chain().focus().toggleBulletList().run(), [editor])
  const toggleOrderedList = useCallback(() => editor?.chain().focus().toggleOrderedList().run(), [editor])
  const toggleTaskList = useCallback(() => editor?.chain().focus().toggleTaskList().run(), [editor])
  const toggleBlockquote = useCallback(() => editor?.chain().focus().toggleBlockquote().run(), [editor])
  const alignLeft = useCallback(() => editor?.chain().focus().setTextAlign("left").run(), [editor])
  const alignCenter = useCallback(() => editor?.chain().focus().setTextAlign("center").run(), [editor])
  const alignRight = useCallback(() => editor?.chain().focus().setTextAlign("right").run(), [editor])
  const setHorizontalRule = useCallback(() => editor?.chain().focus().setHorizontalRule().run(), [editor])
  const undo = useCallback(() => editor?.chain().focus().undo().run(), [editor])
  const redo = useCallback(() => editor?.chain().focus().redo().run(), [editor])

  if (!editor) return null

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <header className="border-b px-4 py-2 flex items-center gap-3 bg-background">
        <Button variant="ghost" size="icon" onClick={() => router.push("/documents")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <input
          className="text-lg font-medium bg-transparent border-none outline-none flex-1"
          value={title}
          onChange={e => {
            setTitle(e.target.value)
            setSaveStatus("unsaved")
            if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
            saveTimeoutRef.current = setTimeout(() => saveFnRef.current(), 1500)
          }}
          onBlur={() => {
            if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
            saveDocument()
          }}
        />
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className={`h-2 w-2 rounded-full ${
            saveStatus === "saved" ? "bg-green-500" :
            saveStatus === "saving" ? "bg-yellow-500 animate-pulse" :
            "bg-red-400"
          }`} />
          {saveStatus === "saving" ? "保存中..." : saveStatus === "saved" ? "已保存" : "未保存"}
        </span>
        <Separator orientation="vertical" className="h-6" />
        <Button variant="outline" size="sm" onClick={saveDocument}>
          <Save className="h-4 w-4 mr-1" /> 保存
        </Button>

        {/* AI operations */}
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}>
              <Sparkles className="h-4 w-4 mr-1" /> AI
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => runAIOperation("polish")}>
              润色文本
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => runAIOperation("expand")}>
              扩展内容
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => runAIOperation("compress")}>
              精简压缩
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => runAIOperation("fix")}>
              修正语法拼写
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => runAIOperation("translate_zh")}>
              翻译为中文
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => runAIOperation("translate_en")}>
              翻译为英文
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Export dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}>
              <Download className="h-4 w-4 mr-1" /> 导出
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => handleExport("markdown")}>
              Markdown (.md)
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport("html")}>
              HTML (.html)
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport("latex")}>
              LaTeX (.tex)
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport("docx")}>
              Word (.docx)
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Standardize */}
        <Button variant="outline" size="sm" onClick={() => setStandardizeOpen(true)}>
          <Sparkles className="h-4 w-4 mr-1" /> 标准化
        </Button>

        {/* Version history */}
        <Button variant="outline" size="sm" onClick={() => setVersionHistoryOpen(true)}>
          <Clock className="h-4 w-4 mr-1" /> 历史
        </Button>
      </header>

      {/* Toolbar */}
      <div className="border-b px-4 py-1 flex items-center gap-1 overflow-x-auto bg-muted/30">
        <ToolbarButton onClick={toggleBold} isActive={editor.isActive("bold")} title="加粗 (Ctrl+B)">
          <Bold className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleItalic} isActive={editor.isActive("italic")} title="斜体 (Ctrl+I)">
          <Italic className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleUnderline} isActive={editor.isActive("underline")} title="下划线 (Ctrl+U)">
          <UnderlineIcon className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleStrike} isActive={editor.isActive("strike")} title="删除线">
          <Strikethrough className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleCode} isActive={editor.isActive("code")} title="行内代码">
          <Code className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleHighlight} isActive={editor.isActive("highlight")} title="高亮">
          <Highlighter className="h-4 w-4" />
        </ToolbarButton>

        <Separator orientation="vertical" className="h-6 mx-1" />

        <ToolbarButton onClick={toggleHeading1} isActive={editor.isActive("heading", { level: 1 })} title="标题 1">
          <Heading1 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleHeading2} isActive={editor.isActive("heading", { level: 2 })} title="标题 2">
          <Heading2 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleHeading3} isActive={editor.isActive("heading", { level: 3 })} title="标题 3">
          <Heading3 className="h-4 w-4" />
        </ToolbarButton>

        <Separator orientation="vertical" className="h-6 mx-1" />

        <ToolbarButton onClick={toggleBulletList} isActive={editor.isActive("bulletList")} title="无序列表">
          <List className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleOrderedList} isActive={editor.isActive("orderedList")} title="有序列表">
          <ListOrdered className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleTaskList} isActive={editor.isActive("taskList")} title="任务列表">
          <CheckSquare className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleBlockquote} isActive={editor.isActive("blockquote")} title="引用块">
          <Quote className="h-4 w-4" />
        </ToolbarButton>

        <Separator orientation="vertical" className="h-6 mx-1" />

        <ToolbarButton onClick={alignLeft} isActive={editor.isActive({ textAlign: "left" })} title="左对齐">
          <AlignLeft className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={alignCenter} isActive={editor.isActive({ textAlign: "center" })} title="居中">
          <AlignCenter className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={alignRight} isActive={editor.isActive({ textAlign: "right" })} title="右对齐">
          <AlignRight className="h-4 w-4" />
        </ToolbarButton>

        <Separator orientation="vertical" className="h-6 mx-1" />

        <ToolbarButton onClick={setHorizontalRule} title="分割线">
          <Minus className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={undo} title="撤销 (Ctrl+Z)">
          <Undo className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton onClick={redo} title="重做 (Ctrl+Y)">
          <Redo className="h-4 w-4" />
        </ToolbarButton>
      </div>

      {/* Editor */}
      <div className="flex-1 overflow-y-auto">
        <EditorContent editor={editor} />
      </div>

      {/* Status bar */}
      <footer className="border-t px-4 py-1 flex items-center gap-4 text-xs text-muted-foreground bg-muted/30">
        <span>字数: {editor.storage.characterCount?.words() || 0}</span>
        <span>字符: {editor.storage.characterCount?.characters() || 0}</span>
        <div className="flex-1" />
        <span>TipTap + KaTeX</span>
      </footer>

      <VersionHistory
        docId={docId}
        open={versionHistoryOpen}
        onOpenChange={setVersionHistoryOpen}
        onRestore={handleVersionRestore}
      />

      <StandardizePanel
        documentId={Number(docId)}
        open={standardizeOpen}
        onClose={() => setStandardizeOpen(false)}
        onApplied={() => toast.success("自动分类完成")}
      />
    </div>
  )
}
