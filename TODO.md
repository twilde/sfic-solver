# TODO

## Before making the repo public

- [ ] Re-run the history sweep right before going public: the data-file guard
      (`scripts/check_no_stray_data.py --history`), a search of all history for
      identifying names and any real bittings, and a look at commit messages.
      Last full sweep: 2026-10-01, clean.

## Ideas for later

- A mode that screens candidate unit masters against decoded unit keys.
- `--avoid-file` for the generator.
- Generate the `cores` list from an exported CSV of the key matrix.
- After 2026-11-19 (`ubuntu-latest` fully on Ubuntu 26.04), replace the pinned
  runner images in CI with `ubuntu-latest` (see D14/D15 in docs/design.md).
- Configurable keyway rules (cut depth range, an explicit allowed-cut set per
  pin) so the tools work for other systems. The pin count is already
  configurable (D22 in docs/design.md).
