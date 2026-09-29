"""Repo-level audit tests.

File-level invariants that catch "we generated this; did we get
it right?" bugs without needing to boot linbpq.  Cheap to run,
high-leverage protection on docs / samples.

Each audit lives here as a separate test so failures pinpoint
the class of bug.  All tests are pure-file inspection, so they
run in milliseconds.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_HTML_DIR = _REPO_ROOT / "HTML"
_DOCS_DIR = _REPO_ROOT / "docs"


# Citation context that should be ignored when extracting
# source-line refs from markdown — e.g. release notes, change
# logs, or example code blocks where the citation is illustrative
# rather than authoritative.  None currently; placeholder for
# future use.
_CITATION_IGNORE_FILES = set()


# ── HTML/samples/ artefact sweep ─────────────────────────────────


def test_samples_files_have_no_extraction_artefacts():
    """No stray C-source backslash sequences in ``HTML/samples/``.

    The samples were copied verbatim from John Wiseman's
    NodePages.zip, so we don't expect any, but the audit guards
    against a future change that regenerates them from C source.
    """
    samples_dir = _HTML_DIR / "samples"
    if not samples_dir.is_dir():
        pytest.skip("HTML/samples/ not present")

    offenders: list[str] = []
    for path in sorted(samples_dir.iterdir()):
        if not path.is_file():
            continue
        text = path.read_text(errors="replace")
        for m in re.finditer(r"\\.", text):
            offenders.append(
                f"{path.name}:{m.start()}: {m.group(0)!r}  "
                f"(context: {text[max(0, m.start()-20):m.end()+20]!r})"
            )
        for ln_idx, line in enumerate(text.splitlines(), 1):
            if line.endswith("\\"):
                offenders.append(
                    f"{path.name}:{ln_idx}: trailing backslash"
                )
    assert not offenders, (
        "samples/ contain backslash artefacts:\n  " + "\n  ".join(offenders)
    )


# ── Sample placeholder support ───────────────────────────────────


def test_sample_placeholders_are_supported():
    """``HTML/samples/`` files use ``##NAME##`` placeholders that
    ``HTTPcode.c::LookupKey`` resolves at serve time.  Any
    placeholder used in samples must be in ``LookupKey``'s
    handled set, otherwise ``ProcessSpecialPage`` leaves it
    rendered as the literal ``##NAME##`` string in the user's
    browser.
    """
    samples_dir = _HTML_DIR / "samples"
    if not samples_dir.is_dir():
        pytest.skip("HTML/samples/ not present")

    placeholders: set[str] = set()
    for path in samples_dir.iterdir():
        if not path.is_file():
            continue
        for m in re.finditer(r"##[A-Z_]+##", path.read_text(errors="replace")):
            placeholders.add(m.group(0))

    if not placeholders:
        pytest.skip("no ##XXX## placeholders to verify")

    httpcode = (_REPO_ROOT / "HTTPcode.c").read_text(errors="replace")
    unsupported = [
        ph for ph in sorted(placeholders) if f'"{ph}"' not in httpcode
    ]
    assert not unsupported, (
        f"placeholders used in HTML/samples/ but not handled in "
        f"HTTPcode.c::LookupKey: {unsupported}"
    )


# ── Docs internal-link health ────────────────────────────────────


_MD_LINK_RE = re.compile(r"\]\(([^)]+)\)")


def test_docs_markdown_internal_links_resolve():
    """Every ``[text](path)`` link in ``docs/*.md`` that points
    at a local file (not http(s)/mailto/anchor-only) must
    resolve to a real file on disk.

    Catches stale references to renamed files / moved tests.
    """
    if not _DOCS_DIR.is_dir():
        pytest.skip("docs/ not present")

    broken: list[str] = []
    for md in sorted(_DOCS_DIR.rglob("*.md")):
        text = md.read_text(errors="replace")
        for m in _MD_LINK_RE.finditer(text):
            ref = m.group(1).strip()
            # Strip fragment / query.
            target = re.split(r"[#?]", ref, maxsplit=1)[0]
            if not target:
                continue  # anchor-only link
            if re.match(r"[a-zA-Z][a-zA-Z+.-]*:", target):
                continue  # http://, https://, mailto:, etc.
            # Resolve relative to the markdown file's dir.
            if target.startswith("/"):
                resolved = _REPO_ROOT / target.lstrip("/")
            else:
                resolved = (md.parent / target).resolve()
            if not resolved.exists():
                broken.append(
                    f"{md.relative_to(_REPO_ROOT)}: -> {ref}  "
                    f"(resolved: {resolved})"
                )

    assert not broken, "broken markdown links:\n  " + "\n  ".join(broken)


# ── Source-line citation gate ────────────────────────────────────


# Match patterns like ``AGWAPI.c:1383`` or ``Cmd.c:1185`` — file
# starting with an uppercase letter, ending in ``.c``, then a
# colon, then a line number.  Surrounding word boundaries so we
# don't catch fragments like ``foo.c:bar``.  Restricted to ``.c``
# so we don't match Markdown paths like ``docs/index.md:23``.
_CITATION_RE = re.compile(r"\b([A-Z][A-Za-z0-9]+\.c):(\d+)\b")


def test_docs_source_line_citations_are_valid():
    """Every ``<File>.c:<line>`` reference in docs/**/*.md must
    point at a file that exists at the repo root and a line that
    falls within the file's current length.

    This catches the most common rot: a refactor moves a
    function, the line numbers in the docs go stale, future
    readers chase phantom citations.  If a citation is no longer
    valid, the gate fires; either fix the line number, or remove
    the citation.

    The check is line-range only (we don't verify the line
    *content* matches what the doc claims).  A stricter v2
    sentinel form ``[FILE.c:N "expected text"]`` could be added
    if the line-range check turns out to be too lax; for now,
    line-range is enough to pin down the most common rot
    (refactors that shift code, files renamed/deleted).
    """
    if not _DOCS_DIR.is_dir():
        pytest.skip("docs/ not present")

    # Cache file line counts so we don't re-read the same file
    # for each citation pointing into it.
    line_counts: dict[Path, int] = {}

    def _line_count(path: Path) -> int:
        if path not in line_counts:
            try:
                line_counts[path] = sum(1 for _ in path.open("rb"))
            except OSError:
                line_counts[path] = -1
        return line_counts[path]

    bad: list[str] = []
    for md in sorted(_DOCS_DIR.rglob("*.md")):
        if md.name in _CITATION_IGNORE_FILES:
            continue
        text = md.read_text(errors="replace")
        for match in _CITATION_RE.finditer(text):
            cfile = match.group(1)
            line = int(match.group(2))
            cpath = _REPO_ROOT / cfile
            if not cpath.exists():
                bad.append(
                    f"{md.relative_to(_REPO_ROOT)}: cites "
                    f"`{cfile}:{line}` — file does not exist"
                )
                continue
            total = _line_count(cpath)
            if total < 0:
                bad.append(
                    f"{md.relative_to(_REPO_ROOT)}: cites "
                    f"`{cfile}:{line}` — couldn't read file"
                )
                continue
            if line < 1 or line > total:
                bad.append(
                    f"{md.relative_to(_REPO_ROOT)}: cites "
                    f"`{cfile}:{line}` — line out of range "
                    f"(file has {total} lines)"
                )

    assert not bad, (
        f"{len(bad)} stale source-line citation(s) in docs:\n  "
        + "\n  ".join(bad)
    )


def test_docs_source_line_citations_present():
    """Sanity check that the citation regex actually matches at
    least one citation.  If a future restructure scrubs all
    ``<file>.c:<line>`` references from docs, this gate would
    silently pass; this companion test fires if that happens."""
    if not _DOCS_DIR.is_dir():
        pytest.skip("docs/ not present")

    total = 0
    for md in _DOCS_DIR.rglob("*.md"):
        text = md.read_text(errors="replace")
        total += sum(1 for _ in _CITATION_RE.finditer(text))
    assert total > 0, (
        "No <File>.c:<line> citations found in docs.  Either the "
        "regex broke or every doc citation has been removed — "
        "either way, ``test_docs_source_line_citations_are_valid`` "
        "wouldn't catch real drift now."
    )
