# Version: 0.6.12-webui.12
"""Tests for Web UI part README version guardrail."""

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
    readme_versions: dict[str, str] | None = None,
) -> WebUiPaths:
    """Create a minimal webui build tree in tmp and return paths."""

    readme_versions = readme_versions or {}

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
    for folder, version in readme_versions.items():
        (tmp / folder).mkdir(exist_ok=True)
        (tmp / folder / "README.md").write_text(
            f"<!-- Version: {version} -->\n# Readme\n",
            encoding="utf-8",
        )

    return WebUiPaths(src_html=src_html, css=css, js=js, out_html=out_html)


def test_readme_version_mismatch_fails(tmp_path: Path) -> None:
    """If a part README declares a mismatched version, the build should fail."""

    paths = _write_minimal_tree(
        tmp_path,
        readme_versions={"webui_html": "bad-version"},
    )

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    msg = str(excinfo.value)
    assert "webui_html/README.md VERSION" in msg
    assert "does not match WEBUI_VERSION" in msg


def test_readme_version_omitted_is_allowed(tmp_path: Path) -> None:
    """README files may omit the version header entirely."""

    paths = _write_minimal_tree(tmp_path)

    out = build_webui(paths)
    assert out.startswith("<!doctype html")


def test_readme_malformed_lowercase_version_header_fails(tmp_path: Path) -> None:
    """Malformed README version headers should fail regardless of case."""

    paths = _write_minimal_tree(tmp_path)
    (tmp_path / "webui_html" / "README.md").write_text("version: nope\n# Readme\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as excinfo:
        build_webui(paths)

    msg = str(excinfo.value)
    assert "webui_html/README.md first line must be" in msg
