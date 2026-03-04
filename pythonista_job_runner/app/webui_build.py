# Version: 0.6.12-webui.2
from __future__ import annotations

"""Build the Home Assistant Ingress-safe Web UI template.

This repository serves the Web UI from a single HTML file (webui.html) so it works
cleanly behind Home Assistant Ingress without requiring a static file server.

To make the UI easier to edit and review, the source is split into:
- webui_src.html (HTML skeleton + placeholders)
- webui.css      (CSS)
- webui_html/*.html (HTML body split into partials)
- webui_js/*.js    (JavaScript split into parts)

This script assembles webui_html/*.html, then inlines webui.css and the JS bundle (from webui_js/*.js) into webui_src.html to produce webui.html.

Usage (from repo root):
    python pythonista_job_runner/app/webui_build.py

Optional:
    python pythonista_job_runner/app/webui_build.py --check
      Raises RuntimeError if webui.html is out of date.
"""

from dataclasses import dataclass
from pathlib import Path

import re


@dataclass(frozen=True)
class WebUiPaths:
    """Paths used by the Web UI build process."""

    src_html: Path
    css: Path
    js: Path
    out_html: Path


def _default_paths() -> WebUiPaths:
    base = Path(__file__).resolve().parent
    return WebUiPaths(
        src_html=base / "webui_src.html",
        css=base / "webui.css",
        js=base / "webui.js",
        out_html=base / "webui.html",
    )





WEBUI_HTML_PARTS: tuple[str, ...] = (
    "00_shell.html",
    "10_overview.html",
    "20_jobs.html",
    "30_detail.html",
    "40_advanced.html",
    "50_help.html",
    "60_toast.html",
)

def _read_html_parts(p: WebUiPaths) -> str:
    """Return the HTML body assembled from webui_html/*.html parts.

    The assembly order is explicit (WEBUI_HTML_PARTS) to make builds deterministic.
    Parts must not contain document-level tags (doctype/html/head/body) or script/style blocks.
    """

    parts_dir = p.src_html.with_name("webui_html")
    if not parts_dir.is_dir():
        raise RuntimeError(f"Web UI HTML parts directory not found: {parts_dir}")

    expected_paths = [parts_dir / name for name in WEBUI_HTML_PARTS]
    missing = [x.name for x in expected_paths if not x.is_file()]
    if missing:
        raise RuntimeError(f"Missing Web UI HTML part(s) in {parts_dir}: {', '.join(missing)}")

    extras = sorted(
        x.name
        for x in parts_dir.glob("*.html")
        if x.is_file() and x.name not in WEBUI_HTML_PARTS
    )
    if extras:
        raise RuntimeError(
            f"Unexpected Web UI HTML part(s) in {parts_dir}: {', '.join(extras)}. "
            "If you intended to add a part, update WEBUI_HTML_PARTS in webui_build.py."
        )

    banned_patterns = [
        re.compile(r"<!doctype", re.IGNORECASE),
        re.compile(r"<html(\s|>)", re.IGNORECASE),
        re.compile(r"</html(\s|>)", re.IGNORECASE),
        re.compile(r"<head(\s|>)", re.IGNORECASE),
        re.compile(r"</head(\s|>)", re.IGNORECASE),
        re.compile(r"<body(\s|>)", re.IGNORECASE),
        re.compile(r"</body(\s|>)", re.IGNORECASE),
        re.compile(r"<script(\s|>)", re.IGNORECASE),
        re.compile(r"</script(\s|>)", re.IGNORECASE),
        re.compile(r"<style(\s|>)", re.IGNORECASE),
        re.compile(r"</style(\s|>)", re.IGNORECASE),
    ]

    texts: list[str] = []
    for part in expected_paths:
        txt = part.read_text(encoding="utf-8").rstrip()
        for pat in banned_patterns:
            if pat.search(txt):
                raise RuntimeError(f"HTML part contains forbidden tag/pattern ({pat.pattern}): {part}")
        texts.append(txt)

    return "\n".join(texts).rstrip()


def _read_js_bundle(p: WebUiPaths) -> str:
    """Return the JavaScript bundle text from webui_js/*.js parts."""

    parts_dir = p.js.with_name("webui_js")
    if not parts_dir.is_dir():
        raise RuntimeError(f"Web UI JavaScript parts directory not found: {parts_dir}")

    parts = sorted(x for x in parts_dir.glob("*.js") if x.is_file())
    if not parts:
        raise RuntimeError(f"No .js files found in {parts_dir}")

    return "\n".join(x.read_text(encoding="utf-8").rstrip() for x in parts).rstrip()
def build_webui(paths: WebUiPaths | None = None) -> str:
    """Return the bundled webui.html content as a string."""

    p = paths or _default_paths()

    src = p.src_html.read_text(encoding="utf-8")
    css = p.css.read_text(encoding="utf-8").rstrip()
    body = _read_html_parts(p)
    js = _read_js_bundle(p)
    if "/*__WEBUI_CSS__*/" not in src:
        raise RuntimeError("webui_src.html missing /*__WEBUI_CSS__*/ placeholder")
    if "<!--__WEBUI_BODY__*/" not in src:
        raise RuntimeError("webui_src.html missing <!--__WEBUI_BODY__*/ placeholder")
    if "/*__WEBUI_JS__*/" not in src:
        raise RuntimeError("webui_src.html missing /*__WEBUI_JS__*/ placeholder")

    out = src.replace("/*__WEBUI_CSS__*/", css)
    out = out.replace("<!--__WEBUI_BODY__*/", body)
    out = out.replace("/*__WEBUI_JS__*/", js)

    # Guardrail: webui must only use relative URLs, because Ingress sits under a path prefix.
    # (This is a heuristic check, not a full HTML/JS parser.)
    bad_patterns = [
        'href="/',
        "href='/",
        'src="/',
        "src='/",
        'fetch("/',
        "fetch('/",
    ]
    for pat in bad_patterns:
        if pat in out:
            raise RuntimeError(f"webui bundle contains root-relative reference: {pat}")

    return out


def write_webui(paths: WebUiPaths | None = None) -> None:
    """Write webui.html in-place."""

    p = paths or _default_paths()
    out = build_webui(p)
    p.out_html.write_text(out, encoding="utf-8")


def check_webui(paths: WebUiPaths | None = None) -> None:
    """Raise RuntimeError if webui.html does not match the bundle output."""

    p = paths or _default_paths()
    expected = build_webui(p)
    actual = p.out_html.read_text(encoding="utf-8")
    if actual != expected:
        raise RuntimeError("webui.html is out of date. Run webui_build.py to regenerate it.")


def main(argv: list[str] | None = None) -> None:
    """Entry point."""

    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if "--check" in args:
        check_webui()
        return
    write_webui()


if __name__ == "__main__":
    main()
