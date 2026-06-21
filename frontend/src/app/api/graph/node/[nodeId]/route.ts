import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ nodeId: string }> }
) {
  const token = request.cookies.get("access_token")?.value
  if (!token) return NextResponse.json({ detail: "未授权" }, { status: 401 })
  try {
    const { nodeId } = await params
    const res = await fetch(`${BACKEND_URL}/api/graph/node/${nodeId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    })
    return NextResponse.json(await res.json(), { status: res.status })
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}
