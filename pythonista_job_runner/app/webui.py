from __future__ import annotations

"""
Web UI generator.

The HTML template lives in a separate file (webui.html) so it is easier to edit and review.
The template is generated from webui_src.html/webui.css/webui_js/*.js via webui_build.py.
The template must only use relative URLs, because Home Assistant ingress proxies under a path prefix.
"""

from pathlib import Path


_TEMPLATE_PATH = Path(__file__).with_name("webui.html")
_TEMPLATE_CACHE: str | None = None


def _template_text() -> str:
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is None:
        _TEMPLATE_CACHE = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return _TEMPLATE_CACHE


def html_page(addon_version: str) -> bytes:
    """Return the add-on Web UI HTML document as UTF-8 bytes."""
    html_text = _template_text().replace("__ADDON_VERSION__", addon_version)
    return html_text.encode("utf-8")
