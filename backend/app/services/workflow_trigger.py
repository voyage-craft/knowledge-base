"""Workflow trigger service.

Called by import_batch and document save endpoints to auto-execute
workflows that have trigger_type configured.
"""

import logging
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.workflow import Workflow, WorkflowRun

logger = logging.getLogger(__name__)

# Throttle: minimum seconds between trigger runs for the same workflow
_THROTTLE_SECONDS = 5


async def fire_triggers(trigger_type: str, user_id: int, background_tasks=None):
    """Find and execute all active workflows matching the trigger type for a user.

    Uses v2 engine with DAG support, condition/loop nodes, and per-node tracking.
    Includes throttling to prevent rapid-fire duplicate runs.
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Workflow).where(
                    Workflow.user_id == user_id,
                    Workflow.is_active == True,
                    Workflow.trigger_type == trigger_type,
                )
            )
            workflows = result.scalars().all()

            for wf in workflows:
                # Throttle: skip if last run was within _THROTTLE_SECONDS
                if wf.last_run_at:
                    from datetime import datetime, timedelta, timezone
                    elapsed = (datetime.now(timezone.utc) - wf.last_run_at).total_seconds()
                    if elapsed < _THROTTLE_SECONDS:
                        logger.debug("Throttling workflow '%s' (%.1fs since last run)", wf.name, elapsed)
                        continue

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

                # Update last_run_at BEFORE scheduling background task
                from datetime import datetime, timezone
                wf.last_run_at = datetime.now(timezone.utc)
                await db.commit()

                if background_tasks:
                    # Use v2 engine with DAG support
                    from app.services.workflow.engine import workflow_engine_v2
                    background_tasks.add_task(
                        workflow_engine_v2.execute, run.id, wf.id, user_id, wf.config_json or {}
                    )

    except Exception as e:
        logger.error("Failed to fire %s triggers for user %d: %s", trigger_type, user_id, e)
