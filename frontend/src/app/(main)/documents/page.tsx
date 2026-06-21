"use client"

import { useState, useEffect, useCallback, useRef, memo } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { FolderTree, FolderItem } from "@/components/documents/FolderTree"
import { DocumentListSkeleton } from "@/components/skeletons/DocumentListSkeleton"
import {
  FileText, Plus, Search, FolderOpen, Trash2, Edit3,
  MoreVertical, Tag, CheckSquare, Square, Move, Download,
  Upload,
} from "lucide-react"
import { toast } from "sonner"
import { apiTry, apiFetchBlob } from "@/lib/api-client"

interface TagItem {
  id: number
  name: string
  color: string
}

interface Document {
  id: number
  title: string
  status: string
  version: number
  folder_id: number | null
  created_at: string
  updated_at: string
  tags: TagItem[]
}

const STATUS_TABS = [
  { value: "", label: "全部" },
  { value: "draft", label: "草稿" },
  { value: "published", label: "已发布" },
  { value: "archived", label: "已归档" },
]

const STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  published: "已发布",
  archived: "已归档",
}

// ── Memoized DocumentCard ────────────────────────

const DocumentCard = memo(function DocumentCard({
  doc, batchMode, isSelected, onToggleSelect, onOpen, onChangeStatus,
  onExport, onDelete,
}: {
  doc: Document
  batchMode: boolean
  isSelected: boolean
  onToggleSelect: (id: number) => void
  onOpen: (id: number) => void
  onChangeStatus: (id: number, status: string) => void
  onExport: (id: number, format: string) => void
  onDelete: (id: number) => void
}) {
  return (
    <div
      className={`flex items-center gap-3 p-3 rounded-lg border transition-all cursor-pointer hover:shadow-sm hover:border-primary/30 ${
        isSelected ? "border-primary bg-primary/5" : ""
      }`}
      onClick={() => !batchMode && onOpen(doc.id)}
    >
      {batchMode && (
        <button
          onClick={e => { e.stopPropagation(); onToggleSelect(doc.id) }}
          className="shrink-0"
        >
          {isSelected ? (
            <CheckSquare className="h-4 w-4 text-primary" />
          ) : (
            <Square className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
      )}

      <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950 shrink-0">
        <FileText className="h-5 w-5 text-blue-600 dark:text-blue-400" />
      </div>

      <div className="flex-1 min-w-0">
        <h3 className="font-medium text-sm truncate">{doc.title}</h3>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-muted-foreground">
            v{doc.version} · 更新于 {new Date(doc.updated_at).toLocaleDateString("zh-CN")}
          </span>
          {doc.tags.length > 0 && (
            <div className="flex items-center gap-1">
              {doc.tags.map(tag => (
                <span
                  key={tag.id}
                  className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full"
                  style={{ backgroundColor: tag.color + "20", color: tag.color }}
                >
                  {tag.name}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <Badge
        variant={doc.status === "published" ? "default" : "secondary"}
        className="text-xs shrink-0"
      >
        {STATUS_LABELS[doc.status] || doc.status}
      </Badge>

      {!batchMode && (
        <DropdownMenu>
          <DropdownMenuTrigger render={
            <Button
              variant="ghost" size="icon" className="h-8 w-8 shrink-0"
              onClick={e => e.stopPropagation()}
            />
          }>
              <MoreVertical className="h-4 w-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onOpen(doc.id)}>
              <Edit3 className="h-4 w-4 mr-2" /> 编辑
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onChangeStatus(doc.id, doc.status === "published" ? "draft" : "published")}>
              <FileText className="h-4 w-4 mr-2" />
              {doc.status === "published" ? "取消发布" : "发布"}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onExport(doc.id, "markdown")}>
              <Download className="h-4 w-4 mr-2" /> 导出 Markdown
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onExport(doc.id, "html")}>
              <Download className="h-4 w-4 mr-2" /> 导出 HTML
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onExport(doc.id, "latex")}>
              <Download className="h-4 w-4 mr-2" /> 导出 LaTeX
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onExport(doc.id, "docx")}>
              <Download className="h-4 w-4 mr-2" /> 导出 Word
            </DropdownMenuItem>
            <DropdownMenuItem className="text-red-500" onClick={() => onDelete(doc.id)}>
              <Trash2 className="h-4 w-4 mr-2" /> 删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  )
})

export default function DocumentsPage() {
  const router = useRouter()
  const [documents, setDocuments] = useState<Document[]>([])
  const [search, setSearch] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  // Filters
  const [folderId, setFolderId] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState("")
  const [tagFilter, setTagFilter] = useState<number | null>(null)

  // Batch mode
  const [batchMode, setBatchMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 20

  // Data sources
  const [folders, setFolders] = useState<FolderItem[]>([])
  const [tags, setTags] = useState<TagItem[]>([])

  // Debounce search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedSearch(search), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [search])

  // Fetch folders
  const fetchFolders = useCallback(async () => {
    const [data] = await apiTry<FolderItem[]>("/api/folders")
    if (data) setFolders(data)
  }, [])

  // Fetch tags
  const fetchTags = useCallback(async () => {
    const [data] = await apiTry<TagItem[]>("/api/tags")
    if (data) setTags(data)
  }, [])

  // Fetch documents
  const fetchDocuments = useCallback(async () => {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) })
    if (debouncedSearch) params.set("search", debouncedSearch)
    if (folderId !== null) params.set("folder_id", String(folderId))
    if (statusFilter) params.set("status", statusFilter)
    if (tagFilter !== null) params.set("tag_id", String(tagFilter))

    const [data, err] = await apiTry<{ documents: Document[]; total: number }>(`/api/documents?${params}`)
    if (data) {
      setDocuments(data.documents || [])
      setTotal(data.total || 0)
    }
    setLoading(false)
  }, [debouncedSearch, folderId, statusFilter, tagFilter, page])

  useEffect(() => { fetchDocuments() }, [fetchDocuments])
  useEffect(() => { fetchFolders() }, [fetchFolders])
  useEffect(() => { fetchTags() }, [fetchTags])

  // Reset page when filters change
  useEffect(() => { setPage(0) }, [debouncedSearch, folderId, statusFilter, tagFilter])

  // ── Document operations (stable callbacks) ─────

  const createDocument = useCallback(async () => {
    const [doc, err] = await apiTry<{ id: number }>("/api/documents", {
      method: "POST",
      body: JSON.stringify({ title: "无标题文档", folder_id: folderId }),
    })
    if (doc) router.push(`/editor/${doc.id}`)
    else toast.error(err?.message || "创建文档失败")
  }, [folderId, router])

  const deleteDocument = useCallback(async (id: number) => {
    if (!confirm("确定要删除这篇文档吗？")) return
    const [, err] = await apiTry(`/api/documents/${id}`, { method: "DELETE" })
    if (!err) { toast.success("文档已删除"); fetchDocuments() }
    else toast.error(err.message || "删除失败")
  }, [fetchDocuments])

  const changeStatus = useCallback(async (id: number, status: string) => {
    const [, err] = await apiTry(`/api/documents/${id}/status`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    })
    if (!err) {
      toast.success(`状态已更新为 ${STATUS_LABELS[status] || status}`)
      fetchDocuments()
    } else {
      toast.error("更新状态失败")
    }
  }, [fetchDocuments])

  const exportDocument = useCallback(async (id: number, format: string) => {
    try {
      const { blob, headers } = await apiFetchBlob(`/api/documents/${id}/export?format=${format}`)
      const disposition = headers.get("content-disposition") || ""
      const match = disposition.match(/filename="(.+?)"/)
      const extMap: Record<string, string> = { markdown: "md", html: "html", latex: "tex", docx: "docx" }
      const filename = match ? match[1] : `document.${extMap[format] || format}`

      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
      toast.success("导出成功")
    } catch {
      toast.error("导出失败")
    }
  }, [])

  const importDocument = useCallback(async (file: File) => {
    const formData = new FormData()
    formData.append("file", file)
    const [, err] = await apiTry("/api/documents/import", {
      method: "POST",
      body: formData,
    })
    if (!err) {
      toast.success(`已导入: ${file.name}`)
      fetchDocuments()
    } else {
      toast.error(err.message || "导入失败")
    }
  }, [fetchDocuments])

  const openDocument = useCallback((id: number) => {
    router.push(`/editor/${id}`)
  }, [router])

  // ── Batch operations ───────────────────────────

  const toggleSelect = useCallback((id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === documents.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(documents.map(d => d.id)))
    }
  }, [selectedIds.size, documents])

  const batchDelete = useCallback(async () => {
    if (selectedIds.size === 0) return
    if (!confirm(`确定要删除选中的 ${selectedIds.size} 篇文档吗？`)) return
    const [data, err] = await apiTry<{ message: string }>("/api/documents/batch-delete", {
      method: "POST",
      body: JSON.stringify({ ids: Array.from(selectedIds) }),
    })
    if (data) {
      toast.success(data.message)
      setSelectedIds(new Set())
      setBatchMode(false)
      fetchDocuments()
    } else {
      toast.error(err?.message || "批量删除失败")
    }
  }, [selectedIds, fetchDocuments])

  const batchMove = useCallback(async (targetFolderId: number | null) => {
    if (selectedIds.size === 0) return
    const [data, err] = await apiTry<{ message: string }>("/api/documents/batch-move", {
      method: "POST",
      body: JSON.stringify({ ids: Array.from(selectedIds), folder_id: targetFolderId }),
    })
    if (data) {
      toast.success(data.message)
      setSelectedIds(new Set())
      setBatchMode(false)
      fetchDocuments()
    } else {
      toast.error(err?.message || "批量移动失败")
    }
  }, [selectedIds, fetchDocuments])

  const toggleBatchMode = useCallback(() => {
    setBatchMode(prev => !prev)
    setSelectedIds(new Set())
  }, [])

  // ── Render ─────────────────────────────────────

  return (
    <div className="flex flex-1 min-h-0">
      {/* Folder tree */}
      <FolderTree
        folders={folders}
        selectedFolderId={folderId}
        onSelect={setFolderId}
        onRefresh={fetchFolders}
      />

      {/* Document list */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="border-b px-6 py-3 shrink-0 space-y-3">
          <div className="flex items-center gap-4">
            <div>
              <h1 className="text-lg font-semibold">文档管理</h1>
              <p className="text-xs text-muted-foreground mt-0.5">共 {total} 篇文档</p>
            </div>
            <div className="flex-1" />
            <div className="relative w-56">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索文档..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="pl-9 h-9"
              />
            </div>
            {/* Tag filter */}
            {tags.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger render={<Button variant="outline" size="sm" className="gap-1.5" />}>
                    <Tag className="h-3.5 w-3.5" />
                    {tagFilter !== null ? tags.find(t => t.id === tagFilter)?.name || "标签" : "标签"}
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => setTagFilter(null)}>
                    全部标签
                  </DropdownMenuItem>
                  {tags.map(tag => (
                    <DropdownMenuItem key={tag.id} onClick={() => setTagFilter(tag.id)}>
                      <span
                        className="inline-block w-2.5 h-2.5 rounded-full mr-2"
                        style={{ backgroundColor: tag.color }}
                      />
                      {tag.name}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
            <Button size="sm" onClick={createDocument}>
              <Plus className="h-4 w-4 mr-1" /> 新建文档
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}>
                  <Upload className="h-4 w-4 mr-1" /> 导入
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => fileInputRef.current?.click()}>
                  Markdown (.md)
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <input
              ref={fileInputRef}
              type="file"
              accept=".md"
              className="hidden"
              onChange={e => {
                const file = e.target.files?.[0]
                if (file) importDocument(file)
                e.target.value = ""
              }}
            />
          </div>

          {/* Status tabs + batch controls */}
          <div className="flex items-center gap-2">
            {STATUS_TABS.map(tab => (
              <button
                key={tab.value}
                onClick={() => setStatusFilter(tab.value)}
                className={`px-3 py-1 text-xs rounded-full transition-colors ${
                  statusFilter === tab.value
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted hover:bg-muted/80 text-muted-foreground"
                }`}
              >
                {tab.label}
              </button>
            ))}

            <div className="flex-1" />

            {/* Batch mode toggle */}
            <Button
              variant={batchMode ? "default" : "outline"}
              size="sm"
              className="text-xs"
              onClick={toggleBatchMode}
            >
              {batchMode ? "取消" : "批量操作"}
            </Button>

            {batchMode && selectedIds.size > 0 && (
              <>
                <span className="text-xs text-muted-foreground">
                  已选 {selectedIds.size} 项
                </span>
                {/* Batch move */}
                <DropdownMenu>
                  <DropdownMenuTrigger render={<Button variant="outline" size="sm" className="text-xs gap-1" />}>
                      <Move className="h-3.5 w-3.5" /> 移动
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => batchMove(null)}>
                      移至根目录
                    </DropdownMenuItem>
                    {folders.map(f => (
                      <DropdownMenuItem key={f.id} onClick={() => batchMove(f.id)}>
                        {f.name}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
                {/* Batch delete */}
                <Button variant="outline" size="sm" className="text-xs text-red-500 gap-1" onClick={batchDelete}>
                  <Trash2 className="h-3.5 w-3.5" /> 删除
                </Button>
              </>
            )}
          </div>
        </header>

        {/* Document list */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <DocumentListSkeleton count={6} />
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
              <FolderOpen className="h-12 w-12 mb-4 opacity-30" />
              <p className="text-sm font-medium">
                {debouncedSearch || tagFilter || statusFilter ? "没有匹配的文档" : "还没有文档"}
              </p>
              {!debouncedSearch && !tagFilter && !statusFilter && (
                <Button variant="outline" size="sm" className="mt-4" onClick={createDocument}>
                  <Plus className="h-4 w-4 mr-1" /> 创建第一篇文档
                </Button>
              )}
            </div>
          ) : (
            <div className="grid gap-2">
              {/* Select all in batch mode */}
              {batchMode && (
                <button
                  onClick={toggleSelectAll}
                  className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground px-4 py-1.5"
                >
                  {selectedIds.size === documents.length ? (
                    <CheckSquare className="h-4 w-4 text-primary" />
                  ) : (
                    <Square className="h-4 w-4" />
                  )}
                  全选
                </button>
              )}

              {documents.map(doc => (
                <DocumentCard
                  key={doc.id}
                  doc={doc}
                  batchMode={batchMode}
                  isSelected={selectedIds.has(doc.id)}
                  onToggleSelect={toggleSelect}
                  onOpen={openDocument}
                  onChangeStatus={changeStatus}
                  onExport={exportDocument}
                  onDelete={deleteDocument}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {total > PAGE_SIZE && (
            <div className="flex items-center justify-center gap-2 mt-6 pt-4 border-t">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage(p => Math.max(0, p - 1))}
              >
                上一页
              </Button>
              <span className="text-sm text-muted-foreground">
                第 {page + 1} / {Math.ceil(total / PAGE_SIZE)} 页
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={(page + 1) * PAGE_SIZE >= total}
                onClick={() => setPage(p => p + 1)}
              >
                下一页
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
