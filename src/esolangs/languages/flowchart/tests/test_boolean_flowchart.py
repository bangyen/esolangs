"""Covers :mod:`esolangs.languages.flowchart.generator`."""

from collections.abc import Callable
from itertools import pairwise

import pytest

from esolangs.languages import generators as boolean
from esolangs.languages.flowchart.generator import (
    _flowchart_cells,
    _flowchart_deque,
    _flowchart_render,
    _flowchart_stacked,
)
from esolangs.runtime.io import IO, ScriptedIO
from tests.generators.boolean_runners import _runner
from tests.support.witness_tables import row_bits

run_flowchart = _runner("flowchart", lines=True)


class TestFlowchart:
    """The Flowchart boolean generator (works for arbitrary n)."""

    @pytest.mark.parametrize(
        "table",
        ["00", "01", "0000", "0110", "11111111", "01101001", "0110100110010110"],
    )
    def test_an_unconstrained_call_uses_the_default_lookup(self, table: str) -> None:
        """Tree layouts remain available for width requests."""
        assert boolean.flowchart(table) == _flowchart_deque(table)

    @pytest.mark.parametrize(
        ("table", "length"),
        [("0011", 210), ("00000000000000111100001111000000", 606)],
    )
    def test_levels_past_the_last_switch_join_the_tail_at_eight_reads(
        self, table: str, length: int
    ) -> None:
        """The tail is emitted: eight ``/ /`` per level past the last switch."""
        program = boolean.flowchart(table)
        assert program == _flowchart_deque(table)
        assert len(program) == length
        if len(table) == 4:
            for row in range(4):
                bits = [str((row >> (1 - i)) & 1) for i in range(2)]
                assert run_flowchart(program, bits) == table[row], row

    def test_a_stacked_parity_tree_beats_the_flat_one(self) -> None:
        """From three inputs the stacked orientation is the shorter tree."""
        table = "01101001"
        flat = _flowchart_render(_flowchart_cells(table))
        stacked = _flowchart_render(_flowchart_stacked(table))
        assert len(stacked) < len(flat)
        assert boolean.flowchart(table, 1) == stacked

    @pytest.mark.medium
    def test_wide_deque_lookup_executes_every_row(self) -> None:
        """The cursor walk lands on exactly the indexed answer's deque."""
        n = 6
        table = "".join(str((row.bit_count() ^ (row >> 2)) & 1) for row in range(2**n))
        program = boolean.flowchart(table)
        for row in range(2**n):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_flowchart(program, bits) == table[row], row

    def test_wide_deque_lookup_scales_linearly(self) -> None:
        """The two-row layout grows no faster than its table doubles."""
        sizes = [len(boolean.flowchart("01" * (2 ** (n - 1)))) for n in range(7, 11)]
        assert all(b <= 2 * a for a, b in pairwise(sizes))

    def test_a_repeated_answer_is_set_once_and_pushed_twice(self) -> None:
        """A run of equal entries shares one set node and still answers."""
        table = "0011" * 8
        program = boolean.flowchart(table)
        assert program.count("[ }") + program.count("{ ]") < len(table)
        for row in (0, 1, 2, 3, 17, 30, 31):
            bits = [str((row >> (4 - i)) & 1) for i in range(5)]
            assert run_flowchart(program, bits) == table[row], row

    def test_tree_depth_matches_input_count(self) -> None:
        """One switch per internal node; the leaves share one end."""
        program = _flowchart_render(_flowchart_cells("0110100110010110"))
        assert program.count("< >") == 15  # 2**4 - 1 internal nodes
        assert program.count("[ }") + program.count("{ ]") == 16 + 3  # + answer
        assert program.count("(( ))") == 1

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice is one leaf, and takes one column band."""

        def tree(table: str) -> str:
            return _flowchart_render(_flowchart_cells(table))

        def leaves(table: str) -> int:
            return tree(table).count("[ }") + tree(table).count("{ ]") - 3

        assert leaves("11111111") == 1
        assert leaves("11110000") == 2
        assert leaves("10010110") == 8  # no fold
        # a constant table needs no switch at all
        assert tree("11111111").count("< >") == 0
        assert tree("11110000").count("< >") == 1
        # a width request retains the folded tree
        assert boolean.flowchart("11111111", 80) == tree("11111111")

    @pytest.mark.parametrize(
        "table", ["01", "0001", "01101001", "0110100110010110", "1000000000000000"]
    )
    def test_vertical_rails_meet_node_middles(self, table: str) -> None:
        """Every ``│`` connects to the middle of the node above and below it."""
        from esolangs.languages.flowchart.interpreter import _Machine

        drawing = _flowchart_render(_flowchart_cells(table))
        machine = _Machine(drawing.splitlines(), IO())
        for row, line in enumerate(machine.grid):
            for col, char in enumerate(line):
                if char != "│":
                    continue
                for neighbour in (row - 1, row + 1):
                    node = machine.nodes.get((neighbour, col))
                    if node is None:
                        continue
                    spelling, start = node
                    middle = start + len(spelling) // 2
                    assert col == middle, (
                        f"rail at ({col}, {row}) meets {spelling!r} at column {col}, "
                        f"but its middle is column {middle}"
                    )

    @pytest.mark.parametrize("table", ["0110100110010110", "1111", "0000000000000001"])
    def test_each_run_reads_exactly_n_bytes(self, table: str) -> None:
        """Every path reads ``8n - 7`` bits: all of n bytes but the last's top.

        The tree draws 1 + 8 reads per later internal node, and a folded
        leaf carries the reads its skipped levels owe.
        """
        from esolangs.languages.flowchart.interpreter import _Machine

        n = len(table).bit_length() - 1
        for name, text in (
            ("flat", _flowchart_render(_flowchart_cells(table))),
            ("stacked", _flowchart_render(_flowchart_stacked(table))),
            ("deque", _flowchart_deque(table)),
        ):
            program = text.splitlines()
            for row in range(2**n):
                stdin = format(row, f"0{n}b")
                io = ScriptedIO(stdin + "1")
                machine = _Machine(program, io)
                reads = 0
                read = machine._read_bit  # noqa: SLF001

                def counted(read: Callable[[], int | None] = read) -> int | None:
                    nonlocal reads
                    reads += 1
                    return read()

                machine._read_bit = counted  # noqa: SLF001
                while not machine.halted:
                    machine.step()
                assert reads == 8 * n - 7, (name, table, row)
                assert io.position() == n
                assert io.getvalue() == table[row]

    def test_a_width_stacks_the_tree_onto_one_column(self) -> None:
        """A narrower drawing is the same tree, separated by rows not columns."""
        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            flat = _flowchart_render(_flowchart_cells(table))
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.flowchart(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 12, 20, wide):
                narrow = boolean.flowchart(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = row_bits(combo, n)
                    got = run_flowchart(narrow, [str(b) for b in bits])
                    assert got == table[combo], (table, width, bits)

    def test_stacking_costs_rows_and_stops_tracking_the_table(self) -> None:
        """The stacked drawing is ``n + 6`` columns whatever the table."""
        for n in (2, 3, 4):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            flat = _flowchart_render(_flowchart_cells(table))
            stacked = boolean.flowchart(table, 1)
            assert max(len(row) for row in stacked.splitlines()) == n + 6, n
            assert max(len(row) for row in flat.splitlines()) == 6 * 2**n - 2, n
            assert len(stacked.splitlines()) > len(flat.splitlines()), n
        # A table that folds to a single leaf is already as wide as one
        # ``(( ))``, and stacking spends a corridor column per level on top
        # of that -- so there the flat drawing is the narrower of the two
        # and asking for any width keeps it.
        assert boolean.flowchart("1111", 1) == _flowchart_render(
            _flowchart_cells("1111")
        )

    def test_a_stacked_corridor_belongs_to_its_depth(self) -> None:
        """Depth ``d``'s zero-branch falls down column ``d``, and nothing else."""
        table = "0110100110010110"
        n = 4
        drawing = boolean.flowchart(table, 1)
        rows = drawing.splitlines()
        width = max(len(row) for row in rows)
        grid = [row.ljust(width) for row in rows]
        for x in range(n):
            column = {row[x] for row in grid} - {" "}
            assert column <= set("│┌└─"), (x, column)
        assert "┼" not in drawing, "a rail crossed a corridor"

    def test_a_width_draws_a_repeated_subtree_once(self) -> None:
        """Three copies of an 8-row block: rails to one drawing, every row right."""
        table = "01110001" + "10110010" * 3
        once = boolean.flowchart(table, 60)
        stacked = boolean.flowchart(table, 1)
        assert len(once.splitlines()) < 0.6 * len(stacked.splitlines())
        for row in range(32):
            bits = [str((row >> (4 - i)) & 1) for i in range(5)]
            assert run_flowchart(once, bits) == table[row], row


def test_a_shared_drawing_has_an_exact_size() -> None:
    """Repeated 8-row blocks drawn once and jumped to: size and rows."""
    table = "00010110" * 2 + "00111110" + "01111100"
    program = boolean.flowchart(table, 60)
    assert len(program) == 5751
    for row in range(32):
        bits = [str((row >> (4 - i)) & 1) for i in range(5)]
        assert run_flowchart(program, bits) == table[row], row


@pytest.mark.slow
def test_a_shared_drawing_reuses_a_freed_rail_column() -> None:
    """A later jump group reuses the rail column an earlier group freed.

    The repeated subtrees' entry rows stagger: one group's rail ends
    above a later group's first copy, so the later group takes the
    freed column instead of a fresh one; every row still answers.
    """
    table = "1000101010101010101010101010100010001010100010101010100010101000"
    program = boolean.flowchart(table, 16)
    assert program == _flowchart_render(_flowchart_stacked(table, share=True))
    for row in range(64):
        bits = [str((row >> (5 - i)) & 1) for i in range(6)]
        assert run_flowchart(program, bits) == table[row], row


@pytest.mark.parametrize("width", [1, 40])
def test_a_width_tree_branches_only_on_essential_inputs(width: int) -> None:
    """Ignored inputs cost their reads, not a switch: f(c, d) of four inputs."""
    table = "0110" * 4
    program = boolean.flowchart(table, width)
    assert program.count("< >") == 3
    for row in range(16):
        bits = [str((row >> (3 - i)) & 1) for i in range(4)]
        assert run_flowchart(program, bits) == table[row], row


@pytest.mark.medium
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_lookup_reads_without_deque_or_selector(bit) -> None:
    from tests.support.generator_support import assert_shared_program

    n = 8
    table = bit * (1 << n)
    program = boolean.flowchart(table)
    assert "< >" not in program
    assert "\\[ ]/" not in program
    assert_shared_program(
        "Flowchart",
        table,
        None,
        3 * (1 << n) + 9 * n + 4,
        lambda program: (
            (7 * (1 << n) + 20 * n + 100) * (len(program).bit_length() + 4)
            + sum(j.bit_length() + 2 for j in range(1 << (n - 1)))
            + 2 * len(program).bit_length()
            + n
            + 2 * n.bit_length()
            + 32
        ),
        size=lambda program: (
            len(program.splitlines()) * max(map(len, program.splitlines()))
        ),
    )


@pytest.mark.parametrize("table", ["0001", "0110", "01101001", "00010111", "11101000"])
def test_balanced_tree_folds_and_still_computes(table: str) -> None:
    """Snaking chains beats the tall tree's side by a third and keeps the table."""
    import esolangs
    from esolangs.generation.wrap import balance_score
    from esolangs.runtime._evaluate import _evaluate

    program = esolangs.generate("Flowchart", table, balance=True)
    tall = _flowchart_render(_flowchart_cells(table))
    assert balance_score(program)[0] * 3 <= balance_score(tall)[0] * 2
    assert _evaluate("Flowchart", program, inputs=len(table).bit_length() - 1) == table
