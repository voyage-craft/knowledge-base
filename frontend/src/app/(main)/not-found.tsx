"use client"

import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { FileQuestion } from "lucide-react"

export default function NotFound() {
  const router = useRouter()

  return (
    <div className="flex flex-col items-center justify-center h-full py-20 px-6 text-center">
      <div className="p-3 rounded-full bg-slate-100 dark:bg-slate-800 mb-4">
        <FileQuestion className="h-8 w-8 text-slate-500" />
      </div>
      <h2 className="text-lg font-semibold mb-2">页面不存在</h2>
      <p className="text-sm text-muted-foreground mb-6">
        你访问的页面不存在或已被移除。
      </p>
      <Button onClick={() => router.push("/documents")}>返回首页</Button>
    </div>
  )
}
