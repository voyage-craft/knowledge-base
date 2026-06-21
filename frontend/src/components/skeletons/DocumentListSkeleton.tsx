export function DocumentListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="grid gap-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-3 rounded-lg border animate-pulse">
          <div className="p-2 rounded-lg bg-muted shrink-0">
            <div className="h-5 w-5 rounded bg-muted-foreground/10" />
          </div>
          <div className="flex-1 min-w-0 space-y-2">
            <div className="h-4 bg-muted rounded w-2/3" />
            <div className="h-3 bg-muted rounded w-1/3" />
          </div>
          <div className="h-5 w-12 bg-muted rounded-full" />
          <div className="h-8 w-8 rounded bg-muted" />
        </div>
      ))}
    </div>
  )
}
