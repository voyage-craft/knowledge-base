/**
 * Shared server-side proxy utility for Next.js API routes.
 * Eliminates code duplication across all proxy routes.
 */
import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

interface ProxyOptions {
  method?: string
  body?: unknown
  formData?: FormData
  headers?: Record<string, string>
}

/**
 * Proxy a request to the backend with authentication.
 * Handles token extraction, error forwarding, and network failures.
 */
export async function proxyRequest(
  request: NextRequest,
  backendPath: string,
  options: ProxyOptions = {},
): Promise<NextResponse> {
  const token = request.cookies.get("access_token")?.value
  if (!token) {
    return NextResponse.json({ message: "未授权，请重新登录" }, { status: 401 })
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    ...options.headers,
  }

  const init: RequestInit = {
    method: options.method || "GET",
    headers,
  }

  if (options.formData) {
    init.body = options.formData
    // Don't set Content-Type for FormData — browser sets boundary automatically
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json"
    init.body = JSON.stringify(options.body)
  }

  try {
    const response = await fetch(`${BACKEND_URL}${backendPath}`, init)

    // Handle 204 No Content
    if (response.status === 204) {
      return new NextResponse(null, { status: 204 })
    }

    const contentType = response.headers.get("content-type") || ""

    // Handle non-JSON responses (streaming, etc.)
    if (!contentType.includes("application/json")) {
      const text = await response.text()
      return new NextResponse(text, {
        status: response.status,
        headers: { "content-type": contentType },
      })
    }

    const data = await response.json().catch(() => ({
      message: "后端返回了无效的响应",
    }))

    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error("[Proxy Error]", backendPath, error)
    return NextResponse.json({ message: "后端服务不可用" }, { status: 503 })
  }
}
