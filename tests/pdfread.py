"""A reader for the PDFs sfic_solver.pdfwriter writes, and no others.

It is the independent check that the file is a PDF at all, since the core suite runs with
no PDF package: every offset, length and count is checked as it is read, so a file a
real reader would refuse fails here.
"""
import re
from collections import namedtuple

Page = namedtuple("Page", "lines footer size leading x y footer_x footer_y media")
Document = namedtuple("Document", "pages title producer")


def unescape(body):
    """The text of a PDF string body written with backslash, ( and ) escaped."""
    out, i = bytearray(), 0
    while i < len(body):
        if body[i:i + 1] == b"\\":
            out += body[i + 1:i + 2]
            i += 2
        else:
            out += body[i:i + 1]
            i += 1
    return bytes(out).decode("cp1252")


def strings(stream):
    """The strings of a content stream's `(text) Tj` operators, in order."""
    found = []
    for line in stream.split(b"\n"):
        match = re.fullmatch(rb"\((.*)\) Tj( T\*)?", line)
        if match:
            found.append(unescape(match.group(1)))
    return found


def read_pdf(data):
    assert data.startswith(b"%PDF-1.4\n") and data.endswith(b"%%EOF\n")
    table = int(re.search(rb"startxref\n(\d+)\n%%EOF\n$", data).group(1))
    header = re.match(rb"xref\n0 (\d+)\n", data[table:])
    assert header, "startxref does not point at the cross-reference table"
    count = int(header.group(1))
    entries = data[table + header.end():]
    trailer = re.match(rb"trailer\n<< /Size (\d+) /Root (\d+) 0 R /Info (\d+) 0 R >>\n",
                       entries[20 * count:])
    assert trailer and int(trailer.group(1)) == count, "the trailer does not match the table"
    assert entries[:20] == b"0000000000 65535 f \n"
    bodies = {}
    for index in range(1, count):
        entry = entries[20 * index:20 * index + 20]
        assert re.fullmatch(rb"\d{10} 00000 n \n", entry), entry
        offset = int(entry[:10])
        label = f"{index} 0 obj\n".encode()
        assert data[offset:offset + len(label)] == label, f"object {index} is not at its offset"
        end = data.index(b"\nendobj\n", offset)
        bodies[index] = data[offset + len(label):end]

    root = re.fullmatch(rb"<< /Type /Catalog /Pages (\d+) 0 R >>", bodies[int(trailer.group(2))])
    tree = re.fullmatch(rb"<< /Type /Pages /Kids \[([\d 0R]*)\] /Count (\d+) >>",
                        bodies[int(root.group(1))])
    kids = [int(k) for k in re.findall(rb"(\d+) 0 R", tree.group(1))]
    assert int(tree.group(2)) == len(kids)
    info = bodies[int(trailer.group(3))].decode("ascii")
    title, producer = re.fullmatch(r"<< /Title \((.*)\) /Producer \((.*)\) >>", info).groups()

    pages = []
    for kid in kids:
        page = re.fullmatch(rb"<< /Type /Page /Parent %d 0 R /MediaBox \[0 0 (\d+) (\d+)\] "
                            rb"/Contents (\d+) 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
                            % int(root.group(1)), bodies[kid])
        body = bodies[int(page.group(3))]
        length = re.match(rb"<< /Length (\d+) >>\nstream\n", body)
        stream = body[length.end():-len(b"\nendstream")]
        assert body.endswith(b"\nendstream") and len(stream) == int(length.group(1))
        text, footer = stream.split(b"\nET\nBT\n")
        size = float(re.search(rb"/F1 ([\d.]+) Tf", text).group(1))
        leading = float(re.search(rb"([\d.]+) TL", text).group(1))
        x, y = map(float, re.search(rb"\n([\d.]+) ([\d.]+) Td", text).groups())
        footer_x, footer_y = map(float, re.search(rb"\n([\d.]+) ([\d.]+) Td", footer).groups())
        pages.append(Page(strings(text), strings(footer)[0], size, leading, x, y,
                          footer_x, footer_y, (int(page.group(1)), int(page.group(2)))))
    return Document(pages, title, producer)
