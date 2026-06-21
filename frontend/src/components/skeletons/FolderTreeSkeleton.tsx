export function FolderTreeSkeleton() {
  return (
    <div className="w-56 border-r bg-muted/30 flex flex-col shrink-0 animate-pulse">
      <div className="flex items-center justify-between px-3 py-3 border-b">
        <div className="h-4 w-12 bg-muted rounded" />
        <div className="h-7 w-7 rounded bg-muted" />
      </div>
      <div className="px-1.5 py-2 space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2 py-1.5 px-2">
            <div className="h-4 w-4 rounded bg-muted" />
            <div className="h-3 bg-muted rounded flex-1" />
          </div>
        ))}
      </div>
    </div>
  )
}
