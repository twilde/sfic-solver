"""The pinner: cuts in, pins out, checked against rules written out independently."""
import itertools
import random

import pytest

from sfic_solver import pinning
from sfic_solver.pinning import A2, Chamber, PinningError, pin_chamber, pin_chambers, pin_core
from helpers import example_charts


def test_the_ledgers_worked_example():
    # Master cut 1, change key cut 5, control cut 3: pins 1, 4, 8 and 10.
    chamber = pin_chamber(A2, [1, 5], 3)
    assert chamber == Chamber(bottom=1, masters=(4,), control=8, driver=10)
    assert chamber.pins == (1, 4, 8, 10)


def test_design_document_example_chamber():
    assert pin_chamber(A2, [3, 7], 5).pins == (3, 4, 8, 8)


def test_keys_that_share_a_cut_share_a_boundary():
    # Two keys with cut 6 and control cut 4: no master pin, so three pins in all.
    chamber = pin_chamber(A2, [6, 6], 4)
    assert chamber.pins == (6, 8, 9)


def test_order_and_duplicates_of_operating_keys_do_not_matter():
    assert pin_chamber(A2, [9, 1, 5, 1], 3) == pin_chamber(A2, [5, 9, 1], 3)
    assert pin_chamber(A2, [9, 1, 5], 3).masters == (4, 4)


def test_boundaries_are_the_partial_sums():
    assert pin_chamber(A2, [1, 5], 3).boundaries == (1, 5, 13)


@pytest.mark.parametrize("operating, control, reason", [
    ([4, 5], 3, "operating cuts 4 and 5 are 1 apart"),
    ([2, 9], 0, "control cut 0 puts the control boundary 1 above the highest operating cut 9"),
])
def test_unpinnable_chambers_say_why(operating, control, reason):
    with pytest.raises(PinningError, match=reason):
        pin_chamber(A2, operating, control)


def test_pin_core_reports_the_chamber():
    with pytest.raises(PinningError) as caught:
        pin_core(A2, [(1, 2, 3), (1, 3, 3)], (4, 4, 4))   # chamber 2: cuts 2 and 3 are 1 apart
    assert caught.value.chamber == 2
    assert caught.value.reason.startswith("operating cuts 2 and 3 are 1 apart")
    assert str(caught.value).startswith("chamber 2: ")


def test_pin_chambers_reports_every_chamber_that_fails_and_pins_the_rest():
    # Chambers 2 and 3 have cuts 1 apart; chamber 1 is fine.
    chambers, errors = pin_chambers(A2, [(1, 2, 3), (1, 3, 4)], (4, 4, 4))
    assert [e.chamber for e in errors] == [2, 3]
    assert chambers[0] == pin_chamber(A2, [1, 1], 4)
    assert chambers[1] is None and chambers[2] is None
    assert pin_chambers(A2, [(1, 2, 3)], (4, 4, 4))[1] == []


@pytest.mark.parametrize("operating, control", [
    ([], 3), ([1, 10], 3), ([1, -1], 3), ([1, 2.0], 3), ([True], 3), ([1], 10),
])
def test_cuts_outside_the_system_are_a_usage_error_not_a_pinning_error(operating, control):
    with pytest.raises(ValueError) as caught:
        pin_chamber(A2, operating, control)
    assert not isinstance(caught.value, PinningError)


def test_pin_core_needs_keys_of_one_length():
    with pytest.raises(ValueError, match="same number of cuts"):
        pin_core(A2, [(1, 2, 3), (1, 2)], (4, 4, 4))
    with pytest.raises(ValueError, match="at least one operating key"):
        pin_core(A2, [], (4, 4, 4))


# -- properties, over every small case -------------------------------------------------

def independent_rule(operating, control):
    """The design's rule, written out separately: boundary heights at least 2 apart."""
    heights = sorted(set(operating)) + [control + 10]
    return all(b - a >= 2 for a, b in zip(heights, heights[1:]))


def test_a_chamber_is_pinnable_exactly_when_boundaries_are_two_apart():
    checked = 0
    for count in (1, 2, 3):
        for operating in itertools.combinations(range(10), count):
            for control in range(10):
                try:
                    pin_chamber(A2, operating, control)
                    pinnable = True
                except PinningError:
                    pinnable = False
                assert pinnable == independent_rule(operating, control), (operating, control)
                checked += 1
    assert checked == (10 + 45 + 120) * 10


def test_every_pinned_chamber_follows_the_a2_rules():
    rng = random.Random(5)
    seen_pin_counts = set()
    for _ in range(3000):
        operating = [rng.randrange(10) for _ in range(rng.randint(1, 5))]
        control = rng.randrange(10)
        try:
            chamber = pin_chamber(A2, operating, control)
        except PinningError:
            continue
        pins = chamber.pins
        assert sum(pins) == 23
        assert 0 <= chamber.bottom <= 9
        assert all(2 <= pin <= 19 for pin in pins[1:])
        distinct = len(set(operating))
        assert len(pins) == distinct + 2            # one pin per gap, plus control and driver
        assert 3 <= len(pins) <= len(operating) + 2
        assert chamber.boundaries[:distinct] == tuple(sorted(set(operating)))
        assert chamber.boundaries[-1] == control + 10
        seen_pin_counts.add(len(pins))
    assert seen_pin_counts >= {3, 4, 5, 6}


def test_pin_core_pins_every_position():
    keys = [(5, 7, 2, 1, 2, 7, 6), (7, 3, 0, 5, 4, 9, 6)]
    chambers = pin_core(A2, keys, (9, 7, 4, 3, 8, 5, 4))
    assert len(chambers) == 7
    assert [c.pins for c in chambers][6] == (6, 8, 9)    # the keys share cut 6 here
    assert all(sum(c.pins) == 23 for c in chambers)


# -- the charts in the design document are what the pinner produces --------------------

def chart_columns(rows):
    """Per chamber, the pins from the bottom up, read off a chart's rows."""
    return [tuple(cells[i] for _, cells in reversed(rows) if cells[i] is not None)
            for i in range(len(rows[0][1]))]


def test_the_design_documents_example_charts_are_reproduced():
    charts = example_charts()
    assert charts
    for fields, keys, control, rows in charts:
        chambers = pin_core(A2, [[int(c) for c in k] for k in keys], [int(c) for c in control])
        expected = chart_columns(rows)
        assert [c.pins for c in chambers] == [tuple(col) for col in expected], fields["Core"]
