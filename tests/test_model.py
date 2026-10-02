"""The counting maths, checked against brute-force enumeration."""
import itertools
import random
from fractions import Fraction

import pytest

from sfic_solver import model


def macs(cuts, max_step):
    """Independent MACS check, so the tests don't lean on the code under test."""
    return all(abs(a - b) <= max_step for a, b in zip(cuts, cuts[1:]))


def parity_digits(pattern):
    return [[d for d in range(10) if d % 2 == (0 if c == "E" else 1)] for c in pattern]


def all_valid(pattern, max_step):
    """Every bitting with the right parity and MACS, by enumeration."""
    return [k for k in itertools.product(*parity_digits(pattern)) if macs(k, max_step)]


def test_total_valid_known_value():
    assert model.KeySpace(7, "OOEOEOE", 5).total_valid == 28_384


@pytest.mark.parametrize("pins", [1, 2, 3, 4, 5])
def test_total_valid_matches_brute_force(pins):
    rng = random.Random(1)
    for _ in range(30):
        pattern = "".join(rng.choice("EO") for _ in range(pins))
        max_step = rng.randint(1, 9)
        space = model.KeySpace(pins, pattern, max_step)
        assert space.total_valid == len(all_valid(pattern, max_step))


def test_total_valid_without_pattern_matches_brute_force():
    for max_step in (1, 3, 5, 9):
        brute = sum(1 for k in itertools.product(range(10), repeat=4) if macs(k, max_step))
        assert model.KeySpace(4, None, max_step).total_valid == brute


def test_operating_set_size_matches_brute_force():
    rng = random.Random(2)
    for i in range(150):
        # 1-3 options per pin (up to 3**7 combinations), a few cases with 4.
        top = 4 if i % 25 == 0 else 3
        options = [sorted(rng.sample(range(10), rng.randint(1, top))) for _ in range(7)]
        max_step = rng.randint(1, 9)
        brute = sum(1 for cuts in itertools.product(*options) if macs(cuts, max_step))
        assert model.KeySpace(max_step=max_step).operating_set_size(options) == brute, \
            (options, max_step)


def test_options_for_collects_distinct_cuts_per_pin():
    change = (1, 2, 3, 4, 5, 6, 7)
    master = (1, 9, 3, 0, 5, 0, 7)
    assert model.options_for(change, [master]) == [
        [1], [2, 9], [3], [0, 4], [5], [0, 6], [7]]


def test_operates_requires_every_pin_to_match_an_option():
    options = [[1], [2, 9], [3], [0, 4], [5], [0, 6], [7]]
    assert model.operates((1, 9, 3, 0, 5, 6, 7), options)
    assert not model.operates((1, 9, 3, 0, 5, 6, 8), options)


@pytest.mark.parametrize("pins, cases", [(3, 40), (4, 8)])
def test_pair_conflict_probability_matches_brute_force(pins, cases):
    rng = random.Random(3 + pins)
    for _ in range(cases):
        pattern = "".join(rng.choice("EO") for _ in range(pins))
        max_step = rng.randint(1, 9)
        space = model.KeySpace(pins, pattern, max_step)
        valid = all_valid(pattern, max_step)
        total = space.total_valid
        assert total == len(valid)
        masters = [rng.choice(valid) for _ in range(rng.randint(0, 3))]

        # B operates the core of A when each of B's cuts is A's cut or a master's.
        hits = sum(1 for a in valid for b in valid
                   if all(b[p] == a[p] or any(b[p] == m[p] for m in masters)
                          for p in range(pins)))
        expected = float(Fraction(hits, total ** 2))
        assert space.pair_conflict_probability(masters) == pytest.approx(expected, rel=1e-12)


def test_pair_conflict_probability_without_masters_is_one_over_count():
    # With no masters B must equal A, so the chance is 1 / count_valid.
    for pattern, max_step in [("EOEO", 5), ("EEOE", 2), ("OOOO", 9)]:
        space = model.KeySpace(4, pattern, max_step)
        p = space.pair_conflict_probability([])
        assert p == pytest.approx(1 / space.total_valid, rel=1e-12)


def test_pair_conflict_probability_full_pin_count_sanity():
    space = model.KeySpace(7, "OOEOEOE", 5)
    p0 = space.pair_conflict_probability([])
    assert p0 == pytest.approx(1 / space.total_valid, rel=1e-12)
    master = (0, 1, 2, 3, 4, 5, 6)
    assert space.pair_conflict_probability([master]) > p0


def test_distance_and_macs_and_parity_helpers():
    assert model.distance((1, 2, 3), (1, 5, 6)) == 2
    space = model.KeySpace(3, None, 5)
    assert space.macs_ok((0, 5, 0)) and not space.macs_ok((0, 6, 0))
    assert space.macs_violations((0, 6, 0)) == [1, 2]
    parity = model.KeySpace(7, "EOEOEOE")
    assert parity.parity_bad((0, 1, 2, 3, 4, 5, 6)) == []
    assert parity.parity_bad((1, 1, 2, 3, 4, 5, 7)) == [1, 7]


def test_without_a_pattern_no_cut_has_the_wrong_parity():
    assert model.KeySpace(3).parity_bad((0, 1, 2)) == []


def test_key_space_defaults_are_the_standard_seven_pin_rules():
    space = model.KeySpace()
    assert (space.pins, space.pattern, space.max_step, space.depths) == (7, None, 5, 10)


def test_key_space_rejects_a_pattern_of_the_wrong_length():
    with pytest.raises(ValueError, match="pattern has 3 characters but the key space has 7"):
        model.KeySpace(7, "EOE")


@pytest.mark.parametrize("kwargs, message", [
    ({"pins": 0}, "pins must be a whole number of at least 1"),
    ({"pins": -3}, "pins must be a whole number of at least 1"),
    ({"pins": 7.0}, "pins must be a whole number of at least 1"),
    ({"pins": True}, "pins must be a whole number of at least 1"),
    ({"max_step": 0}, "max_step must be a whole number of at least 1"),
    ({"depths": 0}, "depths must be a whole number of at least 1"),
    ({"depths": 11}, "depths must be at most 10"),
    ({"pins": 3, "pattern": "EOX"}, "pattern must be E or O for each pin"),
    ({"pins": 3, "pattern": "eoe"}, "pattern must be E or O for each pin"),
    ({"pins": 3, "pattern": ["E", "O", "E"]}, "pattern must be E or O for each pin"),
])
def test_key_space_refuses_nonsense_at_construction(kwargs, message):
    with pytest.raises(ValueError, match=message):
        model.KeySpace(**kwargs)


def test_key_space_accepts_the_smallest_sensible_values():
    space = model.KeySpace(pins=1, pattern="E", max_step=1, depths=1)
    assert space.digits == ((0,),) and space.total_valid == 1


def test_key_space_is_immutable_and_hashable():
    space = model.KeySpace(7, "OOEOEOE", 5)
    with pytest.raises(AttributeError):
        space.pins = 6
    assert space == model.KeySpace(7, "OOEOEOE", 5) and hash(space) == hash(model.KeySpace(7, "OOEOEOE", 5))


def test_is_bitting_checks_length_and_digits():
    space = model.KeySpace(3)
    assert space.is_bitting("012") and space.is_bitting("999")
    assert not space.is_bitting("01") and not space.is_bitting("0123")
    assert not space.is_bitting("01x") and not space.is_bitting(12) and not space.is_bitting(None)


@pytest.mark.parametrize("depths", [2, 5, 8, 10])
def test_depth_count_limits_digits_and_counts(depths):
    space = model.KeySpace(3, None, 2, depths)
    assert space.digits == (tuple(range(depths)),) * 3
    brute = sum(1 for k in itertools.product(range(depths), repeat=3) if macs(k, 2))
    assert space.total_valid == brute
    assert space.is_bitting(str(depths - 1) * 3)
    assert depths == 10 or not space.is_bitting(str(depths) * 3)


def test_digits_follow_the_parity_pattern():
    space = model.KeySpace(3, "EOE")
    assert space.digits == ((0, 2, 4, 6, 8), (1, 3, 5, 7, 9), (0, 2, 4, 6, 8))
