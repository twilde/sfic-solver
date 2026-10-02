"""The simulated lock, and its agreement with the pinner and the key-level counting."""
import itertools
import random

import pytest

from sfic_solver import model
from sfic_solver.lock import CONTROL, OPERATING, Lock
from sfic_solver.pinning import A2, Chamber, PinningError, pin_core
from test_design_docs import example_charts


def lock_for(keys, control):
    return Lock.from_chambers(A2, pin_core(A2, keys, control))


def test_a_deeper_cut_lifts_the_stack_less():
    lock = Lock(A2, [(1, 4, 8, 10)])
    assert [lock.lift(c) for c in range(10)] == [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]


def test_the_ledgers_example_lock():
    lock = Lock(A2, [(1, 4, 8, 10)])           # master cut 1, change cut 5, control cut 3
    assert lock.operates((1,)) and lock.operates((5,))
    assert not any(lock.operates((c,)) for c in (0, 2, 3, 4, 6, 7, 8, 9))
    assert lock.aligned((3,), CONTROL) and not lock.aligned((2,), CONTROL)
    assert lock.lines_aligned((5,)) == {OPERATING}
    assert lock.lines_aligned((3,)) == {CONTROL}
    assert lock.lines_aligned((0,)) == frozenset()


def test_joint_on_line_names_the_joint():
    lock = Lock(A2, [(1, 4, 8, 10)])
    assert lock.joint_on_line(0, 1, OPERATING) == 1       # between the 1 and the 4
    assert lock.joint_on_line(0, 5, OPERATING) == 2       # between the 4 and the 8
    assert lock.joint_on_line(0, 3, CONTROL) == 3         # between the 8 and the 10
    assert lock.joint_on_line(0, 2, OPERATING) is None    # a pin straddles the line


def test_a_key_must_fit_the_lock():
    lock = Lock(A2, [(1, 4, 8, 10)] * 2)
    for key in [(1,), (1, 2, 3), (1, 10), (1, -1), (1, 2.0), (1, True)]:
        with pytest.raises(ValueError, match="a key needs 2 cuts from 0 to 9"):
            lock.operates(key)
    with pytest.raises(ValueError, match="unknown shear line"):
        lock.shear_height("middle")


def test_a_key_cut_like_the_control_key_aligns_the_control_line():
    control = (3, 7, 2)
    lock = lock_for([(1, 5, 9)], control)
    assert lock.aligned(control, CONTROL)
    assert not lock.operates(control)
    # A known operating key that happens to match the control bitting works as a
    # control key too, and still operates the core: both lines line up.
    twin = lock_for([control], control)
    assert twin.lines_aligned(control) == {OPERATING, CONTROL}


def test_splitting_a_gap_into_two_pins_creates_working_keys_nobody_intended():
    proper = Lock.from_chambers(A2, pin_core(A2, [(1,), (5,)], (3,)))
    split = Lock(A2, [(1, 2, 2, 8, 10)])       # the 4 pin cut into 2 + 2
    assert sum(split.stacks[0]) == 23
    assert not proper.operates((3,)) and split.operates((3,))
    assert split.operates((1,)) and split.operates((5,))


# -- agreement with the key-level counting, over every key of small locks ---------------

def random_core(rng, chambers):
    """Operating keys and a control key that can be pinned, or None."""
    keys = [tuple(rng.randrange(10) for _ in range(chambers)) for _ in range(rng.randint(1, 3))]
    control = tuple(rng.randrange(10) for _ in range(chambers))
    try:
        return keys, control, lock_for(keys, control)
    except PinningError:
        return None


def test_the_lock_agrees_with_the_set_arithmetic_for_every_key():
    rng = random.Random(11)
    cores = checked = 0
    while cores < 60:
        core = random_core(rng, 3)
        if core is None:
            continue
        keys, control, lock = core
        cores += 1
        options = model.options_for(keys[0], keys[1:])
        operating = 0
        for key in itertools.product(range(10), repeat=3):
            assert lock.operates(key) == model.operates(key, options), (keys, key)
            assert lock.aligned(key, CONTROL) == (key == control), (control, key)
            operating += lock.operates(key)
            checked += 1
        # With no adjacent-cut limit the model counts the same operating keys.
        assert operating == model.KeySpace(3, None, 9).operating_set_size(options)
    assert checked == 60 * 1000


def test_every_intended_key_operates_and_the_control_key_aligns_control():
    rng = random.Random(12)
    for _ in range(200):
        core = random_core(rng, 7)
        if core is None:
            continue
        keys, control, lock = core
        assert all(lock.operates(k) for k in keys)
        assert lock.aligned(control, CONTROL)


def test_the_design_documents_example_locks_work_with_their_keys():
    for fields, keys, control, rows in example_charts():
        keys = [[int(c) for c in k] for k in keys]
        control = [int(c) for c in control]
        lock = lock_for(keys, control)
        assert all(lock.lines_aligned(k) >= {OPERATING} for k in keys), fields["Core"]
        assert lock.aligned(control, CONTROL), fields["Core"]
        near_miss = [(keys[0][0] + 1) % 10, *keys[0][1:]]       # one cut changed
        options = model.options_for(keys[0], keys[1:])
        assert lock.operates(near_miss) == model.operates(near_miss, options), fields["Core"]
