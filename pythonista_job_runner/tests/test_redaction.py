"""Tests for secret redaction helpers."""

from __future__ import annotations

import runner_core


def test_redact_basic_auth_in_urls() -> None:
    s = "fetching https://alice:secret@example.com/simple"
    out = runner_core._redact_basic_auth_in_urls(s)
    assert "alice:***@example.com" in out
    assert "alice:secret@" not in out


def test_redact_common_query_secrets() -> None:
    s = "token=abc123&x=1 api_key=hello"
    out = runner_core._redact_common_query_secrets(s)
    assert "token=***" in out
    assert "api_key=***" in out
    assert "abc123" not in out
    assert "hello" not in out


def test_redact_pip_text_replaces_known_urls() -> None:
    raw_url = "https://bob:pw@example.com/simple"
    text = f"Looking in indexes: {raw_url}"
    out = runner_core._redact_pip_text(text, [raw_url])

    assert "bob:***@example.com" in out
    assert "bob:pw@" not in out
