#!/usr/bin/env python3
"""Compare Planner visibility between delegated and application tokens."""

from __future__ import annotations

import argparse
import logging
from typing import Dict, Iterable, List, Optional

import requests

from load_env import load_env
from dual_auth_manager import get_dual_auth_manager


GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def fetch_all_pages(url: Optional[str], headers: Dict[str, str]) -> List[Dict]:
    """Retrieve all paginated results for the given Graph endpoint."""

    results: List[Dict] = []
    while url:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            logging.warning("Graph request failed: %s %s", response.status_code, response.text)
            break
        data = response.json()
        page = data.get("value", [])
        if isinstance(page, list):
            results.extend(page)
        url = data.get("@odata.nextLink")
    return results


def count_plan_tasks(plan_id: str, headers: Dict[str, str]) -> int:
    """Count tasks within a Planner plan."""

    total = 0
    url = f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks?$select=id&$top=50"
    while url:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            logging.warning(
                "Failed to list tasks for plan %s: %s %s",
                plan_id,
                response.status_code,
                response.text,
            )
            break
        payload = response.json()
        total += len(payload.get("value", []))
        url = payload.get("@odata.nextLink")
    return total


def plans_with_delegated(token: str) -> List[Dict[str, str]]:
    """Collect Planner plans visible with delegated permissions."""

    headers = {"Authorization": f"Bearer {token}"}
    plans: List[Dict[str, str]] = []

    # Personal plans
    personal = fetch_all_pages(
        f"{GRAPH_API_ENDPOINT}/me/planner/plans?$select=id,title&$top=100",
        headers,
    )
    for item in personal:
        plans.append(
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "source": "personal",
            }
        )

    # Group-based plans
    groups = fetch_all_pages(
        f"{GRAPH_API_ENDPOINT}/me/memberOf?$select=id,displayName,@odata.type&$top=999",
        headers,
    )
    for group in groups:
        if group.get("@odata.type") != "#microsoft.graph.group":
            continue
        group_id = group.get("id")
        if not group_id:
            continue
        group_plans = fetch_all_pages(
            f"{GRAPH_API_ENDPOINT}/groups/{group_id}/planner/plans?$select=id,title&$top=100",
            headers,
        )
        for plan in group_plans:
            plans.append(
                {
                    "id": plan.get("id", ""),
                    "title": plan.get("title", ""),
                    "source": f"group:{group_id}",
                }
            )

    return [p for p in plans if p["id"]]


def plans_with_application(token: str) -> List[Dict[str, str]]:
    """Collect Planner plans visible with application permissions."""

    headers = {"Authorization": f"Bearer {token}"}
    plans = fetch_all_pages(
        f"{GRAPH_API_ENDPOINT}/planner/plans?$select=id,title,owner&$top=100",
        headers,
    )
    output: List[Dict[str, str]] = []
    for plan in plans:
        output.append(
            {
                "id": plan.get("id", ""),
                "title": plan.get("title", ""),
                "source": plan.get("owner", "tenant"),
            }
        )
    return [p for p in output if p["id"]]


def annotate_task_counts(plans: Iterable[Dict[str, str]], token: str) -> List[Dict[str, str]]:
    headers = {"Authorization": f"Bearer {token}"}
    annotated: List[Dict[str, str]] = []
    for plan in plans:
        task_total = count_plan_tasks(plan["id"], headers)
        annotated.append({**plan, "task_count": task_total})
    return annotated


def summarize(label: str, plans: List[Dict[str, str]]) -> None:
    logging.info("%s: %s plans visible", label, len(plans))
    total_tasks = sum(p.get("task_count", 0) for p in plans)
    logging.info("%s: %s total tasks across visible plans", label, total_tasks)
    for plan in plans:
        logging.info(
            "%s plan %s | title=%s | tasks=%s",
            label,
            plan.get("id"),
            plan.get("title", ""),
            plan.get("task_count", 0),
        )


def run_comparison() -> None:
    load_env()
    manager = get_dual_auth_manager()

    delegated_token = manager.get_token("delegated")
    if not delegated_token:
        logging.error("Unable to acquire delegated token; aborting comparison")
        return

    app_token = manager.get_token("application")
    if not app_token:
        logging.warning("Unable to acquire application token; skipping app-only comparison")

    delegated_plans = annotate_task_counts(plans_with_delegated(delegated_token), delegated_token)
    summarize("Delegated", delegated_plans)

    if app_token:
        app_plans = annotate_task_counts(plans_with_application(app_token), app_token)
        summarize("Application", app_plans)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Planner visibility via delegated and application tokens"
    )
    parser.parse_args()
    setup_logging()
    run_comparison()


if __name__ == "__main__":
    main()

