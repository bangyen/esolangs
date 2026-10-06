"""What the Streetcode suites share: drawing a street, and driving one."""

from unittest.mock import patch

from esolangs.interpreters.grid_based.streetcode import (
    _Machine,
    run,
)
from esolangs.interpreters.io import IO
from tests.interpreters.runner import run_program


def machine_unvalidated(code: list[str]) -> _Machine:
    """Build a ``_Machine`` from a wall-shape fixture, skipping validation."""
    with patch.object(_Machine, "_validate", lambda *_: None):
        return _Machine(code, IO())


def street(instructions: str) -> list[str]:
    """Box a one-line program into a street, the way the wiki draws one."""
    wall = "+" + "-" * len(instructions) + "+"
    return [wall, "|" + " " * len(instructions) + "|", f"|{instructions}|", wall]


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    """Run a Streetcode program and return its stdout."""
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


# A counting-ring program printing "Hi".  The ring latches a merge as the car
# approaches the junction, so a full lap is the only thing that drives the
# latch path end to end -- both tests below need exactly that shape.
_RING_PROGRAM = [
    "+----------------------------------------------+",
    "|                                              |",
    "|C^        O^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^O;|",
    "+--+  ++  +------------------------------------+",
    "   |      |",
    "   | ^_~ =|",
    "   | ^++= |",
    "   |^^++^U|",
    "   |^^^^^=|",
    "   |^^^^^^|",
    "   +------+",
]


def run_street(instructions: str, inputs: list[str] | None = None) -> str:
    """Run a one-line program inside a proper two-lane street."""
    return run_and_capture(street(instructions), inputs)
