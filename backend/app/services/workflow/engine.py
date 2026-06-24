"""Workflow execution engine v2.

Enhanced workflow engine with:
- Node registry pattern for extensibility
- Dynamic graph walking (supports branches and loops)
- DAG execution with parallel branches
- Per-node execution tracking
- Error recovery and retry
- Parallel document processing (semaphore-limited)
- Global execution timeout (5 minutes)

Usage:
    from app.services.workflow.engine import workflow_engine_v2

    await workflow_engine_v2.execute(run_id, workflow_id, user_id, config_json)
"""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from app.core.database import get_session, AsyncSessionLocal
from app.models.document import Document
from app.models.workflow import WorkflowRun, WorkflowNodeExecution
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeContext, NodeResult

# Import all node processors to trigger registration
import app.services.workflow.nodes

logger = logging.getLogger(__name__)

# Maximum concurrent document processing
DOC_CONCURRENCY = 3
# Global execution timeout in seconds
EXECUTION_TIMEOUT = 300  # 5 minutes


class WorkflowEngineV2:
    """Enhanced workflow execution engine with node registry pattern."""

    def __init__(self):
        self._max_steps = 1000  # Safety limit for graph walking
        self._semaphore = asyncio.Semaphore(DOC_CONCURRENCY)

    async def execute(self, run_id: int, workflow_id: int, user_id: int, config_json: dict):
        """Execute a workflow run in the background with timeout protection."""
        try:
            await asyncio.wait_for(
                self._execute_inner(run_id, workflow_id, user_id, config_json),
                timeout=EXECUTION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("Workflow run %d timed out after %ds", run_id, EXECUTION_TIMEOUT)
            await self._update_run(run_id, status="failed", error_message=f"执行超时（{EXECUTION_TIMEOUT}s）")

    async def _execute_inner(self, run_id: int, workflow_id: int, user_id: int, config_json: dict):
        """Inner execution logic (wrapped by timeout)."""
        nodes: list[dict] = config_json.get("nodes", [])
        edges: list[dict] = config_json.get("edges", [])

        if not nodes:
            await self._update_run(run_id, status="failed", error_message="工作流没有定义节点")
            return

        # Build node lookup
        node_map = {n["id"]: n for n in nodes}

        # Find start node (first node or explicit start)
        start_node_id = nodes[0]["id"]
        for node in nodes:
            if node.get("type") == "source":
                start_node_id = node["id"]
                break

        async with get_session() as db:
            # Mark as running
            run = await db.get(WorkflowRun, run_id)
            if not run:
                return
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            try:
                # Phase 1: Source — fetch documents
                source_node = node_map.get(start_node_id)
                if not source_node or source_node.get("type") != "source":
                    await self._update_run(run_id, status="failed", error_message="工作流必须以「文档来源」节点开始")
                    return

                # Create context for source node
                source_context = NodeContext(
                    node=source_node,
                    document={},
                    current_text="",
                    db=db,
                    user_id=user_id,
                    run_id=run_id,
                    extra={"node_map": node_map, "edges": edges},
                )

                # Execute source node
                source_processor = NodeProcessorRegistry.get("source")
                source_result = await source_processor().execute(source_context)

                if source_result.error:
                    await self._update_run(run_id, status="failed", error_message=source_result.error)
                    return

                documents = source_result.output_data.get("documents", [])
                if not documents:
                    await self._update_run(
                        run_id, status="completed", total_docs=0, processed_docs=0,
                        results_json={"message": "没有匹配的文档"}
                    )
                    return

                total = len(documents)

                # Phase 2: Process documents in parallel (semaphore-limited)
                results = await self._process_documents_parallel(
                    db, run_id, user_id, documents, node_map, edges, start_node_id
                )

                processed = sum(1 for r in results if r.get("status") != "error")

                # Finalize
                await db.commit()
                await self._update_run(
                    run_id,
                    status="completed",
                    total_docs=total,
                    processed_docs=processed,
                    results_json={"documents": results},
                )

            except Exception as e:
                logger.error("Workflow execution failed for run %d: %s", run_id, e, exc_info=True)
                # Persist any pending node execution records before updating run status.
                # _update_run opens its own session, so uncommitted records on this
                # session would be lost when it closes.
                try:
                    await db.commit()
                except Exception:
                    logger.warning("Failed to commit node execution records for run %d", run_id)
                await self._update_run(run_id, status="failed", error_message=str(e))

    async def _process_documents_parallel(
        self,
        db,
        run_id: int,
        user_id: int,
        documents: list[dict],
        node_map: dict,
        edges: list[dict],
        start_node_id: str,
    ) -> list[dict]:
        """Process documents in parallel with semaphore-limited concurrency."""
        processed_count = 0

        async def process_one(doc: dict) -> dict:
            nonlocal processed_count
            async with self._semaphore:
                # Each parallel task gets its own database session to avoid
                # concurrent access on a shared AsyncSession (not thread-safe).
                async with AsyncSessionLocal() as session:
                    result = await self._process_document(
                        session, run_id, user_id, doc, node_map, edges, start_node_id
                    )
                    processed_count += 1

                    # Update progress using the per-task session
                    run = await session.get(WorkflowRun, run_id)
                    if run:
                        run.processed_docs = processed_count
                        await session.commit()

                return result

        tasks = [process_one(doc) for doc in documents]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _process_document(
        self,
        db,
        run_id: int,
        user_id: int,
        doc: dict,
        node_map: dict,
        edges: list[dict],
        start_node_id: str,
    ) -> dict:
        """Process a single document through the workflow graph.

        Supports DAG execution with parallel branches.
        """
        doc_result = {"id": doc["id"], "title": doc["title"], "actions": []}
        current_text = doc["text"]
        accumulated_data = {}

        # Build adjacency list for DAG traversal
        adj = defaultdict(list)
        for e in edges:
            adj[e["source"]].append(e["target"])

        # Get all nodes after source
        next_nodes = adj.get(start_node_id, [])

        # Execute nodes using topological order with parallel branches
        await self._execute_dag(
            db, run_id, user_id, doc, node_map, edges, adj,
            next_nodes, doc_result, current_text, accumulated_data, visited=set()
        )

        return doc_result

    async def _execute_dag(
        self,
        db,
        run_id: int,
        user_id: int,
        doc: dict,
        node_map: dict,
        edges: list[dict],
        adj: dict,
        node_ids: list[str],
        doc_result: dict,
        current_text: str,
        accumulated_data: dict,
        visited: set,
        step: int = 0,
    ) -> str:
        """Execute nodes in DAG order, with parallel execution of independent branches.

        Returns the current_text after execution.
        """
        if step >= self._max_steps:
            logger.warning("Max steps reached in DAG execution")
            return current_text

        # Filter out already visited nodes
        pending_ids = [nid for nid in node_ids if nid not in visited]
        if not pending_ids:
            return current_text

        # Separate nodes into processable and skippable
        processable = []
        for node_id in pending_ids:
            node = node_map.get(node_id)
            if not node:
                logger.warning("Node %s not found in node map", node_id)
                visited.add(node_id)
                continue
            ntype = node.get("type", "")
            if ntype == "source":
                visited.add(node_id)
                next_nodes = adj.get(node_id, [])
                current_text = await self._execute_dag(
                    db, run_id, user_id, doc, node_map, edges, adj,
                    next_nodes, doc_result, current_text, accumulated_data, visited, step + 1
                )
                continue
            if not NodeProcessorRegistry.has(ntype):
                logger.warning("Unknown node type: %s", ntype)
                visited.add(node_id)
                continue
            processable.append(node_id)

        if not processable:
            return current_text

        # Execute independent siblings in parallel
        async def execute_node(node_id: str) -> tuple[str, str]:
            """Execute a single node, returns (node_id, resulting_text).

            Each node gets its own AsyncSession to avoid concurrent access
            on a shared session during parallel (asyncio.gather) execution.
            """
            node = node_map[node_id]
            ntype = node.get("type", "")
            processor = NodeProcessorRegistry.get(ntype)

            visited.add(node_id)
            async with AsyncSessionLocal() as session:
                try:
                    context = NodeContext(
                        node=node,
                        document=doc,
                        current_text=current_text,
                        accumulated_data=accumulated_data,
                        db=session,
                        user_id=user_id,
                        run_id=run_id,
                        extra={"node_map": node_map, "edges": edges},
                    )

                    result = await processor().execute(context)

                    await self._record_node_execution(
                        session, run_id, node, doc["id"], result, current_text
                    )

                    if result.error:
                        doc_result["actions"].append(f"{ntype}(失败: {result.error})")
                        if node.get("config", {}).get("stop_on_error", False):
                            return node_id, current_text
                    else:
                        doc_result["actions"].extend(result.actions)
                        if result.metadata:
                            doc_result.update(result.metadata)

                    out_text = result.output_text if result.output_text is not None else current_text

                    # Handle branch target (for condition nodes)
                    if result.branch_target:
                        next_nodes = [result.branch_target]
                        out_text = await self._execute_dag(
                            session, run_id, user_id, doc, node_map, edges, adj,
                            next_nodes, doc_result, out_text, accumulated_data, visited, step + 1
                        )
                    elif result.should_continue:
                        next_nodes = adj.get(node_id, [])
                        if next_nodes:
                            out_text = await self._execute_dag(
                                session, run_id, user_id, doc, node_map, edges, adj,
                                next_nodes, doc_result, out_text, accumulated_data, visited, step + 1
                            )

                    return node_id, out_text

                except Exception as e:
                    logger.error("Node %s failed for doc %d: %s", ntype, doc["id"], e, exc_info=True)
                    doc_result["actions"].append(f"{ntype}(异常)")

                    await self._record_node_execution(
                        session, run_id, node, doc["id"],
                        NodeResult(error=str(e)), current_text
                    )

                    next_nodes = adj.get(node_id, [])
                    out_text = current_text
                    if next_nodes:
                        out_text = await self._execute_dag(
                            session, run_id, user_id, doc, node_map, edges, adj,
                            next_nodes, doc_result, out_text, accumulated_data, visited, step + 1
                        )
                    return node_id, out_text
                finally:
                    await session.commit()

        # Run all processable nodes in parallel
        if len(processable) > 1:
            results = await asyncio.gather(
                *[execute_node(nid) for nid in processable],
                return_exceptions=False,
            )
            # Use the last non-empty text result
            for _, text in results:
                if text != current_text:
                    current_text = text
        else:
            _, current_text = await execute_node(processable[0])

        return current_text

    def _get_next_node(self, current_id: str, edges: list[dict]) -> Optional[str]:
        """Get the next node in the graph (follows single outgoing edge)."""
        for e in edges:
            if e["source"] == current_id:
                return e["target"]
        return None

    def _get_all_next_nodes(self, current_id: str, edges: list[dict]) -> list[str]:
        """Get all next nodes from current node (for DAG branches)."""
        return [e["target"] for e in edges if e["source"] == current_id]

    async def _record_node_execution(
        self,
        db,
        run_id: int,
        node: dict,
        document_id: int,
        result: NodeResult,
        input_text: str = "",
    ):
        """Record node execution for tracking and debugging."""
        execution = WorkflowNodeExecution(
            run_id=run_id,
            node_id=node["id"],
            node_type=node.get("type", ""),
            document_id=document_id,
            status="failed" if result.error else "completed",
            input_data={"text_length": len(input_text)},
            output_data=result.output_data,
            error_message=result.error,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(execution)

    async def _update_run(self, run_id: int, **kwargs):
        """Update a workflow run record."""
        async with get_session() as db:
            run = await db.get(WorkflowRun, run_id)
            if not run:
                return
            for key, value in kwargs.items():
                if hasattr(run, key):
                    setattr(run, key, value)
            if kwargs.get("status") in ("completed", "failed"):
                run.completed_at = datetime.now(timezone.utc)
            await db.commit()


# Global workflow engine v2 instance
workflow_engine_v2 = WorkflowEngineV2()
