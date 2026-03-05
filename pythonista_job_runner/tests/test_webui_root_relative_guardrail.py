# Version: 0.6.12-webui.12
"""Tests for root-relative URL guardrails in Web UI build inputs."""

from __future__ import annotations

from pathlib import Path

import pytest

from webui_build import WEBUI_VERSION, WEBUI_CSS_PARTS, WEBUI_HTML_PARTS, WEBUI_JS_PARTS, WebUiPaths, build_webui


def _write_minimal_webui_tree(
    tmp: Path,
    parts: dict[str, str] | None = None,
    js_parts: dict[str, str] | None = None,
    css_parts: dict[str, str] | None = None,
) -> WebUiPaths:
    """Create a minimal webui build tree in tmp and return paths."""

    parts = parts or {}
    js_parts = js_parts or {}
    css_parts = css_parts or {}

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
        (parts_dir / name).write_text(parts.get(name, "<div></div>\n"), encoding="utf-8")

    js_dir = tmp / "webui_js"
    js_dir.mkdir()
    for name in WEBUI_JS_PARTS:
        (js_dir / name).write_text(js_parts.get(name, "// js\n"), encoding="utf-8")

    css_dir = tmp / "webui_css"
    css_dir.mkdir()
    for name in WEBUI_CSS_PARTS:
        (css_dir / name).write_text(css_parts.get(name, "/* css */\n"), encoding="utf-8")

    return WebUiPaths(src_html=src_html, css=css, js=js, out_html=out_html)


def test_builder_reports_html_part_and_line_for_root_relative_href(tmp_path: Path) -> None:
    """A root-relative href in an HTML part should fail with part and line details."""

    paths = _write_minimal_webui_tree(
        tmp_path,
        parts={"00_shell.html": '<a href="/bad">x</a>\n'},
    )

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    msg = str(excinfo.value)
    assert "Root-relative reference found" in msg
    assert "webui_html/00_shell.html:1" in msg
    assert 'href="/' in msg


def test_builder_reports_js_part_and_line_for_root_relative_fetch(tmp_path: Path) -> None:
    """A root-relative fetch in a JS part should fail with part and line details."""

    paths = _write_minimal_webui_tree(
        tmp_path,
        js_parts={"00_core.js": "fetch('/bad')\n"},
    )

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    msg = str(excinfo.value)
    assert "Root-relative reference found" in msg
    assert "webui_js/00_core.js:1" in msg
    assert "fetch('/" in msg


def test_builder_reports_css_part_and_line_for_root_relative_url(tmp_path: Path) -> None:
    """A root-relative url(/...) in CSS should fail with file and line details."""

    paths = _write_minimal_webui_tree(
        tmp_path,
        css_parts={"00_tokens.css": ".x{background:url(/bad.png)}\n"},
    )

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    msg = str(excinfo.value)
    assert "Root-relative reference found" in msg
    assert "webui_css/00_tokens.css:1" in msg
    assert "url(/" in msg


def test_builder_reports_css_part_and_line_for_root_relative_import(tmp_path: Path) -> None:
    """A root-relative @import in CSS should fail with file and line details."""

    paths = _write_minimal_webui_tree(
        tmp_path,
        css_parts={"00_tokens.css": '@import "/bad.css";\n'},
    )

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    msg = str(excinfo.value)
    assert "Root-relative reference found" in msg
    assert "webui_css/00_tokens.css:1" in msg
    assert '@import "/' in msg
