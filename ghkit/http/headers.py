# Version: 0.1.0

"""HTTP header construction."""

from __future__ import annotations

from ..config import GhKitConfig


def build_headers(config: GhKitConfig, token: str | None = None, accept: str | None = None) -> dict[str, str]:
    """Build standard GitHub API headers."""
    headers: dict[str, str] = {
        "User-Agent": config.user_agent,
        "X-GitHub-Api-Version": config.api_version,
        "Accept": accept or "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
