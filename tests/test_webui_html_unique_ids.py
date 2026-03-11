# Version: 0.6.12-webui.10
"""Tests for build-time validation of Web UI HTML partials."""

from __future__ import annotations

from pathlib import Path

import pytest

from webui_build import WEBUI_VERSION, WEBUI_CSS_PARTS, WEBUI_HTML_PARTS, WEBUI_JS_PARTS, WebUiPaths, build_webui


def _write_minimal_webui_tree(tmp: Path, parts: dict[str, str]) -> WebUiPaths:
    """Create a minimal webui build tree in tmp and return paths."""

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

    css.write_text("", encoding="utf-8")
    js.write_text("", encoding="utf-8")
    out_html.write_text("", encoding="utf-8")

    parts_dir = tmp / "webui_html"
    parts_dir.mkdir()

    for name in WEBUI_HTML_PARTS:
        text = parts.get(name, "<div></div>\n")
        (parts_dir / name).write_text(text, encoding="utf-8")

    js_dir = tmp / "webui_js"
    js_dir.mkdir()
    for name in WEBUI_JS_PARTS:
        (js_dir / name).write_text("// js\n", encoding="utf-8")

    css_dir = tmp / "webui_css"
    css_dir.mkdir()
    for name in WEBUI_CSS_PARTS:
        (css_dir / name).write_text("/* css */\n", encoding="utf-8")

    return WebUiPaths(src_html=src_html, css=css, js=js, out_html=out_html)


def test_build_webui_rejects_duplicate_ids(tmp_path: Path) -> None:
    """The builder must fail if two HTML parts define the same id."""

    paths = _write_minimal_webui_tree(
        tmp_path,
        {
            "00_shell.html": '<div id="dup"></div>\n',
            "10_overview.html": '<div id="dup"></div>\n',
        },
    )

    with pytest.raises(RuntimeError, match=r"Duplicate HTML element id"):
        build_webui(paths)
