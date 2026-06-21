import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function POST(request: NextRequest) {
  try {
    const token = request.cookies.get("access_token")?.value
    if (!token) {
      return NextResponse.json({ detail: "未授权" }, { status: 401 })
    }

    // Forward multipart form data as-is
    const formData = await request.formData()
    const res = await fetch(`${BACKEND_URL}/api/documents/import`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
      },
      body: formData,
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}
