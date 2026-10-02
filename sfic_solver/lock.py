"""A simulated lock, built from pin stacks alone.

A lock is a pin stack per chamber and nothing else: it knows nothing of change
keys, masters or control keys, only which shear lines a key lines up. That
makes it an independent check on the pinner and on the key-level counting, and
its geometry (stacks, joints, lift, which line is aligned where) is what a
visualizer would draw.

The geometry is physical. A cut is a depth, so a deeper cut lifts the stack by
less: cut 0 gives the most lift, `depths - 1` the least. Heights are measured
in the pinning system's increments. The operating shear line is `depths - 1`
above the stack's resting position at the deepest cut, which is calibrated so
that bottom pin #n goes with cut n, and the control shear line is
`control_offset` further out. A line is aligned in a chamber when a joint between
two pins sits exactly on it; a key operates the lock (or its control) when every
chamber is aligned.
"""
from itertools import accumulate

OPERATING = "operating"
CONTROL = "control"


class Lock:
    def __init__(self, system, stacks):
        """`stacks`: for each chamber, its pin numbers from the bottom to the top."""
        self.system = system
        self.stacks = tuple(tuple(stack) for stack in stacks)

    @classmethod
    def from_chambers(cls, system, chambers):
        return cls(system, [chamber.pins for chamber in chambers])

    def lift(self, cut):
        """How far a key with this cut lifts the stack: more for a shallower cut."""
        return self.system.depths - 1 - cut

    def shear_height(self, line):
        """The height of a shear line, in increments."""
        if line == OPERATING:
            return self.system.depths - 1
        if line == CONTROL:
            return self.system.depths - 1 + self.system.control_offset
        raise ValueError(f"unknown shear line {line!r}")

    def joint_on_line(self, position, cut, line):
        """The joint (1 = between the first two pins) that sits on the shear line in
        this chamber when a key with this cut is in, or None if a pin straddles it."""
        height = self.shear_height(line) - self.lift(cut)       # height within the stack
        for joint, reached in enumerate(accumulate(self.stacks[position][:-1]), 1):
            if reached == height:
                return joint
        return None

    def aligned(self, key, line):
        """True if every chamber has a joint on `line` for this key."""
        self._check(key)
        return all(self.joint_on_line(p, cut, line) is not None for p, cut in enumerate(key))

    def lines_aligned(self, key):
        """The set of shear lines this key lines up: operating, control, both or neither."""
        return frozenset(line for line in (OPERATING, CONTROL) if self.aligned(key, line))

    def operates(self, key):
        return self.aligned(key, OPERATING)

    def _check(self, key):
        if len(key) != len(self.stacks) or any(
                isinstance(c, bool) or not isinstance(c, int) or not 0 <= c < self.system.depths
                for c in key):
            raise ValueError(f"a key needs {len(self.stacks)} cuts from 0 to "
                             f"{self.system.depths - 1}, got {tuple(key)!r}")
