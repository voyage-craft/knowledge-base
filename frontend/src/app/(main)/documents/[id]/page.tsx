"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import {
  ArrowLeft, Edit3, Clock, Tag,
  Sparkles, Loader2, Eye, Network,
} from "lucide-react"
import { apiTry } from "@/lib/api-client"
import { EditorContent } from "@tiptap/react"
import { useKnowledgeEditor } from "@/lib/use-knowledge-editor"

interface DocumentData {
  id: number
  title: string
  content_json: any
  status: string
  folder_id: number | null
  version: number
  created_at: string
  updated_at: string
  tags: { id: number; name: string; color: string }[]
}

export default function DocumentPreviewPage() {
  const params = useParams()
  const router = useRouter()
  const docId = params.id as string
  const [doc, setDoc] = useState<DocumentData | null>(null)
  const [loading, setLoading] = useState(true)
  const [showAiSummary, setShowAiSummary] = useState(false)
  const [aiSummary, setAiSummary] = useState<string | null>(null)
  const [summarizing, setSummarizing] = useState(false)

  const editor = useKnowledgeEditor({
    editable: false,
    enableCharacterCount: false,
    className: "prose prose-sm sm:prose lg:prose-lg xl:prose-xl max-w-none focus:outline-none min-h-[400px] px-8 py-6",
  })

  useEffect(() => {
    async function loadDocument() {
      const [data, err] = await apiTry<DocumentData>(`/api/documents/${docId}`)
      if (data) {
        setDoc(data)
        if (data.content_json && editor) {
          let content = data.content_json
          if (typeof content === "string") {
            try { content = JSON.parse(content) } catch { content = null }
          }
          if (content) editor.commands.setContent(content)
        }
      } else {
        toast.error(err?.message || "文档不存在")
        router.push("/documents")
      }
      setLoading(false)
    }
    if (editor) loadDocument()
  }, [docId, editor, router])

  async function handleSummarize() {
    if (!doc) return
    setSummarizing(true)
    setShowAiSummary(true)
    setAiSummary(null)

    try {
      toast.info("正在生成 AI 摘要...")
      const res = await fetch("/api/ai/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: editor?.state.doc.textBetween(0, editor.state.doc.content.size, "\n") || "",
          operation: "compress",
          context: "Generate a concise summary of this document",
        }),
      })

      if (!res.ok) {
        toast.error("AI 服务不可用")
        setSummarizing(false)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) { setSummarizing(false); return }

      const decoder = new TextDecoder()
      let result = ""
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        result += decoder.decode(value, { stream: true })
      }

      setAiSummary(result || "未能生成摘要")
      if (result) toast.success("AI 摘要生成完成")
    } catch {
      toast.error("AI 摘要生成失败")
    }
    setSummarizing(false)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!doc) return null

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="border-b px-4 py-3 flex items-center gap-3 bg-background shrink-0">
        <Button variant="ghost" size="icon" onClick={() => router.push("/documents")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>

        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-semibold truncate">{doc.title}</h1>
          <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {doc.updated_at ? new Date(doc.updated_at).toLocaleString("zh-CN") : "未知"}
            </span>
            <span>v{doc.version}</span>
            {doc.tags?.length > 0 && (
              <span className="flex items-center gap-1">
                <Tag className="h-3 w-3" />
                {doc.tags.map(t => t.name).join(", ")}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => router.push("/graph")} title="在知识图谱中查看">
            <Network className="h-3.5 w-3.5 mr-1.5" />
            图谱
          </Button>
          <Button variant="outline" size="sm" onClick={handleSummarize} disabled={summarizing}>
            {summarizing ? (
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5 mr-1.5" />
            )}
            AI 摘要
          </Button>
          <Button size="sm" onClick={() => router.push(`/editor/${docId}`)}>
            <Edit3 className="h-3.5 w-3.5 mr-1.5" />
            编辑
          </Button>
        </div>
      </header>

      {/* AI Summary Panel */}
      {showAiSummary && (
        <div className="border-b bg-blue-50 dark:bg-blue-950/30 px-6 py-4 shrink-0">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium flex items-center gap-1.5">
                <Sparkles className="h-4 w-4 text-blue-500" />
                AI 摘要
              </h3>
              <button onClick={() => setShowAiSummary(false)} className="text-muted-foreground hover:text-foreground">
                <span className="text-xs">关闭</span>
              </button>
            </div>
            {summarizing ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                正在生成摘要...
              </div>
            ) : (
              <p className="text-sm text-foreground/80 whitespace-pre-wrap">{aiSummary}</p>
            )}
          </div>
        </div>
      )}

      {/* Document Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          <EditorContent editor={editor} />
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t px-4 py-2 flex items-center gap-4 text-xs text-muted-foreground bg-muted/30 shrink-0">
        <span>只读模式</span>
        <span className="flex items-center gap-1">
          <Eye className="h-3 w-3" />
          预览
        </span>
        <div className="flex-1" />
        <span>v{doc.version}</span>
      </footer>
    </div>
  )
}
