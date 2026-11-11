"""Exact construction of pinnable bittings for a few unknown keys at once.

Pinning is decided one chamber at a time: whether the cuts at position p can be pinned
depends only on the cuts at p of the keys of one core and its control key. So when
several unknown keys share cores with known keys (and with each other), the digit
combinations that leave every involved chamber pinnable can be listed for each position
on its own, at most 10**u of them for u unknown keys. Only the maximum adjacent cut
specification (MACS) couples the positions, and the counts for it are a dynamic
programme over positions, as in `model.KeySpace`. This module builds those lists and
draws, or enumerates, whole bittings from them. See docs/designs/pinnable-solving.md.

Pure functions and one small class; no I/O.
"""
import itertools
from functools import lru_cache

from .pinning import PinningError, pin_chamber


class TooLarge(Exception):
    """The lists of digit tuples are too long to count exactly within the limit given."""

    def __init__(self, limit):
        super().__init__(f"more than {limit:,} pairs of neighbouring combinations a position")
        self.limit = limit


@lru_cache(maxsize=None)
def chamber_pinnable(system, operating, control):
    """True if a chamber with these operating cuts (a sorted tuple of the distinct cuts) and
    this control cut can be pinned. Cached: the same few cut sets come up again and again."""
    try:
        pin_chamber(system, operating, control)
    except PinningError:
        return False
    return True


def constraint_plan(order, constraints):
    """(index, tested_after, fixed) for choosing the keys of `order` one after another:
    index maps a key's name to its place; tested_after[i] are the constraints to test once
    key i has its digit (they need no later key); `fixed` are those with no key of the order,
    which every choice meets or fails."""
    index = {name: i for i, name in enumerate(order)}
    tested_after = [[] for _ in order]
    fixed = []
    for ops, ctl in constraints:
        last = max((index[n] for n in (*ops, ctl) if n in index), default=None)
        (fixed if last is None else tested_after[last]).append((ops, ctl))
    return index, tested_after, fixed


def allowed_tuples(space, system, group, constraints, known, max_pairs=None):
    """Per position, the digit tuples (one digit for each key of `group`, in order) that leave
    every constraint's chamber pinnable.

    constraints  (operating key names, control key name) for each core and change key that
                 involves a key of the group
    known        name -> bitting for every key of those constraints that is not in the group

    The tuples are found by choosing the group's keys one after another and testing each
    constraint as soon as all of its keys that are in the group have a digit, so a partial
    choice that already breaks a chamber is dropped without being extended to the 10 ** u
    combinations it would start. They come in the order of `itertools.product` over the
    position's digits.

    `max_pairs`, when given, bounds the work `JointSet` will do on the result, which is one
    comparison for each pair of a position's tuple and the next position's: no list may be
    longer than `max_pairs`, and the pairs summed over the positions may not be more than
    `max_pairs` for each step between positions. Past that, TooLarge is raised as soon as it
    is known, before the lists are finished.
    """
    index, tested_after, fixed = constraint_plan(group, constraints)

    allowed = []
    pairs = 0
    for p in range(space.pins):
        cut = [None] * len(group)

        def of(name):
            return cut[index[name]] if name in index else known[name][p]

        def pinnable(tests):
            return all(chamber_pinnable(system, tuple(sorted({of(n) for n in ops})), of(ctl))
                       for ops, ctl in tests)

        at_p = []

        def extend(depth):
            if depth == len(group):
                at_p.append(tuple(cut))
                if max_pairs is not None and len(at_p) > max_pairs:
                    raise TooLarge(max_pairs)
                return
            for digit in space.digits[p]:
                cut[depth] = digit
                if pinnable(tested_after[depth]):
                    extend(depth + 1)

        if pinnable(fixed):
            extend(0)
        if allowed and max_pairs is not None:
            pairs += len(allowed[-1]) * len(at_p)
            if pairs > max_pairs * (space.pins - 1):
                raise TooLarge(max_pairs)
        allowed.append(at_p)
    return allowed


PROJECTION_NODES = 100_000     # most digit choices tried in deciding whether one digit of a
                               # key can be completed by the other keys at a position


def extendable_digits(space, system, group, key, constraints, known):
    """Per position, the digits of `key` that the other keys of `group` can complete to a
    choice that leaves every constraint's chamber pinnable, as one-digit tuples in the order
    of the digits (the shape `JointSet` takes). This is the projection of the tuples
    `allowed_tuples` would list onto one key, found without listing them: a digit is tried
    by choosing the other keys one after another, as there, and stopping at the first choice
    that works.

    A digit whose search passes PROJECTION_NODES choices is kept, not decided: so a position
    with no digit left has none for certain, and one with some may still fail to complete.
    """
    order = [key, *(k for k in group if k != key)]
    index, tested_after, fixed = constraint_plan(order, constraints)
    projected = []
    for p in range(space.pins):
        cut = [None] * len(order)

        def of(name):
            return cut[index[name]] if name in index else known[name][p]

        def pinnable(tests):
            return all(chamber_pinnable(system, tuple(sorted({of(n) for n in ops})), of(ctl))
                       for ops, ctl in tests)

        nodes = 0

        def completes(depth):
            nonlocal nodes
            if depth == len(order):
                return True
            for digit in space.digits[p]:
                nodes += 1
                if nodes > PROJECTION_NODES:
                    return True
                cut[depth] = digit
                if pinnable(tested_after[depth]) and completes(depth + 1):
                    return True
            return False

        at_p = []
        if pinnable(fixed):
            for digit in space.digits[p]:
                cut[0] = digit
                nodes = 0
                if pinnable(tested_after[0]) and completes(1):
                    at_p.append((digit,))
        projected.append(at_p)
    return projected


class JointSet:
    """Every set of bittings for a group of keys whose digit tuples are `allowed` per position
    and whose cuts keep each key within `max_step` of its previous cut (MACS).

    `count` is how many there are, exactly; `draw` picks one uniformly; `enumerate` lists them
    all (only sensible when `count` is small). Each is a list with one digit tuple per
    position, which `bittings` turns into one bitting per key.
    """

    def __init__(self, allowed, max_step):
        pins = len(allowed)
        self.ways = [None] * pins                    # per position: state -> completions
        self.following = [None] * pins               # per position: state -> next states
        self.ways[-1] = {s: 1 for s in allowed[-1]}
        for p in range(pins - 2, -1, -1):
            ways, following = {}, {}
            for s in allowed[p]:
                nxt = [t for t in self.ways[p + 1]
                       if all(abs(a - b) <= max_step for a, b in zip(s, t))]
                if nxt:
                    following[s] = nxt
                    ways[s] = sum(self.ways[p + 1][t] for t in nxt)
            self.ways[p], self.following[p] = ways, following
        self.count = sum(self.ways[0].values())

    def draw(self, rng):
        state = rng.choices(list(self.ways[0]), weights=list(self.ways[0].values()))[0]
        chosen = [state]
        for p in range(len(self.ways) - 1):
            options = self.following[p][state]
            state = rng.choices(options, weights=[self.ways[p + 1][t] for t in options])[0]
            chosen.append(state)
        return chosen

    def enumerate(self):
        def extend(p, state):
            if p == len(self.ways) - 1:
                yield [state]
                return
            for t in self.following[p][state]:
                for rest in extend(p + 1, t):
                    yield [state, *rest]

        for s in self.ways[0]:
            yield from extend(0, s)


def bittings(chosen):
    """One bitting (a tuple of cuts) for each key of the group, from a drawn digit-tuple list."""
    return [tuple(state[i] for state in chosen) for i in range(len(chosen[0]))]


def why_none(allowed):
    """A short reason why no bitting exists: the positions where no digits can be pinned, or
    that the adjacent-cut limit leaves nothing."""
    empty = [p + 1 for p, tuples in enumerate(allowed) if not tuples]
    if empty:
        where = "position " if len(empty) == 1 else "positions "
        return f"no cut at {where}{', '.join(map(str, empty))} leaves every core there pinnable"
    return "no cuts that leave every core pinnable also keep to the adjacent-cut limit"
