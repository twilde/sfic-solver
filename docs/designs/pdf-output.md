# One PDF of all the pinning charts (core pinning, step 7b)

Status: Implemented

This document describes the second half of step 7 of [core pinning](core-pinning.md): an
option on the chart command that writes every chart of a system file, with its drawing if
asked for, as one PDF to print and file. It was written before any code, accepted by
the maintainer and built ([D62 in decisions.md](../decisions.md)). The first half, the
ASCII drawing, is built ([ascii-stack-drawing.md](ascii-stack-drawing.md), D61), and this
document builds on it.

## Why do this

The charts are for people with a cylinder and a set of pins: the technician who loads each
core works from the sheet for that core. Plain text on standard output is the right form for
the tools (diffable, readable by `check_charts`), and a poor one for paper: it prints in
whatever font the editor chooses, wraps at whatever width the printer driver allows, and
breaks a chart or its drawing across two sheets. The drawing in particular is only
readable in a monospaced font at a size that fits its 85 columns. A PDF fixes all of it: a
fixed font, a fixed size, one chart to a page, and a file that can be emailed to a
locksmith or printed anywhere.

None of that adds a rule or changes a number. It is the same text as the charts, laid out
for a page.

## What it does

`pin_system.py system.json --pdf charts.pdf` writes one PDF with one page per chart, in the
order the charts are printed, and prints nothing else on standard output. With `--draw`
each page carries the chart's drawing under it, exactly as the text output does. The text
is the chart text, line for line: the PDF has no layout of its own to disagree with the
chart.

- **One chart to a page.** A chart with its drawing is up to 46 lines and 85 columns, which
  fills a page, and a chart without one is about 14 lines. Packing several short charts to
  a page would save paper, but a technician wants the sheet for one core, and a page that
  is one chart can be handed over, struck through and filed. A page ends with a footer,
  `Page 3 of 8`, so a loose sheet can be put back in order and a missing one noticed.
- **A fixed font.** The text is set in Courier, which every PDF reader and printer has
  (one of the 14 standard fonts), so nothing is embedded and the characters of the drawing
  line up. One font size serves the whole document, so that no page looks different from
  the next: the largest, up to 10 points, at which the widest line fits the page width and
  the longest chart fits its height, in half-point steps. For the fixture with drawings
  that is 9.5 points on a Letter page with three-quarter-inch margins. If a chart would
  need less than 6 points the command stops and says which chart and why, rather than
  printing something nobody can read.
- **Letter by default, `--paper a4` for A4.** SFIC is a US standard, so Letter is the
  default; A4 is a one-word change.
- **No dates or identifiers in the file.** A PDF normally records when it was made and by
  what; this one records neither. The `Date` line in each chart is the date the chart
  command was given, and the PDF does not add another. The document's title is the
  generic `Pinning charts` and its producer is `sfic-solver`, and the building's name and
  the system file's name do not appear in the metadata (the first is on every page, as
  the `Key System` line, where it belongs). Two runs on the same file and date produce
  the same bytes, so a PDF can be compared and tested.
- **Characters.** The font prints Latin-1 text (the PDF's WinAnsi encoding), which covers
  every key name the tools are likely to see. A chart with a character outside it (a key
  named in another script) stops the command with the chart's number, and the text
  output still works. The error does not quote the chart: a chart is key data.

The file is key data, like the text it holds, and a printed sheet is key data too: the
pin sizes give the bittings away. So `--pdf` follows the rules `--out` follows. It
refuses an existing file unless `--force`, opens the file exclusively so that a race
cannot replace one, gives a one-line error for a bad path, and reminds the user on standard
error that the file is key data to keep outside the repository. `--pdf` and `--out` are
alternatives and the command refuses both together, since one run writing the text to one
place and the PDF to another is two outputs and two reminders. If a core cannot be pinned
nothing is written, as with the text.

## The guard

The core pinning plan said the data-file guard has to learn `.pdf` first. It already has:
the guard, `.gitignore`, the pre-commit hook and CI refuse a `.pdf` and every image format
anywhere in the repository, fixtures included (D32 and D35, from the chart-scanning work). So the
PDF output needs no change to the guard, only a test that the file the command writes is
one the guard refuses, so the two cannot drift apart.

## How the PDF is written

The writer is a new module, `pdfwriter.py`, with one function: a list of pages (each a
list of text lines) and a paper size in, bytes out. It writes a PDF 1.4 file by hand with
the standard library only: a catalogue, a page tree, one font object and, for each page, a
page object and a content stream that sets the font and leading, writes each line as a
string and ends with the footer. Strings escape the backslash and the two parentheses,
which matters because a unit core's `Core` line is `Unit cores (unit:101)`. Nothing is
compressed. A document of eight charts is 20 KB, and an uncompressed file can be read with a
text editor, which is useful when something is wrong.

A prototype of exactly this, written for the fixture's eight charts with drawings, opens
and prints in two independent readers (pdfium, through the scanner's optional package, and
poppler's `pdftotext`), has eight pages, and gives the chart text back. It also confirmed
that the drawing, the widest part, fits a Letter page at 9.5 points with room to spare.
No PDF library is added: a PDF writer for one font and plain lines of text is a hundred lines,
and the project's rule is that a new dependency needs its own decision (D38). The
writer deliberately cannot do anything else: no images, no fonts, no links, so there is
nothing in it to go wrong beyond the page geometry.

## How it is tested

The core suite runs with no PDF package, so the main tests parse the file this module
writes with a small reader of their own, which is itself the check that the file is a PDF:

- The structure is exact: the header, the cross-reference table whose every offset points
  at its object, `startxref` pointing at the table, the page count in the page tree equal
  to the number of pages, and each stream's `/Length` equal to its bytes.
- The text round-trips: the strings in each page's content stream, unescaped and decoded,
  are the chart's lines, one for one, including the parentheses and backslashes, and the
  footer says `Page n of N`.
- Every line fits the page: with the chosen font size and the 0.6-em width of Courier, the
  widest line is inside the margins on every page, and the last line is above the footer.
- Two runs give the same bytes, and the file has no date, no author and no file name in it.
- A chart that does not fit even at 6 points, and a character outside WinAnsi, stop the
  command with a one-line error that does not quote the chart. A bad path, an existing
  file and `--out` with `--pdf` are refused as the text output refuses them.
- With the scanner's optional packages installed (the scanner jobs in CI, and any session
  that has them), pdfium opens the file, the page count is right and the extracted text
  matches the chart text after the whitespace is normalised. Without them this test skips,
  and the structural tests above still run everywhere.
- The `.pdf` the command writes in a test is one the data-file guard refuses.

All of these make their PDFs at run time in a temporary directory from the fake fixture.
No PDF is committed.

## Alternatives considered

**A PDF library** (an optional extra, as the scanner has one). It would handle fonts,
encodings and compression for free, and nothing here needs them. It would add a
dependency to a tool that has none, for one font of plain text, and pull the scanner's
precedent (D38) beyond the scanner. The writer is small enough to own.

**HTML for the browser to print.** No writer at all: the tool would write an HTML file
with the charts in `<pre>` blocks and a print stylesheet, and the owner would print to
PDF. It is the cheapest, and it leaves the font, size and page breaks to the browser, which
is the problem this document starts with. It also writes a second kind of key-data file
that the guard does not know.

**Several charts to a page.** Without drawings three or four charts fit a sheet, so a system
with many cores would need a quarter of the pages. A technician then holds a sheet with
other doors' pins on it. One to a page costs paper and is what is filed.

**Embedded fonts and Unicode.** A TrueType font would print any key name. It would make the
file larger and make the writer a font parser, to serve names that today are ASCII. The
error that names the chart is the proportionate answer.

**Compression, bookmarks, tagging, PDF/A.** None is needed for eight pages of text. A
bookmark per core would help a very large system and can be added without changing the
rest; compression is a one-line change to the stream if file size ever matters.

**Writing the PDF and the text together.** One run, two files. It saves a command and
doubles the key-data files a run leaves behind, so the owner has to remember both. Two
commands, each of which says what it wrote, are clearer.

## Decision and plan

Add the PDF output as described, one pull request (step 7b), in three steps (the draft
of this document and its acceptance are commits of their own, outside them):

1. `pdfwriter.py`, with its tests (the structural reader, the round trip, the geometry,
   the determinism, the errors), changing nothing else.
2. `--pdf` and `--paper` in `pin_system.py`, with its tests, including the guard test.
3. The README section on printing charts, the design text, TODO and the decision entry.

Accepting this document means accepting `--pdf FILE` and `--paper` on `pin_system.py`, one
chart to a Letter page by default with the drawing under it when `--draw` is given, the
hand-written writer in `pdfwriter.py`, the metadata and encoding rules above, and that
`--pdf` and `--out` are alternatives. Nothing changes for output printed without `--pdf`,
and no scoring, solver or checker behavior changes.

## What nobody can know yet

How a real printer handles the margins is settled by printing a sheet, which no test can
do: three-quarter-inch margins are the safe choice for most office printers, and the number
is one constant. Whether readers other than the two tried show the pages exactly as these do
is a fair worry for any hand-written PDF. The file uses only what the format has had since
version 1.4 (one standard font, plain content streams, a classic cross-reference table), which
is why the writer is kept so small, and a viewer that cannot open it would be a bug to fix in
the writer.
