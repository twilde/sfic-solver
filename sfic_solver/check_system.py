#!/usr/bin/env python3
"""Whole-scheme check for master-keyed bittings (7 pins unless the file says otherwise).

Reads a JSON description of the system and reports:
  * per-key problems (parity and adjacent-cut limit for keys and control keys;
    duplicates across all keys)
  * advice on the shape of each key (the file's shape rules: equal adjacent cuts, a depth used
    too often, a key that only goes one way, a master that is too narrow); positions only, not
    counted as problems, and decoded unit keys and retired keys are left out
  * pairs of keys that are too close
  * for each core type, how many keys operate it (intended + false keys)
  * known keys that would operate a core they are NOT meant to operate
  * if the file sets `pinning`: cores that cannot be pinned (chamber by chamber, with
    the reason) and known keys that would operate a core's control shear line
  * with `retired_cores` too: whether each retired core, as described, could have been
    pinned (a warning, not a problem: the description or the rules may be wrong)
  * a rough estimate of the chance that still-undecoded unit keys do the same

Usage:
    ./check_system.py system.json

Config (see system.example.json):
    name           optional name of the key system (printed on the charts by pin_system)
    pins           number of pins (default: the length of pattern, else 7)
    pattern        one E/O per pin (optional; enables parity checks)
    max_step       max adjacent-cut difference (default 5)
    min_diff       flag key pairs differing in fewer positions (default 5, or
                   the pin count if smaller);
                   pairs involving unit keys are skipped unless
                   close_check_units is true (cross-operation is the real test)
    shape          optional object of key shape rules (max_run, max_same_depth,
                   forbid_monotone, master_min_span, min_total_variation; null turns one
                   off); see the README
    unit_prefix    key-name prefix for unit keys (default "unit:")
    unit_count     total number of units, to estimate undecoded-key risk
    keys           {name: bitting} operating keys, including decoded unit keys
    retired_keys   {name: bitting} old keys that must not operate new cores
    control_keys   {name: bitting} control keys (closeness checks only)
    cores          list of {name, change, masters, control}
                   change: key name, wildcard ("unit:*") or list of those
                   masters: list of key names pinned above the change key
                   control: name of the core's control key (needed with pinning)
    pinning        optional pinning system name, such as "A2": turns on the
                   pinning checks
    retired_cores  list of {name, change, masters, control} like cores, for the old
                   installation: masters and control are names in retired_keys

A core accepts any key whose cut at every position equals the change key's
cut or one of its masters' cuts. Exits with status 1 if anything is flagged.
"""
import argparse
import itertools
import sys

from .config import load_or_exit
from .model import distance, operates, options_for
from .pinning import pin_chambers
from .population import (MAX_COVERING_CORES, covering_cores, false_key_share, pinnable_fraction,
                         retired_population)

MAX_LISTED = 30        # lines per list before "... and N more"


def capped(lines):
    """The first MAX_LISTED lines of a list, and a count of the rest."""
    shown = list(lines[:MAX_LISTED])
    if len(lines) > MAX_LISTED:
        shown.append(f"... and {len(lines) - MAX_LISTED} more")
    return shown


def check_retired_cores(cfg):
    """The retired-core section: (lines, warnings).

    The old cores were physically pinned, so every key that sat in one with its
    retired masters and control must be pinnable together. A WARNING means the
    description of the old cores is wrong or the rules are too strict, so it is not
    counted as a problem.
    """
    pool = {**cfg.keys, **cfg.retired_keys}
    found = []
    for core in cfg.retired_cores:
        control = cfg.retired_keys[core["control"]]
        for ch in core["changes"]:
            operating = [pool[ch]] + [cfg.retired_keys[m] for m in core["masters"]]
            for error in pin_chambers(cfg.pinning, operating, control)[1]:
                found.append(f"WARNING   {core['name']} [{ch}], chamber {error.chamber}: "
                             f"{error.reason}")
    lines = capped(found)
    if found:
        lines.append("Either the description of the old cores is wrong or the rules are too "
                     "strict.")
    return lines or ["none"], len(found)


def check_pinning(cfg, everything):
    """The pinning section: (lines, problems) for a file that sets `pinning`.

    UNPINNABLE: a core (one per change key) with a chamber whose cuts cannot be pinned.
    CONTROL: a known key that operates a core's control shear line. Only the control
    bitting itself does, whoever the key is meant for.
    """
    unpinnable, control_lines = [], []
    for core in cfg.cores:
        control = cfg.control_keys[core["control"]]
        for ch in core["changes"]:
            operating = [cfg.keys[ch]] + [cfg.keys[m] for m in core["masters"]]
            for error in pin_chambers(cfg.pinning, operating, control)[1]:
                unpinnable.append(f"UNPINNABLE {core['name']} [{ch}], chamber {error.chamber}: "
                                  f"{error.reason}")
    for core in cfg.cores:
        control = cfg.control_keys[core["control"]]
        for name, cuts in everything.items():
            if name != core["control"] and cuts == control:
                control_lines.append(f"CONTROL   key {name} operates the control shear line "
                                     f"of {core['name']}")
    lines = capped(unpinnable) + capped(control_lines)
    return lines or ["none"], len(unpinnable) + len(control_lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("system", metavar="system.json", help="the system file to check")
    args = ap.parse_args(argv)
    cfg = load_or_exit(args.system)
    space, min_diff = cfg.space, cfg.min_diff
    unit_prefix = cfg.unit_prefix
    keys, retired, control = cfg.keys, cfg.retired_keys, cfg.control_keys
    everything = {**keys, **retired, **control}
    cores = cfg.cores
    problems = warnings = 0

    print("== Key checks ==")
    for name, cuts in {**keys, **control}.items():     # retired keys are exempt
        if space.pattern:
            bad = space.parity_bad(cuts)
            if bad:
                print(f"PARITY    {name}: wrong parity at pin(s) {bad}")
                problems += 1
        if not space.macs_ok(cuts):
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

    if not cfg.shape.is_off():
        print("\n== Key shape: advice only (decoded unit keys and retired keys are not "
              "checked) ==")
        masters = cfg.master_keys
        checked = {**{n: c for n, c in keys.items() if not n.startswith(unit_prefix)}, **control}
        advice = [f"SHAPE     {name}: {cfg.shape.describe(rule, pins)}"
                  for name, cuts in checked.items()
                  for rule, pins in cfg.shape.violations(cuts, name in masters)]
        print("\n".join(capped(advice) or ["none"]))

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

    total_valid = space.total_valid
    print(f"\n== Core operating sets (valid bittings in the whole key space: {total_valid:,}) ==")
    group_p = {}
    for core in cores:
        sizes = []
        for ch in core["changes"]:
            opts = options_for(keys[ch], [keys[m] for m in core["masters"]])
            sizes.append(space.operating_set_size(opts))
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

    if cfg.pinning:
        print(f"\n== Pinning ({cfg.pinning.name}): can each core be built, and does a key "
              f"open a control shear line? ==")
        lines, found = check_pinning(cfg, everything)
        print("\n".join(lines))
        problems += found
        if cfg.retired_cores:
            print("\n== Retired cores: could the old cores, as described, have been pinned? ==")
            lines, warnings = check_retired_cores(cfg)
            print("\n".join(lines))

    unit_count = cfg.unit_count
    if unit_count:
        decoded = sum(1 for n in keys if n.startswith(unit_prefix))
        unknown = unit_count - decoded
        unused = None          # why the retired cores were not used, if they were not
        try:
            population = retired_population(cfg)
        except ValueError:
            population = None
            unused = "no valid bitting could have been pinned in them"
        if cfg.pinning and len(covering_cores(cfg)) > MAX_COVERING_CORES:
            unused = (f"{len(covering_cores(cfg))} of them cover unit keys, and at most "
                      f"{MAX_COVERING_CORES} can be combined exactly")
        print(f"\n== Residual risk from undecoded unit keys ({decoded} of {unit_count} decoded) ==")
        if population is None:
            print("Estimate only: assumes unknown unit keys are random valid bittings.")
            if unused:
                print(f"The retired cores were not used: {unused}.")
        else:
            covering = ", ".join(c["name"] for c in covering_cores(cfg))
            print(f"Estimate only: assumes unknown unit keys sat in the retired core(s) "
                  f"{covering}, so at every position each has a cut that chamber could have "
                  f"been pinned with ({space.population_size(population):,} of "
                  f"{total_valid:,} valid bittings).")
        for core in cores:
            p = group_p[core["name"]]
            if core["is_unit"]:
                pairs = unit_count * (unit_count - 1) - decoded * (decoded - 1)
                masters = [keys[m] for m in core["masters"]]
                p = space.pair_conflict_probability(masters, population)
                expected = pairs * p
                print(f"{core['name']}: about {expected:.1f} unit-to-unit cross-operations expected "
                      f"by chance; re-check after decoding")
                if cfg.pinning:
                    cannot = 1 - pinnable_fraction(space, population or space.uniform(),
                                                   cfg.pinning, masters,
                                                   control[core["control"]])
                    print(f"    {unknown} undecoded unit key(s): about {unknown * cannot:.1f} "
                          f"expected to be unable to take this master and control key "
                          f"({cannot * 100:.0f}%), so their cores would need rekeying")
            else:
                if population is not None:
                    p = sum(false_key_share(space, population,
                                            options_for(keys[ch], [keys[m] for m in core["masters"]]),
                                            [keys[ch]] + [keys[m] for m in core["masters"]])
                            for ch in core["changes"]) / len(core["changes"])
                n_inst = len(core["changes"])
                expected = unknown * p * n_inst
                at_least_one = 1 - (1 - p) ** (unknown * n_inst)
                print(f"{core['name']}: {expected:.2f} unit keys expected to operate it "
                      f"({at_least_one * 100:.0f}% chance at least one does)")

    note = f", {warnings} warning(s)" if warnings else ""
    print(f"\n{'OK' if not problems else str(problems) + ' problem(s) flagged'}{note}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
