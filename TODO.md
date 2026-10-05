# TODO

## Ideas for later

- A mode that screens candidate unit masters against decoded unit keys.
- `--avoid-file` for the generator.
- Generate the `cores` list from an exported CSV of the key matrix.
- After 2026-11-19 (`ubuntu-latest` fully on Ubuntu 26.04), replace the pinned
  runner images in CI with `ubuntu-latest` (see D14/D15 in docs/decisions.md).
- Configurable keyway rules (cut depth range, an explicit allowed-cut set per
  pin) so the tools work for other systems. The pin count is already
  configurable (D22 in docs/decisions.md); the rest is covered by the pinning
  system records in docs/designs/core-pinning.md.
- Core pinning (docs/designs/core-pinning.md): steps 1 to 4 are done (the
  key-space object, the pinning library, the `.txt` guard and the conformance
  script, and the config and checker for files that set `pinning`). Step 5 changes
  the solver's scoring and the residual-risk population, and is designed and
  accepted in docs/designs/pinnable-solving.md: part 5a (the population and the
  expected-unpinnable figure) is done, then 5b (the solver and the generator).
  Step 6 is the chart command.
- Core pinning output ideas (docs/designs/core-pinning.md, step 7): an ASCII
  drawing of each core's pin stacks inside the chart output, and optional PDF
  output of all the charts as one document.
- A script for the pull request privacy scan that reviewers now run by hand: seven
  digit strings that are not in `system.example.json`, a short list of key-history
  phrases, commit identity and trailers, and the data-file guard over the whole
  history. It is code, so it needs a short design first (D24).
- Scanning paper charts (docs/designs/chart-scanning.md, accepted; D38; work
  suspended, D44): the tool, its harness and its documentation are built (steps 3 to
  5), and nothing here is being worked on now. If it is picked up again, in this
  order: the three failures on real scans (issue #16), then the dissent check that
  flags some clean charts (issue #12) and the thin macOS fonts (issue #10); then run
  the slow tier to completion (`pytest --runslow tests/test_scan_harness.py -s`,
  about two hours a condition) to see whether anything is accepted wrong, and say in
  the README what it showed.
