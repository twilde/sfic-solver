"""joint: exact construction of the bittings that leave every chamber pinnable."""
import itertools
import random

import pytest

from sfic_solver.joint import JointSet, allowed_tuples, bittings, chamber_pinnable, why_none
from sfic_solver.model import KeySpace
from sfic_solver.pinning import A2, pin_chambers

SPACE = KeySpace(pins=4, max_step=3)


def brute(allowed, max_step):
    """Every digit-tuple list that follows `allowed` per position and the adjacent-cut limit."""
    found = []
    for chosen in itertools.product(*allowed):
        if all(abs(a - b) <= max_step for s, t in zip(chosen, chosen[1:]) for a, b in zip(s, t)):
            found.append(list(chosen))
    return found


def random_allowed(rng, keys):
    return [[t for t in itertools.product(range(10), repeat=keys) if rng.random() < 0.15]
            for _ in range(4)]


@pytest.mark.parametrize("keys", [1, 2])
@pytest.mark.parametrize("seed", range(4))
def test_count_and_enumeration_match_a_brute_force(keys, seed):
    allowed = random_allowed(random.Random(seed), keys)
    joint = JointSet(allowed, 3)
    everything = brute(allowed, 3)
    assert joint.count == len(everything)
    assert sorted(joint.enumerate()) == sorted(everything)


def test_draws_are_always_members_and_reach_every_member():
    allowed = [[(a,) for a in range(3)] for _ in range(3)]
    joint = JointSet(allowed, 1)
    members = {tuple(c) for c in brute(allowed, 1)}
    rng = random.Random(1)
    drawn = {tuple(joint.draw(rng)) for _ in range(400)}
    assert drawn == members and joint.count == len(members)


def test_draws_are_uniform_over_the_members():
    # The first digit 0 has three completions and 5 has one: a draw that chose the first digit
    # with equal odds would be biased (half), one weighted by completions is not (three quarters).
    allowed = [[(0,), (5,)], [(0,), (1,), (2,), (5,)]]
    joint = JointSet(allowed, 2)
    rng = random.Random(2)
    firsts = [joint.draw(rng)[0] for _ in range(3000)]
    assert joint.count == 4 and 0.70 < firsts.count((0,)) / 3000 < 0.80


def test_nothing_is_counted_when_the_adjacent_cut_limit_leaves_none():
    joint = JointSet([[(0,)], [(9,)]], 5)
    assert joint.count == 0
    assert "adjacent-cut limit" in why_none([[(0,)], [(9,)]])


def test_a_single_position_is_every_allowed_tuple():
    joint = JointSet([[(1, 2), (3, 4)]], 5)
    assert joint.count == 2 and sorted(joint.enumerate()) == [[(1, 2)], [(3, 4)]]


def test_bittings_splits_a_draw_by_key():
    assert bittings([(1, 7), (2, 8), (3, 9)]) == [(1, 2, 3), (7, 8, 9)]


def test_why_none_names_the_positions_where_no_cut_pins():
    assert "no cut at position 2 leaves" in why_none([[(1,)], [], [(1,)]])
    assert "no cut at positions 1, 3 leaves" in why_none([[], [(1,)], []])


def test_chamber_pinnable_agrees_with_the_pinner():
    assert chamber_pinnable(A2, (3,), 4) is True
    assert chamber_pinnable(A2, (3, 4), 4) is False           # a pin of size 1 does not exist


def test_allowed_tuples_are_exactly_the_digit_tuples_every_chamber_accepts():
    space = KeySpace(pins=2)
    known = {"unit": (3, 6), "control": (4, 1)}
    constraints = [(["unit", "master"], "control")]
    allowed = allowed_tuples(space, A2, ["master"], constraints, known)
    for p in range(2):
        want = [(d,) for d in range(10)
                if not pin_chambers(A2, [(known["unit"][p],), (d,)], (known["control"][p],))[1]]
        assert allowed[p] == want and want                  # (3 and 6 exclude their neighbours)
    assert (4,) not in allowed[0] and (3,) in allowed[0]


def test_two_unknown_keys_are_tested_together():
    space = KeySpace(pins=1)
    known = {"control": (0,)}
    constraints = [(["a", "b"], "control")]
    allowed = allowed_tuples(space, A2, ["a", "b"], constraints, known)[0]
    for a, b in itertools.product(range(10), repeat=2):
        assert ((a, b) in allowed) == (not pin_chambers(A2, [(a,), (b,)], (0,))[1])
