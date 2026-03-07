from __future__ import annotations

"""Authentication and access checks for the HTTP API handler."""

import hmac
from typing import Any
from urllib.parse import urlparse

from runner_core import INGRESS_PROXY_IP
from utils import ip_in_cidrs


def client_ip(handler: Any) -> str:
    """Return caller IP address from the active request handler."""
    try:
        return (handler.client_address[0] or "").strip()
    except Exception:
        return ""


def is_ingress(handler: Any) -> bool:
    """Return whether the request is coming from Home Assistant ingress proxy."""
    return client_ip(handler) == INGRESS_PROXY_IP


def auth_ok(handler: Any) -> bool:
    """Return whether a request is authorised according to runner settings."""
    runner = handler.server.runner
def auth_ok(handler: Any) -> bool:
    """Return whether a request is authorised according to runner settings."""
    runner = handler.server.runner
    path = urlparse(handler.path).path
    if path == "/health":
        return True

    if runner.ingress_strict and not is_ingress(handler):
        return False
    if is_ingress(handler):
        return True
    if is_ingress(handler):
        return True

    token = handler.headers.get("X-Runner-Token", "")
    if not runner.token or not hmac.compare_digest(token, runner.token):
        return False

    cidrs = runner.api_allow_cidrs
    return ip_in_cidrs(client_ip(handler), list(cidrs)) if cidrs else True
