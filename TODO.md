# TODO

## Ideas for later

- A mode that screens candidate unit masters against decoded unit keys.
- `--avoid-file` for the generator.
- Generate the `cores` list from an exported CSV of the key matrix.
- After 2026-11-19 (`ubuntu-latest` fully on Ubuntu 26.04), replace the pinned
  runner images in CI with `ubuntu-latest` (see D14/D15 in docs/design.md).
- Configurable keyway rules (cut depth range, an explicit allowed-cut set per
  pin) so the tools work for other systems. The pin count is already
  configurable (D22 in docs/design.md); the rest is covered by the pinning
  system records in docs/designs/core-pinning.md.
- Core pinning (docs/designs/core-pinning.md): steps 1 to 3 are done (the
  key-space object, the pinning library, the `.txt` guard and the conformance
  script). Next is step 4: config and checker, once the conformance script has
  been run against real charts.
- Core pinning output ideas (docs/designs/core-pinning.md, step 7): an ASCII
  drawing of each core's pin stacks inside the chart output, and optional PDF
  output of all the charts as one document.
- A script for the pull request privacy scan that reviewers now run by hand: seven
  digit strings that are not in `system.example.json`, a short list of key-history
  phrases, commit identity and trailers, and the data-file guard over the whole
  history. It is code, so it needs a short design first (D24).
- Scanning paper charts (docs/designs/chart-scanning.md, accepted; D38): the tool is
  built (step 3). Still to do: step 4, the synthetic-image harness with the quality
  matrix and the 1,000-chart criterion, including the macOS system fonts (issue #10:
  commas are not found in thin fonts such as Courier New); and step 5, the README
  ("scanning paper charts", the command in the tools table, and the "dependency-free"
  wording with the one stated exception), CLAUDE.md's "standard library only"
  likewise, and the log. Step 5 has to land before a release mentions the tool.
