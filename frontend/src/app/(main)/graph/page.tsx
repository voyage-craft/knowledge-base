"use client"

import { useState, useEffect, useCallback, useRef, useMemo } from "react"
import { apiTry } from "@/lib/api-client"
import { GraphCanvas } from "@/components/graph/GraphCanvas"
import { NodeDetail } from "@/components/graph/NodeDetail"
import { GraphToolbar } from "@/components/graph/GraphToolbar"
import { ReactFlowProvider } from "@xyflow/react"
import { Network } from "lucide-react"

interface GraphNode {
  id: number
  node_type: string
  label: string
  description?: string | null
  document_id?: number | null
  metadata_json?: Record<string, unknown> | null
}

interface GraphEdge {
  id: number
  source_id: number
  target_id: number
  edge_type: string
  weight: number
  description?: string | null
}

interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export default function GraphPage() {
  const [data, setData] = useState<GraphData>({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(true)
  const [building, setBuilding] = useState(false)
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null)
  const [filter, setFilter] = useState("")
  const [searchQuery, setSearchQuery] = useState("")

  const fetchGraph = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (filter) {
      // We filter on client side since backend only supports document_id filter
    }
    const [res, err] = await apiTry<GraphData>(`/api/graph?${params}`)
    if (res) setData(res)
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchGraph()
  }, [fetchGraph])

  // Client-side filtering
  const filteredData: GraphData = useMemo(() => ({
    nodes: data.nodes.filter((n) => {
      if (filter && n.node_type !== filter) return false
      if (searchQuery && !n.label.toLowerCase().includes(searchQuery.toLowerCase())) return false
      return true
    }),
    edges: data.edges,
  }), [data, filter, searchQuery])

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  const handleBuild = useCallback(async () => {
    setBuilding(true)
    const [res] = await apiTry<{ message: string }>("/api/graph/build", { method: "POST" })
    if (res) {
      // Clear any previous timers
      if (pollRef.current) clearInterval(pollRef.current)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)

      // Poll for completion every 3s
      pollRef.current = setInterval(async () => {
        const [graph] = await apiTry<GraphData>("/api/graph")
        if (graph && graph.nodes.length > 0) {
          setData(graph)
          setBuilding(false)
          if (pollRef.current) clearInterval(pollRef.current)
          if (timeoutRef.current) clearTimeout(timeoutRef.current)
          pollRef.current = null
          timeoutRef.current = null
        }
      }, 3000)

      // Timeout after 5 minutes
      timeoutRef.current = setTimeout(() => {
        setBuilding(false)
        if (pollRef.current) clearInterval(pollRef.current)
        pollRef.current = null
        timeoutRef.current = null
        fetchGraph()
      }, 300000)
    } else {
      setBuilding(false)
    }
  }, [fetchGraph])

  const handleDeleteNode = useCallback(async (nodeId: number) => {
    const [_, err] = await apiTry(`/api/graph/node/${nodeId}`, { method: "DELETE" })
    if (!err) {
      setData((prev) => ({
        nodes: prev.nodes.filter((n) => n.id !== nodeId),
        edges: prev.edges.filter((e) => e.source_id !== nodeId && e.target_id !== nodeId),
      }))
    }
  }, [])

  const handleNodeClick = useCallback((id: number) => setSelectedNodeId(id), [])
  const handleNodeClose = useCallback(() => setSelectedNodeId(null), [])

  return (
    <>
      <header className="border-b px-6 py-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Network className="h-5 w-5 text-blue-600" />
            <h1 className="text-lg font-semibold">知识图谱</h1>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {data.nodes.length} 个节点 · {data.edges.length} 条关系
          </p>
        </div>
      </header>

      <GraphToolbar
        onBuild={handleBuild}
        onFilter={setFilter}
        building={building}
        filter={filter}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      <div className="flex-1 relative" style={{ minHeight: "calc(100vh - 140px)" }}>
        {loading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            加载中...
          </div>
        ) : (
          <ReactFlowProvider>
            <GraphCanvas
              data={filteredData}
              onNodeClick={handleNodeClick}
            />
          </ReactFlowProvider>
        )}
      </div>

      <NodeDetail
        nodeId={selectedNodeId}
        onClose={handleNodeClose}
        onDelete={handleDeleteNode}
        allNodes={data.nodes}
      />
    </>
  )
}
