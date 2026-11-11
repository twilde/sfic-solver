# Pinnable answers for larger groups of blank keys

Status: Draft

This document describes how the solver should find pinnable answers when more than three
blank keys share cores, and how it should report the case where none exists. It extends
"Building pinnable keys exactly" in [pinnable-solving.md](pinnable-solving.md) (D60), whose
limit of three keys it removes, and it is the item in TODO.md that begins "A solver for
pinnable answers among more than three unknown keys". It is written before any code. The
numbers are measured on fake systems by throwaway scripts that are not in the repository,
and are illustrations of scale, not claims about any real system.

## Why do this

A system file can leave several keys blank at once (the masters, the area keys, a control
key) and give the solver the keys that are already cut: change keys of other cores, decoded
unit keys, the retired keys. The solver must then choose keys that are pinnable together
with the known ones. The checker's `UNPINNABLE` line is the rule being broken: in some
chamber two operating keys of one core have cuts one apart (or the control cut is too
close to them), so the pin between them would be size 1, which does not exist.

The solver prevents this by construction for a group of up to three blank keys that share
cores (D60). It lists, position by position, the digit combinations that leave every
involved chamber pinnable, and draws only from those. For a larger group it falls back to
what it did before D60: draw random keys, score them, change one cut at a time. That
search cannot repair the failure, for the reason D60 gives (two blank keys that sit one
apart at some position cannot fix it one at a time), and it scores a core as unpinnable
only once every key of the core is assigned, so its first choices are made blind to the
cores that use the keys still to come. Its end of run message, "run it again (a different
random draw may do better)", then sends the owner back to the same failure.

The measurements below are on the fixture `tests/fixtures/pinning.json` with six more
known change keys added, each with random cuts that keep the adjacent-cut limit, in cores
with the same masters and control key as the area cores. Twenty seeded runs each, 500
trials a key.

| Blank keys sharing cores | Path | Runs ending unpinnable |
| --- | --- | --- |
| 2 (two masters) | exact (D60) | 0 of 20 |
| 4 (two masters, two area keys) | fall back | **19 of 20** |

The exact set for those four keys exists (about 6 x 10^14 pinnable combinations) and
building its per-position lists took 0.2 seconds. Five blank keys took 2.2 seconds. The limit of
three was set by the worst case, ten digits to the power of the number of keys at every
position, and the real lists are far smaller because the constraints cut them down. On
the same fixture with every key but the decoded units blank, the groups are of seven and
two keys, so the largest case in ordinary use is out of reach of any fixed cap and needs a
different method, not a higher number.

A second, different failure is hidden by the same message. If two keys that are already
known leave no pinnable cut for some position (they are one apart there in a core that
must contain both), no answer exists whatever the solver chooses. With twelve known
change keys added to the same fixture, positions 1 and 4 of the four-key group had none. The
exact path already says so and that a known key has to change; the fall back path does
not, and says to run it again.

## The model

Nothing about the model of D60 changes, and this document only extends how far it reaches.

Pinning is decided one chamber at a time, so at each position the digits of the blank keys
in a group are constrained only by that position's chambers, with the known keys' cuts
fixed. The constraints are the same at every position: one for each core and change key,
over the operating keys and the control key of that core. The only thing that couples
positions is the adjacent-cut limit (MACS), and it couples each key to itself: the
cut of a key at position p+1 is within `max_step` of its cut at p. So the problem is a path
through the positions, where the step from one position to the next is allowed when every
key's cut moves within the limit.

Three facts follow, and the design rests on them.

1. **Whether any answer exists at a position can be decided on its own.** It is a
   constraint problem over the group's keys with ten digits each, and a depth-first search
   that checks a core's constraint as soon as all of its keys have a digit finds a solution,
   or shows there is none, without listing the 10^u combinations. A position with none is
   the exact reason that no answer exists (the checker's `UNPINNABLE` for the known keys
   alone), and it can be named without running the whole search.
2. **A position's solutions, projected onto one key, say which cuts of that key can be
   extended to a solution at that position.** Choosing a key's whole bitting from those
   projections, subject to MACS for that key alone, is a small dynamic programme over ten
   states per position, and every position of the bitting then has at least one completion
   by the other keys. What it does not promise is that the completions chain with MACS.
3. **Once a key is chosen it is known**, and the rest of the group is smaller, often in
   several independent groups, because the cores that joined them may no longer connect
   the remaining keys.

## The proposal

Three parts, each worth having alone, in this order.

### 1. A cost limit instead of a count of keys

Build the per-position digit lists for a group by the depth-first search above, which never
forms the whole product, and use the exact method of D60 (count, draw, enumerate) whenever
the lists are small enough. "Small enough" is the work the counting does, the sum over
positions of the product of two neighbouring lists' lengths, times the number of keys,
against a named constant next to `MAX_SHAPE_REJECTS`. The constant is set while building,
from timings, so that a group at the limit takes about as long as the largest the code
handles today. `MAX_JOINT_KEYS` goes, and the printed line that says a group is too big
names the work and the limit instead.

This covers the measured four- and five-key cases, and any group of a few more keys whose
constraints are tight. It changes nothing for groups of up to three keys, which the limit is set to
include: for those, a seeded run gives what it gives now.

### 2. Staged construction for groups over the limit

For a group the exact method cannot hold, choose its keys in stages. Order the keys so that
choosing one splits the group as much as possible (the control key or the top master of a
hierarchy, which every other core's constraint passes through, is the likely first choice,
and the order is by the number of cores a key is in, with the rule written down once built).
For the first key take the per-position projections of fact 2 and draw a bitting from
them, exactly as the single key is drawn today (uniform over the projected, MACS-valid
bittings, filtered by the shape rules). Fix it, split what remains into its groups
(fact 3), and solve each group by part 1 if it is now small enough, or by the next stage.

The completions may fail to chain, so a stage can reach a group with no answer, and then
it goes back and draws again for the key before it, up to a bounded number of tries
(a constant, set by measurement). The stage count is the number of keys at worst, and for
the systems this is for (a hierarchy of masters over areas) the first key's projections
already carry most of the constraints, so retries are expected to be rare. That is the
claim most in need of measuring while building, and the document says so.

Candidates are scored as before. For a group built in stages the draw per key is uniform
over what is extendable, not uniform over complete answers as part 1's is, and the output
says which method built each group, as the existing lines do for the exact one.

### 3. Say what failed, and for whom

The end of run verdicts are changed to say the true thing in each case.

- **No answer exists.** Whenever fact 1 shows a position with none, name the position, the
  cores, and which known keys are one apart (or otherwise leave no cut) there, as "a known
  key has to change", and never suggest running again. This is now exact for every group
  size, since it needs no listing.
- **None found.** When a staged construction gives up after its bounded tries, or a hard
  rule other than pinnability still fails (cross-operation, a duplicate), say that no
  answer was found, that one may exist, and that running again can help, with the number
  of tries made.
- **Known keys alone conflict.** A chamber that is unpinnable among known keys only is
  already left out of the solver's count (D59). The verdict now says that these are not the
  solver's to fix, and names them, instead of leaving them to the check below the result.

The exit status is unchanged (D8).

## What stays the same

- The score: hard penalties, closeness, the expected-unpinnable figure and its weight
  (D6, D56). Only where a group's candidates come from changes, and, for groups over the
  limit, how many of them there are.
- Files without `pinning`, and groups the exact method already handles: seeded output
  before and after is compared byte for byte, as the project's rule for refactors asks.
- The shape rules are never relaxed (D65). A group built in stages filters each stage's
  draws by them, and reports the rule that left no bitting.
- The `secrets` and `random.SystemRandom` defaults.

## Alternatives considered

**Raise `MAX_JOINT_KEYS`.** It fixes the four- and five-key cases at the price of a wrong
limit: the cost depends on how tight the constraints are, not on the count, so a number
that is safe for one file is slow for another, and a group of seven stays out of reach.
Part 1 is this change done properly.

**Joint moves in the hill climb**, or **min-conflicts local search** over the whole group.
D60 rejected joint moves for a tie of three keys, and a local search can never say that no
answer exists, which is the thing the owner most needs to be told. It stays an option for
the retries of part 2 if measurement shows they matter.

**More trials, sweeps or restarts.** D60 measured 20,000 trials leaving the stuck case
stuck, and the 19 of 20 above is with restarts built in.

**A general solver (SAT or constraint programming) as a dependency.** The project is
standard library only with one bounded exception (D38), and the problem is small and has
a structure (independent positions, a chain of MACS steps) that makes a purpose-built
search short and exact where it matters.

**Decide every pin of the whole system at once.** The groups are independent already (no
pinning constraint crosses them), so a single big search would only be slower.

## Plan

Three changes, one commit each, with tests in `tests/test_joint.py` and
`tests/test_solve_system.py`, and a seeded before and after comparison for the files that
are not meant to change.

| Part | What | Behavior change |
| --- | --- | --- |
| 1 | The per-position search and the cost limit in `joint.py`; the printed line in the solver | Groups of more than three keys within the limit are built exactly; nothing else |
| 2 | Staged construction for groups over the limit | Groups over the limit stop falling back to the old search |
| 3 | The three verdicts, with the positions and the known keys named | Message text only; the exit status is as it was |

Each gets a log entry when it is built, README text where the solver's behavior is
described, and a regression test for the failure it fixes: a fixture whose pinnable
set is small but not empty for part 1 and 2, and one with two known keys one apart for
part 3, all made from invented keys.

## Details left to the build

These can only be settled by building and measuring, and none waits on a decision.

- The value of the cost limit and the number of retries, from timings on the fixtures
  (the document gives 0.2 s for four keys and 2.2 s for five as the scale).
- The order in which stages choose keys, if the count of cores per key is not enough.
- Whether a group built in stages needs a better figure than "uniform over what is
  extendable" for the share of candidates that were free of other hard conflicts.
- Whether the staged method still finds an answer in a system with so few pinnable
  combinations that part 1 would have listed them all (then part 1's way is simply used).
