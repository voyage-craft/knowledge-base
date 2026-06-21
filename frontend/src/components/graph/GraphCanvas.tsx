"use client"

import { useCallback, useMemo, useEffect, useState } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
  MarkerType,
  Position,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"

interface GraphData {
  nodes: Array<{
    id: number
    node_type: string
    label: string
    description?: string | null
    document_id?: number | null
    metadata_json?: Record<string, unknown> | null
  }>
  edges: Array<{
    id: number
    source_id: number
    target_id: number
    edge_type: string
    weight: number
    description?: string | null
  }>
}

interface GraphCanvasProps {
  data: GraphData
  onNodeClick?: (nodeId: number) => void
}

// Color scheme by node type
const NODE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  document: { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
  entity: { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
  concept: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },
}

const EDGE_COLORS: Record<string, string> = {
  contains_entity: "#22c55e",
  references: "#3b82f6",
  related_to: "#a855f7",
  depends_on: "#ef4444",
  similar_topic: "#f59e0b",
}

// Simple dagre-like layout: arrange nodes in a grid with deterministic jitter
function layoutNodes(nodes: Node[]): Node[] {
  const cols = Math.ceil(Math.sqrt(nodes.length))
  return nodes.map((n, i) => ({
    ...n,
    position: {
      x: (i % cols) * 220 + ((i * 37 + 13) % 40 - 20),
      y: Math.floor(i / cols) * 160 + ((i * 53 + 7) % 40 - 20),
    },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  }))
}

export function GraphCanvas({ data, onNodeClick }: GraphCanvasProps) {
  // Convert backend data to ReactFlow nodes/edges
  const initialNodes = useMemo<Node[]>(() => {
    const nodes = data.nodes.map((n) => {
      const colors = NODE_COLORS[n.node_type] || NODE_COLORS.entity
      const meta = n.metadata_json as Record<string, string> | null
      return {
        id: String(n.id),
        type: "default",
        data: {
          label: n.label,
          nodeType: n.node_type,
          description: n.description,
          documentId: n.document_id,
          entity_type: meta?.entity_type,
        },
        style: {
          background: colors.bg,
          border: `2px solid ${colors.border}`,
          borderRadius: n.node_type === "document" ? "8px" : n.node_type === "concept" ? "0" : "50%",
          padding: "8px 12px",
          fontSize: "12px",
          color: colors.text,
          fontWeight: 500,
          minWidth: n.node_type === "document" ? "120px" : "80px",
          textAlign: "center" as const,
        },
        position: { x: 0, y: 0 },
      }
    })
    return layoutNodes(nodes)
  }, [data.nodes])

  const initialEdges = useMemo<Edge[]>(() => {
    const nodeIds = new Set(data.nodes.map((n) => String(n.id)))
    return data.edges
      .filter((e) => nodeIds.has(String(e.source_id)) && nodeIds.has(String(e.target_id)))
      .map((e) => ({
        id: String(e.id),
        source: String(e.source_id),
        target: String(e.target_id),
        type: "smoothstep",
        label: e.edge_type.replace("_", " "),
        labelStyle: { fontSize: 10, fill: "#666" },
        style: { stroke: EDGE_COLORS[e.edge_type] || "#999", strokeWidth: 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLORS[e.edge_type] || "#999" },
        animated: e.edge_type === "contains_entity",
      }))
  }, [data.edges])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  useEffect(() => {
    setNodes(initialNodes)
    setEdges(initialEdges)
  }, [initialNodes, initialEdges, setNodes, setEdges])

  const onNodeClickHandler = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const id = Number(node.id)
      if (onNodeClick && !isNaN(id)) onNodeClick(id)
    },
    [onNodeClick]
  )

  if (data.nodes.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground">
        <div className="text-center space-y-2">
          <p className="text-lg">暂无知识图谱数据</p>
          <p className="text-sm">请先构建图谱或添加文档</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClickHandler}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
      >
        <Background gap={20} size={1} />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(n) => {
            const type = n.data?.nodeType as string
            const colors = NODE_COLORS[type] || NODE_COLORS.entity
            return colors.border
          }}
          maskColor="rgba(0,0,0,0.1)"
        />
      </ReactFlow>
    </div>
  )
}
