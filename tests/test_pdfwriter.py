"""pdfwriter: a hand-written PDF that a reader of our own, and where installed pdfium and
poppler, take as one page to a chart, with exactly the chart's lines."""
import random

import pytest

from pdfread import read_pdf, unwrap
from sfic_solver import pdfwriter
from sfic_solver.pdfwriter import Page, PdfError, pages_to_pdf

CHART = ["Key System = Example building", "Core = Unit cores (unit:101)", "",
         "T/D      4  6  9", "Bottom   5  3  0"]
OTHER = ["Core = Back\\slash", "", "()", "(unbalanced", "Café £ ®"]


def test_a_page_for_each_chart_with_the_charts_lines_exactly():
    doc = read_pdf(pages_to_pdf([CHART, OTHER, CHART]))
    assert [page.lines for page in doc.pages] == [CHART, OTHER, CHART]
    assert [page.footer for page in doc.pages] == ["Page 1 of 3", "Page 2 of 3", "Page 3 of 3"]


def test_parentheses_backslashes_and_latin_one_survive_the_round_trip():
    page, = read_pdf(pages_to_pdf([OTHER])).pages
    assert page.lines == OTHER


@pytest.mark.parametrize("paper, media", [("letter", (612, 792)), ("a4", (595, 842))])
def test_the_paper_sets_the_page_size(paper, media):
    assert read_pdf(pages_to_pdf([CHART], paper)).pages[0].media == media


def test_the_structure_is_what_a_reader_needs():
    """read_pdf checks every offset, length, count and reference as it reads."""
    data = pages_to_pdf([CHART] * 5)
    assert len(read_pdf(data).pages) == 5
    broken = data.replace(b"/Count 5", b"/Count 4")
    with pytest.raises(AssertionError):
        read_pdf(broken)
    shifted = data.replace(b"1 0 obj", b"1  0 obj", 1)
    with pytest.raises(AssertionError):
        read_pdf(shifted)


def fits(lines, size, width, height):
    """Whether these lines, at this size, sit between the margins of a page."""
    margin = pdfwriter.MARGIN
    across = max(len(line) for line in lines) * pdfwriter.CHAR_WIDTH * size
    down = size * (1 + (len(lines) - 1) * pdfwriter.LEADING)
    return across <= width - 2 * margin and down <= height - 2 * margin


@pytest.mark.parametrize("paper", sorted(pdfwriter.PAPER))
def test_every_page_fits_between_the_margins_at_the_largest_size_that_does(paper):
    width, height = pdfwriter.PAPER[paper]
    pages = [CHART, [f"{n:2} " + "x" * 80 for n in range(60)], OTHER]
    doc = read_pdf(pages_to_pdf(pages, paper))
    size, = {page.size for page in doc.pages}          # one size for the whole document
    assert pdfwriter.MIN_SIZE <= size <= pdfwriter.MAX_SIZE and size % pdfwriter.STEP == 0
    margin = pdfwriter.MARGIN
    for lines, page in zip(pages, doc.pages):
        assert fits(lines, size, width, height)
        last = page.y - (len(lines) - 1) * page.leading
        assert page.x == margin and page.y <= height - margin and last >= margin - 1e-6
    assert size == pdfwriter.MAX_SIZE or not all(
        fits(lines, size + pdfwriter.STEP, width, height) for lines in pages)


def test_short_pages_are_set_at_the_largest_size_and_no_larger():
    page, = read_pdf(pages_to_pdf([CHART])).pages
    assert page.size == pdfwriter.MAX_SIZE == 12
    assert (page.drawing, page.drawing_size) == (0, None)


DRAWING = [f"{n:2} " + "|" * 82 for n in range(31)]          # 85 columns, like a real drawing


def drawn(chart=CHART, drawing=DRAWING):
    return Page(chart + [""], drawing)


def assert_drawn_page_fits(page, chart, drawing, width, height):
    """The chart, then the drawing under it, both inside the margins, the last line above
    the footer; the chart's lines at its leading and the drawing's at its own."""
    margin = pdfwriter.MARGIN
    assert page.lines == chart + [""] + drawing and page.drawing == len(drawing)
    assert max(map(len, chart)) * pdfwriter.CHAR_WIDTH * page.size <= width - 2 * margin
    assert max(map(len, drawing)) * pdfwriter.CHAR_WIDTH * page.drawing_size <= width - 2 * margin
    assert page.leading == pytest.approx(page.size * pdfwriter.LEADING, abs=0.01)
    assert page.drawing_leading == pytest.approx(page.drawing_size * pdfwriter.LEADING, abs=0.01)
    # The blank line that ends the chart is set at the chart's leading, then the drawing.
    last = page.y - (len(chart) + 1) * page.leading - (len(drawing) - 1) * page.drawing_leading
    assert page.y <= height - margin and last >= margin - 1e-6


@pytest.mark.parametrize("paper", sorted(pdfwriter.PAPER))
def test_a_chart_with_room_for_its_drawing_is_set_two_points_larger_than_before(paper):
    """The drawing is the wide part: 85 columns sets its size, as it did when one size
    served the page (9.5 points), and the chart above it is larger (it was 9.5 too)."""
    width, height = pdfwriter.PAPER[paper]
    page, = read_pdf(pages_to_pdf([drawn()], paper)).pages
    assert (page.size, page.drawing_size) == (12, 9.5)
    assert_drawn_page_fits(page, CHART, DRAWING, width, height)


@pytest.mark.parametrize("paper", sorted(pdfwriter.PAPER))
def test_a_tall_drawing_shrinks_before_the_chart_does(paper):
    width, height = pdfwriter.PAPER[paper]
    tall = [f"{n:2} " + "|" * 82 for n in range(60)]
    page, = read_pdf(pages_to_pdf([drawn(drawing=tall)], paper)).pages
    assert page.size == pdfwriter.MAX_SIZE
    assert pdfwriter.MIN_SIZE <= page.drawing_size < 9.5
    assert_drawn_page_fits(page, CHART, tall, width, height)
    # the largest size that fits: half a point more would not
    bigger = (page.drawing_size + pdfwriter.STEP) * pdfwriter.LEADING
    last = page.y - (len(CHART) + 1) * page.leading - (len(tall) - 1) * bigger
    assert last < pdfwriter.MARGIN


def test_the_chart_gives_way_only_when_the_drawing_is_already_as_small_as_allowed():
    page, = read_pdf(pages_to_pdf([drawn(drawing=["|" * 20] * 90)])).pages
    assert page.drawing_size == pdfwriter.MIN_SIZE and pdfwriter.MIN_SIZE < page.size < 12
    with pytest.raises(PdfError, match="page 1 would need a font smaller than 6 points"):
        pages_to_pdf([drawn(drawing=["|" * 20] * 200)])


def test_one_size_for_the_chart_and_one_for_the_drawing_serve_every_page():
    short, tall = drawn(), drawn(drawing=["|" * 80] * 55)
    doc = read_pdf(pages_to_pdf([short, tall, short]))
    assert len({page.size for page in doc.pages}) == 1
    assert len({page.drawing_size for page in doc.pages}) == 1
    assert doc.pages[0].drawing_size < 9.5                   # the tall one sets it for all


def test_a_drawing_too_wide_for_the_page_is_refused_without_quoting_it():
    with pytest.raises(PdfError, match="page 2 would need a font smaller than 6 points") as caught:
        pages_to_pdf([drawn(), drawn(drawing=["|" * 150])])
    assert "|" not in str(caught.value)


def test_the_drawing_is_never_larger_than_the_chart():
    page, = read_pdf(pages_to_pdf([drawn(["x" * 75] * 5, ["|" * 30] * 10)])).pages
    assert (page.size, page.drawing_size) == (11, 10)         # the drawing's own limit
    page, = read_pdf(pages_to_pdf([drawn(["x" * 100] * 5, ["|" * 30] * 10)])).pages
    assert (page.size, page.drawing_size) == (8, 8)           # the chart's size


def test_the_footer_is_centred_in_the_bottom_margin():
    width, _ = pdfwriter.PAPER["letter"]
    page, = read_pdf(pages_to_pdf([CHART])).pages
    footer_width = len(page.footer) * pdfwriter.CHAR_WIDTH * pdfwriter.FOOTER_SIZE
    assert page.footer_x + footer_width / 2 == pytest.approx(width / 2, abs=0.01)
    assert 0 < page.footer_y < pdfwriter.MARGIN


def test_equal_input_gives_equal_bytes_and_the_file_records_no_date_or_name():
    data = pages_to_pdf([CHART, OTHER])
    assert data == pages_to_pdf([CHART, OTHER])
    for forbidden in (b"CreationDate", b"ModDate", b"/Author", b"/Creator", b"D:20"):
        assert forbidden not in data
    doc = read_pdf(data)
    assert (doc.title, doc.producer) == ("Pinning charts", "sfic-solver")


@pytest.mark.parametrize("pages, message", [
    ([["Ω not in the font"]], "page 1 has a character the PDF's font cannot print"),
    ([CHART, ["a\tb"]], "page 2 has a control character"),
    ([CHART, ["x" * 300]], "page 2 would need a font smaller than 6 points"),
    ([["x"] * 200], "page 1 would need a font smaller than 6 points"),
    ([], "there is nothing to write"),
    ([CHART, []], "there is nothing to write"),
])
def test_what_cannot_be_written_is_refused_without_quoting_the_chart(pages, message):
    with pytest.raises(PdfError) as caught:
        pages_to_pdf(pages)
    assert message in str(caught.value)
    assert not any(line in str(caught.value) for page in pages for line in page if line)


def test_an_unknown_paper_is_refused():
    with pytest.raises(PdfError, match="unknown paper size"):
        pages_to_pdf([CHART], "foolscap")


def test_pdfium_reads_the_file_the_way_the_writer_meant(tmp_path):
    pdfium = pytest.importorskip("pypdfium2")
    pages = [CHART, Page(["Core = Area A cores", "", "T/D  1  2", ""],
                         ["Stacks (to scale)", "+---+"]), ["Core = " + " ".join(["word"] * 40)]]
    path = tmp_path / "charts.pdf"
    path.write_bytes(pages_to_pdf(pages))
    document = pdfium.PdfDocument(str(path))
    assert len(document) == 3
    for number, (page, rendered) in enumerate(zip(pages, document), 1):
        lines = page if isinstance(page, list) else page.chart + page.drawing
        text = rendered.get_textpage().get_text_range()
        assert text.split() == (" ".join(lines) + f" Page {number} of 3").split()


# A long line is wrapped in the chart, at a space and under the start of its value, so that
# one long name does not set every page of the document at a small size (D73). All the
# names here are invented.

NAME = ("Sample annex north wing utility room cores for the example building maintenance "
        "storage area and loading dock level two")
LONG = f"Core = {NAME}"                                  # well over a hundred columns
LONG_CHART = ["Key System = Example building", "System = A2", LONG, "Date = 2026-01-01", "",
              "T/D      4  6  9", "Bottom   5  3  0"]


def set_lines(pages, paper="letter"):
    """The lines of each page as they are set (chart and drawing), and the document."""
    doc = read_pdf(pages_to_pdf(pages, paper))
    return [page.lines for page in doc.pages], doc


def test_the_wrap_column_is_what_a_chart_at_the_largest_size_fits_on_letter():
    width, _ = pdfwriter.PAPER["letter"]
    assert pdfwriter.WRAP_COLUMNS == 70
    assert pdfwriter.WRAP_COLUMNS == int((width - 2 * pdfwriter.MARGIN)
                                         / (pdfwriter.CHAR_WIDTH * pdfwriter.MAX_SIZE))


def test_a_long_line_is_wrapped_at_spaces_within_the_limit_and_indented_under_its_value():
    (lines,), doc = set_lines([LONG_CHART])
    assert len(LONG) > 110 and all(len(line) <= pdfwriter.WRAP_COLUMNS for line in lines)
    at = lines.index(next(line for line in lines if line.startswith("Core = ")))
    assert lines[at].startswith("Core = Sample annex")
    continuation = [line for line in lines[at + 1:] if line.startswith(" ")]
    assert len(continuation) >= 1 and lines[at + 1 + len(continuation)] == "Date = 2026-01-01"
    assert all(line.startswith(" " * 7) and line[7] != " " for line in continuation)
    assert unwrap(lines) == LONG_CHART                   # nothing added, dropped or reordered


def test_a_long_line_is_broken_at_a_space_and_as_late_as_possible():
    first, *rest = pdfwriter.wrap_line(LONG)
    assert len(first) <= 70 < len(first) + 1 + len(rest[0].strip().split(" ")[0])
    assert " ".join([first] + [line[7:] for line in rest]) == LONG
    assert all(len(line) <= 70 for line in [first, *rest])


@pytest.mark.parametrize("prefix", ["Key System", "Control Key", "master_sub"])
def test_the_continuation_lines_line_up_under_the_value_whatever_the_name(prefix):
    line = f"{prefix} = " + " ".join(["alpha", "bravo", "charlie", "delta"] * 8)
    first, *rest = pdfwriter.wrap_line(line)
    indent = len(prefix) + 3
    assert rest and all(line.startswith(" " * indent) and line[indent] != " " for line in rest)
    assert all(len(part) <= 70 for part in [first, *rest])
    assert " ".join([first] + [part[indent:] for part in rest]) == line


@pytest.mark.parametrize("line", [
    "Core = short",                                        # fits already
    "T/D " + "  4" * 30,                                  # a table row: no `Name = `
    "Core = " + "x" * 100,                                # one word longer than the limit
    "k" * 68 + " = a b c",                                # the name leaves no room for a word
    "Core = " + " ".join(["word"] * 10) + " " + "y" * 70 + " tail",   # a later word does not fit
    "Core = " + "z" * 64 + " b",                          # the indent leaves no room for ' b'
])
def test_a_line_that_cannot_be_wrapped_within_the_limit_is_left_whole(line):
    assert pdfwriter.wrap_line(line) == [line]


def visible(part):
    """The columns a line takes: spaces at its end print nothing."""
    return len(part.rstrip(" "))


def check_wrapped(line, parts, indent=7):
    """What wrapping a `Name = value` line promises: it rejoins to the line, each part is at
    most 70 columns, and each continuation begins at the value's column and not further in
    (a continuation is never only the indent, and a space of the line is not lost)."""
    assert " ".join([parts[0]] + [part[indent:] for part in parts[1:]]) == line
    assert all(part[:indent] == " " * indent and part[indent:indent + 1] not in ("", " ")
               for part in parts[1:])
    assert all(visible(part) <= pdfwriter.WRAP_COLUMNS for part in parts)


def test_wrapping_a_line_with_repeated_spaces_still_rejoins_to_the_original():
    line = "Core = " + "ab  cd " * 20 + "end"
    parts = pdfwriter.wrap_line(line)
    assert len(parts) > 1
    check_wrapped(line, parts)


@pytest.mark.parametrize("tail", [" ", "   ", "  yy", "   yy", " yy ", "  yy  zz"])
def test_an_empty_word_never_starts_a_continuation_line(tail):
    """A trailing space or a doubled space at the break stays on the line it follows."""
    line = "Core = " + "x" * 63 + tail
    parts = pdfwriter.wrap_line(line)
    check_wrapped(line, parts)
    assert [part.strip() for part in parts][-1] != ""


def test_a_trailing_space_after_a_full_line_does_not_make_a_second_line():
    line = "Core = " + "x" * 63 + " "                        # 70 columns and a space
    assert pdfwriter.wrap_line(line) == [line]


def test_a_doubled_space_at_the_break_goes_to_the_line_before_it():
    parts = pdfwriter.wrap_line("Core = " + "x" * 63 + "  yy")
    assert parts == ["Core = " + "x" * 63 + " ", " " * 7 + "yy"]


def test_a_trailing_space_does_not_count_as_a_column_in_the_size():
    chart = ["Core = " + "x" * 63 + " "]                      # 71 characters, 70 columns
    page, = read_pdf(pages_to_pdf([chart])).pages
    assert page.size == 12 and page.lines == chart


def test_wrapping_holds_its_promises_for_awkward_lines():
    """Random names, words and runs of spaces (invented, seeded): every result rejoins to its
    line and keeps the indent exactly, and is all within 70 columns or the line whole."""
    rng = random.Random(7)
    for _ in range(3000):
        name = "".join(rng.choice("abc_(\\") for _ in range(rng.randint(1, 20)))
        words = ["".join(rng.choice("xyz)") for _ in range(rng.randint(0, 25)))
                 for _ in range(rng.randint(1, 18))]
        line = f"{name} = " + " ".join(words)
        parts = pdfwriter.wrap_line(line)
        if parts == [line]:
            continue
        check_wrapped(line, parts, indent=len(name) + 3)


def test_one_long_name_does_not_shrink_the_document():
    pages = [CHART, LONG_CHART, OTHER, LONG_CHART]
    lines, doc = set_lines(pages)
    size, = {page.size for page in doc.pages}
    assert size == pdfwriter.MAX_SIZE == 12
    assert [unwrap(page) for page in lines] == pages


def test_the_height_rule_counts_the_continuation_lines():
    """Thirty long lines wrap to a few lines each: the page is taller than the thirty lines
    it was given, and the size is the largest at which what is set, wrapped, fits."""
    chart = ["Date = 2026-01-01"] + [f"Name{n} = " + NAME for n in range(30)] + ["T/D      4  6"]
    (lines,), doc = set_lines([chart])
    page, = doc.pages
    assert len(lines) >= len(chart) + 30 and unwrap(lines) == chart
    width, height = pdfwriter.PAPER["letter"]
    assert page.size < pdfwriter.MAX_SIZE
    last = page.y - (len(lines) - 1) * page.leading
    assert last >= pdfwriter.MARGIN - 1e-6
    assert max(map(len, lines)) <= pdfwriter.WRAP_COLUMNS
    bigger = page.size + pdfwriter.STEP                  # half a point more would not fit
    assert (height - pdfwriter.MARGIN - bigger) - (len(lines) - 1) * bigger \
        * pdfwriter.LEADING < pdfwriter.MARGIN


def test_an_unbreakable_long_word_still_sets_the_size_down_to_fit():
    chart = ["Date = 2026-01-01", "Core = " + "x" * 100, "T/D      4  6"]
    (lines,), doc = set_lines([chart])
    page, = doc.pages
    assert lines == chart                                # not cut, not wrapped
    assert page.size == 7.5 and 107 * pdfwriter.CHAR_WIDTH * page.size <= 504


def test_an_unbreakable_word_too_long_for_the_page_is_refused_without_quoting_it():
    chart = ["Date = 2026-01-01", "Core = " + "x" * 300]
    with pytest.raises(PdfError, match="page 2 would need a font smaller than 6 points") as e:
        pages_to_pdf([CHART, chart])
    assert "x" * 20 not in str(e.value)


def test_a_drawing_is_never_wrapped_and_keeps_its_own_width_and_size_rules():
    drawing = [f"Stacks = {'ab ' * 25}", "|" * 85]
    page, = read_pdf(pages_to_pdf([Page(LONG_CHART + [""], drawing)])).pages
    assert page.lines[-2:] == drawing and page.drawing == 2
    assert (page.size, page.drawing_size) == (12, 9.5)   # 85 columns still sets the drawing


def test_a_plain_page_and_a_page_without_a_drawing_are_wrapped_alike():
    plain, = read_pdf(pages_to_pdf([LONG_CHART])).pages
    paged, = read_pdf(pages_to_pdf([Page(LONG_CHART)])).pages
    assert plain.lines == paged.lines and plain.size == paged.size == 12


def test_a_wrapped_line_is_set_once_with_its_parentheses_and_backslashes_intact():
    line = "Core = " + " ".join(["(open", "back\\slash", "close)"] * 12)
    (lines,), _ = set_lines([[line]])
    assert len(lines) > 1 and unwrap(lines) == [line]
