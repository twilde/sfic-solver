"""The synthetic-image harness for the chart scanner (D38, step 4).

Fake charts, computed by the pinner from random fake bittings, are drawn to images at
run time with a controlled amount of damage and read by the real pipeline. Each chart
ends up in one of three places: accepted and right, flagged (failed or in review), or
accepted and WRONG, which must never happen. Nothing is written to disk and no image
is kept. Used by test_scan_harness.py.
"""
import random
from dataclasses import dataclass, field

from scan_helpers import add_strokes, random_chart, render
from sfic_solver import charts
from sfic_solver.scanning import assemble, clean, layout, ocr, pipeline
from sfic_solver.scanning.pages import Page

DOCUMENT = 6          # charts read together, so that their votes are pooled (as a run is)

# The conditions the documented range of image quality is made of: name -> render
# keywords. Fonts are named in `fonts` below, not here, so a condition is about the
# image and not about which fonts a machine has.
CONDITIONS = {
    "clean": {},
    "200 dpi": {"dpi": 200},
    "9 point": {"pt": 9},
    "skewed by 3 degrees": {"skew": 3.0},
    "blurred": {"blur": 1.5},
    "uneven lighting": {"shade": 0.4},
    "ink at half strength": {"contrast": 0.5},
    "speckle on 3% of pixels": {"speckle": 0.03},
    "gaussian noise, sigma 15": {"noise": 15},
    "gaussian noise, sigma 35": {"noise": 35},
}


@dataclass
class Outcome:
    accepted: int = 0          # accepted and right
    flagged: int = 0           # failed or in review
    wrong: int = 0             # accepted and different from the chart drawn: never
    wrong_pages: list = field(default_factory=list)

    @property
    def total(self):
        return self.accepted + self.flagged + self.wrong

    def add(self, other):
        self.accepted += other.accepted
        self.flagged += other.flagged
        self.wrong += other.wrong
        self.wrong_pages += other.wrong_pages
        return self

    def row(self, name):
        return f"| {name} | {self.accepted} | {self.flagged} | {self.wrong} |"


def reads_as_drawn(chart, truth):
    """Whether the text of a chart holds exactly what was drawn."""
    try:
        [parsed] = charts.parse_charts(chart.text)
    except (charts.ChartError, ValueError):
        return False
    rows = [(label, [None if c is None else str(c) for c in cells])
            for label, cells in parsed.rows]
    want = [(label.lower(), [None if c == "--" else c for c in cells])
            for label, cells in truth["rows"]]
    keys = [bitting for _, bitting in parsed.keys]
    return (rows == want and parsed.control == truth["control"]
            and keys == [truth["master"], *truth["change"]])


def judge(result, truths):
    """Classify every chart a scan found against the truth about its page.

    `truths` maps a page number to the truth about the chart drawn there. A page with
    no chart found counts as flagged, and so does a page with more than one.
    """
    outcome = Outcome()
    for page, truth in truths.items():
        found = [c for c in result.charts if c.page == page]
        if len(found) != 1 or found[0].status != assemble.ACCEPTED:
            outcome.flagged += 1
        elif reads_as_drawn(found[0], truth):
            outcome.accepted += 1
        else:
            outcome.wrong += 1
            outcome.wrong_pages.append(page)
    return outcome


def scan_images(images, jobs=4):
    """Read PIL images as the pages of one run (page numbers from 1)."""
    pages = [Page(1, number, image) for number, image in enumerate(images, 1)]
    recogniser = ocr.Recogniser(jobs=jobs)
    try:
        return pipeline.scan(pages, recogniser)
    finally:
        recogniser.close()


def run_condition(count, seed, font=None, damage=None, **kwargs):
    """Draw `count` random charts with the given image damage, read them in runs of
    DOCUMENT charts and return the Outcome.

    `damage(image, truth, rng)` may change an image after it is drawn and return it.
    """
    rng = random.Random(seed)
    total = Outcome()
    remaining = count
    while remaining > 0:
        images, truths = [], {}
        for _ in range(min(DOCUMENT, remaining)):
            lines, truth = random_chart(rng)
            image = render(lines, font=font, seed=rng.randrange(1 << 30), **kwargs)
            if damage:
                image = damage(image, truth, rng)
            images.append(image)
            truths[len(images)] = truth
        total.add(judge(scan_images(images), truths))
        remaining -= len(images)
    return total


# Damage done to an image after it is drawn: each takes (image, truth, rng) and returns
# the image. The places are found by reading the undamaged page with the scanner's own
# layout stage, which needs no OCR.

def row_lines(image, truth):
    """The text lines that are the rows of the chart, and the layout they came from."""
    found = layout.analyse(clean.prepare(image))
    return found.lines[-len(truth["rows"]):]


def erase_cell(image, truth, rng):
    from PIL import ImageDraw
    line = rng.choice(row_lines(image, truth))
    token = rng.choice(line.tokens[1:])
    ImageDraw.Draw(image).rectangle(
        (token.x0 - 3, line.y0 - 3, token.x1 + 3, line.y1 + 3), fill=255)
    return image


def ink_over_cell(image, truth, rng):
    line = rng.choice(row_lines(image, truth))
    token = rng.choice(line.tokens[1:])
    image = image.copy()                 # a page made from an array is read-only
    pixels = image.load()
    for x in range(token.x0 - 3, token.x1 + 3):
        for y in range(line.y0 - 2, line.y1 + 2):
            pixels[x, y] = 0 if rng.random() < 0.55 else 255
    return image


def erase_row(image, truth, rng):
    from PIL import ImageDraw
    line = rng.choice(row_lines(image, truth))
    ImageDraw.Draw(image).rectangle((0, line.y0 - 2, image.width, line.y1 + 2), fill=255)
    return image


def strokes_in_the_margin(image, truth, rng):
    """Notes in the left margin, clear of the printed block."""
    found = layout.analyse(clean.prepare(image))
    return add_strokes(image, [(40, found.lines[0].y0, 200, found.lines[-1].y1)],
                       seed=rng.randrange(1 << 30))


def strokes_beside_a_row(image, truth, rng):
    """A note written just after the last column of a row, touching the printed block."""
    line = rng.choice(row_lines(image, truth))
    return add_strokes(image, [(line.tokens[-1].x1 + 15, line.y0 - 5,
                                line.tokens[-1].x1 + 150, line.y1 + 5)],
                       seed=rng.randrange(1 << 30), count=3)
