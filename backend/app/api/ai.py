from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.api.auth import get_current_user_dep
from app.models.user import User
from app.models.document import Document
from app.services.ai_pipeline import ai_pipeline
from app.services.api_router import api_router
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])

@router.get("/status")
async def ai_status(current_user: User = Depends(get_current_user_dep)):
    return {
        "status": "ready",
        "providers": ["openai", "anthropic", "ollama"],
        "note": "AI streaming is handled by the Next.js frontend via Vercel AI SDK. This endpoint reports backend AI service availability.",
    }


class StandardizeRequest(BaseModel):
    document_id: int

class StandardizeResponse(BaseModel):
    structured_summary: str
    keywords: list[str]
    categories: list[str]
    content_suggestions: dict
    metadata: dict

@router.post("/standardize", response_model=StandardizeResponse)
async def standardize_document(
    data: StandardizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """AI analyze a document and return standardization suggestions (does not auto-apply)."""
    result = await db.execute(
        select(Document).where(
            Document.id == data.document_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # Extract text from document
    text = doc.plain_text or doc.title
    if not text.strip():
        text = doc.title

    # Get current tags
    await db.refresh(doc, attribute_names=["tags"])
    current_tags = [t.name for t in doc.tags] if doc.tags else []

    analysis = await ai_pipeline.standardize_document(text, doc.title, current_tags)

    return StandardizeResponse(
        structured_summary=analysis.get("structured_summary", ""),
        keywords=analysis.get("keywords", []),
        categories=analysis.get("categories", []),
        content_suggestions=analysis.get("content_suggestions", {}),
        metadata=analysis.get("metadata", {}),
    )


class AutoClassifyRequest(BaseModel):
    document_id: int

@router.post("/auto-classify")
async def auto_classify(
    data: AutoClassifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """AI auto-assign tags and classification to a document."""
    result = await db.execute(
        select(Document).where(
            Document.id == data.document_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    text = doc.plain_text or doc.title
    await db.refresh(doc, attribute_names=["tags"])
    current_tags = [t.name for t in doc.tags] if doc.tags else []

    analysis = await ai_pipeline.standardize_document(text, doc.title, current_tags)

    # Auto-apply tags
    from app.models.document import Tag, document_tags
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    keywords = analysis.get("keywords", [])
    for kw in keywords[:5]:  # Max 5 auto-tags
        tag_result = await db.execute(
            select(Tag).where(Tag.user_id == current_user.id, Tag.name == kw)
        )
        tag = tag_result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=kw, user_id=current_user.id)
            db.add(tag)
            await db.flush()
        stmt = sqlite_insert(document_tags).values(
            document_id=doc.id, tag_id=tag.id
        ).on_conflict_do_nothing()
        await db.execute(stmt)

    # Update document status if it's a draft
    if doc.status == "draft":
        doc.status = "published"

    await db.commit()

    return {
        "message": "自动分类完成",
        "keywords": keywords,
        "categories": analysis.get("categories", []),
        "metadata": analysis.get("metadata", {}),
    }


# ── AI Document Generation ──

class GenerateRequest(BaseModel):
    requirements: str
    title: str = ""
    document_type: str = ""  # tutorial, report, plan, note, reference
    language: str = "zh"
    max_sections: int = 10
    target_length: str = "medium"  # short, medium, long
    folder_id: Optional[int] = None
    tags: list[str] = []


class GenerateResponse(BaseModel):
    document_id: int
    title: str
    content_json: dict
    sections_generated: int


@router.post("/generate", response_model=GenerateResponse)
async def generate_document(
    data: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Generate a full document from requirements using AI."""
    if not data.requirements.strip():
        raise HTTPException(400, "请提供文档需求描述")
    if len(data.requirements) > 10000:
        raise HTTPException(400, "需求描述过长（最大 10000 字符）")

    try:
        result = await ai_pipeline.generate_document(
            requirements=data.requirements,
            title=data.title,
            document_type=data.document_type,
            language=data.language,
            max_sections=data.max_sections,
            target_length=data.target_length,
        )
    except Exception as e:
        logger.error("Document generation failed: %s", e)
        raise HTTPException(500, f"文档生成失败: {str(e)}")

    from app.services.content_converter import extract_plain_text
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    doc = Document(
        title=result["title"],
        content_json=result["content_json"],
        plain_text=extract_plain_text(result["content_json"]),
        status="draft",
        user_id=current_user.id,
        folder_id=data.folder_id,
        version=1,
    )
    db.add(doc)
    await db.flush()

    # Handle tags
    if data.tags:
        for tag_name in data.tags:
            tag_result = await db.execute(
                select(Tag).where(Tag.user_id == current_user.id, Tag.name == tag_name)
            )
            tag = tag_result.scalar_one_or_none()
            if not tag:
                tag = Tag(name=tag_name, user_id=current_user.id)
                db.add(tag)
                await db.flush()
            stmt = sqlite_insert(document_tags).values(
                document_id=doc.id, tag_id=tag.id
            ).on_conflict_do_nothing()
            await db.execute(stmt)

    await db.commit()
    await db.refresh(doc)

    return GenerateResponse(
        document_id=doc.id,
        title=doc.title,
        content_json=doc.content_json,
        sections_generated=result.get("sections_generated", 0),
    )


# ── Internal: resolve endpoint credentials (server-to-server only) ──

class ResolveRequest(BaseModel):
    category: str = "chat"


class EndpointCredentials(BaseModel):
    endpoint_id: int
    name: str
    protocol: str
    base_url: str
    api_key: str
    model_id: str
    protocol_mode: str = "completions"


@router.post("/endpoint-resolve", response_model=EndpointCredentials)
async def endpoint_resolve(
    request: Request,
    data: ResolveRequest,
    current_user: User = Depends(get_current_user_dep),
):
    """Return the best endpoint credentials for a given category.

    This is an **internal** endpoint — called only from the Next.js
    server-side route handlers. Requires X-Internal-Request header.
    """
    import os
    internal_secret = os.environ.get("INTERNAL_API_SECRET", "kb-internal-secret-change-me")
    if request.headers.get("X-Internal-Request") != internal_secret:
        raise HTTPException(403, "This endpoint is for internal use only")
    endpoints = await api_router.resolve(data.category)
    if not endpoints:
        # Try any available model as fallback
        all_models = await api_router.get_all_models()
        for m in all_models:
            endpoints = await api_router.resolve(m)
            if endpoints:
                break

    if not endpoints:
        raise HTTPException(400, "未配置 AI 端点，请在设置 → API 路由中添加")

    best = endpoints[0]
    best_models = best.supported_models or []
    model_id = best_models[0] if best_models else "gpt-4o-mini"

    # Determine protocol mode for OpenAI-compatible endpoints
    protocol_mode = "completions"
    if best.protocol != "anthropic":
        pm = best.protocol_mode or "auto"
        if pm == "auto":
            stats = best.stats_json or {}
            protocol_mode = stats.get("detected_protocol_mode", "completions")
        else:
            protocol_mode = pm

    return EndpointCredentials(
        endpoint_id=best.id,
        name=best.name,
        protocol=best.protocol,
        base_url=best.base_url,
        api_key=best.api_key,
        model_id=model_id,
        protocol_mode=protocol_mode,
    )


# ── Chat Streaming (credentials stay server-side) ──

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    system: str = ""


@router.post("/chat/stream")
async def chat_stream(
    data: ChatRequest,
    current_user: User = Depends(get_current_user_dep),
):
    """Stream a chat response using the API routing system with MCP tool calling.
    Credentials never leave the backend."""
    # Resolve the best endpoint
    endpoints = await api_router.resolve("chat")
    if not endpoints:
        all_models = await api_router.get_all_models()
        for m in all_models:
            endpoints = await api_router.resolve(m)
            if endpoints:
                break

    if not endpoints:
        raise HTTPException(400, "未配置 AI 端点，请在设置 → API 路由中添加")

    best = endpoints[0]
    best_models = best.supported_models or []
    model_id = best_models[0] if best_models else "gpt-4o-mini"

    # Build MCP tool definitions
    from app.mcp.server import mcp
    from app.services.mcp_tool_adapter import build_openai_tools_from_mcp, convert_to_anthropic_tools, execute_mcp_tool
    tools = build_openai_tools_from_mcp(mcp)

    # Convert messages to dict format
    messages = [{"role": m.role, "content": m.content} for m in data.messages]
    system = data.system or "You are a helpful assistant."

    # Determine protocol mode
    protocol_mode = best.protocol_mode or "auto"
    if protocol_mode == "auto":
        stats = best.stats_json or {}
        protocol_mode = stats.get("detected_protocol_mode", "completions")

    async def generate():
        try:
            client = api_router._get_or_create_client(best)
            max_tool_rounds = 5  # Prevent infinite tool call loops

            for round_num in range(max_tool_rounds):
                if best.protocol == "anthropic":
                    anthropic_tools = convert_to_anthropic_tools(tools) if tools else None
                    stream_kwargs = {
                        "model": model_id,
                        "system": system,
                        "messages": messages,
                        "max_tokens": 4096,
                    }
                    if anthropic_tools:
                        stream_kwargs["tools"] = anthropic_tools

                    collected_tool_calls = []
                    collected_text = ""

                    async with client.messages.stream(**stream_kwargs) as stream:
                        async for event in stream:
                            if event.type == "content_block_start":
                                if hasattr(event, "content_block") and getattr(event.content_block, "type", None) == "tool_use":
                                    collected_tool_calls.append({
                                        "id": event.content_block.id,
                                        "name": event.content_block.name,
                                        "input_json": "",
                                    })
                            elif event.type == "content_block_delta":
                                if hasattr(event.delta, "text"):
                                    collected_text += event.delta.text
                                    yield f"data: {json.dumps({'text': event.delta.text})}\n\n"
                                elif hasattr(event.delta, "partial_json") and collected_tool_calls:
                                    collected_tool_calls[-1]["input_json"] += event.delta.partial_json

                    # Execute tool calls if any
                    if collected_tool_calls:
                        for tc in collected_tool_calls:
                            try:
                                args = json.loads(tc["input_json"]) if tc["input_json"] else {}
                            except json.JSONDecodeError:
                                args = {}
                            yield f"data: {json.dumps({'tool_call': {'name': tc['name'], 'status': 'calling'}})}\n\n"
                            result = await execute_mcp_tool(mcp, tc["name"], args)
                            yield f"data: {json.dumps({'tool_call': {'name': tc['name'], 'status': 'complete', 'result': result[:500]}})}\n\n"

                            # Add tool use and result to messages
                            messages.append({
                                "role": "assistant",
                                "content": [{"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": args}],
                            })
                            messages.append({
                                "role": "user",
                                "content": [{"type": "tool_result", "tool_use_id": tc["id"], "content": result}],
                            })
                        continue  # Next round with tool results
                    else:
                        break  # No tool calls, done

                else:
                    # OpenAI-compatible
                    call_kwargs = {
                        "model": model_id,
                        "messages": [{"role": "system", "content": system}] + messages,
                        "max_tokens": 4096,
                        "stream": True,
                    }
                    if tools and round_num == 0:
                        call_kwargs["tools"] = tools

                    stream = await client.chat.completions.create(**call_kwargs)

                    tool_calls_buffer = {}
                    finish_reason = None

                    async for chunk in stream:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        finish_reason = chunk.choices[0].finish_reason

                        if delta.content:
                            yield f"data: {json.dumps({'text': delta.content})}\n\n"

                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                idx = tc.index
                                if idx not in tool_calls_buffer:
                                    tool_calls_buffer[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                                if tc.function:
                                    if tc.function.name:
                                        tool_calls_buffer[idx]["name"] = tc.function.name
                                    if tc.function.arguments:
                                        tool_calls_buffer[idx]["arguments"] += tc.function.arguments

                    # Execute tool calls
                    if finish_reason == "tool_calls" and tool_calls_buffer:
                        assistant_tool_calls = []
                        for idx in sorted(tool_calls_buffer.keys()):
                            tc_info = tool_calls_buffer[idx]
                            try:
                                args = json.loads(tc_info["arguments"]) if tc_info["arguments"] else {}
                            except json.JSONDecodeError:
                                args = {}

                            yield f"data: {json.dumps({'tool_call': {'name': tc_info['name'], 'status': 'calling'}})}\n\n"
                            result = await execute_mcp_tool(mcp, tc_info["name"], args)
                            yield f"data: {json.dumps({'tool_call': {'name': tc_info['name'], 'status': 'complete', 'result': result[:500]}})}\n\n"

                            assistant_tool_calls.append({
                                "id": tc_info["id"],
                                "type": "function",
                                "function": {"name": tc_info["name"], "arguments": tc_info["arguments"]},
                            })
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc_info["id"],
                                "content": result,
                            })

                        messages.insert(0, {"role": "assistant", "tool_calls": assistant_tool_calls, "content": None})
                        continue  # Next round with tool results
                    else:
                        break  # No tool calls, done

            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error("Chat stream error: %s", e)
            yield f"data: {json.dumps({'error': 'AI 服务暂时不可用，请稍后重试'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Edit Streaming (credentials stay server-side) ──

class EditRequest(BaseModel):
    text: str
    operation: str
    context: str = ""
    # system_prompt is NOT accepted from client — resolved server-side to prevent prompt injection


@router.post("/edit/stream")
async def edit_stream(
    data: EditRequest,
    current_user: User = Depends(get_current_user_dep),
):
    """Stream an edit response using the API routing system."""
    endpoints = await api_router.resolve("edit")
    if not endpoints:
        all_models = await api_router.get_all_models()
        for m in all_models:
            endpoints = await api_router.resolve(m)
            if endpoints:
                break

    if not endpoints:
        raise HTTPException(400, "未配置 AI 端点")

    best = endpoints[0]
    best_models = best.supported_models or []
    model_id = best_models[0] if best_models else "gpt-4o-mini"

    user_content = f"Context:\n{data.context}\n\nText to edit:\n{data.text}" if data.context else data.text
    # Resolve prompt server-side (don't accept from client — prevents prompt injection)
    EDIT_PROMPT_KEYS = {
        "polish": "prompt_edit_polish",
        "expand": "prompt_edit_expand",
        "compress": "prompt_edit_compress",
        "translate_zh": "prompt_edit_translate_zh",
        "translate_en": "prompt_edit_translate_en",
        "fix": "prompt_edit_fix",
    }
    EDIT_PROMPT_DEFAULTS = {
        "polish": "你是一个专业的文本润色助手。请重写以下文本，改善清晰度、语法和流畅性。保持原有的含义和语气不变。只输出润色后的文本，不要包含任何解释或额外说明。",
        "expand": "你是一个内容扩展助手。请为以下文本补充更多细节、示例和上下文说明，使内容更加丰富和完整。保持原有结构，只输出扩展后的文本，不要包含任何解释。",
        "compress": "你是一个文本压缩助手。请将以下文本压缩到原文约50%的长度，同时保留核心信息和要点。删除冗余表述，只输出压缩后的文本，不要包含任何解释。",
        "translate_zh": "你是一个专业的中英翻译助手。请将以下文本翻译为中文。保留原文的格式和技术术语。翻译要自然流畅，符合中文表达习惯。只输出翻译结果，不要包含任何解释。",
        "translate_en": "You are a professional translation assistant. Translate the following text to English. Preserve formatting and technical terms. Output only the translation, no explanations.",
        "fix": "你是一个语法修正助手。请修正以下文本中的语法、拼写和标点错误，不改变原文含义。只输出修正后的文本，不要包含任何解释或说明。",
    }
    try:
        from app.services.prompt_registry import get_all_prompts
        prompts = await get_all_prompts()
        prompt_key = EDIT_PROMPT_KEYS.get(data.operation)
        system = (prompts.get(prompt_key) if prompt_key else None) or EDIT_PROMPT_DEFAULTS.get(data.operation, "You are a helpful text editing assistant.")
    except Exception:
        system = EDIT_PROMPT_DEFAULTS.get(data.operation, "You are a helpful text editing assistant.")

    async def generate():
        try:
            # Use api_router's cached client (connection pooling)
            client = api_router._get_or_create_client(best)

            if best.protocol == "anthropic":
                async with client.messages.stream(
                    model=model_id,
                    system=system,
                    messages=[{"role": "user", "content": user_content}],
                    max_tokens=4096,
                ) as stream:
                    async for text in stream.text_stream:
                        yield f"data: {json.dumps({'text': text})}\n\n"
            else:
                stream = await client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                    max_tokens=4096,
                    stream=True,
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield f"data: {json.dumps({'text': chunk.choices[0].delta.content})}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error("Edit stream error: %s", e)
            yield f"data: {json.dumps({'error': 'AI 服务暂时不可用，请稍后重试'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
