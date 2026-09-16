"""What the Streetcode suites share: drawing a street, and driving one.

``machine_unvalidated`` is the one that skips ``_validate``, so a test can
build skeletal geometry that is not a legal street.
"""

from unittest.mock import patch

from esolangs.interpreters.grid_based.streetcode import (
    _Machine,
    run,
)
from esolangs.interpreters.io import IO
from tests.interpreters.runner import run_program


def machine_unvalidated(code: list[str]) -> _Machine:
    """Build a ``_Machine`` from a wall-shape fixture, skipping validation.

    The junction and lane-merge tests probe ``_junction_kind`` and the merge
    latches directly, on deliberately skeletal geometry -- bare wall arms and
    gaps, with assertions keyed to exact coordinates.  Such a fixture is not a
    legal street and is not meant to be one, so it is constructed with
    ``_validate`` disabled rather than redrawn, which would change what the
    test measures.  Whole-program tests use the real constructor.
    """
    with patch.object(_Machine, "_validate", lambda *_: None):
        return _Machine(code, IO())


def street(instructions: str) -> list[str]:
    """Box a one-line program into a street, the way the wiki draws one.

    The spec's streets are two characters wide, so a bare instruction row
    is not a street: the instructions become the southern lane (the wall
    below them on the car's right is what sends it East) with a blank
    oncoming lane above, inside a wall.  This is exactly the shape of the
    wiki's own "simple example", ``+----+`` / ``|    |`` / ``|CIO;|`` /
    ``+----+``, and it lets these tests pin instruction semantics on
    conformant geometry rather than on a one-wide corridor.
    """
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
