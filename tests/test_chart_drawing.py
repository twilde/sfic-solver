"""The drawing of a core's pin stacks: it must be right, not only look right.

The tests read a drawing back (joints, pins, ruler) and compare it with the chambers it
was made from, and the ruler with the simulated lock's own geometry.
"""
import random
import re

import pytest

from conftest import FIXTURES, ROOT, run_script
from sfic_solver import charts, chartwriter
from sfic_solver.check_charts import check_chart
from sfic_solver.chartwriter import draw_stacks
from sfic_solver.lock import CONTROL, OPERATING, Lock
from sfic_solver.pinning import A2, Chamber, PinningSystem, pin_chamber, pin_chambers

PINNING = FIXTURES / "pinning.json"
DATE = "2026-10-01"
DESIGN = ROOT / "docs" / "designs" / "ascii-stack-drawing.md"
SEPARATOR = "-" * 40
CELL, STEP = 5, 6              # a chamber's cell is 5 wide, and the next starts 6 on
HEADER_LINES = 3               # title, blank line, the numbers of the chambers
SMALL = PinningSystem("TEST", 0.01, depths=4, stack_total=12, bottom_pins=(0, 3),
                      other_pins=(2, 8), control_offset=5)


def printed(*extra):
    proc = run_script("pin_system", PINNING, "--date", DATE, *extra)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def read_back(system, text):
    """What a drawing says: ([each chamber's pins, bottom first], [(height, ruler)]).

    The pins come from the joints, and the sizes written in the pins and on the floor
    are checked against them on the way, so a drawing whose numbers disagree with its
    joints fails here.
    """
    lines = text.splitlines()[HEADER_LINES:HEADER_LINES + system.stack_total + 1]
    start = lines[0].index("+")
    ruler = [(int(line[:start].split()[0]), " ".join(line[:start].split()[1:]))
             for line in lines]
    assert [height for height, _ in ruler] == list(range(system.stack_total, -1, -1))
    count = (len(lines[0]) - start + 1) // STEP
    pins = []
    for chamber in range(count):
        column = [(height, line[start + STEP * chamber:start + STEP * chamber + CELL])
                  for (height, _), line in zip(ruler, lines)]
        assert all(cell[0] == cell[-1] and cell[0] in "+|" for _, cell in column)
        joints = [height for height, cell in column if cell[0] == "+"][::-1]
        assert joints[0] == 0 and joints[-1] == system.stack_total
        sizes = [high - low for low, high in zip(joints, joints[1:])]
        cells = dict(column)
        for low, high in zip(joints, joints[1:]):
            written = [cells[h][1:4].strip() for h in range(low + 1, high)]
            if high - low >= 2:
                assert written.count(str(high - low)) == 1
                assert written[(high - low - 1) // 2] == str(high - low)   # the middle line
                assert sum(1 for text in written if text) == 1
            else:
                assert written == []
        floor = cells[0][1:4].strip("-")
        if floor:                      # a bottom pin of 0: the floor is itself a joint
            assert floor == "0"
            sizes.insert(0, 0)
        on_a_joint = {h: cell[1:4].strip("-") for h, cell in column
                      if cell[0] == "+" and h and cell[1:4].strip("-")}
        if sizes[0] == 1:              # a bottom pin of 1 is written on the joint above it
            assert on_a_joint == {1: "1"}
        else:
            assert on_a_joint == {}
        pins.append(tuple(sizes))
    return pins, ruler


def random_chambers(rng, count=3):
    """The chambers of a random core, or None when it cannot be pinned."""
    keys = [tuple(rng.randrange(10) for _ in range(count)) for _ in range(rng.randint(1, 4))]
    control = tuple(rng.randrange(10) for _ in range(count))
    chambers, errors = pin_chambers(A2, keys, control)
    return None if errors else chambers


def test_the_drawing_in_the_design_document_is_what_the_command_prints():
    block = re.search(r"```\n(Key System = .*?)```", DESIGN.read_text(), re.S).group(1)
    assert printed("--draw").startswith(block)


def test_every_drawing_of_the_fixture_reads_back_to_its_chart():
    texts = printed("--draw").split("\n" + SEPARATOR + "\n\n")
    assert len(texts) == 8
    for text in texts:
        chart = charts.parse_charts(text)[0]
        pins, _ = read_back(A2, text[text.index("Stacks"):])
        assert pins == [chart.column(i) for i in range(chart.chambers)]


def test_random_pinnable_cores_read_back_to_their_chambers():
    rng, cores = random.Random(21), 0
    while cores < 300:
        chambers = random_chambers(rng)
        if chambers is not None:
            cores += 1
            assert read_back(A2, draw_stacks(A2, chambers))[0] == [c.pins for c in chambers]


@pytest.mark.parametrize("operating, control, bottom", [
    ([0, 4], 3, 0),        # the lowest cut is 0: no bottom pin, the floor is a joint
    ([1, 6], 3, 1),        # a bottom pin of 1 has no line inside it
    ([2, 5], 3, 2),        # a bottom pin of 2 has one
    ([9], 4, 9),
])
def test_a_short_bottom_pin_is_written_on_its_joint(operating, control, bottom):
    chamber = pin_chamber(A2, operating, control)
    assert chamber.bottom == bottom
    text = draw_stacks(A2, [chamber])
    assert read_back(A2, text)[0] == [chamber.pins]
    assert ("+-0-+" in text) == (bottom == 0)
    assert ("+-1-+" in text) == (bottom == 1)


def test_the_ruler_puts_each_joint_on_the_line_of_the_cut_that_lifts_it_there():
    """A joint on a line marked `op N` or `ctl N` is what the lock lines up for that cut."""
    rng, checked = random.Random(22), 0
    while checked < 100:
        chambers = random_chambers(rng)
        if chambers is None:
            continue
        checked += 1
        lock = Lock.from_chambers(A2, chambers)
        _, ruler = read_back(A2, draw_stacks(A2, chambers))
        for height, band in ruler:
            if not band:
                assert height > A2.depths - 1 + A2.control_offset
                continue
            name, cut = band.split()
            line = OPERATING if name == "op" else CONTROL
            assert height == int(cut) + (0 if line == OPERATING else A2.control_offset)
            for position, chamber in enumerate(chambers):
                lined_up = lock.joint_on_line(position, int(cut), line) is not None
                assert lined_up == (height in chamber.boundaries), (height, position)


def test_the_ruler_follows_the_pinning_system_it_is_given():
    chamber = pin_chamber(SMALL, [0, 2], 1)
    text = draw_stacks(SMALL, [chamber])
    pins, ruler = read_back(SMALL, text)
    assert pins == [chamber.pins] and len(ruler) == SMALL.stack_total + 1
    assert [band for _, band in ruler if band.startswith("op")] == [
        "op 3", "op 2", "op 1", "op 0"]
    assert [band for _, band in ruler if band.startswith("ctl")] == [
        "ctl 3", "ctl 2", "ctl 1", "ctl 0"]
    lock = Lock.from_chambers(SMALL, [chamber])
    for height, band in ruler:
        if band:
            name, cut = band.split()
            line = OPERATING if name == "op" else CONTROL
            assert (lock.joint_on_line(0, int(cut), line) is not None) == (
                height in chamber.boundaries)


def test_a_line_that_serves_both_shear_lines_says_so():
    overlapping = PinningSystem("TEST", 0.01, depths=6, stack_total=14, bottom_pins=(0, 5),
                                other_pins=(2, 9), control_offset=3)
    chamber = pin_chamber(overlapping, [0, 3], 3)
    text = draw_stacks(overlapping, [chamber])
    assert read_back(overlapping, text)[0] == [chamber.pins]
    bands = {height: band for height, band in read_back(overlapping, text)[1]}
    assert bands[4] == "op 4 ctl 1" and bands[2] == "op 2" and bands[8] == "ctl 5"
    assert bands[9] == "" and bands[3] == "op 3 ctl 0"


def test_the_drawing_is_plain_ascii_without_trailing_spaces_and_fits_its_columns():
    out = printed("--draw")
    assert out.isascii() and not re.search(r" $", out, re.M)
    drawing = draw_stacks(A2, pin_chambers(A2, [(5, 7, 2)], (9, 9, 9))[0])
    grid = drawing.splitlines()[HEADER_LINES:HEADER_LINES + A2.stack_total + 1]
    # 11 columns for the ruler, then 5 for the first chamber and 6 for each after it
    assert max(len(line) for line in grid) == 11 + CELL + STEP * 2


def test_without_the_flag_the_output_has_no_drawing():
    assert "Stacks" not in printed()


def test_with_the_flag_each_chart_is_followed_by_its_drawing_and_nothing_else_changes():
    plain = printed().split("\n" + SEPARATOR + "\n\n")
    drawn = printed("--draw").split("\n" + SEPARATOR + "\n\n")
    assert len(plain) == len(drawn) == 8
    for text, with_drawing in zip(plain, drawn):
        assert with_drawing.startswith(text + "\n" + chartwriter.DRAWING_TITLE + "\n")
        assert with_drawing.count("Stacks") == 1


def test_the_reader_and_checker_accept_every_drawn_chart_and_read_what_was_printed():
    drawn = charts.parse_charts(printed("--draw"))
    assert drawn == charts.parse_charts(printed())
    assert all(check_chart(chart) == [] for chart in drawn)


def test_the_title_is_what_the_reader_skips_from():
    assert chartwriter.DRAWING_TITLE.lower().startswith(charts.DRAWING)


def test_chambers_that_do_not_add_up_to_the_stack_are_refused_not_drawn_wrongly():
    short = Chamber(bottom=2, masters=(), control=10, driver=9)      # adds up to 21, not 23
    with pytest.raises(ValueError, match="stack total"):
        draw_stacks(A2, [short])
