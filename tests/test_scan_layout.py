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
        assert layout.find_equals(line, found.glyph_height) in (1, 2)
    for row in found.lines[4:]:
        assert layout.find_equals(row, found.glyph_height) is None
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


def rows_are_clean(found, truth):
    rows = found.lines[4:]
    return len(rows) == len(truth["rows"]) and all(
        len(line.tokens) == 1 + len(cells) for line, (_, cells) in zip(rows, truth["rows"]))


def test_a_stroke_close_to_the_block_is_removed_and_reported_like_one_in_the_margin():
    lines, truth = chart()
    image = render(lines)
    width = image.size[0]
    add_strokes(image, [(int(width * 0.5), 330, int(width * 0.5) + 60, 700)])
    found = analyse(image)
    assert found.outside and rows_are_clean(found, truth)


def test_small_marks_beside_a_row_stay_in_the_block_and_spoil_it():
    lines, truth = chart()
    image = render(lines)
    width = image.size[0]
    # Short ticks level with the rows, a little to the right of the last column: too
    # small to be a pen stroke, so they are not removed, and they are extra tokens.
    boxes = [(int(width * 0.5), y, int(width * 0.5) + 12, y + 12) for y in (480, 540, 600)]
    add_strokes(image, boxes, count=1)
    found = analyse(image)
    assert not rows_are_clean(found, truth)


def test_a_stroke_across_the_print_takes_the_print_it_touches_with_it():
    from PIL import ImageDraw
    lines, truth = chart()
    image = render(lines)
    row = analyse(image).lines[5]                                   # a row of cells
    first, last = row.tokens[2], row.tokens[5]
    middle = (row.y0 + row.y1) // 2
    ImageDraw.Draw(image).line((first.x0 - 5, middle - 20, last.x1 + 5, middle + 20),
                               fill=0, width=5)                      # scrawled across it
    found = analyse(image)
    assert found.outside and not rows_are_clean(found, truth)


def test_a_page_with_text_too_small_to_read_is_marked_so():
    lines, _ = chart()
    assert analyse(render(lines, dpi=100, pt=6)).too_small
    assert not analyse(render(lines)).too_small


def test_the_gap_threshold_comes_from_the_page_not_a_constant():
    lines, _ = chart()
    small = analyse(render(lines, pt=9))
    large = analyse(render(lines, pt=14))
    assert large.gap > small.gap > 0


def flood(mask):
    """A plain 8-connected flood fill, as the reference for `layout.components`."""
    import numpy as np
    seen = np.zeros(mask.shape, bool)
    found = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        stack, cells = [(y, x)], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            cells.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] \
                            and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        found.append(frozenset(cells))
    return found


@pytest.mark.parametrize("seed, density", [(1, 0.15), (2, 0.35), (3, 0.5)])
def test_components_match_a_plain_flood_fill(seed, density):
    import numpy as np
    rng = np.random.default_rng(seed)
    mask = rng.random((40, 60)) < density
    got = layout.components(mask)
    ours = sorted(sorted((y, x) for y, a, b in runs for x in range(a, b))
                  for *_, runs in got)
    assert ours == sorted(sorted(cells) for cells in flood(mask))
    for x0, y0, x1, y1, pixels, runs in got:
        cells = {(y, x) for y, a, b in runs for x in range(a, b)}
        assert pixels == len(cells)
        assert x0 == min(x for _, x in cells) and x1 == max(x for _, x in cells) + 1
        assert y0 == min(y for y, _ in cells) and y1 == max(y for y, _ in cells) + 1


def test_a_component_far_larger_than_a_character_is_removed_and_reported():
    import numpy as np
    mask = np.zeros((200, 300), bool)
    for x in range(10, 280, 20):
        mask[100:112, x:x + 8] = True                   # a row of small marks
    mask[10:190, 5:9] = True                            # one long vertical stroke
    cleaned, removed = layout.remove_large(mask)
    assert removed == [(5, 10, 9, 190)]
    assert not cleaned[:, 5:9].any()                    # the stroke is gone
    assert cleaned[100:112, 10:280].sum() == mask[100:112, 10:280].sum()   # the marks stay


def test_a_ruled_line_is_not_print_either():
    import numpy as np
    mask = np.zeros((100, 400), bool)
    for x in range(10, 380, 20):
        mask[40:52, x:x + 8] = True
    mask[70:73, 5:395] = True                           # a line drawn under the text
    cleaned, removed = layout.remove_large(mask)
    assert len(removed) == 1 and not cleaned[70:73].any()


def test_finding_components_on_a_whole_page_takes_a_moment_not_minutes():
    import time
    lines, _ = chart()
    prepared = clean.prepare(render(lines))
    start = time.time()
    layout.components(prepared.mask)
    assert time.time() - start < 20


@pytest.mark.parametrize("font", ["liberation", "dejavu", "freemono"])
@pytest.mark.parametrize("seed", [6, 7, 9])
def test_commas_are_found_in_every_font(font, seed):
    from scan_helpers import font_path
    if font_path(font) is None:
        pytest.skip(f"no {font} font")
    lines, truth = chart(seed)
    found = analyse(render(lines, font=font))
    change = found.lines[3]
    after = change.tokens[layout.find_equals(change, found.glyph_height) + 1:]
    commas = [g for t in after for g in t.glyphs if g.kind == layout.DOT]
    digits = [g for t in after for g in t.glyphs if g.kind == layout.MARK]
    assert len(commas) == len(truth["change"]) - 1
    assert len(digits) == sum(len(k) for k in truth["change"])
