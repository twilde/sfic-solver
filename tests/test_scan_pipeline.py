"""The whole pipeline on rendered pages: scan, assemble, report (needs Tesseract).

One run is made for the module and every test looks at it, since reading ten pages
takes a while. The property that matters is the last one: nothing accepted differs
from the chart that was drawn.
"""
import random

import pytest

pytest.importorskip("PIL")
pytest.importorskip("numpy")

from PIL import Image  # noqa: E402

from scan_helpers import (add_strokes, have_tesseract, need_fonts, random_chart,  # noqa: E402
                          render, row_line)
from sfic_solver import charts, check_charts  # noqa: E402
from sfic_solver.scanning import assemble as asm  # noqa: E402
from sfic_solver.scanning import clean, layout, ocr, output, pipeline  # noqa: E402
from sfic_solver.scanning.pages import Page  # noqa: E402

pytestmark = [need_fonts(),
              pytest.mark.skipif(not have_tesseract(), reason="Tesseract is not installed")]

TITLE = "NOT A REAL SYSTEM 4B"


def erase_cell(image, line_index, cell_index):
    found = layout.analyse(clean.prepare(image))
    line = found.lines[line_index]
    token = line.tokens[1 + cell_index]
    from PIL import ImageDraw
    ImageDraw.Draw(image).rectangle((token.x0 - 3, line.y0 - 3, token.x1 + 3, line.y1 + 3),
                                    fill=255)
    return image


@pytest.fixture(scope="module")
def run():
    pages, truths = [], {}

    def add(image, truth=None):
        pages.append(Page(1, len(pages) + 1, image))
        truths[len(pages)] = truth

    for seed in range(1, 6):                                         # pages 1-5: clean
        lines, truth = random_chart(random.Random(seed))
        add(render(lines, seed=seed), truth)
    lines, truth = random_chart(random.Random(6))                    # page 6: a cell erased
    add(erase_cell(render(lines), 4 + 1, 2), truth)
    lines, truth = random_chart(random.Random(7))                    # page 7: a digit changed
    last = truth["rows"][-1]
    wrong = "4" if last[1][2] != "4" else "5"
    lines[-1] = row_line(last[0], last[1][:2] + [wrong] + last[1][3:])
    add(render(lines), truth)
    add(Image.new("L", (850, 1100), 255))                            # page 8: blank
    add(render([TITLE, "", "a page of words", "and nothing else"]))   # page 9: no chart
    lines, truth = random_chart(random.Random(8))                    # page 10: title, notes
    image = render([TITLE, ""] + lines)
    add(add_strokes(image, [(60, 330, 200, 700)]), truth)

    recogniser = ocr.Recogniser(jobs=4)
    try:
        result = pipeline.scan(pages, recogniser)
    finally:
        recogniser.close()
    return result, truths


def chart_on(result, page):
    found = [c for c in result.charts if c.page == page]
    assert len(found) == 1, f"page {page}: {len(found)} charts"
    return found[0]


def rows_of(chart):
    [parsed] = charts.parse_charts(chart.text)
    return [(label, [None if c is None else str(c) for c in cells])
            for label, cells in parsed.rows]


def truth_rows(truth):
    return [(label.lower(), [None if c == "--" else c for c in cells])
            for label, cells in truth["rows"]]


def test_clean_pages_are_accepted_and_come_out_as_drawn(run):
    result, truths = run
    for page in (1, 2, 3, 4, 5, 10):
        chart = chart_on(result, page)
        assert chart.status == asm.ACCEPTED, (page, chart.flags)
        assert rows_of(chart) == truth_rows(truths[page])
        [parsed] = charts.parse_charts(chart.text)
        assert parsed.control == truths[page]["control"]
        assert check_charts.check_chart(parsed) == []


def test_an_erased_cell_sends_the_chart_to_review_by_position(run):
    chart = chart_on(run[0], 6)
    assert chart.status == asm.REVIEW
    assert any("row 2 (Control) does not have one cell per chamber" in f for f in chart.flags)
    assert asm.UNREADABLE in chart.text


def test_a_changed_digit_is_failed_because_its_column_does_not_add_up(run):
    chart = chart_on(run[0], 7)
    assert chart.status == asm.FAILED
    assert any("chamber 3" in f and "stack total" in f for f in chart.flags)
    charts.parse_charts(chart.text)                    # the failed file is readable


def test_a_blank_page_is_skipped_and_a_page_without_a_chart_is_reported(run):
    result, _ = run
    assert result.pages[7].blank
    assert not result.pages[8].blank and not [c for c in result.charts if c.page == 9]
    assert result.pages[8].ignored == [1, 2, 3]        # the title and the two lines of words


def test_a_title_is_ignored_and_margin_notes_are_not_read(run):
    record = run[0].pages[9]
    assert record.ignored == [1]
    assert record.outside >= 1


def test_nothing_accepted_ever_differs_from_the_chart_that_was_drawn(run):
    result, truths = run
    accepted = [c for c in result.charts if c.status == asm.ACCEPTED]
    assert len(accepted) >= 6
    for chart in accepted:
        assert truths[chart.page] is not None
        assert rows_of(chart) == truth_rows(truths[chart.page])


def test_the_report_quotes_no_digit_from_any_page(run):
    result, truths = run
    lines, ok = output.report(result)
    text = "\n".join(lines)
    assert not ok
    for truth in filter(None, truths.values()):
        assert truth["control"] not in text and truth["master"] not in text
        assert not any(key in text for key in truth["change"])
    assert TITLE not in text
