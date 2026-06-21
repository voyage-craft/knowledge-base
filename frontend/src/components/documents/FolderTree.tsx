"use client"

import { useState, useMemo, useCallback, memo } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Folder, FolderOpen, ChevronRight, ChevronDown, Plus, Trash2, Pencil,
} from "lucide-react"
import { toast } from "sonner"
import { apiTry } from "@/lib/api-client"

export interface FolderItem {
  id: number
  name: string
  parent_id: number | null
  position: number
}

interface FolderTreeProps {
  folders: FolderItem[]
  selectedFolderId: number | null
  onSelect: (folderId: number | null) => void
  onRefresh: () => void
}

interface TreeNode extends FolderItem {
  children: TreeNode[]
}

function buildTree(folders: FolderItem[]): TreeNode[] {
  const map = new Map<number, TreeNode>()
  const roots: TreeNode[] = []

  for (const f of folders) {
    map.set(f.id, { ...f, children: [] })
  }

  for (const f of folders) {
    const node = map.get(f.id)!
    if (f.parent_id && map.has(f.parent_id)) {
      map.get(f.parent_id)!.children.push(node)
    } else {
      roots.push(node)
    }
  }

  return roots
}

const FolderNode = memo(function FolderNode({
  node, depth, selectedId, onSelect, expandedIds, toggleExpand, onDelete, onRename,
}: {
  node: TreeNode
  depth: number
  selectedId: number | null
  onSelect: (id: number) => void
  expandedIds: Set<number>
  toggleExpand: (id: number) => void
  onDelete: (id: number) => void
  onRename: (id: number, name: string) => void
}) {
  const isExpanded = expandedIds.has(node.id)
  const isSelected = selectedId === node.id
  const hasChildren = node.children.length > 0

  const [renaming, setRenaming] = useState(false)
  const [renameValue, setRenameValue] = useState(node.name)

  async function submitRename() {
    if (renameValue.trim() && renameValue !== node.name) {
      onRename(node.id, renameValue.trim())
    }
    setRenaming(false)
  }

  return (
    <div>
      <div
        className={`flex items-center gap-1 py-1.5 px-2 rounded-md text-sm cursor-pointer group transition-colors ${
          isSelected
            ? "bg-primary/10 text-primary font-medium"
            : "hover:bg-muted text-foreground/80"
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => onSelect(node.id)}
      >
        <button
          className="shrink-0 p-0.5 rounded hover:bg-muted-foreground/10"
          onClick={e => { e.stopPropagation(); toggleExpand(node.id) }}
        >
          {hasChildren ? (
            isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />
          ) : (
            <span className="w-3.5" />
          )}
        </button>

        {isExpanded ? (
          <FolderOpen className="h-4 w-4 text-blue-500 shrink-0" />
        ) : (
          <Folder className="h-4 w-4 text-blue-500 shrink-0" />
        )}

        {renaming ? (
          <Input
            value={renameValue}
            onChange={e => setRenameValue(e.target.value)}
            onBlur={submitRename}
            onKeyDown={e => { if (e.key === "Enter") submitRename(); if (e.key === "Escape") setRenaming(false) }}
            className="h-6 text-xs px-1.5 flex-1"
            autoFocus
            onClick={e => e.stopPropagation()}
          />
        ) : (
          <span className="truncate flex-1">{node.name}</span>
        )}

        {/* Actions (visible on hover) */}
        <div className="hidden group-hover:flex items-center gap-0.5 shrink-0">
          <button
            className="p-0.5 rounded hover:bg-muted-foreground/10"
            onClick={e => { e.stopPropagation(); setRenaming(true); setRenameValue(node.name) }}
            title="重命名"
          >
            <Pencil className="h-3 w-3" />
          </button>
          <button
            className="p-0.5 rounded hover:bg-red-100 dark:hover:bg-red-950 text-red-500"
            onClick={e => { e.stopPropagation(); onDelete(node.id) }}
            title="删除"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      </div>

      {isExpanded && node.children.map(child => (
        <FolderNode
          key={child.id}
          node={child}
          depth={depth + 1}
          selectedId={selectedId}
          onSelect={onSelect}
          expandedIds={expandedIds}
          toggleExpand={toggleExpand}
          onDelete={onDelete}
          onRename={onRename}
        />
      ))}
    </div>
  )
})

export function FolderTree({ folders, selectedFolderId, onSelect, onRefresh }: FolderTreeProps) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState("")

  const tree = useMemo(() => buildTree(folders), [folders])

  const toggleExpand = useCallback((id: number) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  async function createFolder() {
    if (!newName.trim()) return
    const [, err] = await apiTry("/api/folders", {
      method: "POST",
      body: JSON.stringify({
        name: newName.trim(),
        parent_id: selectedFolderId,
      }),
    })
    if (!err) {
      toast.success("文件夹已创建")
      setNewName("")
      setCreating(false)
      onRefresh()
    } else {
      toast.error(err.message || "创建失败")
    }
  }

  const deleteFolder = useCallback(async (id: number) => {
    if (!confirm("确定要删除这个文件夹吗？文件夹内的文档将移至根目录。")) return
    const [, err] = await apiTry(`/api/folders/${id}`, { method: "DELETE" })
    if (!err) {
      toast.success("文件夹已删除")
      if (selectedFolderId === id) onSelect(null)
      onRefresh()
    } else {
      toast.error(err.message || "删除失败")
    }
  }, [selectedFolderId, onSelect, onRefresh])

  const renameFolder = useCallback(async (id: number, name: string) => {
    const [, err] = await apiTry(`/api/folders/${id}`, {
      method: "PUT",
      body: JSON.stringify({ name }),
    })
    if (!err) { toast.success("文件夹已重命名"); onRefresh() }
    else toast.error(err.message || "重命名失败")
  }, [onRefresh])

  return (
    <div className="w-56 border-r bg-muted/30 flex flex-col shrink-0">
      <div className="flex items-center justify-between px-3 py-3 border-b">
        <span className="text-sm font-medium">文件夹</span>
        <Button
          variant="ghost" size="icon" className="h-7 w-7"
          onClick={() => setCreating(true)}
          title="新建文件夹"
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-1.5 py-2">
        {/* All documents (root) */}
        <div
          className={`flex items-center gap-2 py-1.5 px-2 rounded-md text-sm cursor-pointer transition-colors ${
            selectedFolderId === null
              ? "bg-primary/10 text-primary font-medium"
              : "hover:bg-muted text-foreground/80"
          }`}
          onClick={() => onSelect(null)}
        >
          <FolderOpen className="h-4 w-4 text-slate-400" />
          <span>全部文档</span>
        </div>

        {/* Folder tree */}
        {tree.map(node => (
          <FolderNode
            key={node.id}
            node={node}
            depth={0}
            selectedId={selectedFolderId}
            onSelect={onSelect}
            expandedIds={expandedIds}
            toggleExpand={toggleExpand}
            onDelete={deleteFolder}
            onRename={renameFolder}
          />
        ))}

        {/* Inline create */}
        {creating && (
          <div className="flex items-center gap-1 mt-1 px-2">
            <Input
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="文件夹名称"
              className="h-7 text-xs"
              autoFocus
              onKeyDown={e => {
                if (e.key === "Enter") createFolder()
                if (e.key === "Escape") { setCreating(false); setNewName("") }
              }}
            />
            <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={createFolder}>
              <Plus className="h-3 w-3" />
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
