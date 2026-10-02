"""The three files and the report: modes, refusals, and what the report may say."""
import os
import stat
import sys

import pytest

from sfic_solver.scanning import assemble as asm
from sfic_solver.scanning import output
from sfic_solver.scanning.pipeline import Scan


def chart(status, source=1, page=1, number=1, flags=(), text=None):
    return asm.Chart(source, page, number, status, text or f"CHART {status} {page}.{number}",
                     list(flags))


def test_the_base_path_is_next_to_the_input_or_where_told(tmp_path):
    scan = tmp_path / "scans.pdf"
    scan.write_bytes(b"x")
    folder = tmp_path / "folder"
    folder.mkdir()
    assert output.base_path(scan) == tmp_path / "scans"
    assert output.base_path(folder) == tmp_path / "folder"
    assert output.base_path(scan, tmp_path / "elsewhere.txt") == tmp_path / "elsewhere"
    assert output.base_path(scan, tmp_path / "elsewhere") == tmp_path / "elsewhere"


def test_each_file_is_written_only_if_it_has_charts(tmp_path):
    base = tmp_path / "out"
    found = [chart(asm.ACCEPTED), chart(asm.ACCEPTED, number=2), chart(asm.REVIEW, page=2)]
    written = output.write_outputs(base, found)
    assert [(s, n, p.name) for s, n, p in written] == [
        (asm.ACCEPTED, 2, "out.txt"), (asm.REVIEW, 1, "out.review.txt")]
    assert not (tmp_path / "out.failed.txt").exists()
    assert (tmp_path / "out.txt").read_text().count(asm.SEPARATOR) == 1


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_files_are_readable_by_their_owner_alone(tmp_path):
    output.write_outputs(tmp_path / "out", [chart(asm.ACCEPTED), chart(asm.FAILED)])
    for name in ("out.txt", "out.failed.txt"):
        assert stat.S_IMODE((tmp_path / name).stat().st_mode) == 0o600


def test_an_existing_file_is_never_overwritten_and_nothing_is_half_written(tmp_path):
    (tmp_path / "out.review.txt").write_text("keep me")
    with pytest.raises(output.OutputExists):
        output.write_outputs(tmp_path / "out", [chart(asm.ACCEPTED), chart(asm.REVIEW)])
    assert (tmp_path / "out.review.txt").read_text() == "keep me"
    assert not (tmp_path / "out.txt").exists()          # the accepted file was not written


def test_force_replaces_a_file_and_makes_it_private(tmp_path):
    existing = tmp_path / "out.txt"
    existing.write_text("old")
    os.chmod(existing, 0o644)
    output.write_outputs(tmp_path / "out", [chart(asm.ACCEPTED)], force=True)
    assert "CHART" in existing.read_text()
    if sys.platform != "win32":
        assert stat.S_IMODE(existing.stat().st_mode) == 0o600


def test_files_left_by_an_earlier_run_are_reported_as_stale(tmp_path):
    (tmp_path / "out.review.txt").write_text("old")
    written = output.write_outputs(tmp_path / "out", [chart(asm.ACCEPTED)])
    assert output.stale_files(tmp_path / "out", written) == [tmp_path / "out.review.txt"]


def make_scan(pages, found, small=0):
    return Scan(pages, found, small, 10)


def test_the_report_names_positions_and_a_clean_run_is_ok():
    pages = [asm.PageRecord(1, 1), asm.PageRecord(1, 2)]
    lines, ok = output.report(make_scan(pages, [chart(asm.ACCEPTED), chart(asm.ACCEPTED, page=2)]),
                              "tesseract 5.3.4")
    assert ok and lines[0] == "Tesseract: tesseract 5.3.4"
    assert "input 1, page 2, chart 1: accepted" in lines
    assert lines[-1] == "OK" and "2 chart(s) accepted" in lines[-2]


def test_flagged_charts_are_listed_with_their_flags_and_the_run_needs_attention():
    pages = [asm.PageRecord(1, 1), asm.PageRecord(2, 1)]
    found = [chart(asm.FAILED, flags=["chamber 3: the pins do not add up to the stack total"]),
             chart(asm.REVIEW, source=2, flags=["row 2 (Control) chamber 4: no usable reading"])]
    lines, ok = output.report(make_scan(pages, found))
    assert not ok and lines[-1].startswith("NEEDS ATTENTION")
    assert "input 1, page 1, chart 1: failed a check" in lines
    assert "    chamber 3: the pins do not add up to the stack total" in lines
    assert "input 2, page 1, chart 1: needs review" in lines


def test_blank_pages_small_text_missing_charts_ignored_lines_and_margins_are_reported():
    pages = [asm.PageRecord(1, 1, blank=True), asm.PageRecord(1, 2, too_small=True),
             asm.PageRecord(1, 3), asm.PageRecord(1, 4, ignored=[1, 14], outside=3),
             asm.PageRecord(1, 5, failed="could not be read (ValueError)")]
    lines, ok = output.report(make_scan(pages, [chart(asm.ACCEPTED, page=4)], small=5))
    text = "\n".join(lines)
    assert "input 1, page 1: blank page, skipped" in text
    assert "input 1, page 2: the text is too small" in text
    assert "input 1, page 3: no chart found" in text
    assert "input 1, page 4: lines not part of a chart, not read: 1, 14" in text
    assert "input 1, page 4: 3 mark(s) outside the printed block, not read" in text
    assert "input 1, page 5: could not be read (ValueError)" in text
    assert "5 mark(s) in shape groups too small to vote" in text
    assert not ok


def test_a_run_that_found_nothing_is_not_ok():
    lines, ok = output.report(make_scan([asm.PageRecord(1, 1, blank=True)], []))
    assert not ok and "0 chart(s) accepted" in "\n".join(lines)


def test_a_flagged_chart_says_which_lines_of_the_page_it_covers():
    flagged = chart(asm.REVIEW, flags=["the System header line is missing"])
    flagged.first_line, flagged.last_line = 1, 3
    lines, ok = output.report(make_scan([asm.PageRecord(1, 1)], [flagged]))
    assert "    (lines 1 to 3 of the page)" in lines and not ok
    # an accepted chart needs no position, and a chart with no span says nothing of one
    assert not any("lines" in l for l in output.chart_lines(chart(asm.ACCEPTED)))
    assert not any("of the page)" in l for l in output.chart_lines(chart(asm.REVIEW)))
