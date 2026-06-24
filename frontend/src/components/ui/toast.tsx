"use client"

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { X, CheckCircle, AlertCircle, Info } from "lucide-react"

// ── Types ──

type ToastVariant = "success" | "error" | "info"

interface Toast {
  id: number
  message: string
  variant: ToastVariant
  duration: number
}

interface ToastContextValue {
  toast: (message: string, options?: { variant?: ToastVariant; duration?: number }) => void
  dismiss: (id: number) => void
}

// ── Context ──

const ToastContext = createContext<ToastContextValue | null>(null)

let _nextId = 1

// ── Provider ──

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback(
    (message: string, options?: { variant?: ToastVariant; duration?: number }) => {
      const id = _nextId++
      const variant = options?.variant ?? "info"
      const duration = options?.duration ?? 4000

      setToasts((prev) => [...prev.slice(-4), { id, message, variant, duration }])

      if (duration > 0) {
        setTimeout(() => dismiss(id), duration)
      }
    },
    [dismiss],
  )

  const value = useMemo(() => ({ toast, dismiss }), [toast, dismiss])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Toaster toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}

// ── Hook ──

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    // Fallback no-op when used outside provider (SSR safety)
    return {
      toast: () => {},
      dismiss: () => {},
    }
  }
  return ctx
}

// ── Toaster (renders toast stack) ──

const VARIANT_STYLES: Record<ToastVariant, string> = {
  success:
    "border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950 text-green-800 dark:text-green-200",
  error:
    "border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950 text-red-800 dark:text-red-200",
  info: "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200",
}

const VARIANT_ICONS: Record<ToastVariant, typeof CheckCircle> = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
}

function Toaster({
  toasts,
  onDismiss,
}: {
  toasts: Toast[]
  onDismiss: (id: number) => void
}) {
  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 max-w-sm pointer-events-none">
      {toasts.map((t) => {
        const Icon = VARIANT_ICONS[t.variant]
        return (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-2.5 px-4 py-3 rounded-lg border shadow-lg animate-in slide-in-from-right-2 fade-in duration-200 ${VARIANT_STYLES[t.variant]}`}
          >
            <Icon className="h-4 w-4 mt-0.5 shrink-0 opacity-70" />
            <p className="text-sm flex-1 leading-snug">{t.message}</p>
            <button
              onClick={() => onDismiss(t.id)}
              className="shrink-0 opacity-50 hover:opacity-100 transition-opacity"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
