"""
维护工具API测试

测试系统维护和批量操作API端点
"""
import pytest
from httpx import AsyncClient
from fastapi import status


# ── 系统统计测试 ──────────────────────────────────────────────────

class TestMaintenanceStats:
    """测试系统统计端点"""

    @pytest.mark.asyncio
    async def test_get_system_stats_unauthorized(self, client: AsyncClient):
        """未认证访问应返回401"""
        response = await client.get("/api/maintenance/stats")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_system_stats_non_admin(self, client: AsyncClient, user_token: str):
        """非管理员访问应返回403"""
        response = await client.get(
            "/api/maintenance/stats",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_get_system_stats_admin(self, client: AsyncClient, admin_token: str):
        """管理员应能获取系统统计"""
        response = await client.get(
            "/api/maintenance/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "total_documents" in data
        assert "total_users" in data
        assert "total_tags" in data
        assert "db_size_mb" in data


# ── 健康检查测试 ──────────────────────────────────────────────────

class TestHealthCheck:
    """测试健康检查端点"""

    @pytest.mark.asyncio
    async def test_detailed_health_check(self, client: AsyncClient, admin_token: str):
        """测试详细健康检查"""
        response = await client.get(
            "/api/maintenance/health",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "timestamp" in data

        # 检查各个子系统
        checks = data["checks"]
        assert "database" in checks
        assert "disk" in checks
        assert "token_blacklist" in checks


# ── 数据清理测试 ──────────────────────────────────────────────────

class TestDataCleanup:
    """测试数据清理端点"""

    @pytest.mark.asyncio
    async def test_cleanup_data(self, client: AsyncClient, admin_token: str):
        """测试数据清理"""
        response = await client.post(
            "/api/maintenance/cleanup",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "clean_deleted_docs": True,
                "clean_old_versions": True,
                "version_keep_days": 30,
                "clean_orphan_tags": True,
            }
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "deleted_documents" in data
        assert "deleted_versions" in data
        assert "cleaned_orphan_tags" in data
        assert "freed_space_mb" in data


# ── 数据库备份测试 ──────────────────────────────────────────────────

class TestDatabaseBackup:
    """测试数据库备份端点"""

    @pytest.mark.asyncio
    async def test_backup_database(self, client: AsyncClient, admin_token: str):
        """测试数据库备份"""
        response = await client.post(
            "/api/maintenance/backup",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"backup_name": "test_backup"}
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "message" in data
        assert data["message"] == "备份成功"
        assert "backup_path" in data
        assert "backup_size_mb" in data

    @pytest.mark.asyncio
    async def test_list_backups(self, client: AsyncClient, admin_token: str):
        """测试列出备份"""
        response = await client.get(
            "/api/maintenance/backups",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "backups" in data
        assert isinstance(data["backups"], list)


# ── 数据库优化测试 ──────────────────────────────────────────────────

class TestDatabaseOptimization:
    """测试数据库优化端点"""

    @pytest.mark.asyncio
    async def test_optimize_database(self, client: AsyncClient, admin_token: str):
        """测试数据库优化"""
        response = await client.post(
            "/api/maintenance/optimize",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "message" in data
        assert "db_size_mb" in data


# ── 批量导出测试 ──────────────────────────────────────────────────

class TestBatchExport:
    """测试批量导出端点"""

    @pytest.mark.asyncio
    async def test_batch_export_empty(self, client: AsyncClient, user_token: str):
        """空文档列表应返回400"""
        response = await client.post(
            "/api/batch/export",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"document_ids": [], "format": "markdown"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_batch_export_invalid_format(self, client: AsyncClient, user_token: str):
        """无效格式应返回400"""
        response = await client.post(
            "/api/batch/export",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"document_ids": [1], "format": "invalid"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_batch_export_markdown(self, client: AsyncClient, user_token: str, test_document_id: int):
        """测试Markdown格式导出"""
        response = await client.post(
            "/api/batch/export",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"document_ids": [test_document_id], "format": "markdown"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/zip"


# ── 批量标签测试 ──────────────────────────────────────────────────

class TestBatchTags:
    """测试批量标签操作"""

    @pytest.mark.asyncio
    async def test_batch_tag_add(self, client: AsyncClient, user_token: str, test_document_id: int, test_tag_id: int):
        """测试批量添加标签"""
        response = await client.post(
            "/api/batch/tags",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "document_ids": [test_document_id],
                "tag_ids": [test_tag_id],
                "action": "add"
            }
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "affected_documents" in data
        assert "affected_tags" in data

    @pytest.mark.asyncio
    async def test_batch_tag_remove(self, client: AsyncClient, user_token: str, test_document_id: int, test_tag_id: int):
        """测试批量移除标签"""
        response = await client.post(
            "/api/batch/tags",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "document_ids": [test_document_id],
                "tag_ids": [test_tag_id],
                "action": "remove"
            }
        )
        assert response.status_code == status.HTTP_200_OK


# ── 批量状态更新测试 ──────────────────────────────────────────────────

class TestBatchStatus:
    """测试批量状态更新"""

    @pytest.mark.asyncio
    async def test_batch_update_status(self, client: AsyncClient, user_token: str, test_document_id: int):
        """测试批量状态更新"""
        response = await client.post(
            "/api/batch/status",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "document_ids": [test_document_id],
                "status": "published"
            }
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "updated_count" in data

    @pytest.mark.asyncio
    async def test_batch_update_invalid_status(self, client: AsyncClient, user_token: str, test_document_id: int):
        """无效状态应返回400"""
        response = await client.post(
            "/api/batch/status",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "document_ids": [test_document_id],
                "status": "invalid_status"
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── 批量移动测试 ──────────────────────────────────────────────────

class TestBatchMove:
    """测试批量移动"""

    @pytest.mark.asyncio
    async def test_batch_move_to_folder(self, client: AsyncClient, user_token: str, test_document_id: int, test_folder_id: int):
        """测试批量移动到文件夹"""
        response = await client.post(
            "/api/batch/move",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "document_ids": [test_document_id],
                "folder_id": test_folder_id
            }
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "moved_count" in data


# ── 批量删除测试 ──────────────────────────────────────────────────

class TestBatchDelete:
    """测试批量删除"""

    @pytest.mark.asyncio
    async def test_batch_soft_delete(self, client: AsyncClient, user_token: str, test_document_id: int):
        """测试批量软删除"""
        response = await client.post(
            "/api/batch/delete",
            headers={"Authorization": f"Bearer {user_token}"},
            json=[test_document_id]
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "deleted_count" in data


# ── 运行测试 ──────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
