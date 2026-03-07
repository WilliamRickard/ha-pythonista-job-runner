"""HTTP client for the Pythonista Job Runner add-on API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class RunnerClientError(Exception):
    """Raised when the runner endpoint is unreachable or returns invalid data."""


@dataclass
class RunnerClient:
    """Small synchronous client for the add-on API."""

    base_url: str
    token: str
    verify_ssl: bool = True

    def _json_get(self, path: str) -> dict:
        req = Request(f"{self.base_url.rstrip('/')}{path}", headers=self._headers(), method="GET")
        try:
            with urlopen(req, timeout=10) as resp:  # noqa: S310
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RunnerClientError(str(exc)) from exc

    def _json_post(self, path: str, payload: dict) -> dict:
        req = Request(
            f"{self.base_url.rstrip('/')}{path}",
            headers={**self._headers(), "Content-Type": "application/json"},
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        try:
            with urlopen(req, timeout=10) as resp:  # noqa: S310
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RunnerClientError(str(exc)) from exc

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.token:
            headers["X-Runner-Token"] = self.token
        return headers

    def health(self) -> dict:
        return self._json_get("/health")

    def stats(self) -> dict:
        return self._json_get("/stats.json")

    def purge(self, states: list[str], older_than_hours: int = 0, dry_run: bool = False) -> dict:
        return self._json_post("/purge", {"states": states, "older_than_hours": older_than_hours, "dry_run": dry_run})
    def purge(self, states: list[str], older_than_hours: int = 0, dry_run: bool = False) -> dict:
        return self._json_post("/purge", {"states": states, "older_than_hours": older_than_hours, "dry_run": dry_run})

    def jobs(self) -> dict:
    def jobs(self) -> dict:
        """Return current jobs payload."""
        return self._json_get("/jobs.json")

    def support_bundle(self) -> dict:
        """Return redacted support bundle from add-on API."""
        return self._json_get("/support_bundle.json")

from urllib.parse import quote

    def cancel(self, job_id: str) -> dict:
        """Cancel a job by id."""
        return self._json_post(f"/cancel/{quote(job_id, safe='')}", {})
