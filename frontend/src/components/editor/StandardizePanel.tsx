"use client"

import { useState } from "react"
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { apiTry } from "@/lib/api-client"
import {
  Sparkles, Loader2, Tag, FolderOpen, BarChart3,
  CheckCircle2, AlertTriangle, X,
} from "lucide-react"

interface StandardizeResult {
  structured_summary: string
  keywords: string[]
  categories: string[]
  content_suggestions: {
    missing_sections?: string[]
    improvements?: string[]
    structure_score?: number
  }
  metadata: {
    difficulty?: string
    audience?: string
    document_type?: string
  }
}

interface StandardizePanelProps {
  documentId: number
  open: boolean
  onClose: () => void
  onApplied: () => void
}

export function StandardizePanel({ documentId, open, onClose, onApplied }: StandardizePanelProps) {
  const [result, setResult] = useState<StandardizeResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [classifying, setClassifying] = useState(false)
  const [appliedKeywords, setAppliedKeywords] = useState<Set<string>>(new Set())
  const [error, setError] = useState("")

  async function handleAnalyze() {
    setLoading(true)
    setError("")
    setResult(null)
    const [res, err] = await apiTry<StandardizeResult>("/api/ai/standardize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_id: documentId }),
    })
    if (res) {
      setResult(res)
    } else {
      setError(err?.message || "分析失败")
    }
    setLoading(false)
  }

  async function handleAutoClassify() {
    setClassifying(true)
    setError("")
    const [res, err] = await apiTry<{ message: string; keywords: string[] }>(
      "/api/ai/auto-classify",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: documentId }),
      }
    )
    if (res) {
      setAppliedKeywords(new Set(res.keywords))
      onApplied()
    } else {
      setError(err?.message || "自动分类失败")
    }
    setClassifying(false)
  }

  const score = result?.content_suggestions?.structure_score ?? 0

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-500" />
            AI 标准化
          </SheetTitle>
          <SheetDescription>AI 分析文档并建议关键词、分类和内容优化</SheetDescription>
        </SheetHeader>

        <div className="px-4 space-y-4">
          {/* Action buttons */}
          <div className="flex gap-2">
            <Button size="sm" onClick={handleAnalyze} disabled={loading || classifying}>
              {loading ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 mr-1.5" />}
              AI 分析
            </Button>
            <Button size="sm" variant="outline" onClick={handleAutoClassify} disabled={loading || classifying}>
              {classifying ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Tag className="h-3.5 w-3.5 mr-1.5" />}
              自动分类
            </Button>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red-600 text-sm">
              <AlertTriangle className="h-4 w-4" />
              {error}
            </div>
          )}

          {result && (
            <>
              {/* Structure score */}
              <div className="flex items-center gap-3">
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
                <div className="flex-1">
                  <div className="flex justify-between text-xs mb-1">
                    <span>结构评分</span>
                    <span className="font-medium">{score}/100</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        score >= 80 ? "bg-green-500" : score >= 50 ? "bg-amber-500" : "bg-red-500"
                      }`}
                      style={{ width: `${score}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Structured summary */}
              {result.structured_summary && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-1">结构化摘要</h4>
                  <p className="text-sm">{result.structured_summary}</p>
                </div>
              )}

              {/* Keywords */}
              {result.keywords.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-1">关键词</h4>
                  <div className="flex flex-wrap gap-1">
                    {result.keywords.map((kw, i) => (
                      <span
                        key={i}
                        className={`px-2 py-0.5 rounded text-xs ${
                          appliedKeywords.has(kw)
                            ? "bg-green-100 text-green-700"
                            : "bg-blue-50 text-blue-700"
                        }`}
                      >
                        {appliedKeywords.has(kw) && <CheckCircle2 className="inline h-3 w-3 mr-0.5" />}
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Categories */}
              {result.categories.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-1">分类</h4>
                  <div className="flex flex-wrap gap-1">
                    {result.categories.map((cat, i) => (
                      <span key={i} className="px-2 py-0.5 bg-purple-50 text-purple-700 rounded text-xs">
                        {cat}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Metadata */}
              {result.metadata && (
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {result.metadata.difficulty && (
                    <div>
                      <span className="text-muted-foreground">难度: </span>
                      <span className="font-medium">
                        {result.metadata.difficulty === "beginner" ? "入门" :
                         result.metadata.difficulty === "intermediate" ? "中级" : "高级"}
                      </span>
                    </div>
                  )}
                  {result.metadata.document_type && (
                    <div>
                      <span className="text-muted-foreground">类型: </span>
                      <span className="font-medium">{result.metadata.document_type}</span>
                    </div>
                  )}
                  {result.metadata.audience && (
                    <div className="col-span-2">
                      <span className="text-muted-foreground">受众: </span>
                      <span className="font-medium">{result.metadata.audience}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Content suggestions */}
              {result.content_suggestions && (
                <>
                  {result.content_suggestions.missing_sections && result.content_suggestions.missing_sections.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-muted-foreground mb-1">缺少的章节</h4>
                      <div className="space-y-0.5">
                        {result.content_suggestions.missing_sections.map((s, i) => (
                          <div key={i} className="flex items-center gap-1.5 text-xs text-amber-600">
                            <AlertTriangle className="h-3 w-3" />
                            {s}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {result.content_suggestions.improvements && result.content_suggestions.improvements.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-muted-foreground mb-1">改进建议</h4>
                      <div className="space-y-0.5">
                        {result.content_suggestions.improvements.map((s, i) => (
                          <div key={i} className="text-xs text-muted-foreground">
                            · {s}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
