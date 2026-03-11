# Version: 0.6.12-webui.10
"""Tests for VERSION header guardrail in Web UI JavaScript parts."""

from __future__ import annotations

from pathlib import Path

import pytest

from webui_build import WEBUI_VERSION, WEBUI_CSS_PARTS, WEBUI_HTML_PARTS, WEBUI_JS_PARTS, WebUiPaths, build_webui


def _write_minimal_webui_tree(tmp: Path, js_parts: dict[str, str] | None = None) -> WebUiPaths:
    """Create a minimal webui build tree in tmp and return paths."""

    js_parts = js_parts or {}

    src_html = tmp / "webui_src.html"
    css = tmp / "webui.css"
    js = tmp / "webui.js"
    out_html = tmp / "webui.html"

    src_html.write_text(
        f"<!doctype html><!-- VERSION: {WEBUI_VERSION} -->\n"
        "<html>\n"
        "<head><style>/*__WEBUI_CSS__*/</style></head>\n"
        "<body><!--__WEBUI_BODY__*/<script>/*__WEBUI_JS__*/</script></body>\n"
        "</html>\n",
        encoding="utf-8",
    )

    # Generated outputs (the builder reads parts, but these paths are still required)
    css.write_text("", encoding="utf-8")
    js.write_text("", encoding="utf-8")
    out_html.write_text("", encoding="utf-8")

    parts_dir = tmp / "webui_html"
    parts_dir.mkdir()
    for name in WEBUI_HTML_PARTS:
        (parts_dir / name).write_text(f"<div id=\"{name.replace('.', '_')}\"></div>\n", encoding="utf-8")

    js_dir = tmp / "webui_js"
    js_dir.mkdir()
    for name in WEBUI_JS_PARTS:
        (js_dir / name).write_text(js_parts.get(name, "// js\n"), encoding="utf-8")

    css_dir = tmp / "webui_css"
    css_dir.mkdir()
    for name in WEBUI_CSS_PARTS:
        (css_dir / name).write_text("/* css */\n", encoding="utf-8")

    return WebUiPaths(src_html=src_html, css=css, js=js, out_html=out_html)


def test_builder_rejects_version_header_in_js_part(tmp_path: Path) -> None:
    """A JS part must not contain a VERSION header comment."""

    paths = _write_minimal_webui_tree(
        tmp_path,
        js_parts={"00_core.js": "// VERSION: 999\n// js\n"},
    )

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    msg = str(excinfo.value)
    assert "JavaScript part must not declare VERSION header" in msg
    assert "00_core.js" in msg
