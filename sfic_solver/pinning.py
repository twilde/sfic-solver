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
