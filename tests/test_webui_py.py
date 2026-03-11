"""Tests for webui.html serving helper."""

from __future__ import annotations

from pathlib import Path

import webui


def test_html_page_replaces_addon_version_and_uses_cached_template(tmp_path, monkeypatch) -> None:
    template = tmp_path / "webui.html"
    template.write_text("<html>__ADDON_VERSION__</html>", encoding="utf-8")

    monkeypatch.setattr(webui, "_TEMPLATE_PATH", template)
    monkeypatch.setattr(webui, "_TEMPLATE_CACHE", None)

    calls = {"count": 0}
    original_read_text = Path.read_text

    def _counting_read_text(path_self: Path, *args, **kwargs):
        if path_self == template:
            calls["count"] += 1
        return original_read_text(path_self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    first = webui.html_page("1.2.3").decode("utf-8")
    second = webui.html_page("9.9.9").decode("utf-8")

    assert first == "<html>1.2.3</html>"
    assert second == "<html>9.9.9</html>"
    assert calls["count"] == 1
