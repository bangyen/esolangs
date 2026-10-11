"""Covers :mod:`esolangs.tools.one_two_three.construction`."""

from collections.abc import Iterable

import pytest

from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs, runs
from esolangs.tools.one_two_three import ONE, ZERO
from esolangs.tools.one_two_three.construction import _RING
from tests.support.witness_tables import row_bits, witnesses
from tests.tools.boolean_runners import one_two_three_result


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
                bits = row_bits(combo, n)
                got = self.run(self.instantiate(template, bits))
                assert got == table[combo], (table, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """A zero and a one embed at equal width, so length leaks nothing."""
        from esolangs import tools as generators

        for table in witnesses(2):
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
        """``test(kills=...)`` refuses a close where a victim tested false."""
        from esolangs.tools.one_two_three.construction import (
            ConstructError,
            _Builder,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = 0  # nothing marked: the victim tests false everywhere
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
            for table in witnesses(n):
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

    def test_the_endgame_reports_a_state_it_cannot_park(self) -> None:
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

    def test_a_looping_row_reads_as_a_one(self) -> None:
        """A 1-row is decided by cycle detection, not by halting."""
        from esolangs import tools as generators
        from tests.tools.one_two_three_support import _replay_verdict

        template = generators.one_two_three("01")
        for bit in (0, 1):
            program = self.instantiate(template, [bit])
            assert self.run(program) == "01"[bit], bit
            assert _replay_verdict(program) == "01"[bit], bit

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


def test_a_malformed_template_is_refused() -> None:
    """The one-run-per-input invariant is asserted, not assumed."""
    from esolangs.tools.one_two_three import _in_name_order

    assert _in_name_order(_X * 2, 2) == _X * 2

    with pytest.raises(ValueError, match="does not embed 2 inputs"):
        _in_name_order(_X, 2)
    with pytest.raises(ValueError, match="does not embed 1 inputs"):
        _in_name_order(_X + "1" + _X, 1)


def test_ignored_trailing_inputs_idle_past_the_end() -> None:
    """Each input past the last essential one appends a run that keeps rows below 0."""
    from esolangs.interpreters.tape_based.one_two_three import _advance, _landings
    from esolangs.tools.one_two_three import _IDLE, one_two_three

    for fill in (ZERO, ONE):
        code = _IDLE.replace(_X, fill)
        for start in (-1, -2, -3):
            state = (0, start, frozenset[int](), False)
            while not state[3]:
                ip, pos = state[0], state[1]
                assert ip >= len(code) or (code[ip], pos) != ("2", -3), "a read"
                state = _advance(state, code, _landings(code))
            assert state[1] < 0, (fill, start)

    base = "0110"
    table = "".join(bit * 4 for bit in base)  # inputs 2 and 3 are ignored
    template = one_two_three(table)
    assert template == one_two_three(base) + _IDLE * 2
    for row, want in enumerate(table):
        bits = [row >> shift & 1 for shift in (3, 2, 1, 0)]
        code = fill_runs(template, TEMPLATE_CHAR, ((ZERO, ONE),) * 4, bits)
        assert one_two_three_result(code) == want, row
