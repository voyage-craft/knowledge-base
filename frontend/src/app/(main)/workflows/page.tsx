"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { ReactFlowProvider } from "@xyflow/react"
import dynamic from "next/dynamic"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { OnboardingGuide, shouldShowOnboarding, resetOnboarding } from "@/components/workflows/OnboardingGuide"
import { apiTry } from "@/lib/api-client"
import { ProgressBanner } from "@/components/ui/progress-banner"

// Lazy-load WorkflowEditor (~200KB+ with @xyflow/react) — only loaded when editor view is active
const WorkflowEditor = dynamic(
  () => import("@/components/workflows/WorkflowEditor").then(m => ({ default: m.WorkflowEditor })),
  { ssr: false, loading: () => <div className="flex items-center justify-center h-full"><Loader2 className="h-6 w-6 animate-spin" /></div> }
)
import {
  ArrowLeft, Plus, Play, Trash2, Loader2, ChevronDown, ChevronRight,
  Workflow, Sparkles, FileText, Languages, ClipboardCheck, Expand,
  Clock, Zap, Calendar, Bell, X, CheckCircle2, XCircle, Timer,
} from "lucide-react"
import { toast } from "sonner"
import type { Node, Edge } from "@xyflow/react"

interface WorkflowItem {
  id: number
  name: string
  description: string | null
  template_type: string
  config_json: { nodes: any[]; edges: any[] }
  schedule_json: { cron: string; enabled: boolean } | null
  trigger_type: string
  trigger_config_json: Record<string, unknown> | null
  is_active: number
  last_run_at: string | null
  created_at: string | null
  updated_at: string | null
}

interface Template { key: string; name: string; description: string; nodes: any[]; edges: any[] }
interface WorkflowRun {
  id: number; workflow_id: number; status: string; total_docs: number
  processed_docs: number; results_json: any; error_message: string | null
  started_at: string | null; completed_at: string | null
}

const TEMPLATE_ICONS: Record<string, typeof Sparkles> = {
  batch_polish: Sparkles, summarize_tag: FileText, batch_translate: Languages,
  standardize: ClipboardCheck, content_expand: Expand,
}

const SCHEDULE_PRESETS = [
  { label: "每天 9:00", cron: "0 9 * * *" },
  { label: "每天 18:00", cron: "0 18 * * *" },
  { label: "每周一 9:00", cron: "0 9 * * 1" },
  { label: "每月 1 号", cron: "0 9 1 * *" },
]

const TRIGGER_OPTIONS = [
  { value: "none", label: "不自动触发" },
  { value: "on_import", label: "导入文档时" },
  { value: "on_save", label: "保存文档时" },
]

export default function WorkflowsPage() {
  const [view, setView] = useState<"list" | "editor">("list")
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([])
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)
  const [currentWorkflow, setCurrentWorkflow] = useState<WorkflowItem | null>(null)
  const [workflowName, setWorkflowName] = useState("")
  const [saving, setSaving] = useState(false)

  // Graph state from editor
  const graphRef = useRef<{ nodes: Node[]; edges: Edge[] }>({ nodes: [], edges: [] })
  const [editorKey, setEditorKey] = useState(0)

  // Quick-run dialog
  const [quickRunTmpl, setQuickRunTmpl] = useState<Template | null>(null)
  const [quickRunFilter, setQuickRunFilter] = useState("all")
  const [quickRunning, setQuickRunning] = useState(false)

  // Expanded runs
  const [expandedRuns, setExpandedRuns] = useState<Set<number>>(new Set())
  const [runDetails, setRunDetails] = useState<Record<number, WorkflowRun>>({})

  // Schedule/trigger config
  const [configuringWfId, setConfiguringWfId] = useState<number | null>(null)

  // Onboarding guide
  const [showOnboarding, setShowOnboarding] = useState(false)
  // Delete confirmation on list page
  const [confirmDeleteWfId, setConfirmDeleteWfId] = useState<number | null>(null)

  const fetchWorkflows = useCallback(async () => {
    const [data] = await apiTry<WorkflowItem[]>("/api/workflows")
    if (data) setWorkflows(data)
    setLoading(false)
  }, [])

  const fetchTemplates = useCallback(async () => {
    const [data] = await apiTry<Template[]>("/api/workflows/templates")
    if (data) setTemplates(data)
  }, [])

  useEffect(() => { fetchWorkflows(); fetchTemplates() }, [fetchWorkflows, fetchTemplates])

  // ── Quick Run ──
  async function handleQuickRun() {
    if (!quickRunTmpl) return
    setQuickRunning(true)
    const [data, err] = await apiTry("/api/workflows/quick-execute", {
      method: "POST",
      body: JSON.stringify({ template_key: quickRunTmpl.key, filter: quickRunFilter }),
    })
    if (data && !err) {
      toast.success(`${quickRunTmpl.name} 已开始执行`)
      setQuickRunTmpl(null)
      fetchWorkflows()
    } else {
      toast.error(err?.message || "执行失败")
    }
    setQuickRunning(false)
  }

  // ── Create/Edit ──
  async function handleCreateFromTemplate(tmpl: Template) {
    const [data] = await apiTry<WorkflowItem>("/api/workflows/from-template", {
      method: "POST", body: JSON.stringify({ template_key: tmpl.key }),
    })
    if (data) { openEditor(data); fetchWorkflows() }
  }

  async function handleCreateEmpty() {
    const [data] = await apiTry<WorkflowItem>("/api/workflows", {
      method: "POST", body: JSON.stringify({ name: "新建工作流", description: "", config_json: { nodes: [], edges: [] } }),
    })
    if (data) { openEditor(data); fetchWorkflows() }
  }

  function openEditor(wf: WorkflowItem) {
    setCurrentWorkflow(wf)
    setWorkflowName(wf.name)
    setEditorKey(k => k + 1) // force re-mount
    setView("editor")
    // Show onboarding for first-time users
    if (shouldShowOnboarding()) {
      setTimeout(() => setShowOnboarding(true), 500)
    }
  }

  const handleGraphChange = useCallback((nodes: Node[], edges: Edge[]) => {
    graphRef.current = { nodes, edges }
  }, [])

  async function handleSave() {
    if (!currentWorkflow) return
    setSaving(true)
    const { nodes, edges } = graphRef.current
    const configNodes = nodes.map(n => ({
      id: n.id, type: (n.data as any)?.moduleType || "unknown",
      label: (n.data as any)?.label || "", config: (n.data as any)?.config || {},
      position: n.position,
    }))
    const configEdges = edges.map(e => ({ source: e.source, target: e.target, type: e.type || "deletable" }))

    const [, err] = await apiTry(`/api/workflows/${currentWorkflow.id}`, {
      method: "PUT", body: JSON.stringify({ name: workflowName, config_json: { nodes: configNodes, edges: configEdges } }),
    })
    if (!err) { toast.success("已保存"); fetchWorkflows() }
    setSaving(false)
  }

  async function handleDelete(wfId: number) {
    if (confirmDeleteWfId === wfId) {
      // Second click = confirmed
      const [, err] = await apiTry(`/api/workflows/${wfId}`, { method: "DELETE" })
      if (!err) { toast.success("已删除"); fetchWorkflows() }
      setConfirmDeleteWfId(null)
    } else {
      setConfirmDeleteWfId(wfId)
      toast.info("再次点击确认删除")
      setTimeout(() => setConfirmDeleteWfId(prev => prev === wfId ? null : prev), 3000)
    }
  }

  const [runningRunId, setRunningRunId] = useState<number | null>(null)

  async function handleRunWorkflow(wfId: number) {
    const [data, err] = await apiTry<{ id: number }>("/api/workflows/execute", {
      method: "POST", body: JSON.stringify({ workflow_id: wfId }),
    })
    if (!err && data) {
      toast.success("工作流已开始执行")
      setRunningRunId(data.id)
      fetchWorkflows()
    }
  }

  // ── Trigger/Schedule ──
  async function updateTrigger(wfId: number, triggerType: string) {
    const [, err] = await apiTry(`/api/workflows/${wfId}/trigger`, {
      method: "PUT", body: JSON.stringify({ trigger_type: triggerType, trigger_config_json: null }),
    })
    if (!err) fetchWorkflows()
  }

  async function updateSchedule(wfId: number, cron: string | null) {
    const scheduleJson = cron ? { cron, enabled: true } : null
    const [, err] = await apiTry(`/api/workflows/${wfId}`, {
      method: "PUT", body: JSON.stringify({ schedule_json: scheduleJson }),
    })
    if (!err) fetchWorkflows()
  }

  // ── Run details ──
  async function fetchRunDetail(runId: number) {
    if (runDetails[runId]) return
    try {
      const res = await fetch(`/api/workflows/run/${runId}`)
      if (res.ok) {
        const data = await res.json()
        setRunDetails(prev => ({ ...prev, [runId]: data }))
      }
    } catch { /* ignore */ }
  }

  function toggleRunExpand(runId: number) {
    setExpandedRuns(prev => {
      const next = new Set(prev)
      if (next.has(runId)) { next.delete(runId) } else { next.add(runId); fetchRunDetail(runId) }
      return next
    })
  }

  function getNodeColor(type: string): string {
    const colors: Record<string, string> = {
      source: "bg-emerald-500", polish: "bg-blue-500", expand: "bg-indigo-500",
      compress: "bg-purple-500", translate_zh: "bg-teal-500", translate_en: "bg-cyan-500",
      fix: "bg-amber-500", summarize: "bg-sky-500", keywords: "bg-orange-500",
      auto_tag: "bg-rose-500", standardize: "bg-violet-500", custom_prompt: "bg-pink-500",
      save: "bg-green-600",
    }
    return colors[type] || "bg-slate-500"
  }

  if (loading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
  }

  // ── Editor View ──
  if (view === "editor" && currentWorkflow) {
    const initNodes: Node[] = (currentWorkflow.config_json?.nodes || []).map((n: any, i: number) => ({
      id: n.id || `node_${i}`, type: "workflow",
      position: n.position || { x: 250, y: i * 150 + 50 },
      data: { label: n.label, moduleType: n.type, color: getNodeColor(n.type), config: n.config || {} },
    }))
    const initEdges: Edge[] = (currentWorkflow.config_json?.edges || []).map((e: any, i: number) => ({
      id: `edge_${i}`, source: e.source, target: e.target, type: "deletable", animated: true, style: { stroke: "#94a3b8", strokeWidth: 2 },
    }))

    return (
      <ReactFlowProvider>
        <div className="flex flex-col h-full">
          <div className="border-b px-6 py-3 flex items-center gap-4 shrink-0">
            <Button variant="ghost" size="sm" onClick={() => { setView("list"); fetchWorkflows() }}>
              <ArrowLeft className="h-4 w-4 mr-1" /> 返回
            </Button>
            <Input value={workflowName} onChange={e => setWorkflowName(e.target.value)} className="max-w-xs h-8" />
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : null}保存
            </Button>
            <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground"
              onClick={() => { resetOnboarding(); setShowOnboarding(true) }} title="重新查看引导">
              使用引导
            </Button>
            <span className="text-xs text-muted-foreground ml-auto">
              {currentWorkflow.template_type === "preset" ? "预设模板" : "自定义"} · {initNodes.length} 个节点
            </span>
          </div>
          <div className="flex-1 min-h-0">
            <WorkflowEditor key={editorKey} initialNodes={initNodes} initialEdges={initEdges} onGraphChange={handleGraphChange} />
          </div>
        </div>
        {showOnboarding && (
          <OnboardingGuide onComplete={() => setShowOnboarding(false)} />
        )}
      </ReactFlowProvider>
    )
  }

  // ── List View ──
  return (
    <>
      <header className="border-b px-6 py-4 shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">AI 工作流</h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              可视化拖拽组合 AI 处理模块，支持定时执行和事件触发
            </p>
          </div>
          <Button onClick={handleCreateEmpty}><Plus className="h-4 w-4 mr-1" /> 新建工作流</Button>
        </div>
      </header>

      {/* Workflow execution progress */}
      {runningRunId && (
        <ProgressBanner
          pollUrl={`/api/workflows/run/${runningRunId}`}
          interval={2000}
          steps={["准备文档", "AI 处理中", "保存结果", "完成"]}
          onComplete={() => {
            toast.success("工作流执行完成")
            setRunningRunId(null)
            fetchWorkflows()
          }}
          onError={(err) => {
            toast.error(`工作流执行失败: ${err}`)
            setRunningRunId(null)
          }}
          onDismiss={() => setRunningRunId(null)}
        />
      )}

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-8">

          {/* ── Preset Templates ── */}
          {templates.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold mb-3">预设模板 · 快速执行</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {templates.map(tmpl => {
                  const Icon = TEMPLATE_ICONS[tmpl.key] || Workflow
                  return (
                    <Card key={tmpl.key} className="group">
                      <CardContent className="p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <Icon className="h-5 w-5 text-blue-500" />
                          <span className="font-medium text-sm">{tmpl.name}</span>
                        </div>
                        <p className="text-xs text-muted-foreground mb-3">{tmpl.description}</p>
                        <p className="text-[10px] text-muted-foreground/70 mb-3">{tmpl.nodes.length} 个步骤</p>
                        <div className="flex gap-2">
                          <Button size="sm" className="flex-1 h-7 text-xs" onClick={() => { setQuickRunTmpl(tmpl); setQuickRunFilter("all") }}>
                            <Zap className="h-3 w-3 mr-1" /> 快速执行
                          </Button>
                          <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => handleCreateFromTemplate(tmpl)}>
                            <Plus className="h-3 w-3" />
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            </section>
          )}

          {/* ── User Workflows ── */}
          <section>
            <h2 className="text-sm font-semibold mb-3">我的工作流</h2>
            {workflows.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Workflow className="h-12 w-12 mx-auto mb-3 opacity-20" />
                <p className="text-sm">还没有工作流</p>
                <p className="text-xs mt-1">从预设模板快速执行，或新建自定义工作流</p>
              </div>
            ) : (
              <div className="space-y-3">
                {workflows.map(wf => (
                  <Card key={wf.id} className="overflow-hidden">
                    <CardContent className="p-0">
                      {/* Main row */}
                      <div className="p-4 flex items-center gap-3">
                        <div className="flex-1 cursor-pointer" onClick={() => openEditor(wf)}>
                          <div className="flex items-center gap-2">
                            <Workflow className="h-4 w-4 text-blue-500" />
                            <span className="font-medium text-sm">{wf.name}</span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                              {wf.template_type === "preset" ? "预设" : "自定义"}
                            </span>
                            {wf.trigger_type !== "none" && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 flex items-center gap-0.5">
                                <Bell className="h-2.5 w-2.5" />
                                {wf.trigger_type === "on_import" ? "导入触发" : "保存触发"}
                              </span>
                            )}
                            {wf.schedule_json?.enabled && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 flex items-center gap-0.5">
                                <Calendar className="h-2.5 w-2.5" />
                                {wf.schedule_json.cron}
                              </span>
                            )}
                          </div>
                          {wf.description && <p className="text-xs text-muted-foreground mt-0.5 ml-6">{wf.description}</p>}
                          <p className="text-[10px] text-muted-foreground/70 mt-1 ml-6">
                            {(wf.config_json?.nodes || []).length} 个节点
                            {wf.last_run_at && ` · 上次运行 ${new Date(wf.last_run_at).toLocaleString("zh-CN")}`}
                          </p>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-1 shrink-0">
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => handleRunWorkflow(wf.id)} title="执行">
                            <Play className="h-3.5 w-3.5 text-green-600" />
                          </Button>
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0"
                            onClick={() => setConfiguringWfId(configuringWfId === wf.id ? null : wf.id)} title="配置定时/触发">
                            <Settings2Icon className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="ghost" size="sm" className={`h-7 w-7 p-0 ${confirmDeleteWfId === wf.id ? "bg-red-100 dark:bg-red-900" : ""}`} onClick={() => handleDelete(wf.id)} title={confirmDeleteWfId === wf.id ? "再次点击确认删除" : "删除"}>
                            <Trash2 className={`h-3.5 w-3.5 ${confirmDeleteWfId === wf.id ? "text-red-500" : "text-muted-foreground hover:text-red-500"}`} />
                          </Button>
                        </div>
                      </div>

                      {/* Config panel (schedule/trigger) */}
                      {configuringWfId === wf.id && (
                        <div className="border-t px-4 py-3 bg-slate-50 dark:bg-slate-900 space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium">自动触发</span>
                          </div>
                          <div className="flex gap-2">
                            {TRIGGER_OPTIONS.map(opt => (
                              <Button key={opt.value} variant={wf.trigger_type === opt.value ? "default" : "outline"}
                                size="sm" className="h-7 text-xs"
                                onClick={() => updateTrigger(wf.id, opt.value)}>
                                {opt.label}
                              </Button>
                            ))}
                          </div>
                          <div className="flex items-center justify-between mt-2">
                            <span className="text-xs font-medium">定时执行</span>
                            {wf.schedule_json?.enabled && (
                              <Button variant="ghost" size="sm" className="h-6 text-xs text-red-500"
                                onClick={() => updateSchedule(wf.id, null)}>
                                <X className="h-3 w-3 mr-1" /> 取消定时
                              </Button>
                            )}
                          </div>
                          <div className="flex gap-2 flex-wrap">
                            {SCHEDULE_PRESETS.map(preset => (
                              <Button key={preset.cron}
                                variant={wf.schedule_json?.cron === preset.cron ? "default" : "outline"}
                                size="sm" className="h-7 text-xs"
                                onClick={() => updateSchedule(wf.id, preset.cron)}>
                                {preset.label}
                              </Button>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Execution history */}
                      <WorkflowRunHistory workflowId={wf.id} expandedRuns={expandedRuns}
                        runDetails={runDetails} onToggle={toggleRunExpand} />
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>

      {/* ── Quick Run Dialog ── */}
      {quickRunTmpl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <Card className="w-96 shadow-xl">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">快速执行 · {quickRunTmpl.name}</CardTitle>
                <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => setQuickRunTmpl(null)}>
                  <X className="h-3 w-3" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-medium">文档范围</label>
                <select value={quickRunFilter} onChange={e => setQuickRunFilter(e.target.value)}
                  className="flex h-8 w-full rounded-md border border-input bg-background px-2 text-xs">
                  <option value="all">全部文档</option>
                  <option value="status:draft">草稿文档</option>
                  <option value="status:published">已发布文档</option>
                </select>
              </div>
              <p className="text-xs text-muted-foreground">{quickRunTmpl.description}</p>
              <div className="flex gap-2 justify-end">
                <Button variant="outline" size="sm" onClick={() => setQuickRunTmpl(null)}>取消</Button>
                <Button size="sm" onClick={handleQuickRun} disabled={quickRunning}>
                  {quickRunning ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Zap className="h-3 w-3 mr-1" />}
                  执行
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  )
}

// ── Settings icon (not in lucide default set, use Timer as alias) ──
function Settings2Icon({ className }: { className?: string }) {
  return <Timer className={className} />
}

// ── Inline run history for a workflow card ──
function WorkflowRunHistory({ workflowId, expandedRuns, runDetails, onToggle }: {
  workflowId: number
  expandedRuns: Set<number>
  runDetails: Record<number, WorkflowRun>
  onToggle: (id: number) => void
}) {
  const [runs, setRuns] = useState<WorkflowRun[]>([])
  const [loaded, setLoaded] = useState(false)
  const [show, setShow] = useState(false)

  async function loadRuns() {
    try {
      const res = await fetch(`/api/workflows/${workflowId}/runs`)
      if (res.ok) setRuns(await res.json())
    } catch { /* ignore */ }
    setLoaded(true)
  }

  useEffect(() => { if (show && !loaded) loadRuns() }, [show, loaded])

  // Reset loaded state when workflowId changes so runs are re-fetched
  useEffect(() => { setLoaded(false); setRuns([]) }, [workflowId])

  const statusIcon = (s: string) => {
    if (s === "completed") return <CheckCircle2 className="h-3 w-3 text-green-500" />
    if (s === "failed") return <XCircle className="h-3 w-3 text-red-500" />
    if (s === "running") return <Loader2 className="h-3 w-3 text-blue-500 animate-spin" />
    return <Clock className="h-3 w-3 text-muted-foreground" />
  }
  const statusLabel = (s: string) => ({ completed: "完成", failed: "失败", running: "运行中", pending: "等待" }[s] || s)

  return (
    <div className="border-t">
      <button onClick={() => { setShow(!show); if (!loaded) loadRuns() }}
        className="w-full flex items-center gap-2 px-4 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors">
        {show ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        执行历史 {runs.length > 0 && `(${runs.length})`}
      </button>
      {show && (
        <div className="px-4 pb-3 space-y-1">
          {!loaded ? (
            <div className="flex justify-center py-2"><Loader2 className="h-3 w-3 animate-spin" /></div>
          ) : runs.length === 0 ? (
            <p className="text-xs text-muted-foreground py-2">暂无执行记录</p>
          ) : (
            runs.slice(0, 10).map(run => (
              <div key={run.id} className="rounded border text-xs">
                <button onClick={() => onToggle(run.id)}
                  className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-muted/50 transition-colors">
                  {statusIcon(run.status)}
                  <span className="font-medium">{statusLabel(run.status)}</span>
                  <span className="text-muted-foreground">#{run.id}</span>
                  <span className="ml-auto text-muted-foreground">
                    {run.processed_docs}/{run.total_docs} · {run.started_at ? new Date(run.started_at).toLocaleString("zh-CN") : "-"}
                  </span>
                  {expandedRuns.has(run.id) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                </button>
                {expandedRuns.has(run.id) && (
                  <div className="px-3 py-2 border-t bg-muted/30 space-y-1">
                    {run.error_message && <p className="text-red-500">{run.error_message}</p>}
                    {runDetails[run.id]?.results_json?.documents ? (
                      <div className="space-y-1">
                        {(runDetails[run.id].results_json.documents as any[]).map((doc: any, i: number) => (
                          <div key={i} className="flex items-center gap-2 text-[11px]">
                            <FileText className="h-3 w-3 text-muted-foreground shrink-0" />
                            <span className="truncate flex-1">{doc.title}</span>
                            <span className="text-muted-foreground">{doc.actions?.join(" → ")}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-muted-foreground">处理了 {run.processed_docs} 篇文档</p>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
