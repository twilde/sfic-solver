## What and why

<!-- What does this change do, and why? Link the issue if there is one. -->

## Never include real key data

Pull requests are public. **Do not include real bittings, real system files, or
anything that identifies a building, its residents or its keys**, in code, tests,
examples, comments, the description or commit messages. Use `system.example.json`
or invented values.

## Checklist

- [ ] I have not included real bittings, real system files, or anything that identifies a real building.
- [ ] One logical change (refactors are in their own commits).
- [ ] Tests added or updated, and `pytest` passes. A bug fix has a regression test.
- [ ] README and the decision log in `docs/design.md` updated if behavior or a design decision changed (and the feature's document in `docs/designs/`, if it has one).
- [ ] No new runtime dependencies; randomness defaults (`secrets`, `random.SystemRandom`) unchanged.

## Behavior changes and AI assistance

<!-- Does this change what any command outputs, or the solver's scoring or algorithms? Please explain. -->

<!-- If an AI tool helped, say so here and with a Co-Authored-By trailer in the commit. -->
