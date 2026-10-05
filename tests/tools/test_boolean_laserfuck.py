"""Covers :mod:`esolangs.tools.laserfuck` and its layout module."""

import importlib

import pytest

from esolangs import tools as boolean
from esolangs.tools.laserfuck import layout as laserfuck_layout
from tests.interpreters.laserfuck_observer import check


def run_laserfuck(program, bits, heading):
    return check(program, "".join(bits), heading)[0]


class TestLaserFuck:
    def test_compact_layout_compares_straight_and_hanging_trees(self) -> None:
        """Explicit widths retain the old straight and hanging layouts."""
        table = "01101001" * 32
        natural = boolean.laserfuck(table, width=10_000)
        hanging = boolean.laserfuck(table, width=1)
        assert len(hanging) < len(natural)

    # n=3 is 256 tables at 2.0s, over the fast run's one-second budget;
    # n=1 and n=2 are 16 tables between them and stay well under it.

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


def test_overhead_funnel_width_floor() -> None:
    assert max(map(len, boolean.laserfuck("0110", 1).splitlines())) == 4


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
    source = esolangs.generate("LaserFuck", table, width)
    if max(map(len, legacy.splitlines())) <= width:
        assert source == legacy
    for heading in range(4):
        for row, expected in enumerate(table):
            assert run_laserfuck(source, list(f"{row:02b}"), heading) == expected
