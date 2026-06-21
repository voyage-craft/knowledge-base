"use client"

import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { toast } from "sonner"
import {
  Loader2, Plus, Trash2, RefreshCw, Zap, Shield, ShieldOff,
  Activity, AlertTriangle, CheckCircle2, XCircle, Pause, Play,
  Lock, Unlock, Settings2, Route, ChevronDown, ChevronUp, X,
} from "lucide-react"
import { apiTry } from "@/lib/api-client"

// -- Types --

interface ProviderTemplate {
  key: string
  name: string
  description: string
  base_url: string
  protocol: string
  models: string[]
  color: string
  icon: string
}

interface Endpoint {
  id: number
  name: string
  provider: string
  base_url: string
  api_key: string
  protocol: string
  protocol_mode: string
  supported_models: string[]
  is_active: boolean
  priority: number
  status: string
  stats_json: Record<string, any>
  frozen_until: string | null
  timeout_ms: number
  created_at: string | null
  updated_at: string | null
}

interface RoutingRule {
  id: number
  model_id: string
  endpoint_id: number | null
  is_locked: boolean
  priority: number
  is_active: boolean
  max_requests_per_minute: number | null
}

interface HealthData {
  summary: { total: number; healthy: number; degraded: number; frozen: number; disabled: number }
  endpoints: {
    id: number
    name: string
    provider: string
    status: string
    success_rate: number | null
    avg_latency_ms: number
    total_requests: number
    consecutive_errors: number
    last_error: string | null
    frozen_until: string | null
  }[]
}

// -- Status helpers --

const STATUS_CONFIG: Record<string, { color: string; label: string; icon: typeof CheckCircle2 }> = {
  healthy: { color: "bg-green-500", label: "健康", icon: CheckCircle2 },
  degraded: { color: "bg-yellow-500", label: "降级", icon: AlertTriangle },
  frozen: { color: "bg-red-500", label: "冻结", icon: Pause },
  disabled: { color: "bg-gray-400", label: "禁用", icon: XCircle },
}

function StatusDot({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.disabled
  return (
    <span className="relative flex h-2.5 w-2.5">
      {status === "healthy" && (
        <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${cfg.color} opacity-40`} />
      )}
      <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${cfg.color}`} />
    </span>
  )
}

// -- Main Component --

export function ApiRoutesTab() {
  const [providers, setProviders] = useState<ProviderTemplate[]>([])
  const [endpoints, setEndpoints] = useState<Endpoint[]>([])
  const [rules, setRules] = useState<RoutingRule[]>([])
  const [health, setHealth] = useState<HealthData | null>(null)
  const [loading, setLoading] = useState(true)
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [addProvider, setAddProvider] = useState<ProviderTemplate | null>(null)
  const [showRules, setShowRules] = useState(false)
  const [editingEndpoint, setEditingEndpoint] = useState<Endpoint | null>(null)
  const [testingId, setTestingId] = useState<number | null>(null)

  const fetchAll = useCallback(async () => {
    const [provRes, epRes, ruleRes, healthRes] = await Promise.all([
      apiTry<ProviderTemplate[]>("/api/api-routes/providers"),
      apiTry<Endpoint[]>("/api/api-routes/endpoints"),
      apiTry<RoutingRule[]>("/api/api-routes/rules"),
      apiTry<HealthData>("/api/api-routes/health"),
    ])
    if (provRes[0]) setProviders(provRes[0])
    if (epRes[0]) setEndpoints(epRes[0])
    if (ruleRes[0]) setRules(ruleRes[0])
    if (healthRes[0]) setHealth(healthRes[0])
    setLoading(false)
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  async function handleTest(id: number) {
    setTestingId(id)
    const [data, err] = await apiTry<{ success: boolean; latency_ms: number; error?: string }>(
      `/api/api-routes/endpoints/${id}/test`,
      { method: "POST" }
    )
    if (data) {
      if (data.success) {
        toast.success(`连接成功，延迟 ${data.latency_ms}ms`)
      } else {
        toast.error(`连接失败: ${data.error || "未知错误"}`)
      }
      await fetchAll()
    } else {
      toast.error(err?.message || "测试失败")
    }
    setTestingId(null)
  }

  async function handleToggle(id: number) {
    const [data, err] = await apiTry<{ is_active: boolean }>(
      `/api/api-routes/endpoints/${id}/toggle`,
      { method: "POST" }
    )
    if (data) {
      toast.success(data.is_active ? "已启用" : "已禁用")
      await fetchAll()
    } else {
      toast.error(err?.message || "操作失败")
    }
  }

  async function handleUnfreeze(id: number) {
    const [data, err] = await apiTry("/api/api-routes/endpoints/" + id + "/unfreeze", { method: "POST" })
    if (data) {
      toast.success("已解除冻结")
      await fetchAll()
    } else {
      toast.error(err?.message || "解除冻结失败")
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("确定要删除此端点吗？相关的路由规则也会被删除。")) return
    const [data, err] = await apiTry(`/api/api-routes/endpoints/${id}`, { method: "DELETE" })
    if (data) {
      toast.success("已删除端点")
      await fetchAll()
    } else {
      toast.error(err?.message || "删除失败")
    }
  }

  async function handleDeleteRule(id: number) {
    if (!confirm("确定要删除此路由规则吗？")) return
    const [data, err] = await apiTry(`/api/api-routes/rules/${id}`, { method: "DELETE" })
    if (data) {
      toast.success("已删除规则")
      await fetchAll()
    } else {
      toast.error(err?.message || "删除失败")
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">加载 API 路由配置...</span>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Health Summary Bar */}
      {health && (
        <div className="grid grid-cols-5 gap-3">
          {[
            { label: "总计", value: health.summary.total, color: "text-foreground" },
            { label: "健康", value: health.summary.healthy, color: "text-green-600" },
            { label: "降级", value: health.summary.degraded, color: "text-yellow-600" },
            { label: "冻结", value: health.summary.frozen, color: "text-red-600" },
            { label: "禁用", value: health.summary.disabled, color: "text-gray-500" },
          ].map(item => (
            <div key={item.label} className="flex items-center gap-2 p-3 rounded-lg border">
              <span className="text-xs text-muted-foreground">{item.label}</span>
              <span className={`text-xl font-semibold ${item.color}`}>{item.value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Provider Templates */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">快速添加端点</CardTitle>
              <CardDescription>选择供应商模板，一键添加 API 端点</CardDescription>
            </div>
            <Button size="sm" variant="outline" onClick={() => { setAddProvider(null); setShowAddDialog(true) }}>
              <Plus className="h-4 w-4 mr-1" /> 自定义添加
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3">
            {providers.map(p => (
              <button
                key={p.key}
                onClick={() => { setAddProvider(p); setShowAddDialog(true) }}
                className="group relative flex flex-col items-start gap-1.5 p-3 rounded-lg border text-left transition-all hover:border-primary hover:shadow-sm"
              >
                <div className={`h-2 w-8 rounded-full ${p.color}`} />
                <span className="text-sm font-medium">{p.name}</span>
                <span className="text-xs text-muted-foreground line-clamp-1">{p.description}</span>
                <span className="text-[10px] text-muted-foreground/70 mt-0.5">
                  {p.models.length} 个模型
                </span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Endpoints List */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">API 端点</CardTitle>
              <CardDescription>管理已配置的 API 端点，系统自动进行智能调度</CardDescription>
            </div>
            <Button size="sm" variant="ghost" onClick={fetchAll}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {endpoints.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">
              <Route className="h-8 w-8 mx-auto mb-2 opacity-40" />
              <p>尚未配置任何 API 端点</p>
              <p className="text-xs mt-1">从上方模板快速添加，或自定义配置</p>
            </div>
          ) : (
            <div className="space-y-3">
              {endpoints.map(ep => {
                const stats = ep.stats_json || {}
                const totalReq = stats.total_requests || 0
                const successCount = stats.success_count || 0
                const successRate = totalReq > 0 ? Math.round(successCount / totalReq * 100) : null
                const avgLatency = stats.avg_latency_ms || 0
                const statusCfg = STATUS_CONFIG[ep.status] || STATUS_CONFIG.disabled

                return (
                  <div
                    key={ep.id}
                    className={`relative p-4 rounded-lg border transition-all ${
                      !ep.is_active ? "opacity-60" : ""
                    } ${ep.status === "frozen" ? "border-red-200 dark:border-red-900" : ""}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <StatusDot status={ep.status} />
                          <span className="font-medium text-sm">{ep.name}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                            {ep.provider}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                            {ep.protocol_mode === "auto"
                              ? (ep.stats_json?.detected_protocol_mode || "auto")
                              : ep.protocol_mode}
                          </span>
                          {ep.status === "frozen" && ep.frozen_until && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300">
                              冻结至 {new Date(ep.frozen_until).toLocaleTimeString()}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1 truncate">{ep.base_url}</p>

                        {/* Models */}
                        <div className="flex flex-wrap gap-1 mt-2">
                          {(ep.supported_models || []).slice(0, 5).map(m => (
                            <span key={m} className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300">
                              {m}
                            </span>
                          ))}
                          {(ep.supported_models || []).length > 5 && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
                              +{(ep.supported_models || []).length - 5}
                            </span>
                          )}
                        </div>

                        {/* Stats */}
                        <div className="flex items-center gap-4 mt-2 text-[11px] text-muted-foreground">
                          {successRate !== null && (
                            <span className={successRate >= 90 ? "text-green-600" : successRate >= 70 ? "text-yellow-600" : "text-red-600"}>
                              成功率 {successRate}%
                            </span>
                          )}
                          {avgLatency > 0 && <span>延迟 {Math.round(avgLatency)}ms</span>}
                          {totalReq > 0 && <span>{totalReq} 次请求</span>}
                          <span>优先级 {ep.priority}</span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 shrink-0">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0"
                          onClick={() => handleTest(ep.id)}
                          disabled={testingId === ep.id}
                          title="测试连接"
                        >
                          {testingId === ep.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Zap className="h-3.5 w-3.5" />
                          )}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0"
                          onClick={() => handleToggle(ep.id)}
                          title={ep.is_active ? "禁用" : "启用"}
                        >
                          {ep.is_active ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                        </Button>
                        {ep.status === "frozen" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0"
                            onClick={() => handleUnfreeze(ep.id)}
                            title="解除冻结"
                          >
                            <ShieldOff className="h-3.5 w-3.5" />
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0"
                          onClick={() => setEditingEndpoint(ep)}
                          title="编辑"
                        >
                          <Settings2 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0 text-red-500 hover:text-red-600"
                          onClick={() => handleDelete(ep.id)}
                          title="删除"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Routing Rules */}
      <Card>
        <CardHeader className="pb-3">
          <button
            className="flex items-center justify-between w-full"
            onClick={() => setShowRules(!showRules)}
          >
            <div className="text-left">
              <CardTitle className="text-base">路由规则</CardTitle>
              <CardDescription>配置模型到端点的路由规则，支持锁定和优先级</CardDescription>
            </div>
            {showRules ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </CardHeader>
        {showRules && (
          <CardContent>
            {rules.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">暂无路由规则</p>
            ) : (
              <div className="space-y-2">
                {rules.map(rule => {
                  const ep = endpoints.find(e => e.id === rule.endpoint_id)
                  return (
                    <div key={rule.id} className="flex items-center justify-between p-2.5 rounded-lg border">
                      <div className="flex items-center gap-2">
                        {rule.is_locked ? (
                          <Lock className="h-3.5 w-3.5 text-amber-600" />
                        ) : (
                          <Unlock className="h-3.5 w-3.5 text-muted-foreground" />
                        )}
                        <span className="text-sm font-mono">{rule.model_id}</span>
                        <span className="text-xs text-muted-foreground">→</span>
                        <span className="text-sm">{ep?.name || `端点 #${rule.endpoint_id}`}</span>
                        {rule.is_locked && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300">
                            已锁定
                          </span>
                        )}
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-red-500"
                        onClick={() => handleDeleteRule(rule.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )
                })}
              </div>
            )}
            <AddRuleDialog endpoints={endpoints} onAdded={fetchAll} />
          </CardContent>
        )}
      </Card>

      {/* Add/Edit Dialogs */}
      {showAddDialog && (
        <AddEndpointDialog
          providers={providers}
          preselectedProvider={addProvider}
          onClose={() => { setShowAddDialog(false); setAddProvider(null) }}
          onSaved={() => { setShowAddDialog(false); setAddProvider(null); fetchAll() }}
        />
      )}
      {editingEndpoint && (
        <EditEndpointDialog
          endpoint={editingEndpoint}
          onClose={() => setEditingEndpoint(null)}
          onSaved={() => { setEditingEndpoint(null); fetchAll() }}
        />
      )}
    </div>
  )
}

// -- Add Endpoint Dialog (with provider pre-selection support) --

function AddEndpointDialog({
  providers, preselectedProvider, onClose, onSaved,
}: {
  providers: ProviderTemplate[]
  preselectedProvider: ProviderTemplate | null
  onClose: () => void
  onSaved: () => void
}) {
  const [step, setStep] = useState(preselectedProvider ? 1 : 0)
  const [selectedProvider, setSelectedProvider] = useState<ProviderTemplate | null>(preselectedProvider)
  const [name, setName] = useState(preselectedProvider?.name || "")
  const [apiKey, setApiKey] = useState("")
  const [baseUrl, setBaseUrl] = useState(preselectedProvider?.base_url || "")
  const [selectedModels, setSelectedModels] = useState<string[]>(preselectedProvider?.models || [])
  const [customModels, setCustomModels] = useState("")
  const [priority, setPriority] = useState("100")
  const [protocolMode, setProtocolMode] = useState("auto")
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testPassed, setTestPassed] = useState(false)
  const [endpointId, setEndpointId] = useState<number | null>(null)

  // Escape key to close + body scroll lock
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", handleKey)
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", handleKey)
      document.body.style.overflow = ""
    }
  }, [onClose])

  function selectProvider(p: ProviderTemplate) {
    setSelectedProvider(p)
    setName(p.name)
    setBaseUrl(p.base_url)
    setSelectedModels(p.models)
    setStep(1)
  }

  function toggleModel(m: string) {
    setSelectedModels(prev =>
      prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m]
    )
  }

  async function handleSave() {
    if (!selectedProvider || !name) return
    setSaving(true)

    const allModels = [...selectedModels]
    if (customModels.trim()) {
      customModels.split(",").map(s => s.trim()).filter(Boolean).forEach(m => {
        if (!allModels.includes(m)) allModels.push(m)
      })
    }

    const [data, err] = await apiTry<Endpoint>("/api/api-routes/endpoints", {
      method: "POST",
      body: JSON.stringify({
        name,
        provider: selectedProvider.key,
        base_url: baseUrl,
        api_key: apiKey,
        protocol: selectedProvider.protocol,
        supported_models: allModels,
        priority: parseInt(priority) || 100,
        protocol_mode: protocolMode,
      }),
    })

    if (data) {
      setEndpointId(data.id)
      toast.success("端点已创建")
      if (apiKey) {
        // Auto-test after creation
        setTesting(true)
        const [testRes] = await apiTry<{ success: boolean; latency_ms: number }>(
          `/api/api-routes/endpoints/${data.id}/test`,
          { method: "POST" }
        )
        if (testRes?.success) {
          setTestPassed(true)
          toast.success(`连接成功，延迟 ${testRes.latency_ms}ms`)
        } else {
          toast.error("连接测试失败，请稍后手动测试")
        }
        setTesting(false)
      }
      // Refresh list but don't close — let user see the test result
      onSaved()
    } else {
      toast.error(err?.message || "创建失败")
    }
    setSaving(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-xl shadow-xl w-[560px] max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-base font-semibold">
            {step === 0 ? "选择供应商" : `添加 ${selectedProvider?.name} 端点`}
          </h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-muted"><X className="h-4 w-4" /></button>
        </div>

        {step === 0 ? (
          <div className="p-4 grid grid-cols-2 gap-3">
            {providers.map(p => (
              <button
                key={p.key}
                onClick={() => selectProvider(p)}
                className="flex flex-col items-start gap-1 p-3 rounded-lg border text-left hover:border-primary transition-colors"
              >
                <div className={`h-2 w-8 rounded-full ${p.color}`} />
                <span className="text-sm font-medium">{p.name}</span>
                <span className="text-xs text-muted-foreground">{p.description}</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="p-4 space-y-4">
            {/* Name */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">端点名称</label>
              <Input value={name} onChange={e => setName(e.target.value)} placeholder="如：智谱-主Key" />
            </div>

            {/* API Key */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">API Key</label>
              <Input
                type="password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder={selectedProvider?.protocol === "anthropic" ? "sk-ant-..." : "sk-..."}
              />
            </div>

            {/* Base URL */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">API 地址</label>
              <Input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} />
            </div>

            {/* Model selection */}
            {selectedProvider && selectedProvider.models.length > 0 && (
              <div className="space-y-1.5">
                <label className="text-sm font-medium">支持的模型</label>
                <div className="flex flex-wrap gap-1.5">
                  {selectedProvider.models.map(m => (
                    <button
                      key={m}
                      onClick={() => toggleModel(m)}
                      className={`text-xs px-2 py-1 rounded-full border transition-colors ${
                        selectedModels.includes(m)
                          ? "bg-blue-100 dark:bg-blue-950 border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300"
                          : "border-muted text-muted-foreground hover:border-foreground/30"
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Custom models */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">自定义模型 (逗号分隔)</label>
              <Input
                value={customModels}
                onChange={e => setCustomModels(e.target.value)}
                placeholder="model-a, model-b"
              />
            </div>

            {/* Priority */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">优先级 (数字越小优先级越高)</label>
              <Input
                type="number"
                value={priority}
                onChange={e => setPriority(e.target.value)}
                min="1"
                max="999"
              />
            </div>

            {/* Protocol Mode */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">API 协议模式</label>
              <select
                value={protocolMode}
                onChange={e => setProtocolMode(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="auto">自动探测 (推荐)</option>
                <option value="completions">Chat Completions (/v1/chat/completions)</option>
                <option value="responses">Responses (/v1/responses)</option>
              </select>
              <p className="text-xs text-muted-foreground">
                {protocolMode === "auto" && "首次测试时自动检测 API 类型，后续直接使用检测结果"}
                {protocolMode === "completions" && "强制使用 Chat Completions API（大多数兼容提供商使用此模式）"}
                {protocolMode === "responses" && "强制使用 Responses API（仅 OpenAI 原生支持）"}
              </p>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3 pt-2">
              <Button variant="outline" onClick={() => selectedProvider ? setStep(0) : onClose()}>
                {selectedProvider ? "上一步" : "取消"}
              </Button>
              <Button onClick={handleSave} disabled={saving || !name || !apiKey}>
                {saving ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
                {testing ? "测试中..." : testPassed ? "已保存" : "保存并测试"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// -- Edit Endpoint Dialog --

function EditEndpointDialog({
  endpoint, onClose, onSaved,
}: {
  endpoint: Endpoint
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState(endpoint.name)
  const [baseUrl, setBaseUrl] = useState(endpoint.base_url)
  const [apiKey, setApiKey] = useState("")
  const [models, setModels] = useState(endpoint.supported_models.join(", "))
  const [priority, setPriority] = useState(String(endpoint.priority))
  const [timeout, setTimeout_] = useState(String(endpoint.timeout_ms))
  const [protocolMode, setProtocolMode] = useState(endpoint.protocol_mode || "auto")
  const [saving, setSaving] = useState(false)

  // Escape key to close + body scroll lock
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", handleKey)
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", handleKey)
      document.body.style.overflow = ""
    }
  }, [onClose])

  async function handleSave() {
    setSaving(true)
    const updateData: Record<string, any> = { name, base_url: baseUrl, priority: parseInt(priority) || 100, timeout_ms: parseInt(timeout) || 60000, protocol_mode: protocolMode }
    if (apiKey) updateData.api_key = apiKey
    if (models.trim()) updateData.supported_models = models.split(",").map(s => s.trim()).filter(Boolean)

    const [data, err] = await apiTry(`/api/api-routes/endpoints/${endpoint.id}`, {
      method: "PUT",
      body: JSON.stringify(updateData),
    })

    if (data) {
      toast.success("端点已更新")
      onSaved()
    } else {
      toast.error(err?.message || "更新失败")
    }
    setSaving(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-xl shadow-xl w-[480px] max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-base font-semibold">编辑端点: {endpoint.name}</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-muted"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-4 space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">端点名称</label>
            <Input value={name} onChange={e => setName(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">API Key (留空不修改)</label>
            <Input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="留空保持不变" />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">API 地址</label>
            <Input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">支持的模型 (逗号分隔)</label>
            <Input value={models} onChange={e => setModels(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">优先级</label>
              <Input type="number" value={priority} onChange={e => setPriority(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">超时 (ms)</label>
              <Input type="number" value={timeout} onChange={e => setTimeout_(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">API 协议模式</label>
            <select
              value={protocolMode}
              onChange={e => setProtocolMode(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="auto">自动探测 (推荐)</option>
              <option value="completions">Chat Completions (/v1/chat/completions)</option>
              <option value="responses">Responses (/v1/responses)</option>
            </select>
          </div>
          <div className="flex items-center gap-3 pt-2">
            <Button variant="outline" onClick={onClose}>取消</Button>
            <Button onClick={handleSave} disabled={saving || !name}>
              {saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
              保存
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

// -- Add Rule Dialog (inline) --

function AddRuleDialog({ endpoints, onAdded }: { endpoints: Endpoint[]; onAdded: () => void }) {
  const [modelId, setModelId] = useState("")
  const [endpointId, setEndpointId] = useState("")
  const [isLocked, setIsLocked] = useState(false)
  const [saving, setSaving] = useState(false)

  async function handleAdd() {
    if (!modelId) return
    setSaving(true)

    let result, err
    if (isLocked && endpointId) {
      ;[result, err] = await apiTry("/api/api-routes/rules/lock", {
        method: "POST",
        body: JSON.stringify({ model_id: modelId, endpoint_id: parseInt(endpointId) }),
      })
    } else {
      ;[result, err] = await apiTry("/api/api-routes/rules", {
        method: "POST",
        body: JSON.stringify({
          model_id: modelId,
          endpoint_id: endpointId ? parseInt(endpointId) : null,
          is_locked: isLocked,
          priority: 100,
        }),
      })
    }

    if (err) {
      toast.error(err.message || "添加规则失败")
    } else {
      toast.success("规则已添加")
      setModelId("")
      setEndpointId("")
      setIsLocked(false)
      onAdded()
    }
    setSaving(false)
  }

  return (
    <div className="flex items-end gap-2 mt-3 p-3 rounded-lg border border-dashed">
      <div className="flex-1 space-y-1">
        <label className="text-xs text-muted-foreground">模型 ID</label>
        <Input value={modelId} onChange={e => setModelId(e.target.value)} placeholder="如 glm-4 或 *" className="h-8 text-xs" />
      </div>
      <div className="flex-1 space-y-1">
        <label className="text-xs text-muted-foreground">端点</label>
        <select
          value={endpointId}
          onChange={e => setEndpointId(e.target.value)}
          className="flex h-8 w-full rounded-md border border-input bg-background px-2 text-xs"
        >
          <option value="">自动选择</option>
          {endpoints.map(ep => (
            <option key={ep.id} value={ep.id}>{ep.name}</option>
          ))}
        </select>
      </div>
      <label className="flex items-center gap-1.5 text-xs cursor-pointer whitespace-nowrap pb-1">
        <input type="checkbox" checked={isLocked} onChange={e => setIsLocked(e.target.checked)} className="rounded" />
        <Lock className="h-3 w-3" /> 锁定
      </label>
      <Button size="sm" className="h-8" onClick={handleAdd} disabled={saving || !modelId}>
        {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
      </Button>
    </div>
  )
}
