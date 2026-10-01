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
- Configurable pin count and keyway rules so the tools work for other buildings
  and systems.
