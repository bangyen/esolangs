"""Tests for the Deadfish interpreter.

The wiki calls three programs mandatory for an implementation -- it threatens
to delist interpreters that fail them -- so they are asserted verbatim rather
than paraphrased.  All three turn on the same trap: the accumulator resets
only on exactly ``-1`` and exactly ``256``, so the range check the C
original's own comment describes would pass the first case and fail the other
two.
"""

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.deadfish import _Machine, run
from tests.interpreters.contract import SnapshotContract, StateViewContract
from tests.interpreters.runner import run_program

#: The wiki's four-line "Hello, world!", whose lines run as one program.
_HELLO = "".join(
    [
        "iiisdsiiiiiiiioiiiiiiiiiiiiiiiiiiiiiiiiiiiiioiiiiiiiooiiio",
        "ddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
        "ddddddddddoddddddddddddo",
        "dddddddddddddddddddddsddoddddddddoiiioddddddoddddddddo",
        "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddo",
    ]
)


class TestTheMandatoryCases:
    """The three the wiki requires, and what each one catches."""

    def test_the_third_square_overshoots_to_zero(self) -> None:
        """``iissso``: 2, 4, 16, then 256 exactly, which traps."""
        assert run_program(run, "iissso") == "0\n"

    def test_two_hundred_eighty_nine_sails_past_the_trap(self) -> None:
        """``diissisdo``: the leading ``d`` traps at -1, and 17*17 does not.

        A ``value > 256`` check -- the one the C comment claims -- would zero
        the 289 here and print 0 instead of 288.
        """
        assert run_program(run, "diissisdo") == "288\n"

    def test_the_trap_fires_on_the_way_down_too(self) -> None:
        """``iissisd...o``: 289 decremented 33 times passes through 256."""
        assert run_program(run, "iissisd" + "d" * 32 + "o") == "0\n"


class TestDeadfish:
    def test_the_wiki_hello_world_spells_it(self) -> None:
        """Thirteen ``o``s, whose values are the string's ASCII codes."""
        printed = [int(num) for num in run_program(run, _HELLO).split()]
        assert "".join(map(chr, printed)) == "Hello, world!"


def _machine(code: object) -> object:
    return _Machine(code, IO())


class TestContract(SnapshotContract, StateViewContract):
    """The shared shapes, with this language's own programs.

    No ``CycleContract``: Deadfish has no backwards jump.
    """

    machine = staticmethod(_machine)
    stepping_program = "iso"
    state_views = ("ip", "memory", "ind", "value")
    viewing_program = "iso"
