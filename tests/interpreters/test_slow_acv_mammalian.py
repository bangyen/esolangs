"""Unit tests for the SLOW ACV SLOW ACV MAMMALIAN interpreter."""

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.slow_acv_mammalian import run
from tests.interpreters.contract import SnapshotContract
from tests.raises import raises_message


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestMammalian:
    @pytest.mark.parametrize("word", ["SEEDSEED", "XSEEDY", "SEED!", "SEED/SEED"])
    def test_embedded_instruction_names_do_not_execute(self, word: str) -> None:
        with pytest.raises(ValueError, match="unknown SLOW ACV MAMMALIAN command"):
            run_and_capture(f"{word} CONSUME PRONOUNCE")

    def test_concatenated_program_does_not_execute(self) -> None:
        with pytest.raises(ValueError, match="unknown SLOW ACV MAMMALIAN command"):
            run_and_capture("SEEDCONSUMEPRONOUNCE")

    def test_hello_world(self) -> None:
        """Hello World program from the language docs."""
        program = Path(__file__).parents[2] / "tests/fixtures/mammalian.txt"
        assert run_and_capture(program.read_text()) == "Hello, world!\n"


class TestStepMachine:
    def test_the_command_halt_flag_starts_false(self) -> None:
        """The flag is ``False`` to begin with, and ``snapshot`` carries it.

        Any falsy value behaves the same in ``halted``, which only reads it
        for truth -- but the flag is part of the state, and a run that has
        not halted by command must be distinguishable from one that has.
        Comparing the snapshot pins the value, not just its truthiness.
        """
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("PRONOUNCE", IO())
        assert machine.snapshot()[-1] is False


class TestSprintIndex:
    """``SPRINT`` indexes from the far end on a negative accumulator."""

    def test_an_accumulator_past_the_far_end_reports_a_list(self) -> None:
        """Walking off the front raises, and says "list", not "tuple".

        The arrays are tuples inside the transition, so letting the
        subscript fault would reword the message callers already see.  The
        guard is one cell out from the legal end: on a one-cell array
        ``-1`` still indexes it and only ``-2`` is out of range.
        """
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _advance

        arrays = tuple((0,) for _ in range(23))
        with raises_message(IndexError, "list index out of range"):
            _advance((arrays, 0, -2, 0, False), 6)

        assert _advance((arrays, 0, -1, 0, False), 6)[1] == 0


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "SEED PRONOUNCE"


@pytest.mark.parametrize("io_modulus", [255, 256])
@pytest.mark.parametrize("cell_modulus", [255, 256])
@pytest.mark.parametrize(
    ("program", "stdin"),
    [
        ("ACCEPT CONSUME CONSUME PRONOUNCE", "ÿ"),
        ("ACCEPT CONSUME CONSUME EXCRETE CONSUME PRONOUNCE", "ÿ"),
        ("ACCEPT CONSUME CONSUME PRONOUNCE", "Ā"),
        (" ".join(["SEED"] * 256 + ["DIGEST", "PRONOUNCE"]), ""),
    ],
)
def test_moduli_agree_between_fast_run_and_vm(
    cell_modulus: int, io_modulus: int, program: str, stdin: str
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine, run

    fast = ScriptedIO(stdin)
    run(program, fast, cell_modulus=cell_modulus, io_modulus=io_modulus)
    stepped = ScriptedIO(stdin)
    machine = _Machine(
        program, stepped, cell_modulus=cell_modulus, io_modulus=io_modulus
    )
    while not machine.halted:
        machine.step()
    raw_value = ord(stdin) if stdin else 256
    expected = raw_value % cell_modulus
    assert fast.getvalue() == stepped.getvalue() == chr(expected % io_modulus)
    assert fast.reads == stepped.reads == len(stdin)


@pytest.mark.parametrize(
    "settings",
    [
        {"cell_modulus": 254},
        {"cell_modulus": 256.0},
        {"io_modulus": 254},
        {"io_modulus": 255.0},
    ],
)
def test_unsupported_moduli_are_rejected_before_execution(settings) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine, run

    for entry in (_Machine, run):
        with pytest.raises(ValueError, match="modulus must"):
            entry("PRONOUNCE", ScriptedIO(), **settings)
