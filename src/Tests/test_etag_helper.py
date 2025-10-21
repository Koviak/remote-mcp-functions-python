"""Tests for ETag-aware Planner task fetch helper."""

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planner_sync_service_v5 import WebhookDrivenPlannerSync


@pytest.mark.asyncio
async def test_get_planner_task_with_etag_behaviour(monkeypatch):
    sync = WebhookDrivenPlannerSync()

    class StubRedis:
        def __init__(self):
            self.cache = {}
            self.last_set = None

        async def get(self, key):
            return self.cache.get(key)

        async def set(self, key, value):
            self.cache[key] = value
            self.last_set = (key, value)

    stub_redis = StubRedis()
    stub_redis.cache["annika:planner:etag:sample"] = 'W/"etag-value"'
    sync.redis_client = stub_redis

    def fake_get_preferred_token():
        return "fake-token", "delegated"

    monkeypatch.setattr(sync, "_get_preferred_read_token", fake_get_preferred_token)

    class StubHTTP:
        def __init__(self):
            self.calls = []
            self.status_code = 304
            self.response_json = {}

        def get(self, url, headers=None, timeout=None):
            self.calls.append((url, headers))
            return types.SimpleNamespace(status_code=self.status_code, json=lambda: self.response_json)

    http = StubHTTP()
    sync.http = http

    # 304 short-circuit should return None and send If-None-Match header
    result = await sync._get_planner_task_with_etag("sample", expect_change=True)
    assert result is None
    assert http.calls[-1][1]["If-None-Match"] == 'W/"etag-value"'

    # 200 response should store new ETag and return payload
    http.status_code = 200
    http.response_json = {"@odata.etag": 'W/"new"', "id": "sample"}
    result = await sync._get_planner_task_with_etag("sample", expect_change=False)
    assert result["id"] == "sample"
    assert stub_redis.last_set == ("annika:planner:etag:sample", 'W/"new"')

    # Cached ETag updated; next request should use the updated value
    result = await sync._get_planner_task_with_etag("sample", expect_change=False)
    assert http.calls[-1][1]["If-None-Match"] == 'W/"new"'

    # No cached ETag: header should be absent
    stub_redis.cache.pop("annika:planner:etag:other", None)
    http.status_code = 200
    http.response_json = {"@odata.etag": 'W/"other"', "id": "other"}
    result = await sync._get_planner_task_with_etag("other", expect_change=False)
    assert "If-None-Match" not in http.calls[-1][1]
    assert stub_redis.last_set == ("annika:planner:etag:other", 'W/"other"')
