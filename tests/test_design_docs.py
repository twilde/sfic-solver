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


def test_core_pinning_example_chart_is_valid_a2_pinning():
    """The chart in the design document must add up, like the README's example."""
    text = (ROOT / "docs" / "designs" / "core-pinning.md").read_text()
    chart = re.search(r"```\n(System = .*?)```", text, re.S).group(1)
    header, _, body = chart.partition("\n\n")
    control = re.search(r"^Control Key = (\d+)$", header, re.M).group(1)
    rows = {}
    for line in body.strip().splitlines():
        label, *cells = line.split()
        rows.setdefault(label, []).append([None if c == "--" else int(c) for c in cells])
    assert len(rows["T/D"]) == len(rows["Control"]) == len(rows["Bottom"]) == 1
    for chamber, cut in enumerate(control):
        bottom = rows["Bottom"][0][chamber]
        others = [row[chamber] for label, layer in rows.items() if label != "Bottom"
                  for row in layer if row[chamber] is not None]
        assert 0 <= bottom <= 9
        assert all(2 <= pin <= 19 for pin in others), f"chamber {chamber + 1}"
        assert bottom + sum(others) == 23, f"chamber {chamber + 1}"
        assert 23 - rows["T/D"][0][chamber] == int(cut) + 10, f"chamber {chamber + 1}: control line"
