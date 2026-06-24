import { NextRequest, NextResponse } from "next/server"
import { verifyToken } from "@/lib/auth"

const protectedRoutes = ["/editor", "/documents", "/chat", "/settings", "/graph", "/import", "/workflows", "/prompts"]
const authRoutes = ["/login"]

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

// Rate limiting for token refresh attempts
const refreshAttempts = new Map<string, { count: number; lastAttempt: number }>()
const MAX_REFRESH_ATTEMPTS = 5
const REFRESH_WINDOW_MS = 60000 // 1 minute

async function tryRefreshToken(refreshToken: string): Promise<{ access_token: string; refresh_token: string } | null> {
  // Rate limit refresh attempts to prevent abuse
  const now = Date.now()
  const key = refreshToken.slice(-10) // Use last 10 chars as key
  const attempts = refreshAttempts.get(key)

  if (attempts) {
    if (now - attempts.lastAttempt < REFRESH_WINDOW_MS && attempts.count >= MAX_REFRESH_ATTEMPTS) {
      console.warn("Rate limit exceeded for token refresh attempts")
      return null
    }
    // Reset if window has passed
    if (now - attempts.lastAttempt >= REFRESH_WINDOW_MS) {
      refreshAttempts.set(key, { count: 1, lastAttempt: now })
    } else {
      attempts.count++
      attempts.lastAttempt = now
    }
  } else {
    refreshAttempts.set(key, { count: 1, lastAttempt: now })
  }

  try {
    const res = await fetch(`${BACKEND_URL}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

function setAuthCookies(response: NextResponse, data: { access_token: string; refresh_token: string }) {
  response.cookies.set("access_token", data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 15,
    path: "/",
  })
  response.cookies.set("refresh_token", data.refresh_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 7,
    path: "/",
  })
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Skip middleware for static assets and API routes
  if (pathname.startsWith("/_next") || pathname.startsWith("/api")) {
    return NextResponse.next()
  }

  const isProtected = protectedRoutes.some(route => pathname.startsWith(route))
  const isAuthRoute = authRoutes.some(route => pathname.startsWith(route))

  const token = request.cookies.get("access_token")?.value

  // Protected route without token - redirect to login
  if (isProtected && !token) {
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("from", pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Protected route with token - verify it
  if (isProtected && token) {
    const payload = await verifyToken(token)
    if (!payload) {
      // Access token expired/invalid — try refresh
      const refreshToken = request.cookies.get("refresh_token")?.value
      if (refreshToken) {
        const newTokens = await tryRefreshToken(refreshToken)
        if (newTokens) {
          // Refresh succeeded — set new cookies and continue
          const response = NextResponse.next()
          setAuthCookies(response, newTokens)
          return response
        }
      }
      // Both tokens invalid — redirect to login
      const response = NextResponse.redirect(new URL("/login", request.url))
      response.cookies.delete("access_token")
      response.cookies.delete("refresh_token")
      return response
    }
  }

  // Auth route with valid token - redirect to documents
  if (isAuthRoute && token) {
    const payload = await verifyToken(token)
    if (payload) {
      return NextResponse.redirect(new URL("/documents", request.url))
    }
  }

  // Add security headers to response
  const response = NextResponse.next()
  response.headers.set("X-Content-Type-Options", "nosniff")
  response.headers.set("X-Frame-Options", "DENY")
  response.headers.set("X-XSS-Protection", "0")

  return response
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
}
