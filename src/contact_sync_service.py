"""Contact sync service primitives for webhook + delta/poll flows."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any, Optional

import httpx

from Redis_Master_Manager_Client import (
    get_async_redis_client,
    get_json_async,
    set_json_async,
)
from endpoints.common import (
    GRAPH_API_ENDPOINT,
    _get_token_and_base_for_me,
    build_json_headers,
)

logger = logging.getLogger(__name__)

CONTACTS_WEBHOOK_CHANNEL = "annika:contacts:webhook"
CONTACTS_UPDATES_CHANNEL = "annika:contacts:updates"
CONTACTS_INGEST_CHANNEL = "annika:contacts:ingest"
CONTACTS_SYNC_STATE_KEY = "annika:contacts:sync:state:microsoft:me"
CONTACTS_DELTA_STATE_KEY = "annika:contacts:sync:state:microsoft:me:delta"
CONTACTS_OUTBOX_MS_KEY = "annika:contacts:outbox:microsoft"
CONTACTS_DLQ_MS_KEY = "annika:contacts:dlq:microsoft"
CONTACTS_HEALTH_MS_KEY = "annika:contacts:sync:health:microsoft"
CONTACTS_LAST_UPLOAD_PREFIX = "annika:contacts:sync:last_upload:microsoft:"
CONTACTS_ID_MAP_PREFIX = "annika:contacts:id_map:"
CONTACTS_MS_REVERSE_PREFIX = "annika:contacts:mapping:microsoft:"
CONTACTS_PROCESSED_PREFIX = "annika:contacts:processed:"

DEFAULT_POLL_INTERVAL_SECONDS = 300
DEFAULT_OUTBOX_TTL_SECONDS = 14 * 24 * 60 * 60
DEFAULT_DLQ_TTL_SECONDS = 30 * 24 * 60 * 60
DEFAULT_MAX_RETRIES = 3


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Optional[str]) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    candidate = value
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def validate_graph_delta_link(url: Optional[str]) -> bool:
    """Validate delta links are Graph URLs only."""
    if not url or not isinstance(url, str):
        return False
    return url.startswith(f"{GRAPH_API_ENDPOINT}/")


def should_fallback_to_poll(delta_link: Optional[str]) -> bool:
    """Fallback to polling when there is no valid delta link."""
    return not validate_graph_delta_link(delta_link)


class ContactSyncService:
    """Webhook-first + delta-fallback contacts sync worker for Microsoft."""

    def __init__(self):
        self.redis_client: Optional[Any] = None
        self.running = False
        self._tasks: list[asyncio.Task] = []

    async def initialize(self) -> None:
        self.redis_client = await get_async_redis_client()
        if self.redis_client is None:
            raise RuntimeError("Redis client unavailable for contact sync service")
        await self.redis_client.ping()

    async def start(self) -> None:
        if self.running:
            return
        if self.redis_client is None:
            await self.initialize()
        self.running = True
        self._tasks.append(asyncio.create_task(self._webhook_loop()))
        self._tasks.append(asyncio.create_task(self._delta_poll_loop()))
        self._tasks.append(asyncio.create_task(self._microsoft_outbox_loop()))

    async def stop(self) -> None:
        self.running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _webhook_loop(self) -> None:
        """Consume contacts webhook notifications and normalize into ingest events."""
        if self.redis_client is None:
            return
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(CONTACTS_WEBHOOK_CHANNEL)
        try:
            while self.running:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if not message or message.get("type") != "message":
                    await asyncio.sleep(0.05)
                    continue
                raw_data = message.get("data")
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8", errors="replace")
                payload: dict[str, Any] = {}
                if isinstance(raw_data, str) and raw_data:
                    try:
                        payload = json.loads(raw_data)
                    except json.JSONDecodeError:
                        payload = {"raw": raw_data}
                await self._apply_webhook_payload(payload)
        finally:
            await pubsub.unsubscribe(CONTACTS_WEBHOOK_CHANNEL)
            await pubsub.close()

    async def _get_graph_token_and_base(self) -> tuple[Optional[str], Optional[str]]:
        try:
            token, base = _get_token_and_base_for_me("Contacts.ReadWrite")
        except Exception:
            return None, None
        return token, base

    async def _fetch_graph_contact(self, contact_id: str) -> Optional[dict[str, Any]]:
        token, base = await self._get_graph_token_and_base()
        if not token or not base:
            return None
        headers = build_json_headers(token)
        url = f"{GRAPH_API_ENDPOINT}{base}/contacts/{contact_id}"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, headers=headers)
        if response.status_code == 200:
            try:
                return response.json()
            except Exception:
                return None
        return None

    @staticmethod
    def _ms_contact_to_canonical_payload(
        contact: dict[str, Any],
        *,
        change_type: str,
        event_origin: str,
        event_timestamp: Optional[str] = None,
    ) -> dict[str, Any]:
        emails = []
        for entry in contact.get("emailAddresses") or []:
            address = str(entry.get("address", "")).strip().lower()
            if address:
                emails.append({"value": address, "type": "work", "is_primary": len(emails) == 0})

        phones = []
        for number in contact.get("businessPhones") or []:
            value = str(number).strip()
            if value:
                phones.append({"value": value, "type": "business", "is_primary": len(phones) == 0})

        mobile = str(contact.get("mobilePhone", "")).strip()
        if mobile:
            phones.append({"value": mobile, "type": "mobile", "is_primary": len(phones) == 0})

        for number in contact.get("homePhones") or []:
            value = str(number).strip()
            if value:
                phones.append({"value": value, "type": "home", "is_primary": len(phones) == 0})

        last_modified = (
            contact.get("lastModifiedDateTime")
            or event_timestamp
            or _utc_now()
        )
        microsoft_contact_id = contact.get("id")

        return {
            "display_name": contact.get("displayName"),
            "given_name": contact.get("givenName"),
            "family_name": contact.get("surname"),
            "phones": phones,
            "emails": emails,
            "company": contact.get("companyName"),
            "job_title": contact.get("jobTitle"),
            "notes": contact.get("personalNotes"),
            "source": "microsoft",
            "event_origin": event_origin,
            "last_modified_at": last_modified,
            "deleted": change_type == "deleted",
            "microsoft_contact_id": microsoft_contact_id,
        }

    async def _publish_ingest_event(
        self,
        *,
        event_id: str,
        payload: dict[str, Any],
    ) -> None:
        if self.redis_client is None:
            return
        event = {
            "provider": "microsoft",
            "event_id": event_id,
            "payload": payload,
        }
        await self.redis_client.publish(CONTACTS_INGEST_CHANNEL, json.dumps(event))

    async def _mark_event_processed(self, event_id: str) -> None:
        if self.redis_client is None:
            return
        await set_json_async(
            self.redis_client,
            f"{CONTACTS_PROCESSED_PREFIX}{event_id}",
            {"processed_at": _utc_now()},
            expire_seconds=24 * 60 * 60,
        )

    async def _is_event_processed(self, event_id: str) -> bool:
        if self.redis_client is None:
            return False
        payload = await get_json_async(self.redis_client, f"{CONTACTS_PROCESSED_PREFIX}{event_id}")
        return isinstance(payload, dict)

    @staticmethod
    def _build_event_id(payload: dict[str, Any]) -> str:
        contact_id = payload.get("contact_id") or payload.get("resource_data", {}).get("id")
        change_type = payload.get("change_type")
        subscription_id = payload.get("subscription_id")
        timestamp = payload.get("timestamp") or _utc_now()
        raw = f"{subscription_id}:{contact_id}:{change_type}:{timestamp}"
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()  # nosec B324
        return f"ms-webhook:{digest}"

    async def _apply_webhook_payload(self, payload: dict[str, Any]) -> None:
        if self.redis_client is None:
            return

        event_id = self._build_event_id(payload)
        if await self._is_event_processed(event_id):
            logger.debug("Skipping duplicate contact webhook event: %s", event_id)
            return

        change_type = str(payload.get("change_type", "updated")).lower()
        contact_id = str(payload.get("contact_id") or "").strip()
        event_timestamp = payload.get("timestamp")

        canonical_payload: Optional[dict[str, Any]] = None
        if change_type == "deleted":
            canonical_payload = {
                "phones": [],
                "emails": [],
                "source": "microsoft",
                "event_origin": "webhook",
                "last_modified_at": event_timestamp or _utc_now(),
                "deleted": True,
                "microsoft_contact_id": contact_id or None,
            }
        elif contact_id:
            contact_data = await self._fetch_graph_contact(contact_id)
            if contact_data:
                canonical_payload = self._ms_contact_to_canonical_payload(
                    contact_data,
                    change_type=change_type,
                    event_origin="webhook",
                    event_timestamp=event_timestamp,
                )

        if canonical_payload:
            await self._publish_ingest_event(event_id=event_id, payload=canonical_payload)

        state = {
            "last_event_at": _utc_now(),
            "last_event": payload,
            "last_event_id": event_id,
        }
        await set_json_async(self.redis_client, CONTACTS_SYNC_STATE_KEY, state)
        await self.redis_client.publish(CONTACTS_UPDATES_CHANNEL, json.dumps(state))
        await self._mark_event_processed(event_id)

    async def set_delta_cursor(self, delta_link: str) -> None:
        if self.redis_client is None:
            return
        if not validate_graph_delta_link(delta_link):
            return
        await set_json_async(
            self.redis_client,
            CONTACTS_DELTA_STATE_KEY,
            {"delta_link": delta_link, "updated_at": _utc_now()},
        )

    async def get_delta_cursor(self) -> Optional[str]:
        if self.redis_client is None:
            return None
        payload = await get_json_async(self.redis_client, CONTACTS_DELTA_STATE_KEY)
        if isinstance(payload, dict):
            value = payload.get("delta_link")
            if isinstance(value, str) and value:
                return value
        return None

    async def _delta_poll_loop(self) -> None:
        while self.running:
            try:
                await asyncio.sleep(DEFAULT_POLL_INTERVAL_SECONDS)
                await self._run_delta_poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Contact delta poll loop error: %s", exc)

    async def _run_delta_poll_once(self) -> None:
        if self.redis_client is None:
            return
        token, base = await self._get_graph_token_and_base()
        if not token or not base:
            return

        delta_link = await self.get_delta_cursor()
        if should_fallback_to_poll(delta_link):
            url = f"{GRAPH_API_ENDPOINT}{base}/contacts/delta"
        else:
            url = delta_link or f"{GRAPH_API_ENDPOINT}{base}/contacts/delta"

        headers = build_json_headers(token)
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, headers=headers)

        if response.status_code != 200:
            logger.warning("Contacts delta poll failed: %s", response.status_code)
            return

        body = response.json()
        for item in body.get("value", []):
            is_deleted = isinstance(item.get("@removed"), dict)
            change_type = "deleted" if is_deleted else "updated"
            webhook_shape = {
                "change_type": change_type,
                "contact_id": item.get("id"),
                "subscription_id": "delta-poll",
                "timestamp": _utc_now(),
            }
            if is_deleted:
                await self._apply_webhook_payload(webhook_shape)
            else:
                canonical_payload = self._ms_contact_to_canonical_payload(
                    item,
                    change_type=change_type,
                    event_origin="poll",
                )
                event_id = f"ms-delta:{item.get('id')}:{canonical_payload.get('last_modified_at')}"
                await self._publish_ingest_event(
                    event_id=event_id,
                    payload=canonical_payload,
                )
                await self._mark_event_processed(event_id)

        next_cursor = body.get("@odata.deltaLink") or body.get("@odata.nextLink")
        if isinstance(next_cursor, str) and validate_graph_delta_link(next_cursor):
            await self.set_delta_cursor(next_cursor)

    async def _json_list_get(self, key: str) -> list[dict[str, Any]]:
        if self.redis_client is None:
            return []
        payload = await get_json_async(self.redis_client, key)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    async def _json_list_set(self, key: str, value: list[dict[str, Any]], ttl: int) -> None:
        if self.redis_client is None:
            return
        await set_json_async(self.redis_client, key, value, expire_seconds=ttl)

    async def _outbox_pop_due(self, key: str, batch_size: int) -> list[dict[str, Any]]:
        queue = await self._json_list_get(key)
        if not queue:
            return []
        now = datetime.now(timezone.utc)
        due: list[dict[str, Any]] = []
        remaining: list[dict[str, Any]] = []
        for item in queue:
            if len(due) >= batch_size:
                remaining.append(item)
                continue
            next_retry_at = item.get("next_retry_at")
            if next_retry_at and _parse_iso(next_retry_at) > now:
                remaining.append(item)
                continue
            due.append(item)
        await self._json_list_set(key, remaining, DEFAULT_OUTBOX_TTL_SECONDS)
        return due

    async def _outbox_push(self, operation: dict[str, Any]) -> None:
        queue = await self._json_list_get(CONTACTS_OUTBOX_MS_KEY)
        queue.append(dict(operation))
        await self._json_list_set(CONTACTS_OUTBOX_MS_KEY, queue, DEFAULT_OUTBOX_TTL_SECONDS)

    async def _dlq_push(self, operation: dict[str, Any]) -> None:
        dlq = await self._json_list_get(CONTACTS_DLQ_MS_KEY)
        dlq.append(dict(operation))
        if len(dlq) > 1000:
            dlq = dlq[-1000:]
        await self._json_list_set(CONTACTS_DLQ_MS_KEY, dlq, DEFAULT_DLQ_TTL_SECONDS)

    @staticmethod
    def _canonical_to_ms_payload(contact_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "displayName": contact_payload.get("display_name") or "",
            "givenName": contact_payload.get("given_name") or "",
            "surname": contact_payload.get("family_name") or "",
            "companyName": contact_payload.get("company") or "",
            "jobTitle": contact_payload.get("job_title") or "",
            "businessPhones": [
                str(phone.get("value")).strip()
                for phone in (contact_payload.get("phones") or [])
                if isinstance(phone, dict) and str(phone.get("value", "")).strip()
            ],
            "emailAddresses": [
                {"address": str(email.get("value")).strip().lower()}
                for email in (contact_payload.get("emails") or [])
                if isinstance(email, dict) and str(email.get("value", "")).strip()
            ],
            "personalNotes": contact_payload.get("notes") or "",
        }

    async def _upsert_microsoft_mapping(
        self,
        *,
        canonical_contact_id: str,
        microsoft_contact_id: str,
    ) -> None:
        if self.redis_client is None:
            return
        id_map_key = f"{CONTACTS_ID_MAP_PREFIX}{canonical_contact_id}"
        existing = await get_json_async(self.redis_client, id_map_key)
        if not isinstance(existing, dict):
            existing = {
                "contact_id": canonical_contact_id,
                "google_resource_name": None,
            }
        existing["microsoft_contact_id"] = microsoft_contact_id
        existing["updated_at"] = _utc_now()
        await set_json_async(self.redis_client, id_map_key, existing)
        await self.redis_client.set(
            f"{CONTACTS_MS_REVERSE_PREFIX}{microsoft_contact_id}",
            canonical_contact_id,
        )

    async def _execute_microsoft_operation(self, operation: dict[str, Any]) -> tuple[bool, Optional[str]]:
        token, base = await self._get_graph_token_and_base()
        if not token or not base:
            return False, "delegated_token_unavailable"

        contact_id = str(operation.get("contact_id", "")).strip()
        payload = operation.get("payload") or {}
        op_name = str(operation.get("operation", "upsert")).lower()
        headers = build_json_headers(token)
        ms_contact_id = payload.get("microsoft_contact_id")

        async with httpx.AsyncClient(timeout=20) as client:
            if op_name == "delete":
                if not ms_contact_id:
                    return True, None
                response = await client.delete(
                    f"{GRAPH_API_ENDPOINT}{base}/contacts/{ms_contact_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if response.status_code in {204, 404}:
                    return True, None
                return False, f"delete_failed:{response.status_code}"

            body = self._canonical_to_ms_payload(payload)
            if ms_contact_id:
                response = await client.patch(
                    f"{GRAPH_API_ENDPOINT}{base}/contacts/{ms_contact_id}",
                    headers=headers,
                    json=body,
                )
                if response.status_code == 200:
                    if self.redis_client is not None:
                        await self.redis_client.set(
                            f"{CONTACTS_LAST_UPLOAD_PREFIX}{contact_id}",
                            _utc_now(),
                        )
                    return True, None
                return False, f"patch_failed:{response.status_code}"

            response = await client.post(
                f"{GRAPH_API_ENDPOINT}{base}/contacts",
                headers=headers,
                json=body,
            )
            if response.status_code == 201:
                created = response.json()
                created_id = created.get("id")
                if created_id and contact_id:
                    await self._upsert_microsoft_mapping(
                        canonical_contact_id=contact_id,
                        microsoft_contact_id=created_id,
                    )
                    if self.redis_client is not None:
                        await self.redis_client.set(
                            f"{CONTACTS_LAST_UPLOAD_PREFIX}{contact_id}",
                            _utc_now(),
                        )
                return True, None
            return False, f"create_failed:{response.status_code}"

    async def _update_health(self, *, delivered: int = 0, failed: int = 0, retried: int = 0, dlq: int = 0) -> None:
        if self.redis_client is None:
            return
        existing = await get_json_async(self.redis_client, CONTACTS_HEALTH_MS_KEY)
        if not isinstance(existing, dict):
            existing = {
                "provider": "microsoft",
                "delivered": 0,
                "failed": 0,
                "retried": 0,
                "dlq": 0,
            }
        existing["delivered"] = int(existing.get("delivered", 0)) + max(delivered, 0)
        existing["failed"] = int(existing.get("failed", 0)) + max(failed, 0)
        existing["retried"] = int(existing.get("retried", 0)) + max(retried, 0)
        existing["dlq"] = int(existing.get("dlq", 0)) + max(dlq, 0)
        existing["updated_at"] = _utc_now()
        await set_json_async(self.redis_client, CONTACTS_HEALTH_MS_KEY, existing)

    async def _microsoft_outbox_loop(self) -> None:
        while self.running:
            try:
                ops = await self._outbox_pop_due(CONTACTS_OUTBOX_MS_KEY, batch_size=20)
                if not ops:
                    await asyncio.sleep(1.0)
                    continue

                delivered = 0
                failed = 0
                retried = 0
                dlq = 0
                for op in ops:
                    ok, error = await self._execute_microsoft_operation(op)
                    if ok:
                        delivered += 1
                        continue

                    failed += 1
                    retry_count = int(op.get("retry_count", 0)) + 1
                    if retry_count <= DEFAULT_MAX_RETRIES:
                        retried += 1
                        delay_seconds = min(2 ** min(retry_count, 8), 300)
                        op["retry_count"] = retry_count
                        op["next_retry_at"] = (
                            datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                        ).isoformat().replace("+00:00", "Z")
                        op["last_error"] = error
                        await self._outbox_push(op)
                    else:
                        dlq += 1
                        op["failed_at"] = _utc_now()
                        op["last_error"] = error
                        await self._dlq_push(op)

                await self._update_health(
                    delivered=delivered,
                    failed=failed,
                    retried=retried,
                    dlq=dlq,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Microsoft outbox loop error: %s", exc)
                await asyncio.sleep(1.0)

    async def get_sync_state(self) -> Optional[dict[str, Any]]:
        if self.redis_client is None:
            await self.initialize()
        if self.redis_client is None:
            return None
        data = await get_json_async(self.redis_client, CONTACTS_SYNC_STATE_KEY)
        if isinstance(data, dict):
            return data
        return None
