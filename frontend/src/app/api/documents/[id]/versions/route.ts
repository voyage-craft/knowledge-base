import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = request.cookies.get("access_token")?.value
  if (!token) {
    return NextResponse.json({ detail: "未授权" }, { status: 401 })
  }
  try {
    const { id } = await params
    const res = await fetch(`${BACKEND_URL}/api/documents/${id}/versions`, {
      headers: { "Authorization": `Bearer ${token}` },
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}
