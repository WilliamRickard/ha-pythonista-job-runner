# Version: 0.6.12-webui.7
"""Tests for deterministic Web UI CSS part ordering.

The builder enforces an explicit ordered list of CSS parts so adding or renaming a
file cannot silently change bundle order.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from webui_build import WEBUI_CSS_PARTS, WEBUI_HTML_PARTS, WEBUI_JS_PARTS, WebUiPaths, build_webui


def _write_minimal_tree(tmp: Path) -> WebUiPaths:
    """Create a minimal webui build tree in tmp and return paths."""

    src_html = tmp / "webui_src.html"
    css = tmp / "webui.css"
    js = tmp / "webui.js"
    out_html = tmp / "webui.html"

    src_html.write_text(
        "<!doctype html>\n"
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


def test_builder_fails_if_expected_css_part_missing(tmp_path: Path) -> None:
    """Missing expected CSS parts must fail loudly."""

    paths = _write_minimal_tree(tmp_path)
    missing = WEBUI_CSS_PARTS[-1]
    (tmp_path / "webui_css" / missing).unlink()

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    assert "Missing expected Web UI CSS part" in str(excinfo.value)


def test_builder_fails_if_unexpected_css_part_exists(tmp_path: Path) -> None:
    """Unexpected CSS parts must fail loudly."""

    paths = _write_minimal_tree(tmp_path)
    (tmp_path / "webui_css" / "99_extra.css").write_text("/* extra */\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    assert "Unexpected Web UI CSS part" in str(excinfo.value)
