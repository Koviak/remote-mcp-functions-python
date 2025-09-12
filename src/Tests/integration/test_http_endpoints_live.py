import json
import importlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests  # type: ignore


class _RouteCapturingApp:
    def __init__(self) -> None:
        self.routes: List[Tuple[str, Tuple[str, ...]]] = []

    def route(self, route: str, methods: List[str], **_kwargs):
        def decorator(func):
            self.routes.append((route, tuple(methods)))
            return func
        return decorator


def _discover_routes() -> List[Tuple[str, Tuple[str, ...]]]:
    http_mod = importlib.import_module("http_endpoints")
    token_mod = importlib.import_module("token_api_endpoints")

    register_http_endpoints = getattr(http_mod, "register_http_endpoints")
    register_token_api_endpoints = getattr(
        token_mod, "register_token_api_endpoints"
    )

    app = _RouteCapturingApp()
    register_http_endpoints(app)  # type: ignore[arg-type]
    register_token_api_endpoints(app)  # type: ignore[arg-type]
    return app.routes


def _load_manifest() -> Dict[str, Any]:
    manifest_path = Path(__file__).parent / "endpoints_manifest.json"
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _base_url(manifest: Dict[str, Any]) -> str:
    return manifest.get("base_url", "http://localhost:7071/api").rstrip("/")


def _timeout(manifest: Dict[str, Any]) -> int:
    return int(manifest.get("timeout_seconds", 20))


def _should_test_write(manifest: Dict[str, Any]) -> bool:
    return bool(manifest.get("test_writes", False))


def _skip_routes(manifest: Dict[str, Any]) -> List[str]:
    return list(manifest.get("skip_routes", []))


def _resolve_path_params(
    route: str, manifest: Dict[str, Any], samples: Dict[str, str]
) -> Optional[str]:
    path_params = manifest.get("path_params", {})
    resolved = route
    placeholders: List[str] = []

    i = 0
    while i < len(resolved):
        if resolved[i] == "{" and "}" in resolved[i:]:
            j = resolved.index("}", i)
            placeholders.append(resolved[i + 1:j])
            i = j + 1
        else:
            i += 1

    for name in placeholders:
        value = samples.get(name) or path_params.get(name)
        if not value or str(value).startswith("REPLACE_WITH_VALID_"):
            return None
        resolved = resolved.replace("{" + name + "}", str(value))

    return resolved


def _get_json(
    url: str, timeout: int, params: Optional[Dict[str, Any]] = None
) -> Tuple[int, Any, Dict[str, str]]:
    resp = requests.get(url, timeout=timeout, params=params)
    ctype = resp.headers.get("content-type", "")
    body: Any
    if "application/json" in ctype.lower():
        try:
            body = resp.json()
        except Exception:
            body = resp.text
    else:
        body = resp.text
    return resp.status_code, body, dict(resp.headers)


def _post_json(
    url: str,
    timeout: int,
    payload: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Any]:
    resp = requests.post(
        url,
        timeout=timeout,
        json=payload or {},
        params=params,
    )
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, resp.text


def _patch_json(
    url: str, timeout: int, payload: Optional[Dict[str, Any]] = None
) -> Tuple[int, Any]:
    resp = requests.patch(url, timeout=timeout, json=payload or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, resp.text


def _delete(url: str, timeout: int) -> int:
    resp = requests.delete(url, timeout=timeout)
    return resp.status_code


def _safe_len(obj: Any) -> int:
    if (
        isinstance(obj, dict)
        and "value" in obj
        and isinstance(obj["value"], list)
    ):
        return len(obj["value"])  # Graph-style list
    if isinstance(obj, list):
        return len(obj)
    return 0


def _preflight(base: str, timeout: int) -> None:
    # Lightweight readiness check; prefer readiness but keep hello fallback
    urls = [f"{base}/health/ready", f"{base}/hello"]
    attempts = 5
    last_err: Optional[str] = None
    for _ in range(attempts):
        try:
            for url in urls:
                status, body, _hdrs = _get_json(url, timeout)
                if 200 <= status < 300:
                    return
                last_err = f"{url} -> {status}"
        except Exception as e:
            last_err = f"preflight -> {type(e).__name__}: {e}"
        time.sleep(2)
    raise AssertionError(
        f"Preflight failed after retries. Last error: {last_err}"
    )


def test_all_http_endpoints_live():
    manifest = _load_manifest()
    base = _base_url(manifest)
    timeout = _timeout(manifest)
    write_tests = _should_test_write(manifest)
    skip = set(_skip_routes(manifest))

    _preflight(base, timeout)

    routes = _discover_routes()

    samples: Dict[str, str] = {}

    s, users, _h = _get_json(f"{base}/users", timeout)
    if 200 <= s < 300 and _safe_len(users) > 0:
        uid = (
            users.get("value", users)[0].get("id")
            if isinstance(users, dict)
            else users[0].get("id")
        )
        if uid:
            samples["user_id"] = uid

    s, plans, _h = _get_json(f"{base}/plans", timeout)
    plan_id: Optional[str] = None
    if 200 <= s < 300 and _safe_len(plans) > 0:
        plan_id = (
            plans.get("value", plans)[0].get("id")
            if isinstance(plans, dict)
            else plans[0].get("id")
        )
        if plan_id:
            samples["plan_id"] = plan_id
            s2, buckets, _h2 = _get_json(
                f"{base}/plans/{plan_id}/buckets", timeout
            )
            if 200 <= s2 < 300 and _safe_len(buckets) > 0:
                bid = (
                    buckets.get("value", buckets)[0].get("id")
                    if isinstance(buckets, dict)
                    else buckets[0].get("id")
                )
                if bid:
                    samples["bucket_id"] = bid

    s, my_tasks, _h = _get_json(f"{base}/me/tasks", timeout)
    if 200 <= s < 300 and _safe_len(my_tasks) > 0:
        tid = (
            my_tasks.get("value", my_tasks)[0].get("id")
            if isinstance(my_tasks, dict)
            else my_tasks[0].get("id")
        )
        if tid:
            samples["task_id"] = tid

    s, teams, _h = _get_json(f"{base}/teams", timeout)
    if 200 <= s < 300 and _safe_len(teams) > 0:
        tm = (
            teams.get("value", teams)[0]
            if isinstance(teams, dict)
            else teams[0]
        )
        if isinstance(tm, dict) and tm.get("id"):
            samples["team_id"] = tm["id"]

    s, msgs, _h = _get_json(f"{base}/me/messages", timeout)
    if (
        200 <= s < 300
        and _safe_len(msgs) > 0
        and isinstance(msgs, (dict, list))
    ):
        first = (
            msgs.get("value", msgs)[0]
            if isinstance(msgs, dict)
            else msgs[0]
        )
        if isinstance(first, dict) and first.get("id"):
            samples["message_id"] = first["id"]

    s, drives, _h = _get_json(f"{base}/me/drives", timeout)
    if 200 <= s < 300 and _safe_len(drives) > 0:
        did = (
            drives.get("value", drives)[0].get("id")
            if isinstance(drives, dict)
            else drives[0].get("id")
        )
        if did:
            samples["drive_id"] = did
            s2, children, _h2 = _get_json(
                f"{base}/me/drive/root/children", timeout
            )
            if 200 <= s2 < 300 and _safe_len(children) > 0:
                it = (
                    children.get("value", children)[0]
                    if isinstance(children, dict)
                    else children[0]
                )
                if isinstance(it, dict) and it.get("id"):
                    samples["item_id"] = it["id"]

    s, upcoming, _h = _get_json(f"{base}/me/events/upcoming", timeout)
    if 200 <= s < 300 and _safe_len(upcoming) > 0:
        ev = (
            upcoming.get("value", upcoming)[0]
            if isinstance(upcoming, dict)
            else upcoming[0]
        )
        if isinstance(ev, dict) and ev.get("id"):
            samples["event_id"] = ev["id"]

    q_defaults: Dict[str, Dict[str, Any]] = manifest.get("query_params", {})

    failures: List[str] = []
    tested: List[str] = []
    skipped: List[str] = []

    for route, methods in routes:
        if route in skip:
            skipped.append(f"{route} (configured skip)")
            continue

        for method in methods:
            if method != "GET" and not write_tests:
                skipped.append(f"{route} [{method}] (writes disabled)")
                continue

            resolved = _resolve_path_params(route, manifest, samples)
            if resolved is None:
                skipped.append(
                    f"{route} [{method}] (missing path params)"
                )
                continue

            url = f"{base}/{resolved}"

            try:
                params: Optional[Dict[str, Any]] = None
                if route == "sites":
                    params = q_defaults.get("sites", {"query": "contoso"})

                if method == "GET":
                    status_code, body, _headers = _get_json(
                        url, timeout, params=params
                    )
                    if status_code == 503:
                        skipped.append(f"{route} [{method}] (503 transient)")
                        continue
                    if not (200 <= status_code < 300):
                        failures.append(
                            f"GET {url} -> {status_code} body={body}"
                        )
                    else:
                        if body is None or (
                            isinstance(body, str) and body.strip() == ""
                        ):
                            failures.append(f"GET {url} -> empty body")
                        else:
                            tested.append(f"GET {url}")
                elif method == "POST":
                    status_code, body = _post_json(url, timeout)
                    if status_code == 503:
                        skipped.append(f"{route} [{method}] (503 transient)")
                        continue
                    if not (
                        200 <= status_code < 300
                        or status_code in (201, 202, 204)
                    ):
                        failures.append(
                            f"POST {url} -> {status_code} body={body}"
                        )
                    else:
                        tested.append(f"POST {url}")
                elif method == "PATCH":
                    status_code, body = _patch_json(url, timeout)
                    if status_code == 503:
                        skipped.append(f"{route} [{method}] (503 transient)")
                        continue
                    if not (200 <= status_code < 300):
                        failures.append(
                            f"PATCH {url} -> {status_code} body={body}"
                        )
                    else:
                        tested.append(f"PATCH {url}")
                elif method == "DELETE":
                    status_code = _delete(url, timeout)
                    if status_code == 503:
                        skipped.append(f"{route} [{method}] (503 transient)")
                        continue
                    if not (200 <= status_code < 300 or status_code == 204):
                        failures.append(f"DELETE {url} -> {status_code}")
                    else:
                        tested.append(f"DELETE {url}")
                else:
                    skipped.append(
                        f"{route} [{method}] (unsupported method)"
                    )
            except Exception as e:
                failures.append(f"{method} {url} -> EXCEPTION {e}")

    if failures:
        msg = (
            "\n".join(
                [
                    "Live HTTP endpoint verification failures:",
                    *failures,
                    "",
                    (
                        f"Tested: {len(tested)} | Skipped: "
                        f"{len(skipped)} | Failed: {len(failures)}"
                    ),
                ]
            )
        )
        raise AssertionError(msg)

    if len(tested) == 0:
        raise AssertionError(
            "No endpoints tested. "
            f"Skipped={len(skipped)}. "
            "Check manifest path_params and server state."
        )
