# Version: 0.6.12-docs.3
"""Checks internal Markdown links, anchors, and prose references stay tidy."""

from __future__ import annotations

import re
from pathlib import Path

DOC_FILES = [
    Path('README.md'),
    Path('CONTRIBUTING.md'),
    Path('SECURITY.md'),
    Path('docs/screenshots/README.md'),
    Path('pythonista_job_runner/README.md'),
    Path('pythonista_job_runner/DOCS.md'),
    Path('pythonista_job_runner/CHANGELOG.md'),
]

PLAIN_REFERENCE_DOC_FILES = [path for path in DOC_FILES if path.name != 'CHANGELOG.md']

EXTERNAL_PREFIXES = ('http://', 'https://', 'mailto:', 'tel:')
LINK_RE = re.compile(r'!?\[[^\]]+\]\(([^)]+)\)')
TEXT_LINK_RE = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$', re.MULTILINE)
COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)
FENCE_RE = re.compile(r'^```.*?^```\s*$', re.MULTILINE | re.DOTALL)
LINK_OR_IMAGE_RE = re.compile(r'!?\[[^\]]+\]\(([^)]+)\)')
INLINE_CODE_RE = re.compile(r'`([^`\n]+)`')
PATH_TEXT_RE = re.compile(
    r'(?<![\w/.-])'
    r'((?:\.\./)?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:md|yaml|yml|py|html|css|js|png|json)(?:#[A-Za-z0-9_-]+)?)'
    r'(?![\w/.-])'
)


def _visible_markdown(text: str) -> str:
    """Strip comments and fenced code blocks before scanning Markdown prose."""
    text = COMMENT_RE.sub('', text)
    return FENCE_RE.sub('', text)


def _slugify_heading(heading: str, seen: dict[str, int]) -> str:
    """Return a GitHub-style anchor slug for the supplied heading."""
    heading = re.sub(r'`([^`]*)`', r'\1', heading)
    heading = re.sub(r'<[^>]+>', '', heading)
    heading = heading.strip().lower()
    heading = re.sub(r'[^\w\- ]', '', heading)
    heading = re.sub(r'\s+', '-', heading).strip('-')
    if not heading:
        heading = 'section'
    count = seen.get(heading, 0)
    seen[heading] = count + 1
    if count:
        return f'{heading}-{count}'
    return heading


def _anchors_for(markdown_path: Path) -> set[str]:
    """Collect valid anchor names for the supplied Markdown file."""
    text = _visible_markdown(markdown_path.read_text(encoding='utf-8'))
    seen: dict[str, int] = {}
    anchors = set()
    for match in HEADING_RE.finditer(text):
        anchors.add(_slugify_heading(match.group(2), seen))
    return anchors


def _iter_internal_links(markdown_path: Path) -> list[str]:
    """Yield internal Markdown link targets from visible prose only."""
    text = _visible_markdown(markdown_path.read_text(encoding='utf-8'))
    return [target for target in LINK_RE.findall(text) if not target.startswith(EXTERNAL_PREFIXES)]


def _resolve_repo_target(markdown_path: Path, target: str) -> Path | None:
    """Resolve a repo-relative target and return it when it exists."""
    path_part = target.partition('#')[0]
    if not path_part:
        return None
    repo_root = Path(__file__).resolve().parents[2]
    candidate_paths = [
        (markdown_path.parent / path_part).resolve(),
        (repo_root / path_part).resolve(),
    ]
    for candidate in candidate_paths:
        if candidate.exists():
            return candidate
    return None


def _visible_text_without_links(markdown_path: Path) -> str:
    """Return visible Markdown prose with links removed for plain-text scans."""
    text = _visible_markdown(markdown_path.read_text(encoding='utf-8'))
    return LINK_OR_IMAGE_RE.sub('', text)


def _iter_section_blocks(markdown_path: Path) -> list[tuple[str, int, str]]:
    """Yield visible prose blocks grouped under the current Markdown heading."""
    text = _visible_markdown(markdown_path.read_text(encoding='utf-8'))
    blocks: list[tuple[str, int, str]] = []
    current_heading = '(preamble)'
    current_lines: list[tuple[int, str]] = []

    def flush() -> None:
        nonlocal current_lines
        if not current_lines:
            return
        block_text = '\n'.join(line for _line_number, line in current_lines).strip()
        if block_text:
            blocks.append((current_heading, current_lines[0][0], block_text))
        current_lines = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        heading_match = re.match(r'^(#{1,6})\s+(.*)$', line)
        if heading_match:
            flush()
            current_heading = heading_match.group(2).strip()
            continue
        if not line.strip():
            flush()
            continue
        if re.match(r'^\s*(?:[-*+] |\d+\. )', line):
            flush()
            current_lines = [(line_number, line)]
            flush()
            continue
        current_lines.append((line_number, line))
    flush()
    return blocks


def test_internal_markdown_links_resolve() -> None:
    """All internal Markdown links should point to real files and anchors."""
    repo_root = Path(__file__).resolve().parents[2]
    for relative_doc in DOC_FILES:
        markdown_path = repo_root / relative_doc
        current_anchors = _anchors_for(markdown_path)
        for target in _iter_internal_links(markdown_path):
            path_part, _sep, anchor = target.partition('#')
            if not path_part:
                resolved_path = markdown_path
            else:
                resolved_path = (markdown_path.parent / path_part).resolve()
                assert resolved_path.exists(), (
                    f'{relative_doc}: missing target {path_part!r} in link {target!r}'
                )
            if anchor:
                assert resolved_path.suffix.lower() == '.md', (
                    f'{relative_doc}: anchor used for non-Markdown target {target!r}'
                )
                anchors = current_anchors if resolved_path == markdown_path else _anchors_for(resolved_path)
                assert anchor in anchors, (
                    f'{relative_doc}: missing anchor #{anchor} in {resolved_path.relative_to(repo_root)}'
                )


def test_internal_markdown_links_do_not_repeat_within_a_single_block() -> None:
    """Repeated internal links inside one prose block should be intentional, not accidental."""
    repo_root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []

    for relative_doc in DOC_FILES:
        markdown_path = repo_root / relative_doc
        for heading, line_number, block_text in _iter_section_blocks(markdown_path):
            targets = [
                target
                for target in TEXT_LINK_RE.findall(block_text)
                if not target.startswith(EXTERNAL_PREFIXES)
            ]
            for target in sorted(set(targets)):
                count = targets.count(target)
                if count > 1:
                    offenders.append(
                        f'{relative_doc}:{line_number}: repeated internal link {target!r} {count} times in section {heading!r}'
                    )

    assert not offenders, (
        'Use a single internal Markdown link per prose block when repeated links look accidental:\n'
        + '\n'.join(offenders)
    )


def test_internal_file_references_use_markdown_links() -> None:
    """Repo file references in visible prose should use Markdown links."""
    repo_root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []

    for relative_doc in PLAIN_REFERENCE_DOC_FILES:
        markdown_path = repo_root / relative_doc
        visible_text = _visible_text_without_links(markdown_path)

        for match in INLINE_CODE_RE.finditer(visible_text):
            candidate = match.group(1).strip()
            if ' ' in candidate:
                continue
            if PATH_TEXT_RE.fullmatch(candidate) is None:
                continue
            if _resolve_repo_target(markdown_path, candidate) is None:
                continue
            line_number = visible_text.count('\n', 0, match.start()) + 1
            offenders.append(
                f'{relative_doc}:{line_number}: unlinked inline repo path {candidate!r}'
            )

        prose_text = INLINE_CODE_RE.sub('', visible_text)
        for match in PATH_TEXT_RE.finditer(prose_text):
            candidate = match.group(1)
            if _resolve_repo_target(markdown_path, candidate) is None:
                continue
            line_number = prose_text.count('\n', 0, match.start()) + 1
            offenders.append(
                f'{relative_doc}:{line_number}: unlinked repo path {candidate!r}'
            )

    assert not offenders, 'Use Markdown links for internal repo file references:\n' + '\n'.join(offenders)
