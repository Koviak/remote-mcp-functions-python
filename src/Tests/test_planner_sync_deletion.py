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
    sync._get_planner_task_with_etag = lambda *args, **kwargs: None

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
    sync._get_planner_task_with_etag = lambda *args, **kwargs: None

    await sync.redis_client.json().set("annika:tasks:Task-keep", "$", {
        "id": "Task-keep",
        "planner_etag": "etag-same",
        "last_modified_at": "2025-10-21T00:00:00Z",
    })

    uploads = []

    async def fake_queue(task):
        uploads.append(task["id"])

    sync._queue_upload = fake_queue

    # No Annika task for Task-2 → deletion path still runs
    await sync._detect_and_queue_changes()
    assert await sync.redis_client.get("annika:planner:id_map:Task-2") is None

    # Task with same ETag should be skipped
    await sync.redis_client.set("annika:planner:id_map:Task-keep", "planner-keep")
    await sync.redis_client.set("annika:planner:id_map:planner-keep", "Task-keep")
    await sync.redis_client.set("annika:planner:etag:planner-keep", "etag-same")
    await sync._detect_and_queue_changes()
    assert "Task-keep" not in uploads

    # Changed ETag should trigger upload
    await sync.redis_client.json().set("annika:tasks:Task-keep", "$", {
        "id": "Task-keep",
        "planner_etag": "etag-old",
        "last_modified_at": "2025-10-21T00:00:00Z",
    })
    await sync._detect_and_queue_changes()
    assert "Task-keep" in uploads


