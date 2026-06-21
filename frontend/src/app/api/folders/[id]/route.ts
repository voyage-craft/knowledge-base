import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

async function proxyWithAuth(request: NextRequest, id: string, options: RequestInit = {}) {
  const token = request.cookies.get("access_token")?.value
  if (!token) {
    return NextResponse.json({ detail: "未授权" }, { status: 401 })
  }
  const response = await fetch(`${BACKEND_URL}/api/folders/${id}`, {
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

export async function PUT(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params
    const body = await request.json()
    return await proxyWithAuth(request, id, {
      method: "PUT",
      body: JSON.stringify(body),
    })
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params
    return await proxyWithAuth(request, id, { method: "DELETE" })
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}
