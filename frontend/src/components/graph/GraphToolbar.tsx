"use client"

import { Button } from "@/components/ui/button"
import { Sparkles, Search } from "lucide-react"

interface GraphToolbarProps {
  onBuild: () => void
  onFilter: (type: string) => void
  building: boolean
  filter: string
  searchQuery: string
  onSearchChange: (q: string) => void
}

const NODE_TYPES = [
  { value: "", label: "全部" },
  { value: "document", label: "文档" },
  { value: "entity", label: "实体" },
  { value: "concept", label: "概念" },
]

export function GraphToolbar({
  onBuild,
  onFilter,
  building,
  filter,
  searchQuery,
  onSearchChange,
}: GraphToolbarProps) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b bg-background">
      <Button
        size="sm"
        onClick={onBuild}
        disabled={building}
      >
        <Sparkles className={`h-3.5 w-3.5 mr-1.5 ${building ? "animate-pulse" : ""}`} />
        {building ? "构建中..." : "构建图谱"}
      </Button>

      <div className="h-5 w-px bg-border mx-1" />

      {/* Filter chips */}
      <div className="flex gap-1">
        {NODE_TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => onFilter(t.value)}
            className={`px-2.5 py-1 rounded text-xs transition-colors ${
              filter === t.value
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1" />

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <input
          type="text"
          placeholder="搜索节点..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-8 pr-3 py-1.5 text-xs rounded-md border bg-background w-40 focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>
    </div>
  )
}
