import { NextRequest, NextResponse } from "next/server"
import { verifyToken } from "@/lib/auth"

const protectedRoutes = ["/editor", "/documents", "/chat", "/settings", "/graph", "/import", "/workflows"]
const authRoutes = ["/login"]

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

async function tryRefreshToken(refreshToken: string): Promise<{ access_token: string; refresh_token: string } | null> {
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

  const isProtected = protectedRoutes.some(route => pathname.startsWith(route))
  const isAuthRoute = authRoutes.some(route => pathname.startsWith(route))

  const token = request.cookies.get("access_token")?.value

  if (isProtected && !token) {
    return NextResponse.redirect(new URL("/login", request.url))
  }

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

  if (isAuthRoute && token) {
    const payload = await verifyToken(token)
    if (payload) {
      return NextResponse.redirect(new URL("/documents", request.url))
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
}
