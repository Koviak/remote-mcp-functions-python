import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import contact_sync_service as css  # noqa: E402  # type: ignore[import-not-found]


def test_validate_graph_delta_link_accepts_graph_url():
    url = "https://graph.microsoft.com/v1.0/me/contacts/delta?$deltatoken=abc"
    assert css.validate_graph_delta_link(url) is True


def test_validate_graph_delta_link_rejects_non_graph_url():
    url = "https://example.com/not-graph"
    assert css.validate_graph_delta_link(url) is False


def test_should_fallback_to_poll_when_no_delta_link():
    assert css.should_fallback_to_poll(None) is True
    assert css.should_fallback_to_poll("") is True
    assert css.should_fallback_to_poll("https://graph.microsoft.com/v1.0/me/contacts/delta?$deltatoken=abc") is False
