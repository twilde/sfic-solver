#!/usr/bin/env python3
"""Check that the pinner reproduces real pinning charts.

Reads charts (the tools' layout or the legacy one: see docs/designs/core-pinning.md)
from files or directories of .txt files, pins each chart's keys with the pinning
system it names, and compares every chamber with the chart. Use it on charts from
your keying software, kept outside this repository, to find out whether the rules
in the pinner match what the software does.

Charts are key data, so the report names no key, core or building and shows no
bitting or pin size: only counts and positions (file, chart and chamber numbers,
in the order given), so that it is safe to quote in an issue. --details adds the
pin sizes for your own eyes; do not share that output.

Usage:
    ./check_charts.py charts.txt [more.txt | a_directory ...]
    SFIC_CHARTS=/path/to/charts ./check_charts.py     # when no path is given

With no path and no SFIC_CHARTS it does nothing. Exits with status 1 if a chart
disagrees or cannot be read.
"""
import argparse
import os
import sys
from pathlib import Path

from . import charts, pinning

ENV_VAR = "SFIC_CHARTS"


class Uncheckable(Exception):
    """A chart that cannot be compared at all. `reason` is safe to print; `detail` may
    quote the chart and is shown only with --details."""

    def __init__(self, reason, detail=""):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


def check_chart(chart):
    """Where the pinner disagrees with a chart: a list of (chamber, kind, detail).

    kind is "differs" (the pins are not the chart's), "unpinnable" (the pinner
    refuses the chamber), "layout" (the chart's master rows do not fill from the
    bottom) or "invalid" (a cut the pinning system does not have). detail holds
    the pin sizes, which are key data.
    """
    try:
        system = pinning.get_system(chart.system)
    except ValueError as err:
        raise Uncheckable("names a pinning system the tools do not have", str(err)) from None
    keys = [[int(c) for c in bitting] for _, bitting in chart.keys]
    control = [int(c) for c in chart.control]
    problems = []
    for chamber in range(chart.chambers):
        number, shown = chamber + 1, chart.column(chamber)
        if shown is None:
            problems.append((number, "layout", ""))
            continue
        try:
            ours = pinning.pin_chamber(system, [key[chamber] for key in keys],
                                       control[chamber]).pins
        except pinning.PinningError as err:
            problems.append((number, "unpinnable", err.reason))
        except ValueError as err:
            problems.append((number, "invalid", str(err)))
        else:
            if ours != shown:
                problems.append((number, "differs",
                                 f"chart {list(shown)}, pinner {list(ours)}"))
    return problems


def find_files(paths):
    """Expand directories to their .txt files (sorted); None for a path that is neither."""
    files = []
    for path in map(Path, paths):
        if path.is_dir():
            files.extend(sorted(path.rglob("*.txt")))
        elif path.is_file():
            files.append(path)
        else:
            return None
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", metavar="PATH",
                    help=f"chart files or directories (default: ${ENV_VAR} if set)")
    ap.add_argument("--details", action="store_true",
                    help="also show pin sizes (key data: for your eyes only)")
    args = ap.parse_args(argv)

    paths = args.paths or ([os.environ[ENV_VAR]] if os.environ.get(ENV_VAR) else [])
    if not paths:
        print(f"no charts given (pass a path or set {ENV_VAR}); nothing to do")
        return 0
    files = find_files(paths)
    if files is None:
        ap.error("a path is not a file or a directory")
    if not files:
        ap.error("no .txt chart files found")

    n = {"files": len(files), "compared": 0, "agree": 0, "disagree": 0, "chambers": 0,
         "bad": 0, "unchecked": 0, "unreadable": 0}      # unchecked: charts; unreadable: files
    if args.details:
        print("--details shows pin sizes: this is key data, do not share it.\n")
    for file_number, path in enumerate(files, 1):
        try:
            parsed = charts.parse_charts(path.read_text(encoding="utf-8-sig"))   # a BOM is fine
        except UnicodeDecodeError:
            print(f"file {file_number}: is not UTF-8 text (save it as UTF-8 or plain ASCII)")
            n["unreadable"] += 1
            continue
        except OSError:
            print(f"file {file_number}: cannot be read")
            n["unreadable"] += 1
            continue
        except charts.ChartError as err:
            print(f"file {file_number}: {err}")
            n["unreadable"] += 1
            continue
        except ValueError as err:          # last resort: whatever it was, do not quote it
            print(f"file {file_number}: could not be read (unexpected content)")
            if args.details:
                print(f"    {err}")
            n["unreadable"] += 1
            continue
        for chart_number, chart in enumerate(parsed, 1):
            try:
                problems = check_chart(chart)
            except (Uncheckable, ValueError) as err:   # ValueError: last resort, never quoted
                reason = err.reason if isinstance(err, Uncheckable) else "could not be checked"
                detail = err.detail if isinstance(err, Uncheckable) else str(err)
                print(f"file {file_number}, chart {chart_number}: {reason}")
                if args.details and detail:
                    print(f"    {detail}")
                n["unchecked"] += 1
                continue
            n["compared"] += 1
            n["chambers"] += chart.chambers
            if not problems:
                n["agree"] += 1
                continue
            n["disagree"] += 1
            n["bad"] += len(problems)
            words = {"differs": "differs", "unpinnable": "cannot be pinned",
                     "layout": "has master rows that do not fill from the bottom",
                     "invalid": "has a cut the pinning system does not have"}
            print(f"file {file_number}, chart {chart_number}: "
                  + "; ".join(f"chamber {c} {words[kind]}" for c, kind, _ in problems))
            if args.details:
                for number, kind, detail in problems:
                    if detail:
                        print(f"    chamber {number}: {detail}")

    print(f"\nChecked {n['files']} file(s), {n['compared']} chart(s), {n['chambers']} chamber(s): "
          f"{n['agree']} chart(s) agree with the pinner, {n['disagree']} do not "
          f"({n['bad']} chamber(s)); {n['unchecked']} chart(s) could not be checked; "
          f"{n['unreadable']} file(s) could not be read.")
    ok = n["disagree"] == 0 and n["unchecked"] == 0 and n["unreadable"] == 0
    print("OK" if ok else "DISAGREEMENTS: the pinner's rules do not match these charts")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
