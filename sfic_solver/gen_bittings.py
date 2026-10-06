#!/usr/bin/env python3
"""Generate random key bittings, optionally from an even/odd pattern.

The pattern has one E or O per pin (7 for an SFIC system, but any length works).
Each cut is 0-9 with the parity the pattern asks for, and adjacent cuts
may differ by at most --max-step (default 5). Without a pattern any cut 0-9 is
allowed at every position (7 pins unless --pins says otherwise), which suits a
system whose cores are pinned for real (see "Pinning" in the README): whether
keys can be pinned together depends on the core, so check_system and
solve_system are where that is tested, not this command.

Keys also follow the shape rules (docs/designs/key-shape-rules.md): by default no equal
adjacent cuts, no depth used more than 3 times, no key whose cuts only go one way, and, with
--master, a span of at least 6 between the deepest and shallowest cut. The flags under "key
shape rules" change them; a number, or "off", for each.

Examples:
    ./gen_bittings.py OOEOEOE
    ./gen_bittings.py OOEOEOE -n 20
    ./gen_bittings.py OOEOEOE -n 5 --avoid 5961634 7305496 --min-diff 4
    ./gen_bittings.py --pins 7 -n 5             # any parity
    ./gen_bittings.py --pins 7 -n 3 --master    # masters must also span the depths
    ./gen_bittings.py OOEOEOE --max-run 2       # allow a pair of equal neighbours
"""
import argparse
import collections
import secrets

from . import model
from .shape_args import FLAGS, add_shape_arguments, shape_rules

MAX_ATTEMPTS = 100_000


def parse_pattern(text):
    """Normalise the pattern; its length is the pin count."""
    text = text.strip()
    if not text:
        raise ValueError("pattern must have at least one E/O character")
    return model.normalize_pattern(text, len(text))


def parse_bitting(text, space):
    if not space.is_bitting(text):
        raise ValueError(f"bitting must be {space.pins} digits, got {text!r}")
    return [int(c) for c in text]


def generate(space):
    """One random bitting matching the key space's parity pattern and max adjacent step.

    Rejection sampling: draw each cut uniformly, retry until the adjacent-cut
    rule holds. This is uniform over all valid bittings.
    """
    for _ in range(MAX_ATTEMPTS):
        cuts = [secrets.choice(c) for c in space.digits]
        if space.macs_ok(cuts):
            return cuts
    raise RuntimeError("no valid bitting found; is --max-step too small?")


MOST_DRAWS = 0.8


def give_up_message(rejected, draws):
    """Why the search ended: the old advice, and which shape rules turned draws down, by the
    flag that governs each. A rule that turned down most of the draws is named, since that
    usually means it cannot be met together with the others."""
    message = "could not find enough bittings; loosen the constraints"
    if rejected:
        counts = ", ".join(f"{FLAGS[name]} {count:,}" for name, count in rejected.most_common())
        message += (f" (draws that broke a shape rule, by the flag that governs it: {counts}; "
                    f"see the key shape rules flags in --help)")
        name, count = rejected.most_common(1)[0]
        if draws and count >= MOST_DRAWS * draws:
            message += (f". {FLAGS[name]} turned down {count / draws:.0%} of the draws, so it "
                        f"may not be possible with the other rules")
    return message


def differs_enough(cuts, avoid, min_diff):
    return all(sum(a != b for a, b in zip(cuts, old)) >= min_diff for old in avoid)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pattern", nargs="?",
                    help="one E/O per pin, e.g. OOEOEOE (its length is the pin count); "
                         "leave it out to allow any parity")
    ap.add_argument("--pins", type=int,
                    help="number of pins (default: the length of the pattern, else 7)")
    ap.add_argument("-n", "--count", type=int, default=10, help="how many bittings")
    ap.add_argument("--max-step", type=int, default=5,
                    help="max difference between adjacent cuts (default 5)")
    ap.add_argument("--avoid", nargs="*", action="extend", default=[], metavar="BITTING",
                    help="existing bittings to stay away from; list several after one "
                         "flag or repeat the flag")
    ap.add_argument("--min-diff", type=int,
                    help="min positions that must differ from each --avoid bitting "
                         "and from each other (default 3, or the pin count if smaller)")
    ap.add_argument("--master", action="store_true",
                    help="the bittings are master keys: the master span rule applies to them")
    add_shape_arguments(ap)
    args = ap.parse_args(argv)

    if args.max_step < 1:
        ap.error("--max-step must be at least 1")
    if args.pins is not None and args.pins < 1:
        ap.error("--pins must be at least 1")
    try:
        pattern = parse_pattern(args.pattern) if args.pattern is not None else None
        pins = len(pattern) if pattern else (args.pins or model.DEFAULT_PINS)
        if pattern and args.pins is not None and args.pins != pins:
            ap.error(f"--pins {args.pins} disagrees with the {pins} pins of the pattern")
        space = model.KeySpace(pins=pins, pattern=pattern, max_step=args.max_step)
        avoid = [parse_bitting(b, space) for b in args.avoid]
    except ValueError as err:
        ap.error(str(err))
    rules = shape_rules(ap, args, space)
    if args.min_diff is None:
        args.min_diff = min(3, pins)
    elif args.min_diff > pins:
        ap.error(f"--min-diff {args.min_diff} is more than the {pins} pins")

    accepted = []
    rejected = collections.Counter()
    attempts = 0
    while len(accepted) < args.count:
        attempts += 1
        if attempts > MAX_ATTEMPTS:
            raise SystemExit(give_up_message(rejected, attempts - 1))
        cuts = generate(space)
        broken = rules.violations(cuts, args.master)
        if broken:
            rejected.update(name for name, _ in broken)
            continue
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
