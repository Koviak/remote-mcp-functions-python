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


def test_annika_adapter_sanitizes_unicode_dash_datetime():
    adapter = AnnikaTaskAdapter(redis_client=None)
    adapter.metadata_manager = None

    payload = adapter.annika_to_planner(
        {
            "id": "Task-unicode-datetime",
            "title": "Unicode datetime",
            "start_date": "2026\u201102\u201124 18:56:29",
        }
    )

    assert payload["startDateTime"] == "2026-02-24T18:56:29Z"


def test_annika_adapter_drops_invalid_datetime_fields():
    adapter = AnnikaTaskAdapter(redis_client=None)
    adapter.metadata_manager = None

    payload = adapter.annika_to_planner(
        {
            "id": "Task-invalid-datetime",
            "title": "Invalid datetime",
            "start_date": "2026-02-24",
            "due_date": "2026-99-99",
        }
    )

    assert payload["startDateTime"] == "2026-02-24T00:00:00Z"
    assert "dueDateTime" not in payload


@pytest.mark.asyncio
async def test_annika_checklist_titles_trim_to_graph_limit():
    adapter = AnnikaTaskAdapter(redis_client=None)

    checklist = await adapter.annika_subtasks_to_planner_checklist(
        "Task-parent",
        inline_subtasks=[{"id": "s1", "title": "A" * 140}],
    )

    first_item = next(iter(checklist.values()))
    assert len(first_item["title"]) == 100

