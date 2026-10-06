# Design

This document says how the tools are built and why, as the design stands now. It
is written as prose and edited in place: when a decision changes, the section it
belongs to changes in the same commit, so that reading it from the top never
meets a rule that a later paragraph takes back. It is the place for reasoning
that is too long for a log entry.

If you want to know what the tools do, read the [README](../README.md). If you
want to know when and why something was decided, or what an older rule used to
be, read the [decision log](decisions.md). If you want the full argument for a
large feature, read its document in [designs/](designs/). The rules for working
on the project are in [CLAUDE.md](../CLAUDE.md) and
[CONTRIBUTING.md](../CONTRIBUTING.md), and the review procedure is in
[reviewing.md](reviewing.md).

## How the documentation fits together

Four kinds of writing carry the project's reasoning, and each has one job, so
that a fact has one home and the others point to it.

This document describes the current design. It is the only place that says how
things are, it is revised whenever they change, and it never records a rule that
no longer holds except in the sentence that says what replaced it.

The decision log, [decisions.md](decisions.md), is a numbered record of
decisions in the order they were made. Each entry is short: what was decided,
the main reason, and a link to the section here (or the feature document) that
holds the detail. Entries are not rewritten when a decision changes. A later
entry records the change, and the old one gets a status line saying it was
superseded or amended and by which entry. The log therefore answers "when was
this decided, and what did it replace?", and this document answers "how is it
now?". The numbers are cited from code comments, tests and the feature
documents, so they are never reused or renumbered.

A feature design document, in `docs/designs/`, is the essay behind a larger piece
of work: the problem, the model, the alternatives, the plan and the questions
nobody can answer yet. A feature gets one when it changes what the tools model,
will land as several commits, or has open questions that should be settled before
any code. It carries a status line (Draft, Accepted, Implemented or Superseded),
is agreed with the maintainer before the work starts, and stays after the feature
ships as the account of why it is the way it is. This document summarises each
feature and links to its essay; the log has one entry for each.

The working rules, in CLAUDE.md and CONTRIBUTING.md, say what to do. This
document and the log say why, so a change can tell what is deliberate from what
is accident.

The reason for splitting the log from this document is that the log had grown to
forty entries, some of them several paragraphs long, and had begun to contradict
itself where later entries changed earlier ones (a continuous-integration matrix
that no longer matched the workflow, a list of refused file types that grew over
four entries, a feature recorded as "nothing built" after it was built). A log
that must stay append-only cannot also be corrected, and a document that is
corrected in place cannot also be a record. So each does one thing (D41).

## What the project is for

The tools plan and check a master-keyed SFIC key system. A system has a hierarchy
of keys (masters, sub-masters, area keys, unit keys), and each core in a door is
pinned so that certain keys operate it. The questions are which keys operate
which cores, whether any key operates a core it must not, and how likely it is
that unit keys nobody has measured yet will. The solver chooses missing bittings
to make that risk small. Core pinning, partly built (see "Pinning"), adds the
pins that make the cores behave that way.

Four commitments shape everything else.

**Real key data never enters the repository.** The repository is public, and the
data the tools work on, down to a scan of a chart, would let a stranger cut keys
for a real building. Most of the project's machinery for this is described under
"Keeping key data out of the repository", but it also shapes ordinary design:
reports that can be quoted in an issue carry positions and counts, never values;
tools that read scans run locally; examples and fixtures are random or obviously
fake.

**Counts are exact, and the tests prove it.** Operating-set sizes and the chance
that two cores cross-operate are computed by dynamic programming over the cut
positions, trimming combinations that break the adjacent-cut limit, not sampled.
Tests check them against brute-force enumeration (D4). The residual-risk figures
are exact given one assumption, that undecoded unit keys are uniformly random
valid bittings, and the report says so.

**Real keys come from real randomness.** `gen_bittings` draws with `secrets` and
`solve_system` defaults to `random.SystemRandom`. `--seed` exists only to make
tests reproducible, and tests assert both defaults so that changing one is a
deliberate act. The generator's output is in generation order and never sorted,
because sorting would bias "take the first one" toward shallow cuts (D5).

**Scoring is behavior.** The solver's priorities are hard rules for
cross-operation and duplicates, then closeness among non-unit keys, then the
expected number of chance cross-operations involving undecoded unit keys. The
weights (`HARD`, `CLOSE_WEIGHT`) and the algorithms were carried over unchanged
from the first version and are changed only with a stated reason and the
maintainer's agreement (D6). For a file that sets `pinning` there are two more,
agreed in designs/pinnable-solving.md (D56): a core that cannot be pinned, with the
keys assigned so far, is a hard conflict like a cross-operation, and the expected
number of undecoded unit keys that cannot be pinned under a unit master and its
control key joins the expected-conflict score with a weight of one (`UNPINNABLE_WEIGHT`).

## The code

The code is a package, `sfic_solver/`, with one module per tool and a few shared
ones, and a thin script at the repository root for each tool so that every
command line that has ever worked from a checkout (`./check_system.py
system.json`) keeps working. Each root script is four lines that call the
module's `main(argv=None)`, which returns an exit status; `pyproject.toml` adds a
`sfic-*` console script for each. The reasons are that tests can import and call
the maths directly, the commands people use do not change, and the alternative of
flat scripts gives no installable commands and makes one tool import another by
path (D1).

The shared modules are `model.py` (the pure maths, built around `KeySpace`), `config.py`
(loading and validating a system file), `pinning.py` (pinning system records and the
pinner), `joint.py` (the exact construction of pinnable bittings, D60), `lock.py` (the
simulated lock) and `charts.py` (reading pinning charts). The tools are `gen_bittings`,
`check_bittings`, `check_system`, `solve_system`, `check_charts` and `scan_charts`,
whose scanning stages live in the subpackage `sfic_solver/scanning/` so that the
optional imports are in one place and the core stays importable without them.

**Exit statuses** mean the same thing in every tool. A malformed command line is
a usage error: `usage:` and a one-line message on stderr, status 2, which is
argparse's convention and applies to a bad pattern or `--avoid` bitting in
`gen_bittings` as much as to a missing argument (D10). Status 1 means the check
flagged something or the system file is invalid, in which case one line reads
`error: <file>: <message>` on stderr. `scan_charts` also uses 2 for "could not
run" (a missing dependency, bad input, an output file in the way). The one
exception to "1 means flagged" is `solve_system`, which exits 0 once it has
written a result. It then runs the checker in-process, after flushing its own
output (it used to be a subprocess whose output could appear before the solver's
own lines when redirected), and the checker's status is not the solver's (D8).

**Saying that it failed.** Exit status 0 does not mean the solver succeeded, only that
it wrote a result. After the search it scores each unknown key's chosen bitting once more
and, if any still carries a hard penalty, prints a `NOT SOLVED` line that names those keys
and how many penalties each carries (a conflict between two unknown keys counts for both).
The line comes before `Wrote ...` and again after the full check, so it is the last line of
the output; the exit status is unchanged. A conflict between known keys alone does not
trigger it: nothing the solver chooses can change that, and the check reports it (D59).

## The key space

The rules that decide which bittings can be cut live in one frozen object,
`model.KeySpace`: the pin count, the optional parity pattern, the adjacent-cut
limit (MACS) and the number of cut depths. The functions that need them are its
methods, and the values derived from them (the allowed cuts per pin, the count of
valid bittings) are worked out once and cached. `Config.space` carries it from a
system file to the tools, and the pinning code builds one too.

It exists because these rules used to travel as loose arguments. Before it, the
pin count was a patchable module constant that tests overwrote, then an explicit
argument on the five functions that could not read it from their inputs, and each
tool unpacked the config into locals and passed them on. Core pinning adds more
rules, and loose arguments would only have multiplied (D3, D21, D26).

`KeySpace` validates itself, because it is now the library entry point. It
refuses a pin count, adjacent-cut limit or depth count below 1, a depth count
above 10 (a bitting is one digit per cut), and a pattern that is not exactly one
`E` or `O` per pin. `check_bittings --max-step 0`, which used to be silently
accepted, is therefore a usage error like the same option in `gen_bittings`. The
refactor changed no behavior for any valid file: the output of all four tools
then existing, including seeded solver runs, was compared with the output from
before and was identical (D26).

**The pin count** is, in order, the `pins` field of the system file, the length
of its `pattern`, or 7, so that every file written before the field existed means
what it did. If `pins` and `pattern` disagree the usual pattern error is reported
("pattern must be 5 characters"), and bittings are checked against the resulting
count, with the error saying what count was expected. The count is deliberately
not inferred from the bittings, since `null` bittings carry no length and a typo
in one bitting should be an error, not a new pin count. The command-line tools
follow the same order: `check_bittings` takes `--pins`, else the length of
`--pattern`, else 7, and `gen_bittings` the same since its pattern became optional
(D57), taking it from the pattern when there is one. The default `min_diff` is `min(5, pins)` (`min(3, pins)` for
`gen_bittings`) and an explicit value above the pin count is an error, because no
two keys could satisfy it; without that, a 5-pin file that never mentions
`min_diff` would be valid at 7 pins and impossible at 4 (D22).

**What is not configurable.** The depth count is a `KeySpace` parameter that
defaults to 10, the only value a system file can use today. Cut depths are 0 to 9
and the parity pattern, `max_step` and `min_diff` are the only keyway rules.
Configurable depth ranges and per-pin allowed-cut sets are on the TODO list and
are covered by the pinning system records described below (D22, D26).

**Parity and MACS apply to keys and control keys, not retired keys.** A control
key that broke the parity pattern could need a pin size the system does not have,
so control keys are held to the same rules as operating keys. Retired keys exist
only to be tested for (non-)operation of the new cores, and their bittings are
whatever they were. Control keys are never tested for operation, since they have
separate control pinning (D11). Closeness and duplicates cover all sections.

## System files

A system file is JSON (the README documents its fields). The loader and the
checker share one code path, so the same file is judged the same way by the
checker and the solver. Every structural problem raises `ConfigError` with a
message naming the offending key or core, which the tools turn into the one
`error:` line and status 1 (before that they were tracebacks, which also
exited 1). The rules worth knowing:

- Names are unique across `keys`, `retired_keys` and `control_keys`, and a
  duplicate name inside one JSON object is an error, since the parser would
  otherwise silently keep the last.
- Only `keys` can be change keys or masters. The error says which section a
  misplaced name is in and suggests close matches.
- Core names are unique, because reports are keyed by them.
- A master may not also be a change key of the same core or appear twice, and a
  key may not be matched by two `change` entries, because either would
  silently skew the counts.
- An unrecognised top-level or core field is a warning on stderr, not an error,
  so that a hand-edited real file with extra fields still runs. Fields starting
  with `_` are free text and never warn.
- Retired keys must always be known: `null` is only for keys the solver picks.

The pinning fields are opt-in per file, so that files without them keep their
meaning (D51). `pinning` names a pinning system, in any case; an unknown name is
refused with the known ones listed, and so is a system whose cut depth count
differs from the key space's, since both default to 10 but are separate numbers.
`name` is an optional name for the key system. With pinning set, every core needs
a `control` naming an entry in `control_keys`; without it a control is optional
but is checked if given. `retired_cores` describes the old installation in the
shape of `cores`: `change` selects names from `keys` and `retired_keys` (a
wildcard may match nothing, since undecoded units are what it is for), `masters`
and `control` name entries in `retired_keys`, and the control is required. It is
read only when pinning is set, and a file that has it without pinning is warned
that it is ignored. The loader only validates these fields; the checks that use
them are described under Pinning.

## Pinning

The tools began by treating a core as a rule, "accept the change key's cut or any
master's cut at every position", and counting what that lets through. That rule
is correct as far as it goes, but it stops short of the thing that is built:
somebody has to put pins in the cores, and the pinning has rules of its own. The
parity pattern is a policy that guarantees those rules are met without anyone
checking, at the price of about a hundredfold of the key space. Core pinning
models the pins faithfully enough that the tools can say not only "these keys are
safe" but "here are the pins, and the combination can be built". The argument is
in [designs/core-pinning.md](designs/core-pinning.md) (accepted); this section
says what has been decided and what has been built.

**The model.** Every core has exactly one control key, which is part of its
pinning and not an extra. Within a core, master and change keys are
indistinguishable: all are operating keys, and the core's behavior depends only
on their cuts. A chamber's pinning is forced, one pin per gap between distinct
cuts, so a shared cut means one pin fewer. The real constraint on bittings is
that two operating cuts in one chamber of one core must not differ by exactly one
(and a control cut of 0 cannot share a chamber with an operating cut of 9). That
is weaker than parity, and real systems use odd-sized master pins, so it is meant
to become the default, with `pattern` kept for owners who want the conservative
style. The retired keys of a rekey are evidence about unit keys nobody has
decoded, since the old cores had to be pinnable, and they are meant to replace
parity as the assumption that completes the residual-risk estimate; the old
pinning is described generically, as a list of retired cores shaped like the
current ones. MACS stays a system parameter (D25).

**Pinning systems are data.** A `PinningSystem` is a frozen record of the name,
the increment, the cut depth count, the stack total, the bottom and other pin
number ranges and the control offset, in `pinning.SYSTEMS`. `get_system` finds
one by name in any case and refuses an unknown name with the known ones listed.
A2 is the only entry: A3 and A4 have a stack total and a control offset in the
Locksmith Ledger guide but no pin ranges, so they stay out until a source gives
all the numbers. The record refuses nonsense (inverted ranges, a control line
outside the stack) so that a mistyped entry fails when defined and not when a
chart looks wrong. The pinner reads these numbers and nothing is hard-coded to A2
(D27).

**The pinner** takes a pinning system, the bittings of every key that operates a
core, and the core's control bitting, and returns one `Chamber` per position (a
bottom pin, the master pins lowest first, a control pin and a driver), all in pin
numbers. Each distinct operating cut is a boundary, keys sharing a cut share one,
the control boundary sits the control offset above the control cut, and the
driver makes up the stack total. The operating keys are an unordered set, since
the pinner does not know which is the master. A chamber that cannot be built
raises `PinningError`, which carries the chamber number and a reason in plain
words ("operating cuts 4 and 5 are 1 apart, so the pin between them would be 1,
outside 2 to 19"), while bad input (a cut out of range, keys of different
lengths) is a `ValueError`, so a caller can tell "this system cannot be built"
from "this call is wrong". Pin sizes are checked against each family's range
rather than reduced to the gap rule, so a system with different ranges needs no
change (D28).

**The simulated lock** is a pin stack per chamber and nothing more. It knows no
change keys, masters or control keys, and answers which shear lines a key lines
up. Its geometry is physical in form, a deeper cut lifting the stack less, with
the operating shear line at the height where bottom pin #n meets cut n and the
control line a control offset further out. It is less independent of the pinner
than it first looked: in the arithmetic the lift cancels, a joint being on the
operating line exactly when the pins below it total the cut, so the lock models
nothing the pinner's rule does not also encode, and the calibration (pin #n with
cut n) is an input it cannot check. What it does check, from the pins alone, is
the pinner's construction (the gaps, the partial sums, the driver making up the
total) and the key-level counting, without using the pinner's `Chamber.boundaries`
or the key-level `operates`. It ignores the adjacent-cut limit, which belongs to
the keys and not to the lock. The tests compare it with the key-level counting
for every key of random three-chamber cores, show that splitting a gap into two
pins creates a working key nobody intended, and place the stack at hand-worked
absolute heights (`joint_heights`) against shear lines written down separately,
since the algebra alone would hide a sign slip in the lift. `joint_on_line` says
which joint is on a shear line, which explanations and a later visualizer need
(D29).

**The conformance check** is the one layer that touches real data. `charts.py`
reads pinning charts in either layout from the design, the tools' own with `name
= bitting` lines and the legacy one of older keying software with a master line,
a comma-separated list of change keys, or both. Several charts to a file are separated
by lines of dashes, and the `FAKE` line of a test fixture is skipped. Header
labels sit in one table, match without regard to case and may be followed by `=`
or `:`; a line that starts with a known label splits right after it, so a value
may contain colons. A chart that mixes the two layouts is refused. Digits are
ASCII only, because `\d` and `str.isdigit` also accept characters such as `²`,
which `int()` then rejects with a message that quotes them.

`check_charts` pins each chart's keys with the pinning system the chart names and
compares every chamber with the chart, reporting each disagreement as one of four
kinds: the pins differ, the pinner refuses the chamber, the master rows do not
fill from the bottom, or a cut the system does not have. It takes files or
directories of `.txt` files (UTF-8, with or without the byte order mark Windows
tools write; any other encoding is reported as such), or `SFIC_CHARTS` when given
no path, and does nothing when it has neither.

Its report is safe to quote in an issue. It holds counts and positions (file,
chart and chamber, numbered in the order given) and no key, core or building
name, bitting or pin size. Every message is fixed text, and every error says
which chart and line and what kind of problem, never what was written there. A
chart that names a pinning system the tools do not have is reported as exactly
that, without the name, since a chart's `System` line is chart content and could
hold anything. A last-resort handler turns any unexpected error into a fixed
message, so that a future slip cannot quote a chart. `--details` adds the pin
sizes, the system name and the underlying errors for the owner's own use and says
not to share them. A test checks the quotability on a deliberately wrong chart.

The summary counts compared, agreeing and disagreeing charts, charts that could
not be checked and files that could not be read separately, so that one kind of
failure cannot skew another's count. The closing line says DISAGREEMENTS only
when a chart really disagrees, and a neutral PROBLEMS when the only trouble is a
file or chart that could not be read or checked, so that quoting it never reports
something the output does not show. The exit status is 1 for any of them. The
command is tested on fake charts computed independently of the pinner; whether it
agrees with real charts is for their owner to find out locally, which is the
point of the step (D31).

**The checker** adds a section to `check_system`'s report for a file that sets
`pinning`, after the cross-operation one. Each core is pinned once per change key
with its masters as the other operating keys and the control key it names, using
`pin_chambers`, so that every chamber that cannot be built is listed with its
reason (`UNPINNABLE`, the core, the change key and the chamber), not only the
first. A second kind of line, `CONTROL`, names a known key that would operate a
core's control shear line. A chamber has one joint in the control range, so only
the control bitting itself does, and for known keys this coincides with
`DUPLICATE`; the line is there to say which cores the duplicate would open, and
there is nothing to estimate for undecoded keys, since exactly one bitting
operates the line. Both are problems and set the exit status. Long lists stop at
30 lines with a count of the rest, as the closeness list does (D52).

The retired-core section pins each retired core, as described, once per change key
that is decoded, with its retired masters and its retired control key, and prints a
`WARNING` for every chamber that cannot be pinned. It is a warning and not a problem
because either reading of a failure is possible: the description of the old cores
may be wrong, or the rules may be stricter than the hardware, and the report says
so. Warnings do not change the exit status; the closing line counts them beside any
problems (D53).

**The population of undecoded unit keys** is a `model.Population`: a signed sum of
products of per-position cut sets, which is how a union of products is written by
inclusion and exclusion, counted by the same exact dynamic programming over
positions as every other count (D55). `population.py` builds one from the retired
cores that cover unit keys, a core covering them when a `change` wildcard starts
with the unit prefix. At each position it keeps the cuts for which that chamber
could have been pinned with the retired masters and control, found with the pinner
chamber by chamber and not with a hard-coded neighbour rule, so a pinning system
with other pin ranges needs no change. Several covering cores give the union, up to
three, since a unit key sat in one of them and which is not known; the unit-to-unit
figure costs (2^n - 1)^2 pair counts for every candidate the solver scores, which
rules out more. With more than three, with none, or when no bitting could have been pinned in them,
the population is every valid bitting, as before, and the report says when the
retired cores were not used and why, since a file is not refused, and its report not
cut short, over a disputed description (D53). `check_system` uses it in the
residual-risk section, says which population it assumed, and for each unit core adds
how many undecoded unit keys cannot be pinned under that core's masters and control
key; a unit core with no master is asked about its control key alone. Without
`pinning` the section is unchanged to the byte.

**The solver** takes the same population and figures. For a file that sets `pinning`
it pins every core a candidate key takes part in, as change key, master or control key,
with the keys assigned so far, and adds the hard penalty for each chamber that cannot
be pinned, so that fixing one of three bad chambers is progress for the hill climb. A
control key being solved for is scored against every core that uses it. A core
whose keys, or whose control key, are not all assigned yet is skipped until they are,
as the cross-operation test already does. The expected-unpinnable figure is added to the
unit core's expected-conflict term with a weight of one. On the fake pinning fixture
without a parity pattern the solver picks a unit master that about a fifth of the
undecoded units cannot take, against about four fifths for a random one. The population
is the checker's, through the same functions, and when the retired cores cannot be used
the solver prints the same line the checker does. Its summary of chance cross-operation
is followed, for such files, by the unpinnable figure against a random master's, because
the chosen master can have more chance cross-operation than a random one and look worse
without it. Files that do not set `pinning` give
byte-identical output and files, which is shown by seeded runs before and after (D56).

**Building pinnable answers exactly.** The one-key-at-a-time hill climb cannot fix two
keys that are both wrong at a position when changing either alone leaves the number of
failing chambers unchanged, and random draws hit a pinnable pair only by luck. Since
pinning is decided one chamber at a time, `joint.py` lists, for each position, the digit
tuples of a group of unknown keys that leave every core involved pinnable with the known
keys, then counts the whole bittings exactly with the adjacent-cut limit (a dynamic
programme over positions) and draws uniformly from them, or lists them all when there
are no more than `--trials`. A group is the unknown keys that share a core, as change
key, master or control key, so that all the keys of any one core are chosen together; a
group has at most three keys (`MAX_JOINT_KEYS`, 10 ** 3 tuples a position), and a larger
one falls back to the single-key search with a printed line. The candidates are scored
with the existing score, so weights, closeness and the unpinnable figure are unchanged;
only where the candidates come from is. When a group has no pinnable bitting the solver
says which positions have none and ends with `NOT SOLVED`, since only a known key can
change that (D60). Files without `pinning` are byte-identical.

**The chart command** (`pin_system.py`, `sfic-pin-system`) prints the charts of the
layout in core-pinning.md for every core of a file that sets `pinning`, one chart per core
and change key. The writer (`chartwriter.py`) is a separate module from the reader so
that the reader's label table is the writer's too, and a test reads back what it prints
and checks it with the conformance checker. A core's `Core` line carries the key's name
for a unit core or one with several change keys. The date is today unless `--date`, which
tests and diffs use. A core that cannot be pinned stops the run with the checker's
`UNPINNABLE` lines and no chart, since a set of charts with a core missing would look
complete. Output goes to standard output, or to `--out` for a new file only, with a reminder
that it is key data; the command never writes inside the repository on its own (D58).

With `--draw` each chart is followed by a drawing of its pin stacks (D61,
[designs/ascii-stack-drawing.md](designs/ascii-stack-drawing.md)): `chartwriter.draw_stacks`
draws one column per chamber to scale, one line per increment, with a ruler built from the
pinning system's own numbers, and the reader skips everything after a `Stacks` line that
follows the rows. The tests read each drawing back and compare it with the chambers and with
the simulated lock's geometry, so the drawing is checked, not only looked at.

**What is built and what is not.** The key-space object (step 1), the pinning
library and simulated lock (step 2), the guard and the conformance script (step 3),
the config and checker for opted-in files (step 4) and step 5, which finishes the
design in [designs/pinnable-solving.md](designs/pinnable-solving.md) (D54): the
population and the expected-unpinnable figure in the checker, the solver's use of
them, and the generator running without a pattern (D55 to D57), and step 6, the chart
command (D58), and step 7a, the ASCII drawing of the stacks (D61). The rest is not: the PDF
output. None of it changes any weight or algorithm for files that do not opt in (D6).

## Reading scanned charts

An owner whose pinning charts exist only on paper needs them as text before
`check_charts` can run on them. [designs/chart-scanning.md](designs/chart-scanning.md)
(accepted) designs a local tool for that, and `sfic-scan-charts` is built, with its
test harness and its README section. Work on it is suspended (D44): it is not
being developed, it does not yet read real printouts well, and the README says so;
issues and fixes are welcome. What it commits to:

The tool transcribes and never repairs. It never consults the pinner or the
pinning rules to choose a reading, because a tool that quietly "fixes" what it
reads so that the chart comes out right would make the conformance check
unfalsifiable. It fails closed. Charts that passed every chart-internal check go
to one file; charts read completely that failed a chart-internal check go to a
second that `check_charts` can read; and the rest, with `??` where a cell could
not be read, go to a review file that `check_charts` deliberately refuses. The
report names positions only.

Tesseract, run locally as a subprocess, reads each row of cells as a line, and
its readings are used as votes that label groups of digit marks of the same shape
on the document itself. Per-row agreement among Tesseract's readings was shown to
flag most charts yet still pass a systematic misreading, which the votes on
shapes catch. The check that every chamber's pins add up to the stack total is
the strongest chart-internal test, and it only ever flags.

**It is tested on charts drawn at test time.** No scan is ever committed or
described, so the tests draw charts that the pinner computes from random fake
bittings and read them with the real pipeline (`tests/scan_harness.py`). What every
condition must show is that no chart is accepted that differs from the one drawn;
how many are accepted is a second, softer assertion. A small seeded sample per
condition always runs (image damage, fonts, a cell or row erased or inked over,
pages too poor to read, margin notes, a PDF), and takes about six minutes because a
chart costs six or seven seconds. The 1,000-chart run that would support a claim in
the README is a slow tier, `pytest --runslow`, run by hand and not yet made. In a
sample of 120 clean and degraded charts nothing wrong was accepted, and 8 were
flagged, one of them among the 12 clean charts
([issue #12](https://github.com/twilde/sfic-solver/issues/12)); the figures and
what the harness covers are in the design document. A first trial on real scans
found three problems that the drawn charts did not show
([issue #16](https://github.com/twilde/sfic-solver/issues/16)).

**Scans are processed locally, always.** A scan of a chart is the chart: the pin
sizes can be read off it, so any service that receives the image receives the key
data, and what is sent to an outside service may be kept, cached or indexed even
if it is later deleted. A cloud recognition service is typically more accurate,
and that alone rules it out. The alternatives are a local engine and
transcription by hand, which stays the fallback for whatever the engine cannot
read with confidence. The same rule covers debugging: a tool that reads scans
reports positions only, and nobody is asked to paste, upload or describe a scan
(D36).

**The exception to "standard library only".** Reading an image needs an image
library and a recogniser, so scanning is the one feature that cannot honor
that rule, and the exception is bounded. The dependencies are an optional extra
(`pip install -e ".[scan]"`: Pillow, numpy and pypdfium2, chosen over `pdftoppm`
for needing no system install and over PyMuPDF for its license) and an optional
Tesseract found at run time. `pyproject.toml` keeps `dependencies = []`, nothing
in the core imports the extra, and a missing package or program gives a clear
message and exit status 2 instead of a traceback. The exception covers this
feature alone; a later feature that wants a dependency (PDF output is the likely
one) needs its own decision. The terms are in "An exception to D2, and its
limits" in the feature document (D2, D38).

## Keeping key data out of the repository

A real system file contains real bittings, and so does anything derived from
one. The protection is layered so that no single slip commits data.

**What counts as key data.** System files, exports of a key matrix, and pinning
charts in any format: text, scan, photograph or PDF. A chart is key data because
the pin sizes in each chamber give the bittings away, and it stays key data
re-typed or "anonymised" from a real one. Charts also name the key system, the
core, the unit and the date. Facts about the real building's key history count as
well, even with no names or bittings in them, so design reasoning is written as
general scenarios and never as facts about this one. Real files live outside the
repository and nobody goes looking for them.

**The guard.** `scripts/check_no_stray_data.py` runs as a pre-commit hook (on
staged files) and in CI (on every tracked file and on all history), and
`.gitignore` ignores the same files so that `git add` does not pick them up.
There are two rules:

- Text data (`.json`, `.csv`, `.txt`) is allowed only as `system.example.json` at
  the root and under `tests/fixtures/`. A fixture must carry obviously fake data,
  and a test enforces the marker: a `_comment` starting `FAKE` in JSON, a first
  line starting `FAKE` in text. `.csv` joined the rule because a key matrix export
  holds the same data as a system file (D12), and `.txt` because pinning charts
  are key data that the tools print as plain text (D30). A blanket `.txt` rule is
  broader than charts, but the repository has never contained a `.txt` file and a
  legitimate one can be allowed by name, as the example system file is.
- Scans and PDFs (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.heic`,
  `.heif`, `.dng`, `.avif`, `.jp2`, `.gif`, `.bmp`, `.webp`) are refused
  everywhere, fixtures included. A text fixture is marked fake by its first line
  and can be read in a diff, but a picture can be neither, so tests that need
  images draw them into a temporary directory when they run, from fake charts,
  and commit none. The `.gitignore` patterns are written case-insensitively
  (`*.[jJ][pP][gG]`), because scanners and phones write `SCAN.PDF` and
  `IMG_0001.JPG`, and git ignores by case on Linux. The list is of formats a scan
  can arrive in, not of every image format, and it has grown as review found
  formats a phone writes that it lacked (`.dng`, `.avif`, `.jp2`, `.gif`). A
  legitimate image, such as a screenshot in the documentation, can be allowed by
  name when one appears (D32, D35).

A test runs every listed extension in three cases against both the guard and
`git check-ignore`, and `.gitignore` and the guard must agree. Nobody bypasses
the layers (`--no-verify`, `git add -f`) (D9).

**The public surface.** Issues and pull requests are public, and users of this
tool hold real key data, so pasting a real system file into a bug report is the
likeliest way to leak it. Blank issues are disabled, and every issue form opens
with a warning and ends with a required "no real data" checkbox, a test checks
that each form keeps them, and the README's Privacy section repeats it (D16). The
pull request template repeats the warning and starts its checklist with a "no
real data" box (D20). `SECURITY.md` points reporters at GitHub's private
vulnerability reporting rather than an email address, so no personal address is
published; it separates genuine vulnerabilities (private), wrong results from the
checker or solver (ordinary public issues, reproduced with made-up data) and the
standing rule never to post real key data anywhere, and promises no response
time (D18).

**Commits.** Commit emails are public and permanent, so commits use the
author's GitHub noreply address. AI involvement is shown with a `Co-Authored-By`
trailer, and cloud sessions also add a `Claude-Session:` trailer and a link to
their claude.ai session. The harness adds those whatever this repository says, so
they are accepted: a link needs the owner's login to open and exposes only a
session identifier. The care that keeps that cheap is that the conversation
behind a link may discuss the real building and its keys, so nothing from a
conversation is copied into a commit or pull request, and sharing stays off for
any session that discussed real key data. A hand-written squash message may omit
the trailer (D37).

## Dependencies, Python versions and CI

**Standard library only, Python 3.11 or newer.** The core tools have no runtime
dependencies, and pytest is the only test dependency. The one exception is
scanning, above: the README, CLAUDE.md, CONTRIBUTING.md and SECURITY.md each say
"standard library only" with that exception named in the same paragraph, and a
test keeps them so. The floor is 3.11: 3.9 was already end-of-life upstream and
had no build for Ubuntu 26.04, and 3.10 reaches end-of-life in October 2026.
`requires-python`, the README, the CI matrix and a test all state the same
minimum. Some older idioms (such as `typing.Optional`) remain from the days of
3.9 and could be modernised in a refactor pass (D2, D15).

**CI runs once per change.** It triggers on pull requests, on pushes to `main` and
`v*` tags, and by hand (`workflow_dispatch`), not on every push: a branch with a pull
request is tested by the pull request run, and triggering on its pushes as well tested
every commit twice. A branch pushed with no pull request, which CLAUDE.md allows for
getting something reviewed early, is therefore not tested until someone runs CI on it
from the Actions tab or opens a pull request (D47).

A new push to a pull request cancels that pull request's run still in progress,
since its result no longer matters (D48). Only pull requests share a concurrency
group. Runs on `main`, tags and manual runs each get their own, so none is ever
cancelled: with a shared group GitHub also drops an older queued run when a newer one
arrives, even without cancel-in-progress, and a commit on `main` could go untested.

**CI** runs a guard job (the stray-data checks over tracked files and over
history) and a test matrix on Python 3.11 to 3.14 on `ubuntu-24.04`, plus one
Python 3.14 job on `ubuntu-26.04` so that problems with the new image show up
early and on our terms. Runners are pinned rather than `ubuntu-latest` because
`ubuntu-latest` moves to 26.04 from late 2026, and a surprise change of image is
not the kind of failure to take by surprise. Once the rollout finishes (by
2026-11-19) the pins can be replaced by `ubuntu-latest`, which is on the TODO
list. The test jobs install only pytest, as a contributor can, so the scanner's
tests that need the `scan` extra or Tesseract skip there, which also shows that
nothing else depends on them (issue #15 was a test that did), and a last step runs
the installed commands. Action versions are tracked by major tag and chosen to run
on Node 24 (D14, D15).

**The scanner's checks run only when a change can affect them** (D46). They are the
slow ones: they install Tesseract and the fonts the tests draw with and the `scan`
extra, then draw and read charts, the quality tests included, on the same matrix as
the test job. A small job, `changes`, runs `scripts/ci_changes.py`, which lists the
files a pull request changes relative to its base and says whether any is the scanner,
a core module it imports, a root script its tests run, its tests, `pyproject.toml` or
CI itself. The `scanner` matrix runs if so. Everything that is not a pull request
(pushes to `main`, tags, a manual run) always runs it, and so does any case where the
comparison cannot be made (a git failure), since skipping by mistake is worse than
running by mistake. The list of paths is in the script, and a test reads the imports of
the scanner's code and tests, and the root scripts the tests run, and fails if one is
missing from it. Both the filter and the jobs are
in the workflow rather than a `paths:` filter on it, because that would stop the
whole workflow, the guard and the core tests with it.

**One check to require.** A final job, `CI passed`, always runs and waits for the
guard, the comparison, the test matrix and the scanner matrix. It passes only if the
first three succeeded and the scanner either succeeded, when the comparison asked for
it, or was skipped, when it did not; a failed, cancelled or undecided job fails it.
Branch protection should require this check and nothing else, because the individual
checks are the wrong thing to require: a skipped matrix shows as one check without the
matrix names, and every change to the Python versions renames them (D49). Every job
also has a `timeout-minutes`, since the default is six hours and a hung Tesseract
should not hold a runner that long, and the pytest steps print their ten slowest
cases (`--durations=10`) so that a test that grows slow shows in the log. A test runs
the summary job's script against each combination of results.

**Choosing tests in a session.** The comparison that decides whether CI runs the
scanner's tests is a script, so a session can ask the same question before it
commits: `scripts/ci_changes.py --base origin/main` prints `scanner=false` or
`scanner=true`. CLAUDE.md tells sessions to run the tests of the module they are
changing as they go, and before committing the whole suite in a venv with only
`.[test]`, adding the `scan` extra and a second run only on `scanner=true`. The
scanner's tests are about two thirds of the suite's time even without Tesseract, and a
session usually has none, so the rule saves the most where the check can least be
made anyway. CI is the backstop, so a session says which it ran rather than claiming
the full suite. The same rule applies to a reviewer testing a merged head (D50).

**Dependabot** opens one grouped pull request a week for GitHub Actions only,
because CI uses third-party actions whose runtimes get deprecated. There is
deliberately no pip entry: the package has no runtime dependencies, and pytest and
setuptools are left unpinned, so there is nothing for it to update. Its pull
requests are reviewed like any other and merged only when CI is green (D17).

**The version** is `sfic_solver.__version__`, and `pyproject.toml` declares it
dynamic and reads it from there, so the two cannot drift. A test checks the
format and that `pyproject.toml` holds no second copy. Release tags (`vX.Y.Z`)
must match it (D23).

**The license** is MIT, with the author as copyright holder. It is a small,
dependency-free planning tool, so a short permissive license fits; Apache 2.0's
patent grant and contribution terms matter most with many outside contributors
or corporate users, which is not expected. `LICENSE` carries the text and
`pyproject.toml` the SPDX identifier (D13).

## Contributing

`CONTRIBUTING.md` makes the privacy rule the first and only hard rule, then
restates for outside contributors the working agreements in CLAUDE.md: open an
issue before large changes, keep scoring and algorithms stable, test every change,
keep refactors in their own commits, keep the randomness defaults, and update the
docs and the log. Contributors keep their own identity (GitHub's noreply address
suggested), contribute under the MIT license, and are asked to disclose AI
assistance with a `Co-Authored-By` trailer, as this project does. The setup
commands are duplicated from the README and a test keeps the two in step (D19).
When one fact is written in several files (a version, a list of extensions, the
setup commands), a test keeps the copies in step, because a list in prose is where
the gaps appeared.

## Pull requests, merging and review

### Direct commit or pull request

Most work is committed straight to `main`, and some goes through a pull request.
The choice follows what the reviewer has already seen, not the size of the
change. A direct commit is for a change whose exact wording or intent the
maintainer has given, or that is small and low risk: a documentation fix, a TODO
update, a mechanical edit. A pull request is for new policy or design wording the
maintainer has not seen, for code or behavior that should pass CI before it lands,
for files another session is editing (so that its author sees the conflict coming
and resolves it on rebase), and whenever the maintainer asks. A draft pull
request is also the place to put a draft for review. Whichever route is taken, the
session says which and why in one line. Always committing directly would give no
place to review new wording and no warning to a session editing the same files,
and always opening a pull request would add a review step to edits whose wording
is already agreed (D34).

### Merging

The first four pull requests used three merge methods, and the differences
mattered. Squash and rebase merge both write new commits on `main`, so anything
built on the original commits has to move: one pull request was stacked on a
branch that was then squash-merged and the next on one that was rebase-merged, and
each needed rebasing. Review replies that cited commit ids pointed at commits
that exist only inside the pull request. A merge commit keeps the original
commits, so a stack built on them stays valid, and `git log --first-parent` still
reads as one line per pull request.

So a merge commit is the default for a pull request whose commits are meant to be
read one by one (the project asks for small, isolated commits, with a refactor in
its own commit), and it is the only method for a pull request that has another
stacked on it. Squash is for a pull request whose commits are iterative
(revisions of a document, fixups), when nothing is stacked on it, and its message
is written by hand as one commit message in the project's style without
key-history facts. Rebase merge stays available for a focused pull request whose
commits each stand alone, when nothing is stacked on it, no other branch is built
on its commits and a straight line is wanted; it rewrites commit ids, so
references to the branch's commits stop matching `main`. The maintainer chooses
at merge time. A pull request's title is its line in the history, so it reads as
a changelog entry, and a merge commit's subject is set to the title followed by
the pull request number (`gh pr merge --subject`), because GitHub's default
subject names the branch and leaves the title in the body.

A strictly linear history (squash and rebase merge only, with merge commits
disabled in the repository settings) is simpler to explain, but it gives up the
per-commit history of a squashed pull request and makes every stack costly, and
disabling rebase merge was rejected because the maintainer likes its clean
history and wants the option. History already on `main` mixes the methods and is
not rewritten; the merge commits of three early pull requests keep GitHub's default
subjects (D33).

### Stacked pull requests

Stacking is allowed but not preferred: if the follow-up can wait for the base to
merge, it waits. Otherwise the stack is one level deep. The upper pull request's
base is the lower one's branch, it stays a draft, and its description says
"Stacked on #N" and is corrected when that stops being true. The bottom merges
first, as a merge commit, and "delete branch on merge" stays on, so GitHub
retargets the upper pull request to `main` by itself. Nothing force-pushes a
branch that has a pull request stacked on it, and review findings on the lower
pull request are fixed with new commits. After the base merges, the upper
branch's author rebases it onto `main` (`git rebase origin/main`, or, if the base
was squashed or rebase-merged, `git rebase --onto origin/main <old tip of the
base> <branch>`), pushes with `--force-with-lease`, and says which commit is now
on GitHub, because "rebased" has meant "rebased locally" before. Rewriting is safe
here because only the upper branch's author uses it. Each stacked pull request is
reviewed against its own base, so its diff shows only its work, and again after it
is retargeted (D33).

### Pull requests are independent

Every pull request is treated as owned by a separate party, including one that we,
or another session, wrote. It is reviewed through GitHub, and its author resolves
the comments. Nobody else commits to, pushes to, rebases or force-pushes its
branch, edits its description, or builds a competing copy of its work. Reading it,
checking it out in a scratch worktree and running its tests are fine. No pull
request, draft or not, carries open questions or exists to ask for a decision;
those are settled in chat first, and work to be seen before then goes on a branch
without a pull request. A design document may still say what nobody can know yet,
but not a question waiting for an answer (D39, D40).

### How a review closes

Reviews are done through GitHub by a session or a person other than the author,
and the author is often another session, so how a review ends has to be written
down. The case that showed it was a pull request merged while two review notes had
no reply and nothing tracked them: an extension list that had been missing
formats, and a rule that was being broken in its own description. The notes sat
on a closed pull request where they were easy to lose, and the project had filed
no issues at all.

Each inline comment starts with a label, Should fix or Optional, and the summary
says whether anything blocks (GitHub does not let an author approve or request
changes on their own pull request, so the verdict has to be in the text). The
author answers every thread with a disposition: fixed in a commit, tracked in an
issue or a named pull request, or declined with a reason. A pull request merges
when no Should-fix thread is open and every Optional one has a disposition. If
the maintainer says to merge now, the merge goes ahead and the leftovers are filed
as an issue straight away. This is the maintainer's own habit of merging only when
nothing is open, made precise enough for a review with optional notes. GitHub's
"require conversation resolution" setting was not used: it blocks a deliberate
merge as well, and the dispositions do the same job without that. Reproductions in
a review use obviously fake names, because a placeholder invented for a review was
copied into a test and read like a real building (D39).

### How a merge is checked

A merge is checked at both ends. Before it, the head on GitHub must be the one
that was reviewed, CI must be green, and the pull request must be tested merged
into current `main`, since that is what lands. The merge is pinned to the
reviewed head (`--match-head-commit`), so nothing pushed afterwards can slip in.
After it, `main` is updated and the first-parent log, the preservation of the
original commits and the test suite are checked, which is also how a wrong merge
subject was noticed. A refactor that claims to change no behavior shows it, by
comparing the output of the commands before and after, seeded runs included, which
is what the key-space refactor did (D39).

### The review task

The maintainer wanted one central session to review larger changes, so that every
change gets a second pair of eyes (the same model, but a session that did not
write the change), while keeping that session's checkout of `main` current for
merging. The procedure is written once, in [reviewing.md](reviewing.md), so a
local task and a cloud session read the same text, and CLAUDE.md keeps only the
policy.

The trigger is manual. A timer would start a session every few minutes to find
nothing, which costs context and money, and the maintainer knows when they are
working on a pull request, so the task is started with "run now". It can be given
a timer later without changing the procedure. It reviews only pull requests from
the maintainer's own account, which includes those cloud sessions open, because
reviewing another person's pull request means checking it out and running its
tests and the repository is public; anything else only produces a report.
Dependabot keeps its own rule. The review never changes the pull request and never
merges, but it does judge: it opens with a verdict, Changes requested or Approved,
and a re-review says which earlier requests are now met. Because it comes from the
same account as the pull request, GitHub's own buttons are unavailable and the
verdict is in the text. Merging, and keeping the local `main` current, stay in the
maintainer's central session, which follows the merge procedure above. The task
needs no state of its own: a review records the head it covered, so "needs a
review" means no review of ours at the current head (D40).

### Numbering log entries

Log entries were numbered over the top of each other three times by pull requests
open at once, so the next free number is taken after looking at the open
branches, and whichever merges second rebases (D39).
