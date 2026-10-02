#!/usr/bin/env python3
"""Fail if any data file other than the allowed ones is committed.

Real system files, exports (such as a key matrix) and pinning charts contain real
bittings and must never be committed. Two kinds of file are refused:

  text data (.json, .csv, .txt)   allowed only as system.example.json (repo root)
                                  and under tests/fixtures/, with obviously fake
                                  bittings
  scans and PDFs (.pdf, .png,     refused everywhere, fixtures included: a picture
  .jpg, .jpeg, .tif, .tiff,       cannot carry a FAKE marker or be reviewed in a
  .heic, .heif, .bmp, .webp)      diff, and tests make their images when they run

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
SCAN_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic", ".heif",
                   ".bmp", ".webp")
ALLOWED_EXACT = {"system.example.json"}
ALLOWED_PREFIX = "tests/fixtures/"


def is_stray(path):
    path = path.replace("\\", "/")
    if path.lower().endswith(SCAN_EXTENSIONS):
        return True
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
              "tests/fixtures/, and any PDF or image (scans of charts), may hold real "
              "key data:", file=sys.stderr)
        for p in stray:
            print(f"  {p}", file=sys.stderr)
        print("Unstage them (git restore --staged <file>); keep real system files outside "
              "this repo.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
