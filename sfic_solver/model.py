"""The counting maths for a master-keyed 7-pin system. Pure functions, no I/O.

A bitting is a tuple of cuts (0-9), one per pin. `PINS` is a module-level
setting that every function reads when called, so tests can patch it to a
smaller number of pins and compare against brute-force enumeration.
"""

PINS = 7


def is_bitting(text):
    """True if `text` is a string of exactly PINS ASCII digits."""
    return isinstance(text, str) and len(text) == PINS and text.isascii() and text.isdigit()


def normalize_pattern(text):
    """Upper-case an E/O parity pattern, or raise ValueError if it is malformed."""
    pattern = text.upper()
    if len(pattern) != PINS or set(pattern) - {"E", "O"}:
        raise ValueError(f"pattern must be {PINS} characters of E/O, got {text!r}")
    return pattern


def macs_violations(cuts, max_step):
    """1-based pin numbers after which the next cut is more than max_step away."""
    return [i + 1 for i, (a, b) in enumerate(zip(cuts, cuts[1:])) if abs(a - b) > max_step]


def macs_ok(cuts, max_step):
    return all(abs(a - b) <= max_step for a, b in zip(cuts, cuts[1:]))


def parity_bad(cuts, pattern):
    """1-based pin numbers whose cut has the wrong parity for the pattern."""
    return [i + 1 for i, (c, p) in enumerate(zip(cuts, pattern))
            if c % 2 != (0 if p == "E" else 1)]


def distance(a, b):
    """Number of pin positions at which two bittings differ."""
    return sum(x != y for x, y in zip(a, b))


def valid_digits(pattern):
    """Per pin, the cut depths allowed by the parity pattern (all of 0-9 if None)."""
    return [[d for d in range(10)
             if pattern is None or d % 2 == (0 if pattern[i] == "E" else 1)]
            for i in range(PINS)]


def count_valid(pattern, max_step):
    """Number of bittings matching the parity pattern and adjacent-cut limit."""
    digits = valid_digits(pattern)
    ways = {d: 1 for d in digits[0]}
    for i in range(1, PINS):
        ways = {d: sum(w for pd, w in ways.items() if abs(d - pd) <= max_step)
                for d in digits[i]}
    return sum(ways.values())


def options_for(change, masters):
    """Per pin, the sorted cuts a core pinned with `change` plus `masters` accepts."""
    keys = [change] + list(masters)
    return [sorted({k[p] for k in keys}) for p in range(PINS)]


def operates(key, options):
    return all(key[p] in options[p] for p in range(PINS))


def operating_set_size(options, max_step):
    """Number of MACS-valid bittings built from the per-position option sets."""
    ways = {d: 1 for d in options[0]}
    for p in range(1, PINS):
        ways = {d: sum(w for pd, w in ways.items() if abs(d - pd) <= max_step)
                for d in options[p]}
    return sum(ways.values())


def pair_conflict_probability(masters, pattern, max_step, total_valid):
    """Chance that a random valid key B operates the core of a random valid key A.

    The core is pinned with A as change key and `masters` above it, so B works
    when, at every position, its cut equals A's cut or a master's cut.
    Exact (dynamic programming over positions), no sampling.
    """
    digits = valid_digits(pattern)

    def allowed(p, a):
        return {a, *(m[p] for m in masters)} & set(digits[p])

    states = {(a, b): 1 for a in digits[0] for b in allowed(0, a)}
    for p in range(1, PINS):
        new = {}
        for (a0, b0), w in states.items():
            for a in digits[p]:
                if abs(a - a0) > max_step:
                    continue
                for b in allowed(p, a):
                    if abs(b - b0) <= max_step:
                        new[(a, b)] = new.get((a, b), 0) + w
        states = new
    return sum(states.values()) / total_valid ** 2
