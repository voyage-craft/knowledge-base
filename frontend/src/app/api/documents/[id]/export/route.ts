import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = request.cookies.get("access_token")?.value
  if (!token) {
    return NextResponse.json({ detail: "未授权" }, { status: 401 })
  }
  try {
    const { id } = await params
    const format = request.nextUrl.searchParams.get("format") || "markdown"
    const res = await fetch(`${BACKEND_URL}/api/documents/${id}/export?format=${format}`, {
      headers: { "Authorization": `Bearer ${token}` },
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({ detail: "导出失败" }))
      return NextResponse.json(data, { status: res.status })
    }
    // Forward the file content directly
    const contentType = res.headers.get("content-type") || "application/octet-stream"
    const contentDisposition = res.headers.get("content-disposition") || ""
    const headers: Record<string, string> = { "Content-Type": contentType }
    if (contentDisposition) headers["Content-Disposition"] = contentDisposition
    const buffer = await res.arrayBuffer()
    return new NextResponse(buffer, { status: 200, headers })
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}
