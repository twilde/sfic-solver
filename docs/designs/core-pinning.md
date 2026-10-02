# Core pinning for SFIC pinning systems (A2 first)

Status: Accepted

This document proposes teaching the tools to pin cores: to take the keys and the
hierarchy a system file already describes and work out the pins that make the
cores behave that way, for a given SFIC pinning system, starting with A2. It
also proposes a simulated lock to test the result against, and, as a
consequence, letting the physical pinning rules rather than the parity pattern
decide which bittings can be built. It is written before any code, to be
discussed and changed, and has been revised three times with the maintainer's
answers to its questions. Decisions that survive discussion will be summarised in
the log ([D25 in design.md](../design.md)).

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
great deal of the key space (about a hundredfold, as shown below). Another
symptom is that control keys are only checked for closeness and duplicates, yet an SFIC core
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
and every pin has a whole-number size. A cut is a depth, numbered from 0, no cut
at all, to 9, the deepest. A deeper cut leaves less metal under the pin, so it
lifts the stack by less: cut 0 gives the most lift and cut 9 the least, and each
step deeper loses one increment of lift. The pins make up the difference. For a
key to turn the plug, the boundary between two pins has to sit exactly on the
operating shear line, and the lower the key sits, the more pin has to be below
that boundary to get it there. So a key of cut c lines a boundary up with the
operating shear line when the pins below that boundary add up to c. That is why
cut numbers and pin numbers share one scale although the lifts they produce run
in opposite directions: bottom pin #n goes with cut n, and a cut of 4 needs 4
increments more pin below the boundary than a cut of 0 does.

A pin is named by its number of increments, and a stack of pins has a boundary at
each **partial sum** of those numbers: the first at the number of the bottom pin,
the next at the bottom pin plus the next pin, and so on. In this document the **height** of a boundary means
that total, the pin numbers beneath it. It is a place in the stack, and not how
far a key lifts. A key operates a chamber when its cut equals the height of one of
the boundaries. That is the whole mechanism, and it is why a core "accepts the
change key's cut or any master's cut" at each position: each of those cuts is a
boundary in the stack. (Bottom pins also have a fixed base length: even a #0 is a
real pin, 0.110 inch long. The base never enters the arithmetic, which is done
entirely in pin numbers.)

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

The control shear line is a further 0.125 inch out, which is 10 increments, so
the stack needs 10 more increments of pin below the boundary there. A boundary
at height 10 + c lines up with the control shear line for a control key whose
cut at that chamber is c. Operating cuts therefore match boundaries at heights
0 to 9 and control cuts match boundaries at heights 10 to 19. The two ranges
never overlap, which is why one stack can serve both.

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
from the bottom, are therefore a 3 (the change key's cut), a 4 (the distance
from 3 to 7, which is the master pin), an 8 (from 7 to 15, the control pin), and an 8
to bring the stack up to 23 (the driver, the top pin). They add up to 23, the
bottom pin is within 0 to 9, and the other three are within 2 to 19, so the
chamber can be built. The Locksmith Ledger's own worked example (a master cut of
1, a change key cut of 5 and a control cut of 3) comes out the same way, as pins
of 1, 4, 8 and 10, the numbers in the article. (The article calls the cut of 1 the
"highest" cut, which fits the picture above: it is the shallowest, the one that
lifts the stack most, and so needs the least pin below its boundary.)

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

It is also, in effect, what keying practice calls a 2-step progression, and the
published description says something the pins alone do not. The Locksmith Ledger
notes that a 6-pin A2 master key system "will generate 4096 change keys". That is
4 to the sixth power: with the master at cut 1, the change cuts at each position
are 3, 5, 7 and 9. The gap rule alone allows 3 through 9, seven cuts at each
position and 117,649 change keys for the same master. So the published practice
is narrower than the pins require. Real systems use odd-sized master pins (the
maintainer has seen them), so it is unclear why the article holds back; it may
simply be conservative, or following an even-and-odd convention of its own. Either
way the pins say what is possible, so the design takes the hardware rule as the
default. Two keys in one chamber of one core are fine if their cuts are equal (the pin
between them is simply omitted, which is why a gap of 0 is allowed) or differ by
2 or more, and are not fine if they differ by exactly 1, because no pin that short
exists. The same holds for a control pin. The existing `pattern` field stays for
owners who want the conservative style, and still means what it means today
(every key follows it): declaring one adds it to the gap rule, and leaving it out
leaves the gap rule alone. Pinnability is checked in both cases.

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
to fit the decoded ones may clash with a unit key not yet decoded. Parity would
make that safe, if every undecoded key were known to follow the pattern, but in a
building that was rekeyed without original records the unit keys follow whatever
was possible, and nobody can say they follow a parity pattern. So parity cannot be
the assumption that completes the check there. The
retired keys can, as the next section describes. Where every key under a master is
known, the tools check the gap rule per core and need no assumption at all. And in
a new system the order of generation flips: choose the masters first, then draw
each change key from the keys that avoid the neighbours of its masters' cuts,
which leaves eight or nine of the ten depths at each position instead of the five
that parity leaves.

## What the retired keys tell us

A rekey starts from a building whose original keys are known. Take an old system
with a single master and a single control, which together covered the units and
the common areas: they are held as `retired_keys`. The tools already use
them to make sure that the new cores refuse them. They also hold information,
because the old cores were physically pinned, and a core can only be pinned if no
two of its keys differ by exactly one in any chamber. So every unit key that sat
in an old core with the old master, decoded or not, avoids that master's cut plus
or minus one at every position. That needs no guess about how the unit keys were
chosen. It rests only on the old cores having been pinned as the old hierarchy
says, which is a fact about the old installation and not about its history. The old
control key adds a weaker constraint of the same kind: it excludes a unit cut of 9
wherever the old control's cut is 0.

Buildings differ in their histories: several masters, an area master above a unit
master, or separate controls for units and common areas, so the description of the
old pinning is generic and not built around any one building. A
system file may carry a `retired_cores` list in the same shape as `cores`: a
name, the keys that were the change keys (names, or wildcards such as `unit:*` so
that undecoded unit keys are covered), the retired keys pinned above them as
`masters`, and the retired `control` key. The single-master history above needs one
entry, and a richer history is simply more entries. A sketch, with invented names:

```json
"retired_cores": [
  {"name": "Original cores", "change": ["unit:*"], "masters": ["old_master"], "control": "old_control"}
]
```

The exact shape is settled when step 4 is built; what this document commits to is
that the description is generic and mirrors `cores`, so that nobody has to learn a
second notation.

It can be put to three uses, in the order they would be built. The first is a
check of the rules themselves against real data: every decoded key in a retired
core must be compatible with the retired keys pinned with it, including at odd
gaps. A failure means either that the description of the old cores is wrong or
that the rules are too strict, and it is reported as a warning for that reason.

The second is a better population for the residual-risk estimate. Today it assumes
every undecoded unit key is uniform among all valid bittings. The retired cores
let it say instead: uniform among valid bittings that also avoid the neighbours of
the retired keys pinned with them. Each retired key removes at most two of the ten
depths at each position, so the population stays large, but it is now exactly
described, and the counting that already works from per-position sets of cuts
adapts to it. The estimate gains a second figure beside the chance of
cross-operation: the chance that an undecoded unit key cannot be pinned under a
candidate master at all.

The third is guidance for the solver. At a position where the new master's cut
equals a retired master's, every unit key is compatible, at no risk; at any other,
the exact chance of a clash can be worked out per candidate cut. The closeness
rule limits how many positions can match (at most two, with seven pins and the
default `min_diff` of 5), and matching positions make it likelier that the retired
master operates the new unit cores, so this is a trade the scoring has to weigh.
That is a change to the solver's scoring, so it will be agreed before it is built
(D6).

Evidence from the decoded keys themselves, such as every one of them sharing a
parity at some position, could be shown as information. It is weaker than the
retired cores, since by chance alone a few keys will often agree, and the tools
would not rely on it.

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
(stacks, boundaries, how far a given key lifts them, which shear lines line up) is
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

The third layer is real charts. An owner may hold pinning charts for a real
system, kept outside this repository, perhaps including proposals that were set
aside for reasons other than being invalid. Every such chart is a valid pinning
with valid bittings. That makes them
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
That risk rests on one confirmed fact, that no pin shorter than 2 exists outside
the bottom family, which is all the gap rule depends on. The opposite risk, rules
that are too strict, is checked from two sides: real systems use odd-sized master
pins, and the retired-key check described above tests the rules against decoded
keys from a real system.

The fourth layer is humility in the output. Until a pinning has passed the
conformance script against real charts, anything the tools print about pinning is
labelled as unverified, and the README's limitations section says that the
manufacturer's software remains the authority.

### The chart layout

Real charts come from older keying software and are single-core charts. A chart
is a header, a blank line, and then one row per layer of pins from the top of the
stack down, one column per chamber, and the tools print the same rows, so that
output can be compared with a chart by eye. The
headers differ. A real chart's header gives `System = A2`, the control key, the
master key and a single `Change Keys` line of comma-separated bittings (the legacy
layout, shown below). The tools' charts instead list one `name = bitting` line for
every operating key, since within one core there is no difference between a master
and a change key, and a name says which key is which. They also add three lines of
metadata. The first line is the name of the key system, from a new optional field
of the system file, so a chart says which building it belongs to. After
`System = A2` come the name of the core, which the system file already has, and
the date the chart was made, in ISO form, which defaults to today and can be set
on the command line so that tests and diffs are reproducible. The labels are
provisional.

A unit core's chart carries the name of its unit key in the `Core` line, as in
`Core = Unit cores (unit:101)`, because a chart for a unit is only useful if it
says which door the core goes in. That is also a reminder of why charts are
sensitive: a chart names the units, gives the bittings and, through the pin sizes,
gives them again.

Every core's chart repeats the whole header. Cores may share a page, separated by
a horizontal line of dashes with at least one blank line on either side, and the
maintainer may later want one core per page for record-keeping, so each chart has
to stand on its own. How the separation looks is to be settled by looking at real
output.

The row labels are T/D (the driver), Control, one Master row for every pin layer
the core needs, and Bottom. Master pins fill from the bottom, so the rows nearest
Bottom are filled first and a chamber with fewer pins shows `--` in the higher
rows, as the real charts do. The example below is computed from the fake example
system's keys, so its numbers are consistent. The first core has three operating
keys, the second is a unit core with the unit control, and the third has one key:

```
Key System = Example building
System = A2
Core = Area A cores
Date = 2026-10-01
Control Key = 9743854
area_a = 5721276
master_sub = 7305496
master_top = 5961634

T/D      4  6  9 10  5  8  9
Control 12  8  8  8 12  6  8
Master  --  2  4 --  2  2 --
Master   2  4  2  4  2  4  2
Bottom   5  3  0  1  2  3  4

----------------------------------------

Key System = Example building
System = A2
Core = Unit cores (unit:101)
Date = 2026-10-01
Control Key = 3785412
unit:101 = 3101658
unit_master = 7587672

T/D     10  6  5  8  9 12 11
Control  6 12 10  8  8  4  4
Master   4  4  8  6 --  2  6
Bottom   3  1  0  1  6  5  2

----------------------------------------

Key System = Example building
System = A2
Core = Standalone cores
Date = 2026-10-01
Control Key = 9743854
area_d = 1161012

T/D      4  6  9 10  5  8  9
Control 18 16  8 12 18 14 12
Bottom   1  1  6  1  0  1  2
```

The legacy layout, as older keying software writes it, has exactly four
header lines: `System`, `Control Key`, `Master Key` and a single `Change Keys` line
listing every change key, separated by commas. It has no key system name, no core
name and no date, and its keys are known only by their roles. Every key on the
master and change lines is an operating key of the one core, so a chart with a
master and two change keys has three. The example is computed from fake keys:

```
System = A2
Control Key = 9743854
Master Key = 5961634
Change Keys = 5721276, 9565698

T/D      4  6  9 10  5  8  9
Control 10  8  8  8 12  6  6
Master  --  2 -- -- --  2  2
Master   4  2  4  4  4  4  2
Bottom   5  5  2  1  2  3  4
```

The reader for the conformance script accepts both layouts, one chart or several
separated by lines of dashes, and tells them apart by their labels. In the tools'
layout it reads `Key System`, `System`, `Core`, `Date` and `Control Key`, and takes
every other `name = bitting` line as an operating key. In the legacy layout it
reads `System`, `Control Key`, `Master Key` and `Change Keys`, splitting the last
on commas and spaces. A chart that mixes the two is refused. These labels are
therefore reserved, and when a pinning system is set a system file that names a key
`Core` or `Change Keys` would have to be refused. The legacy labels are as the
maintainer described them and have not been checked against a real chart here, so
the reader keeps its labels in one table (matched without regard to case) to make
a different spelling a one-line change.

## Charts are key data

A chart is as sensitive as the bittings it is built from, which is the rule in
CLAUDE.md, and more so once it names units and carries a date. So the chart
command writes to standard output unless it is given a file, and it is up to the
owner where that file goes. What the repository can do is refuse to commit one,
and the data-file guard grows with the features. It refuses `.json`, `.csv` and,
since the conformance script, `.txt` (D30), and charts are plain text first and
PDF later, so it learns to refuse `.pdf` in its own commit, ahead of the PDF
output. Spreadsheets are not planned, and the guard is extended as formats appear
and not by trying to list every format now. Fake fixtures under `tests/fixtures/`
stay allowed, and must be marked as fake in whatever way the format allows (for
text, a first line saying so).

## What changes in the tools

The new code is mostly new modules beside the existing ones: the pinning system
record and its registry, the pinner (cuts for one core in, pins out, or a
specific reason it cannot be built), the simulated lock, and a chart renderer.
The config loader gains the `pinning` field (and refuses a pinning system whose
cut depth count differs from the key space's, since both default to 10 but are
separate numbers), a `control` entry on each core (naming one key from
`control_keys`), an optional name for the system, and the `retired_cores` list
described above, and validates them like the rest. The checker, when a pinning
system is set, adds to its report which cores cannot be pinned and why (the
chamber and the gap), any key that operates a core's control shear line, and
the retired-core consistency check. A new command, in the same style as the
others (`sfic-pin-system`, with a root script), prints the pinning chart for
every core in the layout above.

Two of the changes are not additive and need agreement. The first is that
pinnability becomes a hard rule for the solver alongside cross-operation and
duplicates (D6): a master that cannot be pinned over a known unit key is as bad
as one that operates the wrong core. The second is that the residual-risk estimate
assumes undecoded unit keys are uniform among valid bittings, and with a relational
validity rule the population has to be stated: it comes from the retired cores, as
described above, or from a declared pattern where the owner knows one holds.
Neither changes any weight or algorithm for files that do not opt in, and each
will be raised for agreement before it is built.

## Plan

The work is split so that each step is reviewable and the risky assumptions are
tested early. Control is built into the library from the start, because the gap
rule couples control and operating cuts, and the conformance check comes before
the checker, so the rules are verified before anything depends on them.

| Step | What | Behavior change |
| --- | --- | --- |
| 1 | Refactor: bundle pin count, depth count, MACS and the optional parity pattern into one key-space rules object, in place of the loose parameters passed around today (done, D26) | None |
| 2 | Library: the pinning system record with A2, the pinner with control pins, the simulated lock, and property tests (done, D27 to D29) | None for existing files (library only) |
| 3 | (done, D30 and D31) First the data-file guard learns `.txt`, in its own commit. Then the local conformance script: read single-core charts, in the tools' layout or the legacy one (one or several to a file), and check that the pinner reproduces every row of every chart, correcting the rules if it does not | None |
| 4 | Config and checker: the `pinning` field, `control` on each core, `retired_cores`, pinnability, control cross-operation and the retired-core consistency check in the report | Only for files that opt in |
| 5 | The generator and solver work with or without a pattern; the residual-risk population comes from the retired cores, with a pinnability figure beside cross-operation | For opted-in files, with agreement |
| 6 | The chart command (with the key system name, the date and the unit names) and README updates | New command |
| 7 | An ASCII drawing of each core's pin stacks in the chart output, and optional PDF output of all charts as one document, each with its own design document; the guard learns `.pdf` first | New output only |

A visualizer beyond the ASCII drawing is possible later, on the same simulated lock.
The PDF output is a design question in its own right, since writing PDFs without a
dependency is not trivial.

Accepting this document means accepting the model and rules above, the opt-in
design, the generic description of retired cores, and the order of steps 1 to 4,
which add no behavior for files that do not opt in. Step 5 changes the solver's
scoring and the residual-risk estimate, and will be raised for agreement when its
turn comes (D6); steps 6 and 7 are output only.

## Alternatives considered

The cheapest option is to keep parity as the only validity rule and add chart
output on top. It would produce charts for today's key space and nothing more,
and it would leave the control problem and the hundredfold space as they are, so
it is the fallback if the rules cannot be verified rather than the plan.

Another is to model pinning in a generic way, with pin sizes as variables and a
solver or integer programme to find stacks. The A2 pinning turns out to be forced
(one legal stack per chamber, or none), so the problem does not need a solver, and
a dependency would break the standard-library-only rule (D2).

A fourth, which was the first design, is to keep parity as the assumption that
completes the check for undecoded unit keys. It fails for a building with no
original records, where nothing can be said about how the unit keys were cut,
which is why the retired cores took its place.

A fifth is to keep this in a separate repository. The pinner needs the same
bittings, hierarchy, counting and checks as the existing tools, so splitting would
mean copying them.

## Details to settle while building

The rules and the shape of the work are settled. These are the details left to
decide as the code is written, with the default each will take unless the
review says otherwise.

The chart header labels (`Key System`, `Core`, `Date`), the dashed separator and
the position of the metadata are provisional, and will be adjusted by looking at
real output; the reader is written to accept the labels in any order, so changing
the output does not break it. The date is the day the chart is made, overridable.
The unit key's name goes in the `Core` line.

The `retired_cores` list mirrors `cores`. Its names may refer to retired keys,
which `cores` may not, and its `change` entries may use wildcards so that
undecoded unit keys count. Whether it needs fields beyond that is found out by
writing step 4.

Fake text charts in `tests/fixtures/` begin with a line saying they are fake, and
the conformance reader skips it.

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
