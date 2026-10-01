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
