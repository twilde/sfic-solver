# Solving for pinnable systems (core pinning, step 5)

Status: Accepted

This document describes step 5 of [core pinning](core-pinning.md): making the
solver, the residual-risk estimate and the generator work for a system that sets
`pinning` and has no parity pattern. It was written before any code and has been
accepted, including its changes to what the solver scores (D6) and the weight of
one for the new term. Files that do not set `pinning` are unaffected throughout; a
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
`tests/fixtures/pinning.json` (seven pins, a retired master and control, three
decoded units) with a prototype that is not in the repository. They are
illustrations of scale, not claims about any real system, and the tests of the real
implementation will reproduce them exactly.

| Key space | Valid bittings | Unit master chosen | Undecoded unit keys that cannot take it |
| --- | --- | --- | --- |
| Parity pattern `OOEOEOE` | 28,384 | any valid key | 0% (parity guarantees it; 0% in every draw tried) |
| No pattern | 3,027,314 | a random valid key | typically 82% (52% to 92% over 300 draws) |
| No pattern | 3,027,314 | the best a hill-climb finds, ignoring closeness | 8% |
| No pattern | 3,027,314 | the best it finds with the closeness rule (at least 5 positions from every other non-unit key, retired keys included) | 24% (median restart 43%) |

Three things follow. Dropping parity makes the master matter: a careless choice
leaves most undecoded units unable to take it, and a careful one leaves a
quarter. The hill-climb's best answer matches the retired master at most
positions, which the closeness rule forbids past two, so the trade the design
document predicted is real and the closeness rule is the thing that sets the
floor. And the figure is large enough that an owner choosing whether to drop the
pattern needs it in front of them, with the number of units still undecoded, to
see the expected count of cores that will need rekeying.

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
  sets, counted exactly by inclusion and exclusion over the covering cores (a few at
  most; a system with more than six is refused with a message, not approximated).
  With none, the population is uniform.

**Figures.** Three numbers about undecoded unit keys, each an exact count over the
population.

- The existing *expected cross-operation*: for a non-unit core, unit keys expected
  to operate it; for a unit core, unit-to-unit pairs expected to cross-operate. The
  formulas stay as they are, with the population in place of "all valid bittings"
  (the count of bittings that operate the core is taken within the population, and
  the denominator is the population's size).
- The new *expected unpinnable*: for a unit core, the undecoded unit keys expected
  to be unable to take the candidate master and control key. It is the population
  minus the part whose every chamber can be pinned with them, counted the same way,
  times the number of undecoded units. A unit core with no master still has its
  control key to be pinned with, so the figure covers it too, and only the control
  key matters there.
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
   the existing expected-conflict term with a weight of 1: one unit core that must
   be rekeyed counts the same as one expected cross-operation. That weight is a
   judgment, not a measurement, and is a named constant next to `HARD` and
   `CLOSE_WEIGHT`. Rekeying a core is a cost but no security failure, and a chance
   cross-operation is a security failure but a rare, discoverable one, so equal
   weight is a middle course; the output prints both figures separately, so a
   different weight can be argued from what the solver reports.
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
- Whether the inclusion-exclusion over covering retired cores needs a cache, which
  depends on how slow it is with six cores.
- How the solver reports, per unit core, the two figures and the population, so a
  run's output can be compared with `check_system`'s.
- Performance of pinning every involved core inside the scoring loop; if it is
  slow, the per-position sets of pinnable cuts can be computed once per core and
  reused, since they depend only on the other keys of the core.
