"""Plugin management API — list, install, uninstall, toggle workflow plugins."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.api.auth import get_current_user_dep
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


# ── Response Schemas ──

class PluginManifestResponse(BaseModel):
    id: str
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    category: str
    icon: str
    color: str
    node_type: str
    configurable: bool
    config_schema: Optional[dict] = None
    is_builtin: bool
    is_compatible: bool
    compatibility_message: str
    is_active: bool
    error: Optional[str] = None
    permissions: list[str]
    changelog: dict[str, str]


class PluginListResponse(BaseModel):
    plugins: list[PluginManifestResponse]
    total: int
    compatible: int
    system_version: str


class PluginInstallResponse(BaseModel):
    plugin_id: str
    name: str
    version: str
    message: str


class PluginActionResponse(BaseModel):
    plugin_id: str
    message: str


# ── Endpoints ──


@router.get("", response_model=PluginListResponse)
async def list_plugins(
    current_user: User = Depends(get_current_user_dep),
):
    """List all loaded plugins with their manifests and status."""
    from app.services.plugin_loader import plugin_loader
    from app.core.version import SYSTEM_VERSION

    manifests = plugin_loader.get_all_manifests()
    compatible_count = sum(1 for m in manifests if m["is_active"])

    return PluginListResponse(
        plugins=[PluginManifestResponse(**m) for m in manifests],
        total=len(manifests),
        compatible=compatible_count,
        system_version=SYSTEM_VERSION,
    )


@router.get("/{plugin_id}", response_model=PluginManifestResponse)
async def get_plugin(
    plugin_id: str,
    current_user: User = Depends(get_current_user_dep),
):
    """Get details for a specific plugin."""
    from app.services.plugin_loader import plugin_loader

    manifests = plugin_loader.get_all_manifests()
    for m in manifests:
        if m["plugin_id"] == plugin_id:
            return PluginManifestResponse(**m)

    raise HTTPException(404, f"Plugin not found: {plugin_id}")


@router.post("/install", response_model=PluginInstallResponse)
async def install_plugin(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_dep),
):
    """Install a third-party plugin from a .kbplugin (zip) file.

    Admin only.
    """
    if not current_user.is_admin:
        raise HTTPException(403, "仅管理员可安装插件")

    if not file.filename or not file.filename.endswith(".kbplugin"):
        raise HTTPException(400, "请上传 .kbplugin 格式的插件文件")

    MAX_PLUGIN_SIZE = 50 * 1024 * 1024  # 50 MB
    if file.size and file.size > MAX_PLUGIN_SIZE:
        raise HTTPException(status_code=413, detail="插件文件过大（最大 50 MB）")

    from app.services.plugin_loader import plugin_loader
    import tempfile
    import shutil

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".kbplugin") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        plugin = plugin_loader.install_from_zip(tmp_path)
        return PluginInstallResponse(
            plugin_id=plugin.manifest.id,
            name=plugin.manifest.name,
            version=plugin.manifest.version,
            message=f"插件 {plugin.manifest.name} v{plugin.manifest.version} 安装成功",
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/{plugin_id}/uninstall", response_model=PluginActionResponse)
async def uninstall_plugin(
    plugin_id: str,
    current_user: User = Depends(get_current_user_dep),
):
    """Uninstall a third-party plugin. Cannot uninstall builtins.

    Admin only.
    """
    if not current_user.is_admin:
        raise HTTPException(403, "仅管理员可卸载插件")

    from app.services.plugin_loader import plugin_loader

    try:
        success = plugin_loader.uninstall(plugin_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not success:
        raise HTTPException(404, f"Plugin not found: {plugin_id}")

    return PluginActionResponse(
        plugin_id=plugin_id,
        message=f"插件 {plugin_id} 已卸载",
    )


@router.post("/reload", response_model=PluginListResponse)
async def reload_plugins(
    current_user: User = Depends(get_current_user_dep),
):
    """Force reload all plugins from disk. Admin only."""
    if not current_user.is_admin:
        raise HTTPException(403, "仅管理员可重载插件")

    from app.services.plugin_loader import plugin_loader
    from app.core.version import SYSTEM_VERSION

    plugin_loader.reload()

    manifests = plugin_loader.get_all_manifests()
    compatible_count = sum(1 for m in manifests if m["is_active"])

    return PluginListResponse(
        plugins=[PluginManifestResponse(**m) for m in manifests],
        total=len(manifests),
        compatible=compatible_count,
        system_version=SYSTEM_VERSION,
    )


@router.get("/{plugin_id}/versions")
async def get_plugin_versions(
    plugin_id: str,
    current_user: User = Depends(get_current_user_dep),
):
    """Check available versions for a plugin (marketplace integration stub).

    Currently returns only the installed version. Future: fetch from remote registry.
    """
    from app.services.plugin_loader import plugin_loader

    plugin = plugin_loader.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(404, f"Plugin not found: {plugin_id}")

    return {
        "plugin_id": plugin_id,
        "installed_version": plugin.manifest.version,
        "available_versions": [],  # Stub for marketplace
        "has_update": False,
    }
