"""From pages to charts: read every page, then resolve the marks of the whole run.

Reading is in two passes because the shape groups are pooled over the whole run
(a larger batch makes the groups better): the first pass cleans each page, finds its
lines, classifies them by their labels, adds every digit mark to the shared groups
and records the readings as votes; the second resolves the groups and assembles the
charts. Images are dropped as soon as a page is read, so a run holds only the
marks' shapes and the records.

A line is a header line if it has an equals sign after one or two label words, and a
row if it starts with one of the row labels; labels are read as text and must agree
exactly. Anything else is "ignored" and reported by position, so that a title or a
page number is not mistaken for part of a chart, and a dropped row cannot hide.
"""
from .. import charts
from . import assemble, clean, groups, layout, ocr

PAD_X, PAD_Y = 0.4, 0.4          # crop padding, in glyph heights


def padded(tokens, line, height):
    """The crop box (x0, y0, x1, y1) around some tokens on a line."""
    pad_x, pad_y = int(PAD_X * height), int(PAD_Y * height)
    return (tokens[0].x0 - pad_x, line.y0 - pad_y, tokens[-1].x1 + pad_x, line.y1 + pad_y)


def marks_of(tokens):
    """The digit glyphs among tokens, in order, and the boxes of everything else."""
    digits, other = [], []
    for token in tokens:
        for glyph in token.glyphs:
            (digits if glyph.kind == layout.MARK else other).append(glyph)
    return digits, [(g.x0, g.y0, g.x1, g.y1) for g in other]


def read_digit_marks(recogniser, arrays, marks, mask, line, tokens, height):
    """Add the digit marks of `tokens` to the shared groups and vote with the readings
    of the row; returns the mark ids in order.

    Every rendition is read twice: as the row stands, and with a copy of the row's
    first digit pasted after it, because the last character of a line is the one
    Tesseract gets wrong. The two kinds fail in different places, and all the usable
    readings vote.
    """
    digits, blank = marks_of(tokens)
    ids = [marks.add(mask, glyph) for glyph in digits]
    if not ids:
        return ids
    box = padded(tokens, line, height)
    readings = ocr.read_marks(recogniser, arrays, box, height, blank)
    first = next(t for t in tokens if t.kind == layout.MARK)
    follower = (first.x0, line.y0, first.x1, line.y1)
    readings += ocr.read_marks(recogniser, arrays, box, height, blank, tail=follower,
                               tail_marks=sum(1 for g in first.glyphs if g.kind == layout.MARK))
    marks.vote(ids, readings)
    return ids


def read_label(recogniser, arrays, tokens, line, height, whitelist=ocr.LETTERS):
    return ocr.agreed(ocr.read_text(recogniser, arrays, padded(tokens, line, height),
                                    height, whitelist))


def bittings_in(recogniser, arrays, marks, mask, line, tokens, height):
    """The keys in a header line's value: digit marks separated by commas or gaps."""
    digits_all = read_digit_marks(recogniser, arrays, marks, mask, line, tokens, height)
    # Walk the glyphs again to cut the ids into keys where a comma or a token ends.
    bittings, current, at = [], [], 0
    for token in tokens:
        for glyph in token.glyphs:
            if glyph.kind == layout.MARK:
                current.append(digits_all[at])
                at += 1
            elif glyph.kind == layout.DOT and current:
                bittings.append(current)
                current = []
        if current:
            bittings.append(current)
            current = []
    return bittings


def read_page(page, recogniser, marks):
    """Read one page into a PageRecord, adding its marks to `marks`."""
    record = assemble.PageRecord(page.source, page.number)
    try:
        prepared = clean.prepare(page.image)
        found = layout.analyse(prepared)
    except Exception as error:                      # never put page content in a message
        record.failed = f"could not be analysed ({type(error).__name__})"
        return record
    if found is None:
        record.blank = True
        return record
    record.outside = len(found.outside)
    if found.too_small:
        record.too_small = True
        return record
    arrays = ocr.source_arrays(prepared, found.mask)
    try:
        for number, line in enumerate(found.lines, 1):
            read_line(record, number, line, found, arrays, found.mask, recogniser, marks)
    except Exception as error:
        record.failed = f"could not be read ({type(error).__name__})"
    return record


def read_line(record, number, line, found, arrays, mask, recogniser, marks):
    height = found.glyph_height
    equals = layout.find_equals(line, height)
    if equals is not None:
        label = read_label(recogniser, arrays, line.tokens[:equals], line, height)
        kind = assemble.HEADER_NAMES.get(label)
        if kind is None:
            record.ignored.append(number)
            return
        value = line.tokens[equals + 1:]
        entry = assemble.LineRecord(number, kind)
        if kind == charts.SYSTEM:
            name = ocr.agreed(ocr.read_text(recogniser, arrays, padded(value, line, height),
                                            height, ocr.ALPHANUMERIC))
            entry.system = name.upper().replace(" ", "") if name else None
        else:
            entry.bittings = bittings_in(recogniser, arrays, marks, mask, line, value, height)
        record.lines.append(entry)
        return
    label = read_label(recogniser, arrays, line.tokens[:1], line, height)
    kind = assemble.ROW_NAMES.get(label)
    if kind is None or len(line.tokens) < 2:
        record.ignored.append(number)
        return
    cells_tokens = line.tokens[1:]
    ids = read_digit_marks(recogniser, arrays, marks, mask, line, cells_tokens, height)
    cells, at = [], 0
    for token in cells_tokens:
        if token.kind == layout.DASH:
            cells.append(assemble.Cell(True))
            continue
        count = sum(1 for g in token.glyphs if g.kind == layout.MARK)
        cells.append(assemble.Cell(False, ids[at:at + count]))
        at += count
    record.lines.append(assemble.LineRecord(number, kind, cells=cells))


class Scan:
    """The result of reading a run: page records, charts, and what the groups made."""

    def __init__(self, pages, charts_found, small_marks, group_count):
        self.pages = pages
        self.charts = charts_found
        self.small_marks = small_marks
        self.group_count = group_count


def scan(pages, recogniser, progress=None):
    """Read every page (an iterable of Page) and return the Scan."""
    marks = groups.Marks()
    records = []
    for page in pages:
        records.append(read_page(page, recogniser, marks))
        if progress:
            progress(page)
    resolved = assemble.Resolved(marks.resolve())
    found = []
    for record in records:
        found.extend(assemble.assemble(record, resolved))
    return Scan(records, found, marks.small_groups(), len(marks.counts))
