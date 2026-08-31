"""Unit tests for the SLOW ACV SLOW ACV MAMMALIAN interpreter."""

import io
from contextlib import redirect_stdout
from pathlib import Path

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.slow_acv_mammalian import run
from tests.interpreters.contract import SnapshotContract


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

    def test_accept_on_a_blank_line_appends_nothing(self) -> None:
        """``ACCEPT`` takes the first byte of a line, and a blank line has none.

        Reading is by line, so an empty one is a real answer rather than
        end-of-input -- exhausted input raises ``EOFError`` instead.  With
        no byte to fold against the accumulator there is nothing to append,
        and the list is left as it was.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        def accepted(stdin: str) -> list[int]:
            machine = _Machine("ACCEPT", ScriptedIO(stdin))
            machine.step()
            return machine.lst[0]

        assert accepted("\n") == [0], "a blank line appends nothing"
        assert accepted("A\n") == [0, 65], "a byte is folded in and appended"


class TestStepMachine:
    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("", IO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.lst == [[0] for _ in range(23)]


class TestPartial:
    """``partial`` applies one array op, and two of them need a non-empty array."""

    def test_consume_of_an_empty_array_leaves_the_accumulator(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import partial

        curr: list[int] = []
        assert partial(3, curr, 7) == 7
        assert curr == []

    def test_fission_of_an_empty_array_leaves_the_accumulator(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import partial

        curr: list[int] = []
        assert partial(4, curr, 7) == 7
        assert curr == []


class TestLeapfrog:
    """``LEAPFROG`` jumps the cursor, or halts when the target is negative."""

    def test_a_negative_target_halts(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        # acc 0 and a head of 0 give target -1, which halts instead of jumping.
        machine = _Machine("LEAPFROG PRONOUNCE", IO())
        machine.lst[0] = [0, 5]  # non-empty with a truthy tail: the branch fires
        machine.step()
        assert machine.halted

    def test_a_non_negative_target_moves_the_cursor(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        # acc 2, head 0 -> target 1; the step's trailing advance then makes
        # it 2, so the jump is what puts the cursor there rather than at 1.
        machine = _Machine("LEAPFROG PRONOUNCE PRONOUNCE", IO())
        machine.lst[0] = [0, 5]
        machine.acc = 2
        machine.step()
        assert not machine.halted
        assert machine.ind == 2


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "SEED PRONOUNCE"
