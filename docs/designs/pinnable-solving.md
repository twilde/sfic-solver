# Solving for pinnable systems (core pinning, step 5)

Status: Accepted

This document describes step 5 of [core pinning](core-pinning.md): making the
solver, the residual-risk estimate and the generator work for a system that sets
`pinning` and has no parity pattern. It was written before any code and has been
accepted, including its changes to what the solver scores (D6) and the weight of
one for the new term, confirmed with the scale of both terms in view (see "What
changes in the solver"). Files that do not set `pinning` are unaffected throughout; a
test will show that their output is byte for byte what it is today.

## Why do this

Until step 4 the tools could only say whether keys are safe, and parity was the
rule that made every core buildable without anyone checking: with every cut of a
position the same parity, two cuts at one position never differ by exactly one, so
no master pin is the size-1 pin that does not exist. Step 4 lets a system file
say `pinning` and have the checker test the real rule instead, which is the point
of the whole design, since parity costs about a hundredfold of the key space.

The solver and the estimate were written for the parity world, and three things in
them no longer hold once the pattern is dropped.

1. **The solver does not know a core must be buildable.** It will happily choose a
   unit master that sits one cut from a decoded unit key at some position. The
   checker now flags that as `UNPINNABLE`, but only after the solver has written
   its answer. Under parity this could not happen; without it, it is the first
   thing a random master does.
2. **The estimate assumes the undecoded unit keys are uniform among valid
   bittings.** With a pattern that was a modest guess. Without one it is wrong in a
   way that matters, because the old cores of a rekeyed building had to be
   pinnable, so the undecoded keys are not uniform: they avoid the neighbours of
   whatever retired masters were pinned with them (core-pinning.md, "What the
   retired keys tell us"). That is evidence, and step 4 already reads it.
3. **The estimate has no figure for the new risk.** Beside "an undecoded unit key
   operates a core it should not" there is now "an undecoded unit key cannot be
   pinned under this master at all", which means that unit's core cannot take the
   master and has to be rekeyed. Parity made that probability zero, so nobody
   needed to count it.

## What the numbers say

Before proposing weights, here is what the new figure looks like, because it
decides whether the work is worth doing. These are measured on the fake system in
`tests/fixtures/pinning.json` with its parity pattern removed (seven pins, a retired
master and control, three decoded units, 97 undecoded) by a throwaway script that is
not in the repository. They are illustrations of scale, not claims about any real
system. The script's draws are seeded (300 random masters from seed 1, fifteen
hill-climbs from fixed seeds), and the tests of the real implementation will use
seeded draws of their own and assert ranges, not these figures. Each row names the
population the undecoded unit keys are drawn from, because the answers differ a lot:
"uniform" is the only population the tools had before step 4, and "retired core" is
the one this document proposes, where a unit key must be one the old core could have
been pinned with (549,745 of the 3,027,314 valid bittings here).

| Key space | Population | Unit master chosen | Undecoded unit keys that cannot take it |
| --- | --- | --- | --- |
| Parity pattern `OOEOEOE` (28,384 valid) | retired core | any valid key | 0% (parity guarantees it; 0% in every draw tried) |
| No pattern | uniform | a random valid key | mean 79% (61% to 88%) |
| No pattern | uniform | best of 15 hill-climbs, with or without the closeness rule | 42% (every restart) |
| No pattern | retired core | a random valid key | mean 80% (52% to 92%) |
| No pattern | retired core | best of 15 hill-climbs, ignoring closeness | 0% (median restart 8%) |
| No pattern | retired core | best of 15 hill-climbs, with the closeness rule (at least 5 positions from every other non-unit key, retired keys included) | 24% (median restart 34%) |

Three things follow. Dropping parity makes the master matter: a careless choice
leaves about four undecoded units in five unable to take it. The retired-core
population is what makes a low figure reachable at all. The low rows come from
masters that match the retired master at several positions, where every unit key of
the old core is compatible, and the closeness rule allows at most two matching
positions, so it sets the floor at about a quarter. An owner whose retired cores do
not cover the units has only the uniform population and gets 42% at best, so for them
the figure is a warning that dropping the pattern will cost rekeyed cores. And the
figure is large enough that an owner choosing whether to drop the pattern needs it in
front of them, with the number of units still undecoded, to see the expected count of
cores that will need rekeying.

## The model

**Population.** An undecoded unit key is drawn from a population, as a set of
per-position cut sets that the existing counting already knows how to use (the
counting methods take per-position option sets and a MACS limit, and return exact
counts by dynamic programming over positions). Two populations are defined.

- *Uniform*, as today: every cut the key space allows (the pattern's parity if
  there is one) at every position, subject to MACS.
- *From the retired cores.* When the system lists `retired_cores` that cover unit
  keys, an undecoded unit key sat in one of them, so at each position its cut is
  one for which that chamber could have been pinned with the retired masters and
  the retired control key. This is computed with the pinner itself, one chamber at
  a time, not with a hard-coded "plus or minus one", so it stays right for a
  pinning system with different pin ranges. A retired core covers unit keys if one
  of its `change` entries is a wildcard that starts with the unit prefix (for
  example `unit:*`). If several retired cores cover units, an undecoded key sat in
  one of them and we do not know which, so the population is the union of their
  sets, counted exactly by inclusion and exclusion over the covering cores. That
  costs `2^n - 1` terms for a count of one key but `(2^n - 1)^2` pair counts for the
  unit-to-unit figure, where both keys of a pair come from the union, and the pair
  counts depend on the candidate master, so nothing can be cached across the
  solver's candidates. At about 1.2 ms a pair count that is 1 for one core, 9 for
  two (11 ms a candidate), 49 for three (60 ms), 225 for four (0.3 s) and 3,969 for
  six (nearly 5 s), against the few thousand candidates a solve scores. The limit is
  therefore **three** covering cores, about five minutes for a solve at the limit.
  With more than three, the tools do not refuse the file (D53 made problems with the
  description of the old cores warnings, so that a disputed description does not
  fail a file): they fall back to the uniform population and print a line saying
  that the retired cores were not used and why. With none, the population is uniform.

**Figures.** Three numbers about undecoded unit keys, each an exact count over the
population.

- The existing *expected cross-operation*: for a non-unit core, unit keys expected
  to operate it; for a unit core, unit-to-unit pairs expected to cross-operate. The
  counts are taken within the population and divided by its size. One detail changes:
  today the estimate subtracts the core's own keys from its operating set, which is
  right when every valid bitting is a candidate. Within a population only the
  intended keys that lie in it come off, often none, because a non-unit core's keys
  are generally not among the bittings an old unit core could have held. Copying the
  count of intended keys into the new counting would bias the figure low.
- The new *expected unpinnable*: for a unit core, the undecoded unit keys expected
  to be unable to take the candidate master and control key. It is the population
  minus the part whose every chamber can be pinned with them, counted the same way,
  times the number of undecoded units. It is computed for every unit core. A core
  with no master is simply asked about its control key alone, which gives a smaller
  figure but not zero: a change key with a 9 where the control key has a 0 cannot be
  pinned (the control pin would be 1).
- A one-line statement of which population was used, so the number is never quoted
  without its assumption.

**Hard rules.** For known keys nothing is statistical. A core whose change key,
masters and control key are all known must be pinnable, as a hard rule beside
duplicates and cross-operation. This is what the checker's `UNPINNABLE` already
reports, so the two cannot disagree: both call the pinner.

## What changes in the solver

The solver keeps its structure: random candidates, then single-cut hill climbing,
each candidate scored exactly. Three changes, all only when the system sets
`pinning`.

1. **Unpinnable cores are hard conflicts.** Scoring a key now also pins every core
   it takes part in, as a change key, a master or the core's control key, using the
   keys already assigned, and adds the hard penalty for each chamber that cannot be
   pinned. Counting chambers, not cores, gives the hill climb a slope to follow
   (fixing one of three bad chambers is progress). A control key being solved for is
   scored against every core that uses it, which is the shared-control rule of
   core-pinning.md.
2. **The expected-unpinnable figure joins the residual-risk score.** It is added to
   the existing expected-conflict term with a weight of 1, a named constant next to
   `HARD` and `CLOSE_WEIGHT`. That is not a balance, and the document says so plainly:
   on the fixture, over 100 random masters with 97 undecoded units, the expected
   unit-to-unit cross-operations average 0.19 (0.15 to 0.24) under the uniform
   population and 0.45 (0.07 to 1.11) under the retired-core one, while the expected
   unpinnable keys average 77 (63 to 84) and 76 (48 to 87). With a weight of 1 the
   unpinnable term is more than a hundred times larger (about 400 and 170 times) and
   varies far more between candidates, so the solver in effect minimises it first and
   uses cross-operation only to choose among near-ties. That is the intended behavior, and the maintainer
   has confirmed it: the primary goal is to avoid rekeying unit cores, which without
   parity is a certain cost, while a chance cross-operation is rare. The output
   prints both figures separately so the effect can be seen. A balance would need a
   much smaller weight or normalised terms, and that would be a change to this
   paragraph, not an implementation detail.
3. **The population comes from the retired cores**, in the solver's own estimate
   as in `check_system`, through the same function, so the two always print the
   same numbers.

Candidate generation is unchanged: the solver already draws cuts from the key
space's digits, which are all ten depths when there is no pattern. The solver's
printed line "N% of random candidates were free of hard conflicts" will fall
sharply without parity, and the document records that so nobody reads it as a
fault.

## What changes in the generator

`gen_bittings.py` takes the pattern as a required argument, which is why it cannot
be used without parity. The pattern becomes optional, with `--pins` as the other
way to give the length (default 7, as `check_bittings.py` does), and a bitting is
then any MACS-valid key. Nothing else about it changes, and invocations with a
pattern give what they give today. It does not check pinnability, since that is a
property of a core and the generator draws keys with no core in mind; the solver
and the checker are where it is tested. A `--pinnable-with` option that keeps new
keys compatible with named existing ones is possible later but is not proposed
here.

## What stays the same

- No weight, algorithm or output changes for a file that does not set `pinning`.
  The solver's seeded runs and the checker's reports for such files are compared
  before and after, byte for byte, as the project's rule for refactors asks.
- Closeness stays the rule it is: at least `min_diff` positions between non-unit
  keys, retired keys included. It is not relaxed to help the unpinnable figure, even
  though it sets the floor (see the table).
- `check_system`'s `UNPINNABLE`, `CONTROL` and `WARNING` lines, the retired-core
  consistency check and the exit status are as step 4 left them.
- The `secrets` and `random.SystemRandom` defaults are untouched.

## Alternatives considered

**Keep requiring a pattern for the solver and tell owners to use parity.** The
simplest, and the safe answer where the key space is large enough, but it gives up
the main benefit of the design, and the hundredfold gap in the table is the reason
to build this.

**Treat an undecoded unit key's unpinnability as a hard rule.** Impossible: the
probability is never zero without parity, and there is nothing for the solver to
avoid. It has to be an expectation.

**Refuse a system with more covering retired cores than the limit.** It would make
the checker fail on a file whose description of the old cores is disputed or merely
richer than the exact count allows, which D53 chose not to do. Falling back to the
uniform population with a printed line loses less.

**Estimate by sampling instead of counting.** The existing estimates are exact
because the validity rules are per-position sets plus a neighbour limit, and the
pinnability rule is the same kind of set, so exactness comes free and a sample would
only add noise to a figure that is used to compare candidates.

**Weight the new term by the cost of rekeying a core, in real terms.** There is no
number to use without facts about a building, and the tools are meant to work
without any. The weight stays a constant with a printed breakdown.

**Put the population in the configuration** (a declared pattern or a list of
excluded cuts per position). Rejected as a second notation for what the retired
cores already say. A declared parity pattern remains available as it is today, for
owners who know one holds.

## Plan

Two pull requests, because the first can be reviewed and used without the solver.

| Part | What | Behavior change |
| --- | --- | --- |
| 5a | The population and the expected-unpinnable figure, in the counting code and in `check_system`'s residual-risk section; the retired-core population replaces "uniform" there when `retired_cores` cover units | Only for files that set `pinning` and have such retired cores; a new line and different figures |
| 5b | The solver: unpinnable cores as hard conflicts, the new term in the score, the shared population; and the generator with an optional pattern | Only for files that set `pinning`; the generator's new form is additive |

Each part gets its own log entry and README text, and 5b a before-and-after
comparison of seeded runs for files that do not opt in.

## Details to settle while building

- The exact wording of the new report lines, and where the population statement
  sits in the residual-risk section.
- How the solver reports, per unit core, the two figures and the population, so a
  run's output can be compared with `check_system`'s.
- How slow a solve at the limit of three covering cores really is, which is
  estimated above at about five minutes and is measured when 5b is built.
- Performance of pinning every involved core inside the scoring loop; if it is
  slow, the per-position sets of pinnable cuts can be computed once per core and
  reused, since they depend only on the other keys of the core.
