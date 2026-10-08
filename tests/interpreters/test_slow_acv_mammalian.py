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
    def test_seed_adds_to_each_register(self) -> None:
        """SEED adds 1..23 to each list head; three SEEDs then CONSUME -> 3."""
        assert run_and_capture("SEED SEED SEED CONSUME PRONOUNCE") == "\x03"

    @pytest.mark.parametrize("separator", ["\n", "\f"])
    def test_instructions_are_whitespace_delimited(self, separator: str) -> None:
        program = separator.join(("SEED", "CONSUME", "PRONOUNCE"))
        assert run_and_capture(program) == "\x01"

    @pytest.mark.parametrize("word", ["SEEDSEED", "SEED!"])
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

    def test_accept_appends_a_newline(self) -> None:
        """ACCEPT appends a newline byte, narrowed like other input."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        def accepted(stdin: str) -> list[int]:
            machine = _Machine("ACCEPT", ScriptedIO(stdin))
            machine.step()
            return list(machine.lst[0])

        assert accepted("\n") == [0, 10], "a newline is folded in and appended"
        assert accepted("A\n") == [0, 65], "a byte is folded in and appended"
        # A character past U+00FF is the only way the fold exceeds a byte,
        # so it is what pins the wrap: 321 % 256 is 65, where 257 gives 64.
        assert accepted("Ł\n") == [0, 65], "the fold wraps at 256"

    @pytest.mark.parametrize(("io_modulus", "printed"), [(None, "\x01"), (256, "\x00")])
    def test_printed_values_wrap_at_the_io_modulus(
        self, io_modulus: int | None, printed: str
    ) -> None:
        """PRONOUNCE prints ``acc`` modulo 255 ("modulo 255"), or 256 if asked."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        # SEED puts 1 in lst[0]; ACCEPT folds 0xff against acc 0 and appends
        # it; DIGEST xors the accumulator with the sum, giving 256.
        io = ScriptedIO("\xff\n")
        settings = {} if io_modulus is None else {"io_modulus": io_modulus}
        machine = _Machine("SEED ACCEPT DIGEST PRONOUNCE", io, **settings)
        while not machine.halted:
            machine.step()
        assert machine.acc == 256
        assert machine.io.getvalue() == printed

    def test_seed_wraps_its_register_at_a_byte(self) -> None:
        """``SEED``'s addition wraps too, at the same 256."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("CONSUME ACCEPT SEED", ScriptedIO("\xff\n"))
        while not machine.halted:
            machine.step()
        assert machine.lst[0] == (0,)

    def test_sprint_needs_a_position_inside_the_array(self) -> None:
        """``SPRINT`` is a NOP unless the accumulator indexes a real cell."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        machine = _Machine("CONSUME SPRINT", IO())
        while not machine.halted:
            machine.step()
        assert machine.lst[0] == ()
        assert machine.ptr == 0

    def test_fast_run_covers_each_control_branch(self) -> None:
        from esolangs.interpreters.io import ScriptedIO

        run(
            "CONSUME SEED CONFLAGRATE EXCRETE CONSUME FISSION DIGEST SPRINT",
            ScriptedIO(),
        )
        run("CONSUME SPRINT ACCEPT", ScriptedIO("\n"))
        run("SEED LEAPFROG", ScriptedIO())
        run("ACCEPT DIGEST LEAPFROG", ScriptedIO("A\n"))


class TestPartial:
    """``_partial`` applies one array op; two of them need a non-empty array."""

    def test_consume_takes_the_middle_cell(self) -> None:
        """``CONSUME`` pops ``(len - 1) // 2``, the lower of the two middles."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _partial

        after, acc = _partial(3, (10, 11, 12), 0)
        assert acc == 11
        assert after == (10, 12)

    def test_consume_on_an_empty_array_leaves_the_state_alone(self) -> None:
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _partial

        assert _partial(3, (), 7) == ((), 7)

    def test_fission_splits_the_middle_cell(self) -> None:
        """``FISSION`` halves the same middle cell and hangs it off both ends."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _partial

        after, acc = _partial(4, (10, 12, 14), 3)
        assert acc == 3
        assert after == (6, 10, 14, 6)

    def test_excrete_stores_the_accumulator_modulo_the_io_modulus(self) -> None:
        """``EXCRETE`` appends ``acc % 255`` by default and clears ``acc``."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _partial

        after, acc = _partial(2, (), 256)
        assert acc == 0
        assert after == (1,)
        after, acc = _partial(2, (), 256, 256)
        assert acc == 0
        assert after == (0,)
        after, acc = _partial(2, after, 321, 256)
        assert acc == 0
        assert after == (0, 65)


class TestTotal:
    """``total`` is the published mutating shape for the whole-memory ops."""

    def test_seed_adds_each_arrays_index_to_its_head(self) -> None:
        """``SEED`` adds ``index + 1`` to every array's first cell."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _total

        arrays = _total(0, tuple((10, 0) for _ in range(23)))
        assert [arr[0] for arr in arrays] == [11 + k for k in range(23)]
        assert all(arr[1] == 0 for arr in arrays)

    def test_seed_skips_an_empty_array(self) -> None:
        """An empty array has no head to seed, so it stays empty."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _total

        before = [() for _ in range(23)]
        before[5] = (1,)
        arrays = _total(0, tuple(before))
        assert arrays[0] == ()
        assert arrays[5] == (7,)

    def test_conflagrate_pairs_the_flattened_memory(self) -> None:
        """``CONFLAGRATE`` folds the memory end to end, across array bounds."""
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _total

        before = [() for _ in range(23)]
        before[0] = (9, 2)
        arrays = _total(1, tuple(before))
        assert arrays[0] == (5, 6)


class TestSprintIndex:
    """``SPRINT`` indexes from the far end on a negative accumulator."""

    def test_an_accumulator_past_the_far_end_reports_a_list(self) -> None:
        """Walking off the front raises, and says "list", not "tuple"."""
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
        machine.lst = (
            *machine.lst[:0],
            (0, 5),
            *machine.lst[0 + 1 :],
        )  # non-empty with a truthy tail: the branch fires
        machine.step()
        assert machine.halted

    def test_the_target_subtracts_the_head_from_the_accumulator(self) -> None:
        """``target`` is ``acc - head - 1``, so a larger head jumps lower."""
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
        """The guard is the array's *last* value, not its second."""
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
        assert machine.ind == 1  # fell through rather than jumping to 8


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "SEED PRONOUNCE"


@pytest.mark.parametrize("cell_modulus", [255, 256])
def test_conflagrate_uses_cell_modulus(cell_modulus: int) -> None:
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _total

    arrays = ((512, 254),) + ((),) * 22
    assert _total(1, arrays, cell_modulus)[0] == (510, 256 % cell_modulus)


@pytest.mark.parametrize("io_modulus", [255])
def test_excrete_uses_io_modulus_without_changing_seed(io_modulus: int) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

    machine = _Machine("EXCRETE SEED", ScriptedIO(), io_modulus=io_modulus)
    machine.acc = 256
    machine.step()
    assert machine.lst[0] == (0, 256 % io_modulus)
    assert machine.acc == 0
    machine.step()
    assert machine.lst[0] == (1, 256 % io_modulus)


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
