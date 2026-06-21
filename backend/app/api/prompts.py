"""Prompt template CRUD and execution endpoints."""

import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.api.auth import get_current_user_dep
from app.models.user import User
from app.models.prompt_template import PromptTemplate

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "custom"
    system_prompt: str
    input_variables: list[str] = []
    output_format: str = "text"
    is_public: bool = False


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    system_prompt: Optional[str] = None
    input_variables: Optional[list[str]] = None
    output_format: Optional[str] = None
    is_public: Optional[bool] = None


class TemplateExecute(BaseModel):
    variables: dict = {}
    input_text: str = ""


def _template_to_dict(t: PromptTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "system_prompt": t.system_prompt,
        "input_variables": t.input_variables or [],
        "output_format": t.output_format,
        "is_public": t.is_public,
        "usage_count": t.usage_count,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("/templates")
async def list_templates(
    category: str = "",
    current_user: User = Depends(get_current_user_dep),
):
    """List user's prompt templates, optionally filtered by category."""
    async with AsyncSessionLocal() as session:
        query = select(PromptTemplate).where(
            (PromptTemplate.user_id == current_user.id) | (PromptTemplate.is_public == True)
        )
        if category:
            query = query.where(PromptTemplate.category == category)
        query = query.order_by(PromptTemplate.usage_count.desc(), PromptTemplate.updated_at.desc())
        result = await session.execute(query)
        templates = result.scalars().all()
        return [_template_to_dict(t) for t in templates]


@router.post("/templates")
async def create_template(
    data: TemplateCreate,
    current_user: User = Depends(get_current_user_dep),
):
    """Create a new prompt template."""
    async with AsyncSessionLocal() as session:
        template = PromptTemplate(
            user_id=current_user.id,
            name=data.name,
            description=data.description,
            category=data.category,
            system_prompt=data.system_prompt,
            input_variables=data.input_variables,
            output_format=data.output_format,
            is_public=data.is_public,
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        return _template_to_dict(template)


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user_dep),
):
    """Get a single prompt template."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PromptTemplate).where(PromptTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(404, "模板不存在")
        if template.user_id != current_user.id and not template.is_public:
            raise HTTPException(403, "无权访问此模板")
        return _template_to_dict(template)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    data: TemplateUpdate,
    current_user: User = Depends(get_current_user_dep),
):
    """Update a prompt template."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PromptTemplate).where(
                PromptTemplate.id == template_id,
                PromptTemplate.user_id == current_user.id,
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(404, "模板不存在或无权修改")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(template, field, value)

        await session.commit()
        await session.refresh(template)
        return _template_to_dict(template)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user_dep),
):
    """Delete a prompt template."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PromptTemplate).where(
                PromptTemplate.id == template_id,
                PromptTemplate.user_id == current_user.id,
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(404, "模板不存在或无权删除")
        await session.delete(template)
        await session.commit()
        return {"success": True}


@router.post("/templates/{template_id}/execute")
async def execute_template(
    template_id: int,
    data: TemplateExecute,
    current_user: User = Depends(get_current_user_dep),
):
    """Execute a prompt template with variable substitution. Returns the interpolated prompt."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PromptTemplate).where(PromptTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(404, "模板不存在")
        if template.user_id != current_user.id and not template.is_public:
            raise HTTPException(403, "无权访问此模板")

        # Variable interpolation
        prompt = template.system_prompt
        for key, value in data.variables.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))

        # Replace {text} with input_text if present
        if data.input_text:
            prompt = prompt.replace("{text}", data.input_text)

        # Increment usage count
        template.usage_count += 1
        await session.commit()

        return {
            "prompt": prompt,
            "template_name": template.name,
            "output_format": template.output_format,
        }
