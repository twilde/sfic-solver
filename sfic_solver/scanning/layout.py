"""Finding lines, tokens and glyphs on a cleaned page.

A line is a run of ink rows; a token is a run of marks on a line with only narrow
gaps between them; a glyph is one mark. The width that separates a gap inside a
token from a gap between tokens comes from the page's own gaps, not from a constant,
because a dash is narrow and the gap inside `--` is nearly as wide as the gap
between two digits.

Ink that is not print is split off as `outside` and reported; it never reaches the
recogniser. A pen stroke is one connected blob much larger than a character, so any
component far larger than a glyph is removed first, wherever it is (handwriting
running down a margin, and with it anything it touches, which fails closed: the
chart is flagged for the cells that went missing). Small marks that remain are
placed by position: printed lines are flush left, so a token entirely left of that
edge is outside, and on the right the first gap wider than any gap inside a printed
line starts the margin. Small ink inside the block is left alone, and fails the
checks later if it does not belong.
"""
from dataclasses import dataclass, field

# A line must be at least this much of the typical line's height to be a line.
MIN_LINE_SHARE = 0.4
# To the right, a gap wider than this many glyph heights ends the printed block. The
# widest gap inside print is a row label's field (about 7.5 heights), so this is wider.
MARGIN_GAP_HEIGHTS = 9
# A token this close to the flush-left edge (in glyph heights) is still on it.
LEFT_SLACK = 0.5
# A connected component taller than this many typical component heights, or wider than
# WIDE_COMPONENT, is not a character (a pen stroke, a ruled line) and is removed.
TALL_COMPONENT = 2.5
WIDE_COMPONENT = 5.0
# Components smaller than this many pixels are specks and do not count towards the
# typical size.
MIN_COMPONENT_PIXELS = 12
# At least this many lines must share a left edge for there to be a flush-left edge.
MIN_ALIGNED_LINES = 3
# When looking for the gap that separates tokens, only gaps up to this many glyph
# heights are candidates, so that margin ink cannot move the threshold.
CANDIDATE_GAP_HEIGHTS = 4
# Below this glyph height (pixels) the page cannot be read reliably.
MIN_GLYPH_HEIGHT = 14

DASH, EQUALS, DOT, MARK = "dash", "equals", "dot", "mark"


@dataclass
class Glyph:
    x0: int
    x1: int
    y0: int
    y1: int
    kind: str = MARK

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.y1 - self.y0


@dataclass
class Token:
    glyphs: list

    @property
    def x0(self):
        return self.glyphs[0].x0

    @property
    def x1(self):
        return self.glyphs[-1].x1

    @property
    def y0(self):
        return min(g.y0 for g in self.glyphs)

    @property
    def y1(self):
        return max(g.y1 for g in self.glyphs)

    @property
    def kind(self):
        """DASH if every glyph is a dash, EQUALS for a lone equals sign, else MARK."""
        kinds = {g.kind for g in self.glyphs}
        if kinds == {DASH}:
            return DASH
        if kinds == {EQUALS}:
            return EQUALS
        return MARK


@dataclass
class Line:
    y0: int
    y1: int
    tokens: list = field(default_factory=list)


@dataclass
class Layout:
    lines: list
    glyph_height: float          # the typical height of a digit, in pixels
    gap: float                   # the width that separates tokens, in pixels
    too_small: bool              # the text is too small to read reliably
    outside: list = field(default_factory=list)    # (x0, y0, x1, y1) of ink outside the block
    mask: object = None          # the ink mask the lines were found in: large ink removed


def components(mask):
    """Connected components of ink (8-connected), found on run lengths without scipy:
    a list of (x0, y0, x1, y1, pixels, runs), the box exclusive at x1 and y1, with
    `runs` the (y, x0, x1) of each row's stretch of ink in the component."""
    import numpy as np

    padded = np.zeros((mask.shape[0], mask.shape[1] + 2), np.int8)
    padded[:, 1:-1] = mask
    change = np.diff(padded, axis=1)
    run_y, run_start = np.nonzero(change == 1)
    _, run_end = np.nonzero(change == -1)           # exclusive; same order as the starts
    count = len(run_y)
    parent = list(range(count))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    ys, starts, ends = run_y.tolist(), run_start.tolist(), run_end.tolist()
    first_in_row = {}
    for index in range(count - 1, -1, -1):
        first_in_row[ys[index]] = index
    for row, first in first_in_row.items():
        above = first_in_row.get(row - 1)
        if above is None:
            continue
        a = above
        b = first
        while b < count and ys[b] == row:
            while a < count and ys[a] == row - 1 and ends[a] < starts[b]:
                a += 1
            probe = a
            while probe < count and ys[probe] == row - 1 and starts[probe] <= ends[b]:
                root_a, root_b = find(probe), find(b)
                if root_a != root_b:
                    parent[root_a] = root_b
                probe += 1
            b += 1
    grouped = {}
    for index in range(count):
        grouped.setdefault(find(index), []).append(index)
    found = []
    for members in grouped.values():
        x0 = min(starts[i] for i in members)
        x1 = max(ends[i] for i in members)                 # exclusive, like every box here
        y0, y1 = ys[members[0]], ys[members[-1]] + 1       # runs are in row order
        pixels = sum(ends[i] - starts[i] for i in members)
        found.append((x0, y0, x1, y1, pixels, [(ys[i], starts[i], ends[i]) for i in members]))
    return found


def remove_large(mask):
    """(mask without components far larger than a character, [their boxes])."""
    found = components(mask)
    sizes = sorted((c[3] - c[1], c[2] - c[0]) for c in found if c[4] >= MIN_COMPONENT_PIXELS)
    if not sizes:
        return mask, []
    height = sorted(h for h, _ in sizes)[len(sizes) // 2]
    typical = max(height, 1)
    cleaned, removed = mask.copy(), []
    for x0, y0, x1, y1, pixels, runs in found:
        if (y1 - y0) > TALL_COMPONENT * typical or (x1 - x0) > WIDE_COMPONENT * typical:
            for y, a, b in runs:
                cleaned[y, a:b] = False
            removed.append((x0, y0, x1, y1))
    return cleaned, removed


def runs(profile, minimum=0):
    """The (start, end) of each stretch where profile exceeds `minimum`."""
    import numpy as np
    on = np.concatenate(([False], profile > minimum, [False]))
    change = np.flatnonzero(on[1:] != on[:-1])
    return [(int(a), int(b)) for a, b in zip(change[::2], change[1::2])]


def merge_close(spans, closest):
    """Spans with the ones separated by at most `closest` merged."""
    merged = []
    for start, end in spans:
        if merged and start - merged[-1][1] <= closest:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def find_lines(mask, share=0.01):
    """(y0, y1) of each line of text, and the typical height of a line. A row is part
    of a line when its ink exceeds `share` of the busiest row's."""
    rows = mask.sum(axis=1)
    if rows.max() == 0:
        return [], 0
    found = runs(rows, max(2, share * rows.max()))
    typical = sorted(b - a for a, b in found)[len(found) // 2]
    found = merge_close(found, max(2, int(0.2 * typical)))
    found = [(a, b) for a, b in found if b - a >= MIN_LINE_SHARE * typical]
    return found, typical


def glyphs_in(mask, y0, y1):
    """The marks on a line: runs of ink columns, each with its own tight height."""
    band = mask[y0:y1]
    glyphs = []
    for a, b in runs(band.sum(axis=0)):
        rows = band[:, a:b].any(axis=1).nonzero()[0]
        glyphs.append(Glyph(a, b, y0 + int(rows[0]), y0 + int(rows[-1]) + 1))
    return glyphs


def token_gap(gap_lists, height):
    """The gap width that separates tokens: the largest jump (as a ratio) between
    neighbouring sorted gaps, among gaps small enough to be inside a block."""
    gaps = sorted(g for gaps in gap_lists for g in gaps
                  if 0.1 * height <= g <= CANDIDATE_GAP_HEIGHTS * height)
    if len(gaps) < 4:
        return 0.5 * height
    best_ratio, best = 0.0, 0.5 * height
    for low, high in zip(gaps, gaps[1:]):
        if high / low > best_ratio:
            best_ratio, best = high / low, (low * high) ** 0.5
    return best


def classify_glyphs(mask, glyphs, height):
    """Mark the glyphs that are not letters or digits: dashes, equals signs, dots."""
    for glyph in glyphs:
        h, w = glyph.height, glyph.width
        if h <= 0.3 * height and w >= 1.2 * h:
            glyph.kind = DASH
        elif h <= 0.6 * height and w <= 0.35 * height:
            glyph.kind = DOT
        elif 0.25 * height <= h <= 0.7 * height and 0.5 * h <= w <= 2.2 * h:
            band = mask[glyph.y0:glyph.y1, glyph.x0:glyph.x1].any(axis=1)
            if len(runs(band.astype(int))) == 2:
                glyph.kind = EQUALS
    return glyphs


def typical_height(per_line):
    """The typical height of a digit: the median of the tall glyphs on the lines."""
    heights = sorted(g.height for glyphs in per_line for g in glyphs)
    if not heights:
        return 0.0
    tall = [h for h in heights if h >= 0.6 * heights[int(0.75 * (len(heights) - 1))]]
    return float(tall[len(tall) // 2])


def flush_left(lines, height):
    """The x of the edge that printed lines start at, or None if there is none.

    Every printed line starts at it, whatever else is on the line, so it is where the
    most tokens start (notes in a margin start wherever they like). If several x are
    nearly as common, the leftmost is the edge.
    """
    starts = sorted(token.x0 for line in lines for token in line.tokens)
    counts = [sum(1 for other in starts if abs(other - start) <= LEFT_SLACK * height)
              for start in starts]
    if not counts or max(counts) < MIN_ALIGNED_LINES:
        return None
    return min(start for start, count in zip(starts, counts) if count >= 0.8 * max(counts))


def split_outside(tokens, left, height):
    """(tokens in the block, tokens outside it) for one line."""
    inside = list(tokens)
    outside = []
    if left is not None:
        while len(inside) > 1 and inside[0].x1 < left - LEFT_SLACK * height:
            outside.append(inside.pop(0))
    for index in range(1, len(inside)):
        if inside[index].x0 - inside[index - 1].x1 > MARGIN_GAP_HEIGHTS * height:
            outside.extend(inside[index:])
            inside = inside[:index]
            break
    return inside, outside


def find_equals(line, height):
    """The index of the token that is the equals sign in `Label words = value`, or None.

    By structure and not by look, since fonts draw it differently (two bars, or one
    that blurs flat): a single flat glyph, narrower than a `--` cell, after one or two
    label words and followed by a value.
    """
    for index, token in enumerate(line.tokens[:3]):
        if index >= 1 and len(token.glyphs) == 1 and len(line.tokens) > index + 1:
            glyph = token.glyphs[0]
            if glyph.kind in (EQUALS, DASH) and glyph.width <= height:
                return index
    return None


def analyse(prepared):
    """The Layout of a cleaned page (or None for a blank one)."""
    if prepared.blank:
        return None
    mask, removed = remove_large(prepared.mask)
    spans, _ = find_lines(mask)
    if not spans:
        return None
    per_line = [glyphs_in(mask, a, b) for a, b in spans]
    height = typical_height(per_line)
    gap_lists = [[b.x0 - a.x1 for a, b in zip(glyphs, glyphs[1:])] for glyphs in per_line]
    gap = token_gap(gap_lists, height)
    lines = []
    for (a, b), glyphs in zip(spans, per_line):
        classify_glyphs(mask, glyphs, height)
        tokens, current = [], [glyphs[0]]
        for before, after in zip(glyphs, glyphs[1:]):
            if after.x0 - before.x1 > gap:
                tokens.append(Token(current))
                current = []
            current.append(after)
        tokens.append(Token(current))
        lines.append(Line(a, b, tokens))
    left = flush_left(lines, height)
    outside = list(removed)
    for line in lines:
        line.tokens, gone = split_outside(line.tokens, left, height)
        outside.extend((t.x0, t.y0, t.x1, t.y1) for t in gone)
    return Layout(lines, height, gap, height < MIN_GLYPH_HEIGHT, outside, mask)
