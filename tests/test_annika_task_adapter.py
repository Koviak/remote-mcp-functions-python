from __future__ import annotations

import json
from typing import Dict

import pytest

try:
    from src.annika_task_adapter import AnnikaTaskAdapter  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - local execution fallback
    from annika_task_adapter import AnnikaTaskAdapter  # type: ignore


class FakeRedisClient:
    """Minimal Redis stub that supports JSON.GET/SET and metadata caching."""

    def __init__(self) -> None:
        self.storage: Dict[str, str] = {}

    async def execute_command(self, command: str, key: str, *args, **kwargs):
        command = command.upper()
        if command == "JSON.SET":
            payload = args[-1]
            self.storage[key] = payload
            return True
        if command == "JSON.GET":
            payload = self.storage.get(key)
            if payload is None:
                return None
            return json.loads(payload)
        raise NotImplementedError(f"Command {command} not supported in FakeRedisClient")

    async def expire(self, key: str, seconds: int):
        return True


@pytest.mark.asyncio
async def test_planner_metadata_fields_preserved():
    """planner_to_annika should populate canonical Planner metadata fields."""
    fake_redis = FakeRedisClient()
    adapter = AnnikaTaskAdapter(fake_redis)

    planner_task = {
        "id": "MsPlannerTask01",
        "title": "Review Operating Agreement",
        "notes": "Checklist pending",
        "priority": 3,
        "percentComplete": 25,
        "planId": "Plan-Alpha",
        "bucketId": "Bucket-123",
        "orderHint": "8584611890668289492P!",
        "assignments": {},
    }

    # Seed bucket metadata in fake Redis cache to emulate populated metadata manager
    bucket_metadata_key = "annika:graph:buckets:Bucket-123"
    fake_redis.storage[bucket_metadata_key] = json.dumps(
        {
            "id": "Bucket-123",
            "name": "Execution",
            "orderHint": "12345P!",
        }
    )

    annika_task = await adapter.planner_to_annika(planner_task)

    assert annika_task["planner_id"] == "MsPlannerTask01"
    assert annika_task["planner_plan_id"] == "Plan-Alpha"
    assert annika_task["plan_id"] == "Plan-Alpha"
    assert annika_task["planner_bucket_id"] == "Bucket-123"
    assert annika_task["bucket_id"] == "Bucket-123"
    assert annika_task["planner_bucket_name"] == "Execution"
    assert annika_task["planner_bucket_order_hint"] == "12345P!"
