"use client"

import { memo, useState, useCallback } from "react"
import { Bot, User, Copy, Check } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"

interface ChatBubbleProps {
  id: string
  role: "user" | "assistant"
  textParts: string[]
}

/**
 * Individual chat message bubble.
 * Memoised so only the streaming (last) message re-renders on each token.
 */
export const ChatBubble = memo(function ChatBubble({ id, role, textParts }: ChatBubbleProps) {
  const [copied, setCopied] = useState(false)
  const isAssistant = role === "assistant"

  const handleCopy = useCallback(() => {
    const text = textParts.join("")
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [textParts])

  return (
    <div className={`flex gap-3 ${role === "user" ? "justify-end" : ""}`}>
      {isAssistant && (
        <div className="p-2 rounded-full bg-blue-100 dark:bg-blue-900 shrink-0 self-start">
          <Bot className="h-4 w-4 text-blue-600 dark:text-blue-400" />
        </div>
      )}
      <Card className={`max-w-[80%] ${role === "user" ? "bg-blue-50 dark:bg-blue-950" : ""}`}>
        <CardContent className="p-3 prose prose-sm max-w-none dark:prose-invert relative group">
          {textParts.map((text, i) => (
            <span key={i}>{text}</span>
          ))}
          {/* Copy button — visible on hover for assistant messages */}
          {isAssistant && textParts.length > 0 && (
            <button
              onClick={handleCopy}
              className="absolute top-1 right-1 p-1 rounded opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity text-muted-foreground"
              title="复制内容"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-green-500" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
          )}
        </CardContent>
      </Card>
      {role === "user" && (
        <div className="p-2 rounded-full bg-slate-100 dark:bg-slate-800 shrink-0 self-start">
          <User className="h-4 w-4" />
        </div>
      )}
    </div>
  )
})

/**
 * Typing indicator: three bouncing dots shown while waiting for AI response.
 */
export function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="p-2 rounded-full bg-blue-100 dark:bg-blue-900 shrink-0 self-start">
        <Bot className="h-4 w-4 text-blue-600 dark:text-blue-400" />
      </div>
      <Card>
        <CardContent className="p-3 flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:0ms]" />
          <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:150ms]" />
          <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:300ms]" />
        </CardContent>
      </Card>
    </div>
  )
}
