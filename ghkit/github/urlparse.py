# Version: 0.1.0

"""Parse GitHub URLs."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ParsedGitHubUrl:
    """Parsed GitHub URL context."""

    host: str
    owner: str | None = None
    repo: str | None = None
    pr_number: int | None = None
    issue_number: int | None = None


def parse_github_url(url: str) -> ParsedGitHubUrl:
    """Parse repo, PR, and issue URLs."""
    u = urlparse(url)
    host = u.netloc or "github.com"
    parts = [p for p in u.path.split("/") if p]

    if len(parts) >= 2:
        owner, repo = parts[0], parts[1]
        if len(parts) >= 4 and parts[2] == "pull":
            try:
                return ParsedGitHubUrl(host=host, owner=owner, repo=repo, pr_number=int(parts[3]))
            except ValueError:
                return ParsedGitHubUrl(host=host, owner=owner, repo=repo)
        if len(parts) >= 4 and parts[2] == "issues":
            try:
                return ParsedGitHubUrl(host=host, owner=owner, repo=repo, issue_number=int(parts[3]))
            except ValueError:
                return ParsedGitHubUrl(host=host, owner=owner, repo=repo)
        return ParsedGitHubUrl(host=host, owner=owner, repo=repo)

    return ParsedGitHubUrl(host=host)
