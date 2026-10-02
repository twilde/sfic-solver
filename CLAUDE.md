# CLAUDE.md

Guidance for AI assistants (and humans) working in this repo. Read README.md
for what the tools do, docs/design.md for how they are built and why (the
current design, in prose), docs/decisions.md for the decision log (short,
numbered, append-only), and docs/designs/ for the larger feature designs.

## Project

Small, dependency-free Python tools (3.11+, standard library only) that plan and
check a master-keyed SFIC key system. Code lives in `sfic_solver/`; the root
`*.py` scripts are thin entry points that must keep working as command lines.

```bash
pip install -e ".[test]"        # pytest is the only extra dependency
git config core.hooksPath .githooks
pytest
```

In a session, pytest is usually not installed globally: make a venv in the
scratchpad (`python3 -m venv $SCRATCH/venv && $SCRATCH/venv/bin/pip install -e
".[test]"`) and use its `pytest`.

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
- Scans, photos and PDFs of charts, and any OCR text made from them, are real
  key data too. Never ask the user to paste, upload or describe their contents;
  debug with invented values or with reports that give positions only (file,
  chart, chamber numbers). Tools that read them run locally, never through a
  cloud service, because a cloud OCR service would receive the whole chart, and
  an uploaded image can be kept or indexed even if it is later deleted. Tests
  make their images at run time from fake charts and commit none.
- Real system files live outside this repo. Do not go looking for them. If you
  find any `.json`, `.csv` or `.txt` other than `system.example.json` and files
  under `tests/fixtures/`, or any `.pdf` or image (`.png`, `.jpg`, `.jpeg`,
  `.tif`, `.tiff`, `.heic`, `.heif`, `.dng`, `.avif`, `.jp2`, `.gif`, `.bmp`,
  `.webp`) anywhere, stop and ask before reading it.
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
  top of it, so each is easy to read. A refactor that claims to change no
  behavior shows it: capture the output of the commands before (seeded runs
  included) and compare it after.
- **Ask questions.** If you are not sure what the user wants, ask.
- **Write design decisions down.** Every decision gets a short entry in the log,
  `docs/decisions.md` (a few sentences, at most 150 words, ending in a `Detail:`
  line that links to the section of `docs/design.md` with the reasoning), in the
  same commit as the decision. Longer reasoning, and anything that changes how
  the design is now, goes in `docs/design.md`, which is edited in place so that it
  never contradicts itself. Never rewrite an old log entry: add a new one and give
  the old one a `Status: Superseded by Dn.` or `Status: Amended by Dn.` line. A
  larger feature (one that changes what the tools model, will take several
  commits, or has open questions) gets a narrative design document in
  `docs/designs/` first, written as an essay (problem, model, alternatives,
  decision, plan, open questions) and agreed with the user before any code, plus a
  short log entry pointing to it. Before numbering a log entry, look at the open
  pull request branches
  (`git show origin/BRANCH:docs/decisions.md | grep '^## D'`) and take the next
  free number; whichever merges second rebases. See D24, D41.
- **Commit and push when a piece of work is complete.** The user reviews on
  GitHub, not in the Claude interface, so push finished work. Do not push
  half-done work.
- **Direct commit or pull request.** Commit straight to `main` when the user has
  given the exact wording or intent, or the change is small and low risk
  (documentation fixes, TODO updates, mechanical edits). Open a pull request for
  new policy or design wording the user has not seen, for code or behavior that
  should pass CI before it lands, for files another session is editing, and
  whenever the user asks. Say which route you are taking, and why, in one line.
  See D34.
- **No open questions in a pull request.** Do not open a pull request, draft or
  not, that contains open questions or exists to ask the user for a decision;
  settle those in chat first. To get something reviewed before then, push the
  commits to a branch with no pull request and give the user the branch, a
  commit link or a compare link. A design document may still say what nobody can
  know yet (details that can only be settled while building), but not questions
  waiting for the user's answer.
- **Commit identity and attribution.** Commit as the user, using their GitHub
  noreply address (set in this repo's local git config), never a personal
  email: commit emails are public and permanent. Always end commit messages with a `Co-Authored-By: <Claude model>
  <noreply@anthropic.com>` trailer, so AI involvement is transparent. Do the
  same for pull request descriptions as instructed by the session. Cloud sessions
  also add a `Claude-Session:` trailer and a link to their claude.ai session to
  commits and pull request descriptions. Their harness instructions take priority
  over this file, so we accept them: do not strip them and do not flag them in
  review. The link points at a private conversation, so never copy conversation
  content into a commit or pull request, and keep sharing off for any session
  that discussed real key data. See D37.
- **Pull requests are independent.** Treat every pull request as owned by a
  separate party, including one that we, or another Claude session, wrote. Review
  it through GitHub: a review with inline comments, which its author resolves. Do
  not commit to, push to, rebase or force-push its branch, edit its description,
  or build a competing copy of its work. Reading it, checking it out in a scratch
  worktree and running its tests are fine. If you think the branch itself needs
  changing, ask the user first. Merge only when the user says to.
- **Reviews.** Start each inline comment with a label, **Should fix** or
  **Optional**, and say in the summary whether anything blocks. The author gives
  every thread a disposition: fixed in a commit, tracked (an issue or a named
  pull request), or declined with a reason. Merge when no Should-fix thread is
  open and every Optional one has a disposition. If the user says to merge now,
  merge, then file an issue listing the threads still open and tell the user. In
  reproductions and examples use obviously fake names and values (`NOT A REAL
  SYSTEM 4B`), because authors copy them into tests. The procedure, and the
  review task the maintainer starts by hand, are in docs/reviewing.md. See D39,
  D40.
- **Merge procedure.** Before merging, check that the head on GitHub is the one
  that was reviewed and that CI is green, and test the pull request merged into
  current `main`. Pin the merge to the reviewed head
  (`gh pr merge --match-head-commit <sha>`). Afterwards update `main`, check the
  first-parent log, that a merged pull request's original commits are still on
  `main`, and run the suite. See D39.
- **Merging.** The user chooses the method when they say to merge. The default is
  a merge commit; squash an iterative pull request, with a hand-written message;
  rebase merge a focused pull request whose commits each stand alone, only when
  nothing is stacked on it. A pull request with another stacked on it is merged
  with a merge commit and nothing else. Write pull request titles as changelog
  lines, and give a merge commit that title plus `(#N)` as its subject
  (`gh pr merge --subject`), since GitHub's default subject names the branch.
  See D33.
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
  change in the same commit as the behavior they describe. When one fact is
  written in several files (a version, a list of extensions, the setup
  commands), add a test that keeps them in step.
