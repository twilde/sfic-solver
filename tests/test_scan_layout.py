"""Cleaning a page and finding its lines, tokens and glyphs."""
import random

import pytest

pytest.importorskip("PIL")
pytest.importorskip("numpy")

from PIL import Image  # noqa: E402

from scan_helpers import add_strokes, need_fonts, random_chart, render  # noqa: E402
from sfic_solver.scanning import clean, layout  # noqa: E402

pytestmark = need_fonts("liberation")


def chart(seed=3):
    return random_chart(random.Random(seed))


def analyse(image):
    return layout.analyse(clean.prepare(image))


def test_a_white_page_is_blank():
    prepared = clean.prepare(Image.new("L", (800, 1000), 255))
    assert prepared.blank and layout.analyse(prepared) is None


def test_a_faint_smudge_is_not_a_chart_but_a_page_with_text_is_not_blank():
    smudge = Image.new("L", (800, 1000), 250)       # paper with no ink on it
    assert clean.prepare(smudge).blank
    lines, _ = chart()
    assert not clean.prepare(render(lines)).blank


@pytest.mark.parametrize("skew", [2.0, -1.5, 3.5])
def test_skew_is_found_and_undone(skew):
    lines, _ = chart()
    prepared = clean.prepare(render(lines, skew=skew))
    assert abs(prepared.angle + skew) < 0.5
    found = layout.analyse(prepared)
    assert len(found.lines) == len(lines) - 1        # the blank line is not a line


def test_uneven_lighting_does_not_matter():
    lines, _ = chart()
    found = analyse(render(lines, shade=0.4))
    assert len(found.lines) == len(lines) - 1


def test_every_row_has_a_label_and_one_token_per_chamber():
    lines, truth = chart()
    found = analyse(render(lines))
    rows = found.lines[4:]
    assert len(rows) == len(truth["rows"])
    for line, (_, cells) in zip(rows, truth["rows"]):
        assert len(line.tokens) == 1 + len(cells)
    assert found.outside == []


def chart_with(predicate):
    """A random chart whose cells satisfy `predicate(all cells)`."""
    for seed in range(200):
        lines, truth = chart(seed)
        if predicate([c for _, cells in truth["rows"] for c in cells]):
            return lines, truth
    raise AssertionError("no such chart")


def test_dashes_are_found_by_shape_and_digits_by_their_marks():
    lines, truth = chart_with(lambda cells: "--" in cells and any(len(c) == 2 for c in cells))
    found = analyse(render(lines))
    checked = {"dash": 0, "two": 0}
    for line, (_, cells) in zip(found.lines[4:], truth["rows"]):
        for token, cell in zip(line.tokens[1:], cells):
            if cell == "--":
                assert token.kind == layout.DASH and len(token.glyphs) == 2
                checked["dash"] += 1
            else:
                assert token.kind == layout.MARK and len(token.glyphs) == len(cell)
                checked["two"] += len(cell) == 2
    assert checked["dash"] and checked["two"]


def test_a_header_line_has_its_equals_sign_and_the_commas_inside_a_token():
    lines, truth = chart(seed=7)
    found = analyse(render(lines))
    system, control, master, change = found.lines[:4]
    for line in (system, control, master, change):
        assert [t.kind for t in line.tokens].count(layout.EQUALS) == 1
    assert len(control.tokens) == 4 and len(change.tokens) == 3 + len(truth["change"])
    commas = [g for t in change.tokens for g in t.glyphs if g.kind == layout.DOT]
    assert len(commas) == len(truth["change"]) - 1


def test_ink_far_from_the_block_is_split_off_and_reported():
    lines, truth = chart()
    image = render(lines)
    # Strokes in the left margin, level with the rows and well clear of the text.
    add_strokes(image, [(60, 330, 200, 700)])
    found = analyse(image)
    assert len(found.outside) >= 1
    assert len(found.lines) == len(lines) - 1
    for line, (_, cells) in zip(found.lines[4:], truth["rows"]):
        assert len(line.tokens) == 1 + len(cells)


def test_ink_close_to_the_block_stays_in_it_to_fail_the_checks_later():
    lines, truth = chart()
    image = render(lines)
    width = image.size[0]
    add_strokes(image, [(int(width * 0.5), 330, int(width * 0.5) + 60, 700)])
    found = analyse(image)
    rows = found.lines[4:]
    clean_rows = len(rows) == len(truth["rows"]) and all(
        len(line.tokens) == 1 + len(cells) for line, (_, cells) in zip(rows, truth["rows"]))
    assert not clean_rows          # the strokes are part of the block, so the rows are wrong


def test_a_page_with_text_too_small_to_read_is_marked_so():
    lines, _ = chart()
    assert analyse(render(lines, dpi=100, pt=6)).too_small
    assert not analyse(render(lines)).too_small


def test_the_gap_threshold_comes_from_the_page_not_a_constant():
    lines, _ = chart()
    small = analyse(render(lines, pt=9))
    large = analyse(render(lines, pt=14))
    assert large.gap > small.gap > 0
