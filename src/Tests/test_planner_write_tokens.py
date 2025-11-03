import pytest

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from planner_sync_service_v5 import WebhookDrivenPlannerSync


@pytest.fixture
def planner_service(monkeypatch):
    """Provide a Planner sync instance with patched token helpers."""

    service = WebhookDrivenPlannerSync()

    # Ensure each test starts with known token choice state
    service.last_write_token_choice = "delegated"

    yield service


def test_get_preferred_write_token_prefers_application(monkeypatch, planner_service):
    calls = {"application": 0, "delegated": 0}

    def fake_application_token():
        calls["application"] += 1
        return "app-token"

    def fake_agent_token(scope=""):
        calls["delegated"] += 1
        return "delegated-token"

    monkeypatch.setattr("planner_sync_service_v5.get_application_token", fake_application_token)
    monkeypatch.setattr("planner_sync_service_v5.get_agent_token", fake_agent_token)

    token, token_type = planner_service._get_preferred_write_token()

    assert token == "app-token"
    assert token_type == "application"
    assert planner_service.last_write_token_choice == "application"
    assert calls["application"] == 1
    assert calls["delegated"] == 0


def test_get_preferred_write_token_falls_back_to_delegated(monkeypatch, planner_service):
    calls = {"application": 0, "delegated": 0, "scope": None}

    def fake_application_token():
        calls["application"] += 1
        return None

    def fake_agent_token(scope=""):
        calls["delegated"] += 1
        calls["scope"] = scope
        return "delegated-token"

    monkeypatch.setattr("planner_sync_service_v5.get_application_token", fake_application_token)
    monkeypatch.setattr("planner_sync_service_v5.get_agent_token", fake_agent_token)

    token, token_type = planner_service._get_preferred_write_token()

    assert token == "delegated-token"
    assert token_type == "delegated"
    assert planner_service.last_write_token_choice == "delegated"
    assert calls["application"] == 1
    assert calls["delegated"] == 1
    assert calls["scope"] == "Tasks.ReadWrite"

