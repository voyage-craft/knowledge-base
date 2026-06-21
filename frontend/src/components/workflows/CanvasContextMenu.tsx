"use client"

import { useEffect, useRef, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { Trash2, Copy, Settings2, RotateCcw, LayoutList, Maximize2, Plus } from "lucide-react"

export interface ContextMenuItem {
  icon?: ReactNode
  label: string
  onClick: () => void
  variant?: "default" | "destructive"
  separator?: boolean
}

export interface ContextMenuState {
  x: number
  y: number
  type: "node" | "edge" | "pane"
  targetId?: string
}

interface CanvasContextMenuProps {
  menu: ContextMenuState | null
  items: ContextMenuItem[]
  onClose: () => void
}

export function CanvasContextMenu({ menu, items, onClose }: CanvasContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 })

  useEffect(() => {
    if (!menu) return

    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as HTMLElement)) {
        onClose()
      }
    }
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }

    // Delay to avoid immediate close from the same right-click
    setTimeout(() => {
      document.addEventListener("click", handleClick)
      document.addEventListener("keydown", handleKey)
    }, 0)

    return () => {
      document.removeEventListener("click", handleClick)
      document.removeEventListener("keydown", handleKey)
    }
  }, [menu, onClose])

  // Clamp position to viewport after render
  useEffect(() => {
    if (!menu || !ref.current) return
    const rect = ref.current.getBoundingClientRect()
    let x = menu.x
    let y = menu.y
    if (x + rect.width > window.innerWidth - 8) {
      x = window.innerWidth - rect.width - 8
    }
    if (y + rect.height > window.innerHeight - 8) {
      y = window.innerHeight - rect.height - 8
    }
    if (x < 8) x = 8
    if (y < 8) y = 8
    setPos({ x, y })
  }, [menu])

  if (!menu) return null

  return createPortal(
    <div
      ref={ref}
      style={{
        position: "fixed",
        left: pos.x,
        top: pos.y,
        zIndex: 9999,
      }}
      className="min-w-[170px] animate-in fade-in-0 zoom-in-95 duration-100"
    >
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl py-1 overflow-hidden">
        {items.map((item, i) => (
          <div key={i}>
            {item.separator && i > 0 && (
              <div className="my-1 border-t border-slate-100 dark:border-slate-800" />
            )}
            <button
              className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left transition-colors ${
                item.variant === "destructive"
                  ? "text-red-500 hover:bg-red-50 dark:hover:bg-red-950"
                  : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              }`}
              onClick={() => { item.onClick(); onClose() }}
            >
              {item.icon && <span className="h-4 w-4 shrink-0">{item.icon}</span>}
              <span>{item.label}</span>
            </button>
          </div>
        ))}
      </div>
    </div>,
    document.body,
  )
}

// ── Helper: build context menu items ──

export function buildNodeMenuItems(
  nodeId: string,
  onDelete: (id: string) => void,
  onDuplicate: (id: string) => void,
  onConfigure?: (id: string) => void,
): ContextMenuItem[] {
  const items: ContextMenuItem[] = []
  if (onConfigure) {
    items.push({
      icon: <Settings2 className="h-4 w-4" />,
      label: "配置节点",
      onClick: () => onConfigure(nodeId),
    })
  }
  items.push({
    icon: <Copy className="h-4 w-4" />,
    label: "复制节点",
    onClick: () => onDuplicate(nodeId),
  })
  items.push({
    icon: <Trash2 className="h-4 w-4" />,
    label: "删除节点",
    onClick: () => onDelete(nodeId),
    variant: "destructive",
    separator: true,
  })
  return items
}

export function buildEdgeMenuItems(
  edgeId: string,
  onDelete: (id: string) => void,
): ContextMenuItem[] {
  return [
    {
      icon: <Trash2 className="h-4 w-4" />,
      label: "删除连接",
      onClick: () => onDelete(edgeId),
      variant: "destructive",
    },
  ]
}

export function buildPaneMenuItems(
  onAutoLayout: () => void,
  onFitView: () => void,
): ContextMenuItem[] {
  return [
    {
      icon: <LayoutList className="h-4 w-4" />,
      label: "自动排列",
      onClick: onAutoLayout,
    },
    {
      icon: <Maximize2 className="h-4 w-4" />,
      label: "适应画布",
      onClick: onFitView,
    },
  ]
}
