"""Reading marks with Tesseract: crops over stdin, renditions, labels."""
import io
import random

import pytest

pytest.importorskip("PIL")
pytest.importorskip("numpy")

from PIL import Image  # noqa: E402

from scan_helpers import have_tesseract, need_fonts, random_chart, render  # noqa: E402
from sfic_solver.scanning import MissingDependency, clean, layout, ocr  # noqa: E402

needs_tesseract = pytest.mark.skipif(not have_tesseract(), reason="Tesseract is not installed")


def test_agreed_wants_two_readings_that_say_the_same_thing():
    assert ocr.agreed(["Control", "control ", "CONTROL"]) == "control"
    assert ocr.agreed(["Master", "", "master"]) == "master"
    assert ocr.agreed(["Master", "", ""]) is None            # only one reading
    assert ocr.agreed(["Master", "Muster"]) is None          # they differ
    assert ocr.agreed(["T/D", "T /D"]) is None               # spacing is not forgiven
    assert ocr.agreed([]) is None


def test_a_crop_is_scaled_padded_and_painted_over_where_asked():
    import numpy as np
    page = np.full((100, 200), 255, np.float32)
    page[20:60, 30:90] = 0                                   # a black block
    png = ocr.crop_png(page, (20, 10, 120, 70), height=40, scale=20,
                       blank=[(30, 20, 89, 59)])
    image = Image.open(io.BytesIO(png))
    assert image.size == (50 + 2 * ocr.PAD, 30 + 2 * ocr.PAD)
    assert np.asarray(image).min() == 255                    # the block was blanked


def test_a_program_that_fails_gives_none_not_an_error(tmp_path):
    fake = tmp_path / "tesseract"
    fake.write_text("#!/bin/sh\nexit 1\n")
    fake.chmod(0o755)
    recogniser = ocr.Recogniser(str(fake), jobs=1)
    assert recogniser.read_all([(b"x", "0123456789", True)]) == [None]
    recogniser.close()


def test_a_missing_program_is_a_missing_dependency(tmp_path):
    with pytest.raises(MissingDependency):
        ocr.Recogniser(str(tmp_path / "none"))


@pytest.fixture(scope="module")
def recogniser():
    if not have_tesseract():
        pytest.skip("Tesseract is not installed")
    reader = ocr.Recogniser(jobs=2)
    yield reader
    reader.close()


@pytest.fixture(scope="module")
def page():
    """A clean fake chart, prepared, with its layout and truth."""
    lines, truth = random_chart(random.Random(11))
    prepared = clean.prepare(render(lines))
    return prepared, layout.analyse(prepared), truth, ocr.source_arrays(prepared)


def digit_row(page, index):
    prepared, found, truth, arrays = page
    line = found.lines[4 + index]
    cells = line.tokens[1:]
    glyphs = [g for t in cells for g in t.glyphs if g.kind == layout.MARK]
    blank = [(g.x0, g.y0, g.x1, g.y1) for t in cells for g in t.glyphs if g.kind != layout.MARK]
    box = (cells[0].x0 - 12, line.y0 - 10, cells[-1].x1 + 12, line.y1 + 10)
    wanted = "".join(c for c in truth["rows"][index][1] if c != "--")
    return box, found.glyph_height, blank, len(glyphs), wanted


pytestmark = need_fonts()


@needs_tesseract
def test_a_row_of_digits_is_read_in_every_rendition(recogniser, page):
    box, height, blank, count, wanted = digit_row(page, 0)
    readings = ocr.read_marks(recogniser, page[3], box, height, blank)
    assert len(readings) == len(ocr.ROW_RENDITIONS)
    usable = ["".join(r) for r in readings if r is not None and len(r) == count]
    assert len(usable) >= 3
    assert usable.count(wanted) >= len(usable) // 2 + 1      # most usable readings agree


@needs_tesseract
def test_dashes_painted_out_leave_only_digits(recogniser, page):
    # The last row of the chart is `Bottom`, all digits; the master rows have dashes.
    index = next(i for i, (_, cells) in enumerate(page[2]["rows"]) if "--" in cells)
    box, height, blank, count, wanted = digit_row(page, index)
    assert blank                                              # there are dashes to blank
    readings = ocr.read_marks(recogniser, page[3], box, height, blank)
    assert any(r is not None and "".join(r) == wanted for r in readings)
    assert all("-" not in "".join(r) for r in readings if r)


@needs_tesseract
def test_the_whitelist_needs_a_space_or_a_row_merges_into_one_word(recogniser, page):
    box, height, blank, _, _ = digit_row(page, 0)
    png = ocr.crop_png(page[3]["g"], box, height, 36, blank)
    with_space = recogniser._run(png, ocr.DIGITS, False)
    without = recogniser._run(png, "0123456789", False)
    assert " " in with_space and " " not in without


@needs_tesseract
@pytest.mark.parametrize("index, text", [(0, "t/d"), (1, "control"), (-1, "bottom")])
def test_a_row_label_is_read(recogniser, page, index, text):
    prepared, found, truth, arrays = page
    line = found.lines[4 + index] if index >= 0 else found.lines[-1]
    label = line.tokens[0]
    box = (label.x0 - 8, line.y0 - 8, label.x1 + 8, line.y1 + 8)
    readings = ocr.read_text(recogniser, arrays, box, found.glyph_height)
    assert ocr.agreed(readings) == text


@needs_tesseract
def test_nothing_is_written_to_the_temporary_directory(monkeypatch, tmp_path, page):
    empty = tmp_path / "tmp"
    empty.mkdir()
    monkeypatch.setenv("TMPDIR", str(empty))
    reader = ocr.Recogniser(jobs=2)
    try:
        box, height, blank, _, _ = digit_row(page, 0)
        ocr.read_marks(reader, page[3], box, height, blank)
        ocr.read_text(reader, page[3], box, height)
    finally:
        reader.close()
    assert list(empty.iterdir()) == []


@needs_tesseract
def test_a_mark_pasted_after_a_row_is_read_and_dropped(recogniser, page):
    box, height, blank, count, wanted = digit_row(page, 0)
    prepared, found, truth, arrays = page
    line = found.lines[4]
    first = next(t for t in line.tokens[1:] if t.kind == layout.MARK)
    tail = (first.x0, line.y0, first.x1, line.y1)
    marks = sum(1 for g in first.glyphs if g.kind == layout.MARK)
    readings = ocr.read_marks(recogniser, arrays, box, height, blank, tail=tail,
                              tail_marks=marks)
    usable = ["".join(r) for r in readings if r is not None and len(r) == count]
    assert len(usable) >= 3 and usable.count(wanted) >= len(usable) // 2 + 1


@needs_tesseract
def test_the_last_digit_of_a_row_is_read_more_reliably_with_something_after_it(recogniser):
    # Tesseract misreads the last character of a line (a final 3 as 8, a final 0 as 9
    # or nothing). Over the rows of a few charts the sentinel makes the last digit right
    # at least as often, and the rows where it matters, much more often.
    plain_right = tail_right = rows = 0
    for seed in (1, 2, 3):
        lines, truth = random_chart(random.Random(seed))
        prepared = clean.prepare(render(lines))
        found = layout.analyse(prepared)
        arrays = ocr.source_arrays(prepared)
        for index, (_, cells) in enumerate(truth["rows"]):
            line = found.lines[4 + index]
            tokens = line.tokens[1:]
            digits = [g for t in tokens for g in t.glyphs if g.kind == layout.MARK]
            blank = [(g.x0, g.y0, g.x1, g.y1) for t in tokens for g in t.glyphs
                     if g.kind != layout.MARK]
            height = found.glyph_height
            box = (tokens[0].x0 - int(.4 * height), line.y0 - int(.4 * height),
                   tokens[-1].x1 + int(.4 * height), line.y1 + int(.4 * height))
            first = next(t for t in tokens if t.kind == layout.MARK)
            tail = (first.x0, line.y0, first.x1, line.y1)
            marks = sum(1 for g in first.glyphs if g.kind == layout.MARK)
            last = [c for c in cells if c != "--"][-1][-1]

            def right(readings):
                return sum(1 for r in readings
                           if r is not None and len(r) == len(digits) and r[-1] == last)
            plain_right += right(ocr.read_marks(recogniser, arrays, box, height, blank))
            tail_right += right(ocr.read_marks(recogniser, arrays, box, height, blank,
                                               tail=tail, tail_marks=marks))
            rows += 1
    assert tail_right >= plain_right
    assert tail_right >= 0.7 * rows * len(ocr.ROW_RENDITIONS)

