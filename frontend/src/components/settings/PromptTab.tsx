"use client"

import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { toast } from "sonner"
import { Loader2, RotateCcw, Save, ChevronDown, ChevronUp } from "lucide-react"
import { apiTry } from "@/lib/api-client"

interface Prompt {
  key: string
  label: string
  category: string
  description: string
  default: string
  current: string
  is_modified: boolean
}

const CATEGORY_LABELS: Record<string, string> = {
  chat: "对话",
  edit: "编辑操作",
  pipeline: "AI 流水线",
  rag: "RAG 检索增强",
  workflow: "工作流",
}

export function PromptTab() {
  const [prompts, setPrompts] = useState<Prompt[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState<Record<string, string>>({})
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const fetchPrompts = useCallback(async () => {
    const [data, err] = await apiTry<{ prompts: Prompt[] }>("/api/settings/prompts")
    if (data) {
      setPrompts(data.prompts)
      setEditing({})
    } else {
      toast.error(err?.message || "加载提示词失败")
    }
    setLoading(false)
  }, [])

  useEffect(() => { fetchPrompts() }, [fetchPrompts])

  function startEdit(key: string, current: string) {
    setEditing(prev => ({ ...prev, [key]: current }))
    setExpanded(prev => ({ ...prev, [key]: true }))
  }

  function cancelEdit(key: string) {
    setEditing(prev => {
      const next = { ...prev }
      delete next[key]
      return next
    })
  }

  async function saveOne(key: string) {
    const value = editing[key]
    if (value === undefined) return
    setSaving(true)
    const [data, err] = await apiTry<{ message: string }>("/api/settings/prompts", {
      method: "PUT",
      body: JSON.stringify({ updates: { [key]: value } }),
    })
    if (data) {
      toast.success("提示词已更新")
      fetchPrompts()
    } else {
      toast.error(err?.message || "保存失败")
    }
    setSaving(false)
  }

  async function resetOne(key: string) {
    const [, err] = await apiTry<{ message: string }>("/api/settings/prompts", {
      method: "POST",
      body: JSON.stringify({ keys: [key] }),
    })
    if (!err) {
      toast.success("已重置为默认")
      fetchPrompts()
    } else {
      toast.error(err?.message || "重置失败")
    }
  }

  function toggleExpand(key: string) {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }))
  }

  // Group prompts by category
  const grouped = prompts.reduce<Record<string, Prompt[]>>((acc, p) => {
    if (!acc[p.category]) acc[p.category] = []
    acc[p.category].push(p)
    return acc
  }, {})

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">加载提示词中...</span>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>提示词管理</CardTitle>
          <CardDescription>
            自定义所有 AI 功能的系统提示词。修改后立即生效，可随时重置为默认值。
          </CardDescription>
        </CardHeader>
      </Card>

      {Object.entries(grouped).map(([category, items]) => (
        <Card key={category}>
          <CardHeader>
            <CardTitle className="text-base">
              {CATEGORY_LABELS[category] || category}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {items.map(prompt => {
              const isEditing = prompt.key in editing
              const isExpanded = expanded[prompt.key]
              const displayText = isEditing
                ? editing[prompt.key]
                : prompt.current

              return (
                <div key={prompt.key} className="border rounded-lg overflow-hidden">
                  {/* Header row */}
                  <div className="flex items-center gap-2 px-4 py-2.5 bg-muted/30">
                    <span className="text-sm font-medium flex-1">{prompt.label}</span>
                    {prompt.is_modified && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-300 rounded-full">
                        已修改
                      </span>
                    )}
                    {prompt.is_modified && !isEditing && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs h-7 gap-1"
                        onClick={() => resetOne(prompt.key)}
                      >
                        <RotateCcw className="h-3 w-3" /> 重置
                      </Button>
                    )}
                    <button
                      onClick={() => toggleExpand(prompt.key)}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                  </div>

                  {/* Expanded content */}
                  {isExpanded && (
                    <div className="px-4 py-3 space-y-2">
                      <p className="text-xs text-muted-foreground">{prompt.description}</p>

                      <textarea
                        value={displayText}
                        readOnly={!isEditing}
                        onChange={e => {
                          if (isEditing) {
                            setEditing(prev => ({ ...prev, [prompt.key]: e.target.value }))
                          }
                        }}
                        className={`w-full min-h-[120px] rounded-md border px-3 py-2 text-sm font-mono resize-y ${
                          isEditing
                            ? "bg-background border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary"
                            : "bg-muted/20 border-transparent"
                        }`}
                        onFocus={() => {
                          if (!isEditing) startEdit(prompt.key, prompt.current)
                        }}
                      />

                      {isEditing && (
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            onClick={() => saveOne(prompt.key)}
                            disabled={saving}
                          >
                            {saving ? (
                              <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                            ) : (
                              <Save className="h-3.5 w-3.5 mr-1" />
                            )}
                            保存
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => cancelEdit(prompt.key)}
                          >
                            取消
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
