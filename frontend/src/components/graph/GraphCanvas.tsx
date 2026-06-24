"use client"

import { useCallback, useEffect, useState, memo, useRef } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  MarkerType,
  Position,
  Handle,
  ConnectionMode,
  type NodeProps,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  forceX,
  forceY,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from "d3-force"

// ── Types ──

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

// ── Style Constants ──

const NODE_STYLES: Record<string, { fill: string; stroke: string; glow: string; text: string }> = {
  document: { fill: "#6366f1", stroke: "#818cf8", glow: "rgba(99,102,241,0.3)", text: "#eef2ff" },
  entity:   { fill: "#10b981", stroke: "#34d399", glow: "rgba(16,185,129,0.25)", text: "#ecfdf5" },
  concept:  { fill: "#f59e0b", stroke: "#fbbf24", glow: "rgba(245,158,11,0.25)", text: "#fffbeb" },
}

const EDGE_STYLES: Record<string, { color: string; label: string }> = {
  contains_entity: { color: "#22c55e", label: "包含" },
  references:      { color: "#6366f1", label: "引用" },
  related_to:      { color: "#a855f7", label: "关联" },
  depends_on:      { color: "#ef4444", label: "依赖" },
  similar_topic:   { color: "#f59e0b", label: "相似" },
}

// ── Custom Node Component ──

const KnowledgeNode = memo(function KnowledgeNode({ data: nodeData }: NodeProps) {
  const nodeType = nodeData.nodeType as string
  const label = nodeData.label as string
  const degree = nodeData.degree as number
  const style = NODE_STYLES[nodeType] || NODE_STYLES.entity

  // Size based on connection count (degree)
  const baseRadius = nodeType === "document" ? 28 : nodeType === "concept" ? 24 : 20
  const radius = baseRadius + Math.min(degree * 3, 18)
  const diameter = radius * 2

  return (
    <div
      style={{
        width: diameter,
        height: diameter,
        borderRadius: "50%",
        background: `radial-gradient(circle at 35% 35%, ${style.fill}, ${style.stroke})`,
        border: `2px solid ${style.stroke}`,
        boxShadow: `0 0 ${8 + degree * 2}px ${style.glow}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        cursor: "pointer",
        transition: "box-shadow 0.2s, transform 0.2s",
        position: "relative",
      }}
      title={label}
    >
      {/* All-direction handles so ReactFlow picks the closest connection point */}
      <Handle type="target" position={Position.Top} style={{ opacity: 0, position: "absolute" }} />
      <Handle type="target" position={Position.Bottom} style={{ opacity: 0, position: "absolute" }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0, position: "absolute" }} />
      <Handle type="target" position={Position.Right} style={{ opacity: 0, position: "absolute" }} />
      <Handle type="source" position={Position.Top} style={{ opacity: 0, position: "absolute" }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0, position: "absolute" }} />
      <Handle type="source" position={Position.Left} style={{ opacity: 0, position: "absolute" }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0, position: "absolute" }} />
      <span
        style={{
          color: style.text,
          fontSize: radius > 30 ? "11px" : "10px",
          fontWeight: 600,
          textAlign: "center",
          lineHeight: 1.2,
          maxWidth: diameter - 12,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          userSelect: "none",
          pointerEvents: "none",
        }}
      >
        {label.length > 8 ? label.slice(0, 7) + "…" : label}
      </span>
      {/* Full label below node */}
      <span
        style={{
          position: "absolute",
          top: diameter + 4,
          left: "50%",
          transform: "translateX(-50%)",
          color: "#64748b",
          fontSize: "10px",
          fontWeight: 500,
          whiteSpace: "nowrap",
          userSelect: "none",
          pointerEvents: "none",
        }}
      >
        {label}
      </span>
    </div>
  )
})

const nodeTypes = { knowledge: KnowledgeNode }

// ── Force-Directed Layout ──

interface SimNode extends SimulationNodeDatum {
  id: string
  nodeType: string
  degree: number
}

interface SimLink extends SimulationLinkDatum<SimNode> {
  edgeType: string
}

interface LayoutResult {
  positions: Map<string, { x: number; y: number }>
  degrees: Map<string, number>
}

async function computeLayout(data: GraphData): Promise<LayoutResult> {
  if (data.nodes.length === 0) return { positions: new Map(), degrees: new Map() }

  // Calculate node degree (connection count)
  const degreeMap = new Map<string, number>()
  data.nodes.forEach(n => degreeMap.set(String(n.id), 0))
  data.edges.forEach(e => {
    const s = String(e.source_id)
    const t = String(e.target_id)
    degreeMap.set(s, (degreeMap.get(s) || 0) + 1)
    degreeMap.set(t, (degreeMap.get(t) || 0) + 1)
  })

  // Create simulation nodes
  const simNodes: SimNode[] = data.nodes.map(n => ({
    id: String(n.id),
    nodeType: n.node_type,
    degree: degreeMap.get(String(n.id)) || 0,
  }))

  // Create simulation links
  const nodeIds = new Set(simNodes.map(n => n.id))
  const simLinks: SimLink[] = data.edges
    .filter(e => nodeIds.has(String(e.source_id)) && nodeIds.has(String(e.target_id)))
    .map(e => ({
      source: String(e.source_id),
      target: String(e.target_id),
      edgeType: e.edge_type,
    }))

  // Run force simulation
  const simulation = forceSimulation<SimNode>(simNodes)
    .force("link", forceLink<SimNode, SimLink>(simLinks)
      .id(d => d.id)
      .distance(d => {
        if (d.edgeType === "contains_entity") return 80
        if (d.edgeType === "depends_on") return 100
        return 150
      })
      .strength(0.6)
    )
    .force("charge", forceManyBody<SimNode>()
      .strength(d => -(200 + d.degree * 30))
    )
    .force("center", forceCenter(0, 0).strength(0.05))
    .force("collide", forceCollide<SimNode>(d => {
      const base = d.nodeType === "document" ? 38 : d.nodeType === "concept" ? 34 : 30
      return base + Math.min(d.degree * 3, 18) + 20
    }).strength(0.8))
    .force("x", forceX(0).strength(0.02))
    .force("y", forceY(0).strength(0.02))
    .stop()

  // Run simulation asynchronously in batches
  const iterations = Math.min(300, 100 + data.nodes.length * 3)
  const BATCH_SIZE = 50
  for (let i = 0; i < iterations; i += BATCH_SIZE) {
    for (let j = 0; j < BATCH_SIZE && i + j < iterations; j++) simulation.tick()
    await new Promise(r => setTimeout(r, 0))
  }

  // Extract positions
  const positions = new Map<string, { x: number; y: number }>()
  simNodes.forEach(s => {
    positions.set(s.id, { x: s.x ?? 0, y: s.y ?? 0 })
  })

  return { positions, degrees: degreeMap }
}

// ── Main Component ──

export function GraphCanvas({ data, onNodeClick }: GraphCanvasProps) {
  // Layout is computed once per data change, not per filter change
  const [layout, setLayout] = useState<LayoutResult>({ positions: new Map(), degrees: new Map() })
  const [layoutReady, setLayoutReady] = useState(false)
  const originalEdgesRef = useRef<Edge[]>([])

  useEffect(() => {
    let cancelled = false
    setLayoutReady(false)
    computeLayout(data).then(result => {
      if (!cancelled) {
        setLayout(result)
        setLayoutReady(true)
      }
    })
    return () => { cancelled = true }
  }, [data])

  // Build nodes and edges from layout + data
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  useEffect(() => {
    if (!layoutReady) return

    const nodeIds = new Set(data.nodes.map(n => String(n.id)))

    const rfNodes: Node[] = data.nodes.map(n => {
      const pos = layout.positions.get(String(n.id)) || { x: 0, y: 0 }
      const degree = layout.degrees.get(String(n.id)) || 0
      const baseRadius = n.node_type === "document" ? 28 : n.node_type === "concept" ? 24 : 20
      const radius = baseRadius + Math.min(degree * 3, 18)

      return {
        id: String(n.id),
        type: "knowledge",
        position: pos,
        data: {
          label: n.label,
          nodeType: n.node_type,
          description: n.description,
          documentId: n.document_id,
          degree,
        },
        style: { width: radius * 2, height: radius * 2 },
      }
    })

    const rfEdges: Edge[] = data.edges
      .filter(e => nodeIds.has(String(e.source_id)) && nodeIds.has(String(e.target_id)))
      .map(e => {
        const edgeStyle = EDGE_STYLES[e.edge_type] || EDGE_STYLES.related_to
        const strokeWidth = 1 + Math.min(e.weight * 0.3, 1.5)
        return {
          id: String(e.id),
          source: String(e.source_id),
          target: String(e.target_id),
          type: "default", // bezier curves for natural look
          style: {
            stroke: edgeStyle.color,
            strokeWidth,
            opacity: 0.5,
          },
          markerEnd: { type: MarkerType.ArrowClosed, color: edgeStyle.color, width: 15, height: 15 },
        }
      })

    setNodes(rfNodes)
    setEdges(rfEdges)
    originalEdgesRef.current = rfEdges
  }, [layout, layoutReady, data, setNodes, setEdges])

  const onNodeClickHandler = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const id = Number(node.id)
      if (onNodeClick && !isNaN(id)) onNodeClick(id)
    },
    [onNodeClick]
  )

  // Highlight connected edges on node hover — save original styles for proper restoration
  const onNodeMouseEnter = useCallback((_: React.MouseEvent, node: Node) => {
    setEdges(eds => eds.map(e => {
      const orig = originalEdgesRef.current.find(oe => oe.id === e.id)
      const origStrokeWidth = Number(orig?.style?.strokeWidth || 1)
      const origOpacity = orig?.style?.opacity ?? 0.5
      if (e.source === node.id || e.target === node.id) {
        return { ...e, style: { ...e.style, opacity: 1, strokeWidth: origStrokeWidth + 1 } }
      }
      return { ...e, style: { ...e.style, opacity: Math.max(Number(origOpacity) * 0.3, 0.1) } }
    }))
  }, [setEdges])

  const onNodeMouseLeave = useCallback(() => {
    setEdges(eds => eds.map(e => {
      const orig = originalEdgesRef.current.find(oe => oe.id === e.id)
      const origStrokeWidth = Number(orig?.style?.strokeWidth || 1)
      const origOpacity = orig?.style?.opacity ?? 0.5
      return { ...e, style: { ...e.style, opacity: origOpacity, strokeWidth: origStrokeWidth } }
    }))
  }, [setEdges])

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

  if (!layoutReady) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground">
        <p className="text-sm">正在计算布局…</p>
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
        onNodeMouseEnter={onNodeMouseEnter}
        onNodeMouseLeave={onNodeMouseLeave}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.05}
        maxZoom={3}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={30} size={1} color="rgba(148,163,184,0.15)" />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(n) => {
            const type = n.data?.nodeType as string
            return NODE_STYLES[type]?.stroke || "#94a3b8"
          }}
          maskColor="rgba(0,0,0,0.08)"
          pannable
          zoomable
        />
      </ReactFlow>
    </div>
  )
}
