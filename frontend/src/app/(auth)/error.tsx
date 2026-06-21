"use client"

import { Button } from "@/components/ui/button"
import { AlertCircle } from "lucide-react"

export default function AuthError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-slate-50 to-indigo-50 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950">
      <div className="text-center px-6">
        <div className="flex justify-center mb-4">
          <div className="p-3 rounded-full bg-red-100 dark:bg-red-950">
            <AlertCircle className="h-8 w-8 text-red-500" />
          </div>
        </div>
        <h2 className="text-lg font-semibold mb-2">登录页面出错</h2>
        <p className="text-sm text-muted-foreground mb-6 max-w-sm mx-auto">
          登录页面加载时发生了意外错误。请尝试刷新页面。
        </p>
        <div className="flex gap-3 justify-center">
          <Button variant="outline" onClick={() => window.location.href = "/login"}>
            刷新页面
          </Button>
          <Button onClick={reset}>重试</Button>
        </div>
        {error.digest && (
          <p className="text-xs text-muted-foreground mt-6 font-mono">
            错误 ID: {error.digest}
          </p>
        )}
      </div>
    </div>
  )
}
