# Core pinning for SFIC pinning systems (A2 first)

Status: Draft

This document proposes teaching the tools to pin cores: to take the keys and the
hierarchy a system file already describes and work out the pins that make the
cores behave that way, for a given SFIC pinning system, starting with A2. It
also proposes a simulated lock to test the result against, and, as a
consequence, letting the physical pinning rules rather than the parity pattern
decide which bittings can be built. It is written before any code, to be
discussed and changed, and has been revised once with the maintainer's answers to
its first round of questions. Decisions that survive discussion will be
summarised in the log ([D25 in design.md](../design.md)).

## Why do this

Today the tools answer one question well: given these keys and this hierarchy,
which keys operate which cores, and is anything operating that should not be?
They answer it by treating a core as a rule, "accept the change key's cut or any
master's cut at every position", and counting what that rule lets through.

That rule is correct as far as it goes, but it stops short of the thing that is
actually built. Somebody has to put pins in the cores, and the pinning has rules
of its own that the key-level model does not see. The parity pattern is the
clearest symptom. It guarantees that a pinning rule is met without anyone having
to check it, but it is a policy and not a property of the lock, and it costs a
great deal of the key space (about a hundredfold, as shown below). Another symptom is
that control keys are only checked for closeness and duplicates, yet an SFIC core
with no valid control key can be neither installed nor removed, so a system whose
control bittings cannot be pinned is not a system at all.

So the aim is to model the pinning faithfully enough that the tools can say not
only "these keys are safe" but "and here are the pins that make it so, and the
combination can be built". If that works, the tools no longer have to lean on
parity, and can draw from a much larger set of bittings if the owner chooses.

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
named by a number of increments, and a stack of pins has a boundary at each
**partial sum** of those numbers: the first boundary at the length of the bottom
pin, the next at the bottom pin plus the next pin, and so on. A key operates a
chamber when its cut equals the height of one of the boundaries. That is the whole
mechanism, and it is why a core "accepts the change key's cut or any master's cut"
at each position: each of those cuts is a boundary in the stack. (Bottom pins also
have a fixed base length: even a #0 is a real pin, 0.110 inch long, the least
that clears the shear line for the deepest cut. The base never enters the
arithmetic, which is done entirely in pin numbers.)

A word about masters and change keys, because the terminology misleads. Master,
change key, sub-master and the rest describe how a hierarchy is used, but the
pinning of one core knows nothing of them. A core is operated by a set of keys,
and its pins are fixed by those keys' cuts alone: every key's cut at a position
becomes a boundary, and which key is the "master" makes no difference to the
arithmetic. Any two keys pinned into one core are on an equal footing, and either
may be the lower cut, the higher cut, or the same. The names record intent, which
cores a key is meant to open across the building, and they matter in the
key-level checks, where intent is the point. Within one core the pinner and the
charts treat all of its keys alike, so a chart row labelled "Master" is only a
pin layer, and its pin may belong to any of the keys. This document says
**operating keys** of a core when it means all of them.

The control shear line is 0.125 inch beyond the operating one, which is 10
increments. So a boundary at height 10 + c lines up with the control shear line
when the control key's cut at that chamber is c. Operating keys reach heights 0 to
9 and control keys reach 10 to 19, and the two ranges never overlap, which is why
one stack can serve both.

The A2 rules we are working from are these. The maintainer confirmed them, and
the published description we have (see Sources) agrees with the stack total and
the control offset.

| Rule | Value in A2 |
| --- | --- |
| Increment | 0.0125 inch |
| Cut depths | 0 to 9 |
| Total stack in every chamber | 23, a constant of A2 (other systems have their own) |
| Bottom pin sizes | 0 to 9, the #0 being a real pin |
| Other pin sizes (master, control, driver/top) | 2 to 19, all one family |
| Control shear line beyond the operating one | 10 increments |
| Pins in a chamber | at least 3 (bottom, control, D/T), at most the number of operating keys plus 2 |

Take one chamber of a core whose change key has cut 3, whose master has cut 7 and
whose control key has cut 5. The boundaries must be at heights 3 and 7 for the
operating shear line, and at 15 (which is 10 + 5) for the control one. The pins,
from the bottom, are therefore a 3 (the change key's height), a 4 (the distance
from 3 to 7, which is the master pin), an 8 (from 7 to 15, the control pin), and an 8
to bring the stack up to 23 (the driver, the top pin). They add up to 23, the
bottom pin is within 0 to 9, and the other three are within 2 to 19, so the
chamber can be built. The Locksmith Ledger's own worked example (a master cut of
1, a change key cut of 5 and a control cut of 3) comes out the same way, as pins
of 1, 4, 8 and 10, the numbers in the article.

Two practical rules from the maintainer make the pinning forced, meaning that
given the cuts there is one legal stack or none. A gap between two boundaries is
always a single pin, never several: a split would put a boundary at the join, a
boundary is a cut that opens the core, and so splitting would create working keys
that nobody intended. And where operating keys share a cut at a position there is
only one boundary there, so the chamber simply has one pin fewer, and the driver
(the D/T pin, the one pin sized by the stack and not by a key) makes up the total
of 23. That is why a chamber has at least three pins and at most two more than it
has operating keys.

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
cut: it must be at least the highest operating cut in that chamber less 8. Since
cuts stop at 9, in practice this excludes only one thing: a control cut of 0 in a
chamber where an operating key has cut 9.

## What this does to parity

The parity pattern says each position is even or odd for every key in the system.
If it holds, any two cuts at one position differ by an even number, so they are
equal or at least 2 apart, and the gap rule is met for every core without looking
at any. So parity is a sufficient condition for the gap rule, and not the rule
itself.

It is also, in effect, what keying practice calls a 2-step progression, and here
the published description says something the pins alone do not. The Locksmith
Ledger notes that a 6-pin A2 master key system "will generate 4096 change keys".
That is 4 to the sixth power: with the master at cut 1, the change cuts at each
position are 3, 5, 7 and 9. The gap rule alone allows 3 through 9, seven cuts at
each position and 117,649 change keys for the same master. So the published
practice is narrower than the pins require. What the pins allow we can derive,
since pins of every size from 2 to 19 exist. What we cannot derive from the
hardware is whether the keying software, or the locksmith doing the work, will
accept cuts outside the progression, and the charts cannot tell us either, since
charts built under a progression contain only even gaps. The design therefore
makes the choice the owner's: the existing `pattern` field stays, and still means
what it means today (every key follows it), so declaring one asks for the
conservative, progression-style behavior and leaving it out asks for the
hardware rule alone. Pinnability is checked in both cases.

The hardware rule rules out far less. In a prototype of the model (not
committed), the number of cuttable 7-position bittings with a maximum adjacent
step of 5 is 28,384 under the example system's parity pattern and 3,027,314
without parity, about a hundred times as many. The rule is also relational: it
concerns pairs of cuts in one chamber of one core, not a key on its own. A random
master leaves about a fifth of those 3 million keys (measured on a sample) free to
be its change keys, because every key under it must avoid the master's cut plus or
minus one at every position.

That relational nature is the point at which the plan needs care, because going
without parity is not free everywhere. Consider unit cores. One unit master sits
above every unit key, so every unit key has to avoid the master's cut plus or
minus one at every position. If the unit keys are chosen after the master, that is
easy: they are drawn from the compatible keys, a set far larger than parity
allows. If the unit keys already exist, the master has to be found to fit them.
With many unrelated keys the chance that a random master fits them all collapses
(a fifth per key, so a vanishing fraction for a hundred), and even a master found
to fit the decoded ones may clash with a unit key not yet decoded. Parity is what
makes that safe in an existing building whose unit keys were cut under a parity
rule: if every undecoded key is known to follow the pattern, a master that follows
the pattern is guaranteed to fit. So where some keys under a master are unknown,
the pattern doubles as a **promise about a population**, the assumption that lets
the check be completed. Where every key under a master is known, the tools check
the gap rule per core and need no pattern. And in a new system the order of
generation flips: choose the masters first, then draw each change key from the
keys that avoid the neighbours of its masters' cuts, which leaves eight or nine of
the ten depths at each position instead of the five that parity leaves.

## Control keys are part of the core

A control key is not an extra to be checked for closeness; it is half of every
core's pinning. Every core therefore names exactly one control key, the one that
pins its control shear line. The maintainer has never met a system with control
masters or several controls on one core, and all software and discussion use a
single control per core, so that is the model; it is not designed to stretch
further. One control key is normally shared by many cores, and a system often has
more than one, for example one for common areas and one for the units. So a core
carries a `control` entry naming one of the system's control keys, and a key
shared among cores must satisfy every one of them.

The first consequence is the gap rule above, applied across both shear lines: a
control cut of 0 cannot sit in a chamber where an operating key of that core has
cut 9. With a shared control key the exclusion applies to every core that uses it,
so the checker has to say which core and which chamber, and a solver choosing a
control key has to respect them all.

The second is a control form of cross-operation. A physical key aligns the control
shear line when each of its cuts is the core's control cut, whoever intended it as
a control key. So a known operating key whose cuts happen to match a core's
control bitting could remove that core. The existing check for operating
cross-operation extends naturally: every known key is tested against every core's
control shear line too, with the same exact counting.

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

The Ledger's worked example is the first test case, and the pin counts (never
fewer than three, never more than the operating keys plus two) are properties it
checks for every core it builds.

A prototype did this over several hundred random three-chamber cores, comparing
the lock with the existing set arithmetic for all 164,000 key and core
combinations that could be pinned, and found no disagreement. It also confirmed
that the pin-size ranges and the gap rule give the same answer on every one of the
4,422 chamber configurations tried. That is encouraging, but it only shows the
model is consistent with itself. Whether it is consistent with real A2 pinning is
a separate matter, taken up under Verification.

The simulated lock earns its keep in three ways. It is an oracle for the test
suite and, later, for anyone changing the pinner. It is a way of explaining
results, since a lock can say which chamber and which boundary made a key work.
And, as a further step that this document does not plan in detail, its geometry
(stacks, boundaries, the heights a given key lifts to, which shear lines align) is
exactly what a visualizer needs. If the lock exposes those, a drawing of a core
and a key lifting its pins is a rendering exercise and needs no more maths. That
would be its own design document.

## Pinning systems as data

A2 is one of several SFIC pinning systems, and the tools should not bake it into
their logic. A **pinning system** is a small record of the numbers in the table
above: increment, cut depth range, stack total, the bottom and other pin size
ranges, and the control offset, plus a name. A2 is the first entry. The Ledger
gives a stack total and control offset for two others, 16 and 7 for A3 and 14 and
6 for A4, but no pin size ranges, and its A4 example has an arithmetic slip, so
neither can be entered yet. Adding another is data plus a source to check it
against, and no new code; nobody should add one from memory.

Two things deliberately stay outside the record. The number of pins stays the
system file's `pins` (D22), since A2 does not dictate it. And the maximum adjacent
cut step (MACS) stays the system file's `max_step`, with its
current default of 5. MACS is not part of A2 (the Ledger remarks that A2 has no
maximum adjacent cut problems); it is a convention of the owner's, chosen to make
keys go in and out smoothly and to keep cuts from being aggressive. It continues
to apply to every key, control keys included, as it does today (D11).

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
pins sum to 23; every pin is within its range; a chamber has between three and
operating-keys-plus-two pins; and the simulated lock agrees with the key-level
model on all the keys a small lock can have. These run in the test suite on fake
bittings. The second layer is published worked examples, such as the one in the
Locksmith Ledger guide, which have known answers and can be committed.

The third layer is real charts. The maintainer holds pinning charts for a set of
proposals for a real system, kept outside this repository. They were set aside
because a better generation method came along, not because they were invalid, so
every one of them is a valid pinning with valid bittings. That makes them
excellent positive cases and no negative ones: from each chart's header (the
control key and the other keys of the core) the tools must reproduce every row of
pins exactly. Since a chart's pin sizes reveal the bittings, nothing derived from
the charts may be committed (see the privacy rules in CLAUDE.md), and the tests
may use only charts computed from fake bittings. The charts are therefore used by
a **local conformance script** that lives in the repository but reads charts from
a path given on the command line or in an environment variable and does nothing
when there is none. It reports how many chambers and cores agree and, for
disagreements, only their positions (a block number, a chamber number), never a
bitting or a pin size, so that its output is safe to quote in an issue.

The limit of the third layer is that agreement shows the arithmetic and the layout
are right, and says nothing about whether the rules are too permissive: a model
that wrongly allowed a gap of 1 would pass, because no valid chart contains one.
That risk is covered by the first two layers, by the pin ranges the maintainer
confirmed, and by the open question about progression below, which is exactly a
question about permissiveness.

The fourth layer is humility in the output. Until a pinning has passed the
conformance script against real charts, anything the tools print about pinning is
labelled as unverified, and the README's limitations section says that the
manufacturer's software remains the authority.

### The chart layout

The charts the maintainer has, and the ones the tools should print, share one
layout, so that output can be compared with a chart by eye or with a diff. A chart
is a header naming the system and the keys of one core, then a blank line, then
one row per layer of pins from the top of the stack down, one column per chamber.
A pin that a chamber does not have, because keys share a cut there, is shown as
`--`. This example is computed from the fake example system's keys (the sub-master
and one area key, with its control key), so its numbers are consistent:

```
System = Example core
Control Key = 9743854
area_a = 5721276
master_sub = 7305496

T/D      4  6  9 10  5  8  9
Control 12 10 12  8 14  6  8
Master   2  4  2  4  2  2 --
Bottom   5  3  0  1  2  7  6
```

The row labels are T/D (the driver), Control, one Master row for every pin layer
the core needs, and Bottom. In the maintainer's chart, omitted pins appear in the
master row nearest the bottom, so the master rows nearest the control fill first;
the example above follows that and it needs confirming against a real chart. How
several cores are laid out in one file is not yet known either (see the open
questions).

## What changes in the tools

The new code is mostly new modules beside the existing ones: the pinning system
record and its registry, the pinner (cuts for one core in, pins out, or a
specific reason it cannot be built), the simulated lock, and a chart renderer.
The config loader gains the `pinning` field and a `control` entry on each core
(naming one key from `control_keys`), and validates them like the rest. The checker, when a pinning system is set, adds two things to its report:
which cores cannot be pinned and why (the chamber and the gap), and any key that
operates a core's control shear line. A new command, in the same style as the
others (`sfic-pin-system`, with a root script), prints the pinning chart for every
core in the layout above.

Two of the changes are not additive and need agreement. The first is that
pinnability becomes a hard rule for the solver alongside cross-operation and
duplicates (D6): a master that cannot be pinned over a known unit key is as bad
as one that operates the wrong core. The second is that the residual-risk estimate
assumes undecoded unit keys are uniform among valid bittings, and with a relational
validity rule the population has to be stated: it needs the pattern-as-promise
reading above, or another population model, and for a system declaring no pattern
the tools can only say what they know of the decoded keys. Neither changes any weight or
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
| 3 | The local conformance script: read the chart layout and check that the pinner reproduces every row of every chart, correcting the rules if it does not | None |
| 4 | Config and checker: the `pinning` field, `control` on each core, pinnability and control cross-operation in the report | Only for files that opt in |
| 5 | Pinnability is checked whether or not a pattern is declared, so the generator and solver work with or without parity; revisit residual risk | For opted-in files, with agreement |
| 6 | The chart command and README updates | New command |
| 7 | An ASCII drawing of each core's pin stacks in the chart output, and optional PDF output of all charts as one document, each with its own design document | New output only |

A visualizer beyond the ASCII drawing is possible later, on the same simulated lock.
The PDF output is a design question in its own right, since writing PDFs without a
dependency is not trivial.

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

The rules themselves are settled, apart from the first question below. What
remains is about the policy, the chart format and the edges of the work.

Will the keying software or the locksmith accept cuts outside the 2-step
progression? Pins of every size from 2 to 19 exist, so a change cut of 4 under a
master cut of 1 can be pinned with a 3, but the published practice offers only the
odd cuts, and the real charts cannot tell us, because they follow the pattern.
Until the owner knows, the design leaves `pattern` in the owner's hands, as
described above. The question is for the manufacturer's software or the locksmith
who does the pinning, and is worth asking before anything real is generated
without a pattern.

In the chart layout, do omitted pins always sit in the master row nearest the
bottom, as the example suggests? How are several cores laid out in one file: one
block each, separated by a blank line, or something else? Is the system name a
property of one core or of a group of cores?

For the existing building, can the unit keys be assumed to follow the parity
pattern, so that it can serve as the population promise? And should the data-file
guard grow to cover chart formats (a spreadsheet or PDF export, say), beyond
`.json` and `.csv`, which it covers today? That is a guard change in its own
commit, before step 3.

## Sources

The [Locksmith Ledger interchangeable core pinning guide](https://www.locksmithledger.com/locks/article/12440229/interchangeable-core-pinning-guide)
(read in full, from a copy the maintainer supplied) confirms the A2 stack total of
23, the control shear line 10 numbers beyond the operating one, and the worked
example reproduced above. It also supplies the 4096 figure, the remark that A2 has
no maximum adjacent cut problems, and the A3 and A4 totals. The CLK Supplies page
for the A2 pin gauge is a product page with no pinning rules, and only confirms
that the gauge sizes bottom, master and top pins. [Allegion's note on the
difference between A2 and A4 pinning](https://kc.allegion.com/kb/article/what-is-the-difference-between-a2-pinning-and-a4-pinning)
was not available when this was written and should be read before A4 is added.
