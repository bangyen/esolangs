"""Unit tests for the SLOW ACV SLOW ACV MAMMALIAN interpreter."""

from functools import partial

import pytest

from esolangs.languages.slow_acv_mammalian.interpreter import (
    _advance,
    _Machine,
    _partial,
    _total,
    run,
)
from esolangs.languages.slow_acv_mammalian.interpreter import (
    _Machine as SlowAcvMammalian,
)
from esolangs.runtime.io import IO, ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.contract import SnapshotContract, machine_factory
from tests.interpreters.runner import run_printing
from tests.support.paths import ROOT
from tests.support.raises import assert_rejected_with_hint, raises_message

run_and_capture = partial(run_printing, run)


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
        program = (
            ROOT
            / "src/esolangs/languages/slow_acv_mammalian/tests/fixtures/mammalian.txt"
        )
        assert run_and_capture(program.read_text()) == "Hello, world!\n"

    def test_accept_appends_a_newline(self) -> None:
        """ACCEPT appends a newline byte, narrowed like other input."""

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
        # SEED puts 1 in lst[0]; ACCEPT folds 0xff against acc 0 and appends
        # it; DIGEST xors the accumulator with the sum, giving 256.
        io = ScriptedIO("\xff\n")
        settings = {} if io_modulus is None else {"io_modulus": io_modulus}
        machine = _Machine("SEED ACCEPT DIGEST PRONOUNCE", io, **settings)
        while not machine.halted:
            machine.step()
        assert machine.acc == 256
        assert machine.io.getvalue() == printed

    def test_seed_wraps_its_register_at_a_byte(self, monkeypatch) -> None:
        """``SEED``'s addition wraps too, at the same 256."""
        machine = _Machine("CONSUME ACCEPT SEED", ScriptedIO("\xff\n"))
        while not machine.halted:
            machine.step()
        assert machine.lst[0] == (0,)

        import esolangs
        from esolangs.languages.slow_acv_mammalian import interpreter
        from tests.support.prepared_support import check_image_reuse

        settings = esolangs.Language("SLOW ACV MAMMALIAN").settings(io_modulus=256)
        check_image_reuse(
            "SLOW ACV MAMMALIAN",
            "SEED ACCEPT\nDIGEST PRONOUNCE",
            interpreter,
            "_prepare_source",
            monkeypatch,
            cases=(("ÿ", "\x00"), ("A", "B"), ("B", "C")),
            settings=settings,
        )

    def test_sprint_needs_a_position_inside_the_array(self) -> None:
        """``SPRINT`` is a NOP unless the accumulator indexes a real cell."""
        machine = _Machine("CONSUME SPRINT", IO())
        while not machine.halted:
            machine.step()
        assert machine.lst[0] == ()
        assert machine.ptr == 0

    def test_fast_run_covers_each_control_branch(self) -> None:
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
        after, acc = _partial(3, (10, 11, 12), 0)
        assert acc == 11
        assert after == (10, 12)

    def test_consume_on_an_empty_array_leaves_the_state_alone(self) -> None:
        assert _partial(3, (), 7) == ((), 7)

    def test_fission_splits_the_middle_cell(self) -> None:
        """``FISSION`` halves the same middle cell and hangs it off both ends."""
        after, acc = _partial(4, (10, 12, 14), 3)
        assert acc == 3
        assert after == (6, 10, 14, 6)

    def test_excrete_stores_the_accumulator_modulo_the_io_modulus(self) -> None:
        """``EXCRETE`` appends ``acc % 255`` by default and clears ``acc``."""
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
        arrays = _total(0, tuple((10, 0) for _ in range(23)))
        assert [arr[0] for arr in arrays] == [11 + k for k in range(23)]
        assert all(arr[1] == 0 for arr in arrays)

    def test_seed_skips_an_empty_array(self) -> None:
        """An empty array has no head to seed, so it stays empty."""
        before = [() for _ in range(23)]
        before[5] = (1,)
        arrays = _total(0, tuple(before))
        assert arrays[0] == ()
        assert arrays[5] == (7,)

    def test_conflagrate_pairs_the_flattened_memory(self) -> None:
        """``CONFLAGRATE`` folds the memory end to end, across array bounds."""
        before = [() for _ in range(23)]
        before[0] = (9, 2)
        arrays = _total(1, tuple(before))
        assert arrays[0] == (5, 6)


class TestSprintIndex:
    """``SPRINT`` indexes from the far end on a negative accumulator."""

    def test_an_accumulator_past_the_far_end_reports_a_list(self) -> None:
        """Walking off the front raises, and says "list", not "tuple"."""
        arrays = tuple((0,) for _ in range(23))
        with raises_message(IndexError, "list index out of range"):
            _advance((arrays, 0, -2, 0, False), 6)

        assert _advance((arrays, 0, -1, 0, False), 6)[1] == 0


class TestLeapfrog:
    """``LEAPFROG`` jumps the cursor, or halts when the target is negative."""

    def test_a_negative_target_halts(self) -> None:
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


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(machine_factory(_Machine, IO))
    stepping_program = "SEED PRONOUNCE"


@pytest.mark.parametrize("cell_modulus", [255, 256])
def test_conflagrate_uses_cell_modulus(cell_modulus: int) -> None:
    arrays = ((512, 254),) + ((),) * 22
    assert _total(1, arrays, cell_modulus)[0] == (510, 256 % cell_modulus)


@pytest.mark.parametrize("io_modulus", [255])
def test_excrete_uses_io_modulus_without_changing_seed(io_modulus: int) -> None:
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
    for entry in (_Machine, run):
        with pytest.raises(ValueError, match="modulus must"):
            entry("PRONOUNCE", ScriptedIO(), **settings)


def test_unsupported_leapfrog_resume_is_rejected_before_execution() -> None:
    for entry in (_Machine, run):
        with pytest.raises(ValueError, match="leapfrog_resume must be after or at"):
            entry("PRONOUNCE", ScriptedIO(), leapfrog_resume="during")


def test_leapfrog_resume_readings_diverge_on_a_searched_witness() -> None:
    from .oracle_checks import check_raw_slow_acv_mammalian

    check_raw_slow_acv_mammalian()
    # The LEAPFROG's count is acc - head = 1, naming the first SEED.
    # "after" resumes at the DIGEST past it and the second pass prints 2;
    # "at" re-runs the SEED and the second pass prints 4.  The next
    # LEAPFROG's count is negative under both, so both runs halt.
    program = "SEED DIGEST SEED DIGEST PRONOUNCE LEAPFROG"
    outputs = {}
    for resume in ("after", "at"):
        io = ScriptedIO("")
        run(program, io, leapfrog_resume=resume)
        outputs[resume] = io.getvalue()
    assert outputs == {"after": "\x03\x02", "at": "\x03\x04"}
    io = ScriptedIO("")
    run(program, io)
    assert io.getvalue() == outputs["after"]


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint(
        "SLOW ACV MAMMALIAN", "PRONOUNCEE", "did you mean 'PRONOUNCE'"
    )


def test_slow_acv_mammalian_looping_run_is_detected_as_a_cycle() -> None:
    # LEAPFROG jumps back to a point that reproduces the exact same state
    code = "CONFLAGRATE SEED SEED DIGEST FISSION LEAPFROG"
    machine = SlowAcvMammalian(code, ScriptedIO())
    assert run_until_halt_or_cycle(machine) is False
