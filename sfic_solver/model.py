"""The counting maths for a master-keyed system. Pure functions, no I/O.

A bitting is a tuple of cuts (0-9), one per pin. The rules that decide which
bittings can be cut (how many pins, how many depths, the adjacent-cut limit and
the optional parity pattern) live together in a `KeySpace`; functions that need
them are its methods, and the rest read what they need off their arguments.
"""
import itertools
from dataclasses import dataclass
from functools import cached_property
from typing import Optional, Tuple

DEFAULT_PINS = 7
DEFAULT_DEPTHS = 10
DEFAULT_MAX_STEP = 5
DEFAULT_MIN_DIFF = 5


def default_min_diff(pins):
    """The closeness default, capped so that it can be met at all (fewer than 5 pins)."""
    return min(DEFAULT_MIN_DIFF, pins)


def normalize_pattern(text, pins):
    """Upper-case an E/O parity pattern, or raise ValueError if it is malformed."""
    pattern = text.upper()
    if len(pattern) != pins or set(pattern) - {"E", "O"}:
        raise ValueError(f"pattern must be {pins} characters of E/O, got {text!r}")
    return pattern


@dataclass(frozen=True)
class Population:
    """A set of bittings, as a signed sum of products of per-position cut sets.

    Each term is (sign, sets) with one tuple of allowed cuts per position, so a term
    is every bitting whose cut at each position is in that position's set. A union of
    such products is written by inclusion and exclusion: a term for each subset, with
    sign + for an odd number of products and - for an even number. Counting a
    population is then a sum of the per-term counts, which the KeySpace methods do
    exactly (the MACS limit couples the positions, so the counts are dynamic
    programming, not products).
    """
    terms: Tuple[Tuple[int, Tuple[Tuple[int, ...], ...]], ...]

    @classmethod
    def of_sets(cls, sets):
        """The bittings whose cut at each position is in the given set."""
        return cls(((1, tuple(tuple(sorted(s)) for s in sets)),))

    @classmethod
    def union_of(cls, products):
        """The bittings in at least one of several per-position set products.

        Writes the union by inclusion and exclusion, so it has 2**n - 1 terms before
        empty ones are dropped: callers keep n small.
        """
        terms = []
        for size in range(1, len(products) + 1):
            for chosen in itertools.combinations(products, size):
                sets = tuple(tuple(sorted(set.intersection(*(set(p[i]) for p in chosen))))
                             for i in range(len(chosen[0])))
                if all(sets):
                    terms.append(((-1) ** (size + 1), sets))
        return cls(tuple(terms))

    def restricted(self, sets):
        """The part of the population whose cut at each position is also in `sets`."""
        terms = []
        for sign, own in self.terms:
            narrowed = tuple(tuple(c for c in own[i] if c in sets[i]) for i in range(len(own)))
            if all(narrowed):
                terms.append((sign, narrowed))
        return Population(tuple(terms))

    def contains(self, cuts):
        """True if the bitting is in the population (the MACS limit is not considered)."""
        return sum(sign for sign, sets in self.terms
                   if all(c in sets[i] for i, c in enumerate(cuts))) == 1


@dataclass(frozen=True)
class KeySpace:
    """Which bittings can be cut: the rules every key in a system must follow.

    pins       number of cut positions (the length of every bitting)
    pattern    one E/O per pin (already normalised), or None for any parity
    max_step   largest allowed difference between adjacent cuts (MACS)
    depths     number of cut depths, 0 to depths - 1
    """
    pins: int = DEFAULT_PINS
    pattern: Optional[str] = None
    max_step: int = DEFAULT_MAX_STEP
    depths: int = DEFAULT_DEPTHS

    def __post_init__(self):
        for name in ("pins", "max_step", "depths"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a whole number of at least 1, got {value!r}")
        if self.depths > 10:
            raise ValueError(f"depths must be at most 10 (a bitting is one digit per cut), "
                             f"got {self.depths}")
        if self.pattern is not None:
            if not isinstance(self.pattern, str) or set(self.pattern) - {"E", "O"}:
                raise ValueError(f"pattern must be E or O for each pin, got {self.pattern!r}")
            if len(self.pattern) != self.pins:
                raise ValueError(f"pattern has {len(self.pattern)} characters "
                                 f"but the key space has {self.pins} pins")

    def is_bitting(self, text):
        """True if `text` is a string of exactly `pins` digits, each a legal depth."""
        return (isinstance(text, str) and len(text) == self.pins and text.isascii()
                and text.isdigit() and all(int(c) < self.depths for c in text))

    @cached_property
    def digits(self):
        """Per pin, the cut depths allowed by the parity pattern (all depths if None)."""
        return tuple(tuple(d for d in range(self.depths)
                           if self.pattern is None
                           or d % 2 == (0 if self.pattern[i] == "E" else 1))
                     for i in range(self.pins))

    def parity_bad(self, cuts):
        """1-based pin numbers whose cut has the wrong parity for the pattern (none if
        there is no pattern: any parity is allowed)."""
        if self.pattern is None:
            return []
        return [i + 1 for i, (c, p) in enumerate(zip(cuts, self.pattern))
                if c % 2 != (0 if p == "E" else 1)]

    def macs_violations(self, cuts):
        """1-based pin numbers after which the next cut is more than max_step away."""
        return [i + 1 for i, (a, b) in enumerate(zip(cuts, cuts[1:]))
                if abs(a - b) > self.max_step]

    def macs_ok(self, cuts):
        return all(abs(a - b) <= self.max_step for a, b in zip(cuts, cuts[1:]))

    @cached_property
    def total_valid(self):
        """Number of bittings matching the parity pattern and adjacent-cut limit."""
        return self.operating_set_size(self.digits)

    def operating_set_size(self, options):
        """Number of MACS-valid bittings built from the per-position option sets."""
        ways = {d: 1 for d in options[0]}
        for p in range(1, len(options)):
            ways = {d: sum(w for pd, w in ways.items() if abs(d - pd) <= self.max_step)
                    for d in options[p]}
        return sum(ways.values())

    def uniform(self):
        """The population of every valid bitting: the parity pattern's cuts, any MACS-valid key."""
        return Population.of_sets(self.digits)

    def population_size(self, population):
        """Number of MACS-valid bittings in the population."""
        return sum(sign * self.operating_set_size(sets) for sign, sets in population.terms)

    def population_operating(self, population, options):
        """Number of MACS-valid bittings in the population that a core accepts, where
        `options` is the per-position cuts the core accepts (see `options_for`)."""
        return self.population_size(population.restricted(options))

    def population_contains(self, population, cuts):
        """True if the bitting is in the population and MACS-valid."""
        return self.macs_ok(cuts) and population.contains(cuts)

    def pair_conflict_probability(self, masters, population=None):
        """Chance that a random valid key B operates the core of a random valid key A.

        The core is pinned with A as change key and `masters` above it, so B works
        when, at every position, its cut equals A's cut or a master's cut.
        Exact (dynamic programming over positions), no sampling. With a population,
        A and B are both drawn from it instead of from every valid bitting.
        """
        if population is None:
            return self.pair_count(masters, self.digits, self.digits) / self.total_valid ** 2
        pairs = sum(a_sign * b_sign * self.pair_count(masters, a_sets, b_sets)
                    for a_sign, a_sets in population.terms
                    for b_sign, b_sets in population.terms)
        return pairs / self.population_size(population) ** 2

    def pair_count(self, masters, a_sets, b_sets):
        """Pairs (A, B) of MACS-valid keys, A from `a_sets` and B from `b_sets` (per-position
        cut sets), where B operates the core pinned with A and `masters`."""
        def allowed(p, a):
            return {a, *(m[p] for m in masters)} & set(b_sets[p])

        states = {(a, b): 1 for a in a_sets[0] for b in allowed(0, a)}
        for p in range(1, self.pins):
            new = {}
            for (a0, b0), w in states.items():
                for a in a_sets[p]:
                    if abs(a - a0) > self.max_step:
                        continue
                    for b in allowed(p, a):
                        if abs(b - b0) <= self.max_step:
                            new[(a, b)] = new.get((a, b), 0) + w
            states = new
        return sum(states.values())


def distance(a, b):
    """Number of pin positions at which two bittings differ."""
    return sum(x != y for x, y in zip(a, b))


def options_for(change, masters):
    """Per pin, the sorted cuts a core pinned with `change` plus `masters` accepts."""
    keys = [change] + list(masters)
    return [sorted({k[p] for k in keys}) for p in range(len(change))]


def operates(key, options):
    return all(key[p] in options[p] for p in range(len(options)))
