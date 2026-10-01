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

## D2. Standard library only, Python 3.9+

No runtime dependencies. pytest is the only (optional, test) dependency. CI runs
3.9-3.13; there is no 3.9 interpreter locally, so avoid newer syntax (no
`X | Y` types, no `match`, no nested same-quote f-strings).

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
`scripts/check_no_stray_json.py` runs as a pre-commit hook (staged files) and in
CI (tracked files and all history). Fixtures must carry a `_comment` starting
with `FAKE` (a test enforces it). Tests that need other configs build them in a
temporary directory.
