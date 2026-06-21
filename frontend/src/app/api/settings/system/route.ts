import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

async function proxyWithAuth(request: NextRequest, method: string, body?: string) {
  const token = request.cookies.get("access_token")?.value
  if (!token) {
    return NextResponse.json({ detail: "未授权" }, { status: 401 })
  }

  const res = await fetch(`${BACKEND_URL}/api/settings/system`, {
    method,
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body,
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}

export async function GET(request: NextRequest) {
  try {
    return await proxyWithAuth(request, "GET")
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json()
    return await proxyWithAuth(request, "PUT", JSON.stringify(body))
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}
