# Contributing

Thanks for your interest. Bug reports, fixes, documentation and ideas are all
welcome. This is a small project maintained in spare time, so reviews may take a
while.

## The one hard rule: no real key data

Never put real bittings, real system files, real pinning charts (the pin sizes
give the bittings away), or anything that identifies a real building, its
residents or its keys in an issue, pull request, test, example, comment or
commit message. The project is public, and so is its history.

- Reproduce problems with `system.example.json` or invented values.
- Test fixtures live in `tests/fixtures/`, use random or obviously fake
  bittings, and are marked as fake: a JSON fixture carries a `_comment` starting
  with `FAKE`, and a text fixture begins with a line starting with `FAKE`.
- `.gitignore`, a pre-commit hook and CI all refuse to commit `.json`, `.csv` or
  `.txt` files other than `system.example.json` and the fixtures, and every PDF
  or image (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.heic`, `.heif`,
  `.dng`, `.avif`, `.jp2`, `.gif`, `.bmp`, `.webp`) without exception, since a
  picture cannot be marked as fake. Tests that need images make them when they
  run. Please do not bypass the guards (`--no-verify`, `git add -f`).

## Before you start

Open an issue first for anything bigger than a small fix, so we can agree on the
approach. In particular, the solver's scoring weights, the counting algorithms
and the output format are deliberately stable. Changes there need a stated
reason and discussion first (see D6 in [docs/design.md](docs/design.md)).

A larger feature, meaning one that changes what the tools model, needs several
commits, or has open questions, starts with a short design document in
`docs/designs/` that we agree on before any code is written. The existing ones
show the style: an essay about the problem, the model, the alternatives and the
plan, not a list of bullet points.

## Setup

Python 3.11 or newer, standard library only (please do not add runtime
dependencies).

```bash
pip install -e ".[test]"        # pytest is the only extra dependency
git config core.hooksPath .githooks
pytest
```

### Scanning tests (optional)

The chart scanner's tests draw fake charts and read them back with Tesseract,
so they need three things beyond the setup above. Without them those tests are
skipped, not failed, and everything else still runs.

```bash
pip install -e ".[test,scan]"   # adds Pillow, numpy and pypdfium2
brew install tesseract          # macOS; on Debian/Ubuntu: sudo apt-get install tesseract-ocr
```

and a monospaced font with clear commas: Liberation Mono, DejaVu Sans Mono or
FreeMono (on Debian/Ubuntu: `sudo apt-get install fonts-liberation
fonts-dejavu-core`, which is what CI installs). Courier New and Menlo, the
fonts a Mac has by default, are not enough: their commas are too thin to read
reliably (issue #10), so the OCR tests skip there. On a Mac,
`brew install --cask font-liberation-mono` (or font-dejavu) fixes that.

## Making changes

- **One logical change per commit** and per pull request.
- **Test everything.** A bug fix needs a regression test that fails without the
  fix. A behavior change needs tests for the new behavior. The whole suite must
  pass.
- **Keep refactors separate** from behavior changes, as their own commits.
- **Keep the randomness defaults.** Anything that produces real keys uses
  `secrets` or `random.SystemRandom`; `--seed` exists only for reproducible
  tests.
- **Update the docs in the same change:** the README (format, limitations), the
  decision log in `docs/design.md` when you make a design decision, and the
  feature's design document in `docs/designs/` if it has one.
- **Match the surrounding code**: naming, comment density and idiom.
- **Markdown:** do not wrap a line so that it starts with `+`, `-` or a number
  and a period; it renders as a list. A test checks every Markdown file.

## Commits and pull requests

- Commit under your own name. If you would rather not publish your email, use
  GitHub's noreply address (Settings, then Emails).
- If an AI tool helped write the change, please say so, for example with a
  `Co-Authored-By` trailer in the commit message. This project does the same.
- Contributions are accepted under the project's [MIT license](LICENSE).
- The maintainer chooses how a pull request is merged (merge commit, squash or
  rebase), so write each commit to stand on its own and give the pull request a
  title that reads as a changelog line.
- Try not to depend on another unmerged pull request. If you must, base yours on
  its branch, mark it a draft, say "Stacked on #N" in the description, and
  rebase it onto `main` once the base has merged.
- In the pull request, say what changed and why, and mention any behavior
  change. CI must pass: the tests on every supported Python version, and the
  data-file guard.
- Review comments are labelled **Should fix** or **Optional**. Please reply to
  each thread: fixed (say in which commit), will follow up (say where), or
  declined (say why). A pull request merges when nothing labelled Should fix is
  still open.

## Reporting problems

Use the [issue forms](../../issues/new/choose). For a security problem, follow
[SECURITY.md](SECURITY.md) instead.
