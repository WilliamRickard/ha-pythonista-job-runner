# Version: 0.6.12-webui.13
"""Tests for Web UI part README guardrail (no per-folder version headers)."""

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


def _write_minimal_tree(
    tmp: Path,
    readme_folders_with_version_header: set[str] | None = None,
) -> WebUiPaths:
    """Create a minimal webui build tree in tmp and return paths."""

    readme_folders_with_version_header = readme_folders_with_version_header or set()

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

    # These are generated outputs; they only need to exist.
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

    # Optional READMEs
    for folder in ("webui_html", "webui_css", "webui_js"):
        (tmp / folder).mkdir(exist_ok=True)
        readme = tmp / folder / "README.md"
        if folder in readme_folders_with_version_header:
            readme.write_text(
                f"<!-- Version: {WEBUI_VERSION} -->\n# Readme\n",
                encoding="utf-8",
            )
        else:
            readme.write_text("# Readme\n", encoding="utf-8")

    return WebUiPaths(src_html=src_html, css=css, js=js, out_html=out_html)


def test_part_readme_version_header_is_forbidden(tmp_path: Path) -> None:
    """If a part README declares a version header, the build should fail."""

    paths = _write_minimal_tree(tmp_path, readme_folders_with_version_header={"webui_html"})

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    msg = str(excinfo.value)
    assert "webui_html/README.md" in msg
    assert "must not declare a version header" in msg


def test_part_readmes_without_version_headers_are_allowed(tmp_path: Path) -> None:
    """Part README files without version headers are allowed."""

    paths = _write_minimal_tree(tmp_path)

    out = build_webui(paths)
    assert out.startswith("<!doctype html")
