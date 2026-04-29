"""Repo-level audit tests.

File-level invariants that catch "we generated this; did we get
it right?" bugs without needing to boot linbpq.  Cheap to run,
high-leverage protection on extraction work / docs / samples.

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


# ── Template existence / orphan audits ───────────────────────────


def _c_source_files() -> list[Path]:
    return sorted(p for p in _REPO_ROOT.glob("*.c"))


_TEMPLATE_REF_RE = re.compile(rb'GetTemplateFromFile\(\d+,\s*"([^"]+)"\s*\)')


def test_every_referenced_template_exists():
    """Every ``GetTemplateFromFile(N, "X.txt")`` call across the
    C source must point at a file that exists under ``HTML/``.

    If a template name is referenced but missing, the runtime
    falls back to the literal string ``"File is missing"`` —
    silent UX breakage we want to catch before deploy.
    """
    referenced: set[str] = set()
    for path in _c_source_files():
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for m in _TEMPLATE_REF_RE.finditer(data):
            referenced.add(m.group(1).decode("ascii"))

    missing = [
        name for name in sorted(referenced)
        if not (_HTML_DIR / name).exists()
    ]
    assert not missing, (
        f"C source references templates that don't exist in HTML/: "
        f"{missing}.  These would render as 'File is missing' at runtime."
    )


def test_no_orphan_templates():
    """Every file under ``HTML/*.txt`` and ``HTML/*.js`` must be
    referenced from at least one C source file.

    An orphaned template is dead weight — hints we forgot to
    delete it after a rename or removed the C-side caller.
    """
    referenced: set[str] = set()
    c_blob = b""
    for path in _c_source_files():
        try:
            c_blob += path.read_bytes()
        except OSError:
            pass

    orphans: list[str] = []
    for path in sorted(_HTML_DIR.glob("*.txt")):
        if path.name.encode("ascii") not in c_blob:
            orphans.append(path.name)
    for path in sorted(_HTML_DIR.glob("*.js")):
        if path.name.encode("ascii") not in c_blob:
            orphans.append(path.name)

    assert not orphans, (
        f"templates under HTML/ are not referenced from any C file: "
        f"{orphans}.  Either wire them up or delete them."
    )


# ── Version-marker consistency ───────────────────────────────────


_TEMPLATE_REF_WITH_VERSION_RE = re.compile(
    rb'GetTemplateFromFile\((\d+),\s*"([^"]+)"\s*\)'
)


def test_template_version_markers_match_caller():
    """The first non-blank line of every extracted template is a
    ``<!-- Version N -->`` comment.  Each C-side caller passes a
    version number to ``GetTemplateFromFile`` that *must* match;
    a mismatch returns ``"Wrong Version of HTML Page"`` at
    runtime.

    This audit pins that the on-disk markers and the caller
    versions agree across the repo.
    """
    callers: dict[str, set[int]] = {}
    for path in _c_source_files():
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for m in _TEMPLATE_REF_WITH_VERSION_RE.finditer(data):
            ver = int(m.group(1))
            name = m.group(2).decode("ascii")
            callers.setdefault(name, set()).add(ver)

    mismatches: list[str] = []
    for name, versions in sorted(callers.items()):
        path = _HTML_DIR / name
        if not path.exists():
            continue  # covered by test_every_referenced_template_exists
        first = path.read_text(errors="replace").lstrip().splitlines()
        if not first:
            mismatches.append(f"{name}: empty file")
            continue
        m = re.match(r"<!--\s*Version\s+(\d+)", first[0])
        if not m:
            # Caller version 0 means "skip the check"; only flag
            # if any caller actually passes a non-zero version.
            if any(v != 0 for v in versions):
                mismatches.append(
                    f"{name}: file has no version marker but callers "
                    f"request {sorted(versions)}"
                )
            continue
        file_ver = int(m.group(1))
        # 0 in the caller means "don't check" — ignore those.
        non_skip = {v for v in versions if v != 0}
        if non_skip and file_ver not in non_skip:
            mismatches.append(
                f"{name}: file is v{file_ver}, callers request "
                f"{sorted(non_skip)}"
            )

    assert not mismatches, "version-marker mismatches:\n  " + "\n  ".join(
        mismatches
    )


# ── HTML/samples/ artefact sweep ─────────────────────────────────


def test_samples_files_have_no_extraction_artefacts():
    """Same backslash-sequence audit as
    ``test_no_extraction_artefacts_in_templates`` (over
    ``HTML/*.txt``), extended to ``HTML/samples/``.

    The samples were copied verbatim from John Wiseman's
    NodePages.zip — they're not extracted from C source — so we
    don't expect artefacts, but the audit guards against a
    future "regenerate samples from C" change repeating the
    NodeTail.txt mistake.
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


# ── Phase-4 EXTRACTED_TEMPLATES inventory consistency ────────────


def test_extracted_templates_inventory_matches_html_dir():
    """The ``EXTRACTED_TEMPLATES`` table in
    ``test_template_extraction.py`` is an explicit inventory of
    every template the extraction work produced.  Every entry
    must correspond to a real file in HTML/, and there should be
    no significant gap in the other direction (every HTML/*.txt
    that came from extraction should appear in the inventory).

    Tracks "we deleted a template but forgot to update the
    inventory" and the inverse.
    """
    # Avoid a circular import of test_template_extraction by
    # parsing its inventory table directly.
    extr_test = _REPO_ROOT / "tests" / "playwright" / "test_template_extraction.py"
    text = extr_test.read_text()
    rows = re.findall(r'\("([^"]+\.(?:txt|js))",\s*\d+,\s*"[^"]+"\)', text)
    inventoried = set(rows)

    on_disk_txt = {p.name for p in _HTML_DIR.glob("*.txt")}
    on_disk_js = {p.name for p in _HTML_DIR.glob("*.js")}
    on_disk = on_disk_txt | on_disk_js

    missing_on_disk = sorted(inventoried - on_disk)
    assert not missing_on_disk, (
        f"EXTRACTED_TEMPLATES lists files that don't exist in HTML/: "
        f"{missing_on_disk}"
    )

    # We don't fail on extras-on-disk because someone might add a
    # template to HTML/ without going through extraction.  But
    # surface a soft warning via the test name being explicit.
    extras = sorted(on_disk - inventoried)
    # The samples-bundled assets aren't extraction artefacts; ignore.
    expected_extras = {"webscript.js"}  # placeholder, none currently
    surprising = [e for e in extras if e not in expected_extras]
    # Convert to a count check: anything < 5 surprising is fine
    # (one-off samples / new files).  This is a soft gate.
    assert len(surprising) < 5, (
        f"unexpectedly many HTML/ files not in EXTRACTED_TEMPLATES "
        f"(threshold 5): {surprising}.  Consider adding them to "
        f"the inventory."
    )


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
