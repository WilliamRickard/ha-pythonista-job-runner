# Version: 0.1.0

"""Pagination helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Link:
    """A parsed Link header entry."""

    url: str
    rel: str


def parse_link_header(value: str) -> list[Link]:
    """Parse an RFC 5988-style Link header."""
    links: list[Link] = []
    if not value:
        return links
    parts = [p.strip() for p in value.split(",")]
    for part in parts:
        if ";" not in part:
            continue
        url_part, *param_parts = [x.strip() for x in part.split(";")]
        if not (url_part.startswith("<") and url_part.endswith(">")):
            continue
        url = url_part[1:-1]
        rel = ""
        for p in param_parts:
            if p.startswith("rel="):
                rel = p.split("=", 1)[1].strip().strip('"')
        if url and rel:
            links.append(Link(url=url, rel=rel))
    return links
