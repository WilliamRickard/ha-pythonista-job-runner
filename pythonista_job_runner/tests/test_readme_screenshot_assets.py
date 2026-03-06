# Version: 0.6.12-docs.2
"""Checks screenshot assets embedded by the root README exist and are usable."""

from __future__ import annotations

import re
import struct
from pathlib import Path

README_PATH = Path(__file__).resolve().parents[2] / 'README.md'
MIN_WIDTH = 1000
MIN_HEIGHT = 600
MAX_WIDTH = 2000
MAX_HEIGHT = 1400
IMAGE_RE = re.compile(r'!\[([^\]]+)\]\((docs/screenshots/[^)]+)\)')
ALT_TEXT_KEYWORDS = {
    '01_addon_store.png': ('add-on', 'store'),
    '02_config_token.png': ('configuration', 'token'),
    '03_webui_jobs.png': ('web ui', 'jobs'),
}


def _read_png_size(image_path: Path) -> tuple[int, int]:
    """Return PNG image dimensions from the IHDR chunk."""
    data = image_path.read_bytes()
    assert data.startswith(b'\x89PNG\r\n\x1a\n'), f'{image_path} is not a valid PNG file'
    width, height = struct.unpack('>II', data[16:24])
    return width, height


def _iter_readme_screenshots() -> list[tuple[str, Path]]:
    """Collect screenshot alt text and image paths embedded by the root README."""
    screenshots: list[tuple[str, Path]] = []
    for alt_text, target in IMAGE_RE.findall(README_PATH.read_text(encoding='utf-8')):
        screenshots.append((alt_text.strip(), README_PATH.parent / target))
    return screenshots


def test_readme_screenshot_assets_have_reasonable_dimensions() -> None:
    """Embedded README screenshots should exist and be large enough to read."""
    screenshots = _iter_readme_screenshots()
    assert screenshots, 'Root README does not embed any docs/screenshots images'

    for _alt_text, image_path in screenshots:
        assert image_path.exists(), f'Missing embedded screenshot: {image_path.relative_to(README_PATH.parent)}'
        assert image_path.suffix.lower() == '.png', (
            f'{image_path.relative_to(README_PATH.parent)} should stay PNG to match the current docs guidance'
        )
        width, height = _read_png_size(image_path)
        assert MIN_WIDTH <= width <= MAX_WIDTH, (
            f'{image_path.name} width {width}px is outside the expected range '
            f'{MIN_WIDTH}-{MAX_WIDTH}px'
        )
        assert MIN_HEIGHT <= height <= MAX_HEIGHT, (
            f'{image_path.name} height {height}px is outside the expected range '
            f'{MIN_HEIGHT}-{MAX_HEIGHT}px'
        )


def test_readme_screenshot_alt_text_is_descriptive() -> None:
    """Embedded README screenshots should have meaningful alt text."""
    screenshots = _iter_readme_screenshots()
    assert screenshots, 'Root README does not embed any docs/screenshots images'

    for alt_text, image_path in screenshots:
        lowered = alt_text.lower()
        assert alt_text, f'{image_path.name} is missing alt text'
        assert 'placeholder' not in lowered, (
            f'{image_path.name} alt text should describe the intended image, not call it a placeholder'
        )
        if image_path.name not in ALT_TEXT_KEYWORDS:
            raise AssertionError(
                f'{image_path.name} is not in ALT_TEXT_KEYWORDS. '
                f'Add it to the dictionary or remove the unexpected screenshot file.'
            )
        keywords = ALT_TEXT_KEYWORDS.get(image_path.name)
        assert keywords is not None, (
            f'{image_path.name} is not present in ALT_TEXT_KEYWORDS; please add expected keyword(s) for this '
            f'screenshot to {__file__} (ALT_TEXT_KEYWORDS dict)'
        )
        matches = sum(1 for keyword in keywords if keyword in lowered)
        assert matches >= 2, (
            f'{image_path.name} alt text should mention its purpose; expected keywords {keywords!r}, got {alt_text!r}'
        )
