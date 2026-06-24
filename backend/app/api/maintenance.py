"""
系统维护工具API

提供数据清理、备份、系统诊断等维护功能
"""
import os
import shutil
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, AsyncSessionLocal
from app.core.deps import require_admin
from app.core.config import get_settings
from app.models.user import User
from app.models.document import Document, DocumentVersion
from app.models.api_endpoint import ApiEndpoint

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# ── Pydantic schemas ──────────────────────────────────────────

class CleanupRequest(BaseModel):
    """清理请求参数"""
    clean_deleted_docs: bool = True
    clean_old_versions: bool = True
    version_keep_days: int = 30
    clean_orphan_tags: bool = True


class BackupRequest(BaseModel):
    """备份请求参数"""
    backup_name: str = ""


class SystemStats(BaseModel):
    """系统统计信息"""
    total_documents: int
    total_users: int
    total_tags: int
    total_folders: int
    total_versions: int
    total_endpoints: int
    db_size_mb: float
    db_path: str
    uptime_info: str


class CleanupResult(BaseModel):
    """清理结果"""
    deleted_documents: int
    deleted_versions: int
    cleaned_orphan_tags: int
    freed_space_mb: float


# ── 系统诊断 ──────────────────────────────────────────────────

@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取系统统计信息"""
    # 统计各表记录数
    doc_count = (await db.execute(select(func.count(Document.id)))).scalar() or 0
    user_count = (await db.execute(select(func.count(User.id)))).scalar() or 0

    from app.models.document import Tag, Folder
    tag_count = (await db.execute(select(func.count(Tag.id)))).scalar() or 0
    folder_count = (await db.execute(select(func.count(Folder.id)))).scalar() or 0
    version_count = (await db.execute(select(func.count(DocumentVersion.id)))).scalar() or 0
    endpoint_count = (await db.execute(select(func.count(ApiEndpoint.id)))).scalar() or 0

    # 获取数据库大小
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    db_size_mb = 0.0
    if os.path.exists(db_path):
        db_size_mb = os.path.getsize(db_path) / (1024 * 1024)

    return SystemStats(
        total_documents=doc_count,
        total_users=user_count,
        total_tags=tag_count,
        total_folders=folder_count,
        total_versions=version_count,
        total_endpoints=endpoint_count,
        db_size_mb=round(db_size_mb, 2),
        db_path=db_path,
        uptime_info="运行中",
    )


# ── 数据清理 ──────────────────────────────────────────────────

@router.post("/cleanup", response_model=CleanupResult)
async def cleanup_data(
    request: CleanupRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """清理系统数据"""
    result = CleanupResult(
        deleted_documents=0,
        deleted_versions=0,
        cleaned_orphan_tags=0,
        freed_space_mb=0.0,
    )

    # 获取清理前的数据库大小
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    size_before = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    # 1. 清理已删除的文档（软删除超过30天的）
    if request.clean_deleted_docs:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        deleted_docs = await db.execute(
            select(Document).where(
                Document.status == "deleted",
                Document.updated_at < cutoff_date,
            )
        )
        docs_to_delete = deleted_docs.scalars().all()
        for doc in docs_to_delete:
            # 删除关联的版本
            await db.execute(
                select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
            )
            await db.delete(doc)
            result.deleted_documents += 1

    # 2. 清理旧版本
    if request.clean_old_versions:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=request.version_keep_days)
        old_versions = await db.execute(
            select(DocumentVersion).where(DocumentVersion.created_at < cutoff_date)
        )
        versions_to_delete = old_versions.scalars().all()
        for version in versions_to_delete:
            await db.delete(version)
            result.deleted_versions += 1

    # 3. 清理孤立标签
    if request.clean_orphan_tags:
        from app.models.document import Tag, document_tags
        # 找出没有关联文档的标签
        orphan_tags = await db.execute(
            select(Tag).where(
                ~Tag.id.in_(select(document_tags.c.tag_id).distinct())
            )
        )
        for tag in orphan_tags.scalars().all():
            await db.delete(tag)
            result.cleaned_orphan_tags += 1

    await db.commit()

    # 计算释放的空间
    if os.path.exists(db_path):
        size_after = os.path.getsize(db_path)
        result.freed_space_mb = round((size_before - size_after) / (1024 * 1024), 2)

    logger.info("数据清理完成: %s", result.model_dump())
    return result


# ── 数据库备份 ──────────────────────────────────────────────────

@router.post("/backup")
async def backup_database(
    request: BackupRequest,
    admin: User = Depends(require_admin),
):
    """备份数据库"""
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="数据库文件不存在")

    # 创建备份目录
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)

    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = request.backup_name or f"backup_{timestamp}"
    backup_path = backup_dir / f"{backup_name}.db"

    try:
        # 使用SQLite的VACUUM INTO进行在线备份
        import sqlite3
        source = sqlite3.connect(db_path)
        source.execute(f"VACUUM INTO '{backup_path}'")
        source.close()

        backup_size = os.path.getsize(backup_path) / (1024 * 1024)
        logger.info("数据库备份完成: %s (%.2f MB)", backup_path, backup_size)

        return {
            "message": "备份成功",
            "backup_path": str(backup_path),
            "backup_size_mb": round(backup_size, 2),
        }
    except Exception as e:
        logger.error("备份失败: %s", e)
        raise HTTPException(status_code=500, detail=f"备份失败: {str(e)}")


@router.get("/backups")
async def list_backups(
    admin: User = Depends(require_admin),
):
    """列出所有备份"""
    backup_dir = Path("backups")
    if not backup_dir.exists():
        return {"backups": []}

    backups = []
    for f in sorted(backup_dir.glob("*.db"), reverse=True):
        stat = f.stat()
        backups.append({
            "name": f.stem,
            "path": str(f),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        })

    return {"backups": backups}


# ── 数据库优化 ──────────────────────────────────────────────────

@router.post("/optimize")
async def optimize_database(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """优化数据库（VACUUM + ANALYZE）"""
    try:
        # 执行VACUUM压缩数据库
        await db.execute(text("VACUUM"))
        # 执行ANALYZE更新统计信息
        await db.execute(text("ANALYZE"))
        await db.commit()

        # 获取优化后的大小
        db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        db_size = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0

        logger.info("数据库优化完成")
        return {
            "message": "数据库优化完成",
            "db_size_mb": round(db_size, 2),
        }
    except Exception as e:
        logger.error("数据库优化失败: %s", e)
        raise HTTPException(status_code=500, detail=f"优化失败: {str(e)}")


# ── 系统健康检查 ──────────────────────────────────────────────────

@router.get("/health")
async def detailed_health_check(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """详细的系统健康检查"""
    checks = {}

    # 数据库连接检查
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "message": "连接正常"}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}

    # 磁盘空间检查
    try:
        db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        if os.path.exists(db_path):
            disk_usage = shutil.disk_usage(os.path.dirname(db_path))
            checks["disk"] = {
                "status": "ok" if disk_usage.free > 1024 * 1024 * 100 else "warning",
                "free_gb": round(disk_usage.free / (1024**3), 2),
                "total_gb": round(disk_usage.total / (1024**3), 2),
            }
    except Exception as e:
        checks["disk"] = {"status": "error", "message": str(e)}

    # LLM服务检查
    try:
        from app.services.llm_service import llm_service
        config = await llm_service._load_config()
        checks["llm"] = {
            "status": "ok",
            "provider": config.get("provider", "unknown"),
            "model": config.get("model", "unknown"),
        }
    except Exception as e:
        checks["llm"] = {"status": "warning", "message": str(e)}

    # API路由检查
    try:
        from app.services.api_router import api_router
        checks["api_router"] = {"status": "ok", "message": "已初始化"}
    except Exception as e:
        checks["api_router"] = {"status": "warning", "message": str(e)}

    # Token黑名单状态
    from app.core.security import get_blacklist_size
    checks["token_blacklist"] = {
        "status": "ok",
        "size": get_blacklist_size(),
    }

    overall_status = "ok"
    if any(c.get("status") == "error" for c in checks.values()):
        overall_status = "error"
    elif any(c.get("status") == "warning" for c in checks.values()):
        overall_status = "warning"

    return {
        "status": overall_status,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
