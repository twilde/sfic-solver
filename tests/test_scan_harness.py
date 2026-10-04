"""The scanner on many random fake charts drawn with controlled damage (D38, step 4).

Every chart is computed by the pinner from random fake bittings and drawn to an image
here, at run time; nothing is written to disk except the PDF the PDF test makes in
its own temporary directory, and no image is committed. Two assertions matter. No
chart is ever accepted and different from the one drawn, in any condition, and
within the range of image quality the README documents, most charts are accepted.

There are two tiers. The one that always runs is a small deterministic sample per
condition (seeded, so a failure repeats), sized for CI. The slow tier, run with
`pytest --runslow tests/test_scan_harness.py -s`, reads 1,000 charts per condition
and is the one that supports a claim: zero wrong in 1,000 charts bounds the true rate
below 0.3% at 95% confidence (three in n). Run it, and report its table, before the
documented range changes. The number per condition is `SFIC_HARNESS_CHARTS` for the
slow tier (default 1000); the always-on tier ignores it.
"""
import os
import random

import pytest

pytest.importorskip("PIL")
pytest.importorskip("numpy")

import scan_harness as harness  # noqa: E402
from scan_helpers import (OCR_FONTS, default_font, font_path, have_tesseract,  # noqa: E402
                          need_fonts, need_ocr_font, random_chart, render)
from sfic_solver.scanning import pages as scan_pages  # noqa: E402

pytestmark = [pytest.mark.skipif(not have_tesseract(), reason="Tesseract is not installed"),
              need_fonts(), need_ocr_font]

SAMPLE = 3              # charts per condition in the always-on tier (about 6 s each)

# At least this many of the SAMPLE charts are accepted (the matrix in the design
# document had 10 to 12 of 12 accepted in every condition). These are floors from the
# measured runs (see the design document), not targets: a condition that flags more
# than this has got worse, and one that flags fewer is not a reason to raise the floor.
MIN_ACCEPTED = {name: 2 for name in harness.CONDITIONS}


def seed_of(name):
    return sum(map(ord, name))


@pytest.mark.parametrize("name", harness.CONDITIONS)
def test_in_every_condition_no_wrong_chart_is_accepted_and_most_are_accepted(name):
    outcome = harness.run_condition(SAMPLE, seed_of(name), **harness.CONDITIONS[name])
    assert outcome.wrong == 0, outcome.wrong_pages
    assert outcome.accepted >= MIN_ACCEPTED[name], outcome


@pytest.mark.parametrize("font", OCR_FONTS)
def test_every_good_font_is_read_without_a_wrong_chart(font):
    if font_path(font) is None:
        pytest.skip(f"no {font} font")
    if font == default_font():
        pytest.skip("the clean condition already draws with this font")
    outcome = harness.run_condition(SAMPLE, seed_of(font), font=font)
    assert outcome.wrong == 0, outcome.wrong_pages
    assert outcome.accepted >= MIN_ACCEPTED["clean"], outcome


@pytest.mark.parametrize("font", ["courier", "menlo"])
def test_the_thin_comma_fonts_are_flagged_and_never_wrong(font):
    # Issue #10: commas are often not found in these fonts, so many charts go to
    # review. That is the intended direction; only a wrong accepted chart is a failure.
    if font_path(font) is None:
        pytest.skip(f"no {font} font")
    outcome = harness.run_condition(SAMPLE, seed_of(font), font=font)
    assert outcome.wrong == 0, outcome.wrong_pages


DAMAGE = {
    "one cell erased": harness.erase_cell,
    "one cell inked over": harness.ink_over_cell,
    "a row erased": harness.erase_row,
}


@pytest.mark.parametrize("name", DAMAGE)
def test_a_corrupted_chart_is_flagged_and_never_accepted(name):
    outcome = harness.run_condition(SAMPLE, seed_of(name), damage=DAMAGE[name])
    assert outcome.wrong == 0, outcome.wrong_pages
    assert outcome.accepted == 0, outcome        # nothing is lost from these pages


@pytest.mark.parametrize("name, kwargs", [
    ("rotated 9 degrees, past what is straightened", {"skew": 9.0}),
    ("100 dpi, too coarse to read", {"dpi": 100}),
])
def test_a_page_too_poor_to_read_is_flagged_and_never_wrong(name, kwargs):
    outcome = harness.run_condition(SAMPLE, seed_of(name), **kwargs)
    assert outcome.wrong == 0, outcome.wrong_pages


def test_notes_in_the_margin_clear_of_the_block_change_nothing():
    outcome = harness.run_condition(SAMPLE, 77, damage=harness.strokes_in_the_margin)
    assert outcome.wrong == 0, outcome.wrong_pages
    assert outcome.accepted >= MIN_ACCEPTED["clean"], outcome   # as without the notes


def test_notes_touching_a_row_are_flagged_or_ignored_and_never_make_a_wrong_chart():
    outcome = harness.run_condition(SAMPLE, 78, damage=harness.strokes_beside_a_row)
    assert outcome.wrong == 0, outcome.wrong_pages


def test_a_pdf_is_read_like_the_images_it_holds(tmp_path):
    rng = random.Random(5)
    images, truths = [], {}
    for number in range(1, SAMPLE + 1):
        lines, truth = random_chart(rng)
        images.append(render(lines, seed=number).convert("L"))
        truths[number] = truth
    path = tmp_path / "charts.pdf"
    images[0].save(path, "PDF", resolution=300, save_all=True, append_images=images[1:])
    sources = scan_pages.collect_sources([str(path)])
    result = harness.scan_images([page.image for page in scan_pages.iter_pages(sources)])
    outcome = harness.judge(result, truths)
    assert outcome.wrong == 0, outcome.wrong_pages
    assert outcome.accepted >= MIN_ACCEPTED["clean"], outcome


@pytest.mark.slow
@pytest.mark.parametrize("name", harness.CONDITIONS)
def test_full_run_one_condition(name):
    # Read here and not at import, so that a bad value spoils only this tier.
    count = int(os.environ.get("SFIC_HARNESS_CHARTS", "1000"))
    outcome = harness.run_condition(count, seed_of(name), **harness.CONDITIONS[name])
    print(f"\n{outcome.row(name)}   ({outcome.total} charts)")
    assert outcome.wrong == 0, outcome.wrong_pages
