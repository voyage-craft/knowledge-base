"use client"

import { useState, useCallback } from "react"
import { apiTry, apiFetch } from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Upload, FileText, Check, X, AlertTriangle, Loader2,
  ChevronDown, ChevronUp, Sparkles, Tag, FolderOpen,
} from "lucide-react"

interface ImportFile {
  id: number
  batch_id: number
  filename: string
  file_type: string
  status: string
  ai_analysis: Record<string, unknown> | null
  error_message: string | null
  imported_document_id: number | null
  created_at: string
}

interface ImportBatch {
  id: number
  status: string
  total_files: number
  processed_count: number
  created_at: string
  files: ImportFile[]
}

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-gray-100 text-gray-600",
  analyzing: "bg-blue-100 text-blue-600",
  ready: "bg-green-100 text-green-600",
  rejected: "bg-red-100 text-red-600",
  imported: "bg-emerald-100 text-emerald-600",
  error: "bg-red-100 text-red-600",
}

const STATUS_LABEL: Record<string, string> = {
  pending: "待分析",
  analyzing: "分析中",
  ready: "待审核",
  rejected: "已拒绝",
  imported: "已导入",
  error: "出错",
}

export default function ImportPage() {
  const [batch, setBatch] = useState<ImportBatch | null>(null)
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [importing, setImporting] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<Set<number>>(new Set())
  const [expandedFile, setExpandedFile] = useState<number | null>(null)
  const [dragOver, setDragOver] = useState(false)

  async function handleUpload(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return
    setUploading(true)

    const formData = new FormData()
    for (let i = 0; i < fileList.length; i++) {
      formData.append("files", fileList[i])
    }

    try {
      const res = await apiFetch<ImportBatch>("/api/import/batch", {
        method: "POST",
        body: formData,
      })
      setBatch(res)
      setSelectedFiles(new Set())
    } catch (e: any) {
      toast.error(e?.message || "上传失败，请重试")
    }
    setUploading(false)
  }

  async function handleAnalyze() {
    if (!batch) return
    setAnalyzing(true)
    toast.info("开始 AI 分析，正在并发处理文档...")

    const [res, err] = await apiTry<ImportBatch>(`/api/import/batch/${batch.id}/analyze`, {
      method: "POST",
    })
    if (res) {
      setBatch(res)
      const readyCount = res.files?.filter((f: any) => f.status === "ready").length || 0
      const errorCount = res.files?.filter((f: any) => f.status === "error").length || 0
      toast.success(`分析完成：${readyCount} 个成功，${errorCount} 个失败`)
    } else {
      toast.error(err?.message || "分析失败")
    }
    setAnalyzing(false)
  }

  async function handleApprove() {
    if (!batch || selectedFiles.size === 0) return
    setImporting(true)
    const [res, err] = await apiTry<ImportBatch>(`/api/import/batch/${batch.id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_ids: Array.from(selectedFiles) }),
    })
    if (res) {
      setBatch(res)
      setSelectedFiles(new Set())
      const importedCount = res.files?.filter((f: any) => f.status === "imported").length || selectedFiles.size
      toast.success(`成功导入 ${importedCount} 个文档`)
      // Offer to navigate to documents page
      if (confirm(`已导入 ${importedCount} 个文档。是否跳转到知识库查看？`)) {
        window.location.href = "/documents"
      }
    } else {
      toast.error(err?.message || "导入失败")
    }
    setImporting(false)
  }

  async function handleReject(fileId: number) {
    if (!batch) return
    const [res, err] = await apiTry<ImportFile>(`/api/import/file/${fileId}/reject`, {
      method: "POST",
    })
    if (res) {
      setBatch((prev) =>
        prev
          ? {
              ...prev,
              files: prev.files.map((f) => (f.id === fileId ? res : f)),
            }
          : prev
      )
      setSelectedFiles((prev) => {
        const next = new Set(prev)
        next.delete(fileId)
        return next
      })
    } else {
      toast.error(err?.message || "拒绝失败")
    }
  }

  function toggleSelect(fileId: number) {
    setSelectedFiles((prev) => {
      const next = new Set(prev)
      if (next.has(fileId)) next.delete(fileId)
      else next.add(fileId)
      return next
    })
  }

  function selectAllReady() {
    if (!batch) return
    const readyIds = new Set(batch.files.filter((f) => f.status === "ready").map((f) => f.id))
    setSelectedFiles(readyIds)
  }

  const analysis = (file: ImportFile) => file.ai_analysis as Record<string, unknown> | null

  return (
    <>
      <header className="border-b px-6 py-4">
        <h1 className="text-lg font-semibold">批量导入</h1>
        <p className="text-xs text-muted-foreground mt-0.5">上传文件，AI 审核后导入到知识库</p>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Upload area */}
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              dragOver ? "border-blue-400 bg-blue-50" : "border-muted"
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files) }}
          >
            <Upload className="h-8 w-8 mx-auto mb-3 text-muted-foreground" />
            <p className="text-sm font-medium mb-1">拖拽文件到此处，或点击选择</p>
            <p className="text-xs text-muted-foreground mb-3">支持 .md .docx .pdf .txt .tex 格式，单文件最大 10MB</p>
            <label>
              <input
                type="file"
                multiple
                accept=".md,.txt,.tex,.latex,.docx,.pdf"
                className="hidden"
                onChange={(e) => handleUpload(e.target.files)}
                disabled={uploading}
              />
              <Button
                variant="outline"
                size="sm"
                className="cursor-pointer"
                disabled={uploading}
                onClick={() => document.querySelector<HTMLInputElement>('input[type="file"]')?.click()}
              >
                {uploading ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : null}
                {uploading ? "上传中..." : "选择文件"}
              </Button>
            </label>
          </div>

          {/* Batch info + actions */}
          {batch && (
            <>
              <div className="flex items-center justify-between">
                <div className="text-sm">
                  <span className="font-medium">{batch.total_files} 个文件</span>
                  <span className="text-muted-foreground ml-2">
                    · 已处理 {batch.processed_count} · 状态: {
                      batch.status === "pending" ? "待分析" :
                      batch.status === "processing" ? "处理中" :
                      batch.status === "review" ? "待审核" :
                      batch.status === "completed" ? "已完成" : batch.status
                    }
                  </span>
                </div>
                <div className="flex gap-2">
                  {(batch.status === "pending" || batch.status === "review") && (
                    <Button size="sm" onClick={handleAnalyze} disabled={analyzing}>
                      {analyzing ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 mr-1.5" />}
                      AI 分析
                    </Button>
                  )}
                  {selectedFiles.size > 0 && (
                    <Button size="sm" onClick={handleApprove} disabled={importing}>
                      {importing ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Check className="h-3.5 w-3.5 mr-1.5" />}
                      批准导入 ({selectedFiles.size})
                    </Button>
                  )}
                </div>
              </div>

              {/* Select all ready */}
              <div className="flex items-center gap-2">
                <button
                  onClick={selectAllReady}
                  className="text-xs text-blue-600 hover:underline"
                >
                  全选待审核
                </button>
                <button
                  onClick={() => setSelectedFiles(new Set())}
                  className="text-xs text-muted-foreground hover:underline"
                >
                  取消全选
                </button>
              </div>

              {/* File cards */}
              <div className="space-y-2">
                {batch.files.map((file) => {
                  const expanded = expandedFile === file.id
                  const ai = analysis(file)
                  const isSelected = selectedFiles.has(file.id)

                  return (
                    <div key={file.id} className="border rounded-lg overflow-hidden">
                      {/* File header */}
                      <div className="flex items-center gap-3 px-4 py-3 bg-muted/30">
                        {file.status === "ready" && (
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelect(file.id)}
                            className="h-4 w-4 rounded"
                          />
                        )}
                        <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                        <span className="text-sm font-medium flex-1 truncate">{file.filename}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_BADGE[file.status] || ""}`}>
                          {STATUS_LABEL[file.status] || file.status}
                        </span>
                        {ai && (
                          <span className="text-xs text-muted-foreground">
                            质量: {String(ai.quality_score ?? "")}
                          </span>
                        )}
                        <button
                          onClick={() => setExpandedFile(expanded ? null : file.id)}
                          className="text-muted-foreground hover:text-foreground"
                        >
                          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </button>
                      </div>

                      {/* Expanded content */}
                      {expanded && (
                        <div className="px-4 py-3 space-y-3 border-t">
                          {file.error_message && (
                            <div className="flex items-center gap-2 text-red-600 text-sm">
                              <AlertTriangle className="h-4 w-4" />
                              {file.error_message}
                            </div>
                          )}

                          {ai && (
                            <>
                              {/* AI suggestion title */}
                              <div>
                                <h4 className="text-xs font-medium text-muted-foreground mb-1">建议标题</h4>
                                <p className="text-sm font-medium">{String(ai.title || "")}</p>
                              </div>

                              {/* Summary */}
                              {ai.summary && (
                                <div>
                                  <h4 className="text-xs font-medium text-muted-foreground mb-1">摘要</h4>
                                  <p className="text-sm text-muted-foreground">{String(ai.summary)}</p>
                                </div>
                              )}

                              {/* Keywords */}
                              {Array.isArray(ai.keywords) && ai.keywords.length > 0 && (
                                <div>
                                  <h4 className="text-xs font-medium text-muted-foreground mb-1">关键词</h4>
                                  <div className="flex flex-wrap gap-1">
                                    {(ai.keywords as string[]).map((kw, i) => (
                                      <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">
                                        {kw}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Suggested tags */}
                              {Array.isArray(ai.suggested_tags) && ai.suggested_tags.length > 0 && (
                                <div>
                                  <h4 className="text-xs font-medium text-muted-foreground mb-1">建议标签</h4>
                                  <div className="flex flex-wrap gap-1">
                                    {(ai.suggested_tags as string[]).map((tag, i) => (
                                      <span key={i} className="flex items-center gap-0.5 px-2 py-0.5 bg-purple-50 text-purple-700 rounded text-xs">
                                        <Tag className="h-3 w-3" />
                                        {tag}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Suggested folder */}
                              {ai.suggested_folder && (
                                <div>
                                  <h4 className="text-xs font-medium text-muted-foreground mb-1">建议文件夹</h4>
                                  <span className="flex items-center gap-1 text-sm">
                                    <FolderOpen className="h-3.5 w-3.5 text-amber-600" />
                                    {String(ai.suggested_folder)}
                                  </span>
                                </div>
                              )}

                              {/* Issues */}
                              {Array.isArray(ai.issues) && ai.issues.length > 0 && (
                                <div>
                                  <h4 className="text-xs font-medium text-muted-foreground mb-1">问题</h4>
                                  <div className="space-y-1">
                                    {(ai.issues as Array<Record<string, string>>).map((issue, i) => (
                                      <div key={i} className="flex items-start gap-2 text-xs">
                                        <AlertTriangle className={`h-3.5 w-3.5 mt-0.5 shrink-0 ${
                                          issue.severity === "high" ? "text-red-500" :
                                          issue.severity === "medium" ? "text-amber-500" : "text-gray-400"
                                        }`} />
                                        <span>{issue.description}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Fixes */}
                              {Array.isArray(ai.fixes) && ai.fixes.length > 0 && (
                                <div>
                                  <h4 className="text-xs font-medium text-muted-foreground mb-1">修复建议</h4>
                                  <div className="space-y-1">
                                    {(ai.fixes as Array<Record<string, unknown>>).map((fix, i) => (
                                      <div key={i} className="text-xs text-muted-foreground">
                                        · {String(fix.description || "")}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </>
                          )}

                          {/* Actions */}
                          {file.status === "ready" && (
                            <div className="flex gap-2 pt-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  toggleSelect(file.id)
                                }}
                              >
                                {isSelected ? "取消选择" : "选择"}
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => handleReject(file.id)}
                              >
                                <X className="h-3.5 w-3.5 mr-1" />
                                拒绝
                              </Button>
                            </div>
                          )}

                          {file.status === "imported" && file.imported_document_id && (
                            <a
                              href={`/editor/${file.imported_document_id}`}
                              className="text-xs text-blue-600 hover:underline"
                            >
                              查看已导入文档 →
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
