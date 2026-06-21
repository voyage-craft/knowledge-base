"use client"

import { useState, useEffect, FormEvent } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { toast } from "sonner"
import { Loader2, Settings } from "lucide-react"
import { apiTry } from "@/lib/api-client"

interface SettingsData {
  app_name: string
}

export function SystemTab() {
  const [settings, setSettings] = useState<SettingsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchSettings()
  }, [])

  async function fetchSettings() {
    const [data, err] = await apiTry<{ settings: Record<string, string> }>("/api/settings/system")
    if (data) {
      setSettings({ app_name: data.settings.app_name || "知识库" })
    } else {
      toast.error(err?.message || "加载配置失败")
    }
    setLoading(false)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!settings) return

    setSaving(true)
    const [, err] = await apiTry("/api/settings/system", {
      method: "PUT",
      body: JSON.stringify({ settings }),
    })
    if (!err) {
      toast.success("配置已保存")
    } else {
      toast.error(err.message || "保存失败")
    }
    setSaving(false)
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">加载配置中...</span>
        </CardContent>
      </Card>
    )
  }

  if (!settings) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          无法加载系统配置，请确认你拥有管理员权限。
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>系统配置</CardTitle>
        <CardDescription>配置应用基础设置。AI 模型配置请使用「API 路由」标签页。</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6 max-w-lg">
          {/* App name */}
          <div className="space-y-2">
            <label className="text-sm font-medium">应用名称</label>
            <Input
              value={settings.app_name}
              onChange={e => setSettings({ ...settings, app_name: e.target.value })}
              placeholder="知识库"
            />
          </div>

          {/* Info card */}
          <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 text-sm text-blue-700 dark:text-blue-300">
            <Settings className="h-4 w-4 mt-0.5 shrink-0" />
            <div>
              <p className="font-medium">AI 模型配置已迁移</p>
              <p className="text-xs mt-0.5 opacity-80">
                请使用「API 路由」标签页配置 AI 端点。支持多端点、智能调度、故障转移和健康监控。
              </p>
            </div>
          </div>

          {/* Save button */}
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={saving}>
              {saving ? "保存中..." : "保存配置"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
