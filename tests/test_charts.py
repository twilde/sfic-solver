"""Reading pinning charts: both layouts, and errors that never quote the chart."""
import re

import pytest

from conftest import FIXTURES
from sfic_solver.charts import ChartError, parse_charts

TOOLS = (FIXTURES / "charts" / "tools_layout.txt").read_text()
LEGACY = (FIXTURES / "charts" / "legacy_layout.txt").read_text()

ROWS = """T/D      4  6  9 10  5  8  9
Control 12  8  8  8 12  6  8
Master  --  2  4 --  2  2 --
Master   2  4  2  4  2  4  2
Bottom   5  3  0  1  2  3  4"""
TOOLS_HEADER = """Key System = Example building
System = A2
Core = Area A cores
Date = 2026-10-01
Control Key = 9743854
area_a = 5721276
master_sub = 7305496
master_top = 5961634"""
LEGACY_HEADER = """System = A2
Control Key = 9743854
Master Key = 5961634
Change Keys = 5721276, 9565698"""


def chart(header, rows=ROWS):
    return f"{header}\n\n{rows}\n"


def test_the_tools_layout_is_read():
    charts = parse_charts(TOOLS)
    assert [c.layout for c in charts] == ["tools"] * 3
    first = charts[0]
    assert first.system == "A2" and first.control == "9743854"
    assert first.keys == (("area_a", "5721276"), ("master_sub", "7305496"),
                          ("master_top", "5961634"))
    assert dict(first.metadata) == {"key system": "Example building",
                                    "core": "Area A cores", "date": "2026-10-01"}
    assert [label for label, _ in first.rows] == ["t/d", "control", "master", "master", "bottom"]
    assert first.rows[2][1] == (None, 2, 4, None, 2, 2, None)
    assert first.chambers == 7


def test_the_legacy_layout_is_read_with_every_change_key_an_operating_key():
    charts = parse_charts(LEGACY)
    assert [c.layout for c in charts] == ["legacy"] * 3
    assert [len(c.keys) for c in charts] == [3, 2, 4]          # master plus the change keys
    assert [b for _, b in charts[0].keys] == ["5961634", "5721276", "9565698"]
    assert charts[0].metadata == ()                            # the old charts carry none


def test_charts_are_separated_by_dashes_and_the_fake_line_is_skipped():
    assert len(parse_charts(TOOLS)) == 3
    assert len(parse_charts(chart(TOOLS_HEADER) + "\n---\n\n" + chart(LEGACY_HEADER))) == 2
    assert parse_charts("") == [] and parse_charts("FAKE only\n") == []


@pytest.mark.parametrize("drop, keys", [
    ("Master Key = 5961634\n", ["5721276", "9565698"]),
    ("\nChange Keys = 5721276, 9565698", ["5961634"]),
])
def test_a_legacy_chart_may_have_only_a_master_key_or_only_change_keys(drop, keys):
    parsed = parse_charts(chart(LEGACY_HEADER.replace(drop, "")))[0]
    assert parsed.layout == "legacy" and [b for _, b in parsed.keys] == keys


def test_a_colon_may_separate_a_label_from_its_value():
    colons = (LEGACY_HEADER.replace("System =", "System:").replace("Control Key =", "Control Key:")
              .replace("Master Key =", "Master Key:").replace("Change Keys =", "Change Keys:"))
    parsed = parse_charts(chart(colons))[0]
    assert parsed.layout == "legacy" and [b for _, b in parsed.keys] == [
        "5961634", "5721276", "9565698"]
    assert parsed.control == "9743854"


@pytest.mark.parametrize("line", ["unit:101 = 3101658", "unit:101: 3101658", "unit:101 : 3101658"])
def test_a_key_name_may_contain_a_colon_whichever_separator_is_used(line):
    header = TOOLS_HEADER + "\n" + line
    keys = dict(parse_charts(chart(header))[0].keys)
    assert keys["unit:101"] == "3101658"


@pytest.mark.parametrize("separator", ["=", ":"])
def test_a_reserved_label_keeps_colons_that_follow_it_in_the_value(separator):
    header = TOOLS_HEADER.replace("Core = Area A cores", f"Core {separator} Unit cores (unit:101)")
    header = header.replace("Date = 2026-10-01", f"Date {separator} 2026-10-01 12:30")
    parsed = parse_charts(chart(header))[0]
    assert dict(parsed.metadata)["core"] == "Unit cores (unit:101)"
    assert dict(parsed.metadata)["date"] == "2026-10-01 12:30"


def test_a_key_name_that_starts_like_a_label_is_still_a_key():
    from sfic_solver.charts import split_header_line
    assert split_header_line("system_b: 5961634") == ("system_b", "5961634")
    assert split_header_line("Cores = 5961634") == ("Cores", "5961634")
    assert split_header_line("Key System: Example building") == ("Key System", "Example building")


def test_split_header_line_edge_cases():
    from sfic_solver.charts import split_header_line
    assert split_header_line("Change Keys = 1, 2") == ("Change Keys", "1, 2")
    assert split_header_line("Change Keys: 1, 2") == ("Change Keys", "1, 2")
    assert split_header_line("a = b: c") == ("a", "b: c")           # '=' wins over a later ':'
    assert split_header_line("just words") is None
    assert split_header_line("= 5") is None and split_header_line(": 5") is None


def test_a_byte_order_mark_is_ignored():
    parsed = parse_charts("\ufeff" + chart(LEGACY_HEADER))
    assert [len(c.keys) for c in parsed] == [3] and parsed[0].system == "A2"


def test_labels_ignore_case_and_spacing():
    shouty = (LEGACY_HEADER.replace("System", "SYSTEM").replace("Control Key", "control key")
              .replace("Change Keys =", "  change keys   =   "))
    parsed = parse_charts(chart(shouty).replace("T/D", "t/d").replace("Bottom", "BOTTOM"))
    assert parsed[0].layout == "legacy" and len(parsed[0].keys) == 3


def test_column_reads_pins_from_the_bottom_up():
    first = parse_charts(TOOLS)[0]
    assert first.column(0) == (5, 2, 12, 4)            # bottom, one master, control, driver
    assert first.column(1) == (3, 4, 2, 8, 6)


def test_column_is_none_when_masters_do_not_fill_from_the_bottom():
    wrong = ROWS.replace("Master  --  2  4 --  2  2 --\nMaster   2  4  2  4  2  4  2",
                         "Master   2  2  4  4  2  2  2\nMaster  --  4  2 --  2  4 --")
    parsed = parse_charts(chart(TOOLS_HEADER, wrong))[0]
    assert parsed.column(0) is None and parsed.column(1) is not None


@pytest.mark.parametrize("text, reason", [
    (chart(TOOLS_HEADER).replace("System = A2\n", ""), "no System line"),
    (chart(TOOLS_HEADER).replace("Control Key = 9743854\n", ""), "no Control Key line"),
    (chart("System = A2\nControl Key = 9743854"), "no operating keys"),
    (chart(TOOLS_HEADER + "\nMaster Key = 5961634\nChange Keys = 5721276"),
     "mixes the tools' layout"),
    (chart(LEGACY_HEADER.replace("Master Key = 5961634\n", "")
           .replace("Change Keys = 5721276, 9565698", "Change Keys =")),
     "no operating keys"),
    (chart(TOOLS_HEADER + "\nCore = again"), "a header label is repeated"),
    (chart(TOOLS_HEADER + "\nnot a header line"), "not `label = value`"),
    (chart(TOOLS_HEADER + "\nowner = somebody"), "neither a known label nor `name = bitting`"),
    (chart(TOOLS_HEADER.replace("5961634", "596163")), "digits and as long as the control key"),
    (chart(TOOLS_HEADER, ROWS.replace("T/D", "Top")), "does not start with T/D"),
    (chart(TOOLS_HEADER, ROWS.replace("  9\nControl", "\nControl")), "one number (or --) per chamber"),
    (chart(TOOLS_HEADER, ROWS.replace("Bottom   5  3  0  1  2  3  4", "")), "must be T/D, Control"),
    (chart(TOOLS_HEADER, "\n".join([ROWS.splitlines()[i] for i in (0, 2, 1, 3, 4)])),
     "must be T/D, Control"),
    (TOOLS_HEADER + "\n" + ROWS, "no blank line between the header and the rows"),
])
def test_unreadable_charts_are_refused_with_a_reason(text, reason):
    with pytest.raises(ChartError, match=re.escape(reason)):
        parse_charts(text)


DRAWING = """Stacks (to scale, one line per increment)

      cut    1     2
23         +---+ +---+
 1  op  1  |   | |   |
 0  op  0  +---+ +---+

At a line marked op N, a joint is on the operating shear line for a key cut N."""


def test_a_drawing_after_the_rows_is_skipped():
    plain = parse_charts(chart(TOOLS_HEADER, ROWS))
    drawn = parse_charts(chart(TOOLS_HEADER, ROWS + "\n\n" + DRAWING))
    assert drawn == plain
    legacy = parse_charts(chart(LEGACY_HEADER, ROWS))
    assert parse_charts(chart(LEGACY_HEADER, ROWS + "\n\n" + DRAWING)) == legacy


def test_a_drawing_ends_at_the_next_separator_and_the_next_chart_is_read():
    text = (chart(TOOLS_HEADER, ROWS + "\n\n" + DRAWING) + "\n----------------------------------------\n\n"
            + chart(TOOLS_HEADER.replace("Area A", "Area B"), ROWS))
    first, second = parse_charts(text)
    assert dict(first.metadata)["core"] == "Area A cores"
    assert dict(second.metadata)["core"] == "Area B cores"


def test_rows_before_a_drawing_are_still_checked():
    with pytest.raises(ChartError, match="must be T/D, Control"):
        parse_charts(chart(TOOLS_HEADER, ROWS.replace("Bottom   5  3  0  1  2  3  4", "")
                           + "\n\n" + DRAWING))


def test_a_key_named_stacks_is_still_a_key():
    """The drawing starts only after the rows: in the header `Stacks` is a name like any."""
    header = TOOLS_HEADER + "\nStacks = 5961634"
    keys = parse_charts(chart(header, ROWS + "\n\n" + DRAWING))[0].keys
    assert ("Stacks", "5961634") in keys


@pytest.mark.parametrize("digit", ["\u00b2", "\u0663", "\uff13"])    # ², ٣, full-width 3
def test_only_ascii_digits_are_digits(digit):
    """str.isdigit and \\d accept these; int() then raises with the character in its message."""
    bad_header = TOOLS_HEADER.replace("5961634", f"596163{digit}")
    bad_control = TOOLS_HEADER.replace("9743854", f"974385{digit}")
    bad_cell = ROWS.replace("T/D      4", f"T/D      {digit}")
    for text in (chart(bad_header), chart(bad_control), chart(TOOLS_HEADER, bad_cell)):
        with pytest.raises(ChartError) as caught:
            parse_charts(text)
        assert digit not in str(caught.value)


def test_errors_say_where_and_never_quote_the_chart():
    secret = "owner = 5555555\nnonsense about 7777777"
    with pytest.raises(ChartError) as caught:
        parse_charts(chart(LEGACY_HEADER) + "\n---\n\n" + chart(TOOLS_HEADER + "\n" + secret))
    message = str(caught.value)
    assert caught.value.chart == 2 and caught.value.line is not None
    assert message.startswith("chart 2, line ")
    assert not any(token in message for token in ("5555555", "7777777", "5721276", "9743854"))
