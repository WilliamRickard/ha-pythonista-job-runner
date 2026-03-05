# Version: 0.6.12-webui.10
"""Tests for Web UI version synchronisation guardrail.

The builder enforces that webui_src.html contains a first-line VERSION comment
that matches WEBUI_VERSION in webui_build.py so the generated outputs are
consistent and drift is detected early.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from webui_build import (
    WEBUI_VERSION,
    WEBUI_CSS_PARTS,
    WEBUI_HTML_PARTS,
    WEBUI_JS_PARTS,
    WebUiPaths,
    build_webui,
)


def _write_minimal_webui_tree(tmp: Path, src_first_line: str) -> WebUiPaths:
    """Create a minimal webui build tree in tmp and return paths."""

    src_html = tmp / "webui_src.html"
    css = tmp / "webui.css"
    js = tmp / "webui.js"
    out_html = tmp / "webui.html"

    src_html.write_text(
        src_first_line + "\n"
        "<html>\n"
        "<head><style>/*__WEBUI_CSS__*/</style></head>\n"
        "<body><!--__WEBUI_BODY__*/<script>/*__WEBUI_JS__*/</script></body>\n"
        "</html>\n",
        encoding="utf-8",
    )

    # Generated outputs (required paths)
    css.write_text("", encoding="utf-8")
    js.write_text("", encoding="utf-8")
    out_html.write_text("", encoding="utf-8")

    parts_dir = tmp / "webui_html"
    parts_dir.mkdir()
    for name in WEBUI_HTML_PARTS:
        (parts_dir / name).write_text("<div></div>\n", encoding="utf-8")

    js_dir = tmp / "webui_js"
    js_dir.mkdir()
    for name in WEBUI_JS_PARTS:
        (js_dir / name).write_text("// js\n", encoding="utf-8")

    css_dir = tmp / "webui_css"
    css_dir.mkdir()
    for name in WEBUI_CSS_PARTS:
        (css_dir / name).write_text("/* css */\n", encoding="utf-8")

    return WebUiPaths(src_html=src_html, css=css, js=js, out_html=out_html)


def test_builder_fails_when_src_version_mismatches(tmp_path: Path) -> None:
    """Mismatched VERSION in webui_src.html should raise with details."""

    bad = "<!doctype html><!-- VERSION: 0.0.0 -->"
    paths = _write_minimal_webui_tree(tmp_path, bad)

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    msg = str(excinfo.value)
    assert "webui_src.html VERSION" in msg
    assert "0.0.0" in msg
    assert WEBUI_VERSION in msg


def test_builder_fails_when_src_missing_version_comment(tmp_path: Path) -> None:
    """Missing VERSION comment should raise and show the found first line."""

    paths = _write_minimal_webui_tree(tmp_path, "<!doctype html>")

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    msg = str(excinfo.value)
    assert "first line must be" in msg
    assert "<!doctype html>" in msg
