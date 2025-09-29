#!/usr/bin/env python3
"""Inspect application token roles and test Planner API access."""

from __future__ import annotations

import argparse
import base64
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Optional

import requests


def _bootstrap_annika_repo() -> None:
    _current = Path(__file__).resolve()
    _repo_root = _current.parents[1]
    sys.path.insert(0, str(_repo_root))
    _annika_root = None
    for depth in range(2, 6):
        candidate = _current.parents[depth] / "Annika_2.0"
        if candidate.exists():
            _annika_root = candidate
            break
    if _annika_root is None:
        raise RuntimeError("Annika_2.0 repository is required for diagnostics")
    sys.path.insert(0, str(_annika_root))


_bootstrap_annika_repo()

from Redis_Master_Manager_Client import get_redis_client  # noqa: E402  # type: ignore
from dual_auth_manager import get_application_token  # noqa: E402  # type: ignore


GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


def _urlsafe_b64decode(segment: str) -> Dict:
    padding = '=' * (-len(segment) % 4)
    decoded = base64.urlsafe_b64decode(segment + padding)
    return json.loads(decoded)


def decode_jwt(token: str) -> Dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Token is not a JWT")
    header = _urlsafe_b64decode(parts[0])
    payload = _urlsafe_b64decode(parts[1])
    return {"header": header, "payload": payload}


def test_planner_access(headers: Dict[str, str]) -> requests.Response:
    url = f"{GRAPH_API_ENDPOINT}/planner/plans?$top=1"
    response = requests.get(url, headers=headers, timeout=20)
    return response


def test_groups_access(headers: Dict[str, str]) -> requests.Response:
    url = f"{GRAPH_API_ENDPOINT}/groups?$top=1"
    response = requests.get(url, headers=headers, timeout=20)
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Check application token roles and Planner access")
    parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    token = get_application_token()
    if not token:
        logging.error("Failed to acquire application token")
        return

    decoded = decode_jwt(token)
    payload = decoded.get("payload", {})
    roles = payload.get("roles", [])
    logging.info("Application token roles: %s", roles)
    logging.info("AppId: %s", payload.get("appid"))
    logging.info("Tenant: %s", payload.get("tid"))

    headers = {"Authorization": f"Bearer {token}"}

    planner_response = test_planner_access(headers)
    logging.info(
        "Planner plans call status=%s body=%s",
        planner_response.status_code,
        planner_response.text[:500],
    )

    groups_response = test_groups_access(headers)
    logging.info(
        "Groups call status=%s body=%s",
        groups_response.status_code,
        groups_response.text[:500],
    )

    redis_client = get_redis_client()
    redis_client.set(
        "annika:diagnostics:last_app_roles",
        json.dumps({"roles": roles, "timestamp": payload.get("iat")}),
        ex=3600,
    )


if __name__ == "__main__":
    main()

