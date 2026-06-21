"""Tests for Workflows API: CRUD, templates, execution, triggers, schedule."""

import pytest


async def _login(client, username="admin", password="test-admin-password-123"):
    await client.get("/api/health")
    resp = await client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Templates ───────────────────────────────────────────────────────────

class TestWorkflowTemplates:

    @pytest.mark.asyncio
    async def test_list_templates(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.get("/api/workflows/templates", headers=headers)
        assert resp.status_code == 200
        templates = resp.json()
        assert len(templates) >= 5
        keys = [t["key"] for t in templates]
        assert "batch_polish" in keys
        assert "summarize_tag" in keys
        assert "batch_translate" in keys

    @pytest.mark.asyncio
    async def test_template_has_required_fields(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.get("/api/workflows/templates", headers=headers)
        for t in resp.json():
            assert "key" in t
            assert "name" in t
            assert "nodes" in t
            assert "edges" in t
            assert len(t["nodes"]) > 0

    @pytest.mark.asyncio
    async def test_create_from_template(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/workflows/from-template", json={
            "template_key": "batch_polish",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["template_type"] == "preset"
        assert data["name"] == "批量润色"
        assert "nodes" in data["config_json"]

    @pytest.mark.asyncio
    async def test_create_from_invalid_template(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/workflows/from-template", json={
            "template_key": "nonexistent",
        }, headers=headers)
        assert resp.status_code == 400


# ── CRUD ────────────────────────────────────────────────────────────────

class TestWorkflowCRUD:

    @pytest.mark.asyncio
    async def test_create_custom_workflow(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/workflows", json={
            "name": "My Workflow",
            "description": "Custom test",
            "template_type": "custom",
            "config_json": {"nodes": [{"id": "n1", "type": "source", "label": "Src"}], "edges": []},
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Workflow"
        assert data["template_type"] == "custom"

    @pytest.mark.asyncio
    async def test_list_workflows(self, async_client):
        headers = await _login(async_client)
        await async_client.post("/api/workflows", json={
            "name": "WF1", "config_json": {"nodes": [], "edges": []},
        }, headers=headers)
        await async_client.post("/api/workflows", json={
            "name": "WF2", "config_json": {"nodes": [], "edges": []},
        }, headers=headers)
        resp = await async_client.get("/api/workflows", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    @pytest.mark.asyncio
    async def test_get_single_workflow(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/workflows", json={
            "name": "Get Me", "config_json": {"nodes": [], "edges": []},
        }, headers=headers)
        wf_id = create.json()["id"]
        resp = await async_client.get(f"/api/workflows/{wf_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    @pytest.mark.asyncio
    async def test_get_nonexistent_workflow(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.get("/api/workflows/99999", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_workflow(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/workflows", json={
            "name": "Original", "config_json": {"nodes": [], "edges": []},
        }, headers=headers)
        wf_id = create.json()["id"]
        resp = await async_client.put(f"/api/workflows/{wf_id}", json={
            "name": "Updated",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    @pytest.mark.asyncio
    async def test_soft_delete_workflow(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/workflows", json={
            "name": "To Delete", "config_json": {"nodes": [], "edges": []},
        }, headers=headers)
        wf_id = create.json()["id"]
        resp = await async_client.delete(f"/api/workflows/{wf_id}", headers=headers)
        assert resp.status_code == 200

        # Should not appear in list
        list_resp = await async_client.get("/api/workflows", headers=headers)
        assert all(w["id"] != wf_id for w in list_resp.json())

    @pytest.mark.asyncio
    async def test_delete_nonexistent_workflow(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.delete("/api/workflows/99999", headers=headers)
        assert resp.status_code == 404


# ── Execution ───────────────────────────────────────────────────────────

class TestWorkflowExecution:

    @pytest.mark.asyncio
    async def test_execute_workflow_creates_run(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/workflows/from-template", json={
            "template_key": "batch_polish",
        }, headers=headers)
        wf_id = create.json()["id"]

        resp = await async_client.post("/api/workflows/execute", json={
            "workflow_id": wf_id,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow_id"] == wf_id
        assert data["status"] in ("pending", "running")

    @pytest.mark.asyncio
    async def test_execute_nonexistent_workflow(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/workflows/execute", json={
            "workflow_id": 99999,
        }, headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_runs(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/workflows/from-template", json={
            "template_key": "batch_polish",
        }, headers=headers)
        wf_id = create.json()["id"]

        await async_client.post("/api/workflows/execute", json={"workflow_id": wf_id}, headers=headers)

        resp = await async_client.get(f"/api/workflows/{wf_id}/runs", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_get_run_detail(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/workflows/from-template", json={
            "template_key": "batch_polish",
        }, headers=headers)
        wf_id = create.json()["id"]

        exec_resp = await async_client.post("/api/workflows/execute", json={
            "workflow_id": wf_id,
        }, headers=headers)
        run_id = exec_resp.json()["id"]

        resp = await async_client.get(f"/api/workflows/run/{run_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == run_id


# ── Quick Execute ───────────────────────────────────────────────────────

class TestQuickExecute:

    @pytest.mark.asyncio
    async def test_quick_execute_success(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/workflows/quick-execute", json={
            "template_key": "batch_polish",
            "filter": "all",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] in ("pending", "running")

    @pytest.mark.asyncio
    async def test_quick_execute_invalid_template(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/workflows/quick-execute", json={
            "template_key": "nonexistent",
        }, headers=headers)
        assert resp.status_code == 400


# ── Schedule ────────────────────────────────────────────────────────────

class TestWorkflowSchedule:

    @pytest.mark.asyncio
    async def test_set_schedule(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/workflows", json={
            "name": "Scheduled", "config_json": {"nodes": [], "edges": []},
        }, headers=headers)
        wf_id = create.json()["id"]

        resp = await async_client.put(f"/api/workflows/{wf_id}/schedule", json={
            "schedule_json": {"cron": "0 9 * * *", "enabled": True},
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["schedule_json"]["cron"] == "0 9 * * *"

    @pytest.mark.asyncio
    async def test_clear_schedule(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/workflows", json={
            "name": "Clear Sched", "config_json": {"nodes": [], "edges": []},
        }, headers=headers)
        wf_id = create.json()["id"]

        await async_client.put(f"/api/workflows/{wf_id}/schedule", json={
            "schedule_json": {"cron": "0 9 * * *", "enabled": True},
        }, headers=headers)

        resp = await async_client.put(f"/api/workflows/{wf_id}/schedule", json={
            "schedule_json": None,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["schedule_json"] is None


# ── Triggers ────────────────────────────────────────────────────────────

class TestWorkflowTriggers:

    @pytest.mark.asyncio
    async def test_set_trigger(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/workflows", json={
            "name": "Triggered", "config_json": {"nodes": [], "edges": []},
        }, headers=headers)
        wf_id = create.json()["id"]

        resp = await async_client.put(f"/api/workflows/{wf_id}/trigger", json={
            "trigger_type": "on_import",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["trigger_type"] == "on_import"

    @pytest.mark.asyncio
    async def test_invalid_trigger_type(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/workflows", json={
            "name": "Bad Trigger", "config_json": {"nodes": [], "edges": []},
        }, headers=headers)
        wf_id = create.json()["id"]

        resp = await async_client.put(f"/api/workflows/{wf_id}/trigger", json={
            "trigger_type": "invalid_type",
        }, headers=headers)
        assert resp.status_code == 400
