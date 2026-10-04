# sfic-solver

Small Python tools for planning and checking a **master-keyed
SFIC** (small format interchangeable core) key system: generate candidate key
bittings, check a whole key hierarchy for unintended cross-operation, and fill
in missing bittings (such as a unit master) so as to minimise the risk of it.

> **This is a planning aid, not a substitute for your keying software or
> manufacturer.** It models only the rules described below. See
> [Limitations](#limitations).

Standard library only, with one stated exception: the optional command that reads
scans of paper charts needs extra packages and Tesseract (see
[Scanning paper charts](#scanning-paper-charts)). Everything else runs without
them. Python 3.11 or newer.

## The tools

| Command (from a checkout) | Installed as | What it does |
| --- | --- | --- |
| `./gen_bittings.py` | `sfic-gen-bittings` | Random bittings from a parity pattern, optionally staying away from existing bittings. |
| `./check_bittings.py` | `sfic-check-bittings` | Quick check of a few `NAME=BITTING` values: format, parity, adjacent-cut limit, pairwise closeness. |
| `./check_system.py` | `sfic-check-system` | Whole-scheme check of a system file: per-key rules, duplicates, closeness, operating-set sizes, cross-operation, residual risk. |
| `./solve_system.py` | `sfic-solve-system` | Fills in the `null` bittings of a system file by random search plus hill climbing, then runs the full check. |
| `./check_charts.py` | `sfic-check-charts` | Checks that the tools' pinning rules reproduce pinning charts from your keying software (`.txt` files kept outside this repository). Reports positions only, never key data. |
| `./scan_charts.py` | `sfic-scan-charts` | Reads scans (PDF or image) of paper pinning charts and writes them as the text charts `check_charts` reads. Needs the optional `scan` extra and Tesseract; see [Scanning paper charts](#scanning-paper-charts). |

The pin count is 7 unless the system file says otherwise (`pins`, or the length
of `pattern`); `gen_bittings.py` takes it from the pattern's length and
`check_bittings.py` from `--pins` or `--pattern`.

Run them straight from a checkout (`./check_system.py system.json`), as modules
(`python3 -m sfic_solver.check_system system.json`), or install the package
(`pip install .`) to get the `sfic-*` commands. Every tool exits with status 1
if it flagged anything (`solve_system` always exits 0 when it wrote a result;
read the check report that follows).

## The theory, in plain language

**Bitting.** A key's cuts, written as a string of digits: one cut depth (0-9)
per pin position, 7 positions for a standard SFIC core. `5961634` means depth 5
at position 1, depth 9 at position 2, and so on. The number of pins is
configurable (see `pins` below).

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

The names *change key* and *master* describe how a hierarchy is used, not how a
core works. For any one core they are interchangeable: each is simply a key the
core is pinned to accept, and the core's behavior depends only on those keys'
cuts, never on which one is called the master. Two keys pinned into the same core
are on an equal footing, and either may have the higher cut, the lower, or the
same.

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
| `pins` | Number of pins, so the length of every bitting. Default: the length of `pattern` if there is one, otherwise `7`. If both are given they must agree. |
| `pattern` | One `E`/`O` per pin (7 by default). Enables parity checks and restricts the key space. If omitted, any cut 0-9 is allowed at every position. |
| `max_step` | Max difference between adjacent cuts. Default `5`. |
| `min_diff` | Flag non-unit key pairs differing in fewer positions. Default `5`, or `pins` if that is smaller. Cannot be more than `pins`. |
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

Reading the `cores` list: the "Area A cores" are pinned with `area_a`, then
`master_sub`, then `master_top`, so those three keys operate them, plus any
false keys. The sub-master cores are operated by `master_sub` and `master_top`,
and so on: a master operates every core where it appears as a master.
`"unit:*"` creates one core per `unit:` key (three here), each with
`unit_master` above it. Only 3 of the 100 units are decoded, so the report also
estimates the risk from the other 97.

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

## Scanning paper charts

If your pinning charts exist only on paper, `sfic-scan-charts` turns scans of
them into the text charts `check_charts` reads, so that you do not have to retype
them. It is the one part of this project that is not standard-library only: it
needs the optional Python packages (Pillow, numpy and pypdfium2) and the Tesseract
program, and nothing else needs either.

```bash
pip install -e ".[scan]"        # the optional packages
brew install tesseract          # macOS; on Debian or Ubuntu: apt install tesseract-ocr

./scan_charts.py scans.pdf                  # or several files, or a directory of them
./check_charts.py scans.txt                 # then run the conformance check yourself
```

If Tesseract is not on the path, name it with `--tesseract PROGRAM` or the
`SFIC_TESSERACT` environment variable.

It reads PDFs and `.png`, `.jpg`, `.tif` and similar scans (see `--help`; phone
formats such as HEIC and photographs are not supported). Give it scans made by a
scanner at 200 to 300 dpi, of files you made yourself, since a PDF is parsed by
a native library. It runs only on your computer: nothing leaves it, it writes
no images and no temporary files, and the three output files are created readable
by you alone. The report names positions only (input, page, chart, row, chamber),
never a digit or a file name. It does not run `check_charts` for you, so that "what
the paper says" and "whether the pinning rules agree" stay two separate steps.

It writes up to three files next to the input, and never over an existing one
without `--force`:

| File | What is in it | What `check_charts` does with it |
| --- | --- | --- |
| `NAME.txt` | Charts that passed every check. | Reads it. |
| `NAME.failed.txt` | Charts read completely that failed a check inside the chart (a column that does not add up). | Reads it, so you can compare it with the paper. |
| `NAME.review.txt` | Charts it could not read completely, with `??` where. | Refuses it, on purpose. Finish it by hand, looking at the page the report names. |

The tool transcribes and never repairs: it does not use the pinning rules to
choose a reading, and its checks (cell ranges, master rows filling from the
bottom, each chamber adding up to the stack total) can only flag a chart. It
exits 0 if every chart was accepted, 1 if anything needs attention and 2 if it
could not run (a missing package or Tesseract, bad input, an output file in the
way).

What is and is not known about how well it reads:

- It has been tested mostly on charts drawn by the tests from fake bittings. A first
  trial on real scans found three problems that those charts did not show
  ([issue #16](https://github.com/twilde/sfic-solver/issues/16)), so do not expect
  it to read a real printout yet, and nothing is claimed beyond that. The figures
  that follow are about drawn charts: in test runs of about 120 of them under blur,
  noise, skew and low resolution, and in tests that erase or ink over cells, no
  chart was ever accepted wrong. The full 1,000-chart run that would bound the rate
  has not been made.
- Expect some charts to go to the review file even when the scan is good: one of
  the 12 clean charts in those runs was, and 8 of the 120 across all the
  conditions, which is a sample and not a rate
  ([issue #12](https://github.com/twilde/sfic-solver/issues/12)). That costs a look
  at the paper and is the intended direction.
- Fonts with thin commas, such as Courier New and Menlo (a Mac's defaults), can
  hide the commas in the `Change Keys` line, so many charts from such printouts
  will be flagged ([issue #10](https://github.com/twilde/sfic-solver/issues/10)).
- Handwriting in the left margin, or after a row, is ignored or sent to review.
  Handwriting beside the printed block that overlaps its rows is not handled yet and
  can make the whole page unreadable
  ([issue #16](https://github.com/twilde/sfic-solver/issues/16)).
- It takes about six seconds a chart on four cores.

Try it on a single page first. If the report says every chart on it was flagged
for the same reason, that is something you can quote in an issue without a single
digit; never paste or describe the page itself.

## Limitations

- It models **only** the rules above: one pin count for the whole system, cut
  depths 0-9, one parity pattern, a single adjacent-cut limit, and "a core
  accepts the change key's or a master's cut at each position". Nothing else.
- Pin counts other than 7 are not tied to any real keyway: the tools do not
  know which pin counts or cut depths a manufacturer actually offers, and the
  chance of unintended cross-operation grows quickly as pins are removed.
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
ignores every `*.json`, `*.csv` and `*.txt` (system files, exports of your key
matrix and pinning charts) except `system.example.json` and the fake fixtures
under `tests/fixtures/`. It also ignores every PDF and image (`.pdf`, `.png`,
`.jpg`, `.jpeg`, `.tif`, `.tiff`, `.heic`, `.heif`, `.dng`, `.avif`, `.jp2`,
`.gif`, `.bmp`, `.webp`), with no exception, since scans and photos of charts
are key data and a picture cannot be marked as fake. Two guards enforce it:

- a pre-commit hook (`git config core.hooksPath .githooks`) that rejects any
  other staged `.json`, `.csv` or `.txt`, and any staged PDF or image;
- a CI job that fails if any such file is tracked or appears anywhere in the
  history.

Keep real files in a directory outside the repository. A pinning chart counts as
real key data in any format (text, scan, photo or PDF), because the pin sizes
give the bittings away.

Issues and pull requests are public too: never paste real bittings, real system
files, or anything that identifies a real building. Reproduce problems with
`system.example.json` or made-up values (the issue forms say the same).

## Development

```bash
pip install -e ".[test]"        # pytest is the only extra dependency
git config core.hooksPath .githooks
pytest
```

The tests of the chart scanner need Tesseract and a monospaced font with clear
commas, and are skipped without them; see "Scanning tests" in
[CONTRIBUTING.md](CONTRIBUTING.md#scanning-tests-optional).

The tests compare the counting maths against brute-force enumeration, check
the generator's constraints, plant cross-operations and confirm the checker
flags them, and confirm the solver leaves known keys untouched and produces a
system that passes the checker. Test fixtures use obviously fake bittings.

To contribute, see [CONTRIBUTING.md](CONTRIBUTING.md). Open items are in
[TODO.md](TODO.md). Why things are built the way they are is in
[docs/design.md](docs/design.md); the decisions behind it are listed in the log,
[docs/decisions.md](docs/decisions.md), and the larger features have design
documents in [docs/designs/](docs/designs/). To report a security problem, see
[SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE).
