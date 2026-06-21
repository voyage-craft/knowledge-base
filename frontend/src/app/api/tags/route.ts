import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

async function proxyWithAuth(request: NextRequest, path: string, options: RequestInit = {}) {
  const token = request.cookies.get("access_token")?.value
  if (!token) {
    return NextResponse.json({ detail: "未授权" }, { status: 401 })
  }
  const response = await fetch(`${BACKEND_URL}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  })
  const data = await response.json()
  return NextResponse.json(data, { status: response.status })
}

export async function GET(request: NextRequest) {
  try {
    return await proxyWithAuth(request, "/api/tags")
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    return await proxyWithAuth(request, "/api/tags", {
      method: "POST",
      body: JSON.stringify(body),
    })
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}
