"""Writing pinning charts in the tools' layout (docs/designs/core-pinning.md, "The chart layout").

The reader is charts.py and these two agree: its labels are the ones used here, and a
test reads back what this writes. A chart is key data, since its pin sizes give the
bittings away, so nothing here puts one anywhere but in the text it returns.
"""
from . import charts

SEPARATOR = "-" * 40       # between charts that share a page; the reader accepts three or more
LABEL_WIDTH = 7            # row labels are padded to this, then each cell is right-aligned in 3


def bitting_text(cuts):
    return "".join(map(str, cuts))


def core_label(core, change):
    """The `Core` line: the core's name, and the key too when the core stands for several
    (every unit core, or a core with more than one change key), so that a chart says which
    door it is for."""
    if core["is_unit"] or len(core["changes"]) > 1:
        return f"{core['name']} ({change})"
    return core["name"]


def format_chart(key_system, system, core, date, control, keys, chambers):
    """One chart as text, ending in a newline.

    key_system  the name of the key system, or None to leave the line out
    system      the pinning system's name ("A2")
    core        the `Core` line (see core_label)
    date        the ISO date to print
    control     the control key's cuts
    keys        (name, cuts) for every operating key, change key first
    chambers    one pinning.Chamber per position
    """
    def title(label):
        return label.title()

    header = []
    if key_system:
        header.append(f"{title(charts.KEY_SYSTEM)} = {key_system}")
    header += [f"{title(charts.SYSTEM)} = {system}",
               f"{title(charts.CORE)} = {core}",
               f"{title(charts.DATE)} = {date}",
               f"{title(charts.CONTROL_KEY)} = {bitting_text(control)}"]
    header += [f"{name} = {bitting_text(cuts)}" for name, cuts in keys]

    driver, control_row, master, bottom = (title(label) for label in charts.ROW_LABELS)
    layers = max((len(c.masters) for c in chambers), default=0)
    rows = [(driver, [c.driver for c in chambers]),
            (control_row, [c.control for c in chambers])]
    # Master pins fill from the bottom: the highest layer is printed first, and a chamber
    # with fewer pins shows `--` there.
    for layer in reversed(range(layers)):
        rows.append((master, [c.masters[layer] if layer < len(c.masters) else None
                              for c in chambers]))
    rows.append((bottom, [c.bottom for c in chambers]))

    body = [label.ljust(LABEL_WIDTH) + "".join(f"{'--' if cell is None else cell:>3}"
                                                for cell in cells)
            for label, cells in rows]
    return "\n".join(header + [""] + body) + "\n"


def join_charts(texts):
    """Several charts (each ending in a newline) as one text, with a blank line, a line of
    dashes and a blank line between them."""
    return ("\n" + SEPARATOR + "\n\n").join(texts)


DRAWING_TITLE = "Stacks (to scale, one line per increment)"   # the reader skips from `Stacks`
CELL = "+---+"             # a joint; a pin's walls are |   | and its size sits in the middle
RULER_GAP = 2              # spaces between the height and the cut ruler, and after it


def _wall_or_joint(chamber, joints, height):
    """One chamber's cell at one line: a joint, or the wall of the pin that spans the line."""
    if height in joints:
        # A bottom pin of 0 or 1 has no line inside it, so its size is written on the
        # joint at its top (for 0, the floor): a number on a joint line is always that.
        low = chamber.bottom if chamber.bottom <= 1 and height == chamber.bottom else None
        return "+" + (CELL[1:-1] if low is None else f"{low:-^3}") + "+"
    reached = 0
    for pin in chamber.pins:
        if reached < height < reached + pin:
            middle = reached + (pin + 1) // 2
            return "|" + (f"{pin:^3}" if height == middle else "   ") + "|"
        reached += pin
    raise ValueError(f"line {height} is outside the stack")


def draw_stacks(system, chambers):
    """The pin stacks of a core as text, to scale, ending in a newline.

    One column per chamber with the driver at the top, and one line for each increment
    of the stack, so every column ends on the same top line. The ruler gives the height
    of each line and, where a key's cut can put a joint on a shear line, that cut: a
    joint at height h from 0 to the deepest cut is on the operating shear line for the
    key cut h, and from the control offset up it is on the control shear line for the
    control key cut h minus the offset (the geometry of lock.Lock).

    system    the pinning.PinningSystem
    chambers  one pinning.Chamber per position
    """
    total, deepest = system.stack_total, system.depths - 1
    offset = system.control_offset
    if any(sum(chamber.pins) != total for chamber in chambers):
        raise ValueError(f"every chamber must add up to the stack total, {total}")
    height_width, cut_width = len(str(total)), len(str(deepest))

    def band(height):
        """The cuts a joint at this height serves: operating, control, or (if the two
        ranges overlap, which no registered system does) both."""
        parts = []
        if height <= deepest:
            parts.append(f"op  {height:>{cut_width}}")
        if offset <= height <= offset + deepest:
            parts.append(f"ctl {height - offset:>{cut_width}}")
        return " ".join(parts)

    bands = {height: band(height) for height in range(total + 1)}
    ruler_width = height_width + RULER_GAP + max(map(len, bands.values())) + RULER_GAP

    def ruler(height):
        return f"{height:>{height_width}}{' ' * RULER_GAP}{bands[height]}".ljust(ruler_width)

    joints = [set(chamber.boundaries) | {0, total} for chamber in chambers]
    lines = [DRAWING_TITLE, "",
             ((" " * (height_width + RULER_GAP) + "cut").ljust(ruler_width)
              + " ".join(f"{number:^{len(CELL)}}" for number in range(1, len(chambers) + 1)))]
    for height in range(total, -1, -1):
        cells = [_wall_or_joint(chamber, chamber_joints, height)
                 for chamber, chamber_joints in zip(chambers, joints)]
        lines.append(ruler(height) + " ".join(cells))
    lines += ["",
              "At a line marked op N, a joint is on the operating shear line for a key cut N.",
              "At a line marked ctl N, a joint is on the control shear line for a control key "
              "cut N.",
              "A number on a joint line is a bottom pin of 0 or 1, too short to hold its size."]
    return "\n".join(line.rstrip() for line in lines) + "\n"
