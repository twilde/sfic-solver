"""The design documents follow the conventions in D24 and D41 of docs/decisions.md."""
import re

import pytest

from conftest import ROOT
from helpers import example_charts, parse_rows

DESIGNS = sorted((ROOT / "docs" / "designs").glob("*.md"))
STATUSES = {"Draft", "Accepted", "Implemented", "Superseded"}


def test_feature_design_documents_are_found():
    assert "core-pinning.md" in {p.name for p in DESIGNS}


@pytest.mark.parametrize("path", DESIGNS, ids=lambda p: p.name)
def test_design_document_has_a_title_and_a_status(path):
    lines = path.read_text().splitlines()
    assert lines[0].startswith("# "), "the first line must be the title"
    status = re.fullmatch(r"Status: (\w+)", lines[2])
    assert status, "the third line must read 'Status: <status>'"
    assert status.group(1) in STATUSES


@pytest.mark.parametrize("path", DESIGNS, ids=lambda p: p.name)
def test_design_document_is_indexed_in_the_log(path):
    log = (ROOT / "docs" / "decisions.md").read_text()
    assert f"(designs/{path.name})" in log


def test_core_pinning_document_has_example_charts():
    charts = example_charts()
    assert [c[0]["Core"] for c in charts] == [
        "Area A cores", "Unit cores (unit:101)", "Standalone cores"]
    assert all(c[0]["System"] == "A2" for c in charts)
    assert all(re.fullmatch(r"\d{4}-\d\d-\d\d", c[0]["Date"]) for c in charts)


def test_core_pinning_unit_charts_name_their_unit_in_the_core_line():
    unit_charts = [c for c in example_charts() if any(k.startswith("unit:") for k in c[0])]
    assert unit_charts
    for fields, *_ in unit_charts:
        unit = next(k for k in fields if k.startswith("unit:"))
        assert f"({unit})" in fields["Core"]


def assert_chart_is_the_pins_for_its_keys(where, keys, control, rows):
    """Recompute every chamber from the header's keys: the chart must say the same."""
    labels = [label for label, _ in rows]
    assert labels[:2] == ["T/D", "Control"] and labels[-1] == "Bottom"
    assert set(labels[2:-1]) <= {"Master"}
    for chamber in range(len(control)):
        heights = sorted({int(k[chamber]) for k in keys})
        line = int(control[chamber]) + 10
        expected = [heights[0]] + [b - a for a, b in zip(heights, heights[1:])]
        expected += [line - heights[-1], 23 - line]
        column = [cells[chamber] for _, cells in rows]
        filled = [c for c in column if c is not None]
        assert filled == expected[::-1], f"{where}, chamber {chamber + 1}"
        assert sum(filled) == 23
        masters = column[2:-1]       # top to bottom: empties must come first
        assert masters == sorted(masters, key=lambda c: c is not None)


def test_core_pinning_example_charts_are_the_pins_for_their_keys():
    for fields, keys, control, rows in example_charts():
        assert_chart_is_the_pins_for_its_keys(fields["Core"], keys, control, rows)


def test_core_pinning_legacy_example_chart_is_the_pins_for_its_keys():
    """The legacy header of older keying software: one master line and one comma-separated change keys line."""
    text = (ROOT / "docs" / "designs" / "core-pinning.md").read_text()
    chart = re.search(r"```\n(System = A2\nControl Key = .*?)```", text, re.S).group(1)
    header, _, body = chart.strip().partition("\n\n")
    fields = dict(re.findall(r"^(.+?) = (.+)$", header, re.M))
    assert list(fields) == ["System", "Control Key", "Master Key", "Change Keys"]
    keys = [fields["Master Key"], *re.split(r"[,\s]+", fields["Change Keys"])]
    assert len(keys) == 3
    assert_chart_is_the_pins_for_its_keys("legacy", keys, fields["Control Key"], parse_rows(body))


# The decision log is short and append-only; docs/design.md describes the present (D41).

LOG = ROOT / "docs" / "decisions.md"
DESIGN = ROOT / "docs" / "design.md"
MAX_ENTRY_WORDS = 150


def log_entries():
    """(number, heading, body lines) for each '## Dn.' entry of the log, in order."""
    entries = []
    for line in LOG.read_text().splitlines():
        heading = re.fullmatch(r"## D(\d+)\. (.+)", line)
        if heading:
            entries.append((int(heading.group(1)), heading.group(2), []))
        elif entries:
            entries[-1][2].append(line)
    return entries


def github_anchors(path):
    """The anchors GitHub makes for the headings of a Markdown file."""
    anchors = set()
    for line in path.read_text().splitlines():
        heading = re.fullmatch(r"#{1,6} (.+)", line)
        if heading:
            slug = re.sub(r"[^\w\- ]", "", heading.group(1).lower()).replace(" ", "-")
            anchors.add(slug)
    return anchors


def test_log_entries_are_numbered_in_order_without_gaps():
    numbers = [n for n, _, _ in log_entries()]
    assert numbers == list(range(1, len(numbers) + 1))


@pytest.mark.parametrize("entry", log_entries(), ids=lambda e: f"D{e[0]}")
def test_log_entry_is_succinct(entry):
    number, _, body = entry
    prose = [l for l in body if not l.startswith("Detail:") and not l.startswith("    ")]
    words = len(" ".join(prose).split())
    assert words <= MAX_ENTRY_WORDS, (
        f"D{number} has {words} words; move the reasoning into docs/design.md "
        f"and keep the entry to {MAX_ENTRY_WORDS}")


@pytest.mark.parametrize("entry", log_entries(), ids=lambda e: f"D{e[0]}")
def test_log_entry_points_at_the_reasoning_or_says_it_is_superseded(entry):
    number, _, body = entry
    text = "\n".join(body)
    if re.search(r"^Status: Superseded by ", text, re.M):
        return
    assert "Detail: [" in text, f"D{number} needs a Detail: line linking to design.md"


def test_log_links_resolve():
    for target in re.findall(r"\]\(([^)]+)\)", LOG.read_text()):
        path, _, anchor = target.partition("#")
        if path.startswith("http"):
            continue
        assert (LOG.parent / path).exists(), f"{target} does not exist"
        if anchor:
            assert anchor in github_anchors(LOG.parent / path), f"{target} has no such heading"


def test_status_lines_point_at_later_entries():
    numbers = {n for n, _, _ in log_entries()}
    for number, _, body in log_entries():
        for line in body:
            if line.startswith("Status:"):
                assert re.fullmatch(r"Status: (Superseded|Amended) by D\d+[^.]*\.", line), line
                for cited in map(int, re.findall(r"D(\d+)", line)):
                    assert cited in numbers and cited > number, f"D{number}: {line}"


def test_design_document_cites_only_logged_decisions():
    numbers = {n for n, _, _ in log_entries()}
    cited = {int(n) for n in re.findall(r"\bD(\d+)\b", DESIGN.read_text())}
    assert cited <= numbers
