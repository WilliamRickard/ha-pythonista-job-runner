# Version: 0.6.12-docs.1
"""Keeps approved screenshot filenames in sync across docs and assets."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / 'README.md'
SCREENSHOT_README_PATH = REPO_ROOT / 'docs' / 'screenshots' / 'README.md'
SCREENSHOT_DIR = REPO_ROOT / 'docs' / 'screenshots'
README_IMAGE_RE = re.compile(r'!\[[^\]]+\]\(docs/screenshots/([^)]+)\)')
APPROVED_LINK_RE = re.compile(r'\[[^\]]+\]\(([^)]+\.png)\)')


def test_screenshot_filenames_stay_in_sync() -> None:
    """Root README screenshots, approved filenames, and actual PNG assets should match exactly."""
    embedded = set(README_IMAGE_RE.findall(README_PATH.read_text(encoding='utf-8')))
    approved = {
        Path(target).name
        for target in APPROVED_LINK_RE.findall(SCREENSHOT_README_PATH.read_text(encoding='utf-8'))
    }
    actual = {path.name for path in SCREENSHOT_DIR.glob('*.png')}

    assert embedded, 'README.md does not embed any docs/screenshots PNGs'
    assert approved, 'docs/screenshots/README.md does not list any approved screenshot PNGs'
    assert embedded == approved == actual, (
        'Screenshot filenames must stay aligned across README.md, docs/screenshots/README.md, and docs/screenshots/*.png\n'
        f'embedded={sorted(embedded)!r}\n'
        f'approved={sorted(approved)!r}\n'
        f'actual={sorted(actual)!r}'
    )
