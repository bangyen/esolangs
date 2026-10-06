"""Tests for the Deadfish interpreter."""

import pytest

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


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        # The three the wiki requires.  2, 4, 16, then 256 exactly, which traps.
        pytest.param("iissso", "0\n", id="the_third_square_overshoots_to_zero"),
        # the leading d traps at -1, and 17*17 does not
        pytest.param(
            "diissisdo", "288\n", id="two_hundred_eighty_nine_sails_past_the_trap"
        ),
        # 289 decremented 33 times passes through 256
        pytest.param(
            "iissisd" + "d" * 32 + "o", "0\n", id="the_trap_fires_on_the_way_down_too"
        ),
        # the xkcd joke is that the answer is not random
        pytest.param("iiso", "4\n", id="the_xkcd_random_number_is_four"),
        # 65 prints as 65; the language has no character output
        pytest.param("i" * 65 + "o", "65\n", id="output_is_a_number_not_a_character"),
        # "Errors are not acknowledged", so junk is neither read nor refused
        pytest.param("i i\nxyz!o", "2\n", id="a_non_command_is_ignored"),
        pytest.param("", "", id="an_empty_program_prints_nothing"),
        # the command table carries h as optional; it is honoured
        pytest.param("iiohiiio", "2\n", id="h_halts_before_the_rest"),
        # otherwise 1 then 2 and a single 12 are the same output
        pytest.param("ioio", "1\n2\n", id="each_output_is_its_own_line"),
        # -1 is a trap value, so the accumulator never shows a negative
        pytest.param(
            "do", "0\n", id="decrement_below_zero_traps_rather_than_going_negative"
        ),
        # the trap does not fire on 0, and 0 * 0 is not one of its values
        pytest.param("sso", "0\n", id="squaring_zero_stays_zero"),
    ],
)
def test_prints(code: str, expected: str) -> None:
    assert run_program(run, code) == expected


class TestDeadfish:
    def test_the_wiki_hello_world_spells_it(self) -> None:
        """Thirteen ``o``s, whose values are the string's ASCII codes."""
        printed = [int(num) for num in run_program(run, _HELLO).split()]
        assert "".join(map(chr, printed)) == "Hello, world!"

    def test_every_program_halts(self) -> None:
        """The position only ever advances, so there is no loop to detect."""
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
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "iso"
    state_views = ("ip", "memory", "ind", "value")
    viewing_program = "iso"
