"""Covers :mod:`esolangs.tools.laserfuck` and its layout module."""

import importlib

import pytest

from esolangs import tools as boolean
from esolangs.tools import laserfuck_layout
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

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("00000001", 3),  # AND3
            ("1111111100000000", 4),  # top half
            ("0110100110010110", 4),  # XOR4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.laserfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == str(int(table[combo])), f"inputs {bits} heading {heading}"

    # n=3 is 256 tables at 2.0s, over the fast run's one-second budget;
    # n=1 and n=2 are 16 tables between them and stay well under it.
    @pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.slow)])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.laserfuck(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_laserfuck(program, [str(b) for b in bits], 3)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_funnel_is_heading_independent(self) -> None:
        """Every initial heading reaches the tree on the top row."""
        program = boolean.laserfuck("0110")
        for heading in range(4):
            assert run_laserfuck(program, ["1", "0"], heading) == "1"

    def test_input_reordering_folds_a_scattered_table(self) -> None:
        """The tree splits in whichever order folds most, not input order.

        ``10101010`` depends on its last input alone, so it folds nothing
        splitting most-significant-first and everything once that input is
        tested at the root.  The reorder costs only the walk that puts the
        bit in the cell the root tests, which is paid once in the reader
        rather than per node -- so the two one-dependency tables come out
        the same size.
        """
        scattered = len(boolean.laserfuck("10101010"))
        aligned = len(boolean.laserfuck("11110000"))
        parity = len(boolean.laserfuck("01101001"))
        assert scattered == aligned
        assert aligned < parity

    def test_input_reordering_never_grows_a_program(self) -> None:
        """The identity order is built first and ties keep it.

        Parity folds under no order at all, so it has to emit exactly the
        program it emitted before reordering existed -- which is the plain
        read section, one ``,`` per cell stepping rightwards with no walk
        back and forth.
        """
        assert ",>,>," in boolean.laserfuck("01101001")

    def test_only_identity_and_greedy_orders_are_built(self) -> None:
        """Each table costs at most two orders with two named layouts each."""

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
            assert built == 2 * orders, f"n={n} built {built} candidates"

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_reordered_programs_compute_the_table(self, table: str) -> None:
        """A reordered program still computes its function, at every heading.

        The cell an input is read into is the *inverse* of the split order:
        a node steps then tests, so level ``k`` tests cell ``k + 1`` and has
        to be handed input ``perm[k]``.  Reading that forward stores the
        right bits in the wrong cells and computes a different function,
        which only running the program catches.
        """
        program = boolean.laserfuck(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == table[combo], f"{table} inputs {bits} heading {heading}"

    def test_reordering_keeps_the_reads_in_stream_order(self) -> None:
        """Reordering moves where a bit is stored, never when it is read.

        The program consumes its input stream exactly as it did before: one
        ``,`` per input, in input order.  What moves is the cell each lands
        in, so the count of reads is what pins this down.
        """
        for table in ("10101010", "11110000", "01101001"):
            assert boolean.laserfuck(table).count(",") == 3

    def test_decimal_output_mode(self) -> None:
        """No ``\\xff`` marker, so the tape dumps as numbers, not bytes.

        Byte mode would print the answer as ``chr(result)``, which is why
        the leaves used to add 48 to reach ASCII ``'0'``/``'1'``.  In decimal
        mode the leaf writes the result itself.
        """
        program = boolean.laserfuck("10")
        assert program.splitlines()[0][0] != "\u00ff"
        assert "\u00ff" not in program

    def test_prints_only_the_answer(self) -> None:
        """The dump is exactly the result: no input cells, no separators.

        The input cells are driven negative by the leaf, and ``dump`` skips
        negative cells, so nothing but the answer survives.
        """
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
        """``width`` bounds the columns and the table still computes.

        The grid's width is dominated by its straight runs -- 49 columns per
        input reader and another 49 per leaf -- so those fold into zigzags
        that cost rows instead.  The decision tree is not folded: its
        columns carry the descent paths.  Every heading is checked, since
        the fold adds cells the funnel's beam could otherwise land on.
        """
        program = boolean.laserfuck(table, width)
        assert max(len(line) for line in program.split("\n")) <= width
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == str(int(table[combo])), f"{bits} heading {heading}"

    def test_a_width_stands_the_reader_on_end(self) -> None:
        """A width too narrow for the reader rotates it rather than failing.

        Laid flat the rings are one row and forty-odd columns; stood on end
        they are two columns and forty-odd rows, so a width the flat form
        cannot meet is still met.
        """
        table = "01101001"  # XOR3
        natural = max(len(ln) for ln in boolean.laserfuck(table, 10_000).split("\n"))
        assert natural > 30
        narrow = boolean.laserfuck(table, 30).split("\n")
        assert max(len(ln) for ln in narrow) <= 30
        assert len(narrow) > len(boolean.laserfuck(table, 10_000).split("\n"))

    def test_the_fold_uses_its_return_rows(self) -> None:
        """A same-character run fills the leftward leg, not just the right.

        A return row's beam travels left, so it may only carry ops that
        read the same in reverse -- which a run of one repeated character
        does.  The boolean generator's readers are rings now, but the fold
        still lays every leaf band, so the fill is exercised directly here.
        """
        grid = [[" "] * 20 for _ in range(2)]
        end_row, end_col = laserfuck_layout.fold(grid, "-" * 30, 0, 3, 20)
        rows = ["".join(line).rstrip() for line in grid]
        assert rows[0].endswith("v")
        assert rows[1].endswith("{")
        assert "-" in rows[1], "the return row should carry the spilled run"
        # 30 ops at width 20: 16 on the segment row, the rest reversed onto
        # the return row, so the run never needs a second segment row.
        assert end_row == 2, "a same-character run should not need a third row"
        assert end_col == laserfuck_layout.MARGIN + 1

    def test_return_rows_only_take_a_same_character_run(self) -> None:
        """The fill stops at the first character that differs.

        A mixed run may only reverse its leading same-character stretch;
        whatever follows has to resume rightwards on the next segment row.
        """
        grid = [[" "] * 20 for _ in range(2)]
        laserfuck_layout.fold(grid, "-" * 30 + ">+++", 0, 3, 20)
        rows = ["".join(line).rstrip() for line in grid]
        body = rows[1][laserfuck_layout.MARGIN + 1 :].rstrip()
        ops = body[:-1].strip() if body.endswith("{") else body.strip()
        assert set(ops) <= {"-"}, f"mixed ops on a return row: {ops!r}"
        # the '>' that broke the run resumes on the next segment row
        assert ">" in rows[2]

    def test_folded_readers_are_rings(self) -> None:
        """The folded reader loops rather than writing 48 '-' per input.

        Two rings sit on the first row: one multiplies 8 by 6 to build the
        48 a ``,`` needs subtracting, the other spends that counter one unit
        at a time across the counter and every input.  Both are one row, so
        the reader costs a fixed two rows however many inputs there are.
        """
        rows = boolean.laserfuck("0110", 80).split("\n")
        # columns 0..2 are the funnel; the reader starts at the margin
        head = rows[0][laserfuck_layout.MARGIN :]
        legs = rows[1][laserfuck_layout.MARGIN :]
        assert head.count("}") == 3, "the reader's own '}' plus one per ring"
        assert head.count("#/)") == 2, "each ring tests its counter"
        assert legs.count("^") == 2, "each ring returns to its own '}'"
        # no 48-'-' run survives anywhere in the program
        assert "-" * 10 not in "\n".join(rows)

    def test_ringed_leaves_sit_on_their_own_descent_rows(self) -> None:
        """A leaf needs no corridor: the beam already arrives moving right.

        The old layout dropped each leaf down a private column into a band
        of its own below the tree.  With the rings the leaf simply follows
        the ``\\`` that turns the beam onto its row -- so no ``v``, no return
        row and no band, and the grid loses better than half its rows.
        """
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
        """A one-branch drops through the rows above its own catcher.

        Every ``v`` sends the beam down its column until a mirror faces it
        along a row again; whatever it passes on the way is executed.  The
        rows in between must therefore be blank in that column -- which is
        what lets the tree share rows at all.
        """
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
        """Given the width, the tree needs no rows of its own at all.

        The beam leaves the reader still moving right, so the cheapest
        thing is to carry straight on: the tree starts in the next column
        along, on the rows the reader is already using.  A width too narrow
        for that falls back to hanging the tree underneath, mirrored.
        """
        wide = boolean.laserfuck("0110", 80).split("\n")
        narrow = boolean.laserfuck("0110", 50).split("\n")
        assert len(wide) < len(narrow), "sharing rows should cost fewer rows"
        assert max(len(line) for line in wide) > max(len(line) for line in narrow)
        # the reader's own first row carries tree code too
        assert "#/)" in wide[0], "the reader's last ring is on row 0"
        assert ">#v)" in wide[0], "and the tree's first node follows it there"

    def test_widths_come_in_bands_not_a_cliff(self) -> None:
        """Each reader block turns on its own, so widths degrade gradually.

        Turning the whole reader at once gave two sizes and nothing in
        between; turning its blocks independently fills the gap, and a
        tighter width buys rows rather than being ignored.
        """
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
        """The drawing's extents, pinned.

        Almost everything the layout does is arithmetic on grid offsets --
        where the reader's blocks sit, how far the beam falls before it is
        caught, which column a node starts in.  An offset that drifts by
        one still draws a *working* program: the beam is steered by the
        characters it meets, not by absolute position, so the table still
        comes out right and only the shape moves.  The extents are the
        cheapest thing that sees it.
        """
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
        """XOR's layout at each width where the fit decision changes.

        The reader is stood on end one block at a time, and whether the
        next block still fits is a single comparison against the requested
        width.  These are the widths where that comparison flips: at 18 the
        grid is 47 rows and at 19 it is 36, and again between 27 and 28.
        An off-by-one in the fit test moves every one of these boundaries
        by one column, which no truth-table check and no monotonicity
        check can see -- the program still computes XOR at every width, and
        the sizes still decrease.
        """
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
        """One comparison chooses between the two whole layouts.

        Given room for the reader and the tree end to end, the tree runs
        straight on along the reader's own rows and costs no rows of its
        own; one column short of that, it is mirrored and hung underneath
        instead.  Both are correct programs of very different shape, so
        only the geometry sees which was taken -- and the switch is a
        single ``straight + 1 <= width``, whose ``+ 1`` and ``<=`` are
        exactly the kind of off-by-one that keeps computing the table.

        These are the widths where each table flips: one below is the
        mirrored shape, and at the flip the grid reaches the same extents
        it has with no width asked for at all.
        """
        below = boolean.laserfuck(table, flip - 1).split("\n")
        assert (len(below), max(len(line) for line in below)) == narrow

        at = boolean.laserfuck(table, flip).split("\n")
        assert (len(at), max(len(line) for line in at)) == wide

        # The compact build is allowed to choose either named placement.
        free = boolean.laserfuck(table).split("\n")
        assert len("\n".join(free)) <= len("\n".join(at))

    def test_the_grid_uses_only_laserfuck_characters(self) -> None:
        """Nothing but the language's own glyphs and layout space.

        A stray character in a beam's path is a command; one outside it is
        invisible.  Both are worth refusing outright, and the alphabet is
        small enough to name.
        """
        allowed = set(" #)+,-/<>\\^_ovx{|}\n")
        for table in ("01", "0110", "0001", "01101001", "11111110"):
            assert set(boolean.laserfuck(table)) <= allowed, table

    def test_no_row_carries_trailing_space(self) -> None:
        """Rows are trimmed, so the grid's width is its content's width.

        The width knob is measured against the longest row, so a row
        padded past its last glyph would quietly inflate every width
        decision that follows.
        """
        for table in ("01", "0110", "01101001"):
            for row in boolean.laserfuck(table).split("\n"):
                assert row == row.rstrip(), (table, repr(row))

    def test_a_narrow_width_beats_the_old_floor(self) -> None:
        """Standing blocks on end reaches widths the flat reader cannot."""
        for table, floor in (("0110", 18), ("01101001", 24)):
            program = boolean.laserfuck(table, floor).split("\n")
            assert max(len(line) for line in program) <= floor

    def test_ringed_leaves_leave_a_zero_answer_alone(self) -> None:
        """Cell 0 is the counter *and* the answer, so zero costs nothing.

        The rings spend the counter down to zero and leave it touched,
        which is exactly what dump() prints for a zero answer -- so a leaf
        writes a '+' only when the answer is one.

        Both tables are constant, so each folds to a single leaf that fits
        on the reader's own row; the '+' is counted over the whole program
        rather than over the rows below the reader, which a folded tree no
        longer occupies.
        """
        zero = boolean.laserfuck("0000", 80)
        ones = boolean.laserfuck("1111", 80)
        assert ones.count("+") == zero.count("+") + 1, "a one costs exactly one '+'"

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice becomes one leaf instead of branching further.

        Leaves are the ``x`` that ends each one, so counting those counts
        the leaves: a constant table spends one, two constant halves spend
        two, and a parity table -- which has no constant slice above a
        single row -- still spends one per combination.
        """
        assert boolean.laserfuck("11111111").count("x") == 1
        assert boolean.laserfuck("11110000").count("x") == 2
        assert boolean.laserfuck("10010110").count("x") == 8

    def test_a_table_that_folds_nothing_keeps_the_sized_sweep(self) -> None:
        """Parity's leaves retire each input by its own bit, not flatly.

        Only the cells above a leaf's depth need the flat two-``-``
        retiring; a parity table has no folded leaf, so every cell is one
        its path consumed and every run is sized to the bits.  Reading the
        runs back off each leaf is what pins that -- a leaf reached by
        ``bits`` spends ``bit + 1`` dashes per cell, most recent first.
        """
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
        """A width the tree cannot fit in is ignored rather than raising.

        The tree grows six columns per node and is never folded, so below
        some width there is nothing the fold can do; the generator emits the
        grid it can build instead of failing, matching the rest of the
        width plumbing.
        """
        program = boolean.laserfuck("01101001", 8)
        assert run_laserfuck(program, ["0", "0", "0"], 3) == "0"
