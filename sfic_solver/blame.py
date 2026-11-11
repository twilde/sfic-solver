"""Why a position has no cut that can be pinned: the words for the solver's verdict.

When the keys a solver is choosing cannot be pinned at some position whatever they cut
there (`joint` finds that exactly, as an empty list), the owner needs to know which known
keys to look at. This names them: a pair of known keys of one core whose cuts are too close,
or too far, for a pin to sit between them, or, when no single core is at fault, the known
cuts that together leave the group no digit. See docs/designs/larger-pinnable-groups.md,
part 3. Pure functions; no I/O.
"""
from .pinning import PinningError, pin_chamber

MOST_CUTS_SHOWN = 8


def key_list(names):
    """'a', 'a and b', 'a, b and c'."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def known_conflict(system, core, change, ops, control, group, known, p):
    """A sentence if the known keys of this core alone (the group's keys left out) cannot be
    pinned at position p, whatever the group cuts there, else None. Cuts that conflict among
    known keys stay in conflict however many other cuts are added (a pin of size 1 cannot be
    split, and a control pin only gets smaller with a higher operating cut)."""
    by_cut = {}
    for name in ops:
        if name not in group:
            by_cut.setdefault(known[name][p], []).append(name)
    if not by_cut:
        return None
    where = f"core '{core}' (change key {change})"
    low, high = system.other_pins
    cuts = sorted(by_cut)
    for below, above in zip(cuts, cuts[1:]):
        gap = above - below
        if not low <= gap <= high:
            return (f"{where}: known keys {key_list(by_cut[below])} (cut {below}) and "
                    f"{key_list(by_cut[above])} (cut {above}) are {gap} apart, so the pin "
                    f"between them would be {gap}, outside {low} to {high}")
    if control in group:
        return None
    try:
        pin_chamber(system, cuts, known[control][p])
    except PinningError as error:
        named = ", ".join(f"{key_list(by_cut[c])} {c}" for c in cuts)
        return f"{where}: with the known keys alone ({named}; control key {control} " \
               f"{known[control][p]}), {error.reason}"
    return None


def blame_position(system, group, constraints, known, p):
    """Sentences for position p (0-based) explaining why no digits for `group` can be pinned.

    constraints  (core name, change key, operating key names, control key name) for each core
                 and change key that involves a key of the group
    known        name -> bitting for every key of those constraints not in the group

    One sentence for each core whose known keys conflict among themselves; if none does, one
    sentence listing the known cuts that between them leave the group no digit.
    """
    sentences = []
    involved = {}
    for core, change, ops, control in constraints:
        for name in (*ops, control):
            if name not in group:
                involved.setdefault(name, known[name][p])
        sentence = known_conflict(system, core, change, ops, control, group, known, p)
        if sentence and sentence not in sentences:
            sentences.append(sentence)
    if sentences:
        return sentences
    shown = [f"{name} {cut}" for name, cut in list(involved.items())[:MOST_CUTS_SHOWN]]
    more = len(involved) - len(shown)
    return [f"no cut for {', '.join(group)} can be pinned beside the known keys' cuts there "
            f"({', '.join(shown)}{f', and {more} more' if more > 0 else ''})"]
