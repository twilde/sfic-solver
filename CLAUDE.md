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
- Pinning charts are real key data too: the pin sizes in each chamber give the
  bittings away. They follow every rule above, in any format, including a chart
  re-typed or "anonymised" from a real one. Tests may only use charts that are
  computed from fake bittings.
- Facts about the real building's key history are covered too, even with no
  names or bittings in them: whether it was rekeyed, what the old system looked
  like, which records exist or are missing, what charts or software the
  maintainer holds. Write design reasoning as general scenarios ("a building
  rekeyed without original records"), never as facts about this one. This applies
  to commit messages and pull request text as well as files.
- Scans, photos and PDFs of charts, and any OCR text made from them, are real key
  data too. Never ask the user to paste, upload or describe their contents; debug
  with invented values or with reports that give positions only (file, chart,
  chamber numbers). Tools that read them run locally, never through a cloud
  service. Tests make their images at run time from fake charts and commit none.
- Real system files live outside this repo. Do not go looking for them. If you
  find any `.json`, `.csv` or `.txt` other than `system.example.json` and files
  under `tests/fixtures/`, or any `.pdf` or image (`.png`, `.jpg`, `.jpeg`, `.tif`,
  `.tiff`, `.heic`, `.heif`, `.bmp`, `.webp`) anywhere, stop and ask before
  reading it.
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
  same for pull request descriptions as instructed by the session. Do not add
  `Claude-Session:` trailers or links to claude.ai sessions to commits or pull
  request text: they point at private conversations.
- **Pull requests are independent.** Treat every pull request as owned by a
  separate party, including one that we, or another Claude session, wrote. Review
  it through GitHub: a review with inline comments, which its author resolves. Do
  not commit to, push to, rebase or force-push its branch, edit its description,
  or build a competing copy of its work. Reading it, checking it out in a scratch
  worktree and running its tests are fine. If you think the branch itself needs
  changing, ask the user first. Merge only when the user says to.
- **Merging.** The user chooses the method when they say to merge. The default is
  a merge commit; squash an iterative pull request, with a hand-written message;
  rebase merge a focused pull request whose commits each stand alone, only when
  nothing is stacked on it. A pull request with another stacked on it is merged
  with a merge commit and nothing else. Write pull request titles as changelog
  lines. See D33.
- **Stacked pull requests** are allowed but not preferred, and one level deep:
  the upper one is a draft, says "Stacked on #N" and keeps that true. Never
  force-push a branch that has a pull request stacked on it; fix review findings
  with new commits. After the base merges, the upper branch's author rebases it
  onto `main` (`git rebase --onto origin/main <old tip of the base>` if the base
  was squashed or rebase-merged), pushes with `--force-with-lease` and confirms
  the pushed head on GitHub. See D33.
- **Dependabot** opens a weekly pull request for GitHub Actions updates. Merge
  it only when CI is green.
- **Keep docs current.** README limitations, file-format notes and TODO.md
  change in the same commit as the behavior they describe.
