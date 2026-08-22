"""Unit tests for the SLOW ACV SLOW ACV MAMMALIAN interpreter."""

import io
from contextlib import redirect_stdout
from pathlib import Path

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.slow_acv_mammalian import run


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestMammalian:
    def test_seed_adds_to_each_register(self) -> None:
        """SEED adds 1..23 to each list head; three SEEDs then CONSUME -> 3."""
        assert run_and_capture("SEED SEED SEED CONSUME PRONOUNCE") == "\x03"

    def test_pronomce_default(self) -> None:
        assert run_and_capture("PRONOUNCE") == "\x00"

    def test_hello_world(self) -> None:
        """Hello World program from the language docs."""
        program = Path(__file__).parents[2] / "tests/fixtures/mammalian.txt"
        assert run_and_capture(program.read_text()) == "Hello, world!\n"


class TestStepMachine:
    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("", IO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.lst == [[0] for _ in range(23)]
