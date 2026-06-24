"use client"

import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"
import { Loader2, Puzzle, RefreshCw, Trash2, Upload, ChevronDown, ChevronRight, AlertTriangle } from "lucide-react"
import { apiTry, apiFetch } from "@/lib/api-client"

interface PluginManifest {
  id: string
  plugin_id: string
  name: string
  version: string
  description: string
  author: string
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
  is_builtin: boolean
  is_compatible: boolean
  compatibility_message: string
  is_active: boolean
  error: string | null
  permissions: string[]
  changelog: Record<string, string>
}

export function PluginsTab() {
  const [plugins, setPlugins] = useState<PluginManifest[]>([])
  const [loading, setLoading] = useState(true)
  const [reloading, setReloading] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetchPlugins()
  }, [])

  async function fetchPlugins() {
    setLoading(true)
    const [data, err] = await apiTry<{ plugins: PluginManifest[]; total: number; active: number }>("/api/plugins")
    if (data) {
      setPlugins(data.plugins)
    } else {
      toast.error(err?.message || "加载插件列表失败")
    }
    setLoading(false)
  }

  async function handleReload() {
    setReloading(true)
    const [, err] = await apiTry("/api/plugins/reload", { method: "POST" })
    if (!err) {
      toast.success("插件已重新加载")
      await fetchPlugins()
    } else {
      toast.error(err.message || "重新加载失败")
    }
    setReloading(false)
  }

  async function handleInstall() {
    fileInputRef.current?.click()
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    setInstalling(true)
    const formData = new FormData()
    formData.append("file", file)

    try {
      const [data, err] = await apiTry<{ plugin: PluginManifest; message: string }>("/api/plugins/install", {
        method: "POST",
        body: formData,
      })
      if (data) {
        toast.success(data.message || "插件安装成功")
        await fetchPlugins()
      } else {
        toast.error(err?.message || "插件安装失败")
      }
    } finally {
      setInstalling(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  async function handleUninstall(pluginId: string) {
    if (!confirm("确定要卸载此插件吗？")) return

    const [, err] = await apiTry(`/api/plugins/${pluginId}/uninstall`, { method: "POST" })
    if (!err) {
      toast.success("插件已卸载")
      await fetchPlugins()
    } else {
      toast.error(err.message || "卸载失败")
    }
  }

  const builtinPlugins = plugins.filter(p => p.is_builtin)
  const thirdPartyPlugins = plugins.filter(p => !p.is_builtin)
  const activeCount = plugins.filter(p => p.is_active).length

  const categoryLabels: Record<string, string> = {
    input: "输入",
    process: "处理",
    output: "输出",
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">加载插件中...</span>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with actions */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold">插件管理</h3>
          <p className="text-xs text-muted-foreground">
            共 {plugins.length} 个插件，{activeCount} 个已激活
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleReload} disabled={reloading}>
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${reloading ? "animate-spin" : ""}`} />
            重新加载
          </Button>
          <Button variant="outline" size="sm" onClick={handleInstall} disabled={installing}>
            <Upload className="h-3.5 w-3.5 mr-1.5" />
            {installing ? "安装中..." : "安装插件"}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".kbplugin,.zip"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
      </div>

      {/* Third-party plugins section */}
      {thirdPartyPlugins.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-muted-foreground">第三方插件</h4>
          {thirdPartyPlugins.map(plugin => (
            <PluginCard
              key={plugin.id}
              plugin={plugin}
              expanded={expandedId === plugin.id}
              onToggle={() => setExpandedId(expandedId === plugin.id ? null : plugin.id)}
              onUninstall={() => handleUninstall(plugin.id)}
              categoryLabels={categoryLabels}
            />
          ))}
        </div>
      )}

      {/* Built-in plugins section */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-muted-foreground">内置插件</h4>
        {builtinPlugins.map(plugin => (
          <PluginCard
            key={plugin.id}
            plugin={plugin}
            expanded={expandedId === plugin.id}
            onToggle={() => setExpandedId(expandedId === plugin.id ? null : plugin.id)}
            categoryLabels={categoryLabels}
          />
        ))}
      </div>
    </div>
  )
}

function PluginCard({
  plugin,
  expanded,
  onToggle,
  onUninstall,
  categoryLabels,
}: {
  plugin: PluginManifest
  expanded: boolean
  onToggle: () => void
  onUninstall?: () => void
  categoryLabels: Record<string, string>
}) {
  return (
    <Card className={plugin.error || !plugin.is_compatible ? "border-amber-200 dark:border-amber-900" : ""}>
      <div
        className="flex items-center gap-3 p-4 cursor-pointer hover:bg-accent/50 transition-colors"
        onClick={onToggle}
      >
        <div className={`h-8 w-8 rounded-lg ${plugin.color} flex items-center justify-center text-white text-sm shrink-0`}>
          {plugin.name.charAt(0)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium truncate">{plugin.name}</span>
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 shrink-0">
              v{plugin.version}
            </Badge>
            {plugin.is_builtin && (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 shrink-0">
                内置
              </Badge>
            )}
            {!plugin.is_compatible && (
              <Badge variant="destructive" className="text-[10px] px-1.5 py-0 shrink-0">
                不兼容
              </Badge>
            )}
            {plugin.error && !plugin.is_compatible === false && (
              <Badge variant="destructive" className="text-[10px] px-1.5 py-0 shrink-0">
                错误
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground truncate">{plugin.description}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Badge variant="outline" className="text-[10px]">
            {categoryLabels[plugin.category] || plugin.category}
          </Badge>
          {expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
        </div>
      </div>

      {expanded && (
        <CardContent className="pt-0 space-y-3">
          {/* Error / Compatibility message */}
          {plugin.error && (
            <div className="flex items-start gap-2 p-2 bg-destructive/10 rounded text-xs text-destructive">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <span>{plugin.error}</span>
            </div>
          )}
          {!plugin.is_compatible && plugin.compatibility_message && (
            <div className="flex items-start gap-2 p-2 bg-amber-50 dark:bg-amber-950/30 rounded text-xs text-amber-700 dark:text-amber-400">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <span>{plugin.compatibility_message}</span>
            </div>
          )}

          {/* Details grid */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-muted-foreground">插件 ID：</span>{plugin.id}</div>
            <div><span className="text-muted-foreground">节点类型：</span>{plugin.node_type}</div>
            <div><span className="text-muted-foreground">作者：</span>{plugin.author}</div>
            <div><span className="text-muted-foreground">可配置：</span>{plugin.configurable ? "是" : "否"}</div>
          </div>

          {/* Config schema */}
          {plugin.config_schema && plugin.config_schema.fields.length > 0 && (
            <div>
              <p className="text-xs font-medium mb-1">配置项</p>
              <div className="flex flex-wrap gap-1">
                {plugin.config_schema.fields.map(f => (
                  <Badge key={f.key} variant="outline" className="text-[10px]">
                    {f.label}{f.advanced ? " *" : ""}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Permissions */}
          {plugin.permissions.length > 0 && (
            <div>
              <p className="text-xs font-medium mb-1">权限</p>
              <div className="flex flex-wrap gap-1">
                {plugin.permissions.map(p => (
                  <Badge key={p} variant="secondary" className="text-[10px]">{p}</Badge>
                ))}
              </div>
            </div>
          )}

          {/* Changelog */}
          {Object.keys(plugin.changelog).length > 0 && (
            <div>
              <p className="text-xs font-medium mb-1">更新日志</p>
              <div className="space-y-0.5 text-xs text-muted-foreground">
                {Object.entries(plugin.changelog).map(([ver, desc]) => (
                  <div key={ver} className="flex gap-2">
                    <span className="font-mono text-[10px] shrink-0">v{ver}</span>
                    <span>{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          {onUninstall && !plugin.is_builtin && (
            <Button variant="destructive" size="sm" onClick={onUninstall} className="h-7 text-xs">
              <Trash2 className="h-3 w-3 mr-1" />
              卸载
            </Button>
          )}
        </CardContent>
      )}
    </Card>
  )
}
