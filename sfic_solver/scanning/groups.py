"""Reading digit marks by shape, with Tesseract's readings as votes (D38).

Every `3` on a printout looks like every other `3`. So the marks of a whole run are
grouped by shape, each group is labelled by the readings that Tesseract gave for its
members, and a mark is read as its group's label. A single misreading is outvoted by
the other marks in its group. The groups fail in visible ways, and each is a check:

  too small to vote        a group with too few members has no standing
  impure                   the votes in a group do not agree enough
  duplicate label          two groups carry one label, so at least one is mislabelled
                           (a confusion by glyph makes a pure group of the wrong
                           digit, which only the second group of that digit gives away)
  dissent                  a mark whose own readings mostly name another digit than
                           its group's label, which is how a lookalike would slip in

The thresholds start strict (D38): they flag too much rather than too little, and
are relaxed only as far as the test harness shows that no wrong chart is accepted.
Nothing here says what a digit is except the labels that Tesseract's readings gave.
"""
from collections import Counter
from dataclasses import dataclass

SHAPE_SIZE = (16, 24)           # marks are scaled to this (width, height) to compare
SAME_SHAPE = 0.80               # correlation at which a mark joins an existing group
ASPECT_TOLERANCE = 0.35         # how much the width/height ratios may differ (log)
MIN_MEMBERS = 3                 # fewer marks than this and a group has no standing
MIN_PURITY = 0.90               # the share of a group's votes its label must have
DISSENT_SHARE = 0.5             # a mark's own votes must give its group's label this much

TOO_SMALL, IMPURE, DUPLICATE, UNVOTED, DISSENT = (
    "too small", "impure", "duplicate", "unvoted", "dissent")


@dataclass
class Mark:
    value: str          # the digit it is read as, or None if it is flagged
    reason: str         # why it is flagged (one of the constants above), or None
    group: int


def shape(mask, glyph):
    """A mark as a unit vector (zero-mean, 16 by 24) and its width/height ratio."""
    import numpy as np
    from PIL import Image

    piece = mask[glyph.y0:glyph.y1, glyph.x0:glyph.x1].astype(np.uint8) * 255
    scaled = Image.fromarray(piece).resize(SHAPE_SIZE, Image.BILINEAR)
    vector = np.asarray(scaled, dtype=np.float32).ravel()
    vector = vector - vector.mean()
    norm = float(np.linalg.norm(vector))
    ratio = (glyph.x1 - glyph.x0) / max(1, glyph.y1 - glyph.y0)
    return (vector / norm if norm else vector), ratio


class Marks:
    """Marks added over a whole run, grouped by shape, voted on, then resolved."""

    def __init__(self):
        self.vectors = []        # one per mark, for the group centroids
        self.group_of = []       # mark id -> group id
        self.sums, self.counts, self.ratios = [], [], []     # per group
        self.group_votes = []                                # per group: Counter
        self.own_votes = []                                  # per mark: Counter

    def add(self, mask, glyph):
        """Add a mark; returns its id."""
        import numpy as np
        vector, ratio = shape(mask, glyph)
        best, chosen = SAME_SHAPE, None
        for group, total in enumerate(self.sums):
            centre = total / (np.linalg.norm(total) or 1.0)
            score = float(vector @ centre)
            if score >= best and abs(np.log(ratio / self.ratios[group])) <= ASPECT_TOLERANCE:
                best, chosen = score, group
        if chosen is None:
            chosen = len(self.sums)
            self.sums.append(vector.copy())
            self.counts.append(1)
            self.ratios.append(ratio)
            self.group_votes.append(Counter())
        else:
            self.sums[chosen] = self.sums[chosen] + vector
            self.ratios[chosen] = (self.ratios[chosen] * self.counts[chosen] + ratio) \
                / (self.counts[chosen] + 1)
            self.counts[chosen] += 1
        self.group_of.append(chosen)
        self.own_votes.append(Counter())
        return len(self.group_of) - 1

    def vote(self, ids, readings):
        """Count the readings of one row of marks `ids`: each is a list of characters,
        or None. A reading is usable only if it has one character per mark; others are
        thrown away, not repaired. Returns how many were usable."""
        usable = 0
        for reading in readings:
            if reading is None or len(reading) != len(ids):
                continue
            usable += 1
            for mark, char in zip(ids, reading):
                self.own_votes[mark][char] += 1
                self.group_votes[self.group_of[mark]][char] += 1
        return usable

    def resolve(self):
        """A Mark for every mark added, in order."""
        labels, reasons = {}, {}
        for group, votes in enumerate(self.group_votes):
            total = sum(votes.values())
            if self.counts[group] < MIN_MEMBERS:
                reasons[group] = TOO_SMALL
            elif total == 0:
                reasons[group] = UNVOTED
            else:
                label, best = votes.most_common(1)[0]
                if best / total < MIN_PURITY:
                    reasons[group] = IMPURE
                elif len(label) != 1 or not label.isdigit():
                    reasons[group] = IMPURE
                else:
                    labels[group] = label
        carried = Counter(labels.values())
        for group, label in list(labels.items()):
            if carried[label] > 1:
                del labels[group]
                reasons[group] = DUPLICATE
        marks = []
        for mark, group in enumerate(self.group_of):
            if group not in labels:
                marks.append(Mark(None, reasons[group], group))
                continue
            own = self.own_votes[mark]
            total = sum(own.values())
            if total and own[labels[group]] < DISSENT_SHARE * total:
                marks.append(Mark(None, DISSENT, group))
            else:
                marks.append(Mark(labels[group], None, group))
        return marks

    def small_groups(self):
        """How many marks sit in groups too small to vote."""
        return sum(count for count in self.counts if count < MIN_MEMBERS)
