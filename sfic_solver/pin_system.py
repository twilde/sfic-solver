#!/usr/bin/env python3
"""Print the pinning charts for every core of a system file, in the tools' chart layout.

Reads the same JSON as check_system.py. The file must set `pinning` (the pin sizes need a
pinning system), every core must name its `control` key, and no bitting may be null. A
core with several change keys, such as `unit:*`, gets one chart per key, whose `Core` line
carries the key's name so a chart says which door it is for.

Usage:
    ./pin_system.py system.json                       # charts on standard output
    ./pin_system.py system.json --date 2026-10-01     # a fixed date (default: today)
    ./pin_system.py system.json --draw                # and a drawing of the stacks under each
    ./pin_system.py system.json --out charts.txt      # to a file (never over an existing one)
    ./pin_system.py system.json --pdf charts.pdf      # one PDF, a page to a chart (--paper a4)

If a core cannot be pinned, no chart is printed: the cores and chambers are listed, as
check_system.py lists them, and the status is 1.

The charts are key data: their pin sizes give the bittings away, on screen, in a file or
on a printed page. Keep them, like the system file, outside this repository (see Privacy
in the README).
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

from .chartwriter import core_label, draw_stacks, format_chart, join_charts
from .config import load_or_exit
from .pdfwriter import PAPER, PdfError, pages_to_pdf
from .pinning import pin_chambers

MAX_LISTED = 30        # lines of unpinnable chambers before "... and N more"


def today():
    return datetime.date.today().isoformat()


def iso_date(text):
    """`text` if it is a real date written YYYY-MM-DD, else ValueError (for argparse)."""
    try:
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", text):
            raise ValueError
        datetime.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a date written YYYY-MM-DD") from None
    return text


def build(cfg, date, draw=False):
    """(charts, problems): one chart text per core and change key, and an UNPINNABLE line
    for every chamber that cannot be pinned (then there are no charts). With `draw`, each
    chart is followed by a blank line and a drawing of its pin stacks."""
    texts, problems = [], []
    for core in cfg.cores:
        control = cfg.control_keys[core["control"]]
        for change in core["changes"]:
            keys = [(name, cfg.keys[name]) for name in [change, *core["masters"]]]
            chambers, errors = pin_chambers(cfg.pinning, [cuts for _, cuts in keys], control)
            problems += [f"UNPINNABLE {core['name']} [{change}], chamber {e.chamber}: {e.reason}"
                         for e in errors]
            if not errors:
                text = format_chart(cfg.name, cfg.pinning.name, core_label(core, change),
                                    date, control, keys, chambers)
                if draw:
                    text += "\n" + draw_stacks(cfg.pinning, chambers)
                texts.append(text)
    return texts, problems


def write_new_file(path, data, force):
    """Write `data` (text, or bytes for a PDF) to `path`, which must not exist unless `force`.

    The file is opened exclusively, so a file made since the last look is not replaced
    either. A failure is a one-line error, never a traceback."""
    mode = "w" if force else "x"
    try:
        if isinstance(data, bytes):
            with path.open(mode + "b") as f:
                f.write(data)
        else:
            with path.open(mode, encoding="utf-8", newline="\n") as f:
                f.write(data)
    except FileExistsError:
        sys.exit(f"error: {path} exists; give --force to replace it")
    except OSError as e:
        sys.exit(f"error: cannot write {path}: {e.strerror}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--date", type=iso_date, help="the date to print, YYYY-MM-DD (default: today)")
    ap.add_argument("--draw", action="store_true",
                    help="draw each core's pin stacks, to scale, under its chart")
    ap.add_argument("--out", help="write the charts to this file instead of standard output")
    ap.add_argument("--pdf", help="write the charts as one PDF, a page to a chart, instead of "
                                  "text (an alternative to --out)")
    ap.add_argument("--paper", choices=sorted(PAPER), help="the PDF's paper (default: letter)")
    ap.add_argument("--force", action="store_true",
                    help="let --out or --pdf replace an existing file")
    args = ap.parse_args(argv)
    if args.pdf and args.out:
        ap.error("--pdf and --out are alternatives: give one")
    if args.paper and not args.pdf:
        ap.error("--paper is for --pdf")

    cfg = load_or_exit(args.config)
    if not cfg.pinning:
        sys.exit(f"error: {args.config}: the system file does not set pinning, which the pin "
                 f"sizes need (for example \"pinning\": \"A2\")")

    texts, problems = build(cfg, args.date or today(), args.draw)
    if problems:
        for line in problems[:MAX_LISTED]:
            print(line, file=sys.stderr)
        if len(problems) > MAX_LISTED:
            print(f"... and {len(problems) - MAX_LISTED} more", file=sys.stderr)
        print("no charts printed: some cores cannot be pinned (check_system.py says why)",
              file=sys.stderr)
        return 1
    if args.pdf:
        try:
            data = pages_to_pdf([text.rstrip("\n").split("\n") for text in texts],
                                args.paper or "letter")
        except PdfError as e:
            sys.exit(f"error: cannot make the PDF: {e}")
        write_new_file(Path(args.pdf), data, args.force)
        print(f"wrote {len(texts)} chart(s) to {args.pdf}; they are key data, so keep the "
              f"file and any printed pages outside the repository", file=sys.stderr)
    elif args.out:
        write_new_file(Path(args.out), join_charts(texts), args.force)
        print(f"wrote {len(texts)} chart(s) to {args.out}; they are key data, so keep the file "
              f"outside the repository", file=sys.stderr)
    else:
        sys.stdout.write(join_charts(texts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
