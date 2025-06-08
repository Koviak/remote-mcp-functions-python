import os
import sys
import pytest
import fakeredis.aioredis
import respx

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from planner_sync_service_v5 import (
    WebhookDrivenPlannerSync,
    GRAPH_API_ENDPOINT,
)
import agent_auth_manager

@pytest.mark.asyncio
async def test_delete_planner_task_removes_mapping(monkeypatch):
    sync = WebhookDrivenPlannerSync()
    sync.redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    sync.adapter = None

    await sync.redis_client.set("annika:planner:id_map:Task-1", "p1")
    await sync.redis_client.set("annika:planner:id_map:p1", "Task-1")

    monkeypatch.setattr(agent_auth_manager, "get_agent_token", lambda: "dummy")
    monkeypatch.setattr("planner_sync_service_v5.get_agent_token", lambda: "dummy")

    with respx.mock(assert_all_called=True) as mock:
        mock.delete(f"{GRAPH_API_ENDPOINT}/planner/tasks/p1").respond(204)
        result = await sync._delete_planner_task("p1")

    assert result is True
    assert await sync.redis_client.get("annika:planner:id_map:Task-1") is None
    assert await sync.redis_client.get("annika:planner:id_map:p1") is None


@pytest.mark.asyncio
async def test_detect_and_queue_changes_handles_deleted_tasks(monkeypatch):
    sync = WebhookDrivenPlannerSync()
    sync.redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    sync.adapter = None

    await sync.redis_client.set("annika:planner:id_map:Task-2", "p2")
    await sync.redis_client.set("annika:planner:id_map:p2", "Task-2")

    monkeypatch.setattr(agent_auth_manager, "get_agent_token", lambda: "dummy")
    monkeypatch.setattr("planner_sync_service_v5.get_agent_token", lambda: "dummy")

    async def fake_get_all():
        return []

    class FakeAdapter:
        async def get_all_annika_tasks(self):
            return []
    sync.adapter = FakeAdapter()

    called = {}

    async def fake_delete(planner_id):
        called["id"] = planner_id
        return True

    sync._delete_planner_task = fake_delete

    await sync._detect_and_queue_changes()

    assert called.get("id") == "p2"
    assert await sync.redis_client.get("annika:planner:id_map:Task-2") is None
    assert await sync.redis_client.get("annika:planner:id_map:p2") is None


