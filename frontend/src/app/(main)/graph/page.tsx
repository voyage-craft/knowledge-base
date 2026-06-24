"use client"

import { useState, useEffect, useCallback, useRef, useMemo } from "react"
import dynamic from "next/dynamic"
import { apiTry } from "@/lib/api-client"
import { toast } from "sonner"
import { NodeDetail } from "@/components/graph/NodeDetail"
import { GraphToolbar } from "@/components/graph/GraphToolbar"
import { ReactFlowProvider } from "@xyflow/react"
import { Network, Loader2, Sparkles, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

// Lazy-load GraphCanvas (~200KB+ with @xyflow/react)
const GraphCanvas = dynamic(
  () => import("@/components/graph/GraphCanvas").then(m => ({ default: m.GraphCanvas })),
  { ssr: false, loading: () => <div className="flex items-center justify-center h-full"><Loader2 className="h-6 w-6 animate-spin" /></div> }
)

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

interface BuildStatus {
  status: string
  current: number
  total: number
  phase?: string
  failed_count?: number
  nodes_created?: number
  edges_created?: number
  error?: string
}

export default function GraphPage() {
  const [data, setData] = useState<GraphData>({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(true)
  const [building, setBuilding] = useState(false)
  const [buildStatus, setBuildStatus] = useState<BuildStatus | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null)
  const [filter, setFilter] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [isRefreshing, setIsRefreshing] = useState(false)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollFailCountRef = useRef(0)
  const initialCheckRef = useRef(false)

  const fetchGraph = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    else setIsRefreshing(true)
    const [res] = await apiTry<GraphData>(`/api/graph`)
    if (res) setData(res)
    if (!silent) setLoading(false)
    else setIsRefreshing(false)
  }, [])

  useEffect(() => {
    fetchGraph()
  }, [fetchGraph])

  // Check build status on mount — resume polling if build was in progress
  useEffect(() => {
    if (initialCheckRef.current) return
    initialCheckRef.current = true

    ;(async () => {
      const [status] = await apiTry<BuildStatus>(`/api/graph/build/status`)
      if (status && status.status === "building") {
        setBuilding(true)
        setBuildStatus(status)
        startPolling()
      }
    })()
  }, [])

  // Client-side filtering — filter both nodes AND edges
  const filteredData: GraphData = useMemo(() => {
    const filteredNodes = data.nodes.filter((n) => {
      if (filter && n.node_type !== filter) return false
      if (searchQuery && !n.label.toLowerCase().includes(searchQuery.toLowerCase())) return false
      return true
    })
    const visibleNodeIds = new Set(filteredNodes.map(n => String(n.id)))
    const filteredEdges = data.edges.filter(e =>
      visibleNodeIds.has(String(e.source_id)) && visibleNodeIds.has(String(e.target_id))
    )
    return { nodes: filteredNodes, edges: filteredEdges }
  }, [data, filter, searchQuery])

  const stopPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = null
    pollFailCountRef.current = 0
  }, [])

  // Cleanup timers on unmount
  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  const startPolling = useCallback(() => {
    stopPolling()
    pollFailCountRef.current = 0

    pollRef.current = setInterval(async () => {
      const [status, err] = await apiTry<BuildStatus>(`/api/graph/build/status?_t=${Date.now()}`)

      if (err || !status) {
        pollFailCountRef.current += 1
        if (pollFailCountRef.current >= 5) {
          stopPolling()
          setBuilding(false)
          setBuildStatus(null)
          toast.error("无法获取构建状态，请检查服务是否正常运行")
          fetchGraph()
        }
        return
      }

      // Reset fail count on success
      pollFailCountRef.current = 0

      if (status.status === "complete") {
        stopPolling()
        setBuilding(false)
        setBuildStatus(null)
        // Fetch fresh graph data (silent = true to avoid loading flash)
        await fetchGraph(true)
        const failed = status.failed_count || 0
        const nodes = status.nodes_created || 0
        const edges = status.edges_created || 0
        if (failed > 0) {
          toast.success(`图谱构建完成：${nodes} 节点，${edges} 关系（${failed} 篇文档提取失败）`)
        } else {
          toast.success(`图谱构建完成：${nodes} 节点，${edges} 关系`)
        }
      } else if (status.status === "error") {
        stopPolling()
        setBuilding(false)
        setBuildStatus(null)
        fetchGraph(true)
        toast.error(`图谱构建失败：${status.error || "未知错误"}`)
      } else if (status.status === "building") {
        setBuildStatus(status)
      }
    }, 2000)
  }, [stopPolling, fetchGraph])

  const handleBuild = useCallback(async () => {
    setBuilding(true)
    setBuildStatus({ status: "building", current: 0, total: 0 })
    const [res, err] = await apiTry<{ message: string }>("/api/graph/build", { method: "POST" })
    if (res) {
      toast.info(res.message || "图谱构建已启动")
      startPolling()
    } else {
      setBuilding(false)
      setBuildStatus(null)
      toast.error("启动图谱构建失败")
    }
  }, [startPolling])

  const handleDeleteNode = useCallback(async (nodeId: number) => {
    const [, err] = await apiTry(`/api/graph/node/${nodeId}`, { method: "DELETE" })
    if (!err) {
      setData((prev) => ({
        nodes: prev.nodes.filter((n) => n.id !== nodeId),
        edges: prev.edges.filter((e) => e.source_id !== nodeId && e.target_id !== nodeId),
      }))
      toast.success("节点已删除")
    } else {
      toast.error("删除节点失败")
    }
  }, [])

  const handleNodeClick = useCallback((id: number) => setSelectedNodeId(id), [])
  const handleNodeClose = useCallback(() => setSelectedNodeId(null), [])

  // Build progress percentage
  const progressPercent = buildStatus && buildStatus.total > 0
    ? Math.min(Math.round((buildStatus.current / buildStatus.total) * 100), 100)
    : 0
  const progressText = buildStatus
    ? buildStatus.phase === "extracting"
      ? `提取实体 ${buildStatus.current}/${buildStatus.total}`
      : buildStatus.phase === "saving"
      ? "保存图谱数据..."
      : buildStatus.total > 0
      ? `分析文档 ${buildStatus.current}/${buildStatus.total}`
      : "准备中..."
    : ""

  return (
    <>
      <header className="border-b px-6 py-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Network className="h-5 w-5 text-blue-600" />
            <h1 className="text-lg font-semibold">知识图谱</h1>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {filteredData.nodes.length} 个节点 · {filteredData.edges.length} 条关系
            {filteredData.nodes.length !== data.nodes.length && ` (共 ${data.nodes.length} 节点)`}
          </p>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => fetchGraph(true)}
          disabled={isRefreshing || loading}
          title="刷新图谱数据"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
        </Button>
      </header>

      <GraphToolbar
        onBuild={handleBuild}
        onFilter={setFilter}
        building={building}
        filter={filter}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      {/* Build progress indicator with progress bar */}
      {building && (
        <div className="px-6 py-2.5 bg-blue-50 dark:bg-blue-950/30 border-b">
          <div className="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300 mb-1.5">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>正在构建知识图谱 — {progressText}</span>
          </div>
          {buildStatus && buildStatus.total > 0 && (
            <div className="w-full bg-blue-200 dark:bg-blue-900 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-blue-600 h-full rounded-full transition-all duration-500 ease-out"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          )}
        </div>
      )}

      <div className="flex-1 relative" style={{ minHeight: "calc(100vh - 140px)" }}>
        {loading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="h-6 w-6 animate-spin" />
              <span className="text-sm">加载图谱数据...</span>
            </div>
          </div>
        ) : filteredData.nodes.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center space-y-3">
              {data.nodes.length === 0 ? (
                <>
                  <Sparkles className="h-10 w-10 mx-auto text-muted-foreground/50" />
                  <p className="text-lg">暂无知识图谱数据</p>
                  <p className="text-sm">点击「构建图谱」开始 AI 分析文档</p>
                </>
              ) : (
                <>
                  <p className="text-sm">没有匹配的节点</p>
                  <Button size="sm" variant="outline" onClick={() => { setFilter(""); setSearchQuery("") }}>
                    清除筛选
                  </Button>
                </>
              )}
            </div>
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
        allEdges={data.edges}
      />
    </>
  )
}
