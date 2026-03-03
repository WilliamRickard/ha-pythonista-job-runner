from __future__ import annotations

"""Build the Home Assistant Ingress-safe Web UI template.

This repository serves the Web UI from a single HTML file (webui.html) so it works
cleanly behind Home Assistant Ingress without requiring a static file server.

To make the UI easier to edit and review, the source is split into:
- webui_src.html (HTML skeleton + placeholders)
- webui.css      (CSS)
- webui_js/*.js  (JavaScript split into parts)

This script inlines webui.css and the JS bundle (from webui_js/*.js) into webui_src.html to produce webui.html.

Usage (from repo root):
    python pythonista_job_runner/app/webui_build.py

Optional:
    python pythonista_job_runner/app/webui_build.py --check
      Raises RuntimeError if webui.html is out of date.
"""

from dataclasses import dataclass
from pathlib import Path


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
    js = _read_js_bundle(p)
    if "/*__WEBUI_CSS__*/" not in src:
        raise RuntimeError("webui_src.html missing /*__WEBUI_CSS__*/ placeholder")
    if "/*__WEBUI_JS__*/" not in src:
        raise RuntimeError("webui_src.html missing /*__WEBUI_JS__*/ placeholder")

    out = src.replace("/*__WEBUI_CSS__*/", css)
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
