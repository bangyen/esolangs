r"""Unit tests for the S*bleq interpreter."""

import io
import signal

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.sbleq import run


class _TimeoutError(Exception):
    r"""Raised when an S*bleq program does not terminate."""


def _on_alarm(_signum: int, _frame: object) -> None:
    raise _TimeoutError


def run_bounded(program: str, stdin: str = "", store: str = "a") -> str:
    r"""Run ``program`` with a one-second cap; return its output."""
    buffer = io.StringIO()

    class _IO(IO):
        def _read(self, _prompt: str) -> str:
            return stdin

        def _write(self, value: object) -> None:
            buffer.write(str(value))

    old_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, 1.0)
    try:
        run(program, _IO(), store=store)
    except _TimeoutError:
        pytest.fail(f"S*bleq program did not terminate: {program!r}")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
    return buffer.getvalue()


class TestCoreInstruction:
    r"""The single subtract-and-branch instruction."""

    def test_conditional_jump_on_zero(self) -> None:
        r"""A zero result jumps to the address stored in ``c``."""
        # ip0: 0 - 0 = 0 -> jump to.
        assert run_bounded("0 0 2 9 0") == ""

    def test_conditional_jump_on_negative(self) -> None:
        r"""A negative result also jumps."""
        # ip0: 0 - 5 = -5 -> jump to.
        assert run_bounded("0 5 2 9 0") == ""

    def test_negative_target_halts(self) -> None:
        r"""A ``c`` address holding a negative value stops execution."""
        # ip0: 0 - 0 = 0 -> jump to.
        # target, so execution stops.
        assert run_bounded("0 0 2 -1") == ""

    def test_empty_program(self) -> None:
        r"""An empty program produces no output."""
        assert run_bounded("") == ""

    def test_a_difference_of_one_falls_through(self) -> None:
        r"""The branch is on ``<= 0``, so a difference of exactly 1 does not."""
        assert run_bounded("9 10 11  -3 12 0  0 0 13  5 4 99 67 99") == "C"


class TestSpecialAddresses:
    r"""The -1 (IP), -2 (input), and -3 (output) addresses."""

    def test_output_via_a_negative_three(self) -> None:
        r"""``-3`` in ``a`` outputs the value at ``b``."""
        # ip0: a=-3, b=6 -> output.
        # mem[5]=9 (mem[5] is 9, past.
        assert run_bounded("-3 6 3 0 0 7 65 9") == "A"

    def test_output_via_b_negative_three(self) -> None:
        r"""``-3`` in ``b`` outputs the value at ``a``."""
        # ip0: a=6, b=-3 -> output.
        # mem[5]=9 -> halt.
        assert run_bounded("6 -3 3 0 0 7 66 9") == "B"

    def test_input_reads_byte(self) -> None:
        r"""``-2`` as ``a`` supplies the next input byte in the subtraction."""
        # ip0: a=-2 (input 'A'=65), b=0.
        # no jump) -> ip3.
        assert run_bounded("-2 0 3 0 0 5 9", stdin="A") == ""

    def test_input_eof_reads_zero(self) -> None:
        r"""``-2`` on exhausted input reads as zero."""
        # Same program with no input:.
        assert run_bounded("-2 0 3 0 0 5 9", stdin="") == ""

    def test_read_instruction_pointer(self) -> None:
        r"""``-1`` as an operand reads the current instruction pointer."""
        # ip0: a=2, b=-1 (the ip,.
        # ip3: 0-0=0 -> jump to.
        assert run_bounded("2 -1 3 0 0 5 9") == ""

    def test_write_instruction_pointer(self) -> None:
        r"""Storing to ``-1`` moves the instruction pointer."""
        # ip0: a=-1: diff = ip(0) -.
        # the positive result falls.
        assert run_bounded("-1 0 3 6 0 0 0") == ""

    def test_write_past_end_extends_memory_and_breaks(self) -> None:
        r"""Writing past the program end extends memory; a negative target."""
        assert run_bounded("10 0 3 -1 0 0 0") == ""

    def test_invalid_address_rejected(self) -> None:
        r"""An address below -3 is an invalid operation."""
        import pytest

        with pytest.raises(ValueError, match="invalid address"):
            run_bounded("-4 0 3 0 0 5 9")

    def test_output_advances_past_its_own_instruction(self) -> None:
        r"""A ``-3`` instruction moves on three cells from where it stands."""
        assert run_bounded("0 0 9  -3 10 0  0 0 11  3 67 99") == "C"
        assert run_bounded("0 0 9  10 -3 0  0 0 11  3 67 99") == "C"

    def test_a_write_to_the_pointer_redirects_the_fall_through(self) -> None:
        r"""Storing to ``-1`` is what moves the pointer, not the address 1."""
        assert run_bounded("-1 12 0  0 0 12  0 0 0  -3 13 0  -6 67") == "C"


class TestMemoryState:
    r"""Assertions on the memory a program leaves behind."""

    def final(
        self, program: str, stdin: str = "", steps: int = 200
    ) -> tuple[list[int], int]:
        r"""Run at most ``steps`` instructions; S*bleq programs may not halt."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        machine = _Machine(program, ScriptedIO(stdin))
        for _ in range(steps):
            if machine.halted:
                break
            machine.step()
        return list(machine.mem), machine.ip

    def test_writing_past_the_end_pads_with_zeros(self) -> None:
        r"""Memory grows to reach the address, and the new cells hold 0."""
        assert self.final("5 5 9") == ([5, 5, 9, 0, 0, 0], 0)

    def test_address_zero_is_an_ordinary_cell(self) -> None:
        r"""Address 0 is written like any other, not treated as special."""
        assert self.final("0 1 3 7") == ([-1, 1, 3, 7], 7)

    def test_a_zero_difference_takes_the_jump(self) -> None:
        r"""The branch is on ``<= 0``: an exactly zero result jumps too."""
        assert self.final("1 1 0 0 0 0") == ([0, 0, 0, 0, 0, 0], 0)

    def test_falling_through_advances_by_one_instruction(self) -> None:
        r"""A positive result moves on three cells, it does not reset there."""
        assert self.final("9 10 2 9 11 2 0 0 2") == (
            [9, 10, -7, 9, 11, 2, 0, 0, 2, 0],
            9,
        )

    def test_input_takes_the_first_byte_of_the_line(self) -> None:
        r"""``-2`` supplies one byte, and it is the first one."""
        assert self.final("0 -2 3 -3 0 6 9", stdin="A")[0][0] == -65
        assert self.final("0 -2 3 -3 0 6 9", stdin="AB")[0][0] == -65

    def test_exhausted_input_reads_as_zero(self) -> None:
        r"""With no input left the subtraction uses 0, which leaves the cell."""
        assert self.final("0 -2 3 -3 0 6 9", stdin="")[0][0] == 0


class TestVariants:
    r"""The store-target variants (S*bl*q stores in a and b; Subl*q in b)."""

    def test_sblq_stores_in_both(self) -> None:
        r"""``store="ab"`` writes the difference to both a and b."""
        # ip0: a=6, b=7: mem[6]=5 -.
        # mem[7]; a positive result.
        # mem[5]=9 -> halt.
        assert run_bounded("6 7 3 0 0 5 9 5 3", store="ab") == ""

    def test_subleq_store_in_b(self) -> None:
        r"""``store="b"`` writes the difference to b only."""
        # Same program; store="b".
        assert run_bounded("6 7 3 0 0 5 9 5 3", store="b") == ""

    def test_each_variant_writes_where_it_says(self) -> None:
        r"""Which cell receives the difference, which ``== ""`` cannot show."""
        program = "6 7 3 0 0 5 9 5 3"
        assert self.mem(program, "a")[6:8] == [4, 5]
        assert self.mem(program, "ab")[6:8] == [4, 4]
        assert self.mem(program, "b")[6:8] == [4, 4]

    def test_the_default_variant_stores_in_a(self) -> None:
        r"""``run`` defaults to the base language, which writes to a alone."""
        program = "6 7 3 0 0 5 9 5 3"
        assert self.mem(program) == self.mem(program, "a")
        assert self.mem(program) != self.mem(program, "b")

    @pytest.mark.parametrize("store", ["A", "AB", "B", "c", "", "bb", "abc"])
    def test_unknown_store_target_is_rejected(self, store: str) -> None:
        r"""A store outside the three variants raises rather than running."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        with pytest.raises(ValueError, match="unknown store target"):
            _Machine("0 0 0", ScriptedIO(""), store=store)

    def test_the_variant_reaches_run_and_shows_in_the_output(self) -> None:
        r"""``run`` forwards ``store``, and the choice is visible in print."""
        program = "9 10 3  -3 10 6  0 0 11  5 3 99"
        assert run_bounded(program, store="a") == "\x03"
        assert run_bounded(program, store="b") == "\x02"
        assert run_bounded(program, store="ab") == "\x02"

    def test_runs_own_default_is_the_base_language(self) -> None:
        r"""``run`` called with no ``store`` runs base S*bleq."""
        buffer = io.StringIO()

        class _IO(IO):
            def _read(self, _prompt: str) -> str:
                return ""

            def _write(self, value: object) -> None:
                buffer.write(str(value))

        run("9 10 3  -3 10 6  0 0 11  5 3 99", _IO())
        assert buffer.getvalue() == "\x03"

    def test_a_variant_stores_into_address_zero(self) -> None:
        r"""``b`` is an address, and address 0 is one of them."""
        program = "5 0 8 0 0 0 0 0 9 3"
        assert self.mem(program, "a")[0] == 5
        assert self.mem(program, "b")[0] == -5
        assert self.mem(program, "ab")[0] == -5

    @pytest.mark.parametrize("store", ["a", "ab", "b"])
    def test_documented_store_targets_are_accepted(self, store: str) -> None:
        r"""The three wiki variants stay constructible."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        assert _Machine("0 0 0", ScriptedIO(""), store=store).store == store

    def mem(self, program: str, store: str = "a", steps: int = 200) -> list[int]:
        r"""Return the memory ``program`` leaves under the ``store`` variant."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        machine = _Machine(program, ScriptedIO(""), store=store)
        for _ in range(steps):
            if machine.halted:
                break
            machine.step()
        return list(machine.mem)


class TestSnapshot:
    def test_snapshot_is_hashable_and_tracks_progress(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        machine = _Machine("3 4 6 1 1 0 0 0 0", ScriptedIO(""))
        before = machine.snapshot()
        hash(before)  # must not raise.
        machine.step()
        assert machine.snapshot() != before


class TestProgramText:
    r"""Comments and whitespace, via the shared ``parse_int_memory``."""

    def test_comment_is_ignored(self) -> None:
        r"""``#`` starts a comment that runs to the end of its line."""
        program = "-3 6 3 # print, then halt\n0 0 7 65 9"
        assert run_bounded(program) == "A"

    def test_comment_only_program_is_empty(self) -> None:
        assert run_bounded("# nothing but a comment") == ""

    def test_malformed_token_raises_package_error(self) -> None:
        r"""A non-integer token is a ``ValueError`` naming the token."""
        with pytest.raises(ValueError, match="malformed memory token: 'x'"):
            run_bounded("0 0 x")
