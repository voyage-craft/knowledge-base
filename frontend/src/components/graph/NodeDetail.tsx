"use client"

import { useEffect, useState } from "react"
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { apiTry, apiFetch } from "@/lib/api-client"
import { FileText, Trash2, ExternalLink } from "lucide-react"
import { useRouter } from "next/navigation"

interface NodeDetailData {
  id: number
  node_type: string
  label: string
  description?: string | null
  document_id?: number | null
  metadata_json?: Record<string, unknown> | null
}

interface NodeDetailProps {
  nodeId: number | null
  onClose: () => void
  onDelete: (nodeId: number) => void
  allNodes: NodeDetailData[]
}

export function NodeDetail({ nodeId, onClose, onDelete, allNodes }: NodeDetailProps) {
  const router = useRouter()
  const [node, setNode] = useState<NodeDetailData | null>(null)
  const [relatedDocs, setRelatedDocs] = useState<Array<{ id: number; title: string }>>([])

  useEffect(() => {
    if (!nodeId) {
      setNode(null)
      return
    }
    const found = allNodes.find((n) => n.id === nodeId)
    setNode(found || null)

    // If entity/concept, find related documents
    if (found && found.node_type !== "document") {
      // We'd need a separate API for this; for now just show the node info
      setRelatedDocs([])
    }
  }, [nodeId, allNodes])

  const meta = node?.metadata_json as Record<string, string> | null

  return (
    <Sheet open={nodeId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>{node?.label || "节点详情"}</SheetTitle>
          <SheetDescription>
            {node?.node_type === "document" && "文档节点"}
            {node?.node_type === "entity" && `实体 · ${meta?.entity_type || "未知"}`}
            {node?.node_type === "concept" && "概念节点"}
          </SheetDescription>
        </SheetHeader>

        {node && (
          <div className="px-4 space-y-4">
            {/* Description */}
            {node.description && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-1">描述</h4>
                <p className="text-sm">{node.description}</p>
              </div>
            )}

            {/* Node type badge */}
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">类型</h4>
              <span
                className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                  node.node_type === "document"
                    ? "bg-blue-100 text-blue-700"
                    : node.node_type === "entity"
                    ? "bg-green-100 text-green-700"
                    : "bg-amber-100 text-amber-700"
                }`}
              >
                {node.node_type === "document" ? "文档" : node.node_type === "entity" ? "实体" : "概念"}
              </span>
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-2">
              {node.node_type === "document" && node.document_id && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => router.push(`/editor/${node.document_id}`)}
                >
                  <ExternalLink className="h-3.5 w-3.5 mr-1" />
                  打开文档
                </Button>
              )}
              <Button
                size="sm"
                variant="destructive"
                onClick={() => {
                  onDelete(node.id)
                  onClose()
                }}
              >
                <Trash2 className="h-3.5 w-3.5 mr-1" />
                删除节点
              </Button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
