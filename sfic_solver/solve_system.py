#!/usr/bin/env python3
"""Fill in unknown bittings in a system.json, minimizing conflict risk.

Same file format as check_system.py, except any key whose bitting is null is
chosen by this script. Known keys (including decoded unit keys) are never
changed. Typical uses:

  * leave "unit_master" (and control keys) null and solve for them against
    the unit keys decoded so far
  * leave everything null to generate a whole new system

Usage:
    ./solve_system.py system.json                  # writes system.solved.json
    ./solve_system.py system.json --out mine.json --trials 3000 --seed 1

What it optimizes, in priority order:
  1. No known key operates a core it is not meant to operate (hard rule)
  2. No duplicate bittings; non-unit keys at least min_diff positions apart
  3. Lowest expected number of chance cross-operations involving unit keys
     you have not decoded yet (needs unit_count in the config)

If the file sets `pinning`, a core that cannot be pinned (a chamber whose cuts
leave a pin outside the pinning system's sizes) is a hard conflict like a cross-
operation, and the expected number of undecoded unit keys that cannot be pinned
under a unit master and control key is added to the score of item 3 with a
weight of one (docs/designs/pinnable-solving.md). The undecoded keys are then
taken from the retired cores when they describe the units.

Method: random search plus single-cut hill climbing, scoring each candidate
exactly. Each key has only a few tens of thousands of valid bittings, so a few
thousand trials per key is plenty.
"""
import argparse
import json
import os
import random
import sys
from functools import lru_cache

from . import check_system, model
from .config import load_or_exit
from .model import distance, operates
from .pinning import pin_chambers
from .population import (MAX_COVERING_CORES, covering_cores, false_key_share, pinnable_fraction,
                         retired_population)

HARD = 1_000_000.0
CLOSE_WEIGHT = 1_000.0
UNPINNABLE_WEIGHT = 1.0        # one undecoded unit key that cannot take the master counts as
                               # one expected cross-operation; with the scale of the two terms
                               # it makes avoiding rekeyed unit cores the primary goal


@lru_cache(maxsize=None)
def cached_options(change, masters):
    return tuple(tuple(o) for o in model.options_for(change, masters))


class Problem:
    def __init__(self, cfg):
        self.space = cfg.space
        self.min_diff = cfg.min_diff
        self.unit_prefix = cfg.unit_prefix
        self.unit_count = cfg.unit_count

        self.assign = {}
        self.unknown = []
        self.control = set(cfg.control_keys)
        self.retired = set(cfg.retired_keys)
        for section in (cfg.keys, cfg.retired_keys, cfg.control_keys):
            for name, cuts in section.items():
                if cuts is None:
                    self.unknown.append(name)
                else:
                    self.assign[name] = cuts
        self.cores = cfg.cores

        # Pinning: only for files that set it. The population of undecoded unit keys comes
        # from the retired cores when they describe the units, and `population_note` says
        # why not when they cannot be used (the checker prints the same line).
        self.pinning = cfg.pinning
        self.population = None
        self.population_note = None
        self.uniform = self.space.uniform()
        if self.pinning:
            if len(covering_cores(cfg)) > MAX_COVERING_CORES:
                self.population_note = (f"{len(covering_cores(cfg))} of them cover unit keys, "
                                        f"and at most {MAX_COVERING_CORES} can be combined exactly")
            else:
                try:
                    self.population = retired_population(cfg)
                except ValueError:
                    self.population_note = "no valid bitting could have been pinned in them"

    # -- candidate generation -------------------------------------------------
    def random_candidate(self, rng):
        while True:
            cuts = tuple(rng.choice(self.space.digits[p]) for p in range(self.space.pins))
            if self.space.macs_ok(cuts):
                return cuts

    def neighbors(self, cuts):
        for p in range(self.space.pins):
            for d in self.space.digits[p]:
                if d != cuts[p]:
                    cand = cuts[:p] + (d,) + cuts[p + 1:]
                    if self.space.macs_ok(cand):
                        yield cand

    # -- scoring (only terms that depend on key k) -----------------------------
    def expected_unknown_conflicts(self, core):
        if not self.unit_count:
            return 0.0
        decoded = sum(1 for n in self.assign if n.startswith(self.unit_prefix))
        unknown = self.unit_count - decoded
        if unknown <= 0:
            return 0.0
        if core["is_unit"]:
            masters = [self.assign[m] for m in core["masters"]]
            p = self.space.pair_conflict_probability(masters, self.population)
            total = (self.unit_count * (self.unit_count - 1) - decoded * (decoded - 1)) * p
            if self.pinning and core["control"] in self.assign:
                cannot = 1 - pinnable_fraction(
                    self.space, self.uniform if self.population is None else self.population,
                    self.pinning, masters, self.assign[core["control"]])
                total += UNPINNABLE_WEIGHT * unknown * cannot
            return total
        total = 0.0
        for ch in core["changes"]:
            names = [ch] + core["masters"]
            if any(n not in self.assign for n in names):
                continue
            opts = cached_options(self.assign[ch], tuple(self.assign[m] for m in core["masters"]))
            if self.population is not None:
                total += unknown * false_key_share(self.space, self.population, opts,
                                                   [self.assign[n] for n in names])
                continue
            size = self.space.operating_set_size(opts)
            total += unknown * max(size - len(names), 0) / self.space.total_valid
        return total

    def unpinnable_chambers(self, core, ch):
        """How many chambers of the core with change key `ch` cannot be pinned, with the keys
        assigned so far (0 while any of its keys, or its control key, is unassigned)."""
        names = [ch] + core["masters"]
        if any(n not in self.assign for n in names) or core["control"] not in self.assign:
            return 0
        operating = [self.assign[n] for n in names]
        return len(pin_chambers(self.pinning, operating, self.assign[core["control"]])[1])

    def score_key(self, k, cuts):
        previous = self.assign.get(k)
        self.assign[k] = cuts
        try:
            s = 0.0
            is_unit_key = k.startswith(self.unit_prefix)
            for n, other in self.assign.items():
                if n == k:
                    continue
                d = distance(cuts, other)
                if d == 0:
                    s += HARD
                elif (d < self.min_diff and not is_unit_key
                      and not n.startswith(self.unit_prefix)):
                    s += CLOSE_WEIGHT * (self.min_diff - d)
            for core in self.cores:
                involves = False
                for ch in core["changes"]:
                    names = [ch] + core["masters"]
                    if any(n not in self.assign for n in names):
                        continue
                    opts = cached_options(self.assign[ch],
                                          tuple(self.assign[m] for m in core["masters"]))
                    if self.pinning and (k in names or k == core["control"]):
                        involves = True
                        s += HARD * self.unpinnable_chambers(core, ch)
                    if k in names:
                        involves = True
                        for n, other in self.assign.items():
                            if n not in names and n not in self.control and operates(other, opts):
                                s += HARD
                    elif k not in self.control and operates(cuts, opts):
                        s += HARD
                if involves:
                    s += self.expected_unknown_conflicts(core)
            return s
        finally:
            if previous is None:
                del self.assign[k]
            else:
                self.assign[k] = previous


def solve(prob, trials, sweeps, rng):
    report = {}
    for k in prob.unknown:
        scored = [(prob.score_key(k, c), c) for c in
                  (prob.random_candidate(rng) for _ in range(trials))]
        scored.sort()
        best_score, best = scored[0]
        clean = sum(1 for sc, _ in scored if sc < HARD) / len(scored)
        prob.assign[k] = best
        report[k] = (clean, best_score)
        print(f"  {k}: picked {''.join(map(str, best))} "
              f"({clean * 100:.0f}% of random candidates were free of hard conflicts)")

    for sweep in range(sweeps):
        improved = False
        order = prob.unknown[:]
        rng.shuffle(order)
        for k in order:
            cur = prob.assign[k]
            cur_score = prob.score_key(k, cur)
            best_score, best = cur_score, cur
            pool = list(prob.neighbors(cur)) + [prob.random_candidate(rng)
                                                for _ in range(trials // 2)]
            for cand in pool:
                s = prob.score_key(k, cand)
                if s < best_score - 1e-9:
                    best_score, best = s, cand
            if best != cur:
                prob.assign[k] = best
                improved = True
                print(f"  sweep {sweep + 1}: {k} improved to {''.join(map(str, best))} "
                      f"(score {best_score:.3f})")
        if not improved:
            break
    return report


def unit_pair_summary(prob, rng, samples=300):
    """Compare the chosen unit-core masters with typical random choices."""
    for core in prob.cores:
        if not core["is_unit"] or not prob.unit_count:
            continue
        unknown_masters = [m for m in core["masters"] if m in prob.unknown]
        if not unknown_masters:
            continue
        chosen = prob.space.pair_conflict_probability([prob.assign[m] for m in core["masters"]],
                                                      prob.population)
        total = 0.0
        for _ in range(samples):
            masters = [prob.random_candidate(rng) if m in unknown_masters else prob.assign[m]
                       for m in core["masters"]]
            total += prob.space.pair_conflict_probability(masters, prob.population)
        typical = total / samples
        pairs = prob.unit_count * (prob.unit_count - 1)
        print(f"\nUnit-to-unit cross-operation by chance (all {prob.unit_count} units): "
              f"about {pairs * chosen:.1f} pairs with the chosen master vs "
              f"{pairs * typical:.1f} for a typical random one.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--out", help="output file (default: <config>.solved.json)")
    ap.add_argument("--trials", type=int, default=2000,
                    help="random candidates per unknown key (default 2000)")
    ap.add_argument("--sweeps", type=int, default=3,
                    help="improvement passes over all unknown keys (default 3)")
    ap.add_argument("--seed", type=int,
                    help="reproducible run (default: system randomness, better for real keys)")
    args = ap.parse_args(argv)

    cfg = load_or_exit(args.config, allow_null=True)
    prob = Problem(cfg)
    if not prob.unknown:
        sys.exit("no unknown (null) keys in the config; use check_system.py instead")
    rng = random.Random(args.seed) if args.seed is not None else random.SystemRandom()

    print(f"Solving for {len(prob.unknown)} unknown key(s): {', '.join(prob.unknown)}")
    if prob.population is not None:
        print("Undecoded unit keys are assumed to have sat in the retired core(s) "
              + ", ".join(c["name"] for c in covering_cores(cfg)) + ".")
    elif prob.population_note:
        print(f"The retired cores were not used: {prob.population_note}.")
    solve(prob, args.trials, args.sweeps, rng)
    unit_pair_summary(prob, rng)

    raw = cfg.raw
    for label in ("keys", "control_keys"):
        for name in raw.get(label, {}):
            if name in prob.unknown:
                raw[label][name] = "".join(map(str, prob.assign[name]))
    out = args.out or os.path.splitext(args.config)[0] + ".solved.json"
    with open(out, "w") as f:
        json.dump(raw, f, indent=2)
    print(f"\nWrote {out}. Full check of the result:\n")
    sys.stdout.flush()
    check_system.main([out])      # report only; its exit status is not ours (as before)
    return 0


if __name__ == "__main__":
    sys.exit(main())
