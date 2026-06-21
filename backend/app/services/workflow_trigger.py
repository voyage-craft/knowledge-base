"""Workflow trigger service.

Called by import_batch and document save endpoints to auto-execute
workflows that have trigger_type configured.
"""

import logging
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.workflow import Workflow, WorkflowRun
from app.services.workflow_engine import execute_workflow

logger = logging.getLogger(__name__)


async def fire_triggers(trigger_type: str, user_id: int, background_tasks=None):
    """Find and execute all active workflows matching the trigger type for a user.

    Args:
        trigger_type: "on_import" or "on_save"
        user_id: the user whose workflows to check
        background_tasks: FastAPI BackgroundTasks (if available, runs async; otherwise logs only)
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Workflow).where(
                    Workflow.user_id == user_id,
                    Workflow.is_active == 1,
                    Workflow.trigger_type == trigger_type,
                )
            )
            workflows = result.scalars().all()

            for wf in workflows:
                logger.info(
                    "Auto-triggering workflow '%s' (id=%d) for user %d on %s",
                    wf.name, wf.id, user_id, trigger_type,
                )

                run = WorkflowRun(
                    workflow_id=wf.id,
                    user_id=user_id,
                    status="pending",
                )
                db.add(run)
                await db.flush()

                if background_tasks:
                    background_tasks.add_task(
                        execute_workflow, run.id, wf.id, user_id, wf.config_json or {}
                    )

            await db.commit()

    except Exception as e:
        logger.error("Failed to fire %s triggers for user %d: %s", trigger_type, user_id, e)
