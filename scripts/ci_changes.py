#!/usr/bin/env python3
"""Say whether a change can affect the scanner, so CI can skip its slow checks.

The scanner's tests need Tesseract and the `scan` extra and take the most time, so
CI runs them only when the change touches the scanner or something it uses. When it
is unsure it says yes: no base to compare with, or git failing, both mean "run them".

Usage:
    scripts/ci_changes.py                  # no base: run the scanner checks
    scripts/ci_changes.py --base REF       # run them only if a file changed since REF

Prints one line, `scanner=true` or `scanner=false`, to append to $GITHUB_OUTPUT.
The files that decided it go to standard error, for the CI log.
"""
import argparse
import subprocess
import sys

# A changed path that starts with any of these can affect the scanner. Beyond the
# scanner itself: the core modules it imports (and check_charts, which its tests run
# its output through), its tests and their helpers, the packaging that declares its
# extra, and CI itself. tests/test_ci_changes.py checks the list against the imports.
SCANNER_PREFIXES = (
    "sfic_solver/scanning/",
    "sfic_solver/scan_charts.py",
    "sfic_solver/charts.py",
    "sfic_solver/pinning.py",
    "sfic_solver/check_charts.py",
    "tests/test_scan_",
    "tests/scan_",
    "tests/conftest.py",
    "pyproject.toml",
    ".github/workflows/ci.yml",
    "scripts/ci_changes.py",
)


def touches_scanner(paths):
    """The changed paths that can affect the scanner."""
    return [p for p in paths if p.replace("\\", "/").startswith(SCANNER_PREFIXES)]


def changed_since(base):
    """Paths changed on HEAD since it left `base` (what a pull request shows)."""
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"],
                         capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", help="git ref to compare HEAD with; omit to run everything")
    args = parser.parse_args(argv)

    if args.base is None:
        print("no base to compare with: running the scanner checks", file=sys.stderr)
        print("scanner=true")
        return 0
    try:
        changed = changed_since(args.base)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"could not list the changes since {args.base} ({exc}): "
              "running the scanner checks", file=sys.stderr)
        print("scanner=true")
        return 0

    hits = touches_scanner(changed)
    for path in hits:
        print(f"scanner affected by: {path}", file=sys.stderr)
    if not hits:
        print(f"{len(changed)} changed file(s), none touching the scanner", file=sys.stderr)
    print(f"scanner={'true' if hits else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
