"""Unit tests for the S*bleq interpreter."""

import io
import signal

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.sbleq import run


class _TimeoutError(Exception):
    """Raised when an S*bleq program does not terminate."""


def _on_alarm(_signum: int, _frame: object) -> None:
    raise _TimeoutError


def run_bounded(program: str, stdin: str = "", store: str = "a") -> str:
    """Run ``program`` with a one-second cap; return its output."""
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
    """The single subtract-and-branch instruction."""

    def test_conditional_jump_on_zero(self) -> None:
        """A zero result jumps to the address stored in ``c``."""
        # ip0: 0 - 0 = 0 -> jump to mem[2]=9, past the end.
        assert run_bounded("0 0 2 9 0") == ""

    def test_conditional_jump_on_negative(self) -> None:
        """A negative result also jumps."""
        # ip0: 0 - 5 = -5 -> jump to mem[2]=9, past the end.
        assert run_bounded("0 5 2 9 0") == ""

    def test_negative_target_halts(self) -> None:
        """A ``c`` address holding a negative value stops execution."""
        # ip0: 0 - 0 = 0 -> jump to mem[2]; mem[2] holds -1, a negative
        # target, so execution stops.
        assert run_bounded("0 0 2 -1") == ""

    def test_special_addresses_are_not_branch_operands(self) -> None:
        """``c`` is an address, not an operand port."""
        with pytest.raises(ValueError, match="invalid S\\*bleq branch address"):
            run_bounded("0 0 -1")

    def test_a_difference_of_one_falls_through(self) -> None:
        """The branch is on ``<= 0``, so a difference of exactly 1 does not
        take it.
        """
        assert run_bounded("9 10 11  -3 12 0  0 0 13  5 4 99 67 99") == "C"


class TestSpecialAddresses:
    """The -1 (IP), -2 (input), and -3 (output) addresses."""

    def test_output_via_a_negative_three(self) -> None:
        """``-3`` in ``a`` outputs the value at ``b``."""
        # ip0: a=-3, b=6 -> output mem[6]=65 'A'; ip3: 0-0=0 -> jump to
        # mem[5]=9 (mem[5] is 9, past the end) -> halt.
        assert run_bounded("-3 6 3 0 0 7 65 9") == "A"

    def test_output_via_b_negative_three(self) -> None:
        """``-3`` in ``b`` outputs the value at ``a``."""
        # ip0: a=6, b=-3 -> output mem[6]=66 'B'; ip3: 0-0=0 -> jump to
        # mem[5]=9 -> halt.
        assert run_bounded("6 -3 3 0 0 7 66 9") == "B"

    def test_input_reads_byte(self) -> None:
        """``-2`` as ``a`` supplies the next input byte in the subtraction."""
        # ip0: a=-2 (input 'A'=65), b=0 (mem[0] is -2): 65 - (-2) = 67 (>0,
        # no jump) -> ip3.  ip3: 0-0=0 -> jump to mem[5]=9 -> halt.
        assert run_bounded("-2 0 3 0 0 5 9", stdin="A") == ""

    def test_input_eof_reads_zero(self) -> None:
        """``-2`` on exhausted input reads as zero."""
        # Same program with no input: the subtraction uses 0 in place of EOF.
        assert run_bounded("-2 0 3 0 0 5 9", stdin="") == ""

    def test_read_instruction_pointer(self) -> None:
        """``-1`` as an operand reads the current instruction pointer."""
        # ip0: a=2, b=-1 (the ip, currently 0): 2 - 0 = 2 > 0, falls through;
        # ip3: 0-0=0 -> jump to mem[5]=9, past the end.
        assert run_bounded("2 -1 3 0 0 5 9") == ""

    def test_write_instruction_pointer(self) -> None:
        """Storing to ``-1`` moves the instruction pointer."""
        # ip0: a=-1: diff = ip(0) - mem[0](-1) = 1, written back to the ip;
        # the positive result falls through and the program ends off the end.
        assert run_bounded("-1 0 3 6 0 0 0") == ""

    def test_write_past_end_extends_memory_and_breaks(self) -> None:
        """Writing past the program end extends memory; a negative target
        (here held in mem[3]) halts execution.
        """
        assert run_bounded("10 0 3 -1 0 0 0") == ""

    def test_invalid_address_rejected(self) -> None:
        """An address below -3 is an invalid operation."""
        import pytest

        with pytest.raises(ValueError, match="invalid address"):
            run_bounded("-4 0 3 0 0 5 9")

    def test_output_advances_past_its_own_instruction(self) -> None:
        """A ``-3`` instruction moves on three cells from where it stands."""
        assert run_bounded("0 0 9  -3 10 0  0 0 11  3 67 99") == "C"
        assert run_bounded("0 0 9  10 -3 0  0 0 11  3 67 99") == "C"

    def test_a_write_to_the_pointer_redirects_the_fall_through(self) -> None:
        """Storing to ``-1`` is what moves the pointer, not the address 1."""
        assert run_bounded("-1 12 0  0 0 12  0 0 0  -3 13 0  -6 67") == "C"


class TestMemoryState:
    """Assertions on the memory a program leaves behind."""

    def final(
        self, program: str, stdin: str = "", steps: int = 200
    ) -> tuple[list[int], int]:
        """Run at most ``steps`` instructions; S*bleq programs may not halt."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        machine = _Machine(program, ScriptedIO(stdin))
        for _ in range(steps):
            if machine.halted:
                break
            machine.step()
        return list(machine.mem), machine.ip

    def test_writing_past_the_end_pads_with_zeros(self) -> None:
        """Memory grows to reach the address, and the new cells hold 0."""
        assert self.final("5 5 9") == ([5, 5, 9, 0, 0, 0], 0)

    def test_address_zero_is_an_ordinary_cell(self) -> None:
        """Address 0 is written like any other, not treated as special."""
        assert self.final("0 1 3 7") == ([-1, 1, 3, 7], 7)

    def test_falling_through_advances_by_one_instruction(self) -> None:
        """A positive result moves on three cells, it does not reset there."""
        assert self.final("9 10 2 9 11 2 0 0 2") == (
            [9, 10, -7, 9, 11, 2, 0, 0, 2, 0],
            9,
        )

    def test_input_takes_the_first_byte_of_the_line(self) -> None:
        """``-2`` supplies one byte, and it is the first one."""
        assert self.final("0 -2 3 -3 0 6 9", stdin="A")[0][0] == -65
        assert self.final("0 -2 3 -3 0 6 9", stdin="AB")[0][0] == -65

    def test_exhausted_input_reads_as_zero(self) -> None:
        """With no input left the subtraction uses 0, which leaves the cell
        unchanged rather than shifting it by one.
        """
        assert self.final("0 -2 3 -3 0 6 9", stdin="")[0][0] == 0

    def test_a_zero_difference_takes_the_jump(self) -> None:
        """The branch is on ``<= 0``: an exactly zero result jumps too."""
        assert self.final("1 1 0 0 0 0") == ([0, 0, 0, 0, 0, 0], 0)


class TestVariants:
    """The store-target variants (S*bl*q stores in a and b; Subl*q in b)."""

    def test_each_variant_writes_where_it_says(self) -> None:
        """Which cell receives the difference, which ``== ""`` cannot show."""
        program = "6 7 3 0 0 5 9 5 3"
        assert self.mem(program, "a")[6:8] == [4, 5]
        assert self.mem(program, "ab")[6:8] == [4, 4]
        # Wiki rev 188944: "Subl*q ... result of subtraction is stored in b".
        assert self.mem(program, "b")[6:8] == [9, 4]

    @pytest.mark.parametrize(("store", "ip"), [("a", 3), ("ab", 9), ("b", 9)])
    def test_a_b_store_to_minus_one_moves_the_pointer(
        self, store: str, ip: int
    ) -> None:
        """Pins b=-1 writes: ``5 -1 0`` stores 6-0 into the IP, then +3 -> 9."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        machine = _Machine("5 -1 0 0 0 6", ScriptedIO(""), store=store)
        machine.step()
        assert machine.ip == ip

    def test_a_huge_invalid_address_is_reported_in_full(self) -> None:
        """Pins format_integer: a 5001-digit operand past CPython's 4300 cap."""
        big = "1" + "0" * 5000
        with pytest.raises(ValueError, match=f"invalid address -{big}(?!\\d)"):
            run_bounded(f"-{big} 0 3 0 0 5 9")

    def test_the_variant_reaches_run_and_shows_in_the_output(self) -> None:
        """``run`` forwards ``store``, and the choice is visible in print."""
        program = "9 10 3  -3 10 6  0 0 11  5 3 99"
        assert run_bounded(program, store="a") == "\x03"
        assert run_bounded(program, store="b") == "\x02"
        assert run_bounded(program, store="ab") == "\x02"

    def test_a_variant_stores_into_address_zero(self) -> None:
        """``b`` is an address, and address 0 is one of them."""
        program = "5 0 8 0 0 0 0 0 9 3"
        assert self.mem(program, "a")[0] == 5
        assert self.mem(program, "b")[0] == -5
        assert self.mem(program, "ab")[0] == -5

    def mem(self, program: str, store: str = "a", steps: int = 200) -> list[int]:
        """Return the memory ``program`` leaves under the ``store`` variant."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        machine = _Machine(program, ScriptedIO(""), store=store)
        for _ in range(steps):
            if machine.halted:
                break
            machine.step()
        return list(machine.mem)

    @pytest.mark.parametrize("store", ["a", "ab", "b"])
    def test_documented_store_targets_are_accepted(self, store: str) -> None:
        """The three wiki variants stay constructible."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        assert _Machine("0 0 0", ScriptedIO(""), store=store).store == store

    def test_runs_own_default_is_the_base_language(self) -> None:
        """``run`` called with no ``store`` runs base S*bleq."""
        buffer = io.StringIO()

        class _IO(IO):
            def _read(self, _prompt: str) -> str:
                return ""

            def _write(self, value: object) -> None:
                buffer.write(str(value))

        run("9 10 3  -3 10 6  0 0 11  5 3 99", _IO())
        assert buffer.getvalue() == "\x03"

    def test_sblq_stores_in_both(self) -> None:
        """``store="ab"`` writes the difference to both a and b."""
        # ip0: a=6, b=7: mem[6]=5 - mem[7]=3 = 2, stored in both mem[6] and
        # mem[7]; a positive result falls through to ip3 where 0-0=0 jumps to
        # mem[5]=9 -> halt.
        assert run_bounded("6 7 3 0 0 5 9 5 3", store="ab") == ""

    def test_subleq_store_in_b(self) -> None:
        """``store="b"`` writes the difference to b only."""
        # Same program; store="b" writes only to mem[7], leaving mem[6]=9.
        assert run_bounded("6 7 3 0 0 5 9 5 3", store="b") == ""

    def test_the_default_variant_stores_in_a(self) -> None:
        """``run`` defaults to the base language, which writes to a alone."""
        program = "6 7 3 0 0 5 9 5 3"
        assert self.mem(program) == self.mem(program, "a")
        assert self.mem(program) != self.mem(program, "b")

    @pytest.mark.parametrize("store", ["A", "AB", "B", "c", "", "bb", "abc"])
    def test_unknown_store_target_is_rejected(self, store: str) -> None:
        """A store outside the three variants raises rather than running."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        with pytest.raises(ValueError, match="unknown store target"):
            _Machine("0 0 0", ScriptedIO(""), store=store)


class TestSnapshot:
    def test_snapshot_is_hashable_and_tracks_progress(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        machine = _Machine("3 4 6 1 1 0 0 0 0", ScriptedIO(""))
        before = machine.snapshot()
        hash(before)  # must not raise
        machine.step()
        assert machine.snapshot() != before


class TestProgramText:
    """Comments and whitespace, via the shared ``parse_int_memory``."""

    def test_comment_is_ignored(self) -> None:
        """``#`` starts a comment that runs to the end of its line."""
        program = "-3 6 3 # print, then halt\n0 0 7 65 9"
        assert run_bounded(program) == "A"

    def test_comment_only_program_is_empty(self) -> None:
        assert run_bounded("# nothing but a comment") == ""

    def test_malformed_token_raises_package_error(self) -> None:
        """A non-integer token is a ``ValueError`` naming the token."""
        with pytest.raises(ValueError, match="malformed memory token: 'x'"):
            run_bounded("0 0 x")
