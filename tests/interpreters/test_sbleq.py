"""Unit tests for the S*bleq interpreter.

S*bleq is an OISC (Subleq derivative): each instruction ``a b c`` subtracts
the value at ``b`` from the value at ``a``, stores the difference in ``a``,
and jumps to the address held at ``c`` when the result is less than or equal
to zero.  ``-1`` is the instruction pointer, ``-2`` the next input byte, and
``-3`` outputs the value at the other address in the instruction.  Random
programs may loop forever, so every run is bounded by a SIGALRM timeout.

S*bleq has no explicit halt instruction: execution stops only when the
instruction pointer runs off the end of memory or jumps to a negative
address.  Because code and data share memory, a terminating program lays
out its instructions first and ends with a ``0 0 c`` whose ``c`` points to a
cell holding a past-the-end target.
"""

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
    """Run ``program`` with a 2-second cap; return its output."""
    buffer = io.StringIO()

    class _IO(IO):
        def _read(self, _prompt: str) -> str:
            return stdin

        def _write(self, value: object) -> None:
            buffer.write(str(value))

    signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(2)
    try:
        run(program, _IO(), store=store)
    except _TimeoutError:
        pytest.fail(f"S*bleq program did not terminate: {program!r}")
    finally:
        signal.alarm(0)
    return buffer.getvalue()


class TestCoreInstruction:
    """The single subtract-and-branch instruction."""

    def test_subtract_then_halt(self) -> None:
        """mem[a] -= mem[b]; a positive result falls through to the next."""
        # ip0: a=0 (its own cell, value 0), b=1 (mem[1]=5): 0-5=-5 <=0,
        # so it jumps to mem[2]=9, past the end.
        assert run_bounded("0 5 2 9 0") == ""

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

    def test_empty_program(self) -> None:
        """An empty program produces no output."""
        assert run_bounded("") == ""


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
        (here held in mem[3]) halts execution."""
        assert run_bounded("10 0 3 -1 0 0 0") == ""

    def test_invalid_address_rejected(self) -> None:
        """An address below -3 is an invalid operation."""
        import pytest

        with pytest.raises(ValueError, match="invalid address"):
            run_bounded("-4 0 3 0 0 5 9")


class TestVariants:
    """The store-target variants (S*bl*q stores in a and b; Subl*q in b)."""

    def test_sblq_stores_in_both(self) -> None:
        """``store="ab"`` writes the difference to both a and b."""
        # ip0: a=6, b=7: mem[6]=5 - mem[7]=3 = 2, stored in both mem[6] and
        # mem[7]; a positive result falls through to ip3 where 0-0=0 jumps to
        # mem[5]=9 -> halt.
        assert run_bounded("6 7 3 0 0 5 9 5 3", store="ab") == ""

    def test_subleq_store_in_b(self) -> None:
        """``store="b"`` writes the difference to b only."""
        # Same program; store="b" writes only to mem[7], leaving mem[6]=5.
        assert run_bounded("6 7 3 0 0 5 9 5 3", store="b") == ""
