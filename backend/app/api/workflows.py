"""Workflow CRUD, execution, scheduling, and trigger API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete

from app.core.database import get_db
from app.api.auth import get_current_user_dep
from app.models.user import User
from app.models.workflow import Workflow, WorkflowRun
from app.services.workflow_templates import get_template, list_templates, PRESET_TEMPLATES
from app.services.workflow.engine import workflow_engine_v2

async def execute_workflow(run_id: int, workflow_id: int, user_id: int, config_json: dict):
    """Wrapper to maintain API compatibility while using v2 engine."""
    await workflow_engine_v2.execute(run_id, workflow_id, user_id, config_json)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# ── Schemas ─────────────────────────────────────────────────────────────

class WorkflowCreateRequest(BaseModel):
    name: str
    description: str | None = None
    template_type: str = "custom"
    config_json: dict


class WorkflowUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    config_json: dict | None = None
    schedule_json: dict | None = None
    trigger_type: str | None = None
    trigger_config_json: dict | None = None


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    template_type: str
    config_json: dict
    schedule_json: dict | None = None
    trigger_type: str
    trigger_config_json: dict | None = None
    is_active: int
    last_run_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_orm_obj(cls, obj: Workflow) -> "WorkflowResponse":
        return cls(
            id=obj.id,
            name=obj.name,
            description=obj.description,
            template_type=obj.template_type,
            config_json=obj.config_json or {},
            schedule_json=obj.schedule_json,
            trigger_type=obj.trigger_type or "none",
            trigger_config_json=obj.trigger_config_json,
            is_active=obj.is_active,
            last_run_at=obj.last_run_at.isoformat() if obj.last_run_at else None,
            created_at=obj.created_at.isoformat() if obj.created_at else None,
            updated_at=obj.updated_at.isoformat() if obj.updated_at else None,
        )


class WorkflowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    status: str
    total_docs: int
    processed_docs: int
    results_json: dict | None
    error_message: str | None
    started_at: str | None = None
    completed_at: str | None = None

    @classmethod
    def from_orm_obj(cls, obj: WorkflowRun) -> "WorkflowRunResponse":
        return cls(
            id=obj.id,
            workflow_id=obj.workflow_id,
            status=obj.status,
            total_docs=obj.total_docs,
            processed_docs=obj.processed_docs,
            results_json=obj.results_json,
            error_message=obj.error_message,
            started_at=obj.started_at.isoformat() if obj.started_at else None,
            completed_at=obj.completed_at.isoformat() if obj.completed_at else None,
        )


class ExecuteRequest(BaseModel):
    workflow_id: int


class QuickExecuteRequest(BaseModel):
    """Execute a preset template directly without creating a workflow first."""
    template_key: str
    filter: str = "all"           # all / folder / tag / status
    folder_id: int | None = None
    tag_name: str | None = None
    status: str | None = None


class ScheduleRequest(BaseModel):
    schedule_json: dict | None    # {"cron": "0 9 * * *", "enabled": true} or null to clear


class TriggerRequest(BaseModel):
    trigger_type: str             # none / on_import / on_save
    trigger_config_json: dict | None = None


class TemplateResponse(BaseModel):
    key: str
    name: str
    description: str
    nodes: list[dict]
    edges: list[dict]


# ── Templates ───────────────────────────────────────────────────────────

@router.get("/templates", response_model=list[TemplateResponse])
async def get_templates(
    current_user: User = Depends(get_current_user_dep),
):
    """List all preset workflow templates."""
    return list_templates()


@router.post("/from-template", response_model=WorkflowResponse)
async def create_from_template(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Create a new workflow from a preset template."""
    template_key = data.get("template_key", "")
    template = get_template(template_key)
    if not template:
        raise HTTPException(status_code=400, detail=f"未知模板: {template_key}")

    wf = Workflow(
        user_id=current_user.id,
        name=template["name"],
        description=template["description"],
        template_type="preset",
        config_json={"nodes": template["nodes"], "edges": template["edges"]},
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return WorkflowResponse.from_orm_obj(wf)


# ── Quick Execute (preset template, no workflow creation needed) ────────

@router.post("/quick-execute", response_model=WorkflowRunResponse)
async def quick_execute(
    data: QuickExecuteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Execute a preset template directly — auto-creates a temporary workflow."""
    template = get_template(data.template_key)
    if not template:
        raise HTTPException(status_code=400, detail=f"未知模板: {data.template_key}")

    # Override source filter if specified
    nodes = template["nodes"]
    if data.filter != "all":
        nodes = [
            {**n, "config": {**n.get("config", {}), "filter": data.filter,
             "folder_id": data.folder_id, "tag_name": data.tag_name, "status": data.status}}
            if n["type"] == "source" else n
            for n in nodes
        ]

    config = {"nodes": nodes, "edges": template["edges"]}

    # Find or create a workflow for this template
    result = await db.execute(
        select(Workflow).where(
            Workflow.user_id == current_user.id,
            Workflow.template_type == "preset",
            Workflow.name == template["name"],
            Workflow.is_active == 1,
        )
    )
    wf = result.scalar_one_or_none()
    if not wf:
        wf = Workflow(
            user_id=current_user.id,
            name=template["name"],
            description=template["description"],
            template_type="preset",
            config_json=config,
        )
        db.add(wf)
        await db.flush()

    wf.config_json = config

    # Create run
    run = WorkflowRun(workflow_id=wf.id, user_id=current_user.id, status="pending")
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(execute_workflow, run.id, wf.id, current_user.id, config)
    return WorkflowRunResponse.from_orm_obj(run)


# ── CRUD ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """List all user's workflows."""
    result = await db.execute(
        select(Workflow).where(
            Workflow.user_id == current_user.id,
            Workflow.is_active == 1,
        ).order_by(Workflow.updated_at.desc())
    )
    workflows = result.scalars().all()
    return [WorkflowResponse.from_orm_obj(w) for w in workflows]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get a single workflow."""
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.user_id == current_user.id,
        )
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return WorkflowResponse.from_orm_obj(wf)


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    data: WorkflowCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Create a new custom workflow."""
    wf = Workflow(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        template_type=data.template_type,
        config_json=data.config_json,
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return WorkflowResponse.from_orm_obj(wf)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: int,
    data: WorkflowUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Update a workflow."""
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.user_id == current_user.id,
        )
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")

    if data.name is not None:
        wf.name = data.name
    if data.description is not None:
        wf.description = data.description
    if data.config_json is not None:
        wf.config_json = data.config_json
    if data.schedule_json is not None:
        wf.schedule_json = data.schedule_json
    if data.trigger_type is not None:
        wf.trigger_type = data.trigger_type
    if data.trigger_config_json is not None:
        wf.trigger_config_json = data.trigger_config_json

    await db.commit()
    await db.refresh(wf)
    return WorkflowResponse.from_orm_obj(wf)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Soft-delete a workflow."""
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.user_id == current_user.id,
        )
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")

    wf.is_active = 0
    await db.commit()
    return {"message": "工作流已删除"}


# ── Schedule ────────────────────────────────────────────────────────────

@router.put("/{workflow_id}/schedule", response_model=WorkflowResponse)
async def update_schedule(
    workflow_id: int,
    data: ScheduleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Set or clear cron schedule for a workflow."""
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.user_id == current_user.id,
        )
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")

    wf.schedule_json = data.schedule_json
    await db.commit()
    await db.refresh(wf)
    return WorkflowResponse.from_orm_obj(wf)


# ── Triggers ────────────────────────────────────────────────────────────

@router.put("/{workflow_id}/trigger", response_model=WorkflowResponse)
async def update_trigger(
    workflow_id: int,
    data: TriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Set auto-trigger configuration for a workflow."""
    if data.trigger_type not in ("none", "on_import", "on_save"):
        raise HTTPException(status_code=400, detail="无效的触发类型")

    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.user_id == current_user.id,
        )
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")

    wf.trigger_type = data.trigger_type
    wf.trigger_config_json = data.trigger_config_json
    await db.commit()
    await db.refresh(wf)
    return WorkflowResponse.from_orm_obj(wf)


# ── Execution ───────────────────────────────────────────────────────────

@router.post("/execute", response_model=WorkflowRunResponse)
async def execute(
    data: ExecuteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Execute a workflow — creates a run and processes in background."""
    from datetime import datetime, timezone

    result = await db.execute(
        select(Workflow).where(
            Workflow.id == data.workflow_id,
            Workflow.user_id == current_user.id,
            Workflow.is_active == 1,
        )
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")

    run = WorkflowRun(workflow_id=wf.id, user_id=current_user.id, status="pending")
    db.add(run)
    wf.last_run_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(execute_workflow, run.id, wf.id, current_user.id, wf.config_json or {})
    return WorkflowRunResponse.from_orm_obj(run)


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunResponse])
async def list_runs(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """List execution runs for a workflow."""
    result = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.user_id == current_user.id,
        ).order_by(WorkflowRun.id.desc())
    )
    runs = result.scalars().all()
    return [WorkflowRunResponse.from_orm_obj(r) for r in runs]


@router.get("/run/{run_id}", response_model=WorkflowRunResponse)
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get execution run status and results."""
    result = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return WorkflowRunResponse.from_orm_obj(run)
