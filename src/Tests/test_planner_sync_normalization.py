import json

import pytest
import fakeredis.aioredis

from planner_sync_service_v5 import ETAG_PREFIX, WebhookDrivenPlannerSync


@pytest.mark.asyncio
async def test_normalize_json_key_converts_legacy_string():
    sync = WebhookDrivenPlannerSync()
    sync.redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    key = "annika:tasks:Task-legacy-json"
    legacy_payload = {"id": "Task-legacy-json", "title": "Legacy"}
    await sync.redis_client.set(key, json.dumps(legacy_payload))

    normalized = await sync._normalize_json_key(key)
    assert normalized is True

    stored = await sync._redis_json_get(key)
    assert stored["title"] == "Legacy"


@pytest.mark.asyncio
async def test_normalize_json_key_wraps_plain_string():
    sync = WebhookDrivenPlannerSync()
    sync.redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    key = "annika:tasks:Task-legacy-plain"
    await sync.redis_client.set(key, "notes only")

    normalized = await sync._normalize_json_key(key)
    assert normalized is True
    stored = await sync._redis_json_get(key)
    assert stored == {"value": "notes only"}


@pytest.mark.asyncio
async def test_redis_json_set_overwrites_wrongtype_key():
    sync = WebhookDrivenPlannerSync()
    sync.redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    key = "annika:planner:tasks:Task-legacy"
    await sync.redis_client.set(key, "legacy")

    await sync._redis_json_set(key, {"id": "Task-legacy", "status": "open"})
    result = await sync._redis_json_get(key)
    assert result["status"] == "open"


def test_ensure_planner_title_uses_task_identifier():
    sync = WebhookDrivenPlannerSync()
    annika_task = {"id": "Task-123", "title": ""}
    planner_payload = {"title": None}

    sync._ensure_planner_title(annika_task, planner_payload)

    assert planner_payload["title"] == "Task-123"


def test_ensure_planner_title_preserves_existing_title():
    sync = WebhookDrivenPlannerSync()
    annika_task = {"id": "Task-789", "title": "  Research "}
    planner_payload = {"title": "Deep Dive"}

    sync._ensure_planner_title(annika_task, planner_payload)

    assert planner_payload["title"] == "Deep Dive"


@pytest.mark.asyncio
async def test_store_planner_snapshot_persists_without_ttl():
    sync = WebhookDrivenPlannerSync()
    sync.redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    planner_task = {
        "id": "planner-123",
        "title": "Rehydrate cache",
        "@odata.etag": "etag-123",
    }

    await sync._store_planner_snapshot(planner_task)

    stored = await sync._redis_json_get("annika:planner:tasks:planner-123")
    assert stored["title"] == "Rehydrate cache"

    ttl = await sync.redis_client.ttl("annika:planner:tasks:planner-123")
    assert ttl == -1
    assert await sync.redis_client.get(f"{ETAG_PREFIX}planner-123") == "etag-123"

