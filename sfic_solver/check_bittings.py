#!/usr/bin/env python3
"""Sanity-check a set of bittings (7 pins unless --pins or --pattern says otherwise).

Checks each bitting for format, parity (if --pattern is given) and the
adjacent-cut limit, then lists every pair closer than --min-diff positions.

Examples:
    ./check_bittings.py --pattern OOEOEOE key_a=5961634 key_b=7305496 key_c=5721276
    ./check_bittings.py --min-diff 5 key_a=5961634 key_b=7305496 new_master=7587672

Exits with status 1 if anything is flagged.
"""
import argparse
import itertools

from . import model


def parse_item(text, space):
    name, _, bitting = text.rpartition("=")
    name = name or bitting
    if not space.is_bitting(bitting):
        raise ValueError(f"{text!r}: bitting must be {space.pins} digits "
                         f"(set --pins if that is wrong)")
    return name, [int(c) for c in bitting]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keys", nargs="+", metavar="[NAME=]BITTING")
    ap.add_argument("--pins", type=int,
                    help="number of pins (default: the length of --pattern, else 7)")
    ap.add_argument("--pattern",
                    help="one E/O per pin; flags cuts with the wrong parity")
    ap.add_argument("--max-step", type=int, default=5, help="max adjacent-cut difference")
    ap.add_argument("--min-diff", type=int,
                    help="flag pairs differing in fewer positions than this "
                         "(default 5, or the pin count if smaller)")
    args = ap.parse_args(argv)

    if args.pins is not None and args.pins < 1:
        ap.error("--pins must be at least 1")
    if args.max_step < 1:
        ap.error("--max-step must be at least 1")
    if args.pins is not None:
        pins = args.pins
    elif args.pattern:
        pins = len(args.pattern)
    else:
        pins = model.DEFAULT_PINS
    pattern = None
    if args.pattern:
        try:
            pattern = model.normalize_pattern(args.pattern, pins)
        except ValueError:
            ap.error(f"--pattern must be {pins} characters of E/O")
    if args.min_diff is None:
        args.min_diff = model.default_min_diff(pins)
    elif args.min_diff > pins:
        ap.error(f"--min-diff {args.min_diff} is more than the {pins} pins")

    space = model.KeySpace(pins=pins, pattern=pattern, max_step=args.max_step)
    try:
        keys = [parse_item(k, space) for k in args.keys]
    except ValueError as err:
        ap.error(str(err))

    problems = 0
    for name, cuts in keys:
        if pattern:
            bad = space.parity_bad(cuts)
            if bad:
                print(f"PARITY  {name}: wrong parity at pin(s) {bad}")
                problems += 1
        big = space.macs_violations(cuts)
        if big:
            print(f"MACS    {name}: adjacent cuts too far apart after pin(s) {big}")
            problems += 1

    pairs = sorted(((model.distance(a[1], b[1]), a[0], b[0])
                    for a, b in itertools.combinations(keys, 2)))
    for dist, a, b in pairs:
        if dist < args.min_diff:
            print(f"CLOSE   {a} vs {b}: differ in {dist} position(s)")
            problems += 1

    closest = pairs[0] if pairs else None
    if closest:
        print(f"closest pair: {closest[1]} vs {closest[2]} ({closest[0]} positions)")
    print("OK" if not problems else f"{problems} problem(s) flagged")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
