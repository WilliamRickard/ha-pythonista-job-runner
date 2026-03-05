# Version: 0.6.12-webui.11
"""Tests for generated output VERSION header guardrails."""

from __future__ import annotations

from pathlib import Path

import pytest

from webui_build import (
    WEBUI_VERSION,
    WEBUI_CSS_PARTS,
    WEBUI_HTML_PARTS,
    WEBUI_JS_PARTS,
    WebUiPaths,
    check_webui,
    write_webui,
)


def _write_minimal_webui_tree(tmp: Path) -> WebUiPaths:
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


def _replace_first_line(path: Path, new_first_line: str) -> None:
    """Replace the first line of a file, preserving the rest."""

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines, f"Expected non-empty file: {path}"
    lines[0] = new_first_line
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_check_webui_fails_if_webui_css_version_header_mismatches(tmp_path: Path) -> None:
    """check_webui must fail if webui.css first-line VERSION does not match."""

    paths = _write_minimal_webui_tree(tmp_path)
    write_webui(paths)

    _replace_first_line(paths.css, "/* VERSION: 0.0.0 */")

    with pytest.raises(RuntimeError) as excinfo:
        check_webui(paths)

    msg = str(excinfo.value)
    assert "webui.css VERSION" in msg
    assert "WEBUI_VERSION" in msg


def test_check_webui_fails_if_webui_js_version_header_mismatches(tmp_path: Path) -> None:
    """check_webui must fail if webui.js first-line VERSION does not match."""

    paths = _write_minimal_webui_tree(tmp_path)
    write_webui(paths)

    _replace_first_line(paths.js, "/* VERSION: 0.0.0 */")

    with pytest.raises(RuntimeError) as excinfo:
        check_webui(paths)

    msg = str(excinfo.value)
    assert "webui.js VERSION" in msg
    assert "WEBUI_VERSION" in msg


def test_check_webui_fails_if_webui_html_version_header_mismatches(tmp_path: Path) -> None:
    """check_webui must fail if webui.html first-line VERSION does not match."""

    paths = _write_minimal_webui_tree(tmp_path)
    write_webui(paths)

    _replace_first_line(paths.out_html, "<!doctype html><!-- VERSION: 0.0.0 -->")

    with pytest.raises(RuntimeError) as excinfo:
        check_webui(paths)

    msg = str(excinfo.value)
    assert "webui.html VERSION" in msg
    assert "WEBUI_VERSION" in msg
