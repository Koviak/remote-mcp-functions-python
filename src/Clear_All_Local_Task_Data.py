#!/usr/bin/env python3
"""
Utility to wipe all Annika/Planner task state from the shared Redis instance.

This removes every local task artifact so the MS-MCP sync can repopulate
directly from Microsoft Planner on the next run.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Set


def _bootstrap_redis_manager() -> None:
    """Ensure the Annika_2.0 repository is on sys.path for the Redis manager."""

    current_file = Path(__file__).resolve()
    repo_root = current_file.parents[1]
    candidate = repo_root.parent / "Annika_2.0"

    if not candidate.exists():
        raise RuntimeError(
            "Annika_2.0 repository not found next to remote-mcp-functions-python."
        )

    sys.path.insert(0, str(candidate))


_bootstrap_redis_manager()

from Redis_Master_Manager_Client import get_redis_client  # type: ignore


LOGGER = logging.getLogger("clear_local_task_data")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)


PATTERN_GROUPS: Dict[str, List[str]] = {
    "annika_task_records": ["annika:tasks:*"],
    "annika_task_mirrors": [
        "annika:conscious_state",
        "annika:consciousness:*:components:tasks",
        "annika:monitoring:latest",
        "annika:recent_conversations",
    ],
    "agent_outputs": ["annika:agent_outputs:*"],
    "planner_id_maps": [
        "annika:planner:id_map:*",
        "annika:task:mapping:planner:*",
    ],
    "planner_cached_tasks": [
        "annika:planner:tasks:*",
        "annika:planner:etag:*",
    ],
    "planner_sync_state": [
        "annika:sync:pending",
        "annika:sync:failed",
        "annika:sync:log",
        "annika:sync:health",
        "annika:sync:webhook_status",
        "annika:sync:last_upload:*",
    ],
    "task_pubsub_and_queues": [
        "annika:tasks:updates",
        "annika:tasks:assignments",
        "annika:tasks:completions",
        "annika:tasks:queue",
    ],
    "legacy": [
        "annika:consciousness:Global:components:tasks",
    ],
}


def collect_keys(client, pattern: str) -> Set[str]:
    """Gather every key matching the supplied pattern."""

    keys: Set[str] = set()
    for raw_key in client.scan_iter(match=pattern):
        key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
        keys.add(key)
    return keys


def delete_keys(client, keys: Iterable[str]) -> int:
    """Delete the provided keys using a pipeline for efficiency."""

    keys_list = list(keys)
    if not keys_list:
        return 0

    total_deleted = 0
    pipeline = client.pipeline(transaction=False)
    for key in keys_list:
        pipeline.delete(key)
    results = pipeline.execute()
    for deleted in results:
        try:
            total_deleted += int(deleted)
        except (TypeError, ValueError):
            continue
    return total_deleted


def verify_patterns_cleared(client, patterns: Iterable[str]) -> Dict[str, int]:
    """Return the number of keys remaining for each pattern."""

    leftovers: Dict[str, int] = {}
    for pattern in patterns:
        remaining = 0
        for _ in client.scan_iter(match=pattern):
            remaining += 1
            if remaining > 0:
                break
        leftovers[pattern] = remaining
    return leftovers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clear all Annika/Planner task data stored locally in Redis."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List keys that would be deleted without removing them.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = get_redis_client()

    summary: Dict[str, Dict[str, int]] = defaultdict(dict)
    total_keys = 0
    total_deleted = 0

    LOGGER.info("Starting Redis task cleanup%s", " (dry run)" if args.dry_run else "")

    for group_name, patterns in PATTERN_GROUPS.items():
        group_keys: Set[str] = set()
        for pattern in patterns:
            matched = collect_keys(client, pattern)
            summary[group_name][pattern] = len(matched)
            group_keys.update(matched)

        if not group_keys:
            continue

        total_keys += len(group_keys)
        LOGGER.info(
            "Group '%s': %s keys matched", group_name, len(group_keys)
        )

        if args.dry_run:
            for key in sorted(group_keys):
                LOGGER.debug("[DRY RUN] %s", key)
            continue

        deleted = delete_keys(client, group_keys)
        total_deleted += deleted
        LOGGER.info(
            "Group '%s': deleted %s keys (requested %s)",
            group_name,
            deleted,
            len(group_keys),
        )

    if args.dry_run:
        LOGGER.info("Dry run complete. No keys were removed.")
        for group_name, data in summary.items():
            LOGGER.info("%s -> %s", group_name, data)
        return

    LOGGER.info(
        "Cleanup complete. Deleted %s keys across %s groups.",
        total_deleted,
        len([g for g in summary if sum(summary[g].values()) > 0]),
    )

    critical_patterns = ["annika:tasks:*", "annika:planner:id_map:*", "annika:task:mapping:planner:*"]
    verification = verify_patterns_cleared(client, critical_patterns)
    if any(verification.values()):
        LOGGER.warning("Some task data remains: %s", verification)
    else:
        LOGGER.info("Verified: no residual task keys remain for critical patterns.")


if __name__ == "__main__":
    main()

