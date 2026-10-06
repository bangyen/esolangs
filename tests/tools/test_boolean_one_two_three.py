"""Covers :mod:`esolangs.tools.one_two_three.construction`."""

from collections.abc import Iterable

import pytest

from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs, runs
from esolangs.tools.one_two_three import ONE, ZERO
from esolangs.tools.one_two_three.construction import _RING
from tests.tools.boolean_runners import one_two_three_result
from tests.witness_tables import witnesses


def _mask(cells: Iterable[int]) -> int:
    """Build a tape mask from cell numbers (bit ``c + _RING`` per cell)."""
    m = 0
    for c in cells:
        m |= 1 << (c + _RING)
    return m


#: One input's run, as the template spells it.
_X = TEMPLATE_CHAR * len(ZERO)


# 2.3s over 132 tests: runs the generated program.
@pytest.mark.medium
class TestParameterizedOneTwoThree:
    """Input-by-substitution boolean generator for the no-input language 123."""

    def run(self, program: str) -> str:
        return one_two_three_result(program)

    def instantiate(self, template: str, bits: list[int]) -> str:
        return fill_runs(template, TEMPLATE_CHAR, ((ZERO, ONE),) * len(bits), bits)

    @pytest.mark.parametrize("n", [1, 2, 3])
    @pytest.mark.medium
    def test_all_small_tables(self, n: int) -> None:
        """Every one-, two- and three-input table halts or loops per its entry."""
        from esolangs import tools as generators

        for table in witnesses(n):
            template = generators.one_two_three(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run(self.instantiate(template, bits))
                assert got == table[combo], (table, bits)

    def test_the_tables_walls_md_called_unreachable(self) -> None:
        """XOR and NAND build, against the recorded monotone ceiling."""
        from esolangs import tools as generators

        for table in ("0110", "1110", "1001", "1000"):
            template = generators.one_two_three(table)
            got = "".join(
                self.run(self.instantiate(template, [(c >> 1) & 1, c & 1]))
                for c in range(4)
            )
            assert got == table

    def test_no_row_diverges(self) -> None:
        """No emitted row marches the pointer right forever."""
        from esolangs import tools as generators
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        for n in (1, 2, 3):
            for table in witnesses(n):
                template = generators.one_two_three(table)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    code = self.instantiate(template, bits)
                    machine = _Machine(code, ScriptedIO(""))
                    seen = set()
                    for _ in range(10_000):
                        if machine.halted:
                            break
                        state = machine.snapshot()
                        if state in seen:
                            break
                        seen.add(state)
                        machine.step()
                    else:  # pragma: no cover - a diverging row would reach here
                        pytest.fail(f"{code!r} neither halts nor revisits a state")

    def test_batched_gate_agrees_with_the_interpreter(self) -> None:
        """The construction's replay gate matches a per-command run."""
        from esolangs import tools as generators
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from tests.tools.one_two_three_support import _replay_verdict

        for n in (1, 2, 3):
            for table in witnesses(n):
                template = generators.one_two_three(table)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    code = self.instantiate(template, bits)
                    machine = _Machine(code, ScriptedIO(""))
                    seen = set()
                    stepwise = "1"
                    for _ in range(10_000):
                        if machine.halted:
                            stepwise = "0"
                            break
                        state = machine.snapshot()
                        if state in seen:
                            break
                        seen.add(state)
                        machine.step()
                    assert _replay_verdict(code) == stepwise == table[combo], (
                        table,
                        bits,
                    )

    def test_the_construction_emits_an_exact_template(self) -> None:
        """``construct`` itself, pinned -- not the small route."""
        from esolangs.tools.one_two_three.construction import construct

        assert construct("01") == (
            f"2222{_X}1111121211222222111111233222332233222211211211213311111111"
            "122222222212331111111111"
        )

    def test_slots_run_in_name_order(self) -> None:
        """Every emitted template embeds exactly two runs, one per input."""
        from esolangs import tools as generators

        for table_int in range(16):
            table = format(table_int, "04b")
            template = generators.one_two_three(table)
            assert "{X" not in template
            assert len(runs(template, TEMPLATE_CHAR, ((ZERO, ONE),) * 2)) == 2, table

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """A zero and a one embed at equal width, so length leaks nothing."""
        from esolangs import tools as generators

        for table_int in range(16):
            table = format(table_int, "04b")
            template = generators.one_two_three(table)
            sizes = {
                len(self.instantiate(template, [(c >> 1) & 1, c & 1])) for c in range(4)
            }
            assert len(sizes) == 1, (table, sizes)

    def test_a_wider_table_is_constructed(self) -> None:
        """A four-input table builds through the constructed route."""
        from esolangs import tools as generators

        table = "0000000000000000"
        template = generators.one_two_three(table)
        assert len(runs(template, TEMPLATE_CHAR, ((ZERO, ONE),) * 4)) == 4, table
        sizes = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            sizes.add(len(program))
            assert self.run(program) == table[combo], (table, bits)
        assert len(sizes) == 1, (table, sizes)

    @pytest.mark.parametrize(
        ("table", "length", "route"),
        [
            ("00000000", 55, "small"),
            ("10000000", 105, "wide"),
            ("00010111", 131, "small"),
            ("01101001", 151, "small"),
        ],
    )
    def test_three_inputs_take_the_shorter_route(
        self, table: str, length: int, route: str
    ) -> None:
        """``n == 3`` builds both routes and keeps the shorter program."""
        from esolangs import tools as generators
        from esolangs.tools.one_two_three import _construct_small, _in_name_order
        from esolangs.tools.one_two_three.construction import _construct_linear

        small = len(_in_name_order(_construct_small(table, 3), 3))
        wide = len(_in_name_order(_construct_linear(table, 3), 3))
        assert (wide < small) == (route == "wide"), (small, wide)
        assert len(generators.one_two_three(table)) == length <= min(small, wide)

    def test_the_paint_pass_is_only_run_when_something_was_painted(
        self,
    ) -> None:
        """``b.test()`` after the paints is conditional, and the flag varies."""
        from esolangs import tools as generators

        total = 0
        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                total += len(generators.one_two_three(table))
        assert total == 35682

    def test_a_seed_with_even_positions_is_refused(self) -> None:
        """The junky verdict rejects a seed whose rows are not distinct odd."""
        from esolangs.tools.one_two_three import (
            _WORK_BUDGET,
            ConstructError,
            _separated,
            _verdict_junky,
            _work,
        )

        _work[0] = _WORK_BUDGET
        builder = _separated(1).clone()
        # Nudge one row onto an even cell; the law itself never does.
        builder.live()[0].pos += 1
        assert any(r.pos % 2 == 0 for r in builder.live())
        with pytest.raises(ConstructError) as caught:
            _verdict_junky(builder, "01")
        assert str(caught.value) == "verdict precondition: positions not distinct odd"

    def test_a_set_bit_replays_three_times_and_leaves_what_leftover_says(
        self,
    ) -> None:
        """The splitter's contract, re-simulated: 3 passes, and the leftovers."""
        from esolangs.tools.one_two_three.construction import (
            _exec_run,
            _leftover,
            _on_mark,
            _Row,
            _run_parts,
            _segment,
            _walk,
            _work,
        )

        for n in (1, 2, 3, 4, 5):
            _work[0] = 10**9
            bits = [tuple(map(int, format(r, f"0{n}b"))) for r in range(2**n)]
            rows = [_Row(b) for b in bits]
            for i in range(n):
                segment = _segment(i)[: -len("33")]
                for row in rows:
                    code = segment.replace(_X, ONE if row.bits[i] else ZERO)
                    passes = 0
                    while passes == 0 or _on_mark(row):
                        passes += 1
                        for part in _run_parts(code):
                            _exec_run(row, part[0], len(part))
                    assert passes == (3 if row.bits[i] else 1), (n, i, row.bits)
            start = sum(_walk(i) + 2 for i in range(n))
            for r, row in enumerate(rows):
                spread = int(format(r, f"0{n}b")[::-1], 2)
                assert row.pos == start + 2 * spread, (n, r, row.pos)
                for off in range(1, 2 * _walk(n - 1) + 3):
                    marked = bool(row.tape >> (row.pos + off + _RING) & 1)
                    assert marked == _leftover(n, row.bits[-1], off), (n, r, off)

    def test_paint_marks_one_cell_and_restores_every_position(self) -> None:
        """``_paint(k)`` flips exactly cell ``pos + k`` per row, in place."""
        from esolangs.tools.one_two_three.construction import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _paint,
            _work,
        )

        _work[0] = _WORK_BUDGET
        for k in (1, 2, 3, 17, 100):
            b = _Builder(2)
            tapes = (0, 0b1011 << _RING, 1 << (40 + _RING), 0b110 << _RING)
            for row, pos, tape in zip(b.rows, (1, 5, 29, 41), tapes, strict=True):
                row.pos, row.tape = pos, tape
            before = [(r.pos, r.tape) for r in b.rows]
            _paint(b, k)
            after = [(r.pos, r.tape) for r in b.rows]
            for (p0, t0), (p1, t1) in zip(before, after, strict=True):
                assert p1 == p0, k
                assert t1 == t0 ^ (1 << (p0 + k + _RING)), k

    def test_paint_all_sweeps_the_span_once(self) -> None:
        """The fused painter flips an arbitrary mask in one linear sweep."""
        from esolangs.tools.one_two_three.construction import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _paint_all,
            _work,
        )

        _work[0] = _WORK_BUDGET
        b = _Builder(2)
        for row, pos in zip(b.rows, (1, 5, 29, 41), strict=True):
            row.pos = pos
        before = [(r.pos, r.tape) for r in b.rows]
        _paint_all(b, [1, 3, 6])
        assert b.template() == "222222112112111211"
        delta = sum(1 << k for k in (1, 3, 6))
        for (p0, t0), row in zip(before, b.rows, strict=True):
            assert row.pos == p0
            assert row.tape == t0 ^ (delta << (p0 + _RING))

    def test_paint_all_replays_mixed_runs_exactly(self) -> None:
        """A conditional sweep replays ``21`` as two different commands."""
        from esolangs.tools.one_two_three.construction import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _paint_all,
            _work,
        )

        _work[0] = _WORK_BUDGET
        b = _Builder(1)
        b.rows[1].tape = 1 << (2 + _RING)
        b.run("2221")
        _paint_all(b, [7])
        b.test()
        assert [row.pos for row in b.rows] == [2, 4]
        assert all((row.tape >> (9 + _RING)) & 1 for row in b.rows)
        assert not (b.rows[0].tape >> (11 + _RING)) & 1
        assert (b.rows[1].tape >> (11 + _RING)) & 1

    def test_the_verdict_checks_its_position_preconditions(self) -> None:
        """A state violating the parity law raises instead of emitting."""
        from esolangs.tools.one_two_three.construction import (
            _WORK_BUDGET,
            ConstructError,
            _Builder,
            _verdict,
            _work,
        )

        _work[0] = _WORK_BUDGET
        even = _Builder(1)
        even.rows[0].pos, even.rows[1].pos = 2, 5
        with pytest.raises(ConstructError, match="precondition"):
            _verdict(even, "01")

        shared = _Builder(1)
        shared.rows[0].pos = shared.rows[1].pos = 5
        with pytest.raises(ConstructError, match="precondition"):
            _verdict(shared, "01")

        all_zero = _Builder(1)
        all_zero.rows[0].pos, all_zero.rows[1].pos = 2, 5
        _verdict(all_zero, "00")  # no 1-rows: nothing to prove, no check

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_small_geometry_separates_every_row(self, n: int) -> None:
        """The modeled route's complete arity domain needs no geometry probe."""
        from esolangs.tools.one_two_three import construction as module

        module._work[0] = module._WORK_BUDGET  # noqa: SLF001
        marks, escapes = module._geometry(n)  # noqa: SLF001
        builder = module._Builder(n)  # noqa: SLF001
        module._phase_a(builder, list(marks))  # noqa: SLF001
        module._close(builder)  # noqa: SLF001
        module._separate(builder, list(marks), escapes)  # noqa: SLF001
        rows = builder.live()
        assert len(rows) == 1 << n
        assert len({row.pos for row in rows}) == len(rows)
        assert all(row.pos % 2 for row in rows)
        assert not any(module._on_mark(row) for row in rows)  # noqa: SLF001
        assert all(row.tape >> (row.pos + 1 + module._RING) == 0 for row in rows)  # noqa: SLF001

    @pytest.mark.parametrize("n", [0, 4])
    def test_geometry_rejects_other_arities(self, n: int) -> None:
        from esolangs.tools.one_two_three.construction import _geometry

        with pytest.raises(ValueError, match="one through three"):
            _geometry(n)

    def test_linear_endgame_parks_all_four_residues(self) -> None:
        from esolangs.tools.one_two_three import construction as module

        positions = {0, 1, 2, 3}
        program = module._linear_endgame(positions)  # noqa: SLF001
        module._work[0] = module._WORK_BUDGET  # noqa: SLF001
        for pos in positions:
            row = module._Row(())  # noqa: SLF001
            row.pos = pos
            for command in program:
                module._exec_char(row, command)  # noqa: SLF001
            assert row.pos == -1

    def test_an_exhausted_work_budget_is_declined(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Budget exhaustion aborts without changing the mark geometry."""
        from esolangs.tools.one_two_three import construction as module

        geometry = module._geometry(3)  # noqa: SLF001
        with monkeypatch.context() as patch:
            patch.setattr(module, "_WORK_BUDGET", 50)
            with pytest.raises(ValueError, match="work budget ran out"):
                module.construct("00000000")
        assert module._geometry(3) == geometry  # noqa: SLF001
        assert module.construct("00000000")

    def test_normalize_reports_a_live_locked_ring(self) -> None:
        """Four distinct rows pinned to all four ring cells cannot escape."""
        from esolangs.tools.one_two_three.construction import (
            ConstructError,
            _Builder,
            _normalize,
            _Row,
            _work,
        )

        rows = []
        for i, pos in enumerate((-1, -2, -3, 0)):
            row = _Row((i,))
            row.pos = pos
            rows.append(row)
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = []
        b.rows = rows
        _work[0] = 100_000  # _normalize is called outside construct() here
        with pytest.raises(ConstructError, match="live-locked"):
            _normalize(b)

    def test_close_reports_no_clean_cell_in_range(self) -> None:
        """A row TRUE on every cell in the search window has no exit."""
        from esolangs.tools.one_two_three.construction import (
            ConstructError,
            _Builder,
            _close,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask(range(100002))
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = []
        b.rows = [row]
        _work[0] = 10_000_000  # _close is called outside construct() here
        with pytest.raises(ConstructError, match="no clean closing cell"):
            _close(b)

    def test_fixpoint_reports_a_non_converging_rerun(self) -> None:
        """A segment that never revisits a state within the cap gives up."""
        from esolangs.tools.one_two_three.construction import (
            ConstructError,
            _Builder,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask(range(200))
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["2"]
        b.rows = [row]
        _work[0] = 10_000  # fixpoint is called outside construct() here
        with pytest.raises(ConstructError, match="fixpoint cap"):
            b.fixpoint(row)

    def test_test_reports_a_kill_that_escapes(self) -> None:
        """``test(kills=...)`` requires every named victim to provably loop."""
        from esolangs.tools.one_two_three.construction import (
            ConstructError,
            _Builder,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask({0})
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["2"]  # pos 0 -> 1, leaves the tape: escapes, not a kill
        b.rows = [row]
        _work[0] = 10_000  # test() is called outside construct() here
        with pytest.raises(ConstructError, match="kill escaped"):
            b.test(kills=frozenset({(0,)}))

    def test_test_reports_a_kill_that_never_fires(self) -> None:
        """``test(kills=...)`` refuses a close where a victim tested FALSE."""
        from esolangs.tools.one_two_three.construction import (
            ConstructError,
            _Builder,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = 0  # nothing marked: the victim tests FALSE everywhere
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["2"]
        b.rows = [row]
        _work[0] = 10_000  # test() is called outside construct() here
        with pytest.raises(ConstructError, match="kill missed"):
            b.test(kills=frozenset({(0,)}))

    def test_test_reports_an_unintended_loop(self) -> None:
        """A plain ``test()`` requires every TRUE row to escape, not loop."""
        from esolangs.tools.one_two_three.construction import (
            ConstructError,
            _Builder,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask({0})
        # eight '1's flip cells 0,-1,-2,-3 twice each: pos and tape both
        # return to the start, a proven revisit where a plain test wants
        # an escape instead
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["1"] * 8
        b.rows = [row]
        _work[0] = 10_000  # test() is called outside construct() here
        with pytest.raises(ConstructError, match="unintended loop"):
            b.test()

    def test_an_empty_table_is_declined(self) -> None:
        """A table implying zero inputs raises rather than building nothing."""
        from esolangs import tools as generators

        # ``match`` is a substring search, so the equality below is what
        # actually pins the message.
        with pytest.raises(ValueError, match="at least one input") as caught:
            generators.one_two_three("1")
        assert str(caught.value) == (
            "truth table needs at least one input (n >= 1); "
            "a one-entry table is a constant, not a boolean function"
        )

    def test_each_input_is_embedded_once(self) -> None:
        """Each input's run appears exactly once, and nothing else is a run."""

        from esolangs import tools as generators

        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                template = generators.one_two_three(table)
                spans = runs(template, TEMPLATE_CHAR, ((ZERO, ONE),) * n)
                assert len(spans) == n, (table, spans)
                assert template.count(TEMPLATE_CHAR) == n * len(ZERO), table

    def test_every_batched_run_charges_the_work_budget(self) -> None:
        """Each closed form in ``_exec_run`` has to stop on a drained budget."""
        from esolangs.tools.one_two_three.construction import (
            _exec_char,
            _exec_run,
            _Row,
            _work,
            _WorkExhaustedError,
        )

        def drained(budget: int, ch: str, pos: int, w: int) -> None:
            row = _Row((0,))
            row.pos = pos
            _work[0] = budget
            _exec_run(row, ch, w)

        # The per-character fallback, reached directly.
        _work[0] = 0
        with pytest.raises(_WorkExhaustedError):
            _exec_char(_Row((0,)), "1")
        # `2` from pos >= 0: a plain right-walk.
        with pytest.raises(_WorkExhaustedError):
            drained(3, "2", 0, 10)
        # `1` from pos >= 0 stopping at -1 or above: one contiguous XOR.
        with pytest.raises(_WorkExhaustedError):
            drained(3, "1", 8, 5)
        # `1` descending past -1: the head above the ring boundary.
        with pytest.raises(_WorkExhaustedError):
            drained(2, "1", 5, 20)
        # `1` inside the ring: whole laps reduced to a parity.
        with pytest.raises(_WorkExhaustedError):
            drained(3, "1", -1, 12)

    def test_the_endgame_parks_survivors_and_reports_a_state_it_cannot(
        self,
    ) -> None:
        """Parking is what makes a template halt, so failing it must raise."""
        from esolangs.tools.one_two_three.construction import (
            _WORK_BUDGET,
            ConstructError,
            _Builder,
            _endgame,
            _Row,
            _work,
        )

        _work[0] = _WORK_BUDGET

        no_survivors = _Builder(1)
        for row in no_survivors.rows:
            row.dead = True
        _endgame(no_survivors)  # returns rather than dividing by no rows

        crowded = _Builder(2)
        for i, row in enumerate(crowded.rows):
            row.pos, row.tape = i, 0
        assert len({row.pos % 4 for row in crowded.live()}) == 4
        _endgame(crowded)
        assert {row.pos for row in crowded.live()} == {-1}

        stranded = _Builder.__new__(_Builder)
        stranded.n = 1  # an allowance of 192 passes
        stranded.chunks, stranded.seg = [], []
        stranded.rows = []
        for i in range(12):
            row = _Row((i,))
            row.pos, row.tape = i * 977, 0
            stranded.rows.append(row)
        with pytest.raises(ConstructError, match="endgame did not converge"):
            _endgame(stranded)

    def test_a_stage_refusal_surfaces_as_a_value_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stage that cannot prove its move is reported, never worked
        around -- the alternative is emitting a template no stage proved.
        """
        from esolangs.tools.one_two_three import construction as module

        def refuse(*_: object, **__: object) -> None:
            raise module.ConstructError("verdict precondition: constructed refusal")

        monkeypatch.setattr(module, "_verdict", refuse)
        with pytest.raises(ValueError, match="123 construction failed"):
            module.construct("0110")

    def test_a_looping_row_reads_as_a_one(self) -> None:
        """A 1-row is decided by cycle detection, not by halting."""
        from esolangs.tools.one_two_three.construction import construct
        from tests.tools.one_two_three_support import _replay_verdict

        template = construct("01")
        for bit in (0, 1):
            program = self.instantiate(template, [bit])
            assert self.run(program) == "01"[bit], bit
            assert _replay_verdict(program) == "01"[bit], bit

    def test_the_remaining_batched_run_and_token_paths(self) -> None:
        """``2`` from inside the ring batches too, and a plain token is a char."""
        from esolangs.tools.one_two_three.construction import (
            _WORK_BUDGET,
            _Builder,
            _exec_run,
            _Row,
            _work,
            _WorkExhaustedError,
        )

        inside_the_ring = _Row((0,))
        inside_the_ring.pos = -1
        _work[0] = 2
        with pytest.raises(_WorkExhaustedError):
            _exec_run(inside_the_ring, "2", 10)

        _work[0] = _WORK_BUDGET
        b = _Builder(1)
        b.apply_token(b.rows[0], "1")
        assert b.rows[0].pos == -1

    def test_a_two_at_minus_three_is_refused_rather_than_reading_stdin(self) -> None:
        """``2`` at -3 would read real input, so the move is rejected."""
        from esolangs.tools.one_two_three.construction import (
            _WORK_BUDGET,
            ConstructError,
            _exec_char,
            _Row,
            _work,
        )

        _work[0] = _WORK_BUDGET
        reads_stdin = _Row((0,))
        reads_stdin.pos = -3
        with pytest.raises(ConstructError, match="reads stdin"):
            _exec_char(reads_stdin, "2")

        wraps = _Row((0,))
        wraps.pos = -2
        _exec_char(wraps, "2")
        assert wraps.pos == 0

        steps = _Row((0,))
        steps.pos = 4
        _exec_char(steps, "2")
        assert steps.pos == 5

    def test_closing_walks_only_when_a_row_sits_on_a_true_cell(self) -> None:
        """``_close`` emits the walk it needs and nothing when already clean."""
        from esolangs.tools.one_two_three.construction import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _close,
            _work,
        )

        _work[0] = _WORK_BUDGET
        already_clean = _Builder(1)
        _close(already_clean)
        assert "2" not in "".join(already_clean.chunks)

        _work[0] = _WORK_BUDGET
        needs_a_walk = _Builder(1)
        needs_a_walk.run("1")  # flips cell 0 TRUE and steps into the ring
        _close(needs_a_walk)
        emitted = "".join(needs_a_walk.chunks)
        assert "2" in emitted
        # Every row ends on a cell that is FALSE, which is what "closed" means.
        assert all(
            row.pos >= 0 and not row.tape >> (row.pos + _RING) & 1
            for row in needs_a_walk.live()
        )

    def test_replaying_twos_handles_the_empty_walk_and_the_stdin_cell(self) -> None:
        """A zero-width run is a no-op; a run starting at -3 is refused."""
        from esolangs.tools.one_two_three.construction import ConstructError
        from tests.tools.one_two_three_support import _replay_twos

        # Nothing to walk: the state is handed straight back.
        assert _replay_twos(5, 0b1011, 0) == (5, 0b1011)
        assert _replay_twos(-3, 0, -2) == (-3, 0)  # a negative width is empty too

        with pytest.raises(ConstructError, match="reads stdin"):
            _replay_twos(-3, 0, 1)

    def test_replaying_a_verdict_skips_commandless_and_unknown_characters(
        self,
    ) -> None:
        """Only ``1`` and ``2`` are commands; everything else is a NOP."""
        from tests.tools.one_two_three_support import _replay_verdict

        assert _replay_verdict("") == "0"
        assert _replay_verdict("xyz") == "0"  # no command: nothing to run
        # The NOPs are skipped, so padding a program cannot change its verdict.
        assert _replay_verdict("1x1") == _replay_verdict("11")
        assert _replay_verdict("x1y1z") == _replay_verdict("11")


def test_a_malformed_template_is_refused() -> None:
    """The one-run-per-input invariant is asserted, not assumed."""
    from esolangs.tools.one_two_three import _in_name_order

    assert _in_name_order(_X * 2, 2) == _X * 2

    with pytest.raises(ValueError, match="does not embed 2 inputs"):
        _in_name_order(_X, 2)
    with pytest.raises(ValueError, match="does not embed 1 inputs"):
        _in_name_order(_X + "1" + _X, 1)
