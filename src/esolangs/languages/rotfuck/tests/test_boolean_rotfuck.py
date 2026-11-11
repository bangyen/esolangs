"""rotfuck generator tests."""

from collections.abc import Callable, Iterable
from functools import cache
from itertools import product
from unittest.mock import patch

import pytest

import esolangs
from esolangs.generation.helpers import _ASCII_ZERO
from esolangs.languages.rotfuck import generator as boolean
from esolangs.languages.rotfuck.generator import (
    _Builder,
    _constant,
    _groups,
    _parse,
    _rotfuck_rot,
    _shows,
)
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.generators.boolean_runners import _runner
from tests.interpreters.runner import run_program
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import assert_shared_program
from tests.support.witness_tables import row_bits


class TestRotfuck:
    """The ROTfuck boolean generator."""

    def test_program_round_trips_every_table_at_n_2(self) -> None:
        """Every two-input table produces the right result."""
        assert_analysis_complement("ROTfuck", "read_at", "00100010")
        assert_analysis_complement(
            "ROTfuck",
            "symmetric_weights",
            "".join(str(row.bit_count() % 2) for row in range(256)),
            rows=(0, 1, 255),
        )
        for table_int in range(2 ** (2**2)):
            table = format(table_int, "04b")
            program = boolean.rotfuck(table)
            for combo in range(4):
                bits = [(combo >> (1 - i)) & 1 for i in range(2)]
                got = run_rotfuck(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    @pytest.mark.parametrize("n", [6, 7, 8])
    def test_a_second_index_digit_still_selects_the_right_entry(self, n: int) -> None:
        """The arity where the index stops fitting in one walk."""
        table = "".join(str((row).bit_count() & 1) for row in range(2**n))
        program = boolean.rotfuck(table)
        for combo in (0, 1, 2**n - 1, 2**n - 2, 2 ** (n - 1), 2 ** (n - 1) - 1):
            bits = row_bits(combo, n)
            got = run_rotfuck(program, [str(b) for b in bits])
            assert got == table[combo], f"n={n} inputs {bits}"

    def test_the_rotation_cycle_is_the_interpreters_default(self) -> None:
        """The prose's ``+-><,.[]`` turned backward, and it is a cycle."""
        from esolangs.languages.rotfuck.dialect import ROTFUCK_CYCLES as CYCLES

        chain = CYCLES["backward"]
        assert not hasattr(boolean, "_ROTFUCK_CHAIN")

        assert chain == "+][.,<>-" == CYCLES["backward"]
        assert CYCLES["forward"] == "+-><,.[]"
        assert "+" + "+-><,.[]"[:0:-1] == chain
        for i, char in enumerate(chain):
            forward = chain[(i + 1) % 8]
            assert _rotfuck_rot(char, 1) == forward, char
            assert _rotfuck_rot(forward, -1) == char, char
            assert _rotfuck_rot(char, 8) == char, char
            assert _rotfuck_rot(char, 0) == char, char
        for i, char in enumerate(CYCLES["forward"]):
            assert (
                _rotfuck_rot(char, 1, CYCLES["forward"])
                == CYCLES["forward"][(i + 1) % 8]
            )

    @pytest.mark.parametrize("rotation", ["backward", "forward"])
    def test_a_command_never_shows_as_a_bracket_inside_a_seek(
        self, rotation: str
    ) -> None:
        """A command's rotation, seen from a seek's, must not be a bracket."""
        from esolangs.languages.rotfuck.dialect import ROTFUCK_CYCLES as CYCLES

        cycle = CYCLES[rotation]
        for seek in range(8):
            for rot in range(8):
                for cmd in "+-><":
                    assert _shows(cmd, seek, rot, cycle) == (
                        _rotfuck_rot(cmd, seek - rot, cycle) in "[]"
                    ), (rotation, cmd, seek, rot)
        if rotation == "backward":
            assert [c for c in "+-><" if not _shows(c, 0, 4)] == ["+", "-"]
            assert [c for c in "+-><" if not _shows(c, 0, 5)] == ["+", "<"]
            assert [c for c in "+-><" if not _shows(c, 0, 6)] == [">", "<"]

    def test_net_zero_runs_are_pairs_wrapped_in_inverses_and_chained(self) -> None:
        """The brute-force pad set (every ``+-><`` run <= 6) is the grammar's."""
        inverse = {"+": "-", "-": "+", "<": ">", ">": "<"}
        grown: dict[int, set[str]] = {0: {""}}
        for size in range(2, 7, 2):
            made = {
                step + run + inverse[step] for step in "+-><" for run in grown[size - 2]
            }
            for left in range(2, size, 2):
                made |= {a + b for a in grown[left] for b in grown[size - left]}
            grown[size] = made
        assert set(_search_pads()) == set().union(*grown.values()) - {""}

    # 3.8 s alone, but 16-17 s under CI's -n load (3 of 5 runs, 2026-10-16).
    @pytest.mark.slow
    def test_pads_match_the_search_they_replaced(self) -> None:
        """Same length and rotation as the Dijkstra over pads, on every state.

        A state is the open seeks and the rotation; the targets are every
        command hidden, a loop's opening and every phase.  The rule's word is
        hidden and net zero.
        """
        from esolangs.languages.rotfuck import generator as gen
        from esolangs.languages.rotfuck.dialect import ROTFUCK_CYCLES

        # Open phases are pairwise 0, 3, 4 or 5 apart, so a set never has three.
        stacks = {()}
        for _ in range(2):
            stacks |= {
                tuple(sorted({*stack, phase}))
                for stack in stacks
                for phase in range(8)
                if all((seek - phase) % 8 in (0, 3, 4, 5) for seek in stack)
            }
        checked = 0
        for cycle in ROTFUCK_CYCLES.values():
            for stack in stacks:
                for rot in range(8):
                    for done in _targets(stack, cycle):
                        ruled = gen._Builder(cycle)
                        ruled._seeks, ruled.rot = list(stack), rot
                        found = _search_pad_until(ruled, done)
                        try:
                            ruled._pad_until(done)
                        except gen._UnplaceableError:
                            assert found is None
                            continue
                        assert found == len(ruled.src)
                        word = [
                            gen._rotfuck_rot(char, rot + at, cycle)
                            for at, char in enumerate(ruled.src)
                        ]
                        assert not any(
                            gen._shows(cmd, seek, rot + at, cycle)
                            for at, cmd in enumerate(word)
                            for seek in stack
                        )
                        assert _is_net_zero(word)
                        checked += 1
        assert checked > 4000

    @pytest.mark.parametrize("trips", range(7))
    def test_a_loop_leaves_the_rotation_where_it_found_it(self, trips: int) -> None:
        """The invariant every loop rests on, checked by running one."""
        out = _Builder()
        out.emit(_parse("+" * trips + "[->+<]>" + "+" * _ASCII_ZERO + "."))
        assert run_rotfuck(out.text(), []) == str(trips)

    @pytest.mark.parametrize("body", ["-", "-+-", ">+<-", "[-]"])
    def test_a_body_of_either_parity_closes_at_its_phase(self, body: str) -> None:
        """An even body opens with a ``[`` that cannot fire; an odd one does not."""
        out = _Builder()
        out.emit(_parse(f"+++[{body}]" + "+" * _ASCII_ZERO + "."))
        assert run_rotfuck(out.text(), []) == "0"

    def test_the_program_is_only_command_characters(self) -> None:
        """Nothing but the eight commands is emitted."""
        for table in ("01", "0110", "11110000", "01101001"):
            assert set(boolean.rotfuck(table)) <= set("+-><,.[]"), table

    def test_backward_is_the_default_direction(self) -> None:
        assert boolean.rotfuck("01", rotation="backward") == boolean.rotfuck("01")

    @pytest.mark.parametrize("rotation", ["backward", "forward"])
    def test_both_rotations_compute_their_table(self, rotation: str) -> None:
        """Either cycle is targeted; each program runs under its own."""
        run = run_rotfuck if rotation == "backward" else run_rotfuck_forward
        for table in ("01", "0110", "01101001", "11110000"):
            program = boolean.rotfuck(table, rotation=rotation)
            n = len(table).bit_length() - 1
            for combo in range(len(table)):
                bits = row_bits(combo, n)
                assert run(program, [str(b) for b in bits]) == table[combo], (
                    rotation,
                    table,
                    combo,
                )

    @pytest.mark.parametrize("n", [6, 7, 8])
    def test_forward_reaches_a_second_index_digit(self, n: int) -> None:
        """Forward emits its own walks through the arity where the index splits."""
        table = "".join(str((row).bit_count() & 1) for row in range(2**n))
        program = boolean.rotfuck(table, rotation="forward")
        for combo in (0, 1, 2**n - 1, 2 ** (n - 1)):
            bits = row_bits(combo, n)
            assert run_rotfuck_forward(program, [str(b) for b in bits]) == table[combo]

    def test_raw_digits_shed_the_bias_once_per_digit_from_n_7(self) -> None:
        """Raw parity and zero-carrier multipliers keep native input/output."""
        language = esolangs.Language("ROTfuck")
        for witness in construction_boundaries("ROTfuck")["biased_to_raw_index_digits"]:
            n, table = witness.arity, witness.table()
            with patch.object(boolean, "_select", wraps=boolean._select) as select:
                artifact = language.generate(table)
            assert select.call_args.kwargs["raw"] == (n == 7)
            restored = language.load_program(language.dump_program(artifact))
            prepared = language.prepare(restored)
            for row in (0, 1, len(table) // 2, len(table) - 1):
                result = prepared.evaluate(row_bits(row, n))
                assert result.bit == table[row]
                assert result.observation.input_position == n
        _check_symmetric_multipliers()
        _check_raw_five_digits()
        table = "".join(str((row).bit_count() & 1) for row in range(128))
        program = boolean.rotfuck(table)
        assert len(program) == 227
        for combo in range(0, 128, 5):
            got = run_rotfuck(program, [str(b) for b in row_bits(combo, 7)])
            assert got == table[combo], combo

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("01", 103),
            ("10", 103),
            ("0001", 173),
            ("0110", 173),
            ("11110000", 134),
            ("01101001", 244),
        ],
    )
    def test_the_emitted_length_is_exact(self, table: str, length: int) -> None:
        """The layout is deterministic down to the character."""
        assert len(boolean.rotfuck(table)) == length

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("01", 119),
            ("10", 119),
            ("0001", 189),
            ("0110", 189),
            ("11110000", 150),
            ("01101001", 260),
        ],
    )
    def test_the_forward_length_is_exact(self, table: str, length: int) -> None:
        """The forward layout is deterministic down to the character."""
        assert len(boolean.rotfuck(table, rotation="forward")) == length

    def test_a_lone_late_one_in_a_64_table_is_exactly_647_long(self) -> None:
        """The loop-phase set (0, 3, 4, 5) mod 8 fixes the pads, so the length."""
        assert len(boolean.rotfuck("0" * 52 + "1" + "0" * 11)) == 647

    def test_a_zero_upper_half_runs(self) -> None:
        """A zero upper half is 2 * 128 plain steps, and still correct."""
        half = "".join(str((row * 37 % 256).bit_count() & 1) for row in range(128))
        table = half + "0" * 128
        program = boolean.rotfuck(table)
        for combo in (0, 1, 127, 128, 200, 255):
            bits = [(combo >> (7 - i)) & 1 for i in range(8)]
            assert run_rotfuck(program, [str(b) for b in bits]) == table[combo]


def test_rotation_is_checked() -> None:
    from unittest.mock import patch

    from .oracle_checks import check_raw_rotfuck

    check_raw_rotfuck()
    with pytest.raises(ValueError, match="rotation"):
        boolean.rotfuck("01", rotation="sideways")
    for rotation, runner in (
        ("backward", run_rotfuck),
        ("forward", run_rotfuck_forward),
    ):
        for amount in (3, 64):
            builder = _Builder(boolean.ROTFUCK_CYCLES[rotation])
            _constant(builder, "+" * amount)
            builder.emit(_parse("."))
            assert runner("".join(builder.src), []) == chr(amount)
    builder = _Builder()
    with (
        patch.object(builder, "_unit", return_value=None),
        patch.object(builder, "_wrapped", return_value=None),
        pytest.raises(boolean._UnplaceableError, match="no neutral pad"),
    ):
        builder._pad(4)


@pytest.mark.medium
@pytest.mark.parametrize("bit", "01")
def test_every_constant_row_within_written_state_bound(bit: str) -> None:
    from esolangs import generate
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("ROTfuck")["workspace"].formula

    _check_native_constants(bit)
    table = bit * 256
    # Four phase-neutral body commands repeat six times, adding eighty executions.
    commands = len(generate("ROTfuck", table).source) + 80
    assert_shared_program("ROTfuck", table, None, commands, lambda p: workspace(8, p))


run_rotfuck = _runner("rotfuck")


def run_rotfuck_forward(program: str, inputs: list[str]) -> str:
    """Run a ROTfuck program under the forward rotation."""
    from esolangs.languages.rotfuck.interpreter import run as _run

    return run_program(_run, program, "".join(inputs), rotation="forward")


@cache
def _search_pads() -> tuple[str, ...]:
    """Every net-zero run of ``+-><`` of even length <= 6 (the old pad set)."""
    return tuple(
        "".join(run)
        for length in range(2, 7, 2)
        for run in product("+-><", repeat=length)
        if _is_net_zero(run)
    )


def _is_net_zero(run: Iterable[str]) -> bool:
    """Whether ``run`` leaves every cell and the pointer where they were."""
    cells: dict[int, int] = {}
    at = 0
    for char in run:
        at += (char == ">") - (char == "<")
        cells[at] = cells.get(at, 0) + (char == "+") - (char == "-")
    return at == 0 and not any(cells.values())


def _targets(stack: tuple[int, ...], cycle: str) -> list[Callable[[int], bool]]:
    """Every ``done`` predicate the builder passes, for open seeks ``stack``."""
    hides = [
        lambda rot, cmd=cmd: not any(_shows(cmd, seek, rot, cycle) for seek in stack)
        for cmd in "+-<>,.[]"
    ]

    def opens(rot: int) -> bool:
        return all((seek - rot) % 8 in (0, 3, 4, 5) for seek in stack)

    phases = [lambda rot, phase=phase: rot == phase for phase in range(8)]
    return [*hides, opens, *phases]


def _search_pad_until(builder: object, done: Callable[[int], bool]) -> int | None:
    """The old Dijkstra over pad runs: the shortest pad length, or ``None``."""
    import heapq

    pads = _search_pads()
    queue = [(0, builder.rot, "")]  # type: ignore[attr-defined]
    seen: set[int] = set()
    while queue:
        cost, rot, path = heapq.heappop(queue)
        if done(rot):
            return cost
        if rot in seen:
            continue
        seen.add(rot)
        for run in pads:
            if all(
                builder._hidden(c, rot + i)  # type: ignore[attr-defined]
                for i, c in enumerate(run)
            ):
                heapq.heappush(
                    queue, (cost + len(run), (rot + len(run)) % 8, path + run)
                )
    return None


def _check_native_constants(bit: str) -> None:
    from esolangs.languages.rotfuck.interpreter import _Machine
    from esolangs.languages.rotfuck.proof_formulas import execution
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("ROTfuck")["workspace"].formula

    for n in range(1, 13):
        for rotation in ("backward", "forward"):
            settings = esolangs.Language("Rotfuck").settings(rotation=rotation)
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate(
                    "ROTfuck", bit * (1 << n), settings=settings, **options
                ).source
                assert len("".join(program.split())) == n + 26 + int(bit)
                commands = execution(n, program)
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    io = ReadFirstIO(f"{row:0{n}b}" + "Q", expected=n)
                    machine = _Machine(program, io, rotation=rotation)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(machine, commands, written=written)
                    assert steps == commands
                    assert machine.prog.rotation() == n + 106 + int(bit)
                    assert written.bits == workspace(n, program)
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(esolangs.generate("ROTfuck", f"{v:08b}").source) for v in range(256))
        == 71890
    )


def _check_symmetric_multipliers() -> None:
    from esolangs.languages.rotfuck import generator as g
    from esolangs.languages.rotfuck.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("ROTfuck")["workspace"].formula

    for rotation, cycle in g.ROTFUCK_CYCLES.items():
        for delta in (-80, 128):
            for value in (0, 1, 127, 255):
                out = _Builder(cycle)
                out.emit(_parse("+" * value + ">+++++++<"))
                _constant(out, ("+" if delta > 0 else "-") * abs(delta))
                out.emit(_parse("."))
                io = ScriptedIO("Q")
                machine = _Machine(out.text(), io, rotation=rotation)
                for _ in range(5000):
                    if machine.halted:
                        break
                    machine.step()
                assert machine.halted
                assert io.getvalue() == chr((value + delta) % 256)
                cells = (*machine.tape, 0, 0, 0)
                assert cells[machine.ptr + 1] == 7
                assert cells[machine.ptr + 2] == 0
                assert io.input_char() == ord("Q")
        for n in (1, 7, 8):
            table = "".join(
                str((row.bit_count() + (n == 8)) & 1) for row in range(1 << n)
            )
            program = g.rotfuck(table, rotation=rotation)
            for row in (0, (1 << n) - 1):
                io = ScriptedIO(f"{row:0{n}b}" + "Q")
                machine = _Machine(program, io, rotation=rotation)
                written = WrittenState(machine.workspace_snapshot())
                for _ in range(2080 * len(program)):
                    if machine.halted:
                        break
                    machine.step()
                    written.sample(machine.workspace_snapshot())
                    if io.getvalue():
                        assert io.progress() == n
                assert machine.halted
                if rotation == "backward" and n == 1 and row == 1:
                    assert machine.prog.rotation() == 183
                assert io.getvalue() == table[row]
                assert io.input_char() == ord("Q")
                assert written.bits <= workspace(n, program)


def _check_raw_five_digits() -> None:
    from esolangs.languages.rotfuck import generator as g
    from esolangs.languages.rotfuck.interpreter import _Machine
    from esolangs.languages.rotfuck.proof_formulas import execution

    assert _groups(8) == [2, 6]
    assert _groups(8, raw=True) == [3, 5]
    for n in (7, 8):
        table = "1" * ((1 << n) - 2) + "01"
        for rotation in g.ROTFUCK_CYCLES:
            program = g.rotfuck(table, rotation=rotation)
            io = ScriptedIO("1" * n + "Q")
            machine = _Machine(program, io, rotation=rotation)
            bound = execution(n, program)
            steps = 0
            while not machine.halted and steps < bound:
                steps += 1
                machine.step()
                if io.getvalue():
                    assert io.reads == n
                if machine.halted:
                    break
            assert machine.halted
            assert steps == bound
            assert io.getvalue() == "1"
            assert io.past_end == 0
            assert io.input_char() == ord("Q")
