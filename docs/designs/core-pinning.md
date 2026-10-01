# Core pinning for SFIC pinning systems (A2 first)

Status: Draft

This document proposes teaching the tools to pin cores: to take the keys and the
hierarchy a system file already describes and work out the pins that make the
cores behave that way, for a given SFIC pinning system, starting with A2. It
also proposes a simulated lock to test the result against, and, as a
consequence, replacing the parity pattern as the thing that decides which
bittings are legal. It is written before any code, to be discussed and changed.
Decisions that survive discussion will be summarised in the log
([D25 in design.md](../design.md)).

## Why do this

Today the tools answer one question well: given these keys and this hierarchy,
which keys operate which cores, and is anything operating that should not be?
They answer it by treating a core as a rule, "accept the change key's cut or any
master's cut at every position", and counting what that rule lets through.

That rule is correct as far as it goes, but it stops short of the thing that is
actually built. Somebody has to put pins in the cores, and the pinning has rules
of its own that the key-level model does not see. The parity pattern is the
clearest symptom. It is not a rule of the lock; it is a shortcut that guarantees
the real rule is met without anyone having to check it, and it costs a great
deal of the key space (about a hundredfold, as shown below). Another symptom is
that control keys are only checked for closeness and duplicates, yet an SFIC core
with no valid control key can be neither installed nor removed, so a system whose
control bittings cannot be pinned is not a system at all.

So the aim is to model the pinning faithfully enough that the tools can say not
only "these keys are safe" but "and here are the pins that make it so, and the
combination can be built". If that works, the tools can stop leaning on parity and
draw from a much larger set of bittings.

## How a core is pinned, as the model sees it

An SFIC core has a number of **chambers**, one per cut position on the key. Each
chamber holds a stack of pins that the key pushes up. There are two shear lines
in a core: the **operating** shear line, which an ordinary key aligns to turn the
plug, and, a fixed distance further out, the **control** shear line, which the
control key aligns to turn the whole core so that it can be installed or removed.

Everything is measured in increments of 0.0125 inch, the A2 step, and every cut
and every pin has a whole-number size. A key cut of depth 4 means the key lifts
the stack until the boundary between two pins sits at height 4 above where it
started, so that the boundary lines up with the operating shear line. A pin is
named by its length in increments, and a stack of pins has a boundary at each
**partial sum** of its lengths: the first boundary at the length of the bottom
pin, the next at the bottom pin plus the next pin, and so on. A key operates a
chamber when its cut equals the height of one of the boundaries. That is the whole
mechanism, and it is why a core "accepts the change key's cut or any master's cut"
at each position: each of those cuts is a boundary in the stack.

The control shear line is 0.125 inch beyond the operating one, which is 10
increments. So a boundary at height 10 + c lines up with the control shear line
when the control key's cut at that chamber is c. Operating keys reach heights 0 to
9 and control keys reach 10 to 19, and the two ranges never overlap, which is why
one stack can serve both.

The A2 rules we are working from are these. They come from the maintainer's
knowledge of the system, and from published descriptions of A2 that agree with
them (see Sources); verifying them is the first job of the plan below.

| Rule | Value in A2 |
| --- | --- |
| Increment | 0.0125 inch |
| Cut depths | 0 to 9 |
| Total stack in every chamber | 23 increments |
| Bottom pin sizes | 0 to 9 |
| Other pin sizes (master, control, driver or top) | 2 to 19, all one family |
| Control shear line beyond the operating one | 10 increments |

Take one chamber of a core whose change key has cut 3, whose master has cut 7 and
whose control key has cut 5. The boundaries must be at heights 3 and 7 for the
operating shear line, and at 15 (which is 10 + 5) for the control one. The pins,
from the bottom, are therefore a 3 (the change key's height), a 4 (the distance
from 3 to 7, which is the master pin), an 8 (from 7 to 15, the control pin), and an 8
to bring the stack up to 23 (the driver, the top pin). They add up to 23, the
bottom pin is within 0 to 9, and the other three are within 2 to 19, so the
chamber can be built, and the pinning is forced: with these cuts there is no
other legal stack.

Now two chambers that cannot be built. If a change key has cut 4 and the master
has cut 5, the pin between them would have length 1, and no pin in the 2 to 19
family is that short. If a master has cut 9 and the control key has cut 0, the
control boundary is at 10, one above the master's boundary at 9, and again the
pin between them would have length 1. Both are the same problem, and they show
what the rules reduce to.

**A chamber can be pinned exactly when the distinct boundary heights in it,
operating cuts and then control cuts plus 10, are each at least 2 apart.** The
bottom pin is the lowest height and is always in range, and the driver is 23 less
the highest height, which is at least 4, so neither of them can fail. Only the
gaps between boundaries can. For the control key this reads as a limit on its
cut: it must be at least the highest operating cut in that chamber less 8.

## What this does to parity

The parity pattern says each position is even or odd for every key in the system.
If it holds, any two cuts at one position differ by an even number, so they are
equal or at least 2 apart, and the gap rule is satisfied for every core without
looking at any. That is all parity is. It is a sufficient condition for the
rule that was found to be necessary, and not a rule of the lock.

The gap rule rules out far less. In a prototype of the model (not committed),
the number of cuttable 7-position bittings with a maximum adjacent step of 5 is
28,384 under the example system's parity pattern and 3,027,314 without parity,
about a hundred times as many. The rule is also relational: it concerns pairs of
cuts in one chamber of one core, not a key on its own. A random master leaves
about a fifth of those 3 million keys (measured on a sample) free to be its
change keys, because every key under it must avoid the master's cut plus or minus
one at every position.

This is the point at which the plan needs care, because "get rid of parity" is
not free everywhere. Consider unit cores. One unit master sits above every unit
key, so every unit key has to avoid the master's cut plus or minus one at every
position. If the unit keys are chosen after the master, that is easy: they are
drawn from the compatible keys, a set far larger than parity allows. If
the unit keys already exist, the master has to be found to fit them. With many
unrelated keys the chance that a random master fits them all collapses (a fifth
per key, so a vanishing fraction for a hundred), and even a master found to fit
the decoded ones may clash with a unit key not yet decoded. Parity is what makes
that safe in an existing building whose unit keys were cut under a parity rule:
if every undecoded key is known to follow the pattern, a master that follows the
pattern is guaranteed to fit.

So the honest reading is this. Parity stops being a rule every key must obey and
becomes a **promise about a population**: "every key I cannot see follows this
pattern". Where all the keys under a master are known, the tools check the real
gap rule per core and need no pattern. Where some are not, the pattern is the
assumption that lets the check be completed. And in a new system the order of
generation flips: choose the masters first, then draw each change key from the
keys that avoid the neighbours of its masters' cuts. The unit population can then
use up to eight or nine of the ten depths at each position instead of the five
that parity leaves, so the new-system key space is large without needing parity
at all.

## Control keys are part of the core

A control key is not an extra to be checked for closeness; it is half of every
core's pinning. Every core therefore names the control key (or keys) that pin its
control shear line, and the pinning needs them. Two things follow.

The first is the gap rule above, applied across both shear lines: a control cut
must be at least the highest operating cut in its chamber less 8, or the chamber
has no legal stack. A control key chosen without regard to the operating keys
above it may simply fail.

The second is a control form of cross-operation. A physical key aligns the control
shear line when each of its cuts is one of the core's control cuts, whoever
intended it as a control key. So a known operating key whose cuts happen to match
a core's control bitting could remove that core. The existing check for operating
cross-operation extends naturally: every known key is tested against every core's
control shear line too, with the same exact counting. A core may in principle have
a control master, a second control cut set above the first; the maths is the same
as for operating masters, and the design should not rule it out, though it may
wait until the charts show whether the real system uses one.

## A simulated lock

The pinner and the key-level model must agree, and the best way to make sure is to
have a third thing that knows neither. The proposal is a small **simulated lock**:
a lock is nothing but a pin stack for each chamber, and it answers one question,
"which shear lines does this key align?". It computes boundaries as partial sums
and compares them with the key's cuts, and it knows nothing about change keys,
masters or control keys. The pinner then has a clean test: build the pins for a
core, build the lock from the pins alone, and check that the lock is operated by
exactly the keys the key-level model says it should be, for every possible key
when the lock is small enough to enumerate.

A prototype did this over several hundred random three-chamber cores, comparing
the lock with the existing set arithmetic for all 164,000 key and core
combinations that could be pinned, and found no disagreement. It also confirmed
that the pin-size ranges and the gap rule give the same answer on every one of the
4,422 chamber configurations tried. That is encouraging, but it only shows the
model is consistent with itself. Whether it is consistent with real A2 pinning is
a separate matter, taken up below.

The simulated lock earns its keep in three ways. It is an oracle for the test
suite and, later, for anyone changing the pinner. It is a way of explaining
results, since a lock can say which chamber and which boundary made a key work.
And, as a further step that this document does not plan in detail, its geometry
(stacks, boundaries, the heights a given key lifts to, which shear lines align) is
exactly what a visualizer needs. If the lock exposes those, a drawing of a core
and a key lifting its pins is a rendering exercise and needs no more maths. That
would be its own design document.

## Pinning systems as data

A2 is one of several SFIC pinning systems; A3 and A4 differ in their increments,
progressions and pin ranges, and the tools should not bake A2 into their logic. A
**pinning system** is therefore a small record of the numbers in the table above:
increment, cut depth range, stack total, the bottom and other pin size ranges, and
the control offset, plus a name. A2 is the first entry. Adding another is data
plus a source to check it against, and no new code; nobody should add one from
memory.

Two things deliberately stay outside the record. The number of pins stays the
system file's `pins` (D22), since A2 does not dictate it. And the maximum
adjacent cut step (MACS) stays the system file's `max_step`, with its current
default of 5, because it belongs to the keyway and to the owner's policy rather
than to the pinning system. Whether A2 imposes a MACS of its own, and whether the
control key is bound by it, is an open question.

A system file opts in with a new top-level field, for example
`"pinning": "A2"`. A file without it means what it always did: the pattern, MACS
and counting rules of today, unchanged, and no pinning output. That is how D22
introduced configurable pin counts, and it keeps every existing file valid.

## Verification

None of the above is worth anything if the rules are wrong, and the manufacturer's
keying software, which is the authority, cannot be run here or inspected. So
verification is layered, and the layers that touch real data are kept apart from
the repository.

The first layer is properties that must hold for any pinning: every chamber's
pins sum to 23; every pin is within its range; and the simulated lock agrees with
the key-level model on all the keys a small lock can have. These run in the test
suite on fake bittings. The second layer is published worked examples, such as the
one in the Locksmith Ledger guide, which have known answers and can be committed.

The third layer is real charts. The maintainer holds pinning charts for a real
system, kept outside this repository, including some earlier proposals that were
rejected, which are valuable as negative cases: the rules should explain why
something was rejected, and if the model accepts a rejected pinning, the model is
missing a rule. Since a chart's pin sizes reveal the bittings, nothing derived
from the charts may be committed (see the privacy rules in CLAUDE.md), and the
tests may use only charts computed from fake bittings. The charts are therefore
used by a **local conformance script** that lives in the repository but reads
charts from a path given on the command line or in an environment variable and
does nothing when there is none. It reports how many chambers and cores agree and,
for disagreements, only their positions (a row number, a chamber number), never a
bitting or a pin size, so that its output is safe to quote in an issue. To write
the reader we need the chart's layout, described with invented values.

The fourth layer is humility in the output. Until a pinning has passed the
conformance script against real charts, anything the tools print about pinning is
labelled as unverified, and the README's limitations section says that the
manufacturer's software remains the authority.

## What changes in the tools

The new code is mostly new modules beside the existing ones: the pinning system
record and its registry, the pinner (cuts for one core in, pins out, or a
specific reason it cannot be built), the simulated lock, and a chart renderer.
The config loader gains the `pinning` field and a `control` entry on each core
(naming one or more control keys from `control_keys`), and validates them like the
rest. The checker, when a pinning system is set, adds two things to its report:
which cores cannot be pinned and why (the chamber and the gap), and any key that
operates a core's control shear line. A new command, in the same style as the
others (`sfic-pin-system`, with a root script), prints the pinning chart for every
core.

Two of the changes are not additive and need agreement. The first is that
pinnability becomes a hard rule for the solver alongside cross-operation and
duplicates (D6): a master that cannot be pinned over a known unit key is as bad
as one that operates the wrong core. The second is that the residual-risk estimate
assumes undecoded unit keys are uniform among valid bittings, and with a relational
validity rule the population has to be stated: it needs the pattern-as-promise
reading above, or another population model. Neither changes any weight or
algorithm for files that do not opt in, and each will be raised for agreement
before it is built.

## Plan

The work is split so that each step is reviewable and the risky assumptions are
tested early. Control is built into the library from the start, because the gap
rule couples control and operating cuts, and the conformance check comes before
the checker, so the rules are verified before anything depends on them.

| Step | What | Behavior change |
| --- | --- | --- |
| 1 | Refactor: bundle pin count, depth count, MACS and the optional parity pattern into one key-space rules object, in place of the loose parameters passed around today | None |
| 2 | Library: the pinning system record with A2, the pinner with control pins, the simulated lock, and property tests | None for existing files (library only) |
| 3 | The local conformance script for private charts, and any correction to the rules it shows | None |
| 4 | Config and checker: the `pinning` field, `control` on each core, pinnability and control cross-operation in the report | Only for files that opt in |
| 5 | Pinnability replaces parity as validity in the generator and solver; the pattern becomes a population promise; revisit residual risk | For opted-in files, with agreement |
| 6 | The chart command and README updates | New command |
| 7 | A visualizer, if wanted, with its own design document | None |

## Alternatives considered

The cheapest option is to keep parity as the only validity rule and add chart
output on top. It would produce charts for today's key space and nothing more,
and it would leave the control problem and the hundredfold space as they are, so
it is the fallback if the rules cannot be verified rather than the plan.

Another is to model pinning in a generic way, with pin sizes as variables and a
solver or integer programme to find stacks. The A2 pinning turns out to be forced
(one legal stack per chamber, or none), so the problem does not need a solver, and
a dependency would break the standard-library-only rule (D2).

A third is to keep this in a separate repository. The pinner needs the same
bittings, hierarchy, counting and checks as the existing tools, so splitting would
mean copying them.

## Open questions

These are the things we do not yet know, in roughly the order they matter.

Is the stack total of 23 constant for every chamber of a core, and is the bottom
pin 0 a real pin? The rules above depend on both. Do the real charts ever show two
different stacks for the same set of cuts, such as a master gap split into two
pins? If so the pinning is not forced and the model is incomplete. Is the topmost
pin one pin, or do the charts show a driver and a separate top pin sharing the
remainder?

Does A2 impose its own maximum adjacent cut step, and does the control key obey
it? Does the real system use control masters, or only one control key per core?
Is one control key shared by a whole group of cores, or does each core have its
own? Is there a limit on how many pins a chamber may hold that the stack total
does not already imply?

For the existing building, can the unit keys be assumed to follow the parity
pattern, so that it can serve as the population promise? And should the data-file
guard grow to cover chart formats (a spreadsheet or PDF export, say), beyond
`.json` and `.csv`, which it covers today? That is a guard change in its own
commit, probably before step 3.

## Sources

The A2 numbers were cross-checked against published descriptions that I have only
seen as search summaries, so they should be read in full when step 2 is verified.
They include the
[Locksmith Ledger interchangeable core pinning guide](https://www.locksmithledger.com/locks/article/12440229/interchangeable-core-pinning-guide)
(the increment, the 2-step progression, the stack total of 23, a worked pinning
example, and the control shear line 0.125 inch beyond the operating one) and
[Allegion's note on the difference between A2 and A4 pinning](https://kc.allegion.com/kb/article/what-is-the-difference-between-a2-pinning-and-a4-pinning).
The summaries quoted slightly different pin-size ranges from the ones in the
table, for what may be a different progression system; the table follows the
maintainer's description of A2, and the conformance step is what settles it.
