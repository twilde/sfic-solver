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


def test_count_valid_known_value():
    assert model.count_valid("OOEOEOE", 5) == 28_384


@pytest.mark.parametrize("pins", [3, 4])
def test_count_valid_matches_brute_force(monkeypatch, pins):
    monkeypatch.setattr(model, "PINS", pins)
    rng = random.Random(1)
    for _ in range(30):
        pattern = "".join(rng.choice("EO") for _ in range(pins))
        max_step = rng.randint(1, 9)
        assert model.count_valid(pattern, max_step) == len(all_valid(pattern, max_step))


def test_count_valid_without_pattern_matches_brute_force(monkeypatch):
    monkeypatch.setattr(model, "PINS", 4)
    for max_step in (1, 3, 5, 9):
        brute = sum(1 for k in itertools.product(range(10), repeat=4) if macs(k, max_step))
        assert model.count_valid(None, max_step) == brute


def test_operating_set_size_matches_brute_force():
    rng = random.Random(2)
    for i in range(150):
        # 1-3 options per pin (up to 3**7 combinations), a few cases with 4.
        top = 4 if i % 25 == 0 else 3
        options = [sorted(rng.sample(range(10), rng.randint(1, top))) for _ in range(model.PINS)]
        max_step = rng.randint(1, 9)
        brute = sum(1 for cuts in itertools.product(*options) if macs(cuts, max_step))
        assert model.operating_set_size(options, max_step) == brute, (options, max_step)


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
def test_pair_conflict_probability_matches_brute_force(monkeypatch, pins, cases):
    monkeypatch.setattr(model, "PINS", pins)
    rng = random.Random(3 + pins)
    for _ in range(cases):
        pattern = "".join(rng.choice("EO") for _ in range(pins))
        max_step = rng.randint(1, 9)
        valid = all_valid(pattern, max_step)
        total = model.count_valid(pattern, max_step)
        assert total == len(valid)
        masters = [rng.choice(valid) for _ in range(rng.randint(0, 3))]

        # B operates the core of A when each of B's cuts is A's cut or a master's.
        hits = sum(1 for a in valid for b in valid
                   if all(b[p] == a[p] or any(b[p] == m[p] for m in masters)
                          for p in range(pins)))
        expected = float(Fraction(hits, total ** 2))
        assert model.pair_conflict_probability(masters, pattern, max_step, total) \
            == pytest.approx(expected, rel=1e-12)


def test_pair_conflict_probability_without_masters_is_one_over_count(monkeypatch):
    # With no masters B must equal A, so the chance is 1 / count_valid.
    monkeypatch.setattr(model, "PINS", 4)
    for pattern, max_step in [("EOEO", 5), ("EEOE", 2), ("OOOO", 9)]:
        total = model.count_valid(pattern, max_step)
        p = model.pair_conflict_probability([], pattern, max_step, total)
        assert p == pytest.approx(1 / total, rel=1e-12)


def test_pair_conflict_probability_full_pin_count_sanity():
    total = model.count_valid("OOEOEOE", 5)
    p0 = model.pair_conflict_probability([], "OOEOEOE", 5, total)
    assert p0 == pytest.approx(1 / total, rel=1e-12)
    master = (0, 1, 2, 3, 4, 5, 6)
    assert model.pair_conflict_probability([master], "OOEOEOE", 5, total) > p0


def test_distance_and_macs_and_parity_helpers():
    assert model.distance((1, 2, 3), (1, 5, 6)) == 2
    assert model.macs_ok((0, 5, 0), 5) and not model.macs_ok((0, 6, 0), 5)
    assert model.parity_bad((0, 1, 2, 3, 4, 5, 6), "EOEOEOE") == []
    assert model.parity_bad((1, 1, 2, 3, 4, 5, 7), "EOEOEOE") == [1, 7]
