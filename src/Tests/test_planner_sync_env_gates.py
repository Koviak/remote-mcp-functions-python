import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from planner_sync_service_v5 import WebhookDrivenPlannerSync


def test_env_master_switch_disables_both_directions(monkeypatch):
    monkeypatch.setenv("PLANNER_SYNC_ENABLED", "false")
    monkeypatch.setenv("PLANNER_SYNC_FROM_PLANNER_ENABLED", "true")
    monkeypatch.setenv("PLANNER_SYNC_TO_PLANNER_ENABLED", "true")

    service = WebhookDrivenPlannerSync()

    assert service.planner_sync_master_enabled is False
    assert service.planner_sync_enabled is False
    assert service.from_planner_sync_enabled is False
    assert service.to_planner_sync_enabled is False
    assert service.polling_enabled is False


def test_directional_env_switches_can_disable_outbound_only(monkeypatch):
    monkeypatch.setenv("PLANNER_SYNC_ENABLED", "true")
    monkeypatch.setenv("PLANNER_SYNC_FROM_PLANNER_ENABLED", "true")
    monkeypatch.setenv("PLANNER_SYNC_TO_PLANNER_ENABLED", "false")

    service = WebhookDrivenPlannerSync()

    assert service.planner_sync_enabled is True
    assert service.from_planner_sync_enabled is True
    assert service.to_planner_sync_enabled is False


@pytest.mark.asyncio
async def test_initial_sync_returns_early_when_planner_sync_disabled(monkeypatch):
    monkeypatch.setenv("PLANNER_SYNC_ENABLED", "false")

    service = WebhookDrivenPlannerSync()
    service.redis_client = AsyncMock()
    service._queue_upload = AsyncMock()
    service._poll_all_planner_tasks = AsyncMock()

    await service._initial_sync()

    service._queue_upload.assert_not_awaited()
    service._poll_all_planner_tasks.assert_not_awaited()


@pytest.mark.asyncio
async def test_queue_upload_is_noop_when_outbound_sync_disabled(monkeypatch):
    monkeypatch.setenv("PLANNER_SYNC_ENABLED", "true")
    monkeypatch.setenv("PLANNER_SYNC_TO_PLANNER_ENABLED", "false")

    service = WebhookDrivenPlannerSync()
    service.pending_uploads = []

    await service._queue_upload({"id": "Task-123", "title": "Should not upload"})

    assert service.pending_uploads == []


@pytest.mark.asyncio
async def test_poll_all_planner_tasks_returns_disabled_when_inbound_sync_disabled(
    monkeypatch,
):
    monkeypatch.setenv("PLANNER_SYNC_ENABLED", "true")
    monkeypatch.setenv("PLANNER_SYNC_FROM_PLANNER_ENABLED", "false")

    service = WebhookDrivenPlannerSync()

    result = await service._poll_all_planner_tasks()

    assert result == {
        "checked": 0,
        "created": 0,
        "updated": 0,
        "disabled": True,
    }
