# Version: 0.1.0

"""HTTP client wrapper (minimal)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from ..config import GhKitConfig
from ..errors import GhKitHttpError
from .headers import build_headers


@dataclass
class HttpResponse:
    """Simplified HTTP response."""

    status_code: int
    headers: dict[str, str]
    text: str


class HttpClient:
    """Small wrapper around requests.Session."""

    def __init__(self, config: GhKitConfig, token: str | None = None, timeout_s: int = 30) -> None:
        self._config = config
        self._token = token
        self._timeout_s = timeout_s
        self._session = requests.Session()

    def get_text(self, url: str, accept: str | None = None) -> HttpResponse:
        """GET and return response text."""
        try:
            headers = build_headers(self._config, token=self._token, accept=accept)
            r = self._session.get(url, headers=headers, timeout=self._timeout_s)
        except requests.RequestException as e:
            raise GhKitHttpError(f"Request failed: {e}") from e

        if r.status_code < 200 or r.status_code >= 300:
            raise GhKitHttpError(f"HTTP {r.status_code} for GET {url}", http_status=r.status_code)

        return HttpResponse(status_code=r.status_code, headers=dict(r.headers), text=r.text)

    def get_json(self, url: str) -> Any:
        """GET and parse JSON."""
        resp = self.get_text(url)
        try:
            return requests.models.complexjson.loads(resp.text)
        except Exception as e:
            raise GhKitHttpError(f"Failed to parse JSON from {url}: {e}") from e
