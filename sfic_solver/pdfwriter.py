"""Writing the pinning charts as one PDF (docs/designs/pdf-output.md).

One page for each chart, with its drawing under it if it has one, set in Courier, which
every PDF reader and printer has, so nothing is embedded. A long line of a chart is
wrapped at a space. The file is written by hand with the standard library, and does
nothing but pages of plain lines of text: no images, no fonts of its own, no links. It
records no date, author or file name, so equal input gives equal bytes. A chart is key
data, so an error says which page and what kind of problem and never what was written.
"""
from collections import namedtuple

PAPER = {"letter": (612, 792), "a4": (595, 842)}     # points; a point is 1/72 inch
MARGIN = 54                # three-quarters of an inch
CHAR_WIDTH = 0.6           # Courier is 0.6 em wide, a character at a time
LEADING = 1.15             # line pitch, in em
MAX_SIZE, DRAWING_MAX_SIZE, MIN_SIZE, STEP = 12.0, 10.0, 6.0, 0.5     # points
FOOTER_SIZE = 8
WRAP_COLUMNS = 70          # where a chart is set at MAX_SIZE on Letter: 504 / (0.6 * 12)
NAME_VALUE = " = "         # between the name and the value of a `Name = value` line
TITLE, PRODUCER = "Pinning charts", "sfic-solver"
ENCODING = "cp1252"        # the PDF's WinAnsiEncoding


class PdfError(ValueError):
    """The charts cannot be written as a PDF."""


class Page(namedtuple("Page", "chart drawing")):
    """One page: the lines of a chart and, set smaller under it if it has one, the lines of
    its drawing. `pages_to_pdf` also takes a plain list of lines for a page without one."""

    def __new__(cls, chart, drawing=()):
        return super().__new__(cls, list(chart), list(drawing))


def number(value):
    """A number as PDF text: plain decimals, never an exponent."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def encode(page, line):
    """A line as the bytes of the font's encoding, or PdfError (which says where only)."""
    try:
        data = line.encode(ENCODING)
    except UnicodeEncodeError:
        raise PdfError(f"page {page} has a character the PDF's font cannot print") from None
    if any(byte < 32 or byte == 127 for byte in data):
        raise PdfError(f"page {page} has a control character")
    return data


def escape(data):
    """The body of a PDF string: backslash and parentheses escaped."""
    return data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def floor_to_step(size):
    return int(size / STEP + 1e-9) * STEP


def visible_width(line):
    """The columns a line takes: spaces at its end print nothing."""
    return len(line.rstrip(" "))


def wrap_line(line, columns=WRAP_COLUMNS):
    """A chart line as the lines it is set in: itself, or, if it is `Name = value`, longer
    than `columns` and can be, broken at spaces into lines of at most `columns`, each
    after the first indented to the start of the value (as far in as `Name = ` is long).

    Each line is filled as far as it will go. A line is broken only at a space that has a
    word after it, so an empty word (from a doubled space, or a space at the end) stays on
    the line it follows, and spaces at the end of a line print nothing and are not counted.
    A line that cannot be broken to fit (no `Name = `, or a word that is longer than the
    room left after the indent, the first included) is returned whole, never cut: it then
    sets the font size down to fit, or is refused, as it was before lines were wrapped. Cut
    at the indent and joined with a space, the lines are the original again."""
    at = line.find(NAME_VALUE)
    if visible_width(line) <= columns or at < 0:
        return [line]
    indent = at + len(NAME_VALUE)
    words = line[indent:].split(" ")
    lines = [line[:indent] + words[0]]
    for word in words[1:]:
        if not word:
            lines[-1] += " "
        elif len(lines[-1]) + 1 + len(word) <= columns:
            lines[-1] += " " + word
        else:
            lines.append(" " * indent + word)
    return lines if all(visible_width(part) <= columns for part in lines) else [line]


def font_sizes(pages, width, height):
    """(chart size, drawing size or None) for the whole document, in STEP steps.

    The chart comes first: it gets the largest size up to MAX_SIZE at which its widest
    line fits between the margins and the page still fits its height with the drawing
    (if it has one) set as small as MIN_SIZE. The drawing then gets the largest size, up
    to DRAWING_MAX_SIZE and no larger than the chart, that fits the width and the height
    that is left. One pair serves every page, so no page looks different from the next.
    The pages are as they are set, a long chart line already wrapped."""
    across, down = width - 2 * MARGIN, height - 2 * MARGIN
    chart_size = MAX_SIZE
    for page_no, page in enumerate(pages, 1):
        n, m = len(page.chart), len(page.drawing)
        limit = across / (CHAR_WIDTH * max(map(visible_width, page.chart)))
        reserved = m and MIN_SIZE * (m - 1) * LEADING
        limit = min(limit, (down - reserved) / (1 + (n if m else n - 1) * LEADING))
        chart_size = min(chart_size, floor_to_step(limit))
        if chart_size < MIN_SIZE:
            raise PdfError(f"page {page_no} would need a font smaller than {MIN_SIZE:g} points "
                           f"to fit the page")
    drawing_size = None
    for page_no, page in enumerate(pages, 1):
        n, m = len(page.chart), len(page.drawing)
        if not m:
            continue
        limit = min(across / (CHAR_WIDTH * max(map(len, page.drawing))), DRAWING_MAX_SIZE,
                    chart_size)
        if m > 1:
            left = down - chart_size * (1 + n * LEADING)
            limit = min(limit, left / ((m - 1) * LEADING))
        size = floor_to_step(limit)
        if size < MIN_SIZE:
            raise PdfError(f"page {page_no} would need a font smaller than {MIN_SIZE:g} points "
                           f"to fit the page")
        drawing_size = size if drawing_size is None else min(drawing_size, size)
    return chart_size, drawing_size


def page_content(page, sizes, footer, width, height):
    """The content stream of one page: the chart's lines from the top margin down, then the
    drawing's lines in their own size, then the footer centred in the bottom margin.
    `page` is a Page of bytes lines, `sizes` the (chart, drawing) sizes, `footer` bytes."""
    chart_size, drawing_size = sizes
    footer_x = (width - len(footer) * CHAR_WIDTH * FOOTER_SIZE) / 2
    ops = [b"BT", b"/F1 %s Tf" % number(chart_size).encode(),
           b"%s TL" % number(chart_size * LEADING).encode(),
           b"%d %s Td" % (MARGIN, number(height - MARGIN - chart_size).encode())]
    ops += [b"(" + escape(line) + b") Tj T*" for line in page.chart]
    if page.drawing:
        ops += [b"/F1 %s Tf" % number(drawing_size).encode(),
                b"%s TL" % number(drawing_size * LEADING).encode()]
        ops += [b"(" + escape(line) + b") Tj T*" for line in page.drawing]
    ops += [b"ET", b"BT", b"/F1 %d Tf" % FOOTER_SIZE,
            b"%s %s Td" % (number(footer_x).encode(), number(MARGIN / 2).encode()),
            b"(" + escape(footer) + b") Tj", b"ET"]
    return b"\n".join(ops)


def pages_to_pdf(pages, paper="letter"):
    """The bytes of a PDF with one page for each of `pages`.

    pages  a list of pages, each a Page (a chart's lines and, optionally, a drawing's) or a
           plain non-empty list of text lines (no newlines). A long chart line is wrapped
           (wrap_line); a drawing's lines are set as they are.
    paper  "letter" or "a4"
    """
    if paper not in PAPER:
        raise PdfError(f"unknown paper size {paper!r}; known sizes: {', '.join(sorted(PAPER))}")
    pages = [page if isinstance(page, Page) else Page(page) for page in pages]
    if not pages or any(not page.chart for page in pages):
        raise PdfError("there is nothing to write")
    pages = [Page([part for line in page.chart for part in wrap_line(line)], page.drawing)
             for page in pages]
    width, height = PAPER[paper]
    encoded = [Page([encode(page_no, line) for line in page.chart],
                    [encode(page_no, line) for line in page.drawing])
               for page_no, page in enumerate(pages, 1)]
    sizes = font_sizes(pages, width, height)

    # Objects 1 to 4 are the catalogue, the page tree, the font and the document info;
    # each page then adds its content stream and its page object.
    objects = [b"", b"",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
               f"<< /Title ({TITLE}) /Producer ({PRODUCER}) >>".encode("ascii")]
    kids = []
    for page_no, page in enumerate(encoded, 1):
        stream = page_content(page, sizes, f"Page {page_no} of {len(pages)}".encode("ascii"),
                              width, height)
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
                        f"/Contents {len(objects)} 0 R "
                        f"/Resources << /Font << /F1 3 0 R >> >> >>").encode("ascii"))
        kids.append(len(objects))
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = (f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] "
                  f"/Count {len(kids)} >>").encode("ascii")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")      # the second line marks it binary
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    table = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii") + b"0000000000 65535 f \n"
    out += b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets)
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 4 0 R >>\n"
            f"startxref\n{table}\n%%EOF\n").encode("ascii")
    return bytes(out)
