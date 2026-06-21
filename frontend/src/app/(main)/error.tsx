"use client"

import { Button } from "@/components/ui/button"
import { AlertCircle } from "lucide-react"

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full py-20 px-6 text-center">
      <div className="p-3 rounded-full bg-red-100 dark:bg-red-950 mb-4">
        <AlertCircle className="h-8 w-8 text-red-500" />
      </div>
      <h2 className="text-lg font-semibold mb-2">出了一些问题</h2>
      <p className="text-sm text-muted-foreground mb-6 max-w-sm">
        页面加载时发生了意外错误。请尝试重新加载，如果问题持续存在，请联系管理员。
      </p>
      <div className="flex gap-3">
        <Button variant="outline" onClick={() => window.location.href = "/documents"}>
          返回首页
        </Button>
        <Button onClick={reset}>重试</Button>
      </div>
      {error.digest && (
        <p className="text-xs text-muted-foreground mt-6 font-mono">
          错误 ID: {error.digest}
        </p>
      )}
    </div>
  )
}
