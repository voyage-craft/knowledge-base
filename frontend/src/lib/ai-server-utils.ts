/**
 * Shared server-side AI utilities for Next.js API routes.
 * Used by chat/route.ts and edit/route.ts.
 */

import { createOpenAI } from "@ai-sdk/openai"
import { createAnthropic } from "@ai-sdk/anthropic"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

// ── Shared secret for internal API calls (must be set in .env.local) ──
const INTERNAL_SECRET = process.env.INTERNAL_API_SECRET || ""

export interface EndpointCredentials {
  endpoint_id: number
  name: string
  protocol: string
  base_url: string
  api_key: string
  model_id: string
  protocol_mode: string
}

/**
 * Fetch endpoint credentials from backend (server-to-server only).
 * Uses a shared secret to prevent external access.
 */
export async function resolveEndpoint(token: string, category: string = "chat"): Promise<EndpointCredentials | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/ai/endpoint-resolve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        "X-Internal-Request": INTERNAL_SECRET,
      },
      body: JSON.stringify({ category }),
      signal: AbortSignal.timeout(10_000),
    })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

/**
 * Create an AI model from resolved credentials.
 * Uses protocol_mode to determine which API to call.
 */
export function createModelFromCredentials(creds: EndpointCredentials) {
  if (creds.protocol === "anthropic") {
    const anthropic = createAnthropic({
      apiKey: creds.api_key,
      ...(creds.base_url ? { baseURL: creds.base_url } : {}),
    })
    return anthropic(creds.model_id)
  }

  // OpenAI-compatible providers
  const openai = createOpenAI({
    apiKey: creds.api_key,
    baseURL: creds.base_url || undefined,
  })

  // Use protocol_mode to determine API
  if (creds.protocol_mode === "responses") {
    return openai(creds.model_id)  // Responses API
  }
  return openai.chat(creds.model_id)  // Chat Completions API (default)
}

/**
 * Normalize messages from useChat format to streamText format.
 */
export function normalizeMessages(messages: any[]): { role: "user" | "assistant" | "system"; content: string }[] {
  return messages.map(m => {
    const role: "user" | "assistant" | "system" =
      m.role === "assistant" ? "assistant" : m.role === "system" ? "system" : "user"
    if (m.content !== undefined && typeof m.content === "string") return { role, content: m.content }
    if (Array.isArray(m.parts)) {
      return { role, content: m.parts.filter((p: any) => p.type === "text").map((p: any) => p.text).join("") }
    }
    return { role, content: String(m.text || "") }
  })
}

/**
 * Extract the last user message text.
 */
export function getLastUserText(messages: any[]): string {
  const lastUser = [...messages].reverse().find(m => m.role === "user")
  if (!lastUser) return ""
  if (lastUser.content) return lastUser.content
  if (Array.isArray(lastUser.parts)) {
    return lastUser.parts.filter((p: any) => p.type === "text").map((p: any) => p.text).join("")
  }
  return String(lastUser.text || "")
}
