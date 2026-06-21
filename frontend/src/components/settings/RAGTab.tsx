"use client"

import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { toast } from "sonner"
import { Loader2, Database, RefreshCw, Trash2, CheckCircle2, AlertCircle } from "lucide-react"
import { apiTry } from "@/lib/api-client"

interface EmbedStatus {
  total_documents: number
  embedded_documents: number
  total_chunks: number
}

export function RAGTab() {
  const [status, setStatus] = useState<EmbedStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const fetchStatus = useCallback(async () => {
    const [data] = await apiTry<EmbedStatus>("/api/rag/status")
    if (data) setStatus(data)
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  async function handleGenerateAll() {
    setGenerating(true)
    const [data, err] = await apiTry<{ message: string }>("/api/rag/embed-batch", {
      method: "POST",
      body: JSON.stringify({}),
    })
    if (data) {
      toast.success(data.message || "嵌入任务已提交")
      setTimeout(fetchStatus, 2000)
    } else {
      toast.error(err?.message || "生成嵌入失败")
    }
    setGenerating(false)
  }

  const coverage = status
    ? status.total_documents > 0
      ? Math.round((status.embedded_documents / status.total_documents) * 100)
      : 0
    : 0

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">加载嵌入状态...</span>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>RAG 检索增强</CardTitle>
          <CardDescription>
            RAG 将文档内容分块并生成嵌入向量，让 AI 对话能基于知识库内容回答问题
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Status overview */}
          <div className="grid grid-cols-3 gap-4">
            <div className="p-3 rounded-lg border">
              <p className="text-xs text-muted-foreground">文档总数</p>
              <p className="text-2xl font-semibold">{status?.total_documents ?? 0}</p>
            </div>
            <div className="p-3 rounded-lg border">
              <p className="text-xs text-muted-foreground">已嵌入文档</p>
              <p className="text-2xl font-semibold">{status?.embedded_documents ?? 0}</p>
            </div>
            <div className="p-3 rounded-lg border">
              <p className="text-xs text-muted-foreground">分块总数</p>
              <p className="text-2xl font-semibold">{status?.total_chunks ?? 0}</p>
            </div>
          </div>

          {/* Coverage bar */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">嵌入覆盖率</span>
              <span className="font-medium">{coverage}%</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-500"
                style={{ width: `${coverage}%` }}
              />
            </div>
          </div>

          {/* Coverage indicator */}
          {status && status.total_documents > 0 && (
            <div className={`flex items-start gap-2 p-3 rounded-lg text-sm ${
              coverage === 100
                ? "bg-green-50 dark:bg-green-950 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-800"
                : coverage > 0
                  ? "bg-yellow-50 dark:bg-yellow-950 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-800"
                  : "bg-red-50 dark:bg-red-950 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800"
            }`}>
              {coverage === 100 ? (
                <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
              ) : (
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              )}
              <div>
                <p className="font-medium">
                  {coverage === 100
                    ? "所有文档已生成嵌入向量"
                    : coverage > 0
                      ? "部分文档尚未生成嵌入"
                      : "尚未生成任何嵌入向量"}
                </p>
                <p className="text-xs mt-0.5 opacity-80">
                  {coverage < 100
                    ? "点击下方按钮为所有文档生成嵌入向量，以启用 RAG 检索功能"
                    : "RAG 检索功能已就绪，AI 对话将自动引用相关文档内容"}
                </p>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3">
            <Button
              onClick={handleGenerateAll}
              disabled={generating || !status || status.total_documents === 0}
            >
              {generating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  正在生成...
                </>
              ) : (
                <>
                  <Database className="h-4 w-4 mr-1" />
                  {coverage > 0 ? "重新生成全部嵌入" : "生成全部嵌入"}
                </>
              )}
            </Button>

            <Button
              variant="outline"
              onClick={fetchStatus}
              disabled={loading}
            >
              <RefreshCw className="h-4 w-4 mr-1" />
              刷新状态
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>使用说明</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>
            RAG（检索增强生成）通过将文档切分为小块并生成语义向量，
            使 AI 在对话时能检索知识库中的相关内容作为上下文，从而给出更准确的回答。
          </p>
          <p>
            系统使用 BAAI/bge-m3 嵌入模型（1024 维），首次加载模型可能需要几分钟。
            生成嵌入后，新保存或更新的文档需要重新生成嵌入。
          </p>
          <p>
            嵌入模型在后台运行，CPU 模式下约每秒处理 50 个文本块。
            建议在网络稳定时生成，如果中断可重新执行。
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
