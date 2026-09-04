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

    old_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, 0.2)
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

    def test_a_difference_of_one_falls_through(self) -> None:
        """The branch is on ``<= 0``, so a difference of exactly 1 does not
        take it.

        Every other fall-through leaves a difference well above the
        boundary, so a threshold one higher would have agreed with all of
        them.  Here 5 - 4 = 1: falling through reaches the print, while
        taking the branch jumps straight past the end and prints nothing.
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
        (here held in mem[3]) halts execution."""
        assert run_bounded("10 0 3 -1 0 0 0") == ""

    def test_invalid_address_rejected(self) -> None:
        """An address below -3 is an invalid operation."""
        import pytest

        with pytest.raises(ValueError, match="invalid address"):
            run_bounded("-4 0 3 0 0 5 9")

    def test_output_advances_past_its_own_instruction(self) -> None:
        """A ``-3`` instruction moves on three cells from where it stands.

        Both output tests put the ``-3`` at address 0, where advancing by
        three and jumping to the fixed address 3 are the same thing, and
        where stepping *back* three leaves a negative pointer that halts
        after the character is already out.  Reaching the print from a
        jump separates them: from address 3, only a relative advance
        arrives at the instruction that ends the program, and either fixed
        landing runs the print again forever.
        """
        assert run_bounded("0 0 9  -3 10 0  0 0 11  3 67 99") == "C"
        assert run_bounded("0 0 9  10 -3 0  0 0 11  3 67 99") == "C"

    def test_a_write_to_the_pointer_redirects_the_fall_through(self) -> None:
        """Storing to ``-1`` is what moves the pointer, not the address 1.

        ``test_write_instruction_pointer`` writes to ``-1`` and asserts
        ``""``, which every program here prints -- so dropping the write,
        or aiming it at any other address, passed.  This one lands on the
        print: the difference 6 goes to the pointer and the fall-through
        adds three on top, reaching the ``-3`` at address 9.  Without the
        write the pointer advances to 3 instead, where the jump target is
        negative and the program stops with nothing printed.
        """
        assert run_bounded("-1 12 0  0 0 12  0 0 0  -3 13 0  -6 67") == "C"


class TestMemoryState:
    """Assertions on the memory a program leaves behind.

    S*bleq prints only through address -3, so a program that computes
    without printing has ``""`` for its whole observable behaviour -- and
    ``test_write_past_end_extends_memory_and_breaks`` asserts exactly that.
    Where the writes landed, and what padding they left, needs the memory.
    """

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
        """Address 0 is written like any other, not treated as special.

        Every other program writes to a positive address, so a bound that
        excluded 0 would have left them all passing.
        """
        assert self.final("0 1 3 7") == ([-1, 1, 3, 7], 7)

    def test_a_zero_difference_takes_the_jump(self) -> None:
        """The branch is on ``<= 0``: an exactly zero result jumps too.

        ``test_conditional_jump_on_zero`` jumps to a target that ends the
        program either way; here the jump's own target is 0, which a check
        rejecting non-positive targets would refuse to take.
        """
        assert self.final("1 1 0 0 0 0") == ([0, 0, 0, 0, 0, 0], 0)

    def test_falling_through_advances_by_one_instruction(self) -> None:
        """A positive result moves on three cells, it does not reset there.

        Every other program jumps or ends on its first instruction, where
        advancing past it and landing on a fixed third cell agree.  Running
        two in a row separates them: the second advance has to reach 6.
        """
        assert self.final("9 10 2 9 11 2 0 0 2") == (
            [9, 10, -7, 9, 11, 2, 0, 0, 2, 0],
            9,
        )

    def test_input_takes_the_first_byte_of_the_line(self) -> None:
        """``-2`` supplies one byte, and it is the first one.

        The existing input tests subtract the byte into a cell they then
        overwrite, so its value never shows.  Here it lands in cell 0 and
        stays: 'A' and 'AB' must agree, since only the first byte is read.
        """
        assert self.final("0 -2 3 -3 0 6 9", stdin="A")[0][0] == -65
        assert self.final("0 -2 3 -3 0 6 9", stdin="AB")[0][0] == -65

    def test_exhausted_input_reads_as_zero(self) -> None:
        """With no input left the subtraction uses 0, which leaves the cell
        unchanged rather than shifting it by one."""
        assert self.final("0 -2 3 -3 0 6 9", stdin="")[0][0] == 0


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

    def test_each_variant_writes_where_it_says(self) -> None:
        """Which cell receives the difference, which ``== ""`` cannot show.

        Both variant tests above assert no output, and S*bleq prints only
        through address -3 -- so a program that writes to the wrong cell,
        or to no cell, passes them.  Running the same instruction under
        each variant and reading the memory is what tells them apart.
        """
        program = "6 7 3 0 0 5 9 5 3"
        assert self.mem(program, "a")[6:8] == [4, 5]
        assert self.mem(program, "ab")[6:8] == [4, 4]
        assert self.mem(program, "b")[6:8] == [4, 4]

    def test_the_default_variant_stores_in_a(self) -> None:
        """``run`` defaults to the base language, which writes to a alone.

        Every other call passes ``store`` explicitly, so the default was
        free to be any of the three.  The base language writes only to a,
        which leaves b holding its original value where the other two
        variants overwrite it.
        """
        program = "6 7 3 0 0 5 9 5 3"
        assert self.mem(program) == self.mem(program, "a")
        assert self.mem(program) != self.mem(program, "b")

    @pytest.mark.parametrize("store", ["A", "AB", "B", "c", "", "bb", "abc"])
    def test_unknown_store_target_is_rejected(self, store: str) -> None:
        """A store outside the three variants raises rather than running.

        ``step`` tests ``store in ("ab", "b")``, so every unrecognised
        spelling used to fall through to the *base* language silently: a
        caller writing ``"A"`` for ``"a"`` got a wrong answer rather than an
        error, and ``"B"`` ran base S*bleq while claiming to be Subl*q.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        with pytest.raises(ValueError, match="unknown store target"):
            _Machine("0 0 0", ScriptedIO(""), store=store)

    def test_the_variant_reaches_run_and_shows_in_the_output(self) -> None:
        """``run`` forwards ``store``, and the choice is visible in print.

        Every variant test reads memory from a ``_Machine`` built by hand,
        so ``run`` could have dropped the argument on the floor and passed
        them all.  This program subtracts into a cell and then prints that
        same cell: base S*bleq leaves ``b`` alone and prints 3, while both
        storing variants overwrite it with the difference and print 2.
        """
        program = "9 10 3  -3 10 6  0 0 11  5 3 99"
        assert run_bounded(program, store="a") == "\x03"
        assert run_bounded(program, store="b") == "\x02"
        assert run_bounded(program, store="ab") == "\x02"

    def test_runs_own_default_is_the_base_language(self) -> None:
        """``run`` called with no ``store`` runs base S*bleq.

        Its default is never exercised -- ``run_bounded`` always passes one
        -- so the signature was free to name a variant, or a spelling the
        machine rejects outright.
        """
        buffer = io.StringIO()

        class _IO(IO):
            def _read(self, _prompt: str) -> str:
                return ""

            def _write(self, value: object) -> None:
                buffer.write(str(value))

        run("9 10 3  -3 10 6  0 0 11  5 3 99", _IO())
        assert buffer.getvalue() == "\x03"

    def test_a_variant_stores_into_address_zero(self) -> None:
        """``b`` is an address, and address 0 is one of them.

        The variant's write is guarded on ``b >= 0``, which only address 0
        distinguishes from a positive-only bound -- and every variant test
        so far uses ``b = 7``.  With ``b = 0`` the base language leaves
        cell 0 holding the address it read, while both storing variants
        replace it with the difference.
        """
        program = "5 0 8 0 0 0 0 0 9 3"
        assert self.mem(program, "a")[0] == 5
        assert self.mem(program, "b")[0] == -5
        assert self.mem(program, "ab")[0] == -5

    @pytest.mark.parametrize("store", ["a", "ab", "b"])
    def test_documented_store_targets_are_accepted(self, store: str) -> None:
        """The three wiki variants stay constructible.

        The positive half of the check above: a guard that rejected
        everything would pass that test just as well.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.sbleq import _Machine

        assert _Machine("0 0 0", ScriptedIO(""), store=store).store == store

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
    """Comments and whitespace, via the shared ``parse_int_memory``.

    S*bleq once parsed with a bare ``code.split()`` of its own, which made it
    the only OISC in the package that rejected ``#`` comments -- and it
    rejected them with a raw ``int()`` message rather than the package's.
    Its compiler already used the shared parser, so a commented program
    compiled but would not interpret.
    """

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
