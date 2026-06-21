"use client"

import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2, CheckCircle2, XCircle, Clock, Play, RotateCcw } from "lucide-react"

interface WorkflowRun {
  id: number
  workflow_id: number
  status: "pending" | "running" | "completed" | "failed"
  total_docs: number
  processed_docs: number
  results_json: Record<string, unknown> | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
}

interface ExecutionPanelProps {
  workflowId: number
  onExecute?: () => void
}

export function ExecutionPanel({ workflowId, onExecute }: ExecutionPanelProps) {
  const [runs, setRuns] = useState<WorkflowRun[]>([])
  const [loading, setLoading] = useState(true)
  const [executing, setExecuting] = useState(false)
  const [polling, setPolling] = useState(false)

  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch(`/api/workflows/${workflowId}/runs`)
      if (res.ok) {
        const data = await res.json()
        setRuns(data)
        // Stop polling if no active runs
        const hasActive = data.some((r: WorkflowRun) => r.status === "pending" || r.status === "running")
        if (!hasActive) setPolling(false)
      }
    } catch {
      // ignore
    }
    setLoading(false)
  }, [workflowId])

  useEffect(() => {
    fetchRuns()
  }, [fetchRuns])

  useEffect(() => {
    if (!polling) return
    const interval = setInterval(fetchRuns, 2000)
    return () => clearInterval(interval)
  }, [polling, fetchRuns])

  async function handleExecute() {
    setExecuting(true)
    try {
      const res = await fetch("/api/workflows/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow_id: workflowId }),
      })
      if (res.ok) {
        setPolling(true)
        await fetchRuns()
        onExecute?.()
      }
    } catch {
      // ignore
    }
    setExecuting(false)
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case "completed": return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case "failed": return <XCircle className="h-4 w-4 text-red-500" />
      case "running": return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
      default: return <Clock className="h-4 w-4 text-muted-foreground" />
    }
  }

  const statusLabel = (status: string) => {
    switch (status) {
      case "completed": return "已完成"
      case "failed": return "失败"
      case "running": return "运行中"
      default: return "等待中"
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">执行记录</h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchRuns}>
            <RotateCcw className="h-3 w-3 mr-1" /> 刷新
          </Button>
          <Button size="sm" onClick={handleExecute} disabled={executing}>
            {executing ? (
              <><Loader2 className="h-3 w-3 mr-1 animate-spin" /> 提交中...</>
            ) : (
              <><Play className="h-3 w-3 mr-1" /> 执行工作流</>
            )}
          </Button>
        </div>
      </div>

      {runs.length === 0 ? (
        <p className="text-xs text-muted-foreground py-4 text-center">尚无执行记录</p>
      ) : (
        <div className="space-y-2">
          {runs.slice(0, 10).map(run => (
            <Card key={run.id} className="overflow-hidden">
              <CardContent className="p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {statusIcon(run.status)}
                    <span className="text-sm font-medium">{statusLabel(run.status)}</span>
                    <span className="text-xs text-muted-foreground">#{run.id}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {run.started_at ? new Date(run.started_at).toLocaleString("zh-CN") : "-"}
                  </span>
                </div>

                {/* Progress bar */}
                {(run.status === "running" || run.status === "completed") && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>处理进度</span>
                      <span>{run.processed_docs}/{run.total_docs}</span>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${
                          run.status === "completed" ? "bg-green-500" : "bg-blue-500"
                        }`}
                        style={{ width: run.total_docs > 0 ? `${(run.processed_docs / run.total_docs) * 100}%` : "0%" }}
                      />
                    </div>
                  </div>
                )}

                {/* Error message */}
                {run.error_message && (
                  <p className="text-xs text-red-600 dark:text-red-400 mt-1">{run.error_message}</p>
                )}

                {/* Results summary */}
                {run.status === "completed" && run.results_json && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {(run.results_json as any).message || `已处理 ${run.processed_docs} 篇文档`}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
