"""Release metadata helpers for the update entity."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class ReleaseInfo:
    """Normalized release metadata for Home Assistant update entities."""

    latest_version: str | None
    release_url: str | None
    summary: str | None


def fetch_latest_release(repo: str) -> ReleaseInfo:
    """Fetch latest GitHub release metadata for a repo path like owner/name."""
    req = Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "pythonista-job-runner-ha"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return ReleaseInfo(latest_version=None, release_url=None, summary=None)

    return ReleaseInfo(
        latest_version=str(payload.get("tag_name") or "").lstrip("v") or None,
        release_url=str(payload.get("html_url") or "") or None,
        summary=str(payload.get("name") or payload.get("body") or "")[:500] or None,
    )
