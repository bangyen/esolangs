r"""Unit tests for the SLOW ACV SLOW ACV MAMMALIAN interpreter."""

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
        r"""SEED adds 1..23 to each list head; three SEEDs then CONSUME -> 3."""
        assert run_and_capture("SEED SEED SEED CONSUME PRONOUNCE") == "\x03"

    def test_pronomce_default(self) -> None:
        assert run_and_capture("PRONOUNCE") == "\x00"

    def test_hello_world(self) -> None:
        r"""Hello World program from the language docs."""
        program = Path(__file__).parents[2] / "tests/fixtures/mammalian.txt"
        assert run_and_capture(program.read_text()) == "Hello, world!\n"

    def test_accept_on_a_blank_line_appends_nothing(self) -> None:
        r"""``ACCEPT`` takes the first byte of a line, and a blank line has."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        def accepted(stdin: str) -> list[int]:
            machine = _Machine("ACCEPT", ScriptedIO(stdin))
            machine.step()
            return list(machine.lst[0])

        assert accepted("\n") == [0], "a blank line appends nothing"
        assert accepted("A\n") == [0, 65], "a byte is folded in and appended"
        # A character past U+00FF is.
        # so it is what pins the wrap:.
        assert accepted("Ł\n") == [0, 65], "the fold wraps at 256"

    def test_values_wrap_at_a_byte(self) -> None:
        r"""Every stored or printed value is reduced modulo 256, not 257."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        # SEED puts 1 in lst[0]; ACCEPT.
        # it; DIGEST xors the.
        machine = _Machine("SEED ACCEPT DIGEST PRONOUNCE", ScriptedIO("\xff\n"))
        while not machine.halted:
            machine.step()
        assert machine.acc == 256
        assert machine.io.getvalue() == "\x00"

    def test_seed_wraps_its_register_at_a_byte(self) -> None:
        r"""``SEED``'s addition wraps too, at the same 256."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("CONSUME ACCEPT SEED", ScriptedIO("\xff\n"))
        while not machine.halted:
            machine.step()
        assert machine.lst[0] == (0,)

    def test_sprint_needs_a_position_inside_the_array(self) -> None:
        r"""``SPRINT`` is a NOP unless the accumulator indexes a real cell."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("CONSUME SPRINT", IO())
        while not machine.halted:
            machine.step()
        assert machine.lst[0] == ()
        assert machine.ptr == 0


class TestStepMachine:
    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("", IO())
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.lst == tuple((0,) for _ in range(23))

    def test_the_command_halt_flag_starts_false(self) -> None:
        r"""The flag is ``False`` to begin with, and ``snapshot`` carries it."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("PRONOUNCE", IO())
        assert machine.snapshot()[-1] is False


class TestPartial:
    r"""``_partial`` applies one array op; two of them need a non-empty."""

    def test_consume_of_an_empty_array_leaves_the_accumulator(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _partial

        after, acc = _partial(3, (), 7)
        assert acc == 7
        assert after == ()

    def test_fission_of_an_empty_array_leaves_the_accumulator(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _partial

        after, acc = _partial(4, (), 7)
        assert acc == 7
        assert after == ()

    def test_consume_takes_the_middle_cell(self) -> None:
        r"""``CONSUME`` pops ``(len - 1) // 2``, the lower of the two middles."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _partial

        after, acc = _partial(3, (10, 11, 12), 0)
        assert acc == 11
        assert after == (10, 12)

    def test_fission_splits_the_middle_cell(self) -> None:
        r"""``FISSION`` halves the same middle cell and hangs it off both ends."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _partial

        after, acc = _partial(4, (10, 12, 14), 3)
        assert acc == 3
        assert after == (6, 10, 14, 6)

    def test_excrete_stores_the_accumulator_modulo_a_byte(self) -> None:
        r"""``EXCRETE`` appends ``acc % 256`` and clears the accumulator."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _partial

        after, acc = _partial(2, (), 256)
        assert acc == 0
        assert after == (0,)
        after, acc = _partial(2, after, 321)
        assert acc == 0
        assert after == (0, 65)


class TestTotal:
    r"""``total`` is the published mutating shape for the whole-memory ops."""

    def test_seed_adds_each_arrays_index_to_its_head(self) -> None:
        r"""``SEED`` adds ``index + 1`` to every array's first cell."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _total

        arrays = _total(0, tuple((10, 0) for _ in range(23)))
        assert [arr[0] for arr in arrays] == [11 + k for k in range(23)]
        assert all(arr[1] == 0 for arr in arrays)

    def test_seed_skips_an_empty_array(self) -> None:
        r"""An empty array has no head to seed, so it stays empty."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _total

        before = [() for _ in range(23)]
        before[5] = (1,)
        arrays = _total(0, tuple(before))
        assert arrays[0] == ()
        assert arrays[5] == (7,)

    def test_conflagrate_pairs_the_flattened_memory(self) -> None:
        r"""``CONFLAGRATE`` folds the memory end to end, across array bounds."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _total

        before = [() for _ in range(23)]
        before[0] = (9, 2)
        arrays = _total(1, tuple(before))
        assert arrays[0] == (5, 6)


class TestSprintIndex:
    r"""``SPRINT`` indexes from the far end on a negative accumulator."""

    def test_an_accumulator_past_the_far_end_reports_a_list(self) -> None:
        r"""Walking off the front raises, and says "list", not "tuple"."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _advance

        arrays = tuple((0,) for _ in range(23))
        with raises_message(IndexError, "list index out of range"):
            _advance((arrays, 0, -2, 0, False), 6)

        assert _advance((arrays, 0, -1, 0, False), 6)[1] == 0


class TestLeapfrog:
    r"""``LEAPFROG`` jumps the cursor, or halts when the target is negative."""

    def test_a_negative_target_halts(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        # acc 0 and a head of 0 give.
        machine = _Machine("LEAPFROG PRONOUNCE", IO())
        machine.lst = (
            *machine.lst[:0],
            (0, 5),
            *machine.lst[0 + 1 :],
        )  # non-empty with a truthy tail:.
        machine.step()
        assert machine.halted

    def test_a_non_negative_target_moves_the_cursor(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        # acc 2, head 0 -> target 1;.
        # it 2, so the jump is what.
        machine = _Machine("LEAPFROG PRONOUNCE PRONOUNCE", IO())
        machine.lst = (
            *machine.lst[:0],
            (0, 5),
            *machine.lst[0 + 1 :],
        )
        machine.acc = 2
        machine.step()
        assert not machine.halted
        assert machine.ind == 2

    def test_a_target_of_zero_is_a_jump_rather_than_a_halt(self) -> None:
        r"""Zero is a legal target: only a *negative* one halts."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("LEAPFROG PRONOUNCE", IO())
        machine.lst = (
            *machine.lst[:0],
            (0, 5),
            *machine.lst[0 + 1 :],
        )
        machine.acc = 1
        machine.step()
        assert not machine.halted
        assert machine.ind == 1

    def test_the_target_subtracts_the_head_from_the_accumulator(self) -> None:
        r"""``target`` is ``acc - head - 1``, so a larger head jumps lower."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("LEAPFROG PRONOUNCE PRONOUNCE PRONOUNCE", IO())
        machine.lst = (
            *machine.lst[:0],
            (5, 7),
            *machine.lst[0 + 1 :],
        )
        machine.acc = 8
        machine.step()
        assert not machine.halted
        assert machine.ind == 3

    def test_leapfrog_reads_the_last_cell_to_decide_whether_to_jump(self) -> None:
        r"""The guard is the array's *last* value, not its second."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("LEAPFROG PRONOUNCE", IO())
        machine.lst = (
            *machine.lst[:0],
            (0, 5, 0),
            *machine.lst[0 + 1 :],
        )
        machine.acc = 9
        machine.step()
        assert not machine.halted
        assert machine.ind == 1  # fell through rather than.


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "SEED PRONOUNCE"
