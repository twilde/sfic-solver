"""Feature design documents follow the convention in D24 of docs/design.md."""
import re

import pytest

from conftest import ROOT

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
    log = (ROOT / "docs" / "design.md").read_text()
    assert f"(designs/{path.name})" in log


def example_charts():
    """The charts in the core pinning document: (header keys, control, rows by label)."""
    text = (ROOT / "docs" / "designs" / "core-pinning.md").read_text()
    block = re.search(r"```\n(System = .*?)```", text, re.S).group(1)
    charts = []
    for chart in re.split(r"\n-{10,}\n", block):
        header, _, body = chart.strip().partition("\n\n")
        fields = dict(re.findall(r"^(.+?) = (.+)$", header, re.M))
        control = fields["Control Key"]
        reserved = {"System", "Key System", "Core", "Control Key"}
        keys = [v for k, v in fields.items() if k not in reserved]
        rows = []
        for line in body.strip().splitlines():
            label, *cells = line.split()
            rows.append((label, [None if c == "--" else int(c) for c in cells]))
        charts.append((fields, keys, control, rows))
    return charts


def test_core_pinning_document_has_two_example_charts():
    assert [c[0]["Core"] for c in example_charts()] == ["Area A cores", "Standalone cores"]
    assert all(c[0]["System"] == "A2" for c in example_charts())


def test_core_pinning_example_charts_are_the_pins_for_their_keys():
    """Recompute every chamber from the header's keys: the chart must say the same."""
    for fields, keys, control, rows in example_charts():
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
            assert filled == expected[::-1], f"{fields['Core']}, chamber {chamber + 1}"
            assert sum(filled) == 23
            masters = column[2:-1]       # top to bottom: empties must come first
            assert masters == sorted(masters, key=lambda c: c is not None)
