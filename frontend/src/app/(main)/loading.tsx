import { Loader2 } from "lucide-react"

export default function MainLoading() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">加载中...</p>
      </div>
    </div>
  )
}
