"use client"

import { useState, useEffect } from "react"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { apiTry } from "@/lib/api-client"
import { toast } from "sonner"
import { Loader2, RotateCcw, Clock } from "lucide-react"

interface Version {
  id: number
  document_id: number
  version_number: number
  title: string
  created_at: string
}

interface VersionHistoryProps {
  docId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onRestore: (contentJson: unknown) => void
}

export function VersionHistory({ docId, open, onOpenChange, onRestore }: VersionHistoryProps) {
  const [versions, setVersions] = useState<Version[]>([])
  const [loading, setLoading] = useState(false)
  const [restoring, setRestoring] = useState<number | null>(null)

  useEffect(() => {
    if (open) fetchVersions()
  }, [open, docId])

  async function fetchVersions() {
    setLoading(true)
    const [data] = await apiTry<Version[]>(`/api/documents/${docId}/versions`)
    if (data) setVersions(data)
    setLoading(false)
  }

  async function handleRestore(versionId: number) {
    if (!confirm("确定要恢复到此版本吗？当前内容将自动保存为新版本。")) return
    setRestoring(versionId)
    const [data, err] = await apiTry<{ content_json: unknown }>(
      `/api/documents/${docId}/versions/${versionId}/restore`,
      { method: "POST" },
    )
    if (data) {
      onRestore(data.content_json)
      toast.success("版本已恢复")
      onOpenChange(false)
    } else {
      toast.error(err?.message || "恢复失败")
    }
    setRestoring(null)
  }

  function formatTime(dateStr: string) {
    const d = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return "刚刚"
    if (diffMin < 60) return `${diffMin} 分钟前`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr} 小时前`
    const diffDay = Math.floor(diffHr / 24)
    if (diffDay < 7) return `${diffDay} 天前`
    return d.toLocaleDateString("zh-CN")
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-80 p-0">
        <SheetHeader className="px-4 pt-4 pb-2 border-b">
          <SheetTitle className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            版本历史
          </SheetTitle>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              加载中...
            </div>
          ) : versions.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              暂无历史版本
              <p className="text-xs mt-1">编辑文档后将自动保存版本</p>
            </div>
          ) : (
            versions.map((v) => (
              <div
                key={v.id}
                className="flex items-center gap-3 p-3 rounded-lg border hover:bg-muted/50 transition-colors group"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{v.title || "无标题"}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    v{v.version_number} · {formatTime(v.created_at)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                  disabled={restoring !== null}
                  onClick={() => handleRestore(v.id)}
                >
                  {restoring === v.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RotateCcw className="h-3.5 w-3.5" />
                  )}
                </Button>
              </div>
            ))
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
