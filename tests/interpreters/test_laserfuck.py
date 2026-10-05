"""Unit tests for the LaserFuck interpreter."""

import io
from contextlib import redirect_stdout
from typing import ClassVar
from unittest.mock import patch

from esolangs.interpreters.grid_based.laserfuck import run
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import FirstDraw
from tests.interpreters.contract import SnapshotContract


def run_and_capture(code: list[str], heading: int | None = 3) -> str:
    """Run ``code`` with its laser started in ``heading``.

    ``heading=None`` leaves the draw to the interpreter's own source, which
    is the spec's random start.
    """
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO(), rng=None if heading is None else FirstDraw(heading))
    return buffer.getvalue()


class TestSurvivorGaps:
    r"""Programs that separate a mutated interpreter from the original.

    A mutation run left 59 survivors -- edits no test objected to.
    Categorising them found that most were not equivalent mutants but a
    few untested *shapes*, each covering several edits at once: the
    pointer only ever moved at an edge, conditional mirrors were only ever
    met head-on, the command set could widen without any test noticing,
    and the random heading was never drawn at all.  Every grid below was
    run against the mutated code and prints something different there.
    """

    def test_the_random_heading_is_actually_drawn(self) -> None:
        """``run`` with no heading draws one; every other test passes one.

        The helper above takes ``heading: int = 3``, so the branch calling
        ``secrets.randbelow`` is never reached -- not even by
        ``test_every_start_heading_reaches_its_own_arm``, which loops over
        ``range(4)`` and passes each value explicitly, though its docstring
        says the cross "does not need to".  The cross halts whatever it
        draws, so the draw can be exercised without pinning its result.
        """
        cross = ["   x", "   +", "x++o++++x", "   +", "   +", "   +", "   x"]
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(cross, IO())  # no heading: the interpreter draws one
        assert buffer.getvalue() in {"1", "2", "3", "4"}

    def test_rows_are_padded_to_equal_width(self) -> None:
        """Padding makes every row as wide as the widest.

        The bounds check reads ``len(self.text[0])`` -- row 0's width -- so
        a beam on a row left *shorter* than row 0 would pass the check and
        index past that row's end.  A short row under a long one catches
        it; every other grid here is uniform or has its beam on row 0.
        """
        assert run_and_capture(["xxxx", "o"]) == ""

    def test_the_drawn_heading_is_one_of_four(self) -> None:
        r"""The initial draw is ``randbelow(4)``, not some wider range.

        Pinning the draw is the only way to see this: a fifth heading
        would be chosen one run in five, and because it falls through the
        movement chain it travels like ``3`` -- so the outputs it produces
        overlap the real ones and no grid separates them.

        The stub must read its *argument* rather than return a constant: a
        constant is returned whatever range is asked for, which hides the
        very widening this is checking.  Asking for the largest heading in
        whatever range the interpreter requests makes the bound exact, and
        ``\`` is what tells 3 from 4 -- it reverses ``(d + 2) % 4``, which
        is 1 for the real heading and 2 for a fifth one.
        """
        with patch("secrets.randbelow", side_effect=lambda n: n - 1):
            assert run_and_capture(["o\\ ", " +x"], heading=None) == "1"

    def test_the_split_direction_is_drawn_along_the_new_axis(self) -> None:
        r"""``*`` draws only *which way* along the perpendicular axis.

        The axis itself is arithmetic -- ``2 * (1 - d // 2)`` -- and the
        draw adds 0 or 1 to it.  Left and right are therefore headings 2
        and 3 for a vertical beam, and an axis computed even slightly
        differently would offer 3 and 4 instead: still a valid pair of
        moves, still overlapping the real ones, invisible to any grid.
        Pinning the draw to 0 asks for the *first* heading on the axis,
        which must be left, and the ``+`` on the left arm reports it.
        """
        cage = ["  x", "  +", "x+*x", "/ ^\\", "\\ o/", "  _"]
        for heading in range(4):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                run(cage, IO(), rng=FirstDraw(heading, rest=0))
            assert buffer.getvalue() == "2", heading


def _machine(code: object) -> object:
    from esolangs.interpreters.grid_based.laserfuck import _Machine
    from esolangs.interpreters.io import IO

    return _Machine(code, IO(), rng=FirstDraw(3))


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["ÿ}o+x\n x"]
