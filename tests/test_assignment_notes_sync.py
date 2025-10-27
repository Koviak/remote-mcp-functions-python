import pytest

from annika_task_adapter import AnnikaTaskAdapter
from annika_task_adapter import USER_NAME_MAP
from planner_sync_service_v5 import PlannerSyncServiceV5


def test_annika_to_planner_assignments_and_notes(monkeypatch):
    adapter = AnnikaTaskAdapter(redis_client=None)  # type: ignore[arg-type]

    task_payload = {
        "id": "Task-CV-planner-001-001",
        "title": "Test Planner Payload",
        "description": "Description",
        "notes": "Internal notes",
        "output": "Agent output",
        "reasoning": "[Doctrine] Reasoning block",
        "assigned_to_human_id": "user-123",
        "assigned_to": "Test User",
    }

    monkeypatch.setitem(USER_NAME_MAP, "Test User", "user-123")

    planner_payload = adapter.annika_to_planner(task_payload)

    assert "assignments" in planner_payload
    assert "notes" in planner_payload
    assert "[Reasoning]" in planner_payload["notes"]


def test_queue_upload_called_for_repair(monkeypatch):
    service = PlannerSyncServiceV5()

    uploaded_ids = []

    async def fake_queue(task):
        uploaded_ids.append(task.get("id"))

    monkeypatch.setattr(service, "_queue_upload", fake_queue)
    service.processing_upload.add("Task-CV-abc-001-001")

    assert "Task-CV-abc-001-001" in service.processing_upload

