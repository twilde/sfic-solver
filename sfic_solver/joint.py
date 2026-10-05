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


@lru_cache(maxsize=None)
def chamber_pinnable(system, operating, control):
    """True if a chamber with these operating cuts (a sorted tuple of the distinct cuts) and
    this control cut can be pinned. Cached: the same few cut sets come up again and again."""
    try:
        pin_chamber(system, operating, control)
    except PinningError:
        return False
    return True


def allowed_tuples(space, system, group, constraints, known):
    """Per position, the digit tuples (one digit for each key of `group`, in order) that leave
    every constraint's chamber pinnable.

    constraints  (operating key names, control key name) for each core and change key that
                 involves a key of the group
    known        name -> bitting for every key of those constraints that is not in the group
    """
    allowed = []
    for p in range(space.pins):
        at_p = []
        for digits in itertools.product(space.digits[p], repeat=len(group)):
            cut = dict(zip(group, digits))

            def of(name):
                return cut[name] if name in cut else known[name][p]

            if all(chamber_pinnable(system, tuple(sorted({of(n) for n in ops})), of(ctl))
                   for ops, ctl in constraints):
                at_p.append(digits)
        allowed.append(at_p)
    return allowed


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
