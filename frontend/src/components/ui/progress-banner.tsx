"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Loader2, CheckCircle2, XCircle, X } from "lucide-react"
import { apiTry } from "@/lib/api-client"

interface ProgressBannerProps {
  /** URL to poll for status */
  pollUrl: string
  /** Polling interval in ms */
  interval?: number
  /** Timeout in ms */
  timeout?: number
  /** Step labels for progress display */
  steps?: string[]
  /** Called when complete */
  onComplete?: (data: any) => void
  /** Called on error */
  onError?: (error: string) => void
  /** Dismiss the banner */
  onDismiss?: () => void
}

interface PollStatus {
  status: string
  current?: number
  total?: number
  message?: string
  error?: string
}

/**
 * Reusable progress banner with polling.
 * Shows step-by-step progress with Chinese labels.
 */
export function ProgressBanner({
  pollUrl,
  interval = 2000,
  timeout = 300000,
  steps,
  onComplete,
  onError,
  onDismiss,
}: ProgressBannerProps) {
  const [status, setStatus] = useState<PollStatus>({ status: "starting" })
  const [elapsed, setElapsed] = useState(0)
  const pollRef = useRef<NodeJS.Timeout | null>(null)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)
  const startTimeRef = useRef(Date.now())
  const elapsedRef = useRef<NodeJS.Timeout | null>(null)

  // Store callbacks in refs to avoid restarting the polling effect
  // when parent re-renders with new callback references
  const onCompleteRef = useRef(onComplete)
  const onErrorRef = useRef(onError)
  useEffect(() => { onCompleteRef.current = onComplete }, [onComplete])
  useEffect(() => { onErrorRef.current = onError }, [onError])

  const cleanup = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null }
    if (elapsedRef.current) { clearInterval(elapsedRef.current); elapsedRef.current = null }
  }, [])

  useEffect(() => {
    startTimeRef.current = Date.now()

    // Elapsed timer
    elapsedRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000))
    }, 1000)

    // Poll
    pollRef.current = setInterval(async () => {
      const [data] = await apiTry<PollStatus>(pollUrl)
      if (data) {
        setStatus(data)
        if (data.status === "complete" || data.status === "completed") {
          cleanup()
          onCompleteRef.current?.(data)
        } else if (data.status === "failed" || data.status === "error") {
          cleanup()
          onErrorRef.current?.(data.error || "执行失败")
        }
      }
    }, interval)

    // Timeout
    timeoutRef.current = setTimeout(() => {
      cleanup()
      onErrorRef.current?.("执行超时")
    }, timeout)

    return cleanup
  }, [pollUrl, interval, timeout, cleanup])

  const formatTime = (s: number) => {
    if (s < 60) return `${s}秒`
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}分${sec}秒`
  }

  const isRunning = status.status === "running" || status.status === "building" || status.status === "starting"
  const isComplete = status.status === "complete" || status.status === "completed"
  const isFailed = status.status === "failed" || status.status === "error"

  // Determine current step from progress
  const current = status.current || 0
  const total = status.total || 0
  const progress = total > 0 ? Math.round((current / total) * 100) : 0

  // Find current step label
  const currentStep = steps && steps.length > 0
    ? steps[Math.min(current, steps.length - 1)]
    : total > 0
      ? `处理中 ${current}/${total}`
      : status.message || "执行中..."

  return (
    <div className={`border-b px-6 py-3 flex items-center gap-3 text-sm ${
      isComplete
        ? "bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-300"
        : isFailed
          ? "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300"
          : "bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300"
    }`}>
      {isRunning && <Loader2 className="h-4 w-4 animate-spin shrink-0" />}
      {isComplete && <CheckCircle2 className="h-4 w-4 shrink-0" />}
      {isFailed && <XCircle className="h-4 w-4 shrink-0" />}

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium">{currentStep}</span>
          {isRunning && total > 0 && (
            <span className="text-xs opacity-70">{progress}%</span>
          )}
        </div>
        {isRunning && total > 0 && (
          <div className="mt-1 h-1.5 bg-black/10 dark:bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-current rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>

      <span className="text-xs opacity-70 shrink-0">{formatTime(elapsed)}</span>

      {(isComplete || isFailed) && onDismiss && (
        <button onClick={onDismiss} className="p-0.5 hover:bg-black/10 dark:hover:bg-white/10 rounded">
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}
