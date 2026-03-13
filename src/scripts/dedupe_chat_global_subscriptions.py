#!/usr/bin/env python3
"""Dedupe /me/chats/getAllMessages subscriptions and ensure one active global sub."""

import asyncio
import logging
import sys
from pathlib import Path


def _configure_path() -> None:
    """Allow running from repo root or src/scripts directory."""
    current = Path(__file__).resolve()
    src_dir = current.parents[1]
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


async def main() -> int:
    _configure_path()
    import load_env  # noqa: F401
    from chat_subscription_manager import chat_subscription_manager

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger = logging.getLogger("dedupe_chat_global_subscriptions")

    await chat_subscription_manager.initialize()

    kept = await chat_subscription_manager.ensure_single_global_chat_subscription()
    if kept:
        logger.info(
            "[PASS] Kept subscription id=%s clientState=%s expires=%s",
            kept.get("id"),
            kept.get("clientState"),
            kept.get("expirationDateTime"),
        )
    else:
        logger.info("[WARN] No existing global chat subscription found")

    ensured = await chat_subscription_manager.subscribe_to_all_existing_chats()
    if ensured:
        logger.info("[PASS] Global chat subscription is active")
    else:
        logger.error("[FAIL] Could not ensure active global chat subscription")
        return 1

    health = await chat_subscription_manager.get_subscription_health()
    logger.info("[PASS] Local subscription health: %s", health)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)
