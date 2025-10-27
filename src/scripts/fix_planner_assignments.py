"""Retroactively fix Planner assignments and notes consistency.

Usage:
    python -m src.scripts.fix_planner_assignments --dry-run
    python -m src.scripts.fix_planner_assignments --limit 200

This script ensures each Annika task that syncs to Planner carries proper
human assignment metadata and has its reasoning/output reflected in the
Planner notes field. It can operate in dry run (default) or execute mode.
"""

from __future__ import annotations

import asyncio
import argparse
import json
import logging
from typing import Any, Dict, List, Optional

from Redis_Master_Manager_Client import get_async_redis_client, json_get, json_set

from annika_task_adapter import AnnikaTaskAdapter
from planner_sync_service_v5 import PlannerSyncServiceV5

logger = logging.getLogger(__name__)


async def _fetch_task(redis_client: Any, task_id: str) -> Optional[Dict[str, Any]]:
    key = f"annika:tasks:{task_id}"
    try:
        task_json = await json_get(redis_client, key)
        if not task_json:
            raw = await redis_client.get(key)
            if raw:
                return json.loads(raw)
        if isinstance(task_json, list) and len(task_json) == 1:
            task_json = task_json[0]
        if isinstance(task_json, dict):
            return task_json
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("Failed to load %s: %s", key, exc)
    return None


async def _save_task(redis_client: Any, task_id: str, task_data: Dict[str, Any]) -> None:
    key = f"annika:tasks:{task_id}"
    await json_set(redis_client, key, task_data)


async def _resolve_assignment(task: Dict[str, Any], adapter: AnnikaTaskAdapter) -> Dict[str, Any]:
    enriched_task = dict(task)
    human_meta = await adapter._resolve_human_assignment(
        enriched_task.get("assigned_to"),
        enriched_task.get("planner_plan_id"),
    )
    for key, value in human_meta.items():
        if value is not None:
            enriched_task[key] = value
    return enriched_task


async def repair_task(
    adapter: AnnikaTaskAdapter,
    sync_service: PlannerSyncServiceV5,
    redis_client: Any,
    task: Dict[str, Any],
    *,
    dry_run: bool,
) -> bool:
    task_id = task.get("id")
    if not task_id:
        return False

    planner_id = await sync_service._get_planner_id(task_id)
    if not planner_id:
        return False

    needs_update = False
    updated_task = dict(task)

    # Ensure human assignment metadata exists.
    enriched = await _resolve_assignment(updated_task, adapter)
    if enriched != updated_task:
        updated_task = enriched
        needs_update = True

    # Ensure reasoning cascades into notes via adapter mapping.
    reasoning_text = updated_task.get("reasoning")
    if reasoning_text and "[Reasoning]" not in (updated_task.get("notes") or ""):
        updated_task.setdefault("notes", "")
        needs_update = True

    if not needs_update:
        return False

    if dry_run:
        logger.info("DRY RUN: Would repair task %s (planner %s)", task_id, planner_id)
        return True

    await _save_task(redis_client, task_id, updated_task)
    await sync_service._queue_upload(updated_task)
    logger.info("Queued repair for task %s", task_id)
    return True


async def run(dry_run: bool, limit: Optional[int]) -> None:
    redis_client = await get_async_redis_client()
    adapter = AnnikaTaskAdapter(redis_client)
    sync_service = PlannerSyncServiceV5()
    await sync_service.start(redis_client=redis_client)

    cursor = 0
    processed = 0
    repaired = 0
    pattern = "annika:tasks:*"

    while True:
        cursor, keys = await redis_client.scan(cursor, match=pattern, count=200)
        for key in keys:
            task_id = key.split(":")[-1]
            task = await _fetch_task(redis_client, task_id)
            if not task:
                continue
            processed += 1
            try:
                repaired_flag = await repair_task(
                    adapter,
                    sync_service,
                    redis_client,
                    task,
                    dry_run=dry_run,
                )
            except Exception as exc:
                logger.error("Error repairing %s: %s", task_id, exc)
                continue
            if repaired_flag:
                repaired += 1
            if limit and processed >= limit:
                break
        if limit and processed >= limit:
            break
        if cursor == 0:
            break

    logger.info(
        "Processed %d tasks, repaired %d, dry_run=%s", processed, repaired, dry_run
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair Planner assignments/notes")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Scan and log repairs without persisting changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of tasks to inspect",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()

