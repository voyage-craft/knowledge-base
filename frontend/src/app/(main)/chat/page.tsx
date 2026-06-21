"use client"

import { useState, useMemo, useEffect, useRef, FormEvent, ChangeEvent, useCallback } from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Send, Bot, User, FileText, X, Search, ArrowDown, AlertCircle } from "lucide-react"

interface RAGResult {
  document_id: number
  document_title: string
  chunk_index: number
  chunk_text: string
  score: number
}

export default function ChatPage() {
  const [chatInput, setChatInput] = useState("")
  const [ragResults, setRagResults] = useState<RAGResult[]>([])
  const [ragLoading, setRagLoading] = useState(false)
  const [showRag, setShowRag] = useState(false)
  const [isNearBottom, setIsNearBottom] = useState(true)
  const [chatError, setChatError] = useState<string | null>(null)
  const transport = useMemo(() => new DefaultChatTransport({ api: "/api/ai/chat" }), [])
  const { messages, sendMessage, status, stop, error } = useChat({ transport })
  const scrollRef = useRef<HTMLDivElement>(null)

  const isStreaming = status === "streaming" || status === "submitted"

  // Show error when chat fails
  useEffect(() => {
    if (status === "error" || error) {
      setChatError(error?.message || "AI 服务暂时不可用，请检查配置或稍后重试")
    } else if (status === "ready" && chatError) {
      // Clear error when next message succeeds
      setChatError(null)
    }
  }, [status, error, chatError])

  // Track scroll position
  const checkScrollPosition = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 150
    setIsNearBottom(nearBottom)
  }, [])

  // Smart auto-scroll: only scroll to bottom if user is already near bottom
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    if (isNearBottom) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, isNearBottom])

  const scrollToBottom = useCallback(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
    }
  }, [])

  const searchRAG = useCallback(async (query: string) => {
    setRagLoading(true)
    try {
      const res = await fetch(`/api/rag/search?q=${encodeURIComponent(query)}&top_k=5&threshold=0.3`)
      if (res.ok) {
        const result = await res.json()
        setRagResults(result.results || [])
        if (result.results?.length > 0) setShowRag(true)
      } else {
        setRagResults([])
      }
    } catch {
      setRagResults([])
    }
    setRagLoading(false)
  }, [])

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!chatInput.trim() || isStreaming) return
    sendMessage({ text: chatInput })
    searchRAG(chatInput)
    setChatInput("")
    // Scroll to bottom when sending a message
    setTimeout(scrollToBottom, 100)
  }

  return (
    <>
      <header className="border-b px-6 py-4 shrink-0">
        <h1 className="text-lg font-semibold">AI 知识助手</h1>
        <p className="text-xs text-muted-foreground mt-0.5">基于你的知识库回答问题，支持 RAG 检索增强</p>
      </header>

      <div ref={scrollRef} onScroll={checkScrollPosition} className="flex-1 overflow-y-auto p-6 relative">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground py-20">
            <Bot className="h-16 w-16 mb-4 opacity-20" />
            <p className="text-base font-medium">可以问我关于文档的任何问题</p>
            <p className="text-sm mt-2 opacity-70">我能帮你查找、总结和组织信息</p>
          </div>
        ) : (
          <div className="space-y-4 max-w-3xl mx-auto">
            {messages.map(m => (
              <div key={m.id} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
                {m.role === "assistant" && (
                  <div className="p-2 rounded-full bg-blue-100 dark:bg-blue-900 shrink-0 self-start">
                    <Bot className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                  </div>
                )}
                <Card className={`max-w-[80%] ${m.role === "user" ? "bg-blue-50 dark:bg-blue-950" : ""}`}>
                  <CardContent className="p-3 prose prose-sm max-w-none dark:prose-invert">
                    {m.parts
                      .filter(p => p.type === "text")
                      .map((p, i) => <span key={i}>{p.text}</span>)}
                  </CardContent>
                </Card>
                {m.role === "user" && (
                  <div className="p-2 rounded-full bg-slate-100 dark:bg-slate-800 shrink-0 self-start">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Error message */}
        {chatError && (
          <div className="max-w-3xl mx-auto mt-4">
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <div>
                <p className="font-medium">AI 服务错误</p>
                <p className="text-xs mt-0.5 opacity-80">{chatError}</p>
                <p className="text-xs mt-1 opacity-60">请检查设置 → API 路由中的端点配置</p>
              </div>
            </div>
          </div>
        )}

        {/* Scroll to bottom button */}
        {!isNearBottom && messages.length > 0 && (
          <button
            onClick={scrollToBottom}
            className="sticky bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-background border shadow-md text-xs font-medium hover:bg-muted transition-colors"
          >
            <ArrowDown className="h-3 w-3" />
            <span>滚动到底部</span>
          </button>
        )}
      </div>

      {/* RAG References Panel */}
      {ragResults.length > 0 && showRag && (
        <div className="border-t px-6 py-3 bg-slate-50 dark:bg-slate-900 shrink-0">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <Search className="h-3 w-3" />
                <span>检索到 {ragResults.length} 个相关片段</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2"
                onClick={() => setShowRag(false)}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {ragResults.map((r, i) => (
                <div
                  key={`${r.document_id}-${r.chunk_index}`}
                  className="shrink-0 w-64 p-2 rounded-lg border bg-background text-xs"
                >
                  <div className="flex items-center gap-1 font-medium mb-1">
                    <FileText className="h-3 w-3 text-blue-500" />
                    <span className="truncate">{r.document_title}</span>
                  </div>
                  <p className="text-muted-foreground line-clamp-3">{r.chunk_text}</p>
                  <div className="mt-1 text-[10px] text-muted-foreground/70">
                    相关度: {(r.score * 100).toFixed(0)}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* RAG toggle when results exist but panel is hidden */}
      {ragResults.length > 0 && !showRag && (
        <div className="border-t px-6 py-1.5 shrink-0 flex justify-center">
          <button
            onClick={() => setShowRag(true)}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
          >
            <Search className="h-3 w-3" />
            查看 {ragResults.length} 个检索来源
          </button>
        </div>
      )}

      <div className="border-t p-4 shrink-0">
        <form onSubmit={onSubmit} className="flex gap-2 max-w-3xl mx-auto">
          <Input
            value={chatInput}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setChatInput(e.target.value)}
            placeholder="输入你的问题..."
            disabled={isStreaming}
            className="flex-1"
          />
          {isStreaming ? (
            <Button type="button" variant="outline" onClick={stop}>停止</Button>
          ) : (
            <Button type="submit">
              <Send className="h-4 w-4" />
            </Button>
          )}
        </form>
      </div>
    </>
  )
}
