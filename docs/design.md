# Design notes

A running log of decisions, newest last. Each entry says what was decided and
why, so later changes can tell what is deliberate. Add an entry in the same
commit as the decision.

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

## D3. Pin count is one patchable module constant

`model.PINS` (7) is read at call time by every function that depends on it. The
tests patch it to 3 or 4 to compare the dynamic-programming results against
brute-force enumeration. Other modules must refer to `model.PINS`, never copy it
with `from .model import PINS`. Configurable pin count for users is a TODO.

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
