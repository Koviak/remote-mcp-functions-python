import pytest

from planner_sync_service_v5 import WebhookDrivenPlannerSync
from annika_task_adapter import AnnikaTaskAdapter


def test_annika_adapter_adjusts_due_before_start():
    adapter = AnnikaTaskAdapter(redis_client=None)
    adapter.metadata_manager = None  # prevent metadata lookups during test

    payload = adapter.annika_to_planner(
        {
            "id": "Task-datetime",
            "title": "Schedule Safety",
            "start_date": "2025-11-05T12:00:00Z",
            "due_date": "2025-11-04",
        }
    )

    assert payload["startDateTime"] == "2025-11-05T12:00:00Z"
    assert payload["dueDateTime"] == "2025-11-05T12:00:00Z"


def test_planner_schedule_bounds_adjusts_due_with_update_payload():
    sync_service = WebhookDrivenPlannerSync()
    payload = {
        "startDateTime": "2025-11-05T12:00:00Z",
        "dueDateTime": "2025-11-04T00:00:00Z",
    }

    sync_service._ensure_planner_schedule_bounds(payload, task_id="Task-update")

    assert payload["dueDateTime"] == "2025-11-05T12:00:00Z"


def test_planner_schedule_bounds_uses_current_task_start_when_missing():
    sync_service = WebhookDrivenPlannerSync()
    payload = {"dueDateTime": "2025-11-04T00:00:00Z"}
    current_task = {"startDateTime": "2025-11-05T12:00:00Z"}

    sync_service._ensure_planner_schedule_bounds(
        payload,
        current_task=current_task,
        task_id="Task-existing",
    )

    assert payload["dueDateTime"] == "2025-11-05T12:00:00Z"
