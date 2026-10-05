# Decision log

A numbered record of decisions, newest last. It answers "when was this decided,
and what did it replace?". How things are now, and the reasoning at length, is in
[design.md](design.md), and the essays behind large features are in
[designs/](designs/). The three work together (D41).

## How to write an entry

- **Short.** What was decided and the main reason, in a few sentences (the
  limit a test enforces is 150 words). If the alternatives matter, one sentence
  on the one rejected. Reasoning that needs more room is written in design.md or
  in a feature document, and the entry points to it.
- **A `Detail:` line** at the end, linking to the section of design.md or the
  feature document that holds the reasoning. A test checks that the anchors exist.
- **Append-only.** An entry is not rewritten when the decision changes. Write a
  new entry, and give the old one a `Status:` line (`Status: Superseded by D26.`
  or `Status: Amended by D32.`) so a reader of it is sent forward. Correcting a
  slip or a broken link is fine. The current rule is edited in design.md in the
  same commit as the new entry, so the two never disagree.
- **Numbered, never reused.** Code comments, tests and documents cite the numbers.
  Before numbering a new entry, look at the open pull request branches
  (`git show origin/BRANCH:docs/decisions.md | grep '^## D'`) and take the next free
  number; whichever merges second rebases (D39).

A decision that fits in a few sentences is an entry and nothing more. A feature
that changes what the tools model, will land as several commits, or has open
questions gets a design document first (D24) and one entry here.

## D1. Package layout, with root scripts kept as entry points

`sfic_solver/` holds the code, one module per tool plus shared `model.py` and
`config.py`, each tool exposing `main(argv=None)` that returns an exit status. The
root scripts are four-line shims that call them, so every existing command line
keeps working from a checkout, and `pyproject.toml` adds `sfic-*` console scripts.
Flat scripts alone would give no installable commands.

Detail: [design.md, "The code"](design.md#the-code).

## D2. Standard library only, Python 3.11+

No runtime dependencies; pytest is the only (test) dependency. The floor is 3.11
(D15). One feature, reading scanned charts, is a bounded exception: an optional
`scan` extra and an optional Tesseract program (D38).

Detail: [design.md, "Dependencies, Python versions and CI"](design.md#dependencies-python-versions-and-ci),
[chart-scanning.md, "An exception to D2, and its limits"](designs/chart-scanning.md#an-exception-to-d2-and-its-limits).

## D3. Pin count is one patchable module constant

Status: Superseded by D21.

`model.PINS` (7) was read at call time, and tests patched it to compare the
dynamic-programming counts against brute force.

## D4. Counting is exact

Operating-set sizes and the pair cross-operation probability are computed by
dynamic programming over positions (trimming combinations that break MACS), not
sampled, and tests prove them against brute-force enumeration. Residual-risk
figures are exact given that undecoded unit keys are uniformly random valid
bittings.

Detail: [design.md, "What the project is for"](design.md#what-the-project-is-for).

## D5. Randomness

`gen_bittings` draws with `secrets` and `solve_system` defaults to
`random.SystemRandom`; `--seed` is for tests only, and tests assert both defaults.
Generator output is never sorted, since sorting would bias "take the first one"
toward shallow cuts.

Detail: [design.md, "What the project is for"](design.md#what-the-project-is-for).

## D6. Scoring is fixed

The solver's priorities (hard rules for cross-operation and duplicates, then
closeness among non-unit keys, then expected chance cross-operations with
undecoded unit keys) and weights were carried over unchanged. They are behavior:
change them only with a stated reason and the maintainer's agreement.

Detail: [design.md, "What the project is for"](design.md#what-the-project-is-for).

## D7. Config validation

Every structural problem with a system file raises `ConfigError` naming the
offending key or core; the tools print one `error: <file>: <message>` line and
exit with status 1. Unrecognised fields are a warning, not an error, so a
hand-edited real file still runs. The solver and the checker share the code path,
so both judge a file the same way.

Detail: [design.md, "System files"](design.md#system-files).

## D8. `solve_system` runs the checker in-process

The solver calls `check_system.main` directly after flushing its own output (a
subprocess's output could appear first when redirected). The checker's status is not
the solver's: the solver exits 0 once it has written a result.

Detail: [design.md, "The code"](design.md#the-code).

## D9. Private data never enters the repo

Real system files hold real bittings, so `.gitignore` ignores `*.json` except
`system.example.json` and fixtures, and `scripts/check_no_stray_data.py` runs as a
pre-commit hook and in CI over tracked files and all history. Fixtures must say
they are fake. Later entries widened the rule (D12, D30, D32, D35).

Detail: [design.md, "Keeping key data out of the repository"](design.md#keeping-key-data-out-of-the-repository).

## D10. Usage errors exit 2 in every tool

A malformed command-line argument gives `usage:` and a one-line message on stderr
and exit status 2 in every tool. Status 1 keeps meaning "the check flagged
something" or "the config file is invalid".

Detail: [design.md, "The code"](design.md#the-code).

## D11. Parity and MACS apply to keys and control keys, not retired keys

A control key that broke parity could need a pin size the system does not have, so
control keys are held to the same rules as operating keys. Retired keys are exempt:
they exist only to be tested for non-operation. Control keys are still never tested
for operation.

Detail: [design.md, "The key space"](design.md#the-key-space).

## D12. The data-file guard also covers .csv

Status: Amended by D30, D32, D35.

Exports of the key matrix hold the same data as a system file, so `*.csv` is refused
exactly like `*.json`, with the same fixture exception.

Detail: [design.md, "Keeping key data out of the repository"](design.md#keeping-key-data-out-of-the-repository).

## D13. MIT license

MIT, copyright the author: a small, dependency-free planning tool suits a short
permissive license. Apache 2.0 was the alternative, whose patent grant matters most
with many outside or corporate contributors, which is not expected.

Detail: [design.md, "Dependencies, Python versions and CI"](design.md#dependencies-python-versions-and-ci).

## D14. CI runners are pinned, not `ubuntu-latest`

Status: Amended by D15.

`ubuntu-latest` moves to Ubuntu 26.04 from late 2026, so CI pins `ubuntu-24.04` for
the main jobs and adds one job on `ubuntu-26.04`, to meet problems with the new image
early and on our terms. The pins can be replaced once the rollout finishes.

Detail: [design.md, "Dependencies, Python versions and CI"](design.md#dependencies-python-versions-and-ci).

## D15. Python floor raised to 3.11

3.9 was end-of-life and had no 26.04 build, and 3.10 reaches end-of-life in
October 2026. `requires-python`, the README, the CI matrix (3.11 to 3.14) and a
test state the same minimum. The runner pins from D14 stay until `ubuntu-latest` has fully
moved to 26.04.

Detail: [design.md, "Dependencies, Python versions and CI"](design.md#dependencies-python-versions-and-ci).

## D16. Issue forms carry a "no real data" warning

Issues are public and users hold real key data, so all issues go through forms
(blank issues disabled) that open with the warning and end with a required "no real
data" checkbox. A test keeps both.

Detail: [design.md, "Keeping key data out of the repository"](design.md#keeping-key-data-out-of-the-repository).

## D17. Dependabot for GitHub Actions only

CI's third-party actions get deprecated runtimes, so Dependabot opens one grouped
pull request a week. There is no pip entry, since there are no runtime dependencies
to update. Merge its pull requests only when CI is green.

Detail: [design.md, "Dependencies, Python versions and CI"](design.md#dependencies-python-versions-and-ci).

## D18. Security reports go through GitHub private vulnerability reporting

`SECURITY.md` points reporters at GitHub's private flow so no personal address is
published, and separates vulnerabilities (private) from wrong results (public issues
with made-up data) and from the rule never to post real key data. No response-time
promise; only the latest `main` is supported.

Detail: [design.md, "Keeping key data out of the repository"](design.md#keeping-key-data-out-of-the-repository).

## D19. Contribution rules

`CONTRIBUTING.md` makes the privacy rule the one hard rule and restates the working
agreements from CLAUDE.md for outside contributors, who keep their own identity,
contribute under MIT and disclose AI assistance. The setup commands are duplicated
from the README, and a test keeps them in step.

Detail: [design.md, "Contributing"](design.md#contributing).

## D20. Pull request template

The template repeats the "never include real key data" warning, starts its checklist
with a "no real data" box and prompts for behavior changes and AI assistance, which
the maintainer wants to see explicitly.

Detail: [design.md, "Keeping key data out of the repository"](design.md#keeping-key-data-out-of-the-repository).

## D21. Pin count is a parameter, not a module global

Status: Superseded by D26.

`model.PINS` was removed (D26 later bundled the parameters into `KeySpace`). Functions that could not read the count from their
arguments took a `pins` argument, `Config.pins` carried it, and `DEFAULT_PINS` (7) was
the default, so tests pass `pins` instead of patching a global. No behavior change.

Detail: [design.md, "The key space"](design.md#the-key-space).

## D22. Pin count: `pins`, else the pattern's length, else 7

A system file may set `pins`; otherwise the count is the pattern's length, otherwise
7, so every existing file means what it did. It is never inferred from the bittings.
`min_diff` defaults to `min(5, pins)` and may not exceed `pins`. Cut depths stay 0 to
9 and parity, `max_step` and `min_diff` stay the only keyway rules.

Detail: [design.md, "The key space"](design.md#the-key-space).

## D23. One source of truth for the version

The version is `sfic_solver.__version__`; `pyproject.toml` reads it from there, a
test checks that no second copy exists, and release tags must match it.

Detail: [design.md, "Dependencies, Python versions and CI"](design.md#dependencies-python-versions-and-ci).

## D24. Narrative design documents for features, beside the log

Status: Amended by D41.

The log suits decisions that fit in a paragraph, but a feature that changes what the
tools model needs room for the problem, the model, the alternatives, the plan and the
open questions. So such a feature gets an essay in `docs/designs/` with a status
line, agreed before any code, and one short entry in the log. Splitting the log into
one file per decision was rejected because it reads worse as a story and breaks every
reference. Its original statement that existing entries are never rewritten is replaced by D41.

Detail: [design.md, "How the documentation fits together"](design.md#how-the-documentation-fits-together).

## D25. Core pinning gets a feature design document

The tools will grow from "which keys operate which cores" to "which pins make the
cores behave that way", for SFIC A2 first. The model: one control key per core, master
and change keys indistinguishable, one pin per gap, a simulated lock as test oracle,
pinning systems as data, MACS a system parameter, opt-in per system file. The real
constraint on bittings is weaker than parity; retired keys are evidence about undecoded
unit keys. Pinnability as a solver rule and the new residual-risk population are held
for agreement before they are built. Steps 1 to 3 are built (D26 to D31).

Detail: [designs/core-pinning.md](designs/core-pinning.md),
[design.md, "Pinning"](design.md#pinning).

## D26. The key-space rules are one object

Step 1 of core pinning. `model.KeySpace`, a frozen dataclass of `pins`, `pattern`,
`max_step` and `depths`, replaces the loose arguments, with the functions that need
them as methods and `Config.space` carrying it. It validates itself, so
`check_bittings --max-step 0` is now a usage error. No behavior change for any valid
file, shown by comparing every tool's output before and after.

Detail: [design.md, "The key space"](design.md#the-key-space).

## D27. Pinning systems are records in a registry

Step 2. A `PinningSystem` is a frozen record of increment, depth count, stack total,
pin ranges and control offset in `pinning.SYSTEMS`, with A2 the only entry (A3 and A4
lack pin ranges in the source). It refuses nonsense when defined, and the pinner
reads its numbers, so nothing is hard-coded to A2.

Detail: [design.md, "Pinning"](design.md#pinning).

## D28. The pinner: one pin per gap, and refusals that name the chamber

`pinning.pin_core` takes a pinning system, every operating key's bitting and the
control bitting, and returns one `Chamber` per position. A chamber that cannot be built
raises `PinningError` naming the chamber and the reason, and bad input is a
`ValueError`. Pin sizes are checked against each family's range, not reduced to the gap
rule.

Detail: [design.md, "Pinning"](design.md#pinning).

## D29. The simulated lock checks the pins from pins alone

`lock.Lock` is a pin stack per chamber and knows no keys. Review showed it is less
independent of the pinner than it first read, since the lift cancels in the
arithmetic. It still checks the pinner's construction and the key-level counting from
the pins alone, and hand-worked absolute heights catch a sign slip.

Detail: [design.md, "Pinning"](design.md#pinning).

## D30. The data-file guard also covers .txt

Status: Amended by D32.

Pinning charts are key data and the tools print them as text, so `.txt` is refused
anywhere but `tests/fixtures/`, where it must begin with a line starting `FAKE`. The
blanket rule is broader than charts, but the repository has never held a `.txt`.

Detail: [design.md, "Keeping key data out of the repository"](design.md#keeping-key-data-out-of-the-repository).

## D31. The conformance command reads charts and reports positions only

Step 3. `check_charts` reads charts in the tools' layout or the legacy one, pins each
chart's keys with the system it names and reports each disagreement as one of four
kinds. Its report holds counts and positions only, with fixed messages that never quote
a chart, so it is safe to share. `--details` is for the owner alone.

Detail: [design.md, "Pinning"](design.md#pinning).

## D32. The data-file guard also covers scans and PDFs

A scan of a chart is the chart, so `.pdf` and the common image formats are refused
everywhere, fixtures included: a picture cannot carry a `FAKE` marker or be reviewed in
a diff, so tests draw images when they run and commit none. `.gitignore` patterns are
case-insensitive.

Detail: [design.md, "Keeping key data out of the repository"](design.md#keeping-key-data-out-of-the-repository).

## D33. How pull requests are merged, and how stacked ones work

The first four pull requests used three merge methods, and anything stacked on a
squashed or rebased branch needed rebasing. A merge commit is the default and the only
method for a pull request with another stacked on it; squash is for iterative pull
requests, rebase merge for focused ones with nothing built on them. Merge subjects carry
the title and number. Stacks are one level deep and the upper one is a draft.

Detail: [design.md, "Merging"](design.md#merging),
[design.md, "Stacked pull requests"](design.md#stacked-pull-requests).

## D34. Direct commits, or a pull request

The choice follows what the reviewer has already seen, not the change's size. Direct
commits are for wording or intent the maintainer has given and for small, low-risk
changes; pull requests are for new policy or design wording, for code that should pass
CI first, for files another session is editing, and on request. The session says which
route and why.

Detail: [design.md, "Direct commit or pull request"](design.md#direct-commit-or-pull-request).

## D35. The scan formats in the guard grow to cover more camera and web formats

Review of D32 found formats the list lacked: `.dng`, `.avif`, `.jp2` and `.gif`. They
are now refused by the guard, `.gitignore` and the documentation, and one test covers
every listed extension. The list is of formats a scan can arrive in, not of all image
formats.

Detail: [design.md, "Keeping key data out of the repository"](design.md#keeping-key-data-out-of-the-repository).

## D36. Tools that read scans of charts run locally

A scan is the chart, and anything sent to an outside service may be kept or indexed
even if later deleted, so no cloud recognition service, however accurate. Tesseract
runs as a local subprocess and hand transcription stays the fallback. The same rule
covers debugging: positions only, and nobody pastes or describes a scan.

Detail: [design.md, "Reading scanned charts"](design.md#reading-scanned-charts).

## D37. Session trailers and links are accepted

An earlier rule banned `Claude-Session:` trailers and session links. Cloud sessions add
them regardless and their harness outranks this repository, so the rule is dropped. What
remains is the care that keeps it cheap: nothing from a conversation is copied into a
commit or pull request, and sharing stays off for any session that discussed real key
data.

Detail: [design.md, "Keeping key data out of the repository"](design.md#keeping-key-data-out-of-the-repository).

## D38. Scanned charts get a feature design document

A local tool turns scans of paper charts into text for `check_charts`. It transcribes
and never repairs, fails closed into three output files, reports positions only, uses
Tesseract's readings as votes on shape groups, and only ever flags on the stack-total
check. It is an explicit, bounded exception to D2: an optional `scan` extra and an
optional Tesseract. Built through step 3 of the plan.

Detail: [designs/chart-scanning.md](designs/chart-scanning.md),
[design.md, "Reading scanned charts"](design.md#reading-scanned-charts).

## D39. How reviews close, and how a merge is checked

Each inline comment is labelled Should fix or Optional, the summary says whether
anything blocks, and the author gives every thread a disposition (fixed, tracked, or
declined with a reason). A pull request merges when no Should-fix thread is open and
every Optional one has a disposition; on "merge now", leftovers become an issue. A merge
is checked before (reviewed head, green CI, tested against current `main`, pinned with
`--match-head-commit`) and after.

Detail: [design.md, "How a review closes"](design.md#how-a-review-closes),
[design.md, "How a merge is checked"](design.md#how-a-merge-is-checked).

## D40. Reviews are done by a task the maintainer starts by hand

A central review session gives larger changes a second pair of eyes. Its procedure is
in `docs/reviewing.md`, it is started by hand and not on a timer, and it reviews only
the maintainer's own pull requests, with a verdict in the text. It never changes a pull
request and never merges.

Detail: [design.md, "The review task"](design.md#the-review-task).

## D41. The log is short and append-only; design.md describes the present

The log had grown to forty entries, some several paragraphs, and later entries had
begun to contradict earlier ones. The log is now a succinct, append-only record with
status lines, and the reasoning and the current rules are in `docs/design.md`, which is
edited in place. The existing entries were condensed once, under this decision; their
long forms are in the git history before it. Alternatives rejected: one file per decision
(D24) and keeping the long entries and fixing contradictions by hand.

Detail: [design.md, "How the documentation fits together"](design.md#how-the-documentation-fits-together).

## D42. The scanner is tested on drawn charts in two tiers

A tool that reads paper charts cannot be tested on real ones, so tests draw random
fake charts and read them with the real pipeline. The always-on tier reads three
charts per image condition and asserts that none is accepted wrong and that most are
accepted; the slow tier (`--runslow`, 1,000 charts per condition, hours) is what could
support a claim in the README, and has not yet been run. The design had planned tens of
charts per condition in CI, but a chart costs six to seven seconds, so three it is.

Detail: [design.md, "Reading scanned charts"](design.md#reading-scanned-charts),
[designs/chart-scanning.md](designs/chart-scanning.md).

## D43. The README claims no more for the scanner than the harness has shown

The README, CLAUDE.md, CONTRIBUTING.md and SECURITY.md keep saying "standard library
only", each with the scanner named as the one exception (D2, D38), and a test checks
they do. The README's section on scanning says what was run (fake charts, about 120
in the measured runs, nothing accepted wrong), that a first trial on real scans found
problems (issue #16), and that the 1,000-chart run has not been made, so it states no
error rate. The flag rate and the weaknesses are stated as limits, not hidden. When
the slow run is made, the README is updated with what it showed.

Detail: [design.md, "Reading scanned charts"](design.md#reading-scanned-charts),
[designs/chart-scanning.md, "What the harness showed"](designs/chart-scanning.md#what-the-harness-showed).

## D44. Work on the chart scanner is suspended

The scanner is built and documented (D38, D42, D43), but a first trial on real scans
showed it does not yet read printouts usefully (issue #16), and the effort to get it
there is more than the use justifies, since a chart can be typed in instead. It stays
in the repository as it is: the README says that work is suspended and what is known,
and welcomes issues and fixes. Nothing is removed, and the open problems stay
tracked (#10, #12, #16). If work resumes, the fixes in #16 come first.

Detail: [design.md, "Reading scanned charts"](design.md#reading-scanned-charts),
[designs/chart-scanning.md, "What cannot be known yet"](designs/chart-scanning.md#what-cannot-be-known-yet).

## D45. A legacy chart may have a Master Key line, a Change Keys line, or both

The reader first required both lines, because the layout was described from charts
that had both. A core with a single operating key has nothing above it, so older
software has no reason to print both lines, and a chart with only one is plausible.
The reader now needs at least one, and a chart with neither still fails as having no
operating keys. The scanner, whose work is suspended (D44), still expects all four
header lines and flags a chart without them for review.

Detail: [designs/core-pinning.md, "The chart layout"](designs/core-pinning.md#the-chart-layout).

## D46. CI runs the scanner's slow checks only when a change can affect them

Status: Amended by D47.

The scanner's tests need Tesseract and the `scan` extra and are the slowest in CI, but
work on the scanner is suspended (D44) and most changes cannot affect it. The `test`
matrix now installs only pytest and runs the whole suite, so the scanner's tests skip
there, as for a contributor. A `scanner` matrix, with Tesseract and the extra, runs
only if `scripts/ci_changes.py` finds a changed file that is the scanner or something
it uses. Pushes to `main`, tags and any doubt run it. A test keeps the file list in
step with the scanner's imports. This replaces a TODO item for a job without the extra.

Detail: [design.md, "Dependencies, Python versions and CI"](design.md#dependencies-python-versions-and-ci).

## D47. CI runs on pull requests, on `main` and tags, and by hand, not on every push

CI triggered on both `push` and `pull_request`, so every commit on a branch with a
pull request was tested twice. It now runs for pull requests (which also test the
merge with `main`, and work for forks), for pushes to `main` and `v*` tags, and on
demand. The cost: a branch with no pull request gets no CI until it is run by hand or a
pull request is opened. That is accepted, since such branches exist to be read, not
merged. Amends D46 only in that the scanner's comparison has no branch-push case.

Detail: [design.md, "Dependencies, Python versions and CI"](design.md#dependencies-python-versions-and-ci).

## D48. A new push to a pull request cancels its superseded CI run

Every push to a pull request started a full run while the previous one was still
going, though its result no longer mattered. CI now cancels it. Only pull request runs
share a concurrency group; runs on `main`, tags and by hand each get a unique one,
because GitHub drops an older queued run from a shared group even when cancelling is
off, which could leave a commit on `main` untested. A test checks both settings.

Detail: [design.md, "Dependencies, Python versions and CI"](design.md#dependencies-python-versions-and-ci).

## D49. One required CI check, a timeout on every job, and slowest tests in the log

With the scanner job skipped on most changes and the matrices changing over time, no
individual check is a stable thing to require. A last job, `CI passed`, always runs and
passes only if what should have run passed; branch protection requires it alone. Every
job gets `timeout-minutes` (the default is six hours), and the pytest steps pass
`--durations=10` to show the slowest tests. Tests run the summary script against each
combination of results and check that every job has a timeout.

Detail: [design.md, "Dependencies, Python versions and CI"](design.md#dependencies-python-versions-and-ci).

## D50. Sessions pick which tests to run by the same rule as CI

The scanner's tests are most of the suite's time, and a session rarely has Tesseract,
so running them all before every commit costs minutes and checks little. CLAUDE.md now
says: run the changed module's tests while working; before committing, ask
`scripts/ci_changes.py` and run the whole suite with only `.[test]`, adding the `scan`
extra only when it says `scanner=true`; never skip the core suite; say which was run.
The review procedure follows the same rule. CI remains the backstop for what a session
could not run.

Detail: [design.md, "Dependencies, Python versions and CI"](design.md#dependencies-python-versions-and-ci).

## D51. Pinning is switched on by a `pinning` field, and each core names its control key

A system file opts in to pinning with `pinning` (a system name such as `"A2"`);
without it nothing changes. With it, every core needs a `control` naming one of
`control_keys`, since the control is half of the pinning, and an optional `name`
labels the system. `retired_cores` has the shape of `cores`, with `masters` and
`control` taken from `retired_keys` and a wildcard allowed to match nothing yet.
A system whose cut depth count differs from the key space's is refused. The
alternative, one control key used by default when only one exists, was rejected so
that a second control key added later cannot silently re-pin cores.

Detail: [design.md, "System files"](design.md#system-files).

## D52. With pinning set, `check_system` lists every chamber that cannot be pinned

For an opted-in file the report gains a section: one `UNPINNABLE` line per core,
change key and failing chamber, with the reason, and a `CONTROL` line for any known
key that operates a core's control shear line. Both count as problems. Listing every
chamber, not the first, is what an owner needs to fix a core, so the pinner gained
`pin_chambers`. `CONTROL` is redundant with `DUPLICATE` for known keys, since only the
control bitting operates that line, but it says which cores are affected. Rejected:
leaving it out, because the design promised it and the line costs nothing.

Detail: [design.md, "Pinning"](design.md#pinning).

## D53. Retired-core failures are warnings, and the closing line counts them

The retired cores let the tools test the pinning rules against the old
installation: every decoded key in a retired core must be pinnable with the
retired masters and control. A failure means the description is wrong or the rules
are too strict, and the tools cannot tell which, so it is a `WARNING`, listed and
capped like the other sections, and it does not change the exit status. The closing
line says `OK, 1 warning(s)` or `3 problem(s) flagged, 1 warning(s)`. Rejected:
counting warnings as problems, which would fail a file for a fact the owner may
rightly dispute.

Detail: [design.md, "Pinning"](design.md#pinning).

## D54. Step 5 is designed before it is built, and the design is accepted

Step 5 of core pinning makes an unpinnable core a hard conflict in the solver, adds
an expected-unpinnable figure for undecoded unit keys beside the expected
cross-operation, takes the population of undecoded keys from the retired cores when
they cover units, and lets the generator run without a pattern. Without parity a
random master leaves most undecoded units unable to take it, so the figure is
needed, and a hill-climb under the closeness rule still leaves about a quarter. The
design is in its own document and has been accepted; the document states the scale
of the new term against the old, and the weight of one that makes it dominate has
been confirmed, since avoiding rekeyed unit cores is the primary goal. Files that
do not set `pinning` are unaffected.

Detail: [designs/pinnable-solving.md](designs/pinnable-solving.md).

## D55. The residual-risk estimate takes its population from the retired cores

Part 5a of step 5. With `pinning` set, undecoded unit keys are no longer assumed
uniform among valid bittings when a retired core covers unit keys: they are the
bittings that old core could have been pinned with, found with the pinner, and the
report says so. Each unit core gains a second figure, the undecoded unit keys
expected to be unable to take its master and control key, whose cores would need
rekeying. Populations are signed sums of per-position set products, counted
exactly, so up to three covering cores give an exact union; more fall back to the
uniform population with a printed line, not a refusal, and so does a description in
which no bitting could have been pinned, which is also reported as warnings. Files without `pinning` print
what they did, to the byte. The solver does not use it until 5b.

Detail: [design.md, "Pinning"](design.md#pinning).

## D56. With pinning set, the solver rejects unpinnable cores and scores the unpinnable figure

Part 5b of step 5, as agreed in the design. For a file that sets `pinning`, a core that
cannot be pinned with the keys assigned so far is a hard conflict, one penalty per
failing chamber, and the expected number of undecoded unit keys that cannot take the
unit master and control key is added to the expected-conflict term with weight one
(`UNPINNABLE_WEIGHT`), which makes avoiding rekeyed unit cores the primary goal. The
solver uses the checker's population and says when the retired cores were not used.
Files without `pinning` give byte-identical solver output, shown by seeded runs.

Detail: [design.md, "Pinning"](design.md#pinning).
