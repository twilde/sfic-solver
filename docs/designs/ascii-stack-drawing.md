# An ASCII drawing of each core's pin stacks (core pinning, step 7a)

Status: Implemented

This document describes the first half of step 7 of [core pinning](core-pinning.md): an
optional drawing, in plain text, of the pin stacks of each core under the chart the
chart command already prints. It was written before any code, accepted by the
maintainer and built ([D61 in decisions.md](../decisions.md)). The other half of step 7,
one PDF of all the charts, is a separate design (7b, [pdf-output.md](pdf-output.md), D62),
because it needs a PDF writer; nothing here depends on it, and the drawing is built so that
it survives into a PDF unchanged.

## Why do this

A pinning chart is a table of numbers: for each chamber, the size of the driver, the
control pin, each master pin and the bottom pin. It is exact, and it is how a person
loading a core reads it, but it hides the thing that makes the numbers work. A
chamber's pins are a stack with joints between them, a key of a given cut puts one
joint on the shear line, and the whole design of a master-keyed core is the choice of
which joints line up for which cuts. Anyone checking a chart, or explaining to a
trustee or a new maintainer why two keys open one core, has to add the pins up in
their head.

A drawing to scale makes the arithmetic visible. Two keys that share a cut share a
joint, so their chamber has one pin fewer, and the drawing shows one joint where there
could have been two. A control pin that is far too long, or a driver that is barely
long enough, stands out as a tall or short block. And a mistake in a hand-loaded core,
a pin of the wrong size, is easier to spot against a picture than against a row of
numbers. None of that adds a rule or changes a number; it is a second view of the chart
the tools already print.

## What it shows

One column per chamber, drawn from the chart's own pins, with the driver at the top and
the bottom pin at the floor, so it reads the same way up as the chart. The height is to
scale, one line for each increment of the stack, so a pin of size 12 is twelve lines
tall and every chamber ends on the same top line, the stack total. Joints are drawn as
`+---+`, pin walls as `|   |`, and a pin's size is written on the middle line of the pin.

A ruler on the left gives the height of each line and, for the lines where a key can put
a joint on a shear line, which cut does it. The rule that gives the ruler is the same
one the pinner uses: a joint at height `h` from 0 to the deepest cut sits on the
operating shear line for a key whose cut is `h`, and a joint at `h` from the control
offset up sits on the control shear line for a control key whose cut is `h` minus the
control offset. In A2 that is operating cuts 0 to 9 on the lines 0 to 9, and control
cuts 0 to 9 on the lines 10 to 19. The ruler is computed from the pinning system's
numbers, so another system draws correctly when it is added.

Here is the first chart the command prints for the fake fixture
(`tests/fixtures/pinning.json`), with the drawing under it, as it is printed. It is
generated from the same chambers, not drawn by hand, and a test prints it verbatim.

```
Key System = Example building
System = A2
Core = Area A cores
Date = 2026-10-01
Control Key = 9743854
area_a = 5721276
master_sub = 7305496
master_top = 5961634

T/D      4  6  9 10  5  8  9
Control 12  8  8  8 12  6  8
Master  --  2  4 --  2  2 --
Master   2  4  2  4  2  4  2
Bottom   5  3  0  1  2  3  4

Stacks (to scale, one line per increment)

    cut      1     2     3     4     5     6     7
23         +---+ +---+ +---+ +---+ +---+ +---+ +---+
22         |   | |   | |   | |   | |   | |   | |   |
21         | 4 | |   | |   | |   | | 5 | |   | |   |
20         |   | | 6 | |   | |   | |   | |   | |   |
19  ctl 9  +---+ |   | | 9 | |   | |   | | 8 | | 9 |
18  ctl 8  |   | |   | |   | |10 | +---+ |   | |   |
17  ctl 7  |   | +---+ |   | |   | |   | |   | |   |
16  ctl 6  |   | |   | |   | |   | |   | |   | |   |
15  ctl 5  |   | |   | |   | |   | |   | +---+ |   |
14  ctl 4  |   | |   | +---+ |   | |   | |   | +---+
13  ctl 3  |12 | | 8 | |   | +---+ |   | |   | |   |
12  ctl 2  |   | |   | |   | |   | |12 | | 6 | |   |
11  ctl 1  |   | |   | |   | |   | |   | |   | |   |
10  ctl 0  |   | |   | | 8 | |   | |   | |   | | 8 |
 9  op  9  |   | +---+ |   | | 8 | |   | +---+ |   |
 8  op  8  |   | | 2 | |   | |   | |   | | 2 | |   |
 7  op  7  +---+ +---+ |   | |   | |   | +---+ |   |
 6  op  6  | 2 | |   | +---+ |   | +---+ |   | +---+
 5  op  5  +---+ | 4 | |   | +---+ | 2 | | 4 | | 2 |
 4  op  4  |   | |   | | 4 | |   | +---+ |   | +---+
 3  op  3  | 5 | +---+ |   | | 4 | | 2 | +---+ |   |
 2  op  2  |   | | 3 | +---+ |   | +---+ | 3 | | 4 |
 1  op  1  |   | |   | | 2 | +-1-+ | 2 | |   | |   |
 0  op  0  +---+ +---+ +-0-+ +---+ +---+ +---+ +---+

At a line marked op N, a joint is on the operating shear line for a key cut N.
At a line marked ctl N, a joint is on the control shear line for a control key cut N.
A number on a joint line is a bottom pin of 0 or 1, too short to hold its size.
```

To read it: in chamber 1 the joints are at heights 5 and 7, so the bottom pin is 5 and
the pin above it is 2, and a key cutting 5 or 7 there lines a joint up with the
operating line. The long block above is the control pin, 12, and the driver is 4. In
chamber 3 the lowest operating cut is 0, so there is no bottom pin: the floor is itself
a joint, and the zero is written on it.

Two details follow from the pin sizes A2 allows. Every pin is at least 2 except the
bottom pin, which may be 0 or 1. A pin of 2 or more has a line inside it for its size.
A bottom pin of 1 has none, and a bottom pin of 0 has no height at all, so those two
are written on the joint at the top of the bottom pin, as `+-1-+` and `+-0-+`. Only the
bottom pin can be numbered this way, so a number on a joint line cannot be confused with
anything else, and a third line under the drawing says so.

## Where it goes, and how it is asked for

The drawing is printed by `pin_system.py` only when asked, with `--draw`. Without the
flag the output is byte for byte what it is now, so nothing that reads or files today's
charts changes, which is the same promise the earlier steps made for files that do not
opt in. With the flag, each chart is followed by a blank line and the drawing, and the
separator line between charts is unchanged. A chart with its drawing is 46 lines and
85 columns at most, so it still fits a page, and the stacks themselves take 11 columns
for the ruler and 6 for each chamber (5 for the last), which is 52 for seven chambers and
82 for twelve.

Only plain ASCII is used (`+`, `-`, `|`, digits and letters), not box-drawing
characters. That keeps the output safe on any terminal, printer and file encoding, and
keeps it printable in the PDF's built-in monospaced font later with no font to embed.

Both `--out` and standard output work as they do now. A drawn chart is key data like
the chart it sits under, since its joints give the pin sizes away, so the reminder and
the guard stay as they are: nothing here writes a file the user did not name.

## The reader must skip it

`check_charts` and the loader in `charts.py` refuse any line after the rows that is not a
row, so a drawn chart would fail them, and the point of printing charts in the reader's
layout is that the reader can check them. The reader therefore skips a drawing: after
the rows, a line that starts with `Stacks` begins one, and the reader ignores every
line from there to the next separator or the end of the file. `Stacks` cannot be a key
name in the header (the header ends at the blank line before the rows), so nothing is
lost. The reader does not check the drawing against the table: it is a view, and a
hand-edited drawing is the owner's business. The tests do check it, below.

## How the drawing is tested

The point of a drawing is that it is right, so the tests do more than compare text.

- A test reads a drawing back, column by column: the joint lines give each chamber's
  joint heights, the differences give the pin sizes, and the numbers written in the pins
  and on the bottom joint must agree with them. It must return exactly the chamber the
  drawing came from, for every chart of the fixture, for chambers with a bottom pin of 0,
  1 and larger, and for several hundred random pinnable cores (the property tests for
  the pinner already generate them).
- The ruler is checked against the lock's own geometry (`lift` and `joint_on_line`): for
  each joint on a ruler line, a key with the cut the ruler names puts that joint on the
  operating or control line, in every chamber. That ties the drawing to the simulated
  lock, which is how the rules were verified in the first place.
- The fixture chart and drawing are printed verbatim, and without `--draw` the output
  is unchanged.
- The reader accepts every drawn chart and returns the same data as for the chart
  without its drawing, and `check_charts` finds the pinner agrees with each.
- Every line is ASCII, and no drawn line is longer than the ruler and chambers allow.

## Alternatives considered

**Always on.** The drawing would appear in every chart. It is less to remember, but it
changes the output of a command that already ships, lengthens every chart on paper, and
makes the reader's skipping rule mandatory instead of a convenience. Opt-in costs one
flag.

**A separate command or file.** A `--draw-only` output, or a second file, keeps the
chart pure. But the useful case is one page: the chart and its picture together, to be
filed or checked against the lock. A second file is a second piece of key data to keep
track of.

**Box-drawing characters.** The result looks better on a terminal, and it needs a
Unicode-aware printer and, in the PDF, an embedded font. Plain ASCII looks the same
everywhere, and the shapes are the same.

**Letters for the keys.** Marking each joint with the key whose cut it is (`a`, `b`,
`c`, with a legend) would say which key each joint serves. It crowds the bottom-pin
numbers, which already live on joint lines, and the header and the cut ruler already
carry the same information. It can be added later without changing anything above.

**A drawing per key, with the key inserted.** The picture of a key lifting its stack to
the shear line, and of a wrong key stopping short, is the visualizer the main design
mentions. It needs the lock's `lift` and `joint_on_line`, one picture per key and core,
and a way to choose which keys. That is a larger feature with its own design, and this
static drawing is the part of it that stands alone. It uses only the chart's chambers,
and leaves the lock to the tests.

**Drawing at half scale or one line per pin.** One line per pin is the chart again. Half
a line per increment loses the pin of size 1 and the odd heights. One line per increment
is the smallest picture that is to scale.

## Decision and plan

The drawing is added as described, opt-in, in one pull request (step 7a):

1. The reader skips a `Stacks` block after the rows, with tests (no behavior change for
   anything that does not print one).
2. The drawing itself, `draw_stacks` in `chartwriter.py`, with the read-back and ruler
   tests; and `--draw` in `pin_system.py`.
3. The README section on printing charts, the design text and TODO, with a decision
   entry.

The 7b design, a single PDF of all the charts, followed separately and is built. It prints
the same drawn text in a monospaced font, so the drawing is plain ASCII and its stacks are
52 columns wide for seven chambers (the longest legend line is 85).

Accepting this document meant accepting an optional drawing under each chart, the
`--draw` flag, the ruler convention above, and the reader skipping a `Stacks` block.
Nothing changes for output printed without the flag, and no scoring, solver or checker
behavior changes.

## What nobody can know yet

Whether the ruler wording and the three legend lines are clear on a real printed page can
only be settled by looking at the output; the wording is easy to change, and the
read-back test pins the geometry, not the words. A system with more chambers than will
fit a page's width is a matter of how the owner prints it; the drawing does not wrap.
