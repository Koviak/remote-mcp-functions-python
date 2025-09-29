#!/usr/bin/env python3
"""Report counts for all task-related Redis keys."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Iterable, Tuple


def _bootstrap_annika_repo() -> None:
    """Ensure Annika_2.0 repository is importable for Redis manager."""

    current = Path(__file__).resolve()
    # Look for Annika repo within two levels up
    annika_root: Optional[Path] = None
    for depth in range(2, 5):
        candidate = current.parents[depth] / "Annika_2.0"
        if candidate.exists():
            annika_root = candidate
            break
    if annika_root is None:
        raise RuntimeError(
            "Annika_2.0 repository not found near remote-mcp-functions-python."
        )
    sys.path.insert(0, str(annika_root))


try:
    _bootstrap_annika_repo()
    from Redis_Master_Manager_Client import get_redis_client  # type: ignore  # noqa: E402
except Exception as bootstrap_error:
    raise RuntimeError("Unable to import Redis_Master_Manager_Client; ensure Annika_2.0 repository is present.") from bootstrap_error


PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("annika:tasks:{id}", "annika:tasks:*"),
    ("annika:planner:id_map", "annika:planner:id_map:*"),
    ("annika:task:mapping:planner", "annika:task:mapping:planner:*"),
    ("annika:planner:tasks", "annika:planner:tasks:*"),
    ("annika:planner:etag", "annika:planner:etag:*"),
    ("annika:sync:pending", "annika:sync:pending"),
    ("annika:sync:failed", "annika:sync:failed"),
    ("annika:sync:last_upload", "annika:sync:last_upload:*"),
    ("annika:sync:log", "annika:sync:log"),
    ("annika:tasks:updates (channel backlog)", "annika:tasks:updates"),
    ("annika:agent_outputs", "annika:agent_outputs:*"),
    ("annika:conscious_state", "annika:conscious_state"),
    ("annika:consciousness:*:components:tasks", "annika:consciousness:*:components:tasks"),
    ("annika:graph:users", "annika:graph:users:*"),
    ("annika:graph:groups", "annika:graph:groups:*"),
    ("annika:graph:plans", "annika:graph:plans:*"),
    ("annika:graph:buckets", "annika:graph:buckets:*"),
    ("annika:planner:plan_choice", "annika:planner:plan_choice:*"),
    ("annika:planner:inaccessible_plans", "annika:planner:inaccessible_plans"),
)


def count_pattern(client, pattern: str) -> int:
    """Return number of keys matching the pattern."""

    if "*" not in pattern and "?" not in pattern and "[" not in pattern:
        return 1 if client.exists(pattern) else 0

    total = 0
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor=cursor, match=pattern, count=500)
        total += len(keys)
        if cursor == 0:
            break
    return total


def gather_counts() -> Dict[str, int]:
    client = get_redis_client()
    counts: Dict[str, int] = {}
    for label, pattern in PATTERNS:
        counts[label] = count_pattern(client, pattern)
    return counts


def display_counts(counts: Dict[str, int]) -> None:
    header = ("Key Pattern", "Count")
    width = max(len(header[0]), *(len(label) for label in counts))
    logging.info("%s | %s", header[0].ljust(width), header[1])
    logging.info("%s-+-%s", "-" * width, "-" * len(header[1]))
    for label, value in counts.items():
        logging.info("%s | %s", label.ljust(width), value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Display counts for task-related Redis keys"
    )
    parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    counts = gather_counts()
    display_counts(counts)


if __name__ == "__main__":
    main()

