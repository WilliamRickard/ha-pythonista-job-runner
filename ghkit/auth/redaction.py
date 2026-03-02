# Version: 0.1.0

"""Secret redaction utilities."""

import re

_TOKEN_RE = re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")

def redact(text: str) -> str:
    """Redact common GitHub token patterns from text."""
    return _TOKEN_RE.sub("[REDACTED_TOKEN]", text)
