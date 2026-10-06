"""pdfwriter: a hand-written PDF that a reader of our own, and where installed pdfium and
poppler, take as one page to a chart, with exactly the chart's lines."""
import pytest

from pdfread import read_pdf
from sfic_solver import pdfwriter
from sfic_solver.pdfwriter import PdfError, pages_to_pdf

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
    assert page.size == pdfwriter.MAX_SIZE == 10


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
    pages = [CHART, ["Core = Area A cores", "", "T/D  1  2", "Stacks (to scale)"]]
    path = tmp_path / "charts.pdf"
    path.write_bytes(pages_to_pdf(pages))
    document = pdfium.PdfDocument(str(path))
    assert len(document) == 2
    for number, (lines, page) in enumerate(zip(pages, document), 1):
        text = page.get_textpage().get_text_range()
        assert text.split() == (" ".join(lines) + f" Page {number} of 2").split()
