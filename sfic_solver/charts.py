"""Reading pinning charts (see docs/designs/core-pinning.md, "The chart layout").

A chart is a header, a blank line and one row of pins per layer, one column per
chamber. Two header layouts are read:

  the tools' layout   Key System, System, Core, Date (all optional but System),
                      Control Key, then one `name = bitting` line per operating key
  the legacy layout   System, Control Key, Master Key and one Change Keys line of
                      comma-separated bittings (older keying software)

A label and its value may be separated by `=` or `:`. Several charts may share a file,
separated by a line of dashes. A chart is key
data, so nothing here puts a chart's content in an error message: errors say
where (chart and line number) and what kind of problem, never what was written.
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple

# The header labels, in one place so that a different spelling in a real chart
# is a one-line change. Matching ignores case and surrounding space.
KEY_SYSTEM, SYSTEM, CORE, DATE = "key system", "system", "core", "date"
CONTROL_KEY, MASTER_KEY, CHANGE_KEYS = "control key", "master key", "change keys"
LEGACY_LABELS = {MASTER_KEY, CHANGE_KEYS}
RESERVED_LABELS = {KEY_SYSTEM, SYSTEM, CORE, DATE, CONTROL_KEY} | LEGACY_LABELS

ROW_LABELS = ("t/d", "control", "master", "bottom")
SEPARATOR = re.compile(r"^-{3,}\s*$")
DIGITS = re.compile(r"[0-9]+")        # ASCII only: \d and str.isdigit() also take ² and ٣
FAKE_MARKER = "FAKE"


def split_header_line(text):
    """(label, value) of a header line written `label = value` or `label: value`, else None.

    A line with an `=` splits at the first one (labels never contain `=`, but a key's
    name may contain `:`, as in `unit:101 = 3101658`); a line with only colons splits
    at the last one, so `unit:101: 3101658` still reads as a key named `unit:101`.
    """
    if "=" in text:
        label, _, value = text.partition("=")
    elif ":" in text:
        label, _, value = text.rpartition(":")
    else:
        return None
    label, value = label.strip(), value.strip()
    return (label, value) if label else None


class ChartError(ValueError):
    """A chart cannot be read. `chart` and `line` say where (1-based, or None)."""

    def __init__(self, reason, chart=None, line=None):
        where = ""
        if chart is not None:
            where = f"chart {chart}" + (f", line {line}" if line is not None else "") + ": "
        super().__init__(where + reason)
        self.reason, self.chart, self.line = reason, chart, line


@dataclass(frozen=True)
class Chart:
    layout: str                              # "tools" or "legacy"
    system: str                              # the pinning system as written, e.g. "A2"
    control: str                             # the control key's bitting
    keys: Tuple[Tuple[str, str], ...]        # (name, bitting) of every operating key
    rows: Tuple[Tuple[str, Tuple[Optional[int], ...]], ...]   # (label, cells); None for "--"
    metadata: Tuple[Tuple[str, str], ...] = ()   # Key System, Core, Date, as written

    @property
    def chambers(self):
        return len(self.control)

    def column(self, chamber):
        """The pins in a chamber from the bottom up as the chart shows them, or None if
        the chart does not follow the fill rule (masters fill from the bottom)."""
        cells = [cells[chamber] for _, cells in reversed(self.rows)]
        # bottom, then master layers from the bottom up, then control, then T/D
        masters = cells[1:-2]
        filled = [c for c in masters if c is not None]
        if masters[:len(filled)] != filled:
            return None
        return tuple([cells[0], *filled, cells[-2], cells[-1]])


def split_charts(text):
    """The text of each chart in a file, as (first line number, lines).

    Charts are separated by lines of dashes. A first line starting FAKE marks a
    test fixture and is skipped.
    """
    lines = text.removeprefix("\ufeff").splitlines()      # a byte order mark is not content
    first = 1
    if lines and lines[0].strip().startswith(FAKE_MARKER):
        lines, first = lines[1:], 2
    blocks, current, start = [], [], first
    for number, line in enumerate(lines, first):
        if SEPARATOR.match(line):
            blocks.append((start, current))
            current, start = [], number + 1
        else:
            current.append(line)
    blocks.append((start, current))
    return [(start, block) for start, block in blocks if any(line.strip() for line in block)]


def parse_chart(start, lines, index):
    """Parse one chart. `start` is the file line number of lines[0]; `index` numbers charts."""
    numbered = list(enumerate(lines, start))
    while numbered and not numbered[0][1].strip():
        numbered.pop(0)
    while numbered and not numbered[-1][1].strip():
        numbered.pop()
    blank = next((i for i, (_, text) in enumerate(numbered) if not text.strip()), None)
    if blank is None:
        raise ChartError("no blank line between the header and the rows", index)
    header, body = numbered[:blank], [item for item in numbered[blank:] if item[1].strip()]

    fields, keys = {}, []
    for number, text in header:
        parts = split_header_line(text)
        if parts is None:
            raise ChartError("a header line is not `label = value` (or `label: value`)",
                             index, number)
        name, value = parts
        label = name.lower()
        if label in RESERVED_LABELS:
            if label in fields:
                raise ChartError("a header label is repeated", index, number)
            fields[label] = value
        elif DIGITS.fullmatch(value):
            keys.append((name, value))
        else:
            raise ChartError("a header line is neither a known label nor `name = bitting`",
                             index, number)

    legacy = bool(LEGACY_LABELS & fields.keys())
    if legacy and keys:
        raise ChartError("the header mixes the tools' layout (name = bitting lines) "
                         "with the legacy one (Master Key, Change Keys)", index)
    if SYSTEM not in fields:
        raise ChartError("no System line", index)
    if CONTROL_KEY not in fields:
        raise ChartError("no Control Key line", index)
    if legacy:
        if MASTER_KEY not in fields or CHANGE_KEYS not in fields:
            raise ChartError("the legacy layout needs both a Master Key and a Change Keys line",
                             index)
        listed = [fields[MASTER_KEY], *[b for b in re.split(r"[,\s]+", fields[CHANGE_KEYS]) if b]]
        keys = [("master" if i == 0 else f"change {i}", b) for i, b in enumerate(listed)]
    if not keys:
        raise ChartError("no operating keys in the header", index)

    control = fields[CONTROL_KEY]
    if not all(DIGITS.fullmatch(bitting) and len(bitting) == len(control)
               for bitting in [control, *[b for _, b in keys]]):
        raise ChartError("every key must be digits and as long as the control key", index)

    rows = []
    for number, text in body:
        label, *cells = text.split()
        if label.lower() not in ROW_LABELS:
            raise ChartError("a row does not start with T/D, Control, Master or Bottom",
                             index, number)
        if len(cells) != len(control) or not all(c == "--" or DIGITS.fullmatch(c) for c in cells):
            raise ChartError("a row does not have one number (or --) per chamber", index, number)
        rows.append((label.lower(), tuple(None if c == "--" else int(c) for c in cells)))
    order = [label for label, _ in rows]
    if (len(order) < 3 or order[:2] != ["t/d", "control"] or order[-1] != "bottom"
            or any(label != "master" for label in order[2:-1])):
        raise ChartError("the rows must be T/D, Control, any Master rows, then Bottom", index)

    layout = "legacy" if legacy else "tools"
    metadata = tuple((label, fields[label]) for label in (KEY_SYSTEM, CORE, DATE)
                     if label in fields)
    return Chart(layout, fields[SYSTEM], control, tuple(keys), tuple(rows), metadata)


def parse_charts(text):
    """Every chart in a file's text, or ChartError saying which chart and line."""
    return [parse_chart(start, lines, index)
            for index, (start, lines) in enumerate(split_charts(text), 1)]
