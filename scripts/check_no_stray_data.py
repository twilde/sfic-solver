#!/usr/bin/env python3
"""Fail if any data file (.json, .csv or .txt) other than the allowed ones is committed.

Real system files, exports (such as a key matrix) and pinning charts contain real
bittings and must never be committed. The only allowed data files are system.example.json
(repo root) and fixtures under tests/fixtures/, which must use obviously fake
bittings.

Usage:
    scripts/check_no_stray_data.py --staged     # files staged for commit (pre-commit hook)
    scripts/check_no_stray_data.py --tracked    # every tracked file (CI)
    scripts/check_no_stray_data.py --history    # every path ever committed on HEAD (CI)
    scripts/check_no_stray_data.py PATH...      # explicit paths

Exits with status 1 if a disallowed data file is found.
"""
import subprocess
import sys

DATA_EXTENSIONS = (".json", ".csv", ".txt")
ALLOWED_EXACT = {"system.example.json"}
ALLOWED_PREFIX = "tests/fixtures/"


def is_stray(path):
    path = path.replace("\\", "/")
    if not path.lower().endswith(DATA_EXTENSIONS):
        return False
    if path in ALLOWED_EXACT:
        return False
    return not path.startswith(ALLOWED_PREFIX)


def find_stray(paths):
    return sorted({p for p in paths if is_stray(p)})


def git_paths(*args):
    out = subprocess.run(["git", *args, "-z"], check=True, capture_output=True).stdout
    return [p for p in out.decode().split("\0") if p]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--staged"]:
        paths = git_paths("diff", "--cached", "--name-only", "--diff-filter=ACMRT")
    elif argv == ["--tracked"]:
        paths = git_paths("ls-files")
    elif argv == ["--history"]:
        paths = git_paths("log", "--format=", "--name-only", "--diff-filter=ACMRT", "HEAD")
    elif argv and not argv[0].startswith("--"):
        paths = argv
    else:
        sys.exit(__doc__)

    stray = find_stray(paths)
    if stray:
        print("Refusing: .json, .csv and .txt files other than system.example.json and "
              "tests/fixtures/ may hold real key data:", file=sys.stderr)
        for p in stray:
            print(f"  {p}", file=sys.stderr)
        print("Unstage them (git restore --staged <file>); keep real system files outside "
              "this repo.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
