# Version: 0.3.0-client.1
"""HTTP client for the Pythonista Job Runner add-on API."""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class RunnerClientError(Exception):
    """Raised when the runner endpoint is unreachable or returns invalid data."""


@dataclass
class RunnerClient:
    """Small synchronous client for the add-on API."""

    base_url: str
    token: str
    verify_ssl: bool = True

    def _ssl_context(self) -> ssl.SSLContext:
        if self.verify_ssl:
            return ssl.create_default_context()
        return ssl._create_unverified_context()  # noqa: SLF001

    def _json_get(self, path: str) -> dict:
        req = Request(f"{self.base_url.rstrip('/')}{path}", headers=self._headers(), method="GET")
        try:
            with urlopen(req, timeout=10, context=self._ssl_context()) as resp:  # noqa: S310
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
            with urlopen(req, timeout=10, context=self._ssl_context()) as resp:  # noqa: S310
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RunnerClientError(str(exc)) from exc

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.token:
            headers["X-Runner-Token"] = self.token
        return headers

    def health(self) -> dict:
        """Return API health payload."""
        return self._json_get("/health")

    def stats(self) -> dict:
        """Return stats payload."""
        return self._json_get("/stats.json")

    def jobs(self) -> dict:
        """Return current jobs payload."""
        return self._json_get("/jobs.json")

    def info(self) -> dict:
        """Return service info payload."""
        return self._json_get("/info.json")

    def support_bundle(self) -> dict:
        """Return redacted support bundle from add-on API."""
        return self._json_get("/support_bundle.json")

    def package_summary(self) -> dict:
        """Return package subsystem summary payload."""
        return self._json_get("/packages/summary.json")

    def package_profiles(self) -> dict:
        """Return package profile inventory payload."""
        return self._json_get("/package_profiles.json")

    def package_cache(self) -> dict:
        """Return package cache summary payload."""
        return self._json_get("/packages/cache.json")

    def build_package_profile(self, profile_name: str = "", rebuild: bool = False) -> dict:
        """Build or rebuild one named package profile."""
        payload = {"rebuild": bool(rebuild)}
        if profile_name.strip():
            payload["profile_name"] = profile_name.strip()
        return self._json_post("/package_profiles/build", payload)

    def prune_package_cache(self, reason: str = "manual") -> dict:
        """Request package cache prune."""
        return self._json_post("/packages/cache/prune", {"reason": str(reason or "manual")})

    def purge_package_cache(
        self,
        reason: str = "manual",
        include_venvs: bool = False,
        include_imported_wheels: bool = False,
    ) -> dict:
        """Request package cache purge."""
        return self._json_post(
            "/packages/cache/purge",
            {
                "reason": str(reason or "manual"),
                "include_venvs": bool(include_venvs),
                "include_imported_wheels": bool(include_imported_wheels),
            },
        )

    def purge(self, states: list[str], older_than_hours: int = 0, dry_run: bool = False) -> dict:
        """Purge jobs matching selected states."""
        return self._json_post("/purge", {"states": states, "older_than_hours": older_than_hours, "dry_run": dry_run})

    def cancel(self, job_id: str) -> dict:
        """Cancel a job by id."""
        return self._json_post(f"/cancel/{quote(job_id, safe='')}", {})

    def backup_pause(self) -> dict:
        """Pause new-job intake for backup."""
        return self._json_post("/backup/pause", {})

    def backup_resume(self) -> dict:
        """Resume new-job intake after backup."""
        return self._json_post("/backup/resume", {})

    def backup_status(self) -> dict:
        """Return backup pause status."""
        return self._json_get("/backup/status.json")
