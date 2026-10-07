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

Every key the solver chooses also follows the file's shape rules (the optional `shape`
object; by default no equal adjacent cuts, no depth used more than three times, no key
whose cuts only go one way, and a master spanning at least six depths). They filter the
candidates and are never relaxed: if no bitting for a key follows them, the key is left
null, the output says which rules turned the draws down, and the full check is skipped
(docs/designs/key-shape-rules.md).

Method: random search plus single-cut hill climbing, scoring each candidate
exactly. Each key has only a few tens of thousands of valid bittings, so a few
thousand trials per key is plenty.
"""
import argparse
import collections
import json
import os
import random
import sys
from functools import lru_cache

from . import check_system, model
from .config import load_or_exit
from .joint import JointSet, allowed_tuples, bittings, why_none
from .model import distance, operates
from .pinning import pin_chambers
from .population import (MAX_COVERING_CORES, covering_cores, false_key_share, pinnable_fraction,
                         retired_population)

HARD = 1_000_000.0
CLOSE_WEIGHT = 1_000.0
MAX_JOINT_KEYS = 3             # most unknown keys sharing cores that are built together: each
                               # position lists up to 10 ** this digit combinations
MAX_SHAPE_REJECTS = 20_000     # draws turned down by the shape rules before a key is given up
                               # on (at least 50 for each candidate asked for)
SHAPE_OFF = model.ShapeRules(max_run=None, max_same_depth=None, forbid_monotone=False,
                             master_min_span=None, min_total_variation=None)
UNPINNABLE_WEIGHT = 1.0        # one undecoded unit key that cannot take the master counts as
                               # one expected cross-operation; with the scale of the two terms
                               # it makes avoiding rekeyed unit cores the primary goal


class NoShapedBitting(Exception):
    """No bitting that follows the shape rules was found; `rejected` counts, by rule, the
    draws that broke one."""

    def __init__(self, rejected):
        super().__init__(shape_reason(rejected))
        self.rejected = rejected


MOST_DRAWS = 0.8       # a key that broke a rule in this share of the draws is the one to blame


def tally_broken(rejected, broken):
    """Count a draw's broken (key, rule) pairs: each pair once, and the key itself once
    (as (key, None)) however many rules it broke."""
    rejected.update(broken)
    rejected.update({(k, None) for k, _ in broken})


def group_reasons(group, rejected, draws):
    """Why no combination for a group of keys built together follows the shape rules, from
    the counts of the `draws` turned down (see tally_broken): one summary for the group and
    one reason for each key. Only a key that broke a rule in most of the draws is blamed; a
    key that did not says whose rules it waited for, since any random key breaks one now
    and then."""
    tallies = {k: collections.Counter({rule: n for (key, rule), n in rejected.items()
                                       if key == k and rule}) for k in group}
    blamed = [k for k in group if draws and rejected.get((k, None), 0) >= MOST_DRAWS * draws]
    shown = blamed or [k for k in group if tallies[k]]
    if len(group) == 1:
        summary = shape_reason(tallies[group[0]])
    elif shown:
        summary = "draws broke " + "; ".join(
            f"{k}: " + shape_reason(tallies[k]).removeprefix("draws broke ") for k in shown)
    else:
        summary = shape_reason(collections.Counter())
    reasons = {}
    for k in group:
        if blamed and k not in blamed:
            reasons[k] = f"built together with {', '.join(blamed)}, which has none: {summary}"
        elif len(group) == 1 or k in blamed:
            reasons[k] = shape_reason(tallies[k])
        else:
            reasons[k] = summary
    return summary, reasons


def shape_reason(rejected):
    """Which rules turned draws down, for a message."""
    if not rejected:
        return "none of the bittings that could be drawn follows them"
    return "draws broke " + ", ".join(f"{name} {count:,}" for name, count in rejected.most_common())


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

        # Shape rules: they apply to every key the solver chooses; a master is a key that is in
        # the masters of any core. `no_shape` holds the keys for which no bitting was found.
        self.shape = cfg.shape
        self.shape_on = cfg.shape != SHAPE_OFF
        self.masters = {m for core in cfg.cores for m in core["masters"]}
        self.no_shape = {}                    # key -> why no bitting follows the shape rules

        # Pinning: only for files that set it. The population of undecoded unit keys comes
        # from the retired cores when they describe the units, and `population_note` says
        # why not when they cannot be used (the checker prints the same line).
        self.pinning = cfg.pinning
        self.population = None
        self.population_note = None
        self.impossible = []                  # (keys, reason) for groups with no pinnable bitting
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

    # -- joint construction (pinning only) ---------------------------------------
    def joint_groups(self):
        """The unknown keys, grouped so that keys sharing a core (as change key, master or
        control key) are in the same group: a core's pinning couples exactly those."""
        parent = {k: k for k in self.unknown}

        def find(k):
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k

        for core in self.cores:
            names = [n for n in (*core["changes"], *core["masters"], core["control"])
                     if n in parent]
            for n in names[1:]:
                parent[find(n)] = find(names[0])
        groups = {}
        for k in self.unknown:
            groups.setdefault(find(k), []).append(k)
        return list(groups.values())

    def pin_constraints(self, group):
        """(operating key names, control key name) for each core and change key that has a
        key of `group` in it: the chambers whose pinning the group's cuts decide."""
        found = []
        for core in self.cores:
            for ch in core["changes"]:
                ops = [ch] + core["masters"]
                if any(n in group for n in (*ops, core["control"])):
                    found.append((ops, core["control"]))
        return found

    def pinnable_set(self, group):
        """(JointSet of the group's pinnable bittings, the digit tuples it was built from)."""
        known = {n: c for n, c in self.assign.items() if n not in group}
        allowed = allowed_tuples(self.space, self.pinning, group, self.pin_constraints(group),
                                 known)
        return JointSet(allowed, self.space.max_step), allowed

    # -- candidate generation -------------------------------------------------
    def draw_cuts(self, rng):
        return tuple(rng.choice(self.space.digits[p]) for p in range(self.space.pins))

    def shape_ok(self, k, cuts):
        return self.shape.ok(cuts, k in self.masters)

    def shaped_candidates(self, rng, k, n):
        """Up to `n` random MACS-valid bittings for key `k` that follow the shape rules, and
        the count, by rule, of the draws they turned down. Fewer than `n` (maybe none) if the
        rules turn down almost everything."""
        found, rejected, rejects = [], collections.Counter(), 0
        limit = max(50 * n, MAX_SHAPE_REJECTS)
        while len(found) < n:
            cuts = self.draw_cuts(rng)
            if not self.space.macs_ok(cuts):
                continue
            broken = self.shape.violations(cuts, k in self.masters)
            if broken:
                rejected.update(name for name, _ in broken)
                rejects += 1
                if rejects > limit:
                    break
                continue
            found.append(cuts)
        return found, rejected

    def random_candidate(self, rng, k=None):
        """A random MACS-valid bitting; for key `k`, one that follows the shape rules too
        (NoShapedBitting if none turns up)."""
        if k is None:
            while True:
                cuts = self.draw_cuts(rng)
                if self.space.macs_ok(cuts):
                    return cuts
        found, rejected = self.shaped_candidates(rng, k, 1)
        if not found:
            raise NoShapedBitting(rejected)
        return found[0]

    def neighbors(self, cuts, k=None):
        """The MACS-valid bittings one cut away; for key `k`, only those that follow the shape
        rules."""
        for p in range(self.space.pins):
            for d in self.space.digits[p]:
                if d != cuts[p]:
                    cand = cuts[:p] + (d,) + cuts[p + 1:]
                    if self.space.macs_ok(cand) and (k is None or self.shape_ok(k, cand)):
                        yield cand

    def joint_broken(self, group, cand):
        """The shape rules broken by the keys of a group, as (key, rule) pairs, for a drawn
        digit-tuple list `cand` (see joint.bittings)."""
        return [(k, name) for k, cuts in zip(group, bittings(cand))
                for name, _ in self.shape.violations(cuts, k in self.masters)]

    def shaped_draws(self, pinnable, group, rng, trials):
        """Up to `trials` draws from the pinnable set whose keys all follow the shape rules, the
        count of what the turned-down draws broke (see tally_broken), and how many draws were
        made."""
        chosen, rejected, rejects, made = [], collections.Counter(), 0, 0
        limit = max(50 * trials, MAX_SHAPE_REJECTS)
        while len(chosen) < trials:
            cand = pinnable.draw(rng)
            made += 1
            broken = self.joint_broken(group, cand)
            if broken:
                tally_broken(rejected, broken)
                rejects += 1
                if rejects > limit:
                    break
                continue
            chosen.append(cand)
        return chosen, rejected, made

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
                total += UNPINNABLE_WEIGHT * unknown * self.cannot_take(core, masters)
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

    def cannot_take(self, core, masters):
        """The share of undecoded unit keys that cannot be pinned in a unit core with these
        masters and the core's control key (which must be assigned)."""
        population = self.uniform if self.population is None else self.population
        return 1 - pinnable_fraction(self.space, population, self.pinning, masters,
                                     self.assign[core["control"]])

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


def solve_jointly(prob, group, trials, rng, report):
    """Pick the bittings of a group of unknown keys that share cores, drawing them only from
    those that leave every involved chamber pinnable (all of them when there are few enough).
    Returns False, with the reason noted on the problem, if there are none."""
    names = ", ".join(group)
    pinnable, allowed = prob.pinnable_set(group)
    if not pinnable.count:
        reason = why_none(allowed)
        prob.impossible.append((group, reason))
        print(f"  {names}: NO bitting can be pinned with the known keys: {reason}")
        return False
    rejected = collections.Counter()
    if pinnable.count <= trials:
        every = list(pinnable.enumerate())
        draws = len(every)
        chosen = []
        for cand in every:
            broken = prob.joint_broken(group, cand)
            if broken:
                tally_broken(rejected, broken)
            else:
                chosen.append(cand)
        how = ("scored all of them" if len(chosen) == len(every)
               else f"{len(chosen):,} follow the shape rules; scored all of those")
    else:
        chosen, rejected, draws = prob.shaped_draws(pinnable, group, rng, trials)
        chosen = list(dict((tuple(c), c) for c in chosen).values())
        how = f"scored {len(chosen)} drawn from them"
        if prob.shape_on:
            how += " that follow the shape rules"
    noun = "bitting" if len(group) == 1 else "combination"
    print(f"  {names}: {pinnable.count:,} pinnable {noun}{'' if pinnable.count == 1 else 's'} "
          f"with the known keys; {how}")
    if not chosen:
        summary, reasons = group_reasons(group, rejected, draws)
        prob.no_shape.update(reasons)
        print(f"  {names}: NO pinnable {noun} follows the shape rules ({summary})")
        return True
    scored = []
    for i, cand in enumerate(chosen):
        for k, cuts in zip(group, bittings(cand)):
            prob.assign[k] = cuts
        scored.append((sum(prob.score_key(k, prob.assign[k]) for k in group), i))
    scored.sort()
    best_score, best = scored[0]
    clean = sum(1 for sc, _ in scored if sc < HARD) / len(scored)
    for k, cuts in zip(group, bittings(chosen[best])):
        prob.assign[k] = cuts
        report[k] = (clean, prob.score_key(k, cuts))
        print(f"  {k}: picked {''.join(map(str, cuts))} "
              f"({clean * 100:.0f}% of the pinnable candidates were free of other hard conflicts)")
    return True


def solve(prob, trials, sweeps, rng):
    report = {}
    handled = set()
    if prob.pinning:
        for group in prob.joint_groups():
            if len(group) > MAX_JOINT_KEYS:
                print(f"  {', '.join(group)} share cores and are more than the {MAX_JOINT_KEYS} "
                      f"keys that can be built together: searching one key at a time")
            elif solve_jointly(prob, group, trials, rng, report):
                handled.update(group)
    for k in prob.unknown:
        if k in handled:
            continue
        candidates, rejected = prob.shaped_candidates(rng, k, trials)
        if not candidates:
            prob.no_shape[k] = shape_reason(rejected)
            print(f"  {k}: NO bitting found that follows the shape rules "
                  f"({prob.no_shape[k]})")
            continue
        scored = [(prob.score_key(k, c), c) for c in candidates]
        scored.sort()
        best_score, best = scored[0]
        clean = sum(1 for sc, _ in scored if sc < HARD) / len(scored)
        prob.assign[k] = best
        report[k] = (clean, best_score)
        print(f"  {k}: picked {''.join(map(str, best))} "
              f"({clean * 100:.0f}% of random candidates were free of hard conflicts)")

    for sweep in range(sweeps):
        improved = False
        order = [k for k in prob.unknown if k not in prob.no_shape]
        rng.shuffle(order)
        for k in order:
            cur = prob.assign[k]
            cur_score = prob.score_key(k, cur)
            best_score, best = cur_score, cur
            pool = list(prob.neighbors(cur, k)) + prob.shaped_candidates(rng, k, trials // 2)[0]
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


def failed_keys(prob):
    """The unknown keys whose chosen bitting still has a hard conflict, as (name, count)
    pairs: the count is how many hard penalties its score carries (a cross-operation, a
    duplicate or an unpinnable chamber each count once, so a conflict shared by two keys
    is counted for both). Keys that have no pinnable bitting at all are left out: they
    are reported as that, since running the search again cannot help."""
    none_exist = {k for group, _ in prob.impossible for k in group}
    failed = []
    for k in prob.unknown:
        if k in prob.no_shape:
            continue
        hard = int(prob.score_key(k, prob.assign[k]) // HARD)
        if hard and k not in none_exist:
            failed.append((k, hard))
    return failed


def not_solved_lines(prob, check="below"):
    """The lines that say the search failed, none when it did not. `check` says where the
    full check of the result is, for the lines to point at: they are printed before it and
    again after it."""
    lines = []
    for k, reason in prob.no_shape.items():
        lines.append(f"NOT SOLVED: no bitting for {k} follows the shape rules ({reason}), so "
                     f"{k} is left null and running it again will not help; change or turn off "
                     f"a rule in the `shape` object of the system file.")
    for group, reason in prob.impossible:
        lines.append(f"NOT SOLVED: no bitting for {', '.join(group)} can be pinned with the "
                     f"known keys ({reason}), so running it again will not help; a known key "
                     f"has to change. See the check {check}.")
    failed = failed_keys(prob)
    if failed:
        named = ", ".join(f"{k} ({n})" for k, n in failed)
        lines.append(f"NOT SOLVED: the result still has hard conflicts involving {named}. Run it "
                     f"again (a different random draw may do better), or see the check {check}.")
    return lines


def unit_pair_summary(prob, rng, samples=300):
    """Compare the chosen unit-core masters with typical random choices."""
    for core in prob.cores:
        if not core["is_unit"] or not prob.unit_count:
            continue
        unknown_masters = [m for m in core["masters"] if m in prob.unknown]
        if not unknown_masters or any(m not in prob.assign for m in core["masters"]):
            continue
        chosen = prob.space.pair_conflict_probability([prob.assign[m] for m in core["masters"]],
                                                      prob.population)
        # With shape rules on, the typical master is drawn from the keys that follow them, found
        # once for each master (a tight rule set can leave few: they are reused in turn) and
        # not by 300 separate bounded searches; if there are none the summary is left out.
        # With every rule off the draws are the unfiltered ones, as they always were.
        pools = {}
        if prob.shape_on:
            for m in unknown_masters:
                pools[m] = prob.shaped_candidates(rng, m, samples)[0]
        if not all(pools.values()):
            continue
        total = cannot_total = 0.0
        for i in range(samples):
            masters = [(pools[m][i % len(pools[m])] if m in pools else prob.random_candidate(rng))
                       if m in unknown_masters else prob.assign[m]
                       for m in core["masters"]]
            total += prob.space.pair_conflict_probability(masters, prob.population)
            if prob.pinning:
                cannot_total += prob.cannot_take(core, masters)
        typical = total / samples
        pairs = prob.unit_count * (prob.unit_count - 1)
        print(f"\nUnit-to-unit cross-operation by chance (all {prob.unit_count} units): "
              f"about {pairs * chosen:.1f} pairs with the chosen master vs "
              f"{pairs * typical:.1f} for a typical random one.")
        if prob.pinning:
            decoded = sum(1 for n in prob.assign if n.startswith(prob.unit_prefix))
            unknown = prob.unit_count - decoded
            mine = prob.cannot_take(core, [prob.assign[m] for m in core["masters"]])
            print(f"The solver weighed this first: the undecoded unit keys that cannot take the "
                  f"chosen master and control key are about {unknown * mine:.1f} of {unknown} "
                  f"({mine * 100:.0f}%) vs {cannot_total / samples * 100:.0f}% for a typical "
                  f"random one, so a master with more chance cross-operation can be the better one.")


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
            if name in prob.assign and name in prob.unknown:
                raw[label][name] = "".join(map(str, prob.assign[name]))
    out = args.out or os.path.splitext(args.config)[0] + ".solved.json"
    with open(out, "w") as f:
        json.dump(raw, f, indent=2)
    for line in not_solved_lines(prob):
        print(f"\n{line}")
    if prob.no_shape:
        print(f"\nWrote {out}. The full check is skipped: {', '.join(prob.no_shape)} still "
              f"{'has' if len(prob.no_shape) == 1 else 'have'} no bitting, so the file is not "
              f"complete.")
    else:
        print(f"\nWrote {out}. Full check of the result:\n")
        sys.stdout.flush()
        check_system.main([out])  # report only; its exit status is not ours (as before)
    for line in not_solved_lines(prob, "above"):
        print(f"\n{line}")
    return 0     # exit status 0 whenever a result was written (README); the verdict is the line


if __name__ == "__main__":
    sys.exit(main())
