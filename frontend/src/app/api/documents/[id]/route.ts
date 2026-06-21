import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

async function proxyWithAuth(request: NextRequest, id: string, options: RequestInit = {}) {
  const token = request.cookies.get("access_token")?.value
  if (!token) {
    return NextResponse.json({ message: "未授权，请重新登录" }, { status: 401 })
  }

  try {
    const response = await fetch(`${BACKEND_URL}/api/documents/${id}`, {
      ...options,
      headers: {
        ...options.headers,
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    })

    const data = await response.json().catch(() => ({ message: "后端返回了无效的响应" }))
    return NextResponse.json(data, { status: response.status })
  } catch {
    return NextResponse.json({ message: "后端服务不可用" }, { status: 503 })
  }
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return proxyWithAuth(request, id)
}

export async function PUT(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  try {
    const body = await request.json()
    return proxyWithAuth(request, id, {
      method: "PUT",
      body: JSON.stringify(body),
    })
  } catch {
    return NextResponse.json({ message: "请求格式错误" }, { status: 400 })
  }
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return proxyWithAuth(request, id, { method: "DELETE" })
}
