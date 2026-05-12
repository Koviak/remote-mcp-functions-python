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



@pytest.mark.asyncio
async def test_self_heal_stale_bucket_fields_clears_bucket_ids_and_sets_updated_at():
    sync = WebhookDrivenPlannerSync()
    sync.redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    task_id = "Task-bucket-heal"
    key = f"annika:tasks:{task_id}"
    await sync._redis_json_set(
        key,
        {
            "id": task_id,
            "title": "Bucket cleanup",
            "planner_bucket_id": "bucket-stale",
            "bucket_id": "bucket-stale",
        },
    )

    annika_task = {
        "id": task_id,
        "planner_bucket_id": "bucket-stale",
        "bucket_id": "bucket-stale",
    }

    await sync._self_heal_stale_bucket_fields(
        annika_task,
        bucket_id="bucket-stale",
        plan_id="plan-1",
        reason="unit_test",
    )

    healed = await sync._redis_json_get(key)
    assert "planner_bucket_id" not in healed
    assert "bucket_id" not in healed
    assert "updated_at" in healed
    assert "planner_bucket_id" not in annika_task
    assert "bucket_id" not in annika_task


@pytest.mark.asyncio
async def test_create_planner_task_drops_invalid_bucket_and_triggers_self_heal(monkeypatch):
    sync = WebhookDrivenPlannerSync()
    sync.redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    class _Adapter:
        def annika_to_planner(self, _task):
            return {"title": "Demo", "bucketId": "bucket-stale"}

    class _Resp:
        def __init__(self, status_code, payload=None, headers=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.headers = headers or {}

        def json(self):
            return self._payload

    class _Http:
        def __init__(self):
            self.last_post_json = None

        def get(self, url, headers=None, timeout=10):
            if "/buckets" in url:
                return _Resp(200, {"value": [{"id": "bucket-valid"}]})
            return _Resp(500, {})

        def post(self, url, headers=None, json=None, timeout=10):
            self.last_post_json = json
            return _Resp(201, {"id": "planner-1", "@odata.etag": "etag-1"})

    heal_calls = []

    async def _fake_heal(task, *, bucket_id, plan_id, reason):
        heal_calls.append({"task": task.get("id"), "bucket_id": bucket_id, "plan_id": plan_id, "reason": reason})

    async def _noop(*args, **kwargs):
        return None

    sync.adapter = _Adapter()
    sync.http = _Http()

    monkeypatch.setattr(sync, "_get_preferred_write_token", lambda: ("token", "application"))
    monkeypatch.setattr(sync, "_determine_plan_for_task", _noop)
    monkeypatch.setattr(sync, "_self_heal_stale_bucket_fields", _fake_heal)
    monkeypatch.setattr(sync, "_store_id_mapping", _noop)
    monkeypatch.setattr(sync, "_store_etag", _noop)
    monkeypatch.setattr(sync, "_mark_task_synced", _noop)
    monkeypatch.setattr(sync, "_log_sync_operation", _noop)
    monkeypatch.setattr(sync, "_has_checklist_payload", lambda _task: False)

    async def _plan(_task):
        return "plan-1"

    monkeypatch.setattr(sync, "_determine_plan_for_task", _plan)

    annika_task = {"id": "Task-create", "title": "Create test", "planner_bucket_id": "bucket-stale"}
    ok = await sync._create_planner_task(annika_task)

    assert ok is True
    assert sync.http.last_post_json is not None
    assert "bucketId" not in sync.http.last_post_json
    assert heal_calls and heal_calls[0]["reason"] == "create_invalid_bucket"


@pytest.mark.asyncio
async def test_update_planner_task_drops_invalid_bucket_and_triggers_self_heal(monkeypatch):
    sync = WebhookDrivenPlannerSync()
    sync.redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    class _Adapter:
        def annika_to_planner(self, _task):
            return {"title": "Demo", "bucketId": "bucket-stale", "planId": "ignored-on-update"}

    class _Resp:
        def __init__(self, status_code, payload=None, headers=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.headers = headers or {}

        def json(self):
            return self._payload

    class _Http:
        def __init__(self):
            self.last_patch_json = None

        def get(self, url, headers=None, timeout=10):
            if "/planner/tasks/" in url:
                return _Resp(200, {"@odata.etag": "etag-current", "planId": "plan-1"})
            if "/buckets" in url:
                return _Resp(200, {"value": [{"id": "bucket-valid"}]})
            return _Resp(500, {})

        def patch(self, url, headers=None, json=None, timeout=10):
            self.last_patch_json = json
            return _Resp(200, {}, {"ETag": "etag-new"})

    heal_calls = []

    async def _fake_heal(task, *, bucket_id, plan_id, reason):
        heal_calls.append({"task": task.get("id"), "bucket_id": bucket_id, "plan_id": plan_id, "reason": reason})

    async def _noop(*args, **kwargs):
        return None

    sync.adapter = _Adapter()
    sync.http = _Http()

    monkeypatch.setattr(sync, "_get_preferred_write_token", lambda: ("token", "application"))
    monkeypatch.setattr(sync, "_self_heal_stale_bucket_fields", _fake_heal)
    monkeypatch.setattr(sync, "_store_etag", _noop)
    monkeypatch.setattr(sync, "_mark_task_synced", _noop)
    monkeypatch.setattr(sync, "_log_sync_operation", _noop)
    monkeypatch.setattr(sync, "_has_checklist_payload", lambda _task: False)

    annika_task = {"id": "Task-update", "title": "Update test", "planner_bucket_id": "bucket-stale"}
    ok = await sync._update_planner_task("planner-1", annika_task)

    assert ok is True
    assert sync.http.last_patch_json is not None
    assert "bucketId" not in sync.http.last_patch_json
    assert heal_calls and heal_calls[0]["reason"] == "update_invalid_bucket"

