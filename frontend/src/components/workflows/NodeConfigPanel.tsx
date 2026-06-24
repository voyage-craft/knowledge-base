"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { X } from "lucide-react"
import { getModuleByType, type WorkflowModule } from "@/lib/workflow-modules"
import type { Node } from "@xyflow/react"

interface NodeConfigPanelProps {
  node: Node | null
  onUpdate: (nodeId: string, data: Record<string, unknown>) => void
  onClose: () => void
}

export function NodeConfigPanel({ node, onUpdate, onClose }: NodeConfigPanelProps) {
  const [config, setConfig] = useState<Record<string, string>>({})
  const [showAdvanced, setShowAdvanced] = useState(false)

  useEffect(() => {
    if (node) {
      setConfig((node.data as any)?.config || {})
    }
  }, [node])

  if (!node) return null

  const mod = getModuleByType((node.data as any)?.moduleType || "")
  if (!mod?.configurable || !mod.configFields?.length) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">{(node.data as any)?.label}</h3>
          <Button variant="ghost" size="sm" onClick={onClose} className="h-6 w-6 p-0">
            <X className="h-3 w-3" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          {mod?.description || "此模块无需配置"}
        </p>
      </div>
    )
  }

  function handleChange(key: string, value: string) {
    const newConfig = { ...config, [key]: value }
    setConfig(newConfig)
    onUpdate(node!.id, {
      ...node!.data,
      config: newConfig,
    })
  }

  const basicFields = mod.configFields.filter(f => !f.advanced)
  const advancedFields = mod.configFields.filter(f => f.advanced)
  const hasAdvancedFields = advancedFields.length > 0

  function renderField(field: { key: string; label: string; type: string; options?: { value: string; label: string }[]; placeholder?: string; default?: string }) {
    return (
      <div key={field.key} className="space-y-1.5">
        <label className="text-xs font-medium">{field.label}</label>
        {field.type === "select" ? (
          <select
            value={config[field.key] || field.default || field.options?.[0]?.value || ""}
            onChange={e => handleChange(field.key, e.target.value)}
            className="flex h-8 w-full rounded-md border border-input bg-background px-2 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {field.options?.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        ) : field.type === "textarea" ? (
          <textarea
            value={config[field.key] || ""}
            onChange={e => handleChange(field.key, e.target.value)}
            placeholder={field.placeholder}
            rows={4}
            className="flex w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
          />
        ) : (
          <Input
            value={config[field.key] || ""}
            onChange={e => handleChange(field.key, e.target.value)}
            placeholder={field.placeholder}
            className="h-8 text-xs"
          />
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium">{mod.label}</h3>
          <p className="text-[11px] text-muted-foreground">{mod.description}</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} className="h-6 w-6 p-0">
          <X className="h-3 w-3" />
        </Button>
      </div>

      <div className="space-y-3">
        {basicFields.map(renderField)}
      </div>

      {hasAdvancedFields && (
        <div>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            高级选项 {showAdvanced ? "\u25B2" : "\u25BC"}
          </button>
          {showAdvanced && (
            <div className="space-y-3 mt-3">
              {advancedFields.map(renderField)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
