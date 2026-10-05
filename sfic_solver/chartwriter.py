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
