/**
 * Unified API client with automatic auth redirect, error handling,
 * AbortController support, and GET request deduplication.
 */

// Guard flag to prevent multiple concurrent 401 redirects
let _redirecting = false

function handle401() {
  if (typeof window !== "undefined" && !_redirecting) {
    _redirecting = true
    setTimeout(() => { _redirecting = false }, 3000)
    window.location.href = "/login"
  }
}

/**
 * Extract a human-readable error message from a backend response body.
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

// ── GET request deduplication cache ──

interface CacheEntry<T> {
  promise: Promise<T>
  timestamp: number
}

const _getCache = new Map<string, CacheEntry<any>>()
const GET_DEDUP_TTL = 5000 // 5 seconds

function getCachedGet<T>(url: string): Promise<T> | null {
  const entry = _getCache.get(url)
  if (entry && Date.now() - entry.timestamp < GET_DEDUP_TTL) {
    return entry.promise
  }
  _getCache.delete(url)
  return null
}

function setCachedGet<T>(url: string, promise: Promise<T>): void {
  _getCache.set(url, { promise, timestamp: Date.now() })
  // Clean up stale entries periodically
  if (_getCache.size > 50) {
    const now = Date.now()
    for (const [key, entry] of _getCache) {
      if (now - entry.timestamp > GET_DEDUP_TTL * 2) {
        _getCache.delete(key)
      }
    }
  }
}

/**
 * Invalidate the GET deduplication cache (call after mutations).
 */
export function invalidateGetCache(urlPrefix?: string) {
  if (!urlPrefix) {
    _getCache.clear()
    return
  }
  for (const key of _getCache.keys()) {
    if (key.startsWith(urlPrefix)) {
      _getCache.delete(key)
    }
  }
}

/**
 * Fetch with retry for transient failures (GET requests only).
 * Retries on 5xx responses and network errors, up to 2 times with 500ms delay.
 */
async function apiFetchWithRetry(url: string, options?: RequestInit, retries = 2): Promise<Response> {
  try {
    const res = await fetch(url, options)
    if (res.status >= 500 && retries > 0) {
      await new Promise(r => setTimeout(r, 500))
      return apiFetchWithRetry(url, options, retries - 1)
    }
    return res
  } catch (err) {
    if (retries > 0) {
      await new Promise(r => setTimeout(r, 500))
      return apiFetchWithRetry(url, options, retries - 1)
    }
    throw err
  }
}

/**
 * Main API fetch with AbortController support and GET deduplication.
 */
export async function apiFetch<T = unknown>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const isFormData = options.body instanceof FormData
  const isGet = !options.method || options.method === "GET"

  // GET deduplication: return cached promise if same URL within TTL
  if (isGet && !options.signal) {
    const cached = getCachedGet<T>(url)
    if (cached) return cached
  }

  // Invalidate GET cache on mutations
  if (!isGet) {
    invalidateGetCache()
  }

  const doFetch = async (): Promise<T> => {
    const res = await (isGet ? apiFetchWithRetry : fetch)(url, {
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

    const contentType = res.headers.get("content-type") || ""
    if (res.status === 204 || !contentType.includes("application/json")) {
      return undefined as T
    }

    return res.json()
  }

  if (isGet && !options.signal) {
    const promise = doFetch()
    setCachedGet(url, promise)
    // Remove from cache on error so retries work
    promise.catch(() => _getCache.delete(url))
    return promise
  }

  return doFetch()
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
