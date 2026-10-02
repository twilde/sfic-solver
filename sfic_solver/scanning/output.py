"""The three files and the report (D38).

The files hold key data, so they are created readable by their owner alone (mode
0600) and never over an existing file unless `--force` says so; every target is
checked before any is written, so a refusal leaves nothing half done. The report
names positions (input, page, chart, row, chamber) and kinds of problem, never a
digit read from a page or a file name, so that it is safe to quote in an issue.
"""
import os
from pathlib import Path

from . import assemble

SUFFIXES = {assemble.ACCEPTED: ".txt", assemble.FAILED: ".failed.txt",
            assemble.REVIEW: ".review.txt"}


class OutputExists(Exception):
    """A file that would be written already exists (and --force was not given)."""


def base_path(first_input, output=None):
    """The path the output files are named from: `output` (a trailing .txt is dropped)
    if given, else next to the first input, named after it."""
    if output:
        path = Path(output)
        return path.with_suffix("") if path.suffix.lower() == ".txt" else path
    path = Path(first_input)
    return path.with_suffix("") if path.is_file() else path.parent / path.name


def target(base, status):
    return Path(str(base) + SUFFIXES[status])


def write_private(path, text, force=False):
    """Write `text` to `path` readable by its owner only; refuse to replace a file
    unless `force`."""
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if force else os.O_EXCL)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        raise OutputExists(path) from None
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        if hasattr(os, "fchmod"):
            os.fchmod(handle.fileno(), 0o600)           # also when --force reuses a file
        handle.write(text)


def write_outputs(base, found, force=False):
    """Write the accepted, failed and review files for the charts in `found`, each
    only if it has charts. Returns [(status, count, Path)] for what was written.
    Raises OutputExists, before writing anything, if a target is in the way."""
    plan = []
    for status in (assemble.ACCEPTED, assemble.FAILED, assemble.REVIEW):
        texts = [c.text for c in found if c.status == status]
        if texts:
            plan.append((status, len(texts), target(base, status), assemble.join_charts(texts)))
    if not force:
        for _, _, path, _ in plan:
            if path.exists():
                raise OutputExists(path)
    written = []
    for status, count, path, text in plan:
        write_private(path, text, force)
        written.append((status, count, path))
    return written


def stale_files(base, written):
    """Files from an earlier run that are still there and were not written now."""
    wrote = {path for _, _, path in written}
    return [target(base, s) for s in SUFFIXES
            if target(base, s).exists() and target(base, s) not in wrote]


def chart_lines(chart):
    where = f"input {chart.source}, page {chart.page}, chart {chart.number}"
    if chart.status == assemble.ACCEPTED:
        return [f"{where}: accepted"]
    head = "failed a check" if chart.status == assemble.FAILED else "needs review"
    span = [f"    (lines {chart.first_line} to {chart.last_line} of the page)"] \
        if chart.first_line else []
    return [f"{where}: {head}"] + span + [f"    {flag}" for flag in chart.flags]


def report(scan, version=""):
    """The report as a list of lines, and whether everything was accepted."""
    lines = []
    if version:
        lines.append(f"Tesseract: {version}")
    clean_run = True
    by_page = {}
    for chart in scan.charts:
        by_page.setdefault((chart.source, chart.page), []).append(chart)
    blank = 0
    for page in scan.pages:
        where = f"input {page.source}, page {page.number}"
        if page.failed:
            lines.append(f"{where}: {page.failed}")
            clean_run = False
            continue
        if page.blank:
            blank += 1
            lines.append(f"{where}: blank page, skipped")
            continue
        if page.too_small:
            lines.append(f"{where}: the text is too small to read reliably "
                         "(scan at 300 dpi or more)")
            clean_run = False
            continue
        found = by_page.get((page.source, page.number), [])
        if not found:
            lines.append(f"{where}: no chart found")
            clean_run = False
        for chart in found:
            lines.extend(chart_lines(chart))
            clean_run = clean_run and chart.status == assemble.ACCEPTED
        if page.ignored:
            lines.append(f"{where}: lines not part of a chart, not read: "
                         + ", ".join(str(n) for n in page.ignored))
        if page.outside:
            lines.append(f"{where}: {page.outside} mark(s) outside the printed block, not read")
    counts = {s: sum(1 for c in scan.charts if c.status == s)
              for s in (assemble.ACCEPTED, assemble.FAILED, assemble.REVIEW)}
    lines.append("")
    summary = (f"Read {len(scan.pages)} page(s): {counts[assemble.ACCEPTED]} chart(s) accepted, "
               f"{counts[assemble.FAILED]} failed a check, {counts[assemble.REVIEW]} need review")
    if blank:
        summary += f"; {blank} blank page(s) skipped"
    if scan.small_marks:
        summary += (f"; {scan.small_marks} mark(s) in shape groups too small to vote "
                    "(more pages give the groups more to go on)")
    lines.append(summary + ".")
    if not scan.charts:
        clean_run = False
    lines.append("OK" if clean_run else "NEEDS ATTENTION: see the lines above")
    return lines, clean_run
