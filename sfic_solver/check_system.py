#!/usr/bin/env python3
"""Whole-scheme check for master-keyed bittings (7 pins unless the file says otherwise).

Reads a JSON description of the system and reports:
  * per-key problems (parity and adjacent-cut limit for keys and control keys;
    duplicates across all keys)
  * pairs of keys that are too close
  * for each core type, how many keys operate it (intended + false keys)
  * known keys that would operate a core they are NOT meant to operate
  * a rough estimate of the chance that still-undecoded unit keys do the same

Usage:
    ./check_system.py system.json

Config (see system.example.json):
    pins           number of pins (default: the length of pattern, else 7)
    pattern        one E/O per pin (optional; enables parity checks)
    max_step       max adjacent-cut difference (default 5)
    min_diff       flag key pairs differing in fewer positions (default 5, or
                   the pin count if smaller);
                   pairs involving unit keys are skipped unless
                   close_check_units is true (cross-operation is the real test)
    unit_prefix    key-name prefix for unit keys (default "unit:")
    unit_count     total number of units, to estimate undecoded-key risk
    keys           {name: bitting} operating keys, including decoded unit keys
    retired_keys   {name: bitting} old keys that must not operate new cores
    control_keys   {name: bitting} control keys (closeness checks only)
    cores          list of {name, change, masters}
                   change: key name, wildcard ("unit:*") or list of those
                   masters: list of key names pinned above the change key

A core accepts any key whose cut at every position equals the change key's
cut or one of its masters' cuts. Exits with status 1 if anything is flagged.
"""
import itertools
import sys

from .config import load_or_exit
from .model import (count_valid, distance, macs_ok, operates, operating_set_size,
                    options_for, pair_conflict_probability, parity_bad)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        sys.exit(__doc__)
    cfg = load_or_exit(argv[0])
    pattern, max_step, min_diff = cfg.pattern, cfg.max_step, cfg.min_diff
    unit_prefix = cfg.unit_prefix
    keys, retired, control = cfg.keys, cfg.retired_keys, cfg.control_keys
    everything = {**keys, **retired, **control}
    cores = cfg.cores
    problems = 0

    print("== Key checks ==")
    for name, cuts in {**keys, **control}.items():     # retired keys are exempt
        if pattern:
            bad = parity_bad(cuts, pattern)
            if bad:
                print(f"PARITY    {name}: wrong parity at pin(s) {bad}")
                problems += 1
        if not macs_ok(cuts, max_step):
            print(f"MACS      {name}: adjacent cuts too far apart")
            problems += 1
    by_bitting = {}
    for name, cuts in everything.items():
        by_bitting.setdefault(cuts, []).append(name)
    for cuts, names in by_bitting.items():
        if len(names) > 1:
            print(f"DUPLICATE {', '.join(names)} share bitting {''.join(map(str, cuts))}")
            problems += 1
    print("done")

    print(f"\n== Closeness (non-unit keys differing in fewer than {min_diff} positions) ==")
    scope = {n: c for n, c in everything.items()
             if cfg.close_check_units or not n.startswith(unit_prefix)}
    close = sorted((distance(a, b), na, nb)
                   for (na, a), (nb, b) in itertools.combinations(scope.items(), 2)
                   if distance(a, b) < min_diff and a != b)
    for dist, na, nb in close[:30]:
        print(f"CLOSE     {na} vs {nb}: {dist} position(s)")
    if len(close) > 30:
        print(f"... and {len(close) - 30} more")
    problems += len(close)
    if not close:
        print("none")

    total_valid = count_valid(pattern, max_step, cfg.pins)
    print(f"\n== Core operating sets (valid bittings in the whole key space: {total_valid:,}) ==")
    group_p = {}
    for core in cores:
        sizes = []
        for ch in core["changes"]:
            opts = options_for(keys[ch], [keys[m] for m in core["masters"]])
            sizes.append(operating_set_size(opts, max_step))
        intended = 1 + len(core["masters"])
        mean = sum(sizes) / len(sizes)
        group_p[core["name"]] = max(mean - intended, 0) / total_valid
        span = f"{min(sizes):,}" if min(sizes) == max(sizes) else f"{min(sizes):,} to {max(sizes):,}"
        levels = " + ".join(["change"] + core["masters"])
        print(f"{core['name']}: {len(core['changes'])} core(s), {levels}")
        print(f"    {span} operating bittings, of which {intended} intended "
              f"({group_p[core['name']] * 100:.2f}% of all valid bittings are false keys)")

    print("\n== Cross-operation among known keys ==")
    test_keys = {**keys, **retired}
    found = 0
    for core in cores:
        for ch in core["changes"]:
            intended = {ch, *core["masters"]}
            opts = options_for(keys[ch], [keys[m] for m in core["masters"]])
            for name, cuts in test_keys.items():
                if name not in intended and operates(cuts, opts):
                    kind = "retired key " if name in retired else "key "
                    print(f"CROSS     {kind}{name} operates {core['name']} [{ch}]")
                    found += 1
    problems += found
    if not found:
        print("none")

    unit_count = cfg.unit_count
    if unit_count:
        decoded = sum(1 for n in keys if n.startswith(unit_prefix))
        unknown = unit_count - decoded
        print(f"\n== Residual risk from undecoded unit keys ({decoded} of {unit_count} decoded) ==")
        print("Estimate only: assumes unknown unit keys are random valid bittings.")
        for core in cores:
            p = group_p[core["name"]]
            if core["is_unit"]:
                pairs = unit_count * (unit_count - 1) - decoded * (decoded - 1)
                p = pair_conflict_probability([keys[m] for m in core["masters"]],
                                              pattern, max_step, total_valid, cfg.pins)
                expected = pairs * p
                print(f"{core['name']}: about {expected:.1f} unit-to-unit cross-operations expected "
                      f"by chance; re-check after decoding")
            else:
                n_inst = len(core["changes"])
                expected = unknown * p * n_inst
                at_least_one = 1 - (1 - p) ** (unknown * n_inst)
                print(f"{core['name']}: {expected:.2f} unit keys expected to operate it "
                      f"({at_least_one * 100:.0f}% chance at least one does)")

    print(f"\n{'OK' if not problems else str(problems) + ' problem(s) flagged'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
