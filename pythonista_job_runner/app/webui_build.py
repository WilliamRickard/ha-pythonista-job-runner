# Version: 0.6.17-webui.1
from __future__ import annotations

"""Build the Home Assistant Ingress-safe Web UI template.

This repository serves the Web UI from a single HTML file (webui.html) so it works
cleanly behind Home Assistant Ingress without requiring a static file server.

To make the UI easier to edit and review, the source is split into:
- webui_src.html (HTML skeleton + placeholders)
- webui_css/*.css (CSS parts -> generates webui.css)
- webui_html/*.html (HTML body split into partials)
- webui_js/*.js    (JavaScript split into parts)

This script assembles webui_html/*.html, then inlines the bundled webui.css (from webui_css/*.css parts) and the JS bundle (from webui_js/*.js) into webui_src.html to produce webui.html.

Usage (from repo root):
    python pythonista_job_runner/app/webui_build.py

Optional:
    python pythonista_job_runner/app/webui_build.py --check
      Raises RuntimeError if webui.html is out of date.
"""

from dataclasses import dataclass
from pathlib import Path

import re


WEBUI_VERSION = "0.6.17-webui.1"

_RE_JS_VERSION_HEADER = re.compile(r"^\s*(//|/\*)\s*VERSION\s*:", re.IGNORECASE)

_SRC_HTML_VERSION_RE = re.compile(
    r'^\s*<!doctype\s+html><!--\s*VERSION:\s*([^ ]+)\s*-->\s*$',
    re.IGNORECASE,
)


_OUT_TEXT_VERSION_RE = re.compile(
    r'^\s*/\*\s*VERSION:\s*([^\s*]+)\s*\*/\s*$',
    re.IGNORECASE,
)

_README_VERSION_RE = re.compile(
    r'^\s*<!--\s*Version:\s*([^ ]+)\s*-->\s*$',
    re.IGNORECASE,
)

_HTML_PART_VERSION_RE = re.compile(r'^\s*<!--\s*Version:\s*([^ ]+)\s*-->\s*$', re.IGNORECASE)


def _assert_parts_readme_versions(p: "WebUiPaths") -> None:
    """Ensure webui_* part README files do not declare a version header.

    The Web UI version is controlled centrally by WEBUI_VERSION in this builder.
    Allowing per-folder README version headers creates a second, drifting "doc version"
    that is easy to forget to update.

    Rule:
    - README.md may exist or not.
    - If it exists, it must not contain an HTML comment of the form:
        <!-- Version: ... -->
    """

    base = p.src_html.parent
    for folder in ("webui_html", "webui_css", "webui_js"):
        readme = base / folder / "README.md"
        if not readme.is_file():
            continue

        # Fail if a version header appears anywhere in the README.
        # We check the first few lines for speed, then fall back to a full scan
        # if needed (the files are small).
        text = readme.read_text(encoding="utf-8")
        lines = text.splitlines()
        scan_lines = lines[:10] if lines else []
        found_line = None
        for i, line in enumerate(scan_lines, start=1):
            if _README_VERSION_RE.match(line):
                found_line = (i, line)
                break
        if found_line is None:
            # Full scan only if the token appears, to avoid work on normal files.
            if "Version:" in text or "VERSION:" in text:
                for i, line in enumerate(lines, start=1):
                    if _README_VERSION_RE.match(line):
                        found_line = (i, line)
                        break

        if found_line is not None:
            i, line = found_line
            raise RuntimeError(
                f"{folder}/README.md must not declare a version header; "
                f"remove the line {line!r} (line {i})"
            )


def _assert_src_html_version_matches(src_html_path: Path, src_text: str) -> None:
    """Ensure webui_src.html VERSION comment matches WEBUI_VERSION."""
    first_line = src_text.splitlines()[0] if src_text else ""
    m = _SRC_HTML_VERSION_RE.match(first_line)
    if not m:
        raise RuntimeError(
            f"{src_html_path.name} first line must be '<!doctype html><!-- VERSION: {WEBUI_VERSION} -->' "
            f"(found {first_line!r})"
        )
    found = m.group(1)
    if found != WEBUI_VERSION:
        raise RuntimeError(
            f"{src_html_path.name} VERSION ({found}) does not match WEBUI_VERSION ({WEBUI_VERSION})"
        )




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
    "20_jobs.html",
    "10_overview.html",
    "30_detail.html",
    "40_advanced.html",
    "42_setup.html",
    "45_settings.html",
    "50_help.html",
    "55_overlays.html",
    "60_toast.html",
)


WEBUI_JS_PARTS: tuple[str, ...] = (
    "00_core.js",
    "10_render_search.js",
    "20_detail_meta.js",
    "30_refresh_actions.js",
    "40_events_init.js",
)

WEBUI_CSS_PARTS: tuple[str, ...] = (
    "00_tokens.css",
    "10_layout.css",
    "20_jobs_table.css",
    "30_logs.css",
    "40_overlays.css",
    "50_responsive.css",
)





_ROOT_RELATIVE_PATTERNS_HTML: tuple[str, ...] = (
    'href="/',
    "href='/",
    'src="/',
    "src='/",
    'srcset="/',
    "srcset='/",
    'action="/',
    "action='/",
)

_ROOT_RELATIVE_PATTERNS_JS: tuple[str, ...] = (
    'fetch("/',
    "fetch('/",
    'new URL("/',
    "new URL('/",
    'window.open("/',
    "window.open('/",
    'window.location = "/',
    "window.location = '/",
    'location.href = "/',
    "location.href = '/",
)

_ROOT_RELATIVE_PATTERNS_CSS: tuple[str, ...] = (
    "url(/",
    'url("/',
    "url('/",
    '@import "/',
    "@import '/",
    '@import url("/',
    "@import url('/",
    "@import url(/",
)


def _raise_root_relative_error(source: str, line_no: int, pat: str, line: str) -> None:
    """Raise a user-facing error for a root-relative reference.

    Home Assistant Ingress runs add-ons under a path prefix, so root-relative
    references typically break by pointing at the Home Assistant host root.
    """

    snippet = line.strip()
    if len(snippet) > 240:
        snippet = snippet[:237] + "..."
    raise RuntimeError(
        f"Root-relative reference found in {source}:{line_no}: {pat}\n"
        f"  {snippet}"
    )


def _check_root_relative_in_text(source: str, text: str, patterns: tuple[str, ...]) -> None:
    """Raise if text contains a root-relative reference matching patterns."""

    for idx, line in enumerate(text.splitlines(), start=1):
        for pat in patterns:
            if pat in line:
                _raise_root_relative_error(source=source, line_no=idx, pat=pat, line=line)


def _check_unique_html_ids(texts_by_part: dict[str, str]) -> None:
    """Raise if duplicate HTML id attributes exist across parts.

    IDs must be unique across the assembled document. This catches accidental
    collisions when editing a single partial in isolation.
    """

    id_pat = re.compile(r"\bid\s*=\s*(?:\"([^\"]+)\"|'([^']+)')")
    id_to_counts: dict[str, dict[str, int]] = {}
    for part_name, txt in texts_by_part.items():
        for m in id_pat.finditer(txt):
            id_val = m.group(1) or m.group(2)
            if not id_val:
                continue
            counts = id_to_counts.setdefault(id_val, {})
            counts[part_name] = counts.get(part_name, 0) + 1

    duplicates = {k: v for k, v in id_to_counts.items() if sum(v.values()) > 1}
    if not duplicates:
        return

    lines: list[str] = []
    for id_val, counts in sorted(duplicates.items()):
        parts = ", ".join(
            f"{name} ({cnt})" if cnt > 1 else name
            for name, cnt in sorted(counts.items())
        )
        lines.append(f"  id=\"{id_val}\" in: {parts}")

    raise RuntimeError(
        "Duplicate HTML element id attribute(s) across webui_html parts:\n"
        + "\n".join(lines)
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

    texts_by_part: dict[str, str] = {}
    texts: list[str] = []
    for part in expected_paths:
        txt = part.read_text(encoding="utf-8").rstrip()
        if any(_RE_JS_VERSION_HEADER.search(line) for line in txt.splitlines()[:3]):
            raise RuntimeError(f"HTML part must not contain JavaScript-style VERSION header: {part}")
        for i, line in enumerate(txt.splitlines(), start=1):
            if _HTML_PART_VERSION_RE.match(line):
                raise RuntimeError(
                    f"HTML part must not declare Version header comment: webui_html/{part.name}:{i}"
                )
        for pat in banned_patterns:
            if pat.search(txt):
                raise RuntimeError(f"HTML part contains forbidden tag/pattern ({pat.pattern}): {part}")

        _check_root_relative_in_text(
            source=f"webui_html/{part.name}",
            text=txt,
            patterns=_ROOT_RELATIVE_PATTERNS_HTML,
        )

        texts.append(txt)
        texts_by_part[part.name] = txt

    _check_unique_html_ids(texts_by_part)
    return "\n".join(texts).rstrip()


def _read_js_bundle(p: WebUiPaths) -> str:
    """Return the JavaScript bundle text from webui_js/*.js parts.

    The assembly order is explicit (WEBUI_JS_PARTS) to make builds deterministic.
    """

    parts_dir = p.js.with_name("webui_js")
    if not parts_dir.is_dir():
        raise RuntimeError(f"Web UI JavaScript parts directory not found: {parts_dir}")

    expected_paths = [parts_dir / name for name in WEBUI_JS_PARTS]
    missing = [x.name for x in expected_paths if not x.is_file()]
    if missing:
        raise RuntimeError(
            "Missing expected Web UI JavaScript part(s): " + "; ".join(missing)
        )

    unexpected = sorted(
        x.name
        for x in parts_dir.glob("*.js")
        if x.is_file() and x.name not in WEBUI_JS_PARTS
    )
    if unexpected:
        raise RuntimeError(
            "Unexpected Web UI JavaScript part(s): " + "; ".join(unexpected)
            + "\nIf you intended to add a part, update WEBUI_JS_PARTS in webui_build.py."
        )

    texts: list[str] = []
    for part in expected_paths:
        txt = part.read_text(encoding="utf-8").rstrip()
        if any(_RE_JS_VERSION_HEADER.search(line) for line in txt.splitlines()[:3]):
            raise RuntimeError(f"JavaScript part must not declare VERSION header: {part}")
        _check_root_relative_in_text(
            source=f"webui_js/{part.name}",
            text=txt,
            patterns=_ROOT_RELATIVE_PATTERNS_JS,
        )
        texts.append(txt)

    return "\n".join(texts).rstrip()


def _read_css_bundle(p: WebUiPaths) -> str:
    """Return the CSS bundle text from webui_css/*.css parts.

    The assembly order is explicit (WEBUI_CSS_PARTS) to make builds deterministic.
    """

    parts_dir = p.css.with_name("webui_css")
    if not parts_dir.is_dir():
        raise RuntimeError(f"Web UI CSS parts directory not found: {parts_dir}")

    expected_paths = [parts_dir / name for name in WEBUI_CSS_PARTS]
    missing = [x.name for x in expected_paths if not x.is_file()]
    if missing:
        raise RuntimeError("Missing expected Web UI CSS part(s): " + "; ".join(missing))

    unexpected = sorted(
        x.name
        for x in parts_dir.glob("*.css")
        if x.is_file() and x.name not in WEBUI_CSS_PARTS
    )
    if unexpected:
        raise RuntimeError(
            "Unexpected Web UI CSS part(s): " + "; ".join(unexpected)
            + "\nIf you intended to add a part, update WEBUI_CSS_PARTS in webui_build.py."
        )

    texts: list[str] = []
    for part in expected_paths:
        txt = part.read_text(encoding="utf-8")
        if any("VERSION:" in line for line in txt.splitlines()[0:3]):
            raise RuntimeError(f"CSS part must not declare VERSION header: {part}")

        _check_root_relative_in_text(
            source=f"webui_css/{part.name}",
            text=txt,
            patterns=_ROOT_RELATIVE_PATTERNS_CSS,
        )
        if txt and not txt.endswith("\n"):
            txt += "\n"
        texts.append(txt)

    return "".join(texts)


def _build_css(p: WebUiPaths) -> str:
    """Return the generated webui.css content as a string."""

    # Keep the version header as the first line for easy identification.
    version = WEBUI_VERSION
    body = _read_css_bundle(p)
    out = f"/* VERSION: {version} */\n" + body
    if not out.endswith("\n"):
        out += "\n"
    return out


def _build_js(p: WebUiPaths) -> str:
    """Return the generated webui.js content as a string."""

    # Keep the version header as the first line for easy identification.
    version = WEBUI_VERSION
    body = _read_js_bundle(p)
    out = f"/* VERSION: {version} */\n" + body
    if not out.endswith("\n"):
        out += "\n"
    return out


def build_webui(paths: WebUiPaths | None = None) -> str:
    """Return the bundled webui.html content as a string."""

    p = paths or _default_paths()

    src = p.src_html.read_text(encoding="utf-8")
    _assert_src_html_version_matches(p.src_html, src)
    _assert_parts_readme_versions(p)

    css = _build_css(p)

    body = _read_html_parts(p)
    js = _build_js(p)
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
    _check_root_relative_in_text(
        source="webui bundle (post-assembly)",
        text=out,
        patterns=_ROOT_RELATIVE_PATTERNS_HTML
        + _ROOT_RELATIVE_PATTERNS_JS
        + _ROOT_RELATIVE_PATTERNS_CSS,
    )

    return out


def write_webui(paths: WebUiPaths | None = None) -> None:
    """Write webui.html, webui.css, and webui.js in-place."""

    p = paths or _default_paths()
    _assert_parts_readme_versions(p)
    css = _build_css(p)
    js = _build_js(p)
    out = build_webui(p)

    p.css.write_text(css, encoding="utf-8")
    p.js.write_text(js, encoding="utf-8")
    p.out_html.write_text(out, encoding="utf-8")



def _assert_output_text_version_header(path: Path, text: str) -> None:
    """Ensure a generated text output starts with a VERSION header matching WEBUI_VERSION."""
    first_line = text.splitlines()[0] if text else ""
    m = _OUT_TEXT_VERSION_RE.match(first_line)
    if not m:
        raise RuntimeError(
            f"{path.name} first line must be '/* VERSION: {WEBUI_VERSION} */' (found {first_line!r})"
        )
    found = m.group(1)
    if found != WEBUI_VERSION:
        raise RuntimeError(
            f"{path.name} VERSION ({found}) does not match WEBUI_VERSION ({WEBUI_VERSION})"
        )


def _assert_output_html_version_header(path: Path, text: str) -> None:
    """Ensure a generated HTML output starts with a VERSION comment matching WEBUI_VERSION."""
    first_line = text.splitlines()[0] if text else ""
    m = _SRC_HTML_VERSION_RE.match(first_line)
    if not m:
        raise RuntimeError(
            f"{path.name} first line must be '<!doctype html><!-- VERSION: {WEBUI_VERSION} -->' (found {first_line!r})"
        )
    found = m.group(1)
    if found != WEBUI_VERSION:
        raise RuntimeError(
            f"{path.name} VERSION ({found}) does not match WEBUI_VERSION ({WEBUI_VERSION})"
        )


def _assert_generated_outputs_version_headers(p: WebUiPaths, css_text: str, js_text: str, html_text: str) -> None:
    """Ensure generated outputs include a consistent VERSION header."""
    _assert_output_text_version_header(p.css, css_text)
    _assert_output_text_version_header(p.js, js_text)
    _assert_output_html_version_header(p.out_html, html_text)

def check_webui(paths: WebUiPaths | None = None) -> None:
    """Raise RuntimeError if generated Web UI outputs are out of date."""

    p = paths or _default_paths()
    _assert_parts_readme_versions(p)

    actual_css = p.css.read_text(encoding="utf-8")
    actual_js = p.js.read_text(encoding="utf-8")
    actual_html = p.out_html.read_text(encoding="utf-8")

    _assert_generated_outputs_version_headers(p, actual_css, actual_js, actual_html)

    expected_css = _build_css(p)
    if actual_css != expected_css:
        raise RuntimeError("webui.css is out of date. Run webui_build.py to regenerate it.")

    expected_js = _build_js(p)
    if actual_js != expected_js:
        raise RuntimeError("webui.js is out of date. Run webui_build.py to regenerate it.")

    expected_html = build_webui(p)
    if actual_html != expected_html:
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