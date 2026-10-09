"""Covers :mod:`esolangs.tools.arrowqueue`."""

import random
from itertools import pairwise

import pytest

from esolangs.tools.arrowqueue import PAIR
from esolangs.tools.helpers import TEMPLATE_CHAR, runs
from tests.tools.fills import _instantiate_arrowqueue


class TestParameterizedArrowQueue:
    """Input-by-substitution boolean generator for the no-input language ArrowQueue."""

    def run_arrowqueue(self, prog: str) -> str:
        from esolangs.interpreters.grid_based.arrowqueue import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        return "0" if run_until_halt_or_cycle(_Machine(prog.splitlines())) else "1"

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        return _instantiate_arrowqueue(tpl, bits)

    def test_random_tables(self) -> None:
        """Seeded random tables through five inputs produce the right result."""
        from esolangs import tools as generators

        random.seed(13)
        for n in (1, 2, 3, 4, 5):
            for _ in range(2):
                table = "".join(random.choice("01") for _ in range(2**n))
                template = generators.arrowqueue(table)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    got = self.run_arrowqueue(self.instantiate(template, bits))
                    assert got == table[combo], f"{table} inputs {bits}"

    def test_linear_marker_cascade_executes_every_row(self) -> None:
        """Wide inputs become marker counts and select one cascade stage."""
        from esolangs import tools as generators

        n = 6
        table = "".join(str((row.bit_count() ^ (row >> 2)) & 1) for row in range(2**n))
        template = generators.arrowqueue(table)
        sizes = set()
        for row in range(2**n):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            program = self.instantiate(template, bits)
            sizes.add(len(program))
            assert self.run_arrowqueue(program) == table[row], row
        assert len(sizes) == 1

    def test_linear_marker_cascade_scales_with_table(self) -> None:
        """Dense wide templates grow no faster than the table doubles."""
        from esolangs import tools as generators

        sizes = [len(generators.arrowqueue("1" * (2**n))) for n in range(7, 11)]
        assert all(b <= 2 * a for a, b in pairwise(sizes))

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs import tools as generators

        template = generators.arrowqueue("0110")
        assert "{X" not in template
        setters = (PAIR,) * 2
        assert template.count(TEMPLATE_CHAR) == sum(len(zero) for zero, _ in setters)
        assert len(runs(template, TEMPLATE_CHAR, setters)) == 2

    @pytest.mark.parametrize("table", ["0110", "0110100110010110" * 2])
    def test_every_input_is_the_same_one_cell(self, table: str) -> None:
        """Both routes spell every input as one cell, ``.`` against ``~``."""
        from esolangs import tools as generators

        n = len(table).bit_length() - 1
        template = generators.arrowqueue(table)
        setters = (PAIR,) * n
        assert setters == ((".", "~"),) * n
        assert template.count(TEMPLATE_CHAR) == n
        assert len(runs(template, TEMPLATE_CHAR, setters)) == n
        filled = self.instantiate(template, [1] * n)
        assert filled.count("\n") == template.count("\n")
        assert len(filled) == len(template)

    def test_cascade_stage_doubles_and_adds(self) -> None:
        """A stage turns ``m`` queued markers and a bit into ``2m + bit``."""
        from esolangs.interpreters.grid_based.arrowqueue import _advance, _Machine
        from esolangs.tools.arrowqueue import _STAGE

        for m in range(6):
            for bit in (0, 1):
                rows = [
                    row.replace(TEMPLATE_CHAR, "~" if bit else ".") for row in _STAGE
                ]
                machine = _Machine(rows)
                # Entered heading down onto the ``+``, with ``m`` down
                # markers and the previous stage's right heading queued.
                state = (0, 3, 1, (*([1] * m), 0), False)
                for _ in range(10_000):
                    if state[4] or (state[0] == len(rows) and state[1] == 3):
                        break
                    state = _advance(state, machine.grid, machine.width)
                row, col, d, queue, done = state
                assert (row, col, d, done) == (len(rows), 3, 1, True), (m, bit)
                assert queue == (*([1] * (2 * m + bit)), 0), (m, bit)

    @pytest.mark.parametrize(
        ("table", "mixed"),
        [
            ("1111", "1010"),
            ("11110000", "10010110"),
            ("1111111100000000", "1001011001101001"),
        ],
    )
    def test_constant_subtrees_fold(self, table: str, mixed: str) -> None:
        """A constant subtree emits one drained leaf, not a full branch set."""
        from esolangs import tools as generators

        assert len(generators.arrowqueue(table)) < len(generators.arrowqueue(mixed))

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("1" * 16, 4),
            ("0" * 16, 4),
            ("1111111100000000", 4),
            ("1111000000000000", 4),
            ("1" * 32, 5),
            ("1" * 16 + "0" * 16, 5),
        ],
    )
    def test_folded_tables_past_three_inputs(self, table: str, n: int) -> None:
        """Folded leaves stay correct deeper than the exhaustive n <= 3 sweep."""
        from esolangs import tools as generators

        template = generators.arrowqueue(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_arrowqueue(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize(
        "table",
        [
            "0" * 32,
            "0" * 31 + "1",
            "1" * 31 + "0",
            "0" * 16 + "1" * 16,
            "01" * 8 + "1" * 16,
            "10" * 8 + "0" * 16,
            "0110" * 4 + "1" * 48,
            "1" + "0" * 63,
        ],
    )
    def test_cascade_folds_its_constant_tail(self, table: str) -> None:
        """Past four inputs the table's constant tail folds to one row or none."""
        from esolangs import tools as generators
        from esolangs.tools.arrowqueue import _IGNORED, _MIDDLE, _STAGE
        from esolangs.tools.helpers import input_weights

        n = len(table).bit_length() - 1
        template = generators.arrowqueue(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_arrowqueue(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"
        # An ignored input is one setter row; the cascade indexes the rest.
        weights, kept = input_weights(table, n)
        m = sum(map(bool, weights))
        tail = len(kept) - len(kept.rstrip(kept[-1]))
        stages = len(_STAGE) * m + len(_IGNORED) * (n - m)
        rows = 1 + stages + len(_MIDDLE) + 3 * len(kept)
        folded = 3 * (tail if kept[-1] == "0" else tail - 1)
        assert template.count("\n") + 1 == rows - folded

    def test_reusable_drain_pops_every_marker(self) -> None:
        """One drained ring sustains for any marker count; a bare row does not."""
        from esolangs.interpreters.grid_based.arrowqueue import _Machine
        from esolangs.tools.arrowqueue import _DRAINED_RING, _ROWS
        from esolangs.vm import run_until_halt_or_cycle

        def verdict(rows: list[str], markers: int) -> str:
            machine = _Machine(list(rows))
            machine.state = (0, 1, 1, (*([1] * markers), 0, 0, 1, 2, 3), False)
            return "0" if run_until_halt_or_cycle(machine) else "1"

        assert all(verdict(_DRAINED_RING, m) == "1" for m in range(64))
        assert verdict(_ROWS["1"], 0) == "1"
        assert not any(verdict(_ROWS["1"], m) == "1" for m in range(1, 64))

    def test_fold_keeps_equal_width_embedding(self) -> None:
        """Every instantiation of a folded template is the same length."""
        from esolangs import tools as generators

        for table, n in (("1111", 2), ("1100", 2), ("11110000", 3)):
            template = generators.arrowqueue(table)
            sizes = {
                len(
                    self.instantiate(
                        template, [(c >> (n - 1 - i)) & 1 for i in range(n)]
                    )
                )
                for c in range(2**n)
            }
            assert len(sizes) == 1, f"{table}: {sizes}"
