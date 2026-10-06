"""Writing the pinning charts as one PDF (docs/designs/pdf-output.md).

One page for each chart, set in Courier, which every PDF reader and printer has, so
nothing is embedded. The file is written by hand with the standard library, and does
nothing but pages of plain lines of text: no images, no fonts of its own, no links. It
records no date, author or file name, so equal input gives equal bytes. A chart is key
data, so an error says which page and what kind of problem and never what was written.
"""

PAPER = {"letter": (612, 792), "a4": (595, 842)}     # points; a point is 1/72 inch
MARGIN = 54                # three-quarters of an inch
CHAR_WIDTH = 0.6           # Courier is 0.6 em wide, a character at a time
LEADING = 1.15             # line pitch, in em
MAX_SIZE, MIN_SIZE, STEP = 10.0, 6.0, 0.5
FOOTER_SIZE = 8
TITLE, PRODUCER = "Pinning charts", "sfic-solver"
ENCODING = "cp1252"        # the PDF's WinAnsiEncoding


class PdfError(ValueError):
    """The charts cannot be written as a PDF."""


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


def font_size(pages, width, height):
    """The one size for every page: the largest, up to MAX_SIZE and in STEP steps, at which
    the widest line fits between the margins and the longest page fits its height."""
    sizes = []
    for page, lines in enumerate(pages, 1):
        across = (width - 2 * MARGIN) / (CHAR_WIDTH * max(len(line) for line in lines))
        down = (height - 2 * MARGIN) / (1 + (len(lines) - 1) * LEADING)
        size = int(min(across, down, MAX_SIZE) / STEP) * STEP
        if size < MIN_SIZE:
            raise PdfError(f"page {page} would need a font smaller than {MIN_SIZE:g} points "
                           f"to fit the page")
        sizes.append(size)
    return min(sizes)


def page_content(lines, size, footer, width, height):
    """The content stream of one page: the lines from the top margin down, then the footer
    centred in the bottom margin. `lines` and `footer` are bytes."""
    footer_x = (width - len(footer) * CHAR_WIDTH * FOOTER_SIZE) / 2
    ops = [b"BT", b"/F1 %s Tf" % number(size).encode(),
           b"%s TL" % number(size * LEADING).encode(),
           b"%d %s Td" % (MARGIN, number(height - MARGIN - size).encode())]
    ops += [b"(" + escape(line) + b") Tj T*" for line in lines]
    ops += [b"ET", b"BT", b"/F1 %d Tf" % FOOTER_SIZE,
            b"%s %s Td" % (number(footer_x).encode(), number(MARGIN / 2).encode()),
            b"(" + escape(footer) + b") Tj", b"ET"]
    return b"\n".join(ops)


def pages_to_pdf(pages, paper="letter"):
    """The bytes of a PDF with one page for each list of lines in `pages`.

    pages  a list of pages, each a non-empty list of text lines (no newlines)
    paper  "letter" or "a4"
    """
    if paper not in PAPER:
        raise PdfError(f"unknown paper size {paper!r}; known sizes: {', '.join(sorted(PAPER))}")
    if not pages or any(not lines for lines in pages):
        raise PdfError("there is nothing to write")
    width, height = PAPER[paper]
    encoded = [[encode(page, line) for line in lines] for page, lines in enumerate(pages, 1)]
    size = font_size(pages, width, height)

    # Objects 1 to 4 are the catalogue, the page tree, the font and the document info;
    # each page then adds its content stream and its page object.
    objects = [b"", b"",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
               f"<< /Title ({TITLE}) /Producer ({PRODUCER}) >>".encode("ascii")]
    kids = []
    for page, lines in enumerate(encoded, 1):
        stream = page_content(lines, size, f"Page {page} of {len(pages)}".encode("ascii"),
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
