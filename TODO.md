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
- Core pinning (docs/designs/core-pinning.md): steps 1 and 2 are done (the
  key-space object and the pinning library). Next is step 3: the `.txt` guard and
  the local conformance script.
- Extend the data-file guard to chart formats, since a pinning chart is real key
  data (CLAUDE.md): `.txt` before the conformance script, `.pdf` before PDF
  output, each in its own commit (docs/designs/core-pinning.md).
- Core pinning output ideas (docs/designs/core-pinning.md, step 7): an ASCII
  drawing of each core's pin stacks inside the chart output, and optional PDF
  output of all the charts as one document.
