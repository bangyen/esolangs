"""Tests for the Deadfish interpreter.

The wiki calls three programs mandatory for an implementation -- it threatens
to delist interpreters that fail them -- so they are asserted verbatim rather
than paraphrased.  All three turn on the same trap: the accumulator resets
only on exactly ``-1`` and exactly ``256``, so the range check the C
original's own comment describes would pass the first case and fail the other
two.
"""

from esolangs.interpreters.io import IO, ScriptedIO
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

    def test_the_xkcd_random_number_is_four(self) -> None:
        """``iiso``, whose joke is that the answer is not random."""
        assert run_program(run, "iiso") == "4\n"

    def test_output_is_a_number_not_a_character(self) -> None:
        """65 prints as ``65``; the language has no character output."""
        assert run_program(run, "i" * 65 + "o") == "65\n"

    def test_a_non_command_is_ignored(self) -> None:
        """ "Errors are not acknowledged", so junk is neither read nor refused."""
        assert run_program(run, "i i\nxyz!o") == "2\n"

    def test_an_empty_program_prints_nothing(self) -> None:
        assert run_program(run, "") == ""

    def test_h_halts_before_the_rest(self) -> None:
        """The command table carries ``h`` as optional; it is honoured."""
        assert run_program(run, "iiohiiio") == "2\n"

    def test_each_output_is_its_own_line(self) -> None:
        """Otherwise 1 then 2 and a single 12 are the same output."""
        assert run_program(run, "ioio") == "1\n2\n"

    def test_decrement_below_zero_traps_rather_than_going_negative(self) -> None:
        """-1 is a trap value, so the accumulator never shows a negative."""
        assert run_program(run, "do") == "0\n"

    def test_squaring_zero_stays_zero(self) -> None:
        """The trap does not fire on 0, and 0 * 0 is not one of its values."""
        assert run_program(run, "sso") == "0\n"

    def test_every_program_halts(self) -> None:
        """The position only ever advances, so there is no loop to detect.

        Asserted because it is why this file carries no ``CycleContract``:
        Deadfish has no jump of any kind, so no program can revisit a state
        and the hang detector has nothing to find.
        """
        for program in ("", "i", _HELLO, "iissso", "h", "xyz"):
            machine = _Machine(program, ScriptedIO())
            steps = 0
            while not machine.halted:
                machine.step()
                steps += 1
            assert steps <= len(program), program


def _machine(code: object) -> object:
    return _Machine(code, IO())


class TestContract(SnapshotContract, StateViewContract):
    """The shared shapes, with this language's own programs.

    No ``CycleContract``: it wants a program that revisits a snapshot, and
    ``test_every_program_halts`` shows none exists.
    """

    machine = staticmethod(_machine)
    stepping_program = "iso"
    state_views = ("ip", "memory", "ind", "value")
    viewing_program = "iso"
