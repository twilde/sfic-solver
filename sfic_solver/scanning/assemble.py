"""From the lines read off a page to charts, checks, and the legacy chart text.

This works on records, not images: a page's lines classified as header lines or
rows, with the marks of each digit cell. Marks are resolved by `groups` and passed in
as values. A chart ends up in one of three places (D38):

  accepted   read completely, well formed, and every chart-internal check passed
  failed     read completely (every cell and digit is a number) but failed a check;
             written as read, in a layout `check_charts` can read
  review     not read completely or not well formed; unreadable digits are `??`,
             which `check_charts` refuses, so such a chart is never checked by accident

Nothing here consults the pinner or the keys, and nothing chooses between readings
so that a check passes. The two facts about a chart used are the ones that hold for
any chart in the layout: master rows fill from the bottom, and each chamber's pins
add up to the pinning system's stack total. They can only flag.

Flags are positions and kinds of problem, never a digit read from the page.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from .. import charts, pinning
from . import groups

ACCEPTED, FAILED, REVIEW = "accepted", "failed", "review"
UNREADABLE = "??"
SEPARATOR = "-" * 40

HEADER_ORDER = (charts.SYSTEM, charts.CONTROL_KEY, charts.MASTER_KEY, charts.CHANGE_KEYS)
HEADER_NAMES = {"system": charts.SYSTEM, "control key": charts.CONTROL_KEY,
                "master key": charts.MASTER_KEY, "change keys": charts.CHANGE_KEYS}
ROW_NAMES = {"t/d": "T/D", "control": "Control", "master": "Master", "bottom": "Bottom"}
ROW_ORDER_FIRST, ROW_ORDER_LAST = ("T/D", "Control"), "Bottom"

REASON_WORDS = {
    groups.TOO_SMALL: "too few marks of that shape to vote",
    groups.IMPURE: "the readings of that shape did not agree",
    groups.DUPLICATE: "two shapes were read as the same digit",
    groups.UNVOTED: "no usable reading",
    groups.DISSENT: "its own readings disagree with its shape's",
}


@dataclass
class Cell:
    dash: bool
    marks: List[int] = field(default_factory=list)       # mark ids of its digits


@dataclass
class LineRecord:
    number: int                       # the line's position on the page, 1-based
    kind: str                         # a header label (charts.SYSTEM, ...) or a row label
    system: Optional[str] = None      # for the System line: the name as read (upper case)
    bittings: List[List[int]] = field(default_factory=list)   # header keys: mark ids each
    cells: List[Cell] = field(default_factory=list)           # rows


@dataclass
class PageRecord:
    source: int
    number: int
    lines: List[LineRecord] = field(default_factory=list)
    ignored: List[int] = field(default_factory=list)          # line numbers not in a chart
    outside: int = 0                                          # marks outside the block
    blank: bool = False
    too_small: bool = False
    failed: Optional[str] = None                              # a kind of problem, if the page failed


@dataclass
class Chart:
    source: int
    page: int
    number: int
    status: str
    text: str
    flags: List[str]


class Resolved:
    """Mark values and flag reasons, by mark id."""

    def __init__(self, marks):
        self.marks = marks

    def value(self, mark):
        return self.marks[mark].value

    def reason(self, mark):
        return REASON_WORDS.get(self.marks[mark].reason, "unreadable")


def split_charts(records):
    """Group a page's classified lines into chart drafts: a chart starts at a System
    line and runs to the next. Lines before the first System line belong to none."""
    drafts, orphans = [], []
    for record in records:
        if record.kind == charts.SYSTEM:
            drafts.append([record])
        elif drafts:
            drafts[-1].append(record)
        else:
            orphans.append(record.number)
    return drafts, orphans


def read_digits(marks, resolved):
    """(text of digits with ? for unreadable, [reasons], complete?) for mark ids."""
    text, reasons = [], []
    for mark in marks:
        value = resolved.value(mark)
        text.append(value if value is not None else "?")
        if value is None:
            reasons.append(resolved.reason(mark))
    return "".join(text), reasons


def cell_text(cell, resolved):
    """(text, reason or None): the cell as `--`, digits, or ?? if it cannot be read."""
    if cell.dash:
        return "--", None
    if not 1 <= len(cell.marks) <= 2:
        return UNREADABLE, "the cell does not have one or two digits"
    text, reasons = read_digits(cell.marks, resolved)
    if "?" in text:
        return UNREADABLE, reasons[0]
    return text, None


def assemble(page, resolved, first_number=1):
    """The Charts on a page, in order, from its PageRecord and resolved marks."""
    drafts, _ = split_charts(page.lines)
    return [chart_from(page, number, draft, resolved)
            for number, draft in enumerate(drafts, first_number)]


def chart_from(page, number, draft, resolved):
    flags = []
    headers = {r.kind: r for r in draft if r.kind in HEADER_ORDER}
    rows = [r for r in draft if r.kind not in HEADER_ORDER]
    complete = True

    # --- structure -------------------------------------------------------------
    order = [r.kind for r in draft if r.kind in HEADER_ORDER]
    for name in HEADER_ORDER:
        if name not in headers:
            flags.append(f"the {name.title()} header line is missing")
            complete = False
    if complete and order != list(HEADER_ORDER):
        flags.append("the header lines are not in the order System, Control Key, "
                     "Master Key, Change Keys")
        complete = False
    kinds = [r.kind for r in rows]
    if not (len(kinds) >= 3 and kinds[:2] == list(ROW_ORDER_FIRST) and kinds[-1] == ROW_ORDER_LAST
            and all(k == "Master" for k in kinds[2:-1])):
        flags.append("the rows are not T/D, Control, any Master rows, then Bottom")
        complete = False

    system = None
    if charts.SYSTEM in headers:
        try:
            system = pinning.get_system(headers[charts.SYSTEM].system or "")
        except ValueError:
            flags.append("the pinning system named in the header is not known")
            complete = False

    # --- header keys ---------------------------------------------------------------
    header_text = {charts.SYSTEM: system.name if system else UNREADABLE}
    chambers = None
    keys = {}
    for name in (charts.CONTROL_KEY, charts.MASTER_KEY, charts.CHANGE_KEYS):
        record = headers.get(name)
        texts = []
        if record is not None:
            for bitting in record.bittings:
                text, reasons = read_digits(bitting, resolved)
                texts.append(text)
                if "?" in text:
                    complete = False
                    flags.append(f"{name.title()} digit {text.index('?') + 1}: {reasons[0]}")
            if name != charts.CHANGE_KEYS and len(record.bittings) != 1:
                flags.append(f"{name.title()} should hold one key")
                complete = False
            if name == charts.CHANGE_KEYS and not record.bittings:
                flags.append("Change Keys holds no key")
                complete = False
        keys[name] = texts
    if keys.get(charts.CONTROL_KEY):
        chambers = len(keys[charts.CONTROL_KEY][0])
    for name, texts in keys.items():
        if chambers is not None and any(len(t) != chambers for t in texts):
            flags.append(f"{name.title()} has a key of a different length from the control key")
            complete = False
    header_text[charts.CONTROL_KEY] = keys[charts.CONTROL_KEY][0] if keys.get(charts.CONTROL_KEY) \
        else UNREADABLE
    header_text[charts.MASTER_KEY] = keys[charts.MASTER_KEY][0] if keys.get(charts.MASTER_KEY) \
        else UNREADABLE
    header_text[charts.CHANGE_KEYS] = ", ".join(keys[charts.CHANGE_KEYS]) \
        if keys.get(charts.CHANGE_KEYS) else UNREADABLE

    # --- rows -------------------------------------------------------------------------
    row_cells = []
    for index, record in enumerate(rows, 1):
        label = record.kind
        if chambers is None or len(record.cells) != chambers:
            flags.append(f"row {index} ({label}) does not have one cell per chamber")
            complete = False
            row_cells.append((label, [UNREADABLE] * (chambers or len(record.cells))))
            continue
        cells = []
        for chamber, cell in enumerate(record.cells, 1):
            text, why = cell_text(cell, resolved)
            if why:
                complete = False
                flags.append(f"row {index} ({label}) chamber {chamber}: {why}")
            cells.append(text)
        row_cells.append((label, cells))

    status = REVIEW
    if complete:
        problems = check_chart(system, row_cells)
        flags.extend(problems)
        status = FAILED if problems else ACCEPTED
    return Chart(page.source, page.number, number, status,
                 format_chart(header_text, row_cells), flags)


def check_chart(system, row_cells):
    """The chart-internal checks, on a chart read completely: ranges, the fill rule
    for master rows, and each chamber's pins adding up to the stack total."""
    flags = []
    labels = [label for label, _ in row_cells]
    chambers = len(row_cells[0][1])
    for index, (label, cells) in enumerate(row_cells, 1):
        low, high = system.bottom_pins if label == "Bottom" else system.other_pins
        for chamber, text in enumerate(cells, 1):
            if text == "--":
                if label != "Master":
                    flags.append(f"row {index} ({label}) chamber {chamber}: only Master rows "
                                 f"may be empty")
            elif not low <= int(text) <= high:
                flags.append(f"row {index} ({label}) chamber {chamber}: outside the range "
                             f"of a {label} pin")
    for chamber in range(chambers):
        column = [row_cells[i][1][chamber] for i in range(len(row_cells))]
        masters = [column[i] for i, label in enumerate(labels) if label == "Master"]
        # Master rows fill from the bottom, so reading up (the last row first) every
        # empty cell comes after every filled one.
        filled = [c != "--" for c in reversed(masters)]
        if filled != sorted(filled, reverse=True):
            flags.append(f"chamber {chamber + 1}: the master rows do not fill from the bottom")
        if all(c == "--" or c.isdigit() for c in column):
            total = sum(int(c) for c in column if c != "--")
            if total != system.stack_total:
                flags.append(f"chamber {chamber + 1}: the pins do not add up to the "
                             f"stack total")
    return flags


def format_chart(header, row_cells):
    """The chart in the legacy layout, `??` where something could not be read."""
    lines = [f"System = {header[charts.SYSTEM]}",
             f"Control Key = {header[charts.CONTROL_KEY]}",
             f"Master Key = {header[charts.MASTER_KEY]}",
             f"Change Keys = {header[charts.CHANGE_KEYS]}", ""]
    for label, cells in row_cells:
        lines.append(f"{label:<8}" + "".join(f"{c:>3}" for c in cells))
    return "\n".join(lines)


def join_charts(texts):
    """Several charts as one file's text, separated by lines of dashes."""
    return ("\n\n" + SEPARATOR + "\n\n").join(texts) + "\n"
