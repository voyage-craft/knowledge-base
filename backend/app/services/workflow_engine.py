"""Workflow execution engine.

Parses a workflow's node graph, fetches documents, and chains AI processing
modules in topological order. Progress is tracked on the WorkflowRun record.
"""

import json
import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timezone

from sqlalchemy import select, delete as sql_delete
from app.core.database import AsyncSessionLocal
from app.models.document import Document, Tag, document_tags
from app.models.workflow import WorkflowRun
from app.services.llm_service import llm_service
from app.services.prompt_registry import get_prompt

logger = logging.getLogger(__name__)


# ── Topological sort ────────────────────────────────────────────────────

def _topo_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Kahn's algorithm — returns node IDs in execution order."""
    adj: dict[str, list[str]] = defaultdict(list)
    in_deg: dict[str, int] = {n["id"]: 0 for n in nodes}

    for e in edges:
        adj[e["source"]].append(e["target"])
        in_deg[e["target"]] = in_deg.get(e["target"], 0) + 1

    queue = deque(nid for nid, d in in_deg.items() if d == 0)
    order: list[str] = []

    while queue:
        nid = queue.popleft()
        order.append(nid)
        for child in adj[nid]:
            in_deg[child] -= 1
            if in_deg[child] == 0:
                queue.append(child)

    return order


def _strip_tiptap(content_json) -> str:
    """Extract plain text from TipTap JSON or string."""
    if isinstance(content_json, str):
        try:
            content_json = json.loads(content_json)
        except (json.JSONDecodeError, TypeError):
            return content_json

    if not isinstance(content_json, dict):
        return str(content_json)

    parts: list[str] = []
    for node in content_json.get("content", []):
        for inline in node.get("content", []):
            if inline.get("type") == "text":
                parts.append(inline.get("text", ""))
        parts.append("")  # paragraph break
    return "\n".join(parts).strip()


# ── Node processors ─────────────────────────────────────────────────────

async def _process_source(node: dict, db, user_id: int) -> list[dict]:
    """Fetch documents matching the source filter. Returns list of {id, title, text}."""
    cfg = node.get("config", {})
    filt = cfg.get("filter", "all")

    query = select(Document).where(
        Document.user_id == user_id,
        Document.status != "deleted",
    )

    if filt == "folder" and cfg.get("folder_id"):
        query = query.where(Document.folder_id == cfg["folder_id"])
    elif filt == "tag" and cfg.get("tag_name"):
        # Subquery for tagged documents
        tag_result = await db.execute(
            select(Tag.id).where(Tag.user_id == user_id, Tag.name == cfg["tag_name"])
        )
        tag_ids = [r[0] for r in tag_result.all()]
        if tag_ids:
            doc_tag_q = select(document_tags.c.document_id).where(
                document_tags.c.tag_id.in_(tag_ids)
            )
            query = query.where(Document.id.in_(doc_tag_q))
    elif filt == "status" and cfg.get("status"):
        query = query.where(Document.status == cfg["status"])

    result = await db.execute(query)
    docs = result.scalars().all()

    documents: list[dict] = []
    for doc in docs:
        text = doc.plain_text or _strip_tiptap(doc.content_json) or doc.title
        documents.append({"id": doc.id, "title": doc.title, "text": text})
    return documents


async def _run_llm(system_prompt: str, user_content: str, max_tokens: int = 4096) -> str:
    """Call LLM with error handling."""
    result = await llm_service.generate(
        messages=[{"role": "user", "content": user_content}],
        system=system_prompt,
        max_tokens=max_tokens,
    )
    if result.startswith("["):
        logger.warning("LLM returned error marker: %s", result)
    return result


async def _process_edit(text: str, prompt_key: str) -> str:
    """Run an edit operation (polish, expand, compress, translate, fix)."""
    system = await get_prompt(prompt_key)
    return await _run_llm(system, text[:8000])


async def _process_summarize(text: str, title: str) -> str:
    system = await get_prompt("prompt_workflow_summarize")
    prompt = f"文档标题: {title}\n\n文档内容:\n{text[:8000]}"
    return await _run_llm(system, prompt, max_tokens=1024)


async def _process_keywords(text: str) -> list[str]:
    system = await get_prompt("prompt_workflow_keywords")
    result = await _run_llm(system, text[:8000], max_tokens=512)
    # Extract JSON array
    match = re.search(r"\[.*?\]", result, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return []


async def _process_standardize(text: str, title: str) -> dict:
    """Run standardization analysis."""
    from app.services.ai_pipeline import ai_pipeline
    return await ai_pipeline.standardize_document(text, title, [])


# ── Main execution ──────────────────────────────────────────────────────

async def execute_workflow(run_id: int, workflow_id: int, user_id: int, config_json: dict):
    """Execute a workflow run in the background.

    Called via BackgroundTasks from the API endpoint.
    """
    nodes: list[dict] = config_json.get("nodes", [])
    edges: list[dict] = config_json.get("edges", [])

    if not nodes:
        await _update_run(run_id, status="failed", error_message="工作流没有定义节点")
        return

    # Build node lookup
    node_map = {n["id"]: n for n in nodes}

    # Topological sort
    try:
        exec_order = _topo_sort(nodes, edges)
    except Exception as e:
        await _update_run(run_id, status="failed", error_message=f"工作流图解析失败: {e}")
        return

    async with AsyncSessionLocal() as db:
        # Mark as running
        run = await db.get(WorkflowRun, run_id)
        if not run:
            return
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            # Phase 1: Source — fetch documents
            source_node = node_map.get(exec_order[0]) if exec_order else None
            if not source_node or source_node["type"] != "source":
                await _update_run(run_id, status="failed", error_message="工作流必须以「文档来源」节点开始")
                return

            documents = await _process_source(source_node, db, user_id)
            if not documents:
                await _update_run(run_id, status="completed", total_docs=0, processed_docs=0,
                                  results_json={"message": "没有匹配的文档"})
                return

            total = len(documents)
            processed = 0
            results: list[dict] = []

            # Phase 2: Process each document through the pipeline
            for doc in documents:
                doc_result: dict = {"id": doc["id"], "title": doc["title"], "actions": []}
                current_text = doc["text"]
                summaries: list[str] = []
                all_keywords: list[str] = []
                standardize_result: dict | None = None

                for nid in exec_order[1:]:  # skip source
                    node = node_map[nid]
                    ntype = node["type"]

                    try:
                        if ntype == "polish":
                            current_text = await _process_edit(current_text, "prompt_edit_polish")
                            doc_result["actions"].append("润色")

                        elif ntype == "expand":
                            current_text = await _process_edit(current_text, "prompt_edit_expand")
                            doc_result["actions"].append("扩展")

                        elif ntype == "compress":
                            current_text = await _process_edit(current_text, "prompt_edit_compress")
                            doc_result["actions"].append("压缩")

                        elif ntype == "translate_zh":
                            current_text = await _process_edit(current_text, "prompt_edit_translate_zh")
                            doc_result["actions"].append("翻译为中文")

                        elif ntype == "translate_en":
                            current_text = await _process_edit(current_text, "prompt_edit_translate_en")
                            doc_result["actions"].append("翻译为英文")

                        elif ntype == "fix":
                            current_text = await _process_edit(current_text, "prompt_edit_fix")
                            doc_result["actions"].append("修正语法")

                        elif ntype == "summarize":
                            summary = await _process_summarize(current_text, doc["title"])
                            summaries.append(summary)
                            doc_result["actions"].append("生成摘要")

                        elif ntype == "keywords":
                            kws = await _process_keywords(current_text)
                            all_keywords.extend(kws)
                            doc_result["actions"].append("提取关键词")

                        elif ntype == "auto_tag":
                            # Merge keywords as tags
                            if all_keywords:
                                for kw in set(all_keywords):
                                    tag_result = await db.execute(
                                        select(Tag).where(Tag.user_id == user_id, Tag.name == kw)
                                    )
                                    tag = tag_result.scalar_one_or_none()
                                    if not tag:
                                        tag = Tag(name=kw, user_id=user_id)
                                        db.add(tag)
                                        await db.flush()
                                    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                                    stmt = sqlite_insert(document_tags).values(
                                        document_id=doc["id"], tag_id=tag.id
                                    ).on_conflict_do_nothing()
                                    await db.execute(stmt)
                            doc_result["actions"].append("自动打标签")

                        elif ntype == "standardize":
                            standardize_result = await _process_standardize(current_text, doc["title"])
                            doc_result["actions"].append("标准化分析")

                        elif ntype == "custom_prompt":
                            prompt_text = node.get("config", {}).get("prompt", "")
                            if prompt_text:
                                current_text = await _run_llm(prompt_text, current_text[:8000])
                                doc_result["actions"].append("自定义处理")

                        elif ntype == "save":
                            # Save processed text back to document
                            save_mode = node.get("config", {}).get("mode", "overwrite")
                            if save_mode == "overwrite":
                                target_doc = await db.get(Document, doc["id"])
                                if target_doc:
                                    target_doc.plain_text = current_text
                                    # Wrap as TipTap paragraphs
                                    paragraphs = current_text.split("\n\n")
                                    content_nodes = []
                                    for p in paragraphs:
                                        p = p.strip()
                                        if p:
                                            content_nodes.append({
                                                "type": "paragraph",
                                                "content": [{"type": "text", "text": p}],
                                            })
                                    target_doc.content_json = {
                                        "type": "doc",
                                        "content": content_nodes,
                                    }
                                    # Attach summary if available
                                    if summaries:
                                        doc_result["summary"] = summaries[-1]
                                    doc_result["saved"] = True

                            doc_result["actions"].append("保存")

                        elif ntype == "export":
                            # Export is handled at the result level
                            doc_result["actions"].append("标记导出")

                    except Exception as e:
                        logger.error("Workflow node '%s' failed for doc %d: %s", ntype, doc["id"], e)
                        doc_result["actions"].append(f"{ntype}(失败)")

                results.append(doc_result)
                processed += 1

                # Update progress
                run = await db.get(WorkflowRun, run_id)
                if run:
                    run.processed_docs = processed
                    await db.commit()

            # Finalize
            await db.commit()
            await _update_run(
                run_id,
                status="completed",
                total_docs=total,
                processed_docs=processed,
                results_json={"documents": results},
            )

        except Exception as e:
            logger.error("Workflow execution failed for run %d: %s", run_id, e)
            await _update_run(run_id, status="failed", error_message=str(e))


async def _update_run(run_id: int, **kwargs):
    """Update a workflow run record."""
    async with AsyncSessionLocal() as db:
        run = await db.get(WorkflowRun, run_id)
        if not run:
            return
        for key, value in kwargs.items():
            if hasattr(run, key):
                setattr(run, key, value)
        if kwargs.get("status") in ("completed", "failed"):
            run.completed_at = datetime.now(timezone.utc)
        await db.commit()
