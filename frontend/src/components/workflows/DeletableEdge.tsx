"use client"

import { memo, useMemo, useState } from "react"
import { type EdgeProps, getBezierPath, EdgeLabelRenderer } from "@xyflow/react"
import { X } from "lucide-react"

export const DeletableEdge = memo(function DeletableEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  selected,
  label,
}: EdgeProps) {
  const [hovered, setHovered] = useState(false)

  const [edgePath, labelX, labelY] = useMemo(() => getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  }), [sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition])

  const onDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    // Dispatch custom event for the parent to handle deletion
    // (so we can show confirmation if desired)
    window.dispatchEvent(new CustomEvent("edge-delete-request", { detail: { edgeId: id } }))
  }

  const showDeleteBtn = selected || hovered

  return (
    <>
      {/* Invisible wider path for easier clicking/selecting */}
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={20}
        className="cursor-pointer"
      />
      {/* Visible path with glow effect when selected */}
      {selected && (
        <path
          d={edgePath}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={8}
          opacity={0.15}
          className="pointer-events-none"
        />
      )}
      <path
        id={id}
        d={edgePath}
        fill="none"
        stroke={selected ? "#3b82f6" : hovered ? "#64748b" : "#94a3b8"}
        strokeWidth={selected ? 3 : hovered ? 2.5 : 2}
        markerEnd={markerEnd}
        style={style}
        className="transition-[stroke,stroke-width] duration-200 pointer-events-none"
      />
      {/* Animated flow dots - only render when selected to reduce GPU load */}
      {selected && (
        <circle r={3.5} fill="#3b82f6" opacity={1}>
          <animateMotion dur="2s" repeatCount="indefinite" path={edgePath} />
        </circle>
      )}
      {/* Delete button + label */}
      <EdgeLabelRenderer>
        <div
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: "all",
            zIndex: 10,
          }}
          className="flex items-center gap-1"
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          {label && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 whitespace-nowrap">
              {String(label)}
            </span>
          )}
          <button
            onClick={onDelete}
            className={`w-5 h-5 rounded-full flex items-center justify-center transition-all duration-200 ${
              showDeleteBtn
                ? selected
                  ? "bg-red-500 text-white shadow-md scale-100"
                  : "bg-white dark:bg-slate-800 text-slate-500 hover:text-red-500 border border-slate-300 dark:border-slate-600 shadow-sm scale-100"
                : "bg-white dark:bg-slate-800 text-slate-400 border border-slate-200 dark:border-slate-600 shadow-sm scale-75 pointer-events-none"
            }`}
            style={{
              opacity: showDeleteBtn ? 1 : 0,
              transition: "opacity 200ms, transform 200ms, background-color 200ms",
            }}
            title="删除连接"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      </EdgeLabelRenderer>
    </>
  )
})
