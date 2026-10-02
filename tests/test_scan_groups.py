"""Grouping marks by shape and labelling the groups by vote (no Tesseract needed:
the readings here are simulated, so that each failure can be made to order)."""
import pytest

pytest.importorskip("PIL")
pytest.importorskip("numpy")

from scan_helpers import need_fonts, render  # noqa: E402
from sfic_solver.scanning import clean, groups, layout  # noqa: E402

pytestmark = need_fonts("liberation")

ROWS = ["0123456789 3 8 1 0", "9876543210 5 5 2 7", "1357902468 4 6 1 1",
        "2468013579 0 9 3 8", "5050505050 6 4 2 2", "7171717171 9 9 8 3"]


@pytest.fixture(scope="module")
def digits():
    """(mask, [(row of glyphs, the digits they are)]) for a page of known digits."""
    prepared = clean.prepare(render(ROWS))
    found = layout.analyse(prepared)
    rows = []
    for line, text in zip(found.lines, ROWS):
        glyphs = [g for t in line.tokens for g in t.glyphs]
        want = [c for c in text if c != " "]
        assert len(glyphs) == len(want)
        rows.append((glyphs, want))
    return prepared.mask, rows


def run(digits, readings_for, copies=1):
    """Add every mark, vote with simulated readings, resolve. Returns (marks, truth)."""
    mask, rows = digits
    marks, truth, ids = groups.Marks(), [], []
    for _ in range(copies):
        for glyphs, want in rows:
            row = [marks.add(mask, g) for g in glyphs]
            ids.append((row, want))
            truth.extend(want)
    for row, want in ids:
        marks.vote(row, readings_for(row, want))
    return marks.resolve(), truth, marks


def perfect(row, want):
    return [list(want)] * 6


def test_marks_of_a_shape_form_one_group_and_read_as_its_label(digits):
    resolved, truth, marks = run(digits, perfect)
    assert [m.value for m in resolved] == truth
    assert len(marks.counts) == 10 and all(m.reason is None for m in resolved)


def test_a_single_misreading_is_outvoted_by_its_group(digits):
    def one_wrong(row, want):
        readings = [list(want) for _ in range(6)]
        readings[0][2] = "7" if want[2] != "7" else "1"       # one rendition errs
        return readings
    resolved, truth, _ = run(digits, one_wrong)
    assert [m.value for m in resolved] == truth


def test_readings_with_the_wrong_number_of_characters_are_not_counted(digits):
    mask, rows = digits
    marks = groups.Marks()
    row = [marks.add(mask, g) for g in rows[0][0]]
    short = list(rows[0][1])[:-1]
    assert marks.vote(row, [short, None, list(rows[0][1] + ["1"])]) == 0


def test_a_confusion_by_glyph_gives_two_groups_one_label_and_both_are_flagged(digits):
    # Tesseract "reads every 3 as an 8": the 3s are a pure group labelled 8, and the
    # real 8s are another group labelled 8.
    def threes_as_eights(row, want):
        return [["8" if c == "3" else c for c in want]] * 6
    resolved, truth, marks = run(digits, threes_as_eights, copies=3)
    flagged = {t for m, t in zip(resolved, truth) if m.reason == groups.DUPLICATE}
    assert flagged == {"3", "8"}
    assert all(m.value is None for m, t in zip(resolved, truth) if t in "38")
    assert all(m.value == t for m, t in zip(resolved, truth) if t not in "38")


def test_a_group_with_too_few_marks_does_not_vote(digits):
    mask, rows = digits
    marks = groups.Marks()
    row = [marks.add(mask, g) for g in rows[0][0]]            # each digit once
    marks.vote(row, [list(rows[0][1])] * 6)
    resolved = marks.resolve()
    assert all(m.reason == groups.TOO_SMALL for m in resolved)
    assert marks.small_groups() == len(row)


def test_a_group_whose_votes_split_is_impure(digits):
    def split(row, want):
        return [list(want)] * 3 + [["8" if c == "3" else c for c in want]] * 3
    resolved, truth, _ = run(digits, split, copies=3)
    assert {t for m, t in zip(resolved, truth) if m.reason == groups.IMPURE} == {"3"}


def test_a_group_nobody_read_is_unvoted(digits):
    resolved, _, _ = run(digits, lambda row, want: [None] * 6, copies=2)
    assert all(m.reason == groups.UNVOTED for m in resolved)


def test_a_mark_whose_own_readings_name_another_digit_is_flagged(digits):
    # One mark (the 5 in the second row) is read as 1 in every rendition; its group is
    # still overwhelmingly labelled 5, so it is that single mark that is flagged.
    def one_mark_disagrees(row, want):
        readings = [list(want) for _ in range(6)]
        if want[:3] == ["9", "8", "7"]:
            for reading in readings:
                reading[4] = "1"
        return readings
    resolved, truth, _ = run(digits, one_mark_disagrees, copies=4)
    flagged = [(m, t) for m, t in zip(resolved, truth) if m.reason == groups.DISSENT]
    assert len(flagged) == 4 and {t for _, t in flagged} == {"5"}      # once per copy
    assert all(m.value == t for m, t in zip(resolved, truth) if m.reason is None)


def test_a_different_shape_is_not_pulled_into_a_group_by_a_similar_vote(digits):
    # Every mark votes for its true digit, but a "1" read as "7" by all its renditions
    # is one group labelled 7 next to the real 7s: two groups, one label.
    def ones_as_sevens(row, want):
        return [["7" if c == "1" else c for c in want]] * 6
    resolved, truth, _ = run(digits, ones_as_sevens, copies=3)
    assert {t for m, t in zip(resolved, truth) if m.reason == groups.DUPLICATE} == {"1", "7"}
