from __future__ import annotations

"""Audit utilities for request actor extraction and JSONL event persistence."""

import json
from pathlib import Path
from typing import Any, Mapping

from utils import utc_now


def _header_str(headers: Mapping[str, Any], key: str) -> str:
    """Return a trimmed string header value, or empty string when unavailable."""
    raw = headers.get(key)
    if raw is None:
        return ""
    try:
        return str(raw).strip()
    except Exception:
        return ""


def actor_from_headers(headers: Mapping[str, Any], client_ip: str, ingress_proxy_ip: str) -> dict[str, Any]:
    """Extract safe actor identity from request headers.

    Ingress identity headers are accepted only when the request source IP matches
    the Home Assistant ingress proxy IP.
    """
    actor: dict[str, Any] = {
        "client_ip": str(client_ip or ""),
        "via_ingress": False,
        "user_id": None,
        "user_name": None,
        "display_name": None,
        "ingress_path": None,
    }
    if str(client_ip or "") != str(ingress_proxy_ip or ""):
        return actor

    actor["via_ingress"] = True
    user_id = _header_str(headers, "X-Remote-User-Id")
    user_name = _header_str(headers, "X-Remote-User-Name")
    display_name = _header_str(headers, "X-Remote-User-Display-Name")
    ingress_path = _header_str(headers, "X-Ingress-Path")

    actor["user_id"] = user_id or None
    actor["user_name"] = user_name or None
    actor["display_name"] = display_name or None
    actor["ingress_path"] = ingress_path or None
    return actor


def append_audit_event(log_path: Path, lock: Any, event: dict[str, Any]) -> None:
    """Append a single JSONL audit event with best-effort durability."""
    payload = dict(event)
    payload.setdefault("timestamp_utc", utc_now())
    line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with lock:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.write("\n")
