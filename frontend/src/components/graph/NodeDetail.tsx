"use client"

import { useEffect, useState, useMemo } from "react"
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Trash2, ExternalLink, FileText, Network, AlertTriangle } from "lucide-react"
import { useRouter } from "next/navigation"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog"
import { toast } from "sonner"

interface NodeDetailData {
  id: number
  node_type: string
  label: string
  description?: string | null
  document_id?: number | null
  metadata_json?: Record<string, unknown> | null
}

interface EdgeData {
  id: number
  source_id: number
  target_id: number
  edge_type: string
  weight: number
  description?: string | null
}

interface NodeDetailProps {
  nodeId: number | null
  onClose: () => void
  onDelete: (nodeId: number) => void
  allNodes: NodeDetailData[]
  allEdges: EdgeData[]
}

export function NodeDetail({ nodeId, onClose, onDelete, allNodes, allEdges }: NodeDetailProps) {
  const router = useRouter()
  const [node, setNode] = useState<NodeDetailData | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  useEffect(() => {
    if (!nodeId) {
      setNode(null)
      return
    }
    const found = allNodes.find((n) => n.id === nodeId)
    setNode(found || null)
  }, [nodeId, allNodes])

  // Compute related nodes and documents from edges
  const { relatedNodes, relatedDocs } = useMemo(() => {
    if (!node || !allEdges.length) return { relatedNodes: [], relatedDocs: [] }

    // Find all edges connected to this node
    const connectedEdges = allEdges.filter(
      e => e.source_id === node.id || e.target_id === node.id
    )

    // Find related node IDs (the other end of each edge)
    const relatedNodeIds = new Set<number>()
    connectedEdges.forEach(e => {
      if (e.source_id === node.id) relatedNodeIds.add(e.target_id)
      else relatedNodeIds.add(e.source_id)
    })

    // Map to node objects
    const related = allNodes.filter(n => relatedNodeIds.has(n.id))

    // Find related document nodes
    const docs = related
      .filter(n => n.node_type === "document" && n.document_id)
      .map(n => ({
        id: n.document_id as number,
        title: n.label,
        nodeId: n.id,
        edgeType: connectedEdges.find(e =>
          (e.source_id === node.id && e.target_id === n.id) ||
          (e.target_id === node.id && e.source_id === n.id)
        )?.edge_type,
      }))

    return {
      relatedNodes: related.filter(n => n.node_type !== "document"),
      relatedDocs: docs,
    }
  }, [node, allNodes, allEdges])

  const meta = node?.metadata_json as Record<string, string> | null

  const handleNavigateToDoc = (docId: number) => {
    router.push(`/documents/${docId}`)
    onClose()
  }

  const handleViewInGraph = () => {
    // Just close the detail panel — the node is already in the graph
    onClose()
  }

  const handleNavigateRelated = (nodeId: number) => {
    // Navigate to a related node in the graph
    // The parent component will handle this via nodeId prop change
    // We need to communicate this up — but actually the parent passes nodeId
    // and we're in a Sheet, so we just close and let parent handle the new selection
  }

  return (
    <Sheet open={nodeId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{node?.label || "节点详情"}</SheetTitle>
          <SheetDescription>
            {node?.node_type === "document" && "文档节点"}
            {node?.node_type === "entity" && `实体 · ${meta?.entity_type || "未知"}`}
            {node?.node_type === "concept" && "概念节点"}
          </SheetDescription>
        </SheetHeader>

        {node && (
          <div className="px-4 space-y-4 mt-2">
            {/* Description */}
            {node.description && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-1">描述</h4>
                <p className="text-sm leading-relaxed">{node.description}</p>
              </div>
            )}

            {/* Node type badge */}
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">类型</h4>
              <span
                className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                  node.node_type === "document"
                    ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                    : node.node_type === "entity"
                    ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                    : "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
                }`}
              >
                {node.node_type === "document" ? "文档" : node.node_type === "entity" ? "实体" : "概念"}
              </span>
            </div>

            {/* Direct document link (for document nodes) */}
            {node.node_type === "document" && node.document_id && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-1.5">关联文档</h4>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleNavigateToDoc(node.document_id!)}
                  className="w-full justify-start"
                >
                  <FileText className="h-3.5 w-3.5 mr-1.5 flex-shrink-0" />
                  <span className="truncate">{node.label}</span>
                  <ExternalLink className="h-3 w-3 ml-auto flex-shrink-0" />
                </Button>
              </div>
            )}

            {/* Related documents (for entity/concept nodes) */}
            {node.node_type !== "document" && relatedDocs.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-1.5">
                  引用此{node.node_type === "entity" ? "实体" : "概念"}的文档 ({relatedDocs.length})
                </h4>
                <div className="space-y-1.5">
                  {relatedDocs.map(doc => (
                    <Button
                      key={doc.id}
                      size="sm"
                      variant="ghost"
                      onClick={() => handleNavigateToDoc(doc.id)}
                      className="w-full justify-start text-left h-auto py-1.5"
                    >
                      <FileText className="h-3.5 w-3.5 mr-1.5 flex-shrink-0 text-muted-foreground" />
                      <span className="truncate flex-1">{doc.title}</span>
                      <ExternalLink className="h-3 w-3 ml-auto flex-shrink-0 text-muted-foreground" />
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Related entities/concepts */}
            {relatedNodes.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-1.5">
                  关联节点 ({relatedNodes.length})
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {relatedNodes.slice(0, 15).map(rn => (
                    <span
                      key={rn.id}
                      className={`inline-block px-2 py-0.5 rounded text-xs cursor-pointer hover:opacity-80 ${
                        rn.node_type === "entity"
                          ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                          : "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
                      }`}
                      title={rn.description || rn.label}
                    >
                      {rn.label}
                    </span>
                  ))}
                  {relatedNodes.length > 15 && (
                    <span className="text-xs text-muted-foreground py-0.5">
                      +{relatedNodes.length - 15} 更多
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* No relationships */}
            {node.node_type !== "document" && relatedDocs.length === 0 && relatedNodes.length === 0 && (
              <div className="text-sm text-muted-foreground italic">
                此节点暂无关联关系
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 pt-2 border-t">
              {node.node_type === "document" && node.document_id && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleNavigateToDoc(node.document_id!)}
                >
                  <ExternalLink className="h-3.5 w-3.5 mr-1" />
                  打开文档
                </Button>
              )}
              <Button size="sm" variant="destructive" onClick={() => setShowDeleteConfirm(true)}>
                <Trash2 className="h-3.5 w-3.5 mr-1" />
                删除节点
              </Button>
              <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>确认删除节点？</DialogTitle>
                    <DialogDescription>
                      此操作将删除节点「{node.label}」及其所有关联关系，且不可撤销。
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <Button size="sm" variant="outline" onClick={() => setShowDeleteConfirm(false)}>
                      取消
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => {
                        onDelete(node.id)
                        onClose()
                        toast.success("节点已删除")
                      }}
                    >
                      确认删除
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
