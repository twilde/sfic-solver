"""Core pinning: the pins that make a core behave as the key hierarchy says.

Everything here is measured in pin numbers (increments of the pinning system's
step), never inches. See docs/designs/core-pinning.md for the model.
"""
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class PinningSystem:
    """The numbers that define one SFIC pinning system (A2, A3, A4, ...).

    name            what a system file calls it
    increment       inches per pin number (informational; the maths never uses it)
    depths          cut depths 0 .. depths - 1
    stack_total     every chamber's pin numbers add up to this
    bottom_pins     (smallest, largest) bottom pin number
    other_pins      (smallest, largest) number of the master, control and driver pins,
                    which all come from one family
    control_offset  the control shear line is this many increments beyond the
                    operating one
    """
    name: str
    increment: float
    depths: int
    stack_total: int
    bottom_pins: Tuple[int, int]
    other_pins: Tuple[int, int]
    control_offset: int

    def __post_init__(self):
        for label, (low, high) in (("bottom_pins", self.bottom_pins),
                                   ("other_pins", self.other_pins)):
            if not 0 <= low <= high:
                raise ValueError(f"{self.name}: {label} must be (smallest, largest) "
                                 f"with 0 <= smallest <= largest, got {(low, high)}")
        if self.depths < 1 or self.control_offset < 1:
            raise ValueError(f"{self.name}: depths and control_offset must be at least 1")
        if self.depths - 1 + self.control_offset >= self.stack_total:
            raise ValueError(f"{self.name}: the deepest control boundary "
                             f"({self.depths - 1 + self.control_offset}) must be below "
                             f"the stack total ({self.stack_total})")


A2 = PinningSystem(name="A2", increment=0.0125, depths=10, stack_total=23,
                   bottom_pins=(0, 9), other_pins=(2, 19), control_offset=10)

SYSTEMS = {system.name: system for system in (A2,)}


def get_system(name):
    """The pinning system called `name` (any case), or ValueError listing the known ones."""
    system = SYSTEMS.get(name.upper()) if isinstance(name, str) else None
    if system is None:
        raise ValueError(f"unknown pinning system {name!r}; known systems: "
                         f"{', '.join(sorted(SYSTEMS))}")
    return system


class PinningError(ValueError):
    """A chamber cannot be pinned for the cuts it was given.

    `chamber` is the 1-based position (None when a single chamber was pinned on
    its own) and `reason` is the message without the position.
    """

    def __init__(self, reason, chamber=None):
        super().__init__(f"chamber {chamber}: {reason}" if chamber else reason)
        self.reason = reason
        self.chamber = chamber


@dataclass(frozen=True)
class Chamber:
    """The pins in one chamber, as pin numbers.

    bottom   the bottom pin
    masters  the pins between the bottom pin and the control pin, lowest first.
             They are pin layers: any of the core's keys may be the one a pin
             belongs to, whatever the key is called in the hierarchy.
    control  the control pin
    driver   the driver (top) pin
    """
    bottom: int
    masters: Tuple[int, ...]
    control: int
    driver: int

    @property
    def pins(self):
        """All the pins, bottom to top."""
        return (self.bottom, *self.masters, self.control, self.driver)

    @property
    def boundaries(self):
        """The partial sums of the pins from the bottom: the height of each joint."""
        total, heights = 0, []
        for pin in self.pins[:-1]:
            total += pin
            heights.append(total)
        return tuple(heights)


def pin_chamber(system, operating, control):
    """Pin one chamber for the operating keys' cuts and the control key's cut.

    Every distinct operating cut becomes a boundary, the lowest at the bottom pin
    and each next one a single master pin above it; keys that share a cut share a
    boundary, so that chamber has one pin fewer. The control boundary sits
    `control_offset` above the control cut, and the driver makes the stack up to
    its total. Raises PinningError if any pin falls outside its family's sizes.
    """
    cuts = [*operating, control]
    if not operating or any(isinstance(c, bool) or not isinstance(c, int)
                            or not 0 <= c < system.depths for c in cuts):
        raise ValueError(f"cuts must be whole numbers from 0 to {system.depths - 1}, "
                         f"with at least one operating cut; got {tuple(operating)} "
                         f"and control {control!r}")
    heights = sorted(set(operating))
    control_height = control + system.control_offset
    masters = tuple(high - low for low, high in zip(heights, heights[1:]))
    chamber = Chamber(bottom=heights[0], masters=masters,
                      control=control_height - heights[-1],
                      driver=system.stack_total - control_height)

    low, high = system.bottom_pins
    if not low <= chamber.bottom <= high:
        raise PinningError(f"the bottom pin would be {chamber.bottom}, outside {low} to {high}")
    low, high = system.other_pins
    for (below, above), pin in zip(zip(heights, heights[1:]), masters):
        if not low <= pin <= high:
            raise PinningError(f"operating cuts {below} and {above} are {pin} apart, so the "
                               f"pin between them would be {pin}, outside {low} to {high}")
    if not low <= chamber.control <= high:
        raise PinningError(f"control cut {control} puts the control boundary "
                           f"{chamber.control} above the highest operating cut "
                           f"{heights[-1]}, outside {low} to {high}")
    if not low <= chamber.driver <= high:
        raise PinningError(f"the driver would be {chamber.driver}, outside {low} to {high}")
    return chamber


def pin_core(system, operating_keys, control):
    """Pin every chamber of a core: one Chamber per position, or PinningError.

    operating_keys  the bittings of every key that operates the core (all on an
                    equal footing: change key, masters, whatever the hierarchy calls them)
    control         the bitting of the core's control key
    """
    if not operating_keys:
        raise ValueError("a core needs at least one operating key")
    length = len(control)
    if any(len(key) != length for key in operating_keys):
        raise ValueError("every key must have the same number of cuts")
    chambers = []
    for position in range(length):
        try:
            chambers.append(pin_chamber(system, [key[position] for key in operating_keys],
                                        control[position]))
        except PinningError as err:
            raise PinningError(err.reason, position + 1) from None
    return tuple(chambers)
