/**
 * Unified API client with automatic auth redirect and error handling.
 */

// Guard flag to prevent multiple concurrent 401 redirects
let _redirecting = false

function handle401() {
  if (typeof window !== "undefined" && !_redirecting) {
    _redirecting = true
    // Reset after a short delay to allow future redirects after re-login
    setTimeout(() => { _redirecting = false }, 3000)
    window.location.href = "/login"
  }
}

/**
 * Extract a human-readable error message from a backend response body.
 * Handles both old format ({detail: "..."}) and new format ({message: "..."}).
 */
function extractError(body: any, status: number): string {
  if (!body || typeof body !== "object") return `请求失败 (${status})`
  if (typeof body.message === "string" && body.message) return body.message
  if (typeof body.detail === "string" && body.detail) return body.detail
  if (Array.isArray(body.detail)) {
    return body.detail.map((e: any) => e.msg || e.message || String(e)).join("; ")
  }
  return `请求失败 (${status})`
}

export async function apiFetch<T = unknown>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const isFormData = options.body instanceof FormData

  const res = await fetch(url, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  })

  if (res.status === 401) {
    handle401()
    throw new Error("未授权，请重新登录")
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(extractError(body, res.status))
  }

  // Handle 204 No Content or non-JSON responses
  const contentType = res.headers.get("content-type") || ""
  if (res.status === 204 || !contentType.includes("application/json")) {
    return undefined as T
  }

  return res.json()
}

/**
 * Fetch API and return blob response (for file downloads).
 */
export async function apiFetchBlob(
  url: string,
): Promise<{ blob: Blob; headers: Headers }> {
  const res = await fetch(url)

  if (res.status === 401) {
    handle401()
    throw new Error("未授权，请重新登录")
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body ? extractError(body, res.status) : `请求失败 (${res.status})`)
  }

  const blob = await res.blob()
  return { blob, headers: res.headers }
}

/**
 * Fire-and-forget API call that returns [data, error] tuple.
 */
export async function apiTry<T = unknown>(
  url: string,
  options?: RequestInit,
): Promise<[T, null] | [null, Error]> {
  try {
    const data = await apiFetch<T>(url, options)
    return [data, null]
  } catch (err) {
    return [null, err instanceof Error ? err : new Error(String(err))]
  }
}
