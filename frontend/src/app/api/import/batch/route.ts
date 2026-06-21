import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function POST(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value
  if (!token) return NextResponse.json({ detail: "未授权" }, { status: 401 })
  try {
    // Forward raw body as FormData for file uploads
    const formData = await request.formData()
    const res = await fetch(`${BACKEND_URL}/api/import/batch`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    })
    return NextResponse.json(await res.json(), { status: res.status })
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}

export async function GET(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value
  if (!token) return NextResponse.json({ detail: "未授权" }, { status: 401 })
  try {
    const url = new URL(request.url)
    const res = await fetch(`${BACKEND_URL}/api/import/batch?${url.searchParams}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    return NextResponse.json(await res.json(), { status: res.status })
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}
