#!/usr/bin/env python3
"""Turn scans of paper pinning charts into text charts that check_charts can read.

Reads PDFs and image files (or directories of them), reads the charts on the pages
with Tesseract, run locally, and writes up to three text files in the legacy chart
layout (see docs/designs/chart-scanning.md):

  NAME.txt          charts that passed every check; give this to check_charts
  NAME.failed.txt   charts read completely that failed a chart-internal check
                    (a column that does not add up, say); check_charts can read it
  NAME.review.txt   charts that could not be read completely, with ?? where; it is
                    deliberately unreadable to check_charts. Finish it by hand,
                    looking at the page the report names

Scans are key data, so the files are created readable by you alone, nothing is
written but those files (no images, no temporary files), nothing leaves this
computer, and the report names positions only (input, page, chart, row, chamber),
never a digit or a file name. It does not run the conformance check: run
check_charts on the output yourself.

Needs the optional extras and Tesseract: pip install -e ".[scan]", and
brew install tesseract (macOS) or apt install tesseract-ocr (Debian, Ubuntu).

Usage:
    ./scan_charts.py scans.pdf [more.pdf | a_directory ...] [-o NAME] [--force]

Exits 0 if every chart was accepted, 1 if anything needs attention, 2 if it could
not run (missing dependency, bad input, an output file in the way).
"""
import argparse
import sys

from . import scanning
from .scanning import assemble, output


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", metavar="PATH",
                    help="PDF or image files, or directories of them (sorted)")
    ap.add_argument("-o", "--output", metavar="NAME",
                    help="write NAME.txt, NAME.failed.txt and NAME.review.txt "
                         "(default: next to the first input, named after it)")
    ap.add_argument("--force", action="store_true",
                    help="replace output files that already exist")
    ap.add_argument("--tesseract", metavar="PROGRAM",
                    help=f"the Tesseract program (default: on the path, or "
                         f"${scanning.TESSERACT_ENV})")
    ap.add_argument("--jobs", type=int, metavar="N",
                    help="Tesseract processes to run at once (default: one per CPU)")
    args = ap.parse_args(argv)

    try:
        program = scanning.require(args.tesseract)
        from .scanning import ocr, pages, pipeline
        sources = pages.collect_sources(args.paths)
    except scanning.ScanError as err:
        print(f"sfic-scan-charts: {err}", file=sys.stderr)
        return 2

    base = output.base_path(args.paths[0], args.output)
    targets = [output.target(base, s) for s in output.SUFFIXES]
    links = [p for p in targets if p.is_symlink()]
    if links:
        print("sfic-scan-charts: these output paths are symbolic links, which are never "
              "written through, so nothing was read (move them away):", file=sys.stderr)
        for path in links:
            print(f"  {path}", file=sys.stderr)
        return 2
    if not args.force:
        in_the_way = [p for p in targets if p.exists()]
        if in_the_way:
            print("sfic-scan-charts: these files already exist, so nothing was read "
                  "(use --force to replace them, or -o to write elsewhere):", file=sys.stderr)
            for path in in_the_way:
                print(f"  {path}", file=sys.stderr)
            return 2

    recogniser = ocr.Recogniser(program, args.jobs)
    try:
        def progress(page):
            print(f"read input {page.source}, page {page.number}", file=sys.stderr)
        scan = pipeline.scan(pages.iter_pages(sources), recogniser, progress)
    except scanning.ScanError as err:
        print(f"sfic-scan-charts: {err}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("sfic-scan-charts: interrupted; nothing was written", file=sys.stderr)
        return 130
    finally:
        recogniser.close()

    try:
        written = output.write_outputs(base, scan.charts, args.force)
    except output.OutputExists as err:
        why = ("is a symbolic link, which is never written through; move it away"
               if err.link else "already exists (use --force to replace it)")
        print(f"sfic-scan-charts: {err.args[0]} {why}; nothing was written", file=sys.stderr)
        return 2
    lines, ok = output.report(scan, recogniser.version)
    print("\n".join(lines))
    names = {assemble.ACCEPTED: "accepted", assemble.FAILED: "failed",
             assemble.REVIEW: "review"}
    for status, count, path in written:
        print(f"wrote {count} {names[status]} chart(s) to {path}", file=sys.stderr)
    for path in output.stale_files(base, written):
        print(f"note: {path} is left from an earlier run", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
