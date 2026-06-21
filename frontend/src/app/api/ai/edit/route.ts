import { NextRequest, NextResponse } from "next/server"
import { streamText } from "ai"
import { resolveEndpoint, createModelFromCredentials } from "@/lib/ai-server-utils"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

const VALID_OPERATIONS = ["polish", "expand", "compress", "translate_zh", "translate_en", "fix"]

const FALLBACK_EDIT_PROMPTS: Record<string, string> = {
  polish: "你是一个专业的文本润色助手。请重写以下文本，改善清晰度、语法和流畅性。保持原有的含义和语气不变。只输出润色后的文本，不要包含任何解释或额外说明。",
  expand: "你是一个内容扩展助手。请为以下文本补充更多细节、示例和上下文说明，使内容更加丰富和完整。保持原有结构，只输出扩展后的文本，不要包含任何解释。",
  compress: "你是一个文本压缩助手。请将以下文本压缩到原文约50%的长度，同时保留核心信息和要点。删除冗余表述，只输出压缩后的文本，不要包含任何解释。",
  translate_zh: "你是一个专业的中英翻译助手。请将以下文本翻译为中文。保留原文的格式和技术术语。翻译要自然流畅，符合中文表达习惯。只输出翻译结果，不要包含任何解释。",
  translate_en: "You are a professional translation assistant. Translate the following text to English. Preserve formatting and technical terms. Output only the translation, no explanations.",
  fix: "你是一个语法修正助手。请修正以下文本中的语法、拼写和标点错误，不改变原文含义。只输出修正后的文本，不要包含任何解释或说明。",
}

const EDIT_PROMPT_KEYS: Record<string, string> = {
  polish: "prompt_edit_polish", expand: "prompt_edit_expand", compress: "prompt_edit_compress",
  translate_zh: "prompt_edit_translate_zh", translate_en: "prompt_edit_translate_en", fix: "prompt_edit_fix",
}

async function fetchPrompts(token: string): Promise<Record<string, string> | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/settings/prompts-internal`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(5_000),
    })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function POST(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value
  if (!token) return NextResponse.json({ error: "Not authenticated" }, { status: 401 })

  let text, operation, context
  try {
    const body = await request.json()
    ;({ text, operation, context } = body)
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 })
  }

  if (!text || !operation) return NextResponse.json({ error: "Missing text or operation" }, { status: 400 })
  if (!VALID_OPERATIONS.includes(operation)) {
    return NextResponse.json({ error: `Invalid operation: ${operation}` }, { status: 400 })
  }

  // Parallel: fetch prompts and endpoint credentials
  const [allPrompts, creds] = await Promise.all([
    fetchPrompts(token),
    resolveEndpoint(token, "edit"),
  ])

  if (!creds) return NextResponse.json({ error: "未配置 AI 端点" }, { status: 500 })

  // Resolve system prompt server-side (prevents prompt injection)
  const promptKey = EDIT_PROMPT_KEYS[operation]
  const systemPrompt = (allPrompts && promptKey ? (allPrompts[promptKey] || FALLBACK_EDIT_PROMPTS[operation]) : FALLBACK_EDIT_PROMPTS[operation]) || "You are a helpful text editing assistant."

  // Create model from resolved credentials
  const model = createModelFromCredentials(creds)

  const userContent = context ? `Context:\n${context}\n\nText to edit:\n${text}` : text
  const result = streamText({
    model,
    system: systemPrompt,
    messages: [{ role: "user", content: userContent }],
    maxOutputTokens: 4096,
  })

  return result.toTextStreamResponse()
}
