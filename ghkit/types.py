# Version: 0.1.0

"""Typed structures (initial placeholders)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RepoRef:
    """A repository reference like owner/name."""

    owner: str
    name: str
