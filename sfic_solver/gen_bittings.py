#!/usr/bin/env python3
"""Generate random key bittings from an even/odd pattern.

The pattern has one E or O per pin (7 for an SFIC system, but any length works).
Each cut is 0-9 with the parity the pattern asks for, and adjacent cuts
may differ by at most --max-step (default 5).

Examples:
    ./gen_bittings.py OOEOEOE
    ./gen_bittings.py OOEOEOE -n 20
    ./gen_bittings.py OOEOEOE -n 5 --avoid 5961634 7305496 --min-diff 4
"""
import argparse
import secrets

from . import model

MAX_ATTEMPTS = 100_000


def parse_pattern(text):
    """Normalise the pattern; its length is the pin count."""
    text = text.strip()
    if not text:
        raise ValueError("pattern must have at least one E/O character")
    return model.normalize_pattern(text, len(text))


def parse_bitting(text, pins):
    if not model.is_bitting(text, pins):
        raise ValueError(f"bitting must be {pins} digits, got {text!r}")
    return [int(c) for c in text]


def digits_for(parity):
    return [d for d in range(10) if d % 2 == (0 if parity == "E" else 1)]


def generate(pattern, max_step):
    """One random bitting matching the parity pattern and max adjacent step.

    Rejection sampling: draw each cut uniformly, retry until the adjacent-cut
    rule holds. This is uniform over all valid bittings.
    """
    choices = [digits_for(p) for p in pattern]
    for _ in range(MAX_ATTEMPTS):
        cuts = [secrets.choice(c) for c in choices]
        if all(abs(a - b) <= max_step for a, b in zip(cuts, cuts[1:])):
            return cuts
    raise RuntimeError("no valid bitting found; is --max-step too small?")


def differs_enough(cuts, avoid, min_diff):
    return all(sum(a != b for a, b in zip(cuts, old)) >= min_diff for old in avoid)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pattern", help="one E/O per pin, e.g. OOEOEOE (its length is the pin count)")
    ap.add_argument("-n", "--count", type=int, default=10, help="how many bittings")
    ap.add_argument("--max-step", type=int, default=5,
                    help="max difference between adjacent cuts (default 5)")
    ap.add_argument("--avoid", nargs="*", action="extend", default=[], metavar="BITTING",
                    help="existing bittings to stay away from; list several after one "
                         "flag or repeat the flag")
    ap.add_argument("--min-diff", type=int,
                    help="min positions that must differ from each --avoid bitting "
                         "and from each other (default 3, or the pin count if smaller)")
    args = ap.parse_args(argv)

    if args.max_step < 1:
        ap.error("--max-step must be at least 1")
    try:
        pattern = parse_pattern(args.pattern)
        avoid = [parse_bitting(b, len(pattern)) for b in args.avoid]
    except ValueError as err:
        ap.error(str(err))
    if args.min_diff is None:
        args.min_diff = min(3, len(pattern))
    elif args.min_diff > len(pattern):
        ap.error(f"--min-diff {args.min_diff} is more than the {len(pattern)} pins in the pattern")

    accepted = []
    attempts = 0
    while len(accepted) < args.count:
        attempts += 1
        if attempts > MAX_ATTEMPTS:
            raise SystemExit("could not find enough bittings; loosen the constraints")
        cuts = generate(pattern, args.max_step)
        # New bittings must also stay --min-diff away from each other, not just
        # from the --avoid list. Also rejects duplicates when min-diff >= 1.
        if cuts not in accepted and differs_enough(cuts, avoid + accepted, args.min_diff):
            accepted.append(cuts)

    # Printed in generation order, not sorted, so picking "the first one" is unbiased.
    for cuts in accepted:
        print("".join(map(str, cuts)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
