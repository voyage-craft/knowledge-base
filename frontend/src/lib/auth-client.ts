import { cookies } from "next/headers"
import type { User } from "./user-context"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function authCheck(): Promise<User | null> {
  const cookieStore = await cookies()
  const token = cookieStore.get("access_token")?.value
  if (!token) return null

  try {
    const res = await fetch(`${BACKEND_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      next: { revalidate: 60 },
    })
    if (!res.ok) return null
    const data = await res.json()
    return {
      id: data.id,
      username: data.username,
      email: data.email,
      is_admin: data.is_admin ?? false,
    }
  } catch {
    return null
  }
}
