"use client"

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useReactFlow,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
  type OnConnect,
  type OnNodesChange,
  type OnEdgesChange,
  useNodesState,
  useEdgesState,
  addEdge,
  Handle,
  Position,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import {
  FolderOpen, Sparkles, Expand, Minimize2, Languages, Wrench,
  FileText, Key, Tags, ClipboardCheck, MessageSquare, Save,
  Trash2, Settings2, Search, LayoutList, GripVertical,
  Plus, ArrowLeft, PanelRightClose, PanelRightOpen,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { NodeConfigPanel } from "@/components/workflows/NodeConfigPanel"
import { DeletableEdge } from "@/components/workflows/DeletableEdge"
import {
  CanvasContextMenu,
  type ContextMenuState,
  type ContextMenuItem,
  buildNodeMenuItems,
  buildEdgeMenuItems,
  buildPaneMenuItems,
} from "@/components/workflows/CanvasContextMenu"
import { WORKFLOW_MODULES, getModuleByType, MODULE_CATEGORIES, type WorkflowModule } from "@/lib/workflow-modules"

// ── Icon map ──
const ICONS: Record<string, typeof Sparkles> = {
  FolderOpen, Sparkles, Expand, Minimize2, Languages, Wrench,
  FileText, Key, Tags, ClipboardCheck, MessageSquare, Save,
}

// ── Memoized MiniMap node color function (stable reference) ──
const miniMapNodeColor = (n: Node) => {
  const color = (n.data as Record<string, unknown>)?.color as string
  if (color?.includes("emerald") || color?.includes("green")) return "#10b981"
  if (color?.includes("blue") || color?.includes("sky")) return "#3b82f6"
  if (color?.includes("indigo") || color?.includes("violet")) return "#6366f1"
  if (color?.includes("purple")) return "#a855f7"
  if (color?.includes("pink") || color?.includes("rose")) return "#ec4899"
  if (color?.includes("amber") || color?.includes("orange")) return "#f59e0b"
  if (color?.includes("teal") || color?.includes("cyan")) return "#14b8a6"
  return "#94a3b8"
}

// ── Custom workflow node (memoized to avoid re-render on every drag frame) ──
const WorkflowNode = memo(function WorkflowNode({ data, selected }: { data: { label: string; moduleType: string; color: string }; selected?: boolean }) {
  const mod = getModuleByType(data.moduleType)
  const Icon = mod?.icon ? (ICONS[mod.icon] || Sparkles) : Sparkles

  return (
    <div className={`px-4 py-3 rounded-xl border-2 shadow-md bg-white dark:bg-slate-900 min-w-[170px] transition-[border-color,box-shadow] duration-200 ${
      selected
        ? "border-blue-500 ring-2 ring-blue-200 dark:ring-blue-800 shadow-blue-100 dark:shadow-blue-900"
        : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600"
    }`}>
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-blue-400 !border-2 !border-white dark:!border-slate-900 hover:!scale-125 hover:!bg-blue-500 transition-transform"
      />
      <div className="flex items-center gap-2.5">
        <div className={`p-1.5 rounded-lg ${data.color}`}>
          <Icon className="h-4 w-4 text-white" />
        </div>
        <div>
          <p className="text-sm font-medium leading-tight">{data.label}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">{mod?.description}</p>
        </div>
      </div>
      {mod?.configurable && (
        <div className="mt-1.5 flex items-center gap-1 text-[10px] text-blue-500 dark:text-blue-400">
          <Settings2 className="h-3 w-3" />
          <span>可配置</span>
        </div>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-blue-400 !border-2 !border-white dark:!border-slate-900 hover:!scale-125 hover:!bg-blue-500 transition-transform"
      />
    </div>
  )
})

const nodeTypes: NodeTypes = { workflow: WorkflowNode }
const edgeTypes: EdgeTypes = { deletable: DeletableEdge }

// ── Props ──
interface WorkflowEditorProps {
  initialNodes?: Node[]
  initialEdges?: Edge[]
  onGraphChange?: (nodes: Node[], edges: Edge[]) => void
}

let _nodeId = 100
function nextId() { return `node_${++_nodeId}` }

// ── Inner editor (needs ReactFlow context) ──
function EditorInner({
  initialNodes,
  initialEdges,
  onGraphChange,
}: WorkflowEditorProps) {
  const { screenToFlowPosition, fitView, setCenter } = useReactFlow()
  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes || [])
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges || [])
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [moduleSearch, setModuleSearch] = useState("")
  const [isDragOver, setIsDragOver] = useState(false)
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [rightPanelOpen, setRightPanelOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<{ type: "node" | "edge"; id: string } | null>(null)
  const confirmDeleteRef = useRef(confirmDelete)
  confirmDeleteRef.current = confirmDelete
  const graphRef = useRef({ nodes, edges })
  // Keep a ref to current nodes/edges for use in callbacks without creating dependencies
  const nodesRef = useRef(nodes)
  const edgesRef = useRef(edges)
  nodesRef.current = nodes
  edgesRef.current = edges
  // Ref for delete edge handler to avoid circular dependency with useEffect
  const handleDeleteEdgeRef = useRef<((edgeId: string) => void) | null>(null)

  // Auto-open right panel when a node is selected
  useEffect(() => {
    if (selectedNodeId) setRightPanelOpen(true)
  }, [selectedNodeId])

  // Sync when parent provides new initial data
  useEffect(() => {
    if (initialNodes?.length !== undefined) setNodes(initialNodes)
  }, [initialNodes, setNodes])

  useEffect(() => {
    if (initialEdges?.length !== undefined) setEdges(initialEdges)
  }, [initialEdges, setEdges])

  // Propagate graph changes to parent (use ref to avoid re-creating callback dependency)
  useEffect(() => {
    graphRef.current = { nodes, edges }
    onGraphChange?.(nodes, edges)
  }, [nodes, edges, onGraphChange])

  // Listen for edge delete requests from DeletableEdge
  // Uses ref to avoid circular dependency — handleDeleteEdge is defined below
  useEffect(() => {
    const handler = (e: Event) => {
      const { edgeId } = (e as CustomEvent).detail
      handleDeleteEdgeRef.current?.(edgeId)
    }
    window.addEventListener("edge-delete-request", handler)
    return () => window.removeEventListener("edge-delete-request", handler)
  }, [])

  // ── Connect handler: create deletable edges ──
  const handleConnect: OnConnect = useCallback((params) => {
    setEdges((eds) => addEdge({
      ...params,
      type: "deletable",
      animated: true,
      style: { stroke: "#94a3b8", strokeWidth: 2 },
    }, eds))
  }, [setEdges])

  // ── Node change handler with selection tracking ──
  const handleNodesChange: OnNodesChange = useCallback((changes) => {
    onNodesChange(changes)
    for (const change of changes) {
      if (change.type === "select") {
        if (change.selected) {
          setSelectedNodeId(change.id)
        } else {
          setSelectedNodeId(prev => prev === change.id ? null : prev)
        }
      }
    }
  }, [onNodesChange])

  const handleEdgesChange: OnEdgesChange = useCallback((changes) => {
    onEdgesChange(changes)
  }, [onEdgesChange])

  // ── Add module node (with optional position for drag-drop) ──
  const addModuleNode = useCallback((mod: WorkflowModule, position?: { x: number; y: number }) => {
    const id = nextId()
    const currentNodes = nodesRef.current
    const pos = position || { x: 250 + Math.random() * 100, y: 80 + currentNodes.length * 130 }
    const newNode: Node = {
      id,
      type: "workflow",
      position: pos,
      data: { label: mod.label, moduleType: mod.type, color: mod.color, config: {} },
    }
    setNodes((nds) => [...nds, newNode])

    // Auto-connect to nearest source node if dropped on canvas
    if (position && currentNodes.length > 0) {
      const nearest = currentNodes.reduce<{ node: Node; dist: number } | null>((best, n) => {
        const dx = n.position.x - pos.x
        const dy = n.position.y - pos.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (!best || (dist < best.dist && n.position.y < pos.y)) {
          return { node: n, dist }
        }
        return best
      }, null)

      if (nearest && nearest.dist < 300) {
        setEdges((eds) => [...eds, {
          id: `e_${nearest.node.id}_${id}`,
          source: nearest.node.id,
          target: id,
          type: "deletable",
          animated: true,
          style: { stroke: "#94a3b8", strokeWidth: 2 },
        }])
      }
    }

    // Select the new node
    setSelectedNodeId(id)

    // Auto-scroll to new node if added via click (not drag)
    if (!position) {
      setTimeout(() => {
        setCenter(pos.x + 85, pos.y + 40, { zoom: 1, duration: 300 })
      }, 50)
    }
  }, [setNodes, setEdges, setCenter])

  // ── Drag-and-drop handlers ──
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = "move"
    // Only update state if not already in drag-over state to avoid re-renders on every mousemove
    setIsDragOver(prev => prev ? prev : true)
  }, [])

  const onDragLeave = useCallback((e: React.DragEvent) => {
    if (reactFlowWrapper.current && !reactFlowWrapper.current.contains(e.relatedTarget as HTMLElement)) {
      setIsDragOver(false)
    }
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)

    const moduleData = e.dataTransfer.getData("application/reactflow")
    if (!moduleData) return

    try {
      const mod: WorkflowModule = JSON.parse(moduleData)
      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
      addModuleNode(mod, position)
    } catch {
      // Invalid data
    }
  }, [screenToFlowPosition, addModuleNode])

  // ── Delete with confirmation ──
  const handleDeleteNode = useCallback((nodeId: string) => {
    const current = confirmDeleteRef.current
    if (current?.type === "node" && current.id === nodeId) {
      // Second click = confirmed
      setNodes((nds) => nds.filter(n => n.id !== nodeId))
      setEdges((eds) => eds.filter(e => e.source !== nodeId && e.target !== nodeId))
      setSelectedNodeId(prev => prev === nodeId ? null : prev)
      setConfirmDelete(null)
    } else {
      setConfirmDelete({ type: "node", id: nodeId })
      // Auto-clear after 3s
      setTimeout(() => setConfirmDelete(prev => prev?.id === nodeId ? null : prev), 3000)
    }
  }, [setNodes, setEdges])

  const handleDeleteEdge = useCallback((edgeId: string) => {
    // Read confirmDelete from ref to avoid stale closure
    const current = confirmDeleteRef.current
    if (current?.type === "edge" && current.id === edgeId) {
      setEdges((eds) => eds.filter(e => e.id !== edgeId))
      setConfirmDelete(null)
    } else {
      setConfirmDelete({ type: "edge", id: edgeId })
      setTimeout(() => setConfirmDelete(prev => prev?.id === edgeId ? null : prev), 3000)
    }
  }, [setEdges])
  // Keep ref in sync with the latest callback
  handleDeleteEdgeRef.current = handleDeleteEdge

  // ── Delete selected nodes ──
  const deleteSelectedNodes = useCallback(() => {
    setNodes((nds) => {
      const selected = nds.filter(n => n.selected)
      if (selected.length === 0) return nds
      const selectedIds = new Set(selected.map(n => n.id))
      setEdges((eds) => eds.filter(e => !selectedIds.has(e.source) && !selectedIds.has(e.target)))
      setSelectedNodeId(null)
      return nds.filter(n => !n.selected)
    })
  }, [setNodes, setEdges])

  // ── Duplicate node (with deep copy fix) ──
  const duplicateNode = useCallback((nodeId: string) => {
    const original = nodesRef.current.find(n => n.id === nodeId)
    if (!original) return
    const id = nextId()
    const originalData = original.data as Record<string, unknown>
    const newNode: Node = {
      ...original,
      id,
      position: { x: original.position.x + 40, y: original.position.y + 60 },
      selected: false,
      data: {
        ...originalData,
        config: { ...((originalData.config as Record<string, unknown>) || {}) },
      },
    }
    setNodes((nds) => [...nds, newNode])
  }, [setNodes])

  // ── Auto-layout: simple vertical arrangement ──
  const autoLayout = useCallback(() => {
    const currentEdges = edgesRef.current
    setNodes((nds) => {
      const nodeMap = new Map(nds.map(n => [n.id, n]))
      const inDegree = new Map<string, number>()
      const adj = new Map<string, string[]>()
      nds.forEach(n => { inDegree.set(n.id, 0); adj.set(n.id, []) })
      currentEdges.forEach(e => {
        inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1)
        adj.get(e.source)?.push(e.target)
      })

      const queue: string[] = []
      inDegree.forEach((deg, id) => { if (deg === 0) queue.push(id) })
      const sorted: string[] = []
      while (queue.length > 0) {
        const id = queue.shift()!
        sorted.push(id)
        adj.get(id)?.forEach(t => {
          const d = (inDegree.get(t) || 1) - 1
          inDegree.set(t, d)
          if (d === 0) queue.push(t)
        })
      }
      nds.forEach(n => { if (!sorted.includes(n.id)) sorted.push(n.id) })

      const centerX = 300
      return sorted.map((id, i) => ({
        ...nodeMap.get(id)!,
        position: { x: centerX, y: i * 160 + 50 },
      }))
    })

    setTimeout(() => fitView({ duration: 400, padding: 0.2 }), 50)
  }, [setNodes, fitView])

  // ── Node update from config panel (debounced by panel component) ──
  const handleNodeUpdate = useCallback((nodeId: string, newData: Record<string, unknown>) => {
    setNodes(nds => nds.map(n => n.id === nodeId ? { ...n, data: newData } : n))
  }, [setNodes])

  // ── Context menu handlers ──
  const onNodeContextMenu = useCallback((event: React.MouseEvent, node: Node) => {
    event.preventDefault()
    setContextMenu({ x: event.clientX, y: event.clientY, type: "node", targetId: node.id })
  }, [])

  const onEdgeContextMenu = useCallback((event: React.MouseEvent, edge: Edge) => {
    event.preventDefault()
    setContextMenu({ x: event.clientX, y: event.clientY, type: "edge", targetId: edge.id })
  }, [])

  const onPaneContextMenu = useCallback((event: MouseEvent | React.MouseEvent) => {
    event.preventDefault()
    setContextMenu({
      x: "clientX" in event ? event.clientX : (event as React.MouseEvent).clientX,
      y: "clientY" in event ? event.clientY : (event as React.MouseEvent).clientY,
      type: "pane",
    })
  }, [])

  const closeContextMenu = useCallback(() => setContextMenu(null), [])

  // Build context menu items (use nodesRef to avoid re-computing during drag when contextMenu is null)
  const contextMenuItems = useMemo<ContextMenuItem[]>(() => {
    if (!contextMenu) return []
    if (contextMenu.type === "node" && contextMenu.targetId) {
      const node = nodesRef.current.find(n => n.id === contextMenu.targetId)
      const mod = node ? getModuleByType(node.data.moduleType as string) : null
      const canConfigure = mod?.configurable
      return buildNodeMenuItems(
        contextMenu.targetId,
        handleDeleteNode,
        duplicateNode,
        canConfigure ? (id: string) => setSelectedNodeId(id) : undefined,
      )
    }
    if (contextMenu.type === "edge" && contextMenu.targetId) {
      return buildEdgeMenuItems(contextMenu.targetId, handleDeleteEdge)
    }
    return buildPaneMenuItems(autoLayout, () => fitView({ duration: 300 }))
  }, [contextMenu, handleDeleteNode, duplicateNode, handleDeleteEdge, autoLayout, fitView])

  // ── Module search filtering ──
  const filteredModules = useMemo(() => {
    const q = moduleSearch.toLowerCase().trim()
    if (!q) return WORKFLOW_MODULES
    return WORKFLOW_MODULES.filter(m =>
      m.label.toLowerCase().includes(q) ||
      m.description.toLowerCase().includes(q) ||
      m.type.toLowerCase().includes(q)
    )
  }, [moduleSearch])

  const selectedNode = nodes.find(n => n.id === selectedNodeId) || null

  // Close right panel when no node selected
  const closeRightPanel = useCallback(() => {
    setRightPanelOpen(false)
    setSelectedNodeId(null)
  }, [])

  return (
    <div className="flex h-full">
      {/* ── Module Palette (Left Sidebar) ── */}
      <div
        data-onboarding="module-panel"
        className="w-60 border-r bg-slate-50 dark:bg-slate-950 overflow-hidden shrink-0 flex flex-col"
      >
        {/* Search */}
        <div className="p-3 pb-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="搜索模块..."
              value={moduleSearch}
              onChange={e => setModuleSearch(e.target.value)}
              className="h-8 pl-8 text-xs"
            />
          </div>
        </div>

        {/* Module list */}
        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {MODULE_CATEGORIES.map(cat => {
            const mods = filteredModules.filter(m => m.category === cat.key)
            if (mods.length === 0) return null
            return (
              <div key={cat.key} className="mb-3">
                <p className="text-[10px] font-semibold text-muted-foreground/70 mb-1.5 px-1 uppercase tracking-wider">
                  {cat.label}
                </p>
                <div className="space-y-0.5">
                  {mods.map(mod => (
                    <button
                      key={mod.type}
                      draggable
                      onDragStart={(e) => {
                        e.dataTransfer.setData("application/reactflow", JSON.stringify(mod))
                        e.dataTransfer.effectAllowed = "move"
                      }}
                      onClick={() => addModuleNode(mod)}
                      className="flex items-center gap-2 w-full p-2 rounded-lg text-left hover:bg-white dark:hover:bg-slate-800 transition-all duration-150 border border-transparent hover:border-slate-200 dark:hover:border-slate-700 hover:shadow-sm cursor-grab active:cursor-grabbing group relative"
                      title={`拖拽到画布或点击添加: ${mod.label}`}
                    >
                      {/* Colored left strip */}
                      <div className={`absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full ${mod.color} opacity-40 group-hover:opacity-80 transition-opacity`} />
                      <GripVertical className="h-3 w-3 text-muted-foreground/30 group-hover:text-muted-foreground/60 shrink-0 transition-colors ml-1" />
                      <div className={`p-1.5 rounded-md shrink-0 ${mod.color}`}>
                        {(() => { const I = ICONS[mod.icon] || Sparkles; return <I className="h-3 w-3 text-white" /> })()}
                      </div>
                      <div className="min-w-0 flex-1">
                        <span className="truncate block text-xs font-medium">{mod.label}</span>
                        <span className="truncate block text-[10px] text-muted-foreground/80">{mod.description}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )
          })}
          {filteredModules.length === 0 && (
            <div className="text-center py-8">
              <Search className="h-5 w-5 mx-auto mb-2 text-muted-foreground/30" />
              <p className="text-xs text-muted-foreground">未找到匹配模块</p>
            </div>
          )}
        </div>

        {/* Stats bar */}
        <div className="px-3 py-2 border-t bg-slate-100/50 dark:bg-slate-900/50">
          <div className="flex items-center justify-between text-[10px] text-muted-foreground">
            <span>画布 {nodes.length} 个节点 · {edges.length} 条连线</span>
          </div>
          <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground/70">
            <span>拖拽放置</span>
            <span>·</span>
            <span>右键操作</span>
            <span>·</span>
            <span>Delete 删除</span>
          </div>
        </div>
      </div>

      {/* ── ReactFlow Canvas ── */}
      <div
        ref={reactFlowWrapper}
        data-onboarding="canvas"
        className={`flex-1 relative transition-all duration-200 ${
          isDragOver ? "ring-2 ring-inset ring-blue-400/50" : ""
        }`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={handleConnect}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          className="bg-slate-50 dark:bg-slate-950"
          onPaneClick={() => { setSelectedNodeId(null); setContextMenu(null); setConfirmDelete(null) }}
          onNodeContextMenu={onNodeContextMenu}
          onEdgeContextMenu={onEdgeContextMenu}
          onPaneContextMenu={onPaneContextMenu}
          deleteKeyCode={["Backspace", "Delete"]}
          multiSelectionKeyCode="Shift"
          snapToGrid
          snapGrid={[15, 15]}
          nodeDragThreshold={2}
          proOptions={{ hideAttribution: false }}
        >
          <Background gap={15} size={1} color="#e2e8f0" />
          <Controls showInteractive={false} className="!bg-white !dark:bg-slate-900 !border-slate-200" />
          <MiniMap
            className="!bg-white dark:!bg-slate-900 !border-slate-200 dark:!border-slate-700"
            maskColor="rgba(0,0,0,0.06)"
            nodeColor={miniMapNodeColor}
          />

          {/* Toolbar */}
          <Panel position="top-right" className="flex gap-1.5" data-onboarding="toolbar">
            <Button
              variant="outline"
              size="sm"
              onClick={autoLayout}
              className="bg-white/90 dark:bg-slate-900/90 backdrop-blur-sm h-7 text-xs"
              title="自动排列所有节点"
            >
              <LayoutList className="h-3 w-3 mr-1" /> 自动排列
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={deleteSelectedNodes}
              className="bg-white/90 dark:bg-slate-900/90 backdrop-blur-sm h-7 text-xs"
              title="删除选中的节点"
            >
              <Trash2 className="h-3 w-3 mr-1" /> 删除选中
            </Button>
            {/* Toggle right panel */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRightPanelOpen(!rightPanelOpen)}
              className="bg-white/90 dark:bg-slate-900/90 backdrop-blur-sm h-7 w-7 p-0"
              title={rightPanelOpen ? "关闭配置面板" : "打开配置面板"}
            >
              {rightPanelOpen ? <PanelRightClose className="h-3 w-3" /> : <PanelRightOpen className="h-3 w-3" />}
            </Button>
          </Panel>

          {/* Empty canvas state */}
          {nodes.length === 0 && (
            <Panel position="top-center">
              <div className="mt-20 text-center pointer-events-none">
                <div className="inline-flex flex-col items-center gap-3 p-8 rounded-2xl border-2 border-dashed border-slate-200 dark:border-slate-700 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm">
                  <div className="p-3 rounded-full bg-blue-50 dark:bg-blue-950">
                    <Plus className="h-8 w-8 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
                      从左侧拖拽模块到这里
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      开始构建你的工作流 · 也可以点击模块快速添加
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground/60 mt-1">
                    <ArrowLeft className="h-3 w-3" />
                    <span>← 左侧模块面板</span>
                  </div>
                </div>
              </div>
            </Panel>
          )}

          {/* Drop zone overlay when dragging */}
          {isDragOver && (
            <Panel position="top-center">
              <div className="mt-4 px-5 py-2.5 bg-blue-500/90 text-white text-sm rounded-xl shadow-lg backdrop-blur-sm flex items-center gap-2">
                <Plus className="h-4 w-4" />
                松开鼠标放置模块
              </div>
            </Panel>
          )}

          {/* Delete confirmation toast */}
          {confirmDelete && (
            <Panel position="bottom-center">
              <div className="mb-4 px-4 py-2.5 bg-slate-800 dark:bg-slate-200 text-white dark:text-slate-900 text-xs rounded-xl shadow-lg flex items-center gap-3 animate-in slide-in-from-bottom-2 duration-200">
                <Trash2 className="h-3.5 w-3.5 text-red-400 dark:text-red-500" />
                <span>再次点击确认删除{confirmDelete.type === "node" ? "节点" : "连线"}</span>
                <button
                  className="text-[10px] px-2 py-0.5 rounded bg-white/20 dark:bg-black/20 hover:bg-white/30 transition-colors"
                  onClick={() => setConfirmDelete(null)}
                >
                  取消
                </button>
              </div>
            </Panel>
          )}
        </ReactFlow>
      </div>

      {/* ── Right Panel: Node Config (collapsible) ── */}
      <div
        className={`border-l bg-white dark:bg-slate-950 overflow-hidden shrink-0 transition-all duration-300 ease-in-out ${
          rightPanelOpen && selectedNode ? "w-72" : "w-0"
        }`}
      >
        <div className="w-72 h-full p-4 overflow-y-auto">
          {selectedNode ? (
            <NodeConfigPanel
              node={selectedNode}
              onUpdate={handleNodeUpdate}
              onClose={closeRightPanel}
            />
          ) : null}
        </div>
      </div>

      {/* ── Context Menu ── */}
      <CanvasContextMenu
        menu={contextMenu}
        items={contextMenuItems}
        onClose={closeContextMenu}
      />
    </div>
  )
}

// ── Wrapper with ReactFlow context ──
export function WorkflowEditor(props: WorkflowEditorProps) {
  return <EditorInner {...props} />
}
