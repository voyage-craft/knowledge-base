import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

async function proxy(request: NextRequest, path: string[]) {
  const token = request.cookies.get("access_token")?.value
  if (!token) {
    return NextResponse.json({ detail: "未授权" }, { status: 401 })
  }

  const urlPath = path.join("/")
  const searchParams = request.nextUrl.searchParams.toString()
  const url = `${BACKEND_URL}/api/rag/${urlPath}${searchParams ? `?${searchParams}` : ""}`

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  }

  const init: RequestInit = {
    method: request.method,
    headers,
  }

  if (request.method !== "GET" && request.method !== "DELETE") {
    try {
      const body = await request.json()
      init.body = JSON.stringify(body)
    } catch {
      // no body
    }
  }

  try {
    const res = await fetch(url, init)
    // Handle 204 No Content
    if (res.status === 204) {
      return new NextResponse(null, { status: 204 })
    }
    const contentType = res.headers.get("content-type") || ""
    if (contentType.includes("application/json")) {
      const data = await res.json()
      return NextResponse.json(data, { status: res.status })
    }
    const text = await res.text()
    return new NextResponse(text, { status: res.status })
  } catch {
    return NextResponse.json({ detail: "后端服务不可用" }, { status: 503 })
  }
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(request, path)
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(request, path)
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(request, path)
}
