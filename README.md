# sfic-solver

Small, dependency-free Python tools for planning and checking a **master-keyed
SFIC** (small format interchangeable core) key system: generate candidate key
bittings, check a whole key hierarchy for unintended cross-operation, and fill
in missing bittings (such as a unit master) so as to minimise the risk of it.

> **This is a planning aid, not a substitute for your keying software or
> manufacturer.** It models only the rules described below. See
> [Limitations](#limitations).

Standard library only. Python 3.9 or newer.

## The tools

| Command (from a checkout) | Installed as | What it does |
| --- | --- | --- |
| `./gen_bittings.py` | `sfic-gen-bittings` | Random bittings from a parity pattern, optionally staying away from existing bittings. |
| `./check_bittings.py` | `sfic-check-bittings` | Quick check of a few `NAME=BITTING` values: format, parity, adjacent-cut limit, pairwise closeness. |
| `./check_system.py` | `sfic-check-system` | Whole-scheme check of a system file: per-key rules, duplicates, closeness, operating-set sizes, cross-operation, residual risk. |
| `./solve_system.py` | `sfic-solve-system` | Fills in the `null` bittings of a system file by random search plus hill climbing, then runs the full check. |

Run them straight from a checkout (`./check_system.py system.json`), as modules
(`python3 -m sfic_solver.check_system system.json`), or install the package
(`pip install .`) to get the `sfic-*` commands. Every tool exits with status 1
if it flagged anything (`solve_system` always exits 0 when it wrote a result;
read the check report that follows).

## The theory, in plain language

**Bitting.** A key's cuts, written as a 7-digit string: one cut depth (0-9) per
pin position. `5961634` means depth 5 at position 1, depth 9 at position 2, and
so on.

**Parity pattern** (for example `OOEOEOE`). Each position must be even (`E`) or
odd (`O`). If every key in the system follows the pattern, two keys' cuts at a
position always differ by an even number of depth steps, so a master pin never
has to be the smallest size to bridge a change key and its master.

**Maximum adjacent cut specification (MACS).** Adjacent cuts may differ by at
most `max_step` (default 5), a physical limit on how steep a key can be cut.

**Cores and master keying.** A core is pinned with a *change key* plus zero or
more *masters* above it. At every position the core accepts the change key's
cut or any master's cut, so it is **operated by every key whose cut at every
position is one of those cuts**, as long as the key is cuttable (parity, MACS).
That set always contains the change key and the masters (the *intended* keys),
but usually many more: any mix-and-match of their cuts. Those extra keys are
**false keys**. Their number is computed exactly (dynamic programming over
positions, trimming combinations that break MACS), not estimated.

**Cross-operation.** A known key that operates a core it was not meant to
operate. This is the problem the checker exists to find. A common trap is a key
that happens to be made of one key's cuts and a master's cuts.

**Unit keys.** Unit door cores are usually many cores sharing one master. A
unit key is named `unit:<number>`; one `change` entry such as `"unit:*"`
expands to a core per unit key. Unit-to-unit *closeness* is not checked by
default (unit keys are meant to be unrelated to each other; what matters is
whether they operate each other's cores).

**Control keys** use a separate control pinning. The tools only check them for
closeness and duplicates, never for operation.

**Closeness.** Two keys that differ in fewer than `min_diff` positions are
flagged; very similar bittings are easy to confuse or to cut by mistake.

**Residual risk.** Some unit keys are usually not decoded yet, so the tools can
only estimate the chance that they cross-operate. The estimate assumes every
undecoded unit key is a random valid bitting, uniformly chosen. If your real
keys were chosen differently, the numbers do not apply.

## System file format

A JSON file. Fields (only `keys` and `cores` are needed for the basics):

| Field | Meaning |
| --- | --- |
| `pattern` | 7 characters of `E`/`O`. Enables parity checks and restricts the key space. If omitted, any cut 0-9 is allowed at every position. |
| `max_step` | Max difference between adjacent cuts. Default `5`. |
| `min_diff` | Flag non-unit key pairs differing in fewer positions. Default `5`. |
| `unit_prefix` | Name prefix of unit keys. Default `"unit:"`. |
| `unit_count` | Total number of units; enables the residual-risk estimate and lets the solver weigh it. |
| `close_check_units` | `true` to also run the closeness check on unit keys. Default `false`. |
| `keys` | `{name: bitting}` of operating keys, including decoded unit keys. |
| `retired_keys` | `{name: bitting}` of old keys that must **not** operate any new core. |
| `control_keys` | `{name: bitting}` of control keys. |
| `cores` | List of `{"name", "change", "masters"}`. `change` is a key name, a wildcard such as `"unit:*"`, or a list of those. `masters` is a list of key names pinned above the change key (may be empty). |

Names must be unique across `keys`, `retired_keys` and `control_keys`. Only
entries in `keys` can be change keys or masters. Top-level and core fields
starting with `_` (such as `_comment`) are free text and ignored; any other
unrecognised field produces a warning, since it is usually a typo. In a file
given to `solve_system`, a `null` bitting in `keys` or `control_keys` means
"choose this for me".

### Worked example

This is `system.example.json` (random placeholder bittings, generic names):

```json
{
  "pattern": "OOEOEOE",
  "max_step": 5,
  "min_diff": 5,
  "unit_prefix": "unit:",
  "unit_count": 100,
  "keys": {
    "master_top": "5961634",
    "master_sub": "7305496",
    "area_a": "5721276",
    "area_b": "9565698",
    "area_c": "3323872",
    "area_d": "1161012",
    "unit_master": "7587672",
    "unit:101": "3101658",
    "unit:102": "5549878",
    "unit:103": "7741438"
  },
  "retired_keys": {
    "old_master": "1327238"
  },
  "control_keys": {
    "control_a": "9743854",
    "control_b": "3785412"
  },
  "cores": [
    {"name": "Area A cores",     "change": "area_a",     "masters": ["master_sub", "master_top"]},
    {"name": "Area B cores",     "change": "area_b",     "masters": ["master_sub", "master_top"]},
    {"name": "Area C cores",     "change": "area_c",     "masters": ["master_top"]},
    {"name": "Sub-master cores", "change": "master_sub", "masters": ["master_top"]},
    {"name": "Standalone cores", "change": "area_d",     "masters": []},
    {"name": "Unit cores",       "change": "unit:*",     "masters": ["unit_master"]}
  ]
}
```

Reading the `cores` list: the "Area A cores" are pinned `area_a` + `master_sub`
+ `master_top`, so those three keys operate them, plus any false keys. The
sub-master cores are operated by `master_sub` and `master_top`, and so on: a
master operates every core where it appears as a master. `"unit:*"` creates one
core per `unit:` key (three here), each with `unit_master` above it. Only 3 of
the 100 units are decoded, so the report also estimates the risk from the other
97.

Checking it (output abridged):

```console
$ ./check_system.py system.example.json
...
== Core operating sets (valid bittings in the whole key space: 28,384) ==
Area A cores: 1 core(s), change + master_sub + master_top
    384 operating bittings, of which 3 intended (1.34% of all valid bittings are false keys)
...
== Cross-operation among known keys ==
none

== Residual risk from undecoded unit keys (3 of 100 decoded) ==
Estimate only: assumes unknown unit keys are random valid bittings.
Area A cores: 1.30 unit keys expected to operate it (73% chance at least one does)
...
Unit cores: about 14.8 unit-to-unit cross-operations expected by chance; re-check after decoding

OK
```

`CROSS     key unit:104 operates Unit cores [unit:101]` would mean the key
`unit:104` operates the core of `unit:101`, which it must not.

## Typical workflow

1. **Generate keys.** Draw bittings for the non-unit keys, keeping each at
   least a few positions from the others and from anything that already exists:

   ```bash
   ./gen_bittings.py OOEOEOE -n 8 --min-diff 5
   ./gen_bittings.py OOEOEOE -n 3 --avoid 5961634 7305496 --min-diff 5
   ```

   Output is in generation order (not sorted), so taking the first one is as
   random as any other. Spot-check candidates with
   `./check_bittings.py --pattern OOEOEOE name=1234567 other=7654321`.

2. **Write the system file.** List keys, retired keys and the `cores` hierarchy.
   Leave the unit master as `null` until you are ready to solve for it.
   **Keep this file outside this repository** (see [Privacy](#privacy)).

3. **Decode unit keys.** As unit keys are measured, add each to `keys` as
   `"unit:<number>": "<bitting>"` and set `unit_count` to the total number of
   units.

4. **Solve the unit master** (and any other `null` keys) against the unit keys
   decoded so far:

   ```bash
   ./solve_system.py system.json            # writes system.solved.json
   ./solve_system.py system.json --out chosen.json --trials 5000
   ```

   Known keys are never changed. Candidates are scored exactly: a known key
   operating a core it should not, or a duplicate, is a hard rule; then
   closeness among non-unit keys; then the expected number of chance
   cross-operations involving unit keys not yet decoded. By default it uses
   the operating system's randomness (`--seed` exists only for reproducible
   tests, never use it for real keys). Review the result; it is a suggestion.

5. **Check after every decode batch.**

   ```bash
   ./check_system.py system.solved.json
   ```

   Newly decoded unit keys can cross-operate. Any `CROSS` line needs action
   before keys are cut. The residual-risk section shrinks as more units are
   decoded.

## Limitations

- It models **only** the rules above: a fixed 7 pins, one parity pattern, a
  single adjacent-cut limit, and "a core accepts the change key's or a master's
  cut at each position". Nothing else.
- **Real manufacturer MACS, parity and progression rules still apply**, and so
  do the keying software's own checks (pinning limits, master-ring and control
  rules, available pin sizes, and so on). Use the keying software's output as
  the authority.
- It is a **planning aid**, not a substitute for the keying software or an
  experienced locksmith.
- Parity and MACS are checked for `keys` and `control_keys` (a control key that
  broke parity could need a pin size that does not exist), but not for
  `retired_keys`. Closeness and duplicates cover all sections. Control keys are
  never tested for operation.
- Closeness counts differing positions only. It does not model the physical
  similarity of cuts.
- **Residual-risk numbers assume undecoded unit keys are random valid
  bittings.** They are estimates for planning, and say nothing about keys that
  were chosen differently.
- Searches are heuristic. The solver is not guaranteed to find the best
  possible bitting, or any solution when fixed keys already conflict.

## Privacy

A real system file contains real bittings. **Never commit one.** `.gitignore`
ignores every `*.json` and `*.csv` (system files and exports of your key matrix)
except `system.example.json` and the fake fixtures under `tests/fixtures/`, and
two guards enforce it:

- a pre-commit hook (`git config core.hooksPath .githooks`) that rejects any
  other staged `.json` or `.csv`;
- a CI job that fails if any other `.json` or `.csv` is tracked or appears
  anywhere in the history.

Keep real files in a directory outside the repository.

## Development

```bash
pip install -e ".[test]"        # pytest is the only extra dependency
git config core.hooksPath .githooks
pytest
```

The tests compare the counting maths against brute-force enumeration, check
the generator's constraints, plant cross-operations and confirm the checker
flags them, and confirm the solver leaves known keys untouched and produces a
system that passes the checker. Test fixtures use obviously fake bittings.

See [TODO.md](TODO.md) for open items.
