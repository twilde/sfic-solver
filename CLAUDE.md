# CLAUDE.md

Guidance for AI assistants (and humans) working in this repo. Read README.md
for what the tools do, docs/design.md for the decision log, and docs/designs/
for the larger feature designs that explain why the tools are built the way they
are.

## Project

Small, dependency-free Python tools (3.11+, standard library only) that plan and
check a master-keyed SFIC key system. Code lives in `sfic_solver/`; the root
`*.py` scripts are thin entry points that must keep working as command lines.

```bash
pip install -e ".[test]"        # pytest is the only extra dependency
git config core.hooksPath .githooks
pytest
```

## Privacy (hard rules)

Treat everything committed as if strangers will read it. The repo is public.

- Never commit, and never ask the user to paste, real key data: real bittings,
  decoded unit keys, or anything identifying the building, residents, trustees
  or vendors. This applies to files, tests, docs, examples and commit messages.
- Real system files live outside this repo. Do not go looking for them. If you
  find any `.json` or `.csv` other than `system.example.json` and files under
  `tests/fixtures/`, stop and ask before reading it.
- Example and fixture data must be random or obviously fake, with generic names.
- `.gitignore`, the pre-commit hook and CI all enforce the data-file rule.
  Never bypass them (`--no-verify`, `git add -f`).

## Commands that produce real keys

Keep the `secrets` / `random.SystemRandom` defaults. `--seed` is for tests only.
Do not change scoring weights, algorithms or output semantics without asking
first and explaining why.

## How we work

- **Small, isolated commits.** One logical change per commit. (The very first
  commit was the baseline and is the exception.)
- **Always test.** Strict TDD is optional, but every bug gets a regression test
  and every behavior change gets tests. Run the full suite before committing.
- **Refactor freely, separately.** We do periodic refactor passes, and you
  should suggest or make refactors when you see duplication. If a refactor is
  significant, make it its own commit, separate from the deeper work built on
  top of it, so each is easy to read.
- **Ask questions.** If you are not sure what the user wants, ask.
- **Write design decisions down.** A small decision goes in the log,
  `docs/design.md`, in the same commit as the decision. A larger feature (one
  that changes what the tools model, will take several commits, or has open
  questions) gets a narrative design document in `docs/designs/` first, written
  as an essay (problem, model, alternatives, decision, plan, open questions) and
  agreed with the user before any code, plus a short log entry pointing to it.
  See D24.
- **Commit and push when a piece of work is complete.** The user reviews on
  GitHub, not in the Claude interface, so push finished work. Do not push
  half-done work.
- **Commit identity and attribution.** Commit as the user, using their GitHub
  noreply address (set in this repo's local git config), never a personal
  email: commit emails are public and permanent. Always end commit messages with a `Co-Authored-By: <Claude model>
  <noreply@anthropic.com>` trailer, so AI involvement is transparent. Do the
  same for pull request descriptions as instructed by the session.
- **Dependabot** opens a weekly pull request for GitHub Actions updates. Merge
  it only when CI is green.
- **Keep docs current.** README limitations, file-format notes and TODO.md
  change in the same commit as the behavior they describe.
