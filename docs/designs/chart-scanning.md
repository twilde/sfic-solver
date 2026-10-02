# Reading scanned pinning charts

Status: Draft

This document proposes a local tool that turns scans of paper pinning charts into
the text chart format that `check_charts` reads, so that an owner who has charts
only on paper can run the conformance check without retyping them. It is written
before any code, to be discussed and changed. It builds on the chart layouts and
the privacy rules in [core-pinning.md](core-pinning.md) ("The chart layout",
"Verification" and "Charts are key data"), and, once agreed, will be summarised in
the decision log ([D38 in design.md](../design.md)).

## Why do this

The conformance check is the layer of verification that touches real data: it
takes a chart from the keying software, pins the chart's own keys with the pinner,
and compares every row. Its value depends on having charts as text. An owner whose
charts exist only as printouts has two choices today: retype hundreds of numbers
by hand, which is slow and, worse, error-prone in exactly the way the check cannot
distinguish from a real disagreement, or not check at all. Reading the paper by
machine is the obvious answer, and it is also an obvious trap. A recognition error
in a pin size looks to `check_charts` like a pinning rule the pinner got wrong, and
a tool that quietly "fixes" what it reads so that it comes out right would defeat
the purpose of the check. So the design below is mostly about what the tool
refuses to do.

## What a scan is, and what the tool promises

A scan or photograph of a chart is the chart. The pin sizes can be read off it by
eye or by OCR, and from them the bittings, so every rule about key data applies to
the image, to any text recognised from it, and to anything derived from either: it
is never committed, never uploaded, never pasted into an issue and never described
in a report. The tool therefore runs entirely on the owner's computer, starts no
network connection, writes no intermediate images, and reports only positions
(which input, which page, which chart, which row, which chamber), as
`check_charts` already does.

Within those limits the tool makes three promises, in this order of importance.

**It transcribes and never repairs.** The tool writes what is on the page. It does
not consult the pinner, the pinning rules, the key hierarchy or the system file,
and it never adjusts a reading so that the chart agrees with them. The reason is
that the owner will run `check_charts` on the output, and the answer to "does the
pinner reproduce this chart?" is only meaningful if the chart is the paper's and
not the pinner's. A tool that picked, among several plausible readings of a cell,
the one that makes the column add up, or the one the pinner would have produced,
would turn every real disagreement into a clean pass. The tool does use two facts
about the *chart itself*, which any chart in the layout must satisfy whoever made
it: the master rows fill from the bottom, and every chamber's pins add up to the
named pinning system's stack total. These can only flag a reading; they are never
used to choose one.

**It fails closed.** Anything uncertain is flagged, and a flagged chart never
reaches the file that is meant to be checked. The cost of a false alarm is a few
seconds with the paper and a pencil. The cost of a silent error is a chart that
passes or fails for the wrong reason, which is the one outcome the tool exists to
prevent. When the two conflict, the tool flags.

**It says where, not what.** Every flag names a position and a kind of problem,
never a bitting, a pin size or a name, so that the report can be quoted in an
issue. The owner looks at the paper.

## What the printouts look like

The design targets one kind of printout and is honest that it has not seen a real
one. The charts are plain fixed-width type: lines of text and rows of numbers
separated by spaces, with no table lines drawn between them, as in the legacy layout
of core-pinning.md. They arrive as PDFs from a scanner, flat and nearly straight, at
200 to 300 dpi, and the first platform supported is macOS, though nothing in the
design is specific to it. A page is one chart or more than one. The header is four
lines (`System`, `Control Key`, `Master Key`, a `Change Keys` line of
comma-separated bittings), followed by the rows `T/D`, `Control`, one or more
`Master` and `Bottom`, one number or `--` per chamber. Photographs, bordered tables
and other fonts are not ruled out, but they are not what the design is tuned for,
and the tool's answer to a page it cannot read is to say so, not to guess.

A page may also carry handwriting, typically notes in the margin that say which
core or system a chart is for. Handwriting is never read: a recogniser built for
print is poor at it, and such notes are the very information that identifies a
building, so the tool must neither transcribe them nor be disturbed by them. The
design handles the case where the notes sit in the margins, clear of the printed
block; notes that touch or sit among the printed lines are not designed for, and
the charts they affect end up in the review file.

A bordered table would need one more stage, to find and remove the ruled lines
before reading, and an easier way to find the columns. It is not built, since it is
not needed; it is the first thing to add if it is.

## How a page becomes a chart

The pipeline has seven stages. Each can fail, and each failure ends in a flag
rather than a guess.

**Pixels.** A PDF page is rasterised at 300 dpi; an image is used as it comes. Any
text layer in a PDF is ignored, deliberately: a scanner's PDF usually has none,
and when one has been added by other software it is the output of an OCR program
of unknown quality, which is exactly what this tool must not trust. One code path
reads pixels, always.

**Cleaning.** The page is converted to grey, a median filter removes speckle, the
background is estimated and divided out so that uneven lighting does not matter,
the angle of the text is found by trying small rotations and keeping the one that
makes the lines of ink sharpest, and the page is straightened and thresholded.
Blank pages are reported as blank and skipped; a page with ink and no recognisable
chart is reported as such.

**Lines and tokens.** Rows of text are found as runs of ink in the horizontal
projection, and each line is cut into tokens at its wide gaps. The width that
separates "a gap inside a token" from "a gap between tokens" is not a constant: it
is found from the page's own gaps, as the largest jump in their sorted widths. This
matters for the dashes, which are narrow, so that the gap inside `--` is nearly as
wide as the gap between two digits, and a threshold fixed as a fraction of the
line height cuts them apart. A cell that is a dash is recognised by its shape (a
short, wide bar), not by OCR, which in a test turned `--` into letters.

**Reading.** This is the part that needed finding out, and the prototype's results
decide the design. They are described in the next section.

**Headers.** Each header line is split at its `=`. The label is read as letters and
matched, loosely, against the table of labels in `charts.py` (the one that already
lets a different spelling be a one-line change); the value is read like a row of
digits. The header gives the chamber count, the length of the control bitting, and
every other bitting and every row must have exactly that many digits or cells.

**Assembling.** Lines are classified by their labels, a header line or a row, and
a chart is a header followed by its rows in the required order. A page may hold
several charts, and lines that belong to neither (a title, a page number) are
reported as ignored, by position, so that a dropped row cannot hide among them.
Ink outside a chart's printed block, meaning left of its row labels, right of its
last column, or above its header or below its last row, is treated the same way and
never recognised: the tool cuts the page to the block that the header and rows
span, reports the ink outside it by position and size (so that margin notes are
visible as skipped, and a mark that merely looks like a chart line is not skipped
silently), and does not pass it to the recogniser. Ink that lands inside the block
is the printed chart's to explain, so a stray mark there adds a token to a row,
fails the cell-count check, and sends the chart to review.

**Checking and writing**, described under "Never silently wrong".

## Reading the digits

Plain OCR is the obvious tool and Tesseract is the best one that runs locally on
every platform, but how it is used decides whether the output can be trusted. A
prototype run on fake charts rendered to images found the following, and each
finding shaped the design.

Reading the whole page as one block drops the spaces between columns (`4  6  9 10
5` comes back as `4 6910 5`), so the columns are lost; sparse-text mode keeps
more structure and drops or garbles cells. Reading each cell on its own works
mostly, but a lone `0` often comes back empty, and a `10` can come back as `1`,
both worse with the slashed zero some fonts use. The best arrangement found is to
cut the page into tokens ourselves, as above, and then to let Tesseract read each
*row of cells as a line*, which gives it the context it needs, asking for
character-level output with one confidence per character. The characters are then
assigned to the tokens in order, using as a check the number of separate marks in
each token, which we know from the image: if Tesseract returns a different number
of characters than there are marks, that reading is unusable and is thrown away
rather than repaired. (Whether the spaces survive depends on a detail worth
recording: with a character whitelist that lacks the space, Tesseract cannot emit
one and merges the row into a single word.)

Two further findings changed the design most. The first is that Tesseract's
confidence is not a good error detector. A row read wrongly came back with every
character at 98 or 99, and the same row read at a slightly different size came back
right. The second is that readings of the same image at several sizes are not
independent: a small `3` was read as `8` by most of them, in one position, because
what confuses the recogniser is the glyph, not the scale. Agreement among
renditions of one image is therefore worth less than it looks, and unanimity among
them, which looked like the natural rule, flags far too many cells (most charts
had at least one) while still passing a systematic error that every rendition
shares. It was only the column-sum check that stopped such a chart.

What does work is to stop asking Tesseract to be right about every glyph, and to use
the one thing a printout has in abundance: every `3` on the page looks like every
other `3`. The tool cuts out each digit mark, scales it to a fixed size and groups
the marks by shape. A page of charts has thousands of marks and ten shapes.
Tesseract's readings (all the renditions of all the rows in which a mark appears)
are then used as votes, and each *group* gets the label that most of its members'
votes name. A mark is read as its group's label. A single misreading is outvoted by
the dozens of other `3`s on the document; a group in which the votes disagree too
much, or that has too few members to vote, is flagged and so is every mark in it. A
mark is flagged as well when its own votes, taken alone, mostly name a different
digit from its group's label, which is how a mark that was grouped with a lookalike
would otherwise slip through. This is a classifier trained on the document itself,
with Tesseract only as the source of labels, and it has two properties that matter
here. It is independent of the recogniser's mistakes in the way renditions were not,
since a mark's reading comes from the whole group's votes and not from its own
context. And it fails in a visible way: if two digits look alike enough to be
grouped together, the group's votes split and the group is flagged, instead of the
marks being quietly read as the same digit. In the prototype, ten groups formed on
clean renders, one for each digit, each at least 98% pure by the votes, and every
cell of the sample came out right where per-row unanimity had flagged most charts.
Votes are pooled across all the pages of a run, so a larger batch makes the groups
better, not worse; this is also the reason the tool takes a whole directory at once.

The prototype's results across image quality are in the next table. They come from
fake charts rendered by the prototype itself, and say nothing about real scans; the
test harness (step 4) is where they become tests, and the README documents only
what that harness proves. The criterion is a number: zero accepted-wrong charts in
at least 1,000 random charts for every condition inside the documented range of
image quality, which bounds the true rate below 0.3% at 95% confidence, and the
README claims exactly that and no more. A thousand charts at two to three seconds
each is far too slow for every CI run, so the harness has two tiers: CI runs a small
sample per condition (some tens of charts) and asserts zero wrong charts and a
minimum accepted, and the full run, marked slow and run on demand and before the
README's documented range changes, is the one that supports the claim.

Each row is 18 random fake charts (three runs of six, the votes pooled within a
run), except the last two, which use 12 charts each and say so; rendered at 300 dpi
and 11 point in a monospaced font unless the row says otherwise, with the
prototype's pipeline and all the checks above. "Wrong" means a chart that was
accepted and differs from the one rendered.

| Image | Accepted and right | Flagged | Wrong |
| --- | --- | --- | --- |
| Clean | 18 | 0 | 0 |
| A second font, with a slashed zero | 18 | 0 | 0 |
| 200 dpi | 17 | 1 | 0 |
| 9 point | 18 | 0 | 0 |
| Skewed by 3 degrees | 18 | 0 | 0 |
| Blurred (Gaussian, sigma 1.5 px) | 18 | 0 | 0 |
| Uneven lighting (40% darker at one corner) | 18 | 0 | 0 |
| Ink at half strength | 18 | 0 | 0 |
| Salt-and-pepper speckle on 3% of pixels | 17 | 1 | 0 |
| Gaussian noise, sigma 15 | 13 | 5 | 0 |
| Gaussian noise, sigma 35 | 12 | 6 | 0 |
| One cell erased, per chart | 0 | 12 of 12 | 0 |
| One cell inked over, per chart | 0 | 12 of 12 | 0 |

Two things stand out. The failure that does occur, as the image degrades, is
flagging, which is the intended direction, and no wrong chart was accepted in any
row. The sample is small: about 200 charts in all, and zero wrong in n trials bounds
the true rate only at about 3 in n (at 95% confidence), so here at about 1.5%. The
harness is where that becomes a number worth claiming. And
degraded images cost something in a way the table understates: a flagged chart
costs a look at the paper, so a scanner setting that gives 12 charts of 18 is a
setting to change. On four cores the prototype took two to three seconds per chart.

## Never silently wrong

A chart is accepted only if every one of the following holds, and otherwise it is
flagged, with the position of the first thing that failed.

| Check | What it catches |
| --- | --- |
| The page was straightened, and lines and tokens were found | Pages too small, too blurred or too skewed to read |
| The header has the four labels in order, and the pinning system's name is known | A page that is not a chart, a cut-off header |
| Every bitting is digits and as long as the control bitting | A dropped or extra digit in a header |
| The rows are `T/D`, `Control`, one or more `Master`, then `Bottom`, each with the chamber count of cells | A missing or merged row or cell |
| Every mark belongs to a group that is large enough and pure enough | Misreadings, and digits the recogniser or the shapes confuse |
| No two groups carry the same label, and every label is a digit | A whole group of one digit read consistently as another: its marks vote together, so purity and size cannot see it, but the digit it was taken for now has two groups |
| Every cell is within the range for its row, and `--` appears only in master rows, filled from the bottom | A digit read as the wrong digit that lands outside what a chart can contain |
| Every chamber's pins add up to the stack total of the system the header names | A digit read as a different digit that stays in range: nearly every single-digit error breaks the sum |

The uniqueness check on group labels exists because group voting is only as good as
the recogniser's mistakes are scattered. The finding above is that the confusion is
by glyph: if Tesseract reads a small `3` as `8` for every `3` on the page, the group
of `3`s is perfectly pure, large and unanimous, and every one of its marks is read
as `8`. The real `8`s form another group, also labelled `8`, and that is what gives
it away: a printout has one shape per digit, so two groups with one label mean that
at least one of them is mislabelled, and the tool flags every mark in both. In the
prototype, ten groups formed on clean renders, one per digit, but the acceptance rule
did not require it, so this is a rule to add and not a description of what the
prototype did. It has a cost: noise can split one digit into two groups, and a
correct run then flags itself. That is the right way round for a rule that is meant
to fail closed, and the harness decides whether merging near-identical groups
earns back the lost acceptance, again only as far as it keeps the no-wrong-chart
property. The check cannot tell which of two same-labelled groups is wrong and does
not try; and a digit that is mislabelled without colliding (a `3` group labelled `8`
in a run with no real `8`s) is the case it cannot see, which the column sums and
`check_charts` are for, and which the header digits, covered by no sum, are exposed
to.

The last row of the table above is the strongest, and it is chart-internal: it does
not say the pins are right for the keys, only that they are a possible stack. It
cannot detect two errors that cancel, nor an error in a header bitting, which no row
repeats. That is why this tool is the first of two stages and not the whole answer.
After accepting a chart, `check_charts` recomputes every row from the header, so a
header digit read wrongly shows up there as a disagreement at its chamber, and the
owner, told the position, looks at that chamber and that header on the paper. A
disagreement at a chamber of a chart that passed every check here is therefore
either a real disagreement with the pinner or a header digit that was misread, and
the two are told apart by the paper and not by the tool. To make the second case
rare, header digits are read with the same group voting as the rows, and a header
digit from a group with any doubt flags the whole chart.

What the tool does not do is as much a part of the design. It does not search
among alternative readings for the one that satisfies a check. It does not use the
pinner to resolve or to confirm a cell. It does not retry a flagged cell until it
passes. A second look at a flagged cell, with different settings, is allowed, but
only to produce more votes for its group; the acceptance rule is the same, and
there is no rule that a retry can satisfy by luck.

## What the tool writes

The input is any number of files and directories, PDF or image, in the order
given, with directories sorted. Pages and charts are numbered in that order, and
the report uses the numbers, not the file names, which can name a building.

Charts are identified by position and nowhere else. The tool carries no name, label
or note from the page into any output: the owner matches "input 1, page 3, chart 1"
to the paper, where whatever is written beside the chart says which core it is. The
legacy layout has no place for a name, and giving it one would mean changing the
reader, which this feature does not do.

There are three outputs and a report, and the difference between them is what
`check_charts` can do with each.

- The **accepted file** holds every chart that passed every check, in the legacy
  layout, and can be given to `check_charts` as it stands.
- The **failed file** (`.failed.txt`) holds every chart that was read completely, so
  that every cell and header digit is a number, but failed a chart-internal check:
  a column that does not add up, a cell outside its range, master rows that do not
  fill from the bottom. It is written out as read, in the legacy layout, and
  `check_charts` can read it. It is kept apart from the accepted file so that "the
  paper's own column does not add up" is not mistaken for "the tool could not read
  it", and so that these charts can be run through `check_charts` and compared with
  the paper without being mixed with the ones that passed.
- The **review file** (`.review.txt`) holds every chart that could not be read
  completely or is not well formed (a row with the wrong number of cells, say), in
  the same layout with `??` in place of any cell or header digit that could not be
  read. `check_charts` refuses this file, as a whole and at its first unreadable
  chart: a row without a number per chamber is unreadable to it. That is deliberate,
  so that a flagged chart can never be checked by accident, and it is the reason a
  chart that was read completely does not go here: it would be refused along with
  the rest of the file. The owner finishes the review file by hand, looking at the
  page named in the report, and checks the result like the others.

The report lists, per input and page, the charts accepted and flagged, and for each
flag its position (row and chamber, or the header line and digit) and its kind
(unreadable, a count that does not match, the votes did not agree, a check that
failed). It lists pages skipped as blank, lines ignored, and a count of marks in
groups too small to vote, and ends with a line that says how many charts were
accepted, how many failed a check and how many need review, and the exit status is 1
if any did not pass, as with `check_charts`. None of it contains a digit read from
the page.

By default the files are written next to the input, with the input's name and the
extensions `.txt`, `.failed.txt` and `.review.txt`, since the owner chose that
directory and it is outside this repository; `-o` chooses another place. The tool
will not overwrite an existing file without being told to, and it writes nothing
else: there are no debugging images, because an image of a page is key data in a
place the owner did not choose. That includes temporary files. Pages are rendered in
memory, and each crop is handed to Tesseract over its standard input (`tesseract
stdin stdout`), so that no image of a page ever exists as a file. The three outputs
hold key data, and SECURITY.md says to treat such files like a password file, so
they are created readable by their owner alone (mode `0600`), not with the default.

## Dependencies and platforms

Tesseract is optional. It is a program, not a Python package; the tool looks for it
at run time, on the path or where `--tesseract` says, and the project does not
install it or import it. Every other tool in the project works without it, and
without any of the Python packages below, exactly as before. Only
`sfic-scan-charts` needs them, and without them it says what is missing and exits
with status 2. This is an exception to D2, which says the project has no runtime
dependencies (standard library only), and it is bounded and stated in "An exception
to D2, and its limits" below.

The rest of the project is standard library only and stays so. Scanning needs more,
and it is kept in an optional extra: `pip install -e ".[scan]"` installs Pillow
(images), numpy (the projections and the shape comparison) and pypdfium2 (PDF
pages). Nothing in the core imports them, the tool imports them when it runs, and
without them it exits with a message that names what is missing and how to install
it. Tesseract is a system program, not a Python package, and the tool runs it as a
subprocess and does not need pytesseract: it is installed with `brew install
tesseract` on macOS, `apt install tesseract-ocr` on Debian and Ubuntu, and with the
UB Mannheim installer on Windows, and found on the path or with `--tesseract`.
The report states Tesseract's version, since readings can change between versions.
The tool starts it with one thread per process and runs several at once.

pypdfium2 is the PDF rasteriser because it is a wheel that carries its own PDF
engine, so a `pip install` is all it takes on every platform, it is permissively
licensed, and one call turns a page into an image. The alternatives were
`pdftoppm`, which is part of poppler and has to be installed separately, not
simply on Windows, and PyMuPDF, whose AGPL licence sits badly with an MIT project.

## An exception to D2, and its limits

D2 says the project has no runtime dependencies. Scanning cannot honour that, since
reading an image needs an image library and a recogniser, so this feature is an
exception to D2, and the exception is made here and not left implied. It holds
only on these terms, each of which is meant to be tested.

The dependencies are optional. `pyproject.toml` keeps `dependencies = []`, and the
Python packages are an extra that nobody installs by accident. Nothing in the core
imports them, so every other tool, and the whole test suite apart from the scanning
tests, runs unchanged on a machine that has none of them. Tesseract is optional in
the same way and is looked for at run time, on the path or where `--tesseract` says,
not at install time. Without a package or without Tesseract, `sfic-scan-charts`
does not fail with a traceback: it exits with status 2 and a message that names
what is missing and how to install it, and everything else keeps working.

The exception covers this feature and no other. It does not make the other tools
depend on anything, and a later feature that wants a dependency (PDF output, D25
step 7, is the likely one) needs its own decision. When step 3 lands, the entry
for D2 in the log gains a line pointing here, so that a reader of D2 finds the
exception.

The alternative, a recogniser written in the standard library alone, is weighed
under "Alternatives considered" and not chosen.

A PDF is parsed by a native library, which is a reason to run the tool on files the
owner made, not on files received from elsewhere. The tool opens no network
connection and Tesseract needs none. The first of those is checked from inside
Python; the second and the native PDF library cannot be, so for them it is a design
rule and not a tested property (see "Testing without real scans").

## Testing without real scans

Tests may use only charts computed from fake bittings, and no image is committed
(the guard refuses them, D32). The harness therefore renders the fake charts to
images when it runs, in a temporary directory: in several fonts, at several
resolutions and sizes, with skew, blur, noise, speckle, uneven lighting and fainter
ink, and as PDFs by way of Pillow and pypdfium2. For each, the test runs the tool
and then `check_charts` on the accepted file, and asserts two things: charts in the
documented range of quality come out accepted and OK, and no accepted chart ever
differs from the one rendered. The second assertion is the one that matters, and the
harness runs it on many random charts, not only the fixtures. Corrupted images (a
digit painted over, a column smudged, a row erased, a page rotated too far,
resolution too low) must be flagged, never accepted with a wrong value. Tests are
skipped cleanly when Tesseract or the extra is not installed, and CI installs both
so that they run there. The privacy promises are tests where Python can check them.
One test runs the tool with `TMPDIR` pointing at an empty directory and asserts that
it is still empty afterwards, which holds only if no temporary file, image or
otherwise, was written. One blocks `socket` in the test process and runs the tool,
so that any attempt by the Python code to open a connection fails the test. One
checks that the three outputs are created with mode `0600`. What cannot be checked
from inside Python is the Tesseract subprocess and the native PDF library: for them
"no files, no network" is a design rule, kept by how they are called (images over
standard input, nothing in the command line that names a file or a host), and the
document says so rather than claiming a test.

The limits of the exception to D2 are tested too: one test
imports every core module with the scanning packages blocked, and one runs the
command with them blocked and with Tesseract missing and checks for exit status 2
and a message that names what is missing.

The harness also draws invented handwriting-like strokes in the margins and checks
two things: with the strokes clear of the printed block the chart is accepted
exactly as without them, and with strokes drawn beside a row, close to its last
column, the chart is flagged and never accepted with a wrong value. The strokes
are random lines and curves, not text, so no handwritten content is needed.

What cannot be tested is real printouts: fonts the harness does not have, printing
and scanning defects it does not model, labels spelt differently. The owner is the
test for that, and the way to take it safely is with positions only. The first run
on real scans should be a single page: if the report says that every chart on it
was flagged for the same reason (say, the marks did not group), that is something
that can be quoted in an issue without a single digit.

## Alternatives considered

Cloud OCR is typically more accurate, but it would receive the whole chart, and that
alone rules it out under the privacy rules (D36): a scan of a chart is key data and is
not sent anywhere.

A pure-Python recogniser would keep the project dependency-free. The group-voting
idea above comes close to one, since once the groups are labelled the page is
classified without Tesseract, but the labels must come from somewhere, and a
hand-built digit classifier would be a second project that this one would have to
maintain for the sake of one command. It remains possible for the labels to come
from elsewhere later.

Other OCR engines installable from pip (neural recognisers running on ONNX or a
deep learning framework) avoid a system program at the cost of a much larger
install. They were not measured here and are not excluded, which is a reason for
keeping the recogniser behind a small interface.

Whole-page OCR, sparse-text OCR and cell-by-cell OCR were tried and are described
above. Unanimity among renditions was the first design and is described there too;
the group votes replaced it.

Having the pinner choose among readings, or the sum check pick the reading that
adds up, would give much higher acceptance and is the one alternative that is ruled
out on principle, not on performance. It would make the conformance check
unfalsifiable.

Retyping charts by hand remains the fallback, and the review file is how the tool
degrades into it: the part of a chart that could not be read is the part that is
left to type, with the rest filled in.

## Plan

One pull request per step, each ready for review once CI is green.

| Step | What | Behaviour change |
| --- | --- | --- |
| 1 | The data-file guard learns PDFs and images (done, D32) | Guard only |
| 2 | This document and its log entry, agreed before any code | None |
| 3 | The tool: `sfic-scan-charts` and `scan_charts.py`, in these commits: the `scan` extra and page loading (PDF and images) with the missing-dependency message and the pointer from D2 to the exception; cleaning, deskew, lines and tokens; the Tesseract wrapper and character-level reading; shape groups and voting; chart assembly, the checks and the writers; the command line | New command, optional dependencies |
| 4 | The synthetic-image harness, and CI installing Tesseract and the extra | Tests only |
| 5 | README ("scanning paper charts", and its "dependency-free" wording with the one stated exception), CLAUDE.md's "standard library only" likewise, the pointer from D2, the log and TODO.md | Documentation |

The package would hold the tool as `sfic_solver/scan_charts.py` with the command
line, and the stages in a subpackage, `sfic_solver/scanning/`, so that the optional
imports are in one place and the core stays importable without them. The test
helpers that render fake charts to images live with the tests.

## Decisions from review

Review settled the questions that this document first left open.

The exception to D2 is a decision, and it is the biggest one here: for this one
feature the project stops being standard-library-only, with an optional `scan` extra
(Pillow, numpy and pypdfium2) and Tesseract as a program found at run time. The
maintainer approved the optional extra, the choice of pypdfium2 and the local
Tesseract at the outset, and accepting this document accepts the exception, on the
terms in "An exception to D2, and its limits". The README and CLAUDE.md say
"standard library only" or "dependency-free" without qualification today, so when
the tool lands they say it with this one stated exception.

Pages carry handwritten notes in the margin, and charts are matched to cores by
position: see "What the printouts look like" and "What the tool writes". No
annotated copy of the page is written: the report names page, chart, row and
chamber and the owner finds the cell on the paper, since an annotated copy is one
more image of key data in a place nobody chose; an explicit opt-in option can be
added later if review proves slow. The tool does not run the conformance check on
its own output, so the two stages (what the paper says, and whether the pinner
agrees) stay visibly separate, and the README shows both commands. Phone formats
(HEIC) and photographs in general are left out of the first version; the guard
still refuses them, and a later version can add an optional package and
perspective correction.

The thresholds start strict. How many renditions to run per row, and the group size
and purity below which a group is flagged, begin at values that flag too much
rather than too little, and are relaxed only as far as the harness shows that no
wrong chart is ever accepted. The values themselves are settled while building.

## What cannot be known yet

How closely the real printouts match the assumptions here can only be learned by
running the tool on them. The font may be proportional or have a slashed zero, the
digits may touch, the header labels may be spelt differently from the table in
`charts.py`, a long `Change Keys` line may wrap onto a second line, a page may hold
more than one chart, and a page may carry a title, a date or a page number. Each is
handled by flagging today, and none is a design driver unless the first real run
shows it to be one; it is then decided from a report of positions only, and the
design is revised.
