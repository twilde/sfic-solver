"""Charts from recorded lines: structure, checks, and the three places a chart can go.

No images and no Tesseract here: records are built from fake charts, so every outcome
can be produced to order, and the text written is read back with the real reader.
"""
import random

import pytest

from scan_helpers import random_chart
from sfic_solver import charts, check_charts
from sfic_solver.scanning import assemble as asm
from sfic_solver.scanning import groups


class Builder:
    """Records and resolved marks for a fake chart, with controlled damage."""

    def __init__(self):
        self.marks = []

    def digits(self, text, unreadable=()):
        ids = []
        for position, char in enumerate(text):
            value = None if position in unreadable else char
            self.marks.append(groups.Mark(value, groups.IMPURE if value is None else None, 0))
            ids.append(len(self.marks) - 1)
        return ids

    def cell(self, text, unreadable=()):
        if text == "--":
            return asm.Cell(True)
        return asm.Cell(False, self.digits(text, unreadable))

    def records(self, truth, system="A2", drop=(), swap=None, unreadable=None,
                cells_changed=None, extra_cell=None, start=1):
        unreadable = unreadable or {}
        out = []
        number = start - 1

        def line(kind, **kw):
            nonlocal number
            number += 1
            return asm.LineRecord(number, kind, **kw)

        header = [(charts.SYSTEM, {"system": system}),
                  (charts.CONTROL_KEY, {"bittings": [self.digits(
                      truth["control"], unreadable.get("control", ()))]}),
                  (charts.MASTER_KEY, {"bittings": [self.digits(truth["master"])]}),
                  (charts.CHANGE_KEYS, {"bittings": [self.digits(c) for c in truth["change"]]})]
        for kind, kw in header:
            if kind not in drop:
                out.append(line(kind, **kw))
        rows = [(label, list(cells)) for label, cells in truth["rows"]]
        for (r, c), value in (cells_changed or {}).items():
            rows[r][1][c] = value
        for r, (label, cells) in enumerate(rows):
            built = [self.cell(text, unreadable.get((r, c), ()))
                     for c, text in enumerate(cells)]
            if extra_cell == r:
                built.append(self.cell("5"))
            out.append(line(label, cells=built))
        return out

    def page(self, records, ignored=()):
        return asm.PageRecord(1, 1, records, ignored=list(ignored))

    def run(self, truth, **kw):
        records = self.records(truth, **kw)
        return asm.assemble(self.page(records), asm.Resolved(self.marks))


@pytest.fixture
def truth():
    return random_chart(random.Random(21))[1]


def only(charts_found):
    assert len(charts_found) == 1
    return charts_found[0]


def test_a_chart_read_perfectly_is_accepted_and_check_charts_reads_it_back(truth):
    chart = only(Builder().run(truth))
    assert chart.status == asm.ACCEPTED and chart.flags == []
    [parsed] = charts.parse_charts(chart.text)
    assert parsed.layout == "legacy" and parsed.system == "A2"
    assert parsed.control == truth["control"]
    assert [(label.title() if label != "t/d" else "T/D", [None if c == "--" else str(c) for c in cells])
            for label, cells in parsed.rows] == [(l, c) for l, c in truth["rows"]]
    assert check_charts.check_chart(parsed) == []         # it is the pinner's chart too


def test_a_column_that_does_not_add_up_is_failed_but_still_readable(truth):
    bottom = len(truth["rows"]) - 1
    other = "4" if truth["rows"][bottom][1][2] != "4" else "5"
    chart = only(Builder().run(truth, cells_changed={(bottom, 2): other}))
    assert chart.status == asm.FAILED
    assert any("chamber 3" in f and "stack total" in f for f in chart.flags)
    charts.parse_charts(chart.text)                       # check_charts can read it


def test_a_cell_out_of_range_is_failed(truth):
    chart = only(Builder().run(truth, cells_changed={(len(truth["rows"]) - 1, 0): "12"}))
    assert chart.status == asm.FAILED
    assert any("outside the range" in f for f in chart.flags)


def test_a_dash_outside_the_master_rows_is_failed(truth):
    chart = only(Builder().run(truth, cells_changed={(0, 1): "--"}))
    assert chart.status == asm.FAILED
    assert any("only Master rows may be empty" in f for f in chart.flags)


def test_master_rows_that_do_not_fill_from_the_bottom_are_failed():
    # Two master rows; chamber 1 has a pin in the upper row and a dash below it.
    ascending = "".join(str(n) for n in range(1, 8))      # an invented bitting
    truth = {"system": "A2", "control": ascending, "master": ascending, "change": [ascending],
             "rows": [("T/D", ["4"] * 7), ("Control", ["8"] * 7),
                      ("Master", ["2"] + ["--"] * 6), ("Master", ["--"] + ["2"] * 6),
                      ("Bottom", ["1"] * 7)]}
    chart = only(Builder().run(truth))
    assert chart.status == asm.FAILED
    assert any("chamber 1" in f and "fill from the bottom" in f for f in chart.flags)


def test_an_unreadable_cell_goes_to_review_with_question_marks_and_is_refused(truth):
    chart = only(Builder().run(truth, unreadable={(1, 3): (0,)}))
    assert chart.status == asm.REVIEW
    assert asm.UNREADABLE in chart.text
    assert any("row 2 (Control) chamber 4" in f for f in chart.flags)
    with pytest.raises(charts.ChartError):
        charts.parse_charts(chart.text)                   # a ?? chart is never checked


def test_an_unreadable_header_digit_goes_to_review_with_its_position(truth):
    chart = only(Builder().run(truth, unreadable={"control": (2,)}))
    assert chart.status == asm.REVIEW
    assert any("Control Key digit 3" in f for f in chart.flags)
    assert f"Control Key = {truth['control'][:2]}?{truth['control'][3:]}" in chart.text


def test_a_row_with_the_wrong_number_of_cells_goes_to_review(truth):
    chart = only(Builder().run(truth, extra_cell=1))
    assert chart.status == asm.REVIEW
    assert any("row 2 (Control) does not have one cell per chamber" in f for f in chart.flags)


def test_an_unknown_pinning_system_goes_to_review(truth):
    chart = only(Builder().run(truth, system="ZZ"))
    assert chart.status == asm.REVIEW
    assert any("pinning system" in f for f in chart.flags)
    assert "System = ??" in chart.text


@pytest.mark.parametrize("missing", [charts.MASTER_KEY, charts.CHANGE_KEYS])
def test_a_missing_header_line_goes_to_review(truth, missing):
    chart = only(Builder().run(truth, drop=(missing,)))
    assert chart.status == asm.REVIEW
    assert any(f"{missing.title()} header line is missing" in f for f in chart.flags)


def test_rows_out_of_order_go_to_review(truth):
    swapped = dict(truth, rows=[truth["rows"][1], truth["rows"][0]] + truth["rows"][2:])
    chart = only(Builder().run(swapped))
    assert chart.status == asm.REVIEW
    assert any("rows are not T/D, Control" in f for f in chart.flags)


def test_a_key_of_the_wrong_length_goes_to_review(truth):
    short = dict(truth, master=truth["master"][:-1])
    chart = only(Builder().run(short))
    assert chart.status == asm.REVIEW
    assert any("different length" in f for f in chart.flags)


def test_two_charts_on_a_page_are_numbered():
    builder = Builder()
    first = random_chart(random.Random(1))[1]
    second = random_chart(random.Random(2))[1]
    records = builder.records(first) + builder.records(second, start=20)
    assert len(asm.split_charts(records)) == 2
    found = asm.assemble(builder.page(records), asm.Resolved(builder.marks))
    assert [c.number for c in found] == [1, 2] and [c.status for c in found] == [asm.ACCEPTED] * 2


def test_lines_before_the_first_system_line_are_a_chart_to_review_not_nothing():
    # The reviewer's reproduction: a chart whose System line was not recognised, so its
    # other lines come first, followed by a System line of an invented unknown system.
    records = [asm.LineRecord(1, charts.CONTROL_KEY), asm.LineRecord(2, charts.MASTER_KEY),
               asm.LineRecord(3, "T/D"),
               asm.LineRecord(4, charts.SYSTEM, system="NOT A REAL SYSTEM 4B")]
    found = asm.assemble(asm.PageRecord(1, 1, records), asm.Resolved([]))
    assert len(found) == 2
    orphans = found[0]
    assert orphans.status == asm.REVIEW
    assert any("System header line is missing" in f for f in orphans.flags)
    assert (orphans.first_line, orphans.last_line) == (1, 3)
    assert found[1].status == asm.REVIEW


def test_a_page_whose_first_system_line_was_ignored_cannot_come_out_clean():
    # Two good charts, but the first one's System line was misread and is ignored.
    builder = Builder()
    first = random_chart(random.Random(31))[1]
    second = random_chart(random.Random(32))[1]
    one = builder.records(first, start=1)
    two = builder.records(second, start=20)
    records = one[1:] + two                      # the first System line is not there
    found = asm.assemble(builder.page(records, ignored=[1]), asm.Resolved(builder.marks))
    assert [c.status for c in found] == [asm.REVIEW, asm.ACCEPTED]
    assert any("System header line is missing" in f for f in found[0].flags)


def test_a_missed_system_line_between_charts_flags_the_chart_that_swallows_the_next():
    builder = Builder()
    first = random_chart(random.Random(33))[1]
    second = random_chart(random.Random(34))[1]
    records = builder.records(first) + builder.records(second, start=20)[1:]   # no System
    found = asm.assemble(builder.page(records, ignored=[20]), asm.Resolved(builder.marks))
    assert len(found) == 1 and found[0].status == asm.REVIEW


def test_a_line_that_was_not_recognised_inside_a_chart_sends_it_to_review(truth):
    builder = Builder()
    records = builder.records(truth)
    inside = records[6].number                     # a row of the chart
    found = asm.assemble(builder.page(records, ignored=[inside]), asm.Resolved(builder.marks))
    [chart] = found
    assert chart.status == asm.REVIEW
    assert any(f"line {inside}" in f and "inside this chart" in f for f in chart.flags)


def test_a_title_above_and_a_page_number_below_a_chart_do_not_spoil_it(truth):
    builder = Builder()
    records = builder.records(truth, start=3)       # lines 1 and 2: a title block
    below = records[-1].number + 1                  # and a page number after the last row
    found = asm.assemble(builder.page(records, ignored=[1, 2, below]),
                         asm.Resolved(builder.marks))
    assert [c.status for c in found] == [asm.ACCEPTED]


def test_flags_name_positions_and_never_a_value(truth):
    bad = Builder().run(truth, unreadable={(1, 3): (0,), "control": (2,)},
                        cells_changed={(len(truth["rows"]) - 1, 0): "12"})
    flags = [flag for chart in bad for flag in chart.flags]
    assert flags
    for flag in flags:
        assert truth["control"] not in flag and truth["master"] not in flag
        assert not any(key in flag for key in truth["change"])


def test_charts_are_joined_with_lines_of_dashes_and_read_back(truth):
    builder = Builder()
    other = random_chart(random.Random(22))[1]
    found = (asm.assemble(builder.page(builder.records(truth)), asm.Resolved(builder.marks))
             + asm.assemble(builder.page(builder.records(other)), asm.Resolved(builder.marks)))
    text = asm.join_charts([c.text for c in found])
    assert len(charts.parse_charts(text)) == 2
