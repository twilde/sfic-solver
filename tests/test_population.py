"""The population of undecoded unit keys, checked against brute force over three pins."""
import itertools

import pytest

from sfic_solver import model, pinning
from sfic_solver.config import parse_config
from sfic_solver.pinning import A2, PinningError, pin_core
from sfic_solver.population import (false_key_share, pinnable_cuts, pinnable_fraction,
                                    pinnable_sets, retired_population)

ALL = [k for k in itertools.product(range(10), repeat=3)]


def system(**changes):
    raw = {"pins": 3, "max_step": 5, "unit_prefix": "unit:", "pinning": "A2",
           "keys": {"master": "357", "unit:1": "571"},
           "retired_keys": {"old_master": "135", "old_control": "246",
                            "area_master": "792", "area_control": "880"},
           "control_keys": {"control": "468"},
           "cores": [{"name": "Units", "change": "unit:*", "masters": ["master"],
                      "control": "control"}],
           "retired_cores": [{"name": "Original", "change": "unit:*", "masters": ["old_master"],
                              "control": "old_control"}]}
    raw.update(changes)
    return parse_config(raw)


def can_pin(operating, control):
    try:
        pin_core(A2, operating, control)
    except PinningError:
        return False
    return True


def gap_rule(cut, others, control):
    """The gap rule, written out separately from the pinner: the distinct operating cuts
    and the control cut plus 10 are each at least 2 apart."""
    heights = sorted({cut, *others} | {control + 10})
    return all(b - a >= 2 for a, b in zip(heights, heights[1:]))


def test_pinnable_cuts_follow_the_gap_rule_written_out_separately():
    for others, control in itertools.product([[], [0], [4], [4, 7], [9]], range(10)):
        expected = tuple(d for d in range(10) if gap_rule(d, others, control))
        assert pinnable_cuts(A2, range(10), others, control) == expected


def test_pinnable_sets_apply_the_gap_rule_at_every_position():
    sets = pinnable_sets(A2, [range(10)] * 3, [(4, 4, 4)], (3, 9, 0))
    for position, control in enumerate((3, 9, 0)):
        assert sets[position] == tuple(d for d in range(10) if gap_rule(d, [4], control))
    assert 9 not in pinnable_sets(A2, [range(10)] * 3, [(4, 4, 9)], (3, 9, 0))[2]


def test_the_retired_population_is_what_could_have_been_pinned_in_a_retired_core():
    cfg = system()
    population = retired_population(cfg)
    master, control = cfg.retired_keys["old_master"], cfg.retired_keys["old_control"]
    expected = {k for k in ALL if cfg.space.macs_ok(k) and can_pin([k, master], control)}
    assert cfg.space.population_size(population) == len(expected) > 0
    assert {k for k in ALL if cfg.space.population_contains(population, k)} == expected


def test_several_covering_retired_cores_give_the_union():
    cfg = system(retired_cores=[
        {"name": "A", "change": "unit:*", "masters": ["old_master"], "control": "old_control"},
        {"name": "B", "change": ["unit:1*"], "masters": ["area_master"],
         "control": "area_control"}])
    population = retired_population(cfg)
    keys = cfg.retired_keys

    def fits(k, master, control):
        return can_pin([k, keys[master]], keys[control])

    expected = {k for k in ALL if cfg.space.macs_ok(k)
                and (fits(k, "old_master", "old_control") or fits(k, "area_master", "area_control"))}
    assert {k for k in ALL if cfg.space.population_contains(population, k)} == expected
    assert cfg.space.population_size(population) == len(expected)


def test_a_retired_core_that_covers_no_unit_keys_gives_no_population():
    cfg = system(retired_cores=[{"name": "A", "change": "area_master", "masters": ["old_master"],
                                 "control": "old_control"}])
    assert retired_population(cfg) is None


def test_no_pinning_and_no_retired_cores_give_no_population():
    assert retired_population(system(retired_cores=[])) is None
    raw_cfg = system()
    raw_cfg.pinning = None
    assert retired_population(raw_cfg) is None


def test_an_impossible_description_is_an_error():
    # A control cut of 0 with the master's 9 at every position: no key can sit beside both.
    cfg = system(retired_keys={"old_master": "999", "old_control": "000",
                               "area_master": "792", "area_control": "880"})
    with pytest.raises(ValueError, match="no valid bitting could have been pinned"):
        retired_population(cfg)


def test_the_pinnable_fraction_is_counted_within_the_population():
    cfg = system()
    population = retired_population(cfg)
    master, control = cfg.keys["master"], cfg.control_keys["control"]
    valid = [k for k in ALL if cfg.space.population_contains(population, k)]
    pinnable = [k for k in valid if can_pin([k, master], control)]
    assert pinnable_fraction(cfg.space, population, A2, [master], control) == \
        pytest.approx(len(pinnable) / len(valid), rel=1e-12)
    # With no masters only the control key matters.
    pinnable = [k for k in valid if can_pin([k], control)]
    assert pinnable_fraction(cfg.space, population, A2, [], control) == \
        pytest.approx(len(pinnable) / len(valid), rel=1e-12)


def test_the_pinnable_fraction_of_the_uniform_population_is_over_every_valid_key():
    cfg = system()
    master, control = cfg.keys["master"], cfg.control_keys["control"]
    valid = [k for k in ALL if cfg.space.macs_ok(k)]
    pinnable = [k for k in valid if can_pin([k, master], control)]
    assert pinnable_fraction(cfg.space, cfg.space.uniform(), A2, [master], control) == \
        pytest.approx(len(pinnable) / len(valid), rel=1e-12)


def test_the_false_key_share_leaves_out_the_intended_keys():
    cfg = system()
    population = retired_population(cfg)
    intended = [(5, 7, 1), cfg.keys["master"]]
    options = model.options_for(intended[0], [intended[1]])
    accepted = [k for k in ALL if cfg.space.population_contains(population, k)
                and model.operates(k, options) and k not in {tuple(i) for i in intended}]
    valid = sum(1 for k in ALL if cfg.space.population_contains(population, k))
    assert false_key_share(cfg.space, population, options, intended) == \
        pytest.approx(len(accepted) / valid, rel=1e-12)


def test_a_pinning_system_other_than_a2_is_used_as_given(monkeypatch):
    from dataclasses import replace
    narrow = replace(pinning.A2, name="NARROW", other_pins=(4, 19))
    monkeypatch.setitem(pinning.SYSTEMS, "NARROW", narrow)
    assert pinnable_cuts(narrow, range(10), [4], 3) != pinnable_cuts(A2, range(10), [4], 3)
