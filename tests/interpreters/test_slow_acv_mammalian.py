"""Unit tests for the SLOW ACV SLOW ACV MAMMALIAN interpreter."""

import io
from contextlib import redirect_stdout
from pathlib import Path

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
        # A character past U+00FF is the only way the fold exceeds a byte,
        # so it is what pins the wrap: 321 % 256 is 65, where 257 gives 64.
        assert accepted("Ł\n") == [0, 65], "the fold wraps at 256"

    def test_values_wrap_at_a_byte(self) -> None:
        """Every stored or printed value is reduced modulo 256, not 257.

        The two are indistinguishable until something actually reaches 256,
        which nothing in the suite did -- the accumulator is usually built
        by ``DIGEST``, an XOR that cannot exceed its operands.  ``SEED``
        adds and ``ACCEPT`` folds in a byte, and 255 XOR 1 is 254 while
        255 + 1 is 256: the one value the two moduli disagree about.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        # SEED puts 1 in lst[0]; ACCEPT folds 0xff against acc 0 and appends
        # it; DIGEST xors the accumulator with the sum, giving 256.
        machine = _Machine("SEED ACCEPT DIGEST PRONOUNCE", ScriptedIO("\xff\n"))
        while not machine.halted:
            machine.step()
        assert machine.acc == 256
        assert machine.io.getvalue() == "\x00"

    def test_seed_wraps_its_register_at_a_byte(self) -> None:
        """``SEED``'s addition wraps too, at the same 256.

        The head has to be carried to 255 first, which ``ACCEPT`` can do
        with a 0xff byte: seeding it once more makes 256 and stores 0.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("CONSUME ACCEPT SEED", ScriptedIO("\xff\n"))
        while not machine.halted:
            machine.step()
        assert machine.lst[0] == [0]

    def test_sprint_needs_a_position_inside_the_array(self) -> None:
        """``SPRINT`` is a NOP unless the accumulator indexes a real cell.

        The wiki makes a too-large ``x`` do nothing, and the bound is off
        by one from the length: on an empty array even 0 is too large.
        Comparing inclusively would index a cell that is not there.
        """
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("CONSUME SPRINT", IO())
        while not machine.halted:
            machine.step()
        assert machine.lst[0] == []
        assert machine.ptr == 0


class TestStepMachine:
    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("", IO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.lst == [[0] for _ in range(23)]

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

    def test_consume_takes_the_middle_cell(self) -> None:
        """``CONSUME`` pops ``(len - 1) // 2``, the lower of the two middles.

        An even length hides which midpoint is meant, since the two
        candidate expressions agree there; an odd one separates them.  On
        three cells the middle is index 1, where counting from a shorter
        length would take the head instead.
        """
        from esolangs.interpreters.tape_based.slow_acv_mammalian import partial

        curr = [10, 11, 12]
        assert partial(3, curr, 0) == 11
        assert curr == [10, 12]

    def test_fission_splits_the_middle_cell(self) -> None:
        """``FISSION`` halves the same middle cell and hangs it off both ends."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import partial

        curr = [10, 12, 14]
        assert partial(4, curr, 3) == 3
        assert curr == [6, 10, 14, 6]

    def test_excrete_stores_the_accumulator_modulo_a_byte(self) -> None:
        """``EXCRETE`` appends ``acc % 256`` and clears the accumulator.

        Nothing in the suite fed it a value at or above 256, so the wrap
        itself was untested and 257 would have done just as well.
        """
        from esolangs.interpreters.tape_based.slow_acv_mammalian import partial

        curr: list[int] = []
        assert partial(2, curr, 256) == 0
        assert curr == [0]
        assert partial(2, curr, 321) == 0
        assert curr == [0, 65]


class TestTotal:
    """``total`` is the published mutating shape for the whole-memory ops."""

    def test_seed_adds_each_arrays_index_to_its_head(self) -> None:
        """``SEED`` adds ``index + 1`` to every array's first cell.

        The offset is what separates the arrays: a shell that dropped the
        index would give all 23 the same head.  Only the head moves, so a
        second cell pins that the rest of the array is left alone.
        """
        from esolangs.interpreters.tape_based.slow_acv_mammalian import total

        lst = [[10, 0] for _ in range(23)]
        total(0, lst)
        assert [arr[0] for arr in lst] == [11 + k for k in range(23)]
        assert all(arr[1] == 0 for arr in lst)

    def test_seed_skips_an_empty_array(self) -> None:
        """An empty array has no head to seed, so it stays empty.

        The arrays still count for the offset, though -- index 5 is seeded
        with 6, not with whatever a re-numbering over the non-empty ones
        would have given it.
        """
        from esolangs.interpreters.tape_based.slow_acv_mammalian import total

        lst: list[list[int]] = [[] for _ in range(23)]
        lst[5] = [1]
        total(0, lst)
        assert lst[0] == []
        assert lst[5] == [7]

    def test_conflagrate_pairs_the_flattened_memory(self) -> None:
        """``CONFLAGRATE`` folds the memory end to end, across array bounds.

        The write-back is the part the shell owns: the pure core returns
        tuples, and the caller's own lists have to carry the result.
        """
        from esolangs.interpreters.tape_based.slow_acv_mammalian import total

        lst: list[list[int]] = [[] for _ in range(23)]
        lst[0] = [9, 2]
        total(1, lst)
        assert lst[0] == [5, 6]


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

    def test_a_target_of_zero_is_a_jump_rather_than_a_halt(self) -> None:
        """Zero is a legal target: only a *negative* one halts.

        The halting case above lands on -1 and the jumping case on 1, so
        the boundary between them went untested -- a floor of 1, or an
        inclusive comparison against 0, behaves the same at both.  Here
        ``acc`` 1 against a head of 0 gives exactly 0, which jumps.
        """
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("LEAPFROG PRONOUNCE", IO())
        machine.lst[0] = [0, 5]
        machine.acc = 1
        machine.step()
        assert not machine.halted
        assert machine.ind == 1

    def test_the_target_subtracts_the_head_from_the_accumulator(self) -> None:
        """``target`` is ``acc - head - 1``, so a larger head jumps lower.

        Every case above uses a head of 0, where adding and subtracting it
        agree.  A non-zero head separates them: 5 against an accumulator of
        8 gives 2, where adding would give 12 and run off the end.
        """
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("LEAPFROG PRONOUNCE PRONOUNCE PRONOUNCE", IO())
        machine.lst[0] = [5, 7]
        machine.acc = 8
        machine.step()
        assert not machine.halted
        assert machine.ind == 3

    def test_leapfrog_reads_the_last_cell_to_decide_whether_to_jump(self) -> None:
        """The guard is the array's *last* value, not its second.

        On one or two cells the two lookups coincide, so the array needs a
        third to separate them: here the tail is 0 and the middle is 5, so
        the jump must not fire.  A guard reading the second cell sees the 5
        and jumps instead.
        """
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("LEAPFROG PRONOUNCE", IO())
        machine.lst[0] = [0, 5, 0]
        machine.acc = 9
        machine.step()
        assert not machine.halted
        assert machine.ind == 1  # fell through rather than jumping to 8


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "SEED PRONOUNCE"
