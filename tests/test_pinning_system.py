"""The pinning system record and its registry."""
import dataclasses

import pytest

from sfic_solver import pinning


def test_a2_matches_the_rules_in_the_design():
    a2 = pinning.A2
    assert (a2.name, a2.increment, a2.depths, a2.stack_total) == ("A2", 0.0125, 10, 23)
    assert a2.bottom_pins == (0, 9)
    assert a2.other_pins == (2, 19)
    assert a2.control_offset == 10


def test_a2_control_offset_is_the_shear_line_gap_in_increments():
    # The control shear line is 0.125 inch beyond the operating one.
    assert pinning.A2.control_offset * pinning.A2.increment == pytest.approx(0.125)


def test_systems_are_found_by_name_in_any_case():
    assert pinning.get_system("A2") is pinning.A2
    assert pinning.get_system("a2") is pinning.A2


@pytest.mark.parametrize("name", ["A5", "", "A 2", None, 2])
def test_unknown_system_names_list_the_known_ones(name):
    with pytest.raises(ValueError, match="unknown pinning system .*known systems: A2"):
        pinning.get_system(name)


def test_a_system_is_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        pinning.A2.stack_total = 24


@pytest.mark.parametrize("change, message", [
    ({"bottom_pins": (5, 2)}, "bottom_pins must be"),
    ({"other_pins": (-1, 9)}, "other_pins must be"),
    ({"depths": 0}, "depths and control_offset must be at least 1"),
    ({"control_offset": 0}, "depths and control_offset must be at least 1"),
    ({"stack_total": 19}, "must be below the stack total"),
])
def test_a_malformed_system_is_refused(change, message):
    with pytest.raises(ValueError, match=message):
        dataclasses.replace(pinning.A2, **change)
