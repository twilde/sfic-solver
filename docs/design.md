# Design notes

Two kinds of document explain why this project is built the way it is.

This file is the **decision log**, a running record with the newest entry last.
Each entry says what was decided and why, in a paragraph a later reader can
follow without the code open, so that a change can tell what is deliberate and
what is accident. Add an entry in the same commit as the decision.

Bigger pieces of work get their own **feature design document** in
`docs/designs/` (see D24). A feature document is written as an essay rather than
a list of choices. It starts with the problem and why it matters, builds up the
model a reader needs, walks through the alternatives that were weighed, says
what was chosen and why, lays out how the work will be split into commits, and
is honest about what is still unknown. The log then carries one short entry for
the feature that summarises the outcome and links to the document, so the log
remains a complete index of decisions even when the reasoning lives elsewhere.

Both are written as prose, not fragments: say why, and keep tables and lists
for material that really is list-shaped (formats, ranges, a plan of commits).

## Feature design documents

- [Core pinning for SFIC pinning systems (A2 first)](designs/core-pinning.md):
  pinning cores, control keys, a simulated lock, and moving beyond the parity
  pattern. Accepted (D25).

## D1. Package layout, with root scripts kept as entry points

`sfic_solver/` holds the code: `model.py` (pure maths), `config.py` (loading and
validation), and one module per tool (`gen_bittings`, `check_bittings`,
`check_system`, `solve_system`), each exposing `main(argv=None)` that returns an
exit status. The root `gen_bittings.py` etc. are four-line shims that call
those, so every pre-existing command line (`./check_system.py system.json`)
keeps working from a checkout. `pyproject.toml` adds `sfic-*` console scripts.

Why: tests can import and call the maths directly; the commands people already
use do not change. Alternative considered: flat scripts only. That works for
four files, but gives no installable commands and makes `solve_system` import
`check_system` by path.

## D2. Standard library only, Python 3.11+

No runtime dependencies. pytest is the only (optional, test) dependency. The
floor is 3.11 (see D15); CI runs 3.11-3.14. The original floor was 3.9, so the
code still has some older idioms (such as `typing.Optional`) that could be
modernised in a refactor pass.

## D3. Pin count is one patchable module constant (superseded by D21)

`model.PINS` (7) was read at call time by every function that depends on it, and
tests patched it to 3 or 4 to compare the dynamic-programming results against
brute-force enumeration. D21 replaced the global with an explicit parameter.

## D4. Counting is exact

Operating-set sizes and the pair cross-operation probability are computed by
dynamic programming over positions (MACS-trimmed), not sampled. Tests prove they
match brute force. Residual-risk figures are exact *given* the assumption that
undecoded unit keys are uniformly random valid bittings.

## D5. Randomness

`gen_bittings` draws with `secrets`; `solve_system` defaults to
`random.SystemRandom`. `--seed` exists only to make tests reproducible. Tests
assert both defaults, so changing them is a deliberate act. Generator output is
in generation order, never sorted: sorting would bias "take the first one"
toward shallow cuts.

## D6. Scoring is fixed

The solver's priorities (hard rules for cross-operation and duplicates, then
closeness among non-unit keys, then expected chance cross-operations with
undecoded unit keys) and weights (`HARD`, `CLOSE_WEIGHT`) were carried over
unchanged. Treat them as behavior: change only with a stated reason and the
user's agreement.

## D7. Config validation

All structural problems with a system file raise `ConfigError` with a message
naming the offending key or core. The command-line tools turn that into one
`error: <file>: <message>` line on stderr and exit status 1 (the same status as
before, when these were tracebacks). Rules worth knowing:

- Names are unique across `keys`, `retired_keys` and `control_keys`, and
  duplicate names inside one JSON object are an error (the JSON parser would
  otherwise silently keep the last).
- Only `keys` can be change keys or masters; the error says which section a
  misplaced name is in, and suggests close matches.
- Core names are unique (reports are keyed by core name).
- A master may not also be a change key of the same core, appear twice, and a
  key may not be matched by two `change` entries (each would silently skew the
  counts).
- Unrecognised top-level or core fields are a *warning* on stderr, not an
  error, so a hand-edited real file with extra fields still runs. Fields
  starting with `_` are free text and never warn.
- Retired keys must always be known (`null` is only for keys the solver picks).

The solver and the checker share this code path, so the same file is judged the
same way by both.

## D8. `solve_system` runs the checker in-process

After writing its result, the solver calls `check_system.main` directly, after
flushing its own output (previously a subprocess whose output could appear
before the solver's own lines when redirected). The checker's status is not the
solver's: the solver exits 0 once it has written a result. This is the original
behavior.

## D9. Private data never enters the repo

Real system files contain real bittings. Layers: `.gitignore` ignores `*.json`
except `/system.example.json` and `/tests/fixtures/**/*.json`;
`scripts/check_no_stray_data.py` runs as a pre-commit hook (staged files) and in
CI (tracked files and all history). Fixtures must carry a `_comment` starting
with `FAKE` (a test enforces it). Tests that need other configs build them in a
temporary directory. `.csv` is covered the same way (D12).

## D10. Usage errors exit 2 in every tool

A malformed command-line argument is a usage error: `usage:` plus a one-line
message on stderr and exit status 2 (argparse's convention), in all four tools.
`gen_bittings` previously let a bad pattern or `--avoid` bitting escape as a
traceback with status 1; `check_bittings` already behaved this way. Status 1
keeps meaning "the check flagged something" or "the config file is invalid".

## D11. Parity and MACS apply to keys and control keys, not retired keys

The per-key check covers `keys` and `control_keys`. A control key that broke the
parity pattern could need a pin size the system does not have, so it is held to
the same rules as operating keys. Retired keys are exempt: they exist only to be
tested for (non-)operation of the new cores, and their bittings are whatever
they were. Control keys are still never tested for operation (separate control
pinning). The solver already drew control keys from parity- and MACS-valid
candidates, so only the checker changed.

## D12. The data-file guard also covers .csv

Exports of the key matrix (a planned input format) hold the same real data as a
system file, so `*.csv` is ignored and rejected exactly like `*.json`: allowed
only under `tests/fixtures/` (the single exception for JSON is the root
`system.example.json`). `.gitignore` and `scripts/check_no_stray_data.py` must
agree; `test_gitignore_matches_the_guard` checks them against each other.

## D13. MIT license

The project is MIT licensed (copyright holder: the author). It is a small,
dependency-free planning tool, so a short permissive license fits. Apache 2.0
was the alternative; its explicit patent grant and contribution terms matter
most with many outside contributors or corporate users, which is not expected.
`LICENSE` carries the text and `pyproject.toml` the SPDX identifier. Part of the
code was written with AI assistance; commits record that with a Co-Authored-By
trailer.

## D14. CI runners are pinned, not `ubuntu-latest`

`ubuntu-latest` moves to Ubuntu 26.04 from late 2026, and Python 3.9 has no
build for 26.04 in `actions/python-versions`, so the 3.9 job would start failing
by surprise. CI therefore pins `ubuntu-24.04` for the guard job and the full
Python 3.9-3.13 matrix, and adds one Python 3.13 job on `ubuntu-26.04` so
problems with the new image show up early and on our terms. When 3.9 support is
dropped (it is already end-of-life upstream), the matrix can move to a newer
runner and these pins can be revisited. Action versions are tracked by major tag
and chosen to run on Node 24.

## D15. Python floor raised to 3.11

3.9 was already end-of-life upstream and was the only reason D14 needed runner
pins (it has no Ubuntu 26.04 build), and 3.10 reaches end-of-life in October
2026, so the floor is 3.11 and CI covers 3.11-3.14. `requires-python`, the
README, the CI matrix and a test all state the same minimum. The runner pins
from D14 stay for now; once `ubuntu-latest` has fully moved to 26.04
(rollout finishes by 2026-11-19) they can be replaced by `ubuntu-latest`.

## D16. Issue forms carry a "no real data" warning

Issues are public and users of this tool hold real key data, so pasting a real
system file into a bug report is the most likely way to leak it. All issues go
through a form (blank issues are disabled), and every form opens with the
warning and ends with a required "no real data" checkbox. The README's Privacy
section repeats it. A test checks that each form keeps the warning and the
required checkbox.

## D17. Dependabot for GitHub Actions only

CI uses third-party actions whose runtimes get deprecated (Node 20, runner
images), so Dependabot opens one grouped pull request a week to keep them
current. There is deliberately no pip entry: the package has no runtime
dependencies, and pytest and setuptools are left unpinned, so there is nothing
for it to update. Review its pull requests like any other and merge only when
CI is green.

## D18. Security reports go through GitHub private vulnerability reporting

`SECURITY.md` points reporters at GitHub's private "Report a vulnerability"
flow rather than an email address, so no personal address needs to be published
(see the noreply decision in CLAUDE.md). It separates three things: genuine
vulnerabilities (private), wrong results from the checker or solver (ordinary
public issues, reproduced with made-up data), and the standing rule never to
post real key data anywhere. It makes no response-time promise, and only the
latest `main` is supported while the project is pre-1.0.

## D19. Contribution rules

`CONTRIBUTING.md` makes the privacy rule the first and only "hard" rule (no real
key data in issues, pull requests, tests, examples or commit messages), then
restates the working agreements already in CLAUDE.md for outside contributors:
open an issue before large changes, keep scoring and algorithms stable, test
every change, keep refactors separate, keep the randomness defaults, update the
docs and this log. Contributors keep their own identity (with GitHub's noreply
address suggested), contribute under the MIT license, and are asked to disclose
AI assistance with a `Co-Authored-By` trailer, as this project does. The setup
commands are duplicated from the README, and a test keeps the two in sync.

## D20. Pull request template

Pull requests are public, so the template repeats the "never include real key
data" warning and starts its checklist with a "no real data" box, alongside the
agreements from CONTRIBUTING.md (one logical change, tests, docs, no new
dependencies, randomness defaults). It also prompts for behavior changes and AI
assistance, since both are things the maintainer wants to see explicitly.

## D21. Pin count is a parameter, not a module global (now part of KeySpace, D26)

To let the pin count vary per system file, `model.PINS` is gone. Functions that
cannot read the count off their arguments (`is_bitting`, `normalize_pattern`,
`valid_digits`, `count_valid`, `pair_conflict_probability`) take a `pins`
argument; the others use the length of the bittings or option lists they are
given. `Config.pins` carries the value to the tools, and `model.DEFAULT_PINS`
(7) is the default. Tests pass `pins` directly instead of patching a global,
which also removes the "never `from .model import PINS`" trap from D3. This
commit changes no behavior (the count is still always 7); making it
configurable comes next.

## D22. Pin count: `pins`, else the pattern's length, else 7

A system file may set `pins` (a whole number, at least 1). If it does not, the
count is the length of `pattern`, and if there is no pattern either it is 7, so
every existing file means what it did. If `pins` and `pattern` disagree the
usual pattern error is reported ("pattern must be 5 characters"). Bittings are
checked against the resulting count, and the error says what count was
expected. The count is deliberately not inferred from the bittings: `null`
bittings carry no length, and a typo in one bitting should be an error, not a
new pin count.

The command-line tools follow the same order. `gen_bittings` always has a
pattern, so its pin count is the pattern's length (any length of at least 1).
`check_bittings` takes `--pins`, else the length of `--pattern`, else 7.

`min_diff` has a pin-count-aware default of `min(5, pins)` (`gen_bittings`:
`min(3, pins)`), and an explicit value above `pins` is an error (a usage error
on the command line), because no two keys could ever satisfy it. Without this a
5-pin file that never mentions `min_diff` would be valid at 7 pins and
impossible at 4.

Scope: this covers the pin count only. Cut depths stay 0-9, and the parity
pattern, `max_step` and `min_diff` stay the only keyway rules; configurable cut
depth ranges and per-pin allowed-cut sets remain a TODO. The counting maths
needed no change beyond D21, and the existing brute-force tests now also cover
1, 2 and 5 pins. Scoring weights and algorithms are unchanged (D6).

## D23. One source of truth for the version

The version is `sfic_solver.__version__`; `pyproject.toml` declares it dynamic
and reads it from there, so it cannot drift between the two. A test checks the
format and that `pyproject.toml` holds no second copy. Release tags (`vX.Y.Z`)
must match it.

## D24. Narrative design documents for features, beside the log

The log suits decisions that fit in a paragraph, but larger work has strained
it. The pin-count change needed D21 and D22, written a commit apart, to tell one
story, and a feature that changes what the tools model needs room for things a
log entry cannot hold: the problem, the physical or mathematical model, the
alternatives, the plan, and the questions nobody can answer yet.

So a feature gets a design document in `docs/designs/`, one file per feature
named for it (`core-pinning.md`), when it changes what the tools model, will
land as several commits, or has open questions that should be discussed before
any code is written. The document is written as an essay, carries a status line
(Draft, Accepted, Implemented or Superseded), is agreed with the maintainer
before the work starts, and is revised as the design evolves. When the feature
ships it stays, as the account of why things are the way they are. The log keeps
one short entry per feature, pointing at the document; decisions that fit in a
paragraph stay in the log alone.

Alternatives considered: splitting the log into one file per decision (the ADR
style) would make it harder to read as a story and would break every reference
to `docs/design.md` (CLAUDE.md, CONTRIBUTING.md, the pull request template);
writing every feature into the log would make it unreadable. Existing entries are
unchanged: they already read as short narratives, and rewriting history helps
nobody.

## D25. Core pinning gets a feature design document

The tools will grow from "which keys operate which cores" to "which pins make
the cores behave that way", for SFIC A2 first and other pinning systems as data.
The reasoning is long and has open questions, so it lives in
[docs/designs/core-pinning.md](designs/core-pinning.md) (status: accepted) rather
than here. The decisions it records so far, none yet built: every core has
exactly one control key, which is part of its pinning, not an extra; within one
core, master and change keys are indistinguishable and all are just operating
keys; a chamber's pinning is forced, one pin per gap, so a shared cut means one
pin fewer; a simulated lock built from pins alone is the test oracle; A2 is a
data record, not code; MACS stays a system parameter; and the work opts in per
system file so that existing files keep their meaning. The real constraint on
bittings is that two operating cuts in one chamber of one core must not differ
by exactly one (and a control cut of 0 cannot share a chamber with an operating
cut of 9), which is weaker than parity; real systems use odd-sized
master pins, so that rule is the default and the `pattern` field stays only for
owners who want the conservative style. The retired keys of a rekey are evidence
about unit keys nobody has decoded, since the old cores had to be pinnable, and
they replace parity as the assumption that completes the residual-risk estimate;
the old pinning is described generically, as a list of retired cores shaped like
the current ones. Charts name the key system, the core, the unit and the date, so
they are key data, and the data-file guard grows to `.txt` and `.pdf` as the
features that read or write them are built. The conformance reader also takes
the legacy layout of older keying software (one master line and one
comma-separated list of change keys), which the tools never write.
Pinnability as a hard rule in the solver, and the new residual-risk population,
are flagged there for agreement before they are built.

## D26. The key-space rules are one object

Step 1 of core pinning (see D25). The rules that decide which bittings can be cut
travelled as loose arguments: after D21, five functions took some mix of
`pattern`, `max_step` and `pins`, and each tool unpacked the config into locals
and passed them along. Core pinning adds more rules (the cut depth count now, and
a pinning system after that), and the loose arguments would only have multiplied.
So `model.KeySpace`, a frozen dataclass of `pins`, `pattern`, `max_step` and
`depths`, holds them, the functions that need them are its methods, and the
derived values (the allowed cuts per pin, the count of valid bittings) are worked
out once and cached. `Config.space` replaces `Config.pins`, `pattern` and
`max_step`, and the tools read it from there.

There is no behavior change for any valid file. The depth count is new as a
parameter, but it defaults to 10, the only value any file can use today. The
output of all four tools, including seeded solver runs, was compared with the
output from before the change and is identical. Two small tidy-ups came with
it: `count_valid` was a second copy of `operating_set_size` fed with the
allowed cuts, so it is now the same call, and a `KeySpace` refuses a pattern
whose length is not the pin count, where the old functions would have silently
compared the shorter of the two. Review of the change asked for the rest of
its validation, since `KeySpace` is now the library entry point and the
pinning code will build one too: it also refuses a pin count, adjacent-cut
limit or depth count below 1, a depth count above 10 (a bitting is one digit
per cut) and a pattern with anything but E and O. The one command that could
reach that, `check_bittings --max-step 0`, was silently accepted before and is
now a usage error like the same option in `gen_bittings`.

## D27. Pinning systems are records in a registry

Step 2 of core pinning (D25) starts with the numbers that define A2. A
`PinningSystem` is a frozen record of the name, the increment, the cut depth
count, the stack total, the bottom and other pin number ranges and the control
offset, and `pinning.SYSTEMS` maps names to records, with `get_system` finding
one by name in any case and refusing an unknown name with the list of known ones.
A2 is the only entry. A3 and A4 have a stack total and a control offset in the
Locksmith Ledger guide but no pin ranges, so they stay out until a source gives
all the numbers. The record refuses nonsense (inverted ranges, a control line
that would fall outside the stack) so that a mistyped future entry fails when it
is defined and not when a chart looks wrong. The record is data, not logic: the
pinner reads these numbers and nothing is hard-coded to A2.

## D28. The pinner: one pin per gap, and refusals that name the chamber

`pinning.pin_core` takes a pinning system, the bittings of every key that operates
a core and the core's control bitting, and returns one `Chamber` per position (a
bottom pin, the master pins lowest first, a control pin and a driver), all in pin
numbers. The rules are the ones in the design document and read from the system
record: each distinct operating cut is a boundary, a gap between two boundaries
is a single pin, keys sharing a cut share a boundary, the control boundary sits
the control offset above the control cut, and the driver makes up the stack
total. The operating keys are an unordered set; the pinner does not know which is
the master. A chamber that cannot be built raises `PinningError`, which carries
the chamber number and a reason in plain words ("operating cuts 4 and 5 are 1
apart, so the pin between them would be 1, outside 2 to 19"), and bad input (a
cut out of range, keys of different lengths) is a `ValueError`, so a caller can
tell "this system cannot be built" from "this call is wrong". Pin sizes are
checked against each family's range rather than reduced to the gap rule, so a
system with different ranges needs no change here. The tests check the pinner
against the design's gap rule written out separately, exhaustively for one
chamber, against the Locksmith Ledger's worked example, and against the example
charts in the design document.

## D29. The simulated lock checks the pins from pins alone

`lock.Lock` is a pin stack per chamber and nothing more: it knows no change keys,
masters or control keys, and answers which shear lines a key lines up. Its geometry
is physical in form, a deeper cut lifting the stack less (cut 0 the most, cut 9 the
least), with the operating shear line at the height where bottom pin #n meets cut n
and the control line a further control offset out. Review pointed out that this is
less independent than it first read: in the arithmetic the lift cancels, a joint
being on the operating line exactly when the pins below it total the cut, so the
lock models nothing the pinner's rule does not also encode, and the calibration
(pin #n with cut n) is an input that it cannot check. What it does check, from the
pins alone, is the pinner's construction (the gaps, the partial sums, the driver
making up the total) and the key-level counting, and it does not use the pinner's
`Chamber.boundaries` or the key-level `operates`. It ignores the adjacent-cut
limit, which belongs to the keys and not to the lock.

The tests compare it with the key-level counting for every key of random
three-chamber cores, with the Ledger's example and with the example charts in the
design document, and show that splitting a gap into two pins creates a working key
nobody intended. Because the algebra alone would hide a sign slip in the lift, they
also place the stack at hand-worked absolute heights (`joint_heights`) against
shear lines written down separately. `joint_on_line` says which joint is on a shear
line in a chamber, which is what explanations and a later visualizer need. It also
shows the control cross-operation the checker will report: a key cut like a core's
control bitting lines up the control line.

## D30. The data-file guard also covers .txt

Pinning charts are key data (D25) and the tools will print them as plain text, so
the guard that already refuses `.json` (D9) and `.csv` (D12) learns `.txt` before
anything reads or writes a chart: `.gitignore`, the pre-commit hook and CI reject a
`.txt` file anywhere except under `tests/fixtures/`, where it must begin with a
line starting `FAKE` (a test enforces it, as it does for the `_comment` in JSON
fixtures). A blanket `.txt` rule is broader than charts, but the repository has
never contained a `.txt` file, in its tree or its history, and a legitimate one
(a requirements file, say) can be allowed by name when it appears, as the example
system file is. `.pdf` follows when PDF output does (D25); spreadsheets are not
planned.

## D31. The conformance command reads charts and reports positions only

Step 3 of core pinning (D25). `sfic_solver/charts.py` reads pinning charts in
either layout from the design (the tools' own, with `name = bitting` lines, and
the legacy one of older keying software, with a master line and a
comma-separated list of change keys), several to a file when separated by lines
of dashes, skipping the `FAKE` line of a test fixture. Its header labels sit in
one table, match without regard to case and may be followed by `=` or `:` (a
line that starts with a known label splits right after it, so a value may
contain colons), a chart that mixes the two layouts is refused, and every error
says which chart and line and what kind of problem, never what was written
there, because a chart is key data. Digits are ASCII only: `\d` and
`str.isdigit` also accept characters such as `²`, which `int()` then rejects
with a message that quotes them.

`check_charts` (root script `check_charts.py`, installed as `sfic-check-charts`)
pins each chart's keys with the pinning system it names and compares every
chamber with the chart, reporting each disagreement as one of four kinds: the
pins differ, the pinner refuses the chamber, the master rows do not fill from the
bottom, or a cut the system does not have. It takes files or directories of `.txt`
files (UTF-8, with or without the byte order mark that Windows tools write; any
other encoding is reported as such), or `SFIC_CHARTS` when given no path, and does
nothing when it has neither.
The report holds counts and positions (file, chart and chamber, numbered in the
order given) and no key, core or building name, bitting or pin size, so it is safe
to quote in an issue, and a test checks that on a deliberately wrong chart.
Every message is fixed text: a chart that names a pinning system the tools do not
have is reported as exactly that, without the name (a chart's `System` line is
chart content, and could hold anything), and a last-resort handler turns any
unexpected error into a fixed message, so that a future slip cannot quote a chart.
`--details` adds the pin sizes, the system name and the underlying errors for the
owner's own use, and says not to share them. The summary counts compared, agreeing
and disagreeing charts, charts that could not be checked and files that could not
be read separately, so that one kind of failure cannot skew another's count. The
closing line says DISAGREEMENTS only when a chart really disagrees, and a neutral
PROBLEMS when the only trouble is a file or chart that could not be read or
checked, so that quoting it never reports something the output does not show. The
exit status is 1 for any of them. It has been tested on fake charts computed
independently of the pinner; whether it agrees with real charts is for their owner
to find out locally, which is the point of the step.

## D32. The data-file guard also covers scans and PDFs

An owner whose charts exist only on paper will scan or photograph them, and a scan
of a chart is the chart: the pin sizes can be read off it, by eye or by OCR. So the
guard that refuses `.json`, `.csv` and `.txt` (D9, D12, D30) learns `.pdf`, `.png`,
`.jpg`, `.jpeg`, `.tif`, `.tiff`, `.heic`, `.heif`, `.bmp` and `.webp` before any
code reads such a file. `.gitignore`, the pre-commit hook and CI all enforce it. It
differs from the text rule in one way: there is no fixture exception. A text
fixture is marked fake by its first line and can be read in a diff, but a picture
can be neither, so tests that need images draw them into a temporary directory
when they run, from fake charts, and commit none. The `.gitignore` patterns are
written case-insensitively (`*.[jJ][pP][gG]`), because scanners and phones write
`SCAN.PDF` and `IMG_0001.JPG`, and git ignores by case on Linux. A legitimate image
(a screenshot in the documentation, say) can be allowed by name when one appears,
as the example system file is. The list is of formats a scan can arrive in, not of
every format; spreadsheets and word-processor files are still not planned. `.pdf`
output (D25, step 7) will need the same guard, and already has it.

## D33. How pull requests are merged, and how stacked ones work

The first four pull requests used three merge methods, and the differences
mattered. Squash and rebase merge both write new commits on `main`, so anything
built on the original commits has to move. One pull request was stacked on a
branch that was then squash-merged, and the next on one that was then
rebase-merged, and each needed rebasing. Review replies that cited commit ids
("fixed in e72ff02") pointed at commits that exist only inside the pull request,
not on `main`. A merge commit keeps the original commits, so a stack built on
them stays valid, and `git log --first-parent` still reads as one line per pull
request.

The rules follow from that. A merge commit is the default for a pull request
whose commits are meant to be read one by one (this project asks for small,
isolated commits, with a refactor in its own commit), and it is the only method
for a pull request that has another stacked on it. Squash is for a pull request
whose commits are iterative (revisions of a document, fixups), when nothing is
stacked on it; its message is written by hand as one commit message in the
project's style, without session trailers or key-history facts. Rebase merge
stays available, for a focused pull request whose commits each stand alone, when
nothing is stacked on it, no other branch is built on its commits and a straight
line is wanted; it rewrites commit ids, so references to the branch's commits
stop matching `main`. The maintainer chooses at merge time. A pull request's
title is its line in the history, so it should read as a changelog entry. For
that to be true of a merge commit, its subject is set to the title followed by the
pull request number (`gh pr merge --subject`), because GitHub's default subject
names the branch ("Merge pull request #6 from twilde/docs/merge-conventions") and
leaves the title in the body.

Stacking is allowed but not preferred. If the follow-up can wait for the base to
merge, it waits. Otherwise the stack is one level deep: the upper pull request's
base is the lower one's branch, it stays a draft, and its description says
"Stacked on #N" and is corrected when that stops being true. The bottom merges
first, as a merge commit, and "delete branch on merge" stays on, so GitHub
retargets the upper pull request to `main` by itself. Nothing force-pushes a
branch that has a pull request stacked on it; review findings on the lower pull
request are fixed with new commits. After the base merges, the upper branch's
author rebases it onto `main` (`git rebase origin/main`, or, if the base was
squashed or rebase-merged, `git rebase --onto origin/main <old tip of the base>
<branch>`), pushes with `--force-with-lease`, and says which commit is now on
GitHub, because "rebased" has meant "rebased locally" before. Rewriting is safe
here because only the upper branch's author uses it. Each stacked pull request is
reviewed against its own base, so its diff shows only its work, and again after
it is retargeted.

Alternatives considered: a strictly linear history (squash and rebase merge
only, with merge commits disallowed in the repository settings) is simpler to
explain, but it gives up the per-commit history of a squashed pull request and
makes every stack costly, so it was not chosen. Disabling rebase merge was also
rejected, since the maintainer likes its clean history and wants the option.
History already on `main` mixes the methods and is not rewritten; the merge
commits of #4, #5 and #6 keep GitHub's default subjects.

## D34. Direct commits, or a pull request

Most work here is committed straight to `main`, and some of it goes through a
pull request. The choice follows what the reviewer has already seen, not the
size of the change. A direct commit is for a change whose exact wording or intent
the maintainer has given, or that is small and low risk: a documentation fix, a
TODO update, a mechanical edit. A pull request is for new policy or design
wording the maintainer has not seen yet, for code or behavior that should pass CI
before it lands, for files another session is editing (so that its author sees
the conflict coming and resolves it on rebase), and whenever the maintainer asks
for one. Because the maintainer reviews on GitHub, a draft pull request is also
the place to put a draft for review. Whichever route is taken, the session says
which and why in one line, so the choice is never a surprise. Alternatives
considered: always committing directly (no place to review new wording, and no
warning to a session editing the same files) and always opening a pull request
(a review step for edits whose wording is already agreed).

## D35. The scan formats in the guard grow to cover more camera and web formats

Review of D32 pointed out formats that phones and scanners also write and that the
list lacked: `.dng` (a raw photograph, such as an iPhone's ProRAW), `.avif`, `.jp2`
(JPEG 2000) and `.gif`. A scan exported or renamed to one of them would have passed
every layer, so the guard, `.gitignore` (case-insensitively, as before) and the
documentation now refuse them too, and the existing test that runs every listed
extension in three cases against both the guard and `git check-ignore` covers them
without change. D32 said the list grows as formats appear, and this is that; it is
still a list of formats a scan can arrive in and not of every image format.

## D36. Tools that read scans of charts run locally

When D32 and CLAUDE.md said that tools reading scans "run locally, never through a
cloud service", that was a design decision and not a note about the guard, and it
belongs in the log. A scan of a chart is the chart: the pin sizes can be read off
it, so any service that receives the image receives the key data, and what is
sent to an outside service may be kept, cached or indexed even if it is later
deleted. A cloud OCR service would be the more accurate by default and is ruled out
for exactly that reason. The alternatives are a local engine (Tesseract, run as a
subprocess, is the candidate) and transcription by hand, which stays the fallback
for whatever a local engine cannot read with confidence. The same rule covers
debugging: a tool that reads scans reports positions only, and nobody is asked to
paste, upload or describe a scan. The feature's design document weighs the
alternatives in full when it is agreed.

