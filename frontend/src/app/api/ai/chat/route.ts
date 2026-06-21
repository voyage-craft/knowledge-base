import { NextRequest, NextResponse } from "next/server"
import { streamText } from "ai"
import { resolveEndpoint, createModelFromCredentials, normalizeMessages, getLastUserText } from "@/lib/ai-server-utils"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

const FALLBACK_SYSTEM_PROMPT =
  "你是知识库的 AI 知识助手。你可以帮助用户撰写、编辑和整理文档，回答关于知识库内容的问题。" +
  "你的回答应当准确、简洁、有条理。使用与用户相同的语言进行回复。"

const FALLBACK_RAG_TEMPLATE =
  "以下是从用户知识库中检索到的相关文档片段，请参考这些内容回答用户的问题：\n\n{context}\n\n" +
  "回答要求：\n1. 优先基于上述文档片段回答问题\n" +
  "2. 如果文档片段不足以回答，可以结合通用知识补充，但需注明\n" +
  "3. 如果检索内容与问题不相关，忽略检索内容直接回答"

let cachedPrompts: { value: Record<string, string>; expiresAt: number } | null = null

async function fetchPrompts(token: string): Promise<Record<string, string>> {
  if (cachedPrompts && Date.now() < cachedPrompts.expiresAt) return cachedPrompts.value
  try {
    const res = await fetch(`${BACKEND_URL}/api/settings/prompts-internal`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(5_000),
    })
    if (!res.ok) return {}
    const prompts = await res.json()
    cachedPrompts = { value: prompts, expiresAt: Date.now() + 60_000 }
    return prompts
  } catch {
    return {}
  }
}

async function searchRAG(token: string, query: string) {
  try {
    const res = await fetch(
      `${BACKEND_URL}/api/rag/search?q=${encodeURIComponent(query)}&top_k=5&threshold=0.3`,
      { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(5_000) },
    )
    if (!res.ok) return []
    const data = await res.json()
    return data.results || []
  } catch {
    return []
  }
}

export async function POST(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value
  if (!token) return NextResponse.json({ error: "Not authenticated" }, { status: 401 })

  let rawMessages
  try {
    const body = await request.json()
    rawMessages = body.messages
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 })
  }

  if (!rawMessages || rawMessages.length === 0) {
    return NextResponse.json({ error: "No messages provided" }, { status: 400 })
  }

  // Validate message limits
  if (rawMessages.length > 100) {
    return NextResponse.json({ error: "Too many messages" }, { status: 400 })
  }

  const messages = normalizeMessages(rawMessages)

  // Parallel: fetch prompts and endpoint credentials simultaneously
  const [prompts, creds] = await Promise.all([
    fetchPrompts(token),
    resolveEndpoint(token, "chat"),
  ])

  if (!creds) {
    return NextResponse.json({ error: "未配置 AI 端点，请在设置 → API 路由中添加" }, { status: 500 })
  }

  // Build system prompt with RAG context
  const basePrompt = prompts.prompt_chat_system || FALLBACK_SYSTEM_PROMPT
  const lastUserText = getLastUserText(rawMessages)
  let systemPrompt = basePrompt

  if (lastUserText && lastUserText.length >= 4) {
    const ragResults = await searchRAG(token, lastUserText)
    if (ragResults.length > 0) {
      const ragTemplate = prompts.prompt_rag_context || FALLBACK_RAG_TEMPLATE
      const contextText = ragResults.map((r: any, i: number) => `[${i + 1}] 《${r.document_title}》\n${r.chunk_text}`).join("\n\n---\n\n")
      systemPrompt = `${basePrompt}\n\n---\n\n${ragTemplate.replace("{context}", contextText)}`
    }
  }

  // Create model from resolved credentials
  const model = createModelFromCredentials(creds)

  // Stream using AI SDK — produces correct UIMessageStream format
  const result = streamText({ model, system: systemPrompt, messages, maxOutputTokens: 4096 })
  return result.toUIMessageStreamResponse()
}
