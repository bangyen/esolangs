"""Covers :mod:`esolangs.tools.laserfuck`."""

import importlib
import random

import pytest

from esolangs import tools as boolean
from esolangs.tools.laserfuck import MARGIN
from tests.support.witness_tables import row_bits, witnesses
from tests.tools.boolean_runners import (
    run_laserfuck,
)


class TestLaserFuck:
    def test_compact_layout_compares_straight_and_hanging_trees(self) -> None:
        """Explicit widths retain the old straight and hanging layouts."""
        table = "01101001" * 32
        natural = boolean.laserfuck(table, width=10_000)
        hanging = boolean.laserfuck(table, width=1)
        assert len(hanging) < len(natural)

    @pytest.mark.medium
    def test_weighted_table_executes_every_row(self) -> None:
        """The linear default computes dense tables at every initial heading."""
        for n in (5, 6):
            size = 1 << n
            tables = (
                ("01101001" * (size // 8))[:size],
                "".join(str((i * 73 + i // 3) & 1) for i in range(size)),
            )
            for table in tables:
                program = boolean.laserfuck(table)
                for combo in range(size):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    for heading in range(4):
                        assert run_laserfuck(program, bits, heading) == table[combo]

    def test_an_ignored_input_crosses_no_arm(self) -> None:
        """The weighted lookup reads an ignored input but indexes the rest."""
        # Five inputs, the middle one ignored: rows pair up across bit 2.
        table = "".join("0110100110010110"[(r >> 3) << 2 | r & 3] for r in range(32))
        program = boolean.laserfuck(table)
        assert program.count("#v)") == 4
        for combo in range(32):
            bits = [str((combo >> (4 - i)) & 1) for i in range(5)]
            assert run_laserfuck(program, bits, 0) == table[combo]

    def test_input_reordering_folds_a_scattered_table(self) -> None:
        """The tree splits in whichever order folds most, not input order."""
        scattered = len(boolean.laserfuck("10101010"))
        aligned = len(boolean.laserfuck("11110000"))
        parity = len(boolean.laserfuck("01101001"))
        assert scattered == aligned
        assert aligned < parity

    def test_input_reordering_never_grows_a_program(self) -> None:
        """The identity order is built first and ties keep it."""
        assert ",>,>," in boolean.laserfuck("01101001")

    def test_only_identity_and_greedy_orders_are_built(self) -> None:
        """Each table costs at most two orders, one natural layout each."""

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.laserfuck")
        real = module._laserfuck_build  # noqa: SLF001

        for n, table, orders in ((3, "01011010", 2),):
            built = 0

            def counted(*args: object, _build: object = real, **kwargs: object) -> str:
                nonlocal built
                built += 1
                return _build(*args, **kwargs)  # type: ignore[operator, no-any-return]

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(module, "_laserfuck_build", counted)
                boolean.laserfuck(table)
            assert built == orders, f"n={n} built {built} candidates"

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_reordered_programs_compute_the_table(self, table: str) -> None:
        """A reordered program still computes its function, at every heading."""
        program = boolean.laserfuck(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == table[combo], f"{table} inputs {bits} heading {heading}"

    def test_reordering_keeps_the_reads_in_stream_order(self) -> None:
        """Reordering moves where a bit is stored, never when it is read."""
        for table in ("10101010", "11110000", "01101001"):
            assert boolean.laserfuck(table).count(",") == 3

    def test_decimal_output_mode(self) -> None:
        """No ``\\xff`` marker, so the tape dumps as numbers, not bytes."""
        program = boolean.laserfuck("10")
        assert program.splitlines()[0][0] != "\u00ff"
        assert "\u00ff" not in program

    def test_prints_only_the_answer(self) -> None:
        """The dump is exactly the result: no input cells, no separators."""
        program = boolean.laserfuck("0001")  # AND2
        for bits, want in (([0, 1], "0"), ([1, 1], "1")):
            got = run_laserfuck(program, [str(b) for b in bits], 3)
            assert got == want, f"inputs {bits}"

    def test_loop_free_tree(self) -> None:
        """The decision tree branches with #, ) and a turning mirror."""
        program = boolean.laserfuck("0110")
        assert "#" in program
        assert ")" in program
        # the tree is mirrored, so a one-branch turns on '/' rather than '\\'
        assert "/" in program

    @pytest.mark.parametrize(
        ("table", "n", "width"),
        [
            # The tree is never folded and grows six columns per node, so the
            # narrowest width a table can honour rises with its input count:
            # roughly 19, 34, and 63 columns for one, two, and three inputs.
            ("01", 1, 20),
            ("01", 1, 40),
            ("10", 1, 80),
            ("0110", 2, 34),
            ("0110", 2, 80),
            ("1000", 2, 120),
            ("01101001", 3, 63),
            ("01101001", 3, 80),
            ("11111110", 3, 120),
        ],
    )
    def test_honours_a_width(self, table: str, n: int, width: int) -> None:
        """``width`` bounds the columns and the table still computes."""
        program = boolean.laserfuck(table, width)
        assert max(len(line) for line in program.split("\n")) <= width
        for combo in range(2**n):
            bits = row_bits(combo, n)
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == str(int(table[combo])), f"{bits} heading {heading}"

    def test_a_width_stands_the_reader_on_end(self) -> None:
        """A width too narrow for the reader rotates it rather than failing."""
        table = "01101001"  # XOR3
        natural = max(len(ln) for ln in boolean.laserfuck(table, 10_000).split("\n"))
        assert natural > 30
        narrow = boolean.laserfuck(table, 30).split("\n")
        assert max(len(ln) for ln in narrow) <= 30
        assert len(narrow) > len(boolean.laserfuck(table, 10_000).split("\n"))

    def test_folded_readers_are_rings(self) -> None:
        """The folded reader loops rather than writing 48 '-' per input."""
        rows = boolean.laserfuck("0110", 80).split("\n")
        # columns 0..2 are the funnel; the reader starts at the margin
        head = rows[0][MARGIN:]
        legs = rows[1][MARGIN:]
        assert head.count("}") == 3, "the reader's own '}' plus one per ring"
        assert head.count("#/)") == 2, "each ring tests its counter"
        assert legs.count("^") == 2, "each ring returns to its own '}'"
        # no 48-'-' run survives anywhere in the program
        assert "-" * 10 not in "\n".join(rows)

    def test_ringed_leaves_sit_on_their_own_descent_rows(self) -> None:
        """A leaf needs no corridor: the beam already arrives moving right."""
        # width 50 forces the mirrored form, where the tree hangs below
        rows = boolean.laserfuck("0110", 50).split("\n")
        # 'x' only ever ends a leaf, so the leaf rows are exactly these
        leaves = [line for line in rows if "x" in line]
        assert len(leaves) == 4, "one leaf per input combination"
        # the all-zero leaf rides the row the tree starts on, so only the
        # mirrored, a one-branch's leaf hangs under a '/' and its code runs
        # leftward, so the 'x' comes *before* the turn.  The all-zero leaf
        # shares the tree's first row, which carries the entry mirror too.
        first = min(index for index, line in enumerate(rows) if "x" in line)
        turned = [
            line for index, line in enumerate(rows) if "x" in line and index > first
        ]
        assert len(turned) == 3
        for line in turned:
            assert line.index("x") < line.index("/")
        # nothing below the leaves: no bands, no drop corridors.  Mirrored,
        # a leaf's row ends at its turn rather than at its 'x'.
        assert rows[-1].rstrip()[-1] in "x/"

    def test_a_dropping_beam_crosses_no_other_row_s_code(self) -> None:
        """A one-branch drops through the rows above its own catcher."""
        for table in ("0110", "01101001", "0110100110010110"):
            rows = boolean.laserfuck(table, 200).split("\n")
            for index, line in enumerate(rows):
                for column, char in enumerate(line):
                    if char != "v" or index < 3:
                        continue  # the funnel and reader steer themselves
                    # find the '\' that catches this drop
                    below = [
                        (k, rows[k])
                        for k in range(index + 1, len(rows))
                        if column < len(rows[k])
                    ]
                    for k, lower in below:
                        cell = lower[column]
                        if cell in "\\/":
                            break  # caught, as intended
                        assert cell == " ", (
                            f"{table}: beam from row {index} column {column} "
                            f"runs {cell!r} on row {k}"
                        )

    def test_a_wide_grid_runs_the_tree_on_the_reader_s_rows(self) -> None:
        """Given the width, the tree needs no rows of its own at all."""
        wide = boolean.laserfuck("0110", 80).split("\n")
        narrow = boolean.laserfuck("0110", 50).split("\n")
        assert len(wide) < len(narrow), "sharing rows should cost fewer rows"
        assert max(len(line) for line in wide) > max(len(line) for line in narrow)
        # the reader's own first row carries tree code too
        assert "#/)" in wide[0], "the reader's last ring is on row 0"
        assert ">#v)" in wide[0], "and the tree's first node follows it there"

    def test_widths_come_in_bands_not_a_cliff(self) -> None:
        """Each reader block turns on its own, so widths degrade gradually."""
        seen = {
            max(len(line) for line in boolean.laserfuck("0110", width).split("\n"))
            for width in (45, 40, 30, 25, 18)
        }
        assert len(seen) >= 4, f"expected several distinct widths, got {seen}"
        # asking for less never gives more
        widths = [
            max(len(line) for line in boolean.laserfuck("0110", w).split("\n"))
            for w in (45, 40, 30, 25, 18)
        ]
        assert widths == sorted(widths, reverse=True)

    @pytest.mark.parametrize(
        ("table", "rows", "columns"),
        [
            ("01", 3, 44),
            ("0001", 3, 56),
            ("0110", 4, 56),
            ("11111110", 4, 68),
            ("01101001", 8, 68),
        ],
    )
    def test_the_grid_has_exact_dimensions(
        self, table: str, rows: int, columns: int
    ) -> None:
        """The drawing's extents, pinned."""
        grid = boolean.laserfuck(table).split("\n")
        assert len(grid) == rows
        assert max(len(line) for line in grid) == columns

    @pytest.mark.parametrize(
        ("width", "rows", "columns"),
        [
            (18, 47, 18),
            (19, 36, 18),
            (27, 28, 26),
            (28, 25, 27),
            (35, 17, 34),
            (44, 6, 43),
        ],
    )
    def test_the_width_steps_land_where_they_should(
        self, width: int, rows: int, columns: int
    ) -> None:
        """XOR's layout at each width where the fit decision changes."""
        grid = boolean.laserfuck("0110", width).split("\n")
        assert len(grid) == rows
        assert max(len(line) for line in grid) == columns

    @pytest.mark.parametrize(
        ("table", "flip", "narrow", "wide"),
        [
            ("11111110", 69, (6, 49), (4, 68)),
            ("01101001", 69, (10, 49), (8, 68)),
        ],
    )
    def test_the_straight_layout_starts_at_its_exact_width(
        self,
        table: str,
        flip: int,
        narrow: tuple[int, int],
        wide: tuple[int, int],
    ) -> None:
        """One comparison chooses between the two whole layouts."""
        below = boolean.laserfuck(table, flip - 1).split("\n")
        assert (len(below), max(len(line) for line in below)) == narrow

        at = boolean.laserfuck(table, flip).split("\n")
        assert (len(at), max(len(line) for line in at)) == wide

        # The compact build is allowed to choose either named placement.
        free = boolean.laserfuck(table).split("\n")
        assert len("\n".join(free)) <= len("\n".join(at))

    def test_the_grid_uses_only_laserfuck_characters(self) -> None:
        """Nothing but the language's own glyphs and layout space."""
        allowed = set(" #)+,-/<>\\^_ovx{|}\n")
        for table in ("01", "0110", "0001", "01101001", "11111110"):
            assert set(boolean.laserfuck(table)) <= allowed, table

    def test_no_row_carries_trailing_space(self) -> None:
        """Rows are trimmed, so the grid's width is its content's width."""
        for table in ("01", "0110", "01101001"):
            for row in boolean.laserfuck(table).split("\n"):
                assert row == row.rstrip(), (table, repr(row))

    def test_a_narrow_width_beats_the_old_floor(self) -> None:
        """Standing blocks on end reaches widths the flat reader cannot."""
        for table, floor in (("0110", 18), ("01101001", 24)):
            program = boolean.laserfuck(table, floor).split("\n")
            assert max(len(line) for line in program) <= floor

    def test_ringed_leaves_leave_a_zero_answer_alone(self) -> None:
        """Cell 0 is the counter *and* the answer, so zero costs nothing."""
        zero = boolean.laserfuck("0000", 80)
        ones = boolean.laserfuck("1111", 80)
        assert ones.count("+") == zero.count("+") + 1, "a one costs exactly one '+'"

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice becomes one leaf instead of branching further."""
        assert boolean.laserfuck("11111111").count("x") == 1
        assert boolean.laserfuck("11110000").count("x") == 2
        assert boolean.laserfuck("10010110").count("x") == 8

    def test_a_table_that_folds_nothing_keeps_the_sized_sweep(self) -> None:
        """Parity's leaves retire each input by its own bit, not flatly."""
        program = boolean.laserfuck("10010110")
        leaves = program.split("x")[:-1]
        for path in range(8):
            bits = [(path >> (2 - i)) & 1 for i in range(3)]
            want = "".join("-" * (b + 1) + "<" for b in reversed(bits))
            assert any(leaf.endswith(want) or want in leaf for leaf in leaves), (
                f"no leaf retires {bits} with its sized run {want!r}"
            )

    def test_without_a_width_is_unchanged(self) -> None:
        """The default stays exactly what the generator always produced."""
        for table in ("01", "10", "0110", "01101001"):
            assert boolean.laserfuck(table) == boolean.laserfuck(table, None)

    def test_too_narrow_a_width_is_ignored(self) -> None:
        """A width the tree cannot fit in is ignored rather than raising."""
        program = boolean.laserfuck("01101001", 8)
        assert run_laserfuck(program, ["0", "0", "0"], 3) == "0"


@pytest.mark.parametrize("heading", range(4))
def test_overhead_funnel_executes_the_witness_tables(heading: int) -> None:
    for n in range(1, 4):
        for table in witnesses(n):
            program = boolean.laserfuck(table, 1)
            for row in range(2**n):
                assert (
                    run_laserfuck(program, list(format(row, f"0{n}b")), heading)
                    == table[row]
                )


def test_overhead_funnel_floor_and_corpus_size() -> None:
    assert max(map(len, boolean.laserfuck("0110", 1).splitlines())) == 4
    assert len(boolean.laserfuck("0110", 1)) == 569
    assert sum(len(boolean.laserfuck(format(v, "04b"), 1)) for v in range(16)) == 9104
    assert (
        sum(len(boolean.laserfuck(format(v, "08b"), 1)) for v in range(256)) == 102623
    )


@pytest.mark.parametrize("n", [5, 7])
def test_overhead_funnel_larger_tables(n: int) -> None:
    rng = random.Random(20260930 + n)
    for table in (
        "".join(str(row.bit_count() & 1) for row in range(2**n)),
        format(rng.getrandbits(2**n), f"0{2**n}b"),
    ):
        program = boolean.laserfuck(table, 1)
        for row in rng.sample(range(2**n), 12):
            for heading in range(4):
                assert (
                    run_laserfuck(program, list(format(row, f"0{n}b")), heading)
                    == table[row]
                )


def test_valid_more_expensive_input_order_keeps_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from esolangs.tools.laserfuck import _laserfuck_build

    module = importlib.import_module("esolangs.tools.laserfuck")
    table = "01101001"
    identity = _laserfuck_build(table, (0, 1, 2), 80)
    alternative = _laserfuck_build(table, (1, 0, 2), 80)
    assert len(alternative) > len(identity)
    monkeypatch.setattr(module, "input_orders", lambda _table: [(0, 1, 2), (1, 0, 2)])
    selected = boolean.laserfuck(table, 80)
    assert selected == identity
    for row, expected in enumerate(table):
        bits = list(format(row, "03b"))
        for heading in range(4):
            assert run_laserfuck(selected, bits, heading) == expected
            assert run_laserfuck(alternative, bits, heading) == expected


@pytest.mark.parametrize("width", [1, 7, 9, 10, 15, 18, 20, 40, 80])
def test_vertical_tree_preserves_fitting_public_layouts(width: int) -> None:
    import esolangs
    from esolangs.tools.laserfuck import _laserfuck_build, _laserfuck_raise_funnel

    table = "0110"
    legacy = _laserfuck_build(table, (0, 1), width)
    if max(map(len, legacy.splitlines())) > width:
        legacy = _laserfuck_raise_funnel(legacy)
    source = esolangs.generate("LaserFuck", table, width=width)
    if max(map(len, legacy.splitlines())) <= width:
        assert source == legacy
    for heading in range(4):
        for row, expected in enumerate(table):
            assert run_laserfuck(source, list(f"{row:02b}"), heading) == expected


@pytest.mark.parametrize(("table", "perm"), [("0001", (1, 0)), ("10010110", (2, 0, 1))])
def test_vertical_tree_places_permuted_inputs_in_stream_order(
    table: str, perm: tuple[int, ...]
) -> None:
    from esolangs.tools.helpers import permute_truth_table
    from esolangs.tools.laserfuck import _laserfuck_build, _laserfuck_raise_funnel

    source = _laserfuck_build(
        permute_truth_table(table, perm), perm, 1, vertical_tree=True
    )
    source = _laserfuck_raise_funnel(source)
    for row, expected in enumerate(table):
        for heading in range(4):
            assert (
                run_laserfuck(source, list(f"{row:0{len(perm)}b}"), heading) == expected
            )


@pytest.mark.parametrize("width", [1, 40])
def test_a_width_tree_tests_only_essential_inputs(width: int) -> None:
    """Ignored inputs cost a bare step, not a node: f(c, d) of four inputs."""
    table = "0110" * 4
    program = boolean.laserfuck(table, width)
    assert len(program) < len(boolean.laserfuck("0110100110010110", width))
    for row in range(16):
        assert run_laserfuck(program, list(format(row, "04b")), 0) == table[row]
