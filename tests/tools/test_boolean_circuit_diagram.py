"""Covers :mod:`esolangs.tools.circuit_diagram` and its layout guards."""

import hashlib
import importlib

import pytest

from esolangs import tools as boolean


# 6.2s over 99 tests: builds and runs banded drawings.
@pytest.mark.medium
class TestCircuitDiagramLayoutGuards:
    """The layout's collision checks, reached by constructing the state.

    ``_Layout`` asserts its own geometry as it is built: two signals may
    not run the same way through a cell, a glyph may not land on a wire or
    another glyph, and two different signals' junctions may not come within
    one cell of each other (a ``.`` connects to all eight neighbours, so
    adjacent junctions merge into one wiring).

    None of these fires on a table the generator actually builds -- swept
    over every table through three inputs, the closest two different
    signals' junctions ever come is Chebyshev distance 2, one clear of the
    guard.  That is the design working, and it is also why the guards were
    the single largest cluster of surviving mutants in the module: code
    that never runs cannot be wrong in a way a truth table notices.  So the
    states are built directly rather than searched for.

    Each check is asserted in both directions.  The negative cases are what
    stop a guard from being "fixed" by making it fire always: a wire may
    legally re-claim a cell for the *same* signal, may cross itself in the
    other direction, and same-signal junctions may touch.
    """

    @staticmethod
    def _layout() -> object:
        from esolangs.tools.circuit_diagram import _Layout

        return _Layout()

    def test_two_signals_may_not_run_the_same_way_through_a_cell(self) -> None:
        layout = self._layout()
        layout.run_horizontal(2, 5, 4, 7)
        with pytest.raises(AssertionError) as caught:
            layout.run_horizontal(2, 5, 4, 9)
        assert str(caught.value) == "two signals run horizontal through (3, 4)"
        layout = self._layout()
        layout.run_vertical(3, 2, 6, 1)
        with pytest.raises(AssertionError) as caught:
            layout.run_vertical(3, 2, 6, 2)
        assert str(caught.value) == "two signals run vertical through (3, 3)"

    def test_partly_overlapping_runs_clash_at_the_first_shared_cell(self) -> None:
        """Runs are intervals now, so overlap is not only exact re-tracing."""
        layout = self._layout()
        layout.run_horizontal(2, 6, 4, 7)
        with pytest.raises(AssertionError) as caught:
            layout.run_horizontal(4, 8, 4, 9)
        assert str(caught.value) == "two signals run horizontal through (5, 4)"

    def test_one_signal_may_reclaim_its_own_cells(self) -> None:
        """A repeated claim by the same signal is the ordinary case."""
        layout = self._layout()
        layout.run_horizontal(2, 5, 4, 7)
        layout.run_horizontal(2, 5, 4, 7)
        assert layout.render().split("\n")[4] == "   --"

    def test_two_signals_may_cross_at_right_angles(self) -> None:
        """The clash is per direction: crossing wires share the cell as ``=``."""
        layout = self._layout()
        layout.run_horizontal(2, 5, 4, 1)
        layout.run_vertical(3, 2, 6, 2)
        rows = layout.render().split("\n")
        assert rows[3] == "   |"
        assert rows[4] == "   =-"
        assert rows[5] == "   |"

    @pytest.mark.parametrize(
        ("run", "args"),
        [("run_horizontal", (2, 5, 4, 1)), ("run_vertical", (3, 2, 6, 1))],
    )
    def test_a_wire_may_not_cross_a_glyph(
        self, run: str, args: tuple[int, ...]
    ) -> None:
        """Both run directions consult the glyphs along their line."""
        layout = self._layout()
        layout.glyph(3, 4, "&")
        with pytest.raises(AssertionError) as caught:
            getattr(layout, run)(*args)
        assert str(caught.value) == "wire crosses glyph at (3, 4)"

    def test_a_glyph_may_not_land_on_a_glyph(self) -> None:
        layout = self._layout()
        layout.glyphs[(1, 1)] = "&"
        with pytest.raises(AssertionError) as caught:
            layout._check_free(1, 1)  # noqa: SLF001
        assert str(caught.value) == "two glyphs at (1, 1)"

    @pytest.mark.parametrize("axis", ["horizontal", "vertical"])
    def test_a_glyph_may_not_land_on_a_wire(self, axis: str) -> None:
        """Both wire tables are consulted, not just the first."""
        layout = self._layout()
        if axis == "horizontal":
            layout.run_horizontal(0, 2, 1, 1)
        else:
            layout.run_vertical(1, 0, 2, 1)
        with pytest.raises(AssertionError) as caught:
            layout._check_free(1, 1)  # noqa: SLF001
        assert str(caught.value) == "glyph at (1, 1) lands on a wire"

    def test_a_free_cell_takes_a_glyph(self) -> None:
        self._layout()._check_free(1, 1)  # noqa: SLF001

    def test_a_run_between_touching_junctions_records_nothing(self) -> None:
        """The span is exclusive, so neighbours leave no cell to claim.

        Two junctions a cell apart -- or the same one twice -- have an empty
        interior, and recording an empty interval would make the next run
        through that cell clash with nothing.
        """
        layout = self._layout()
        layout.run_vertical(3, 4, 4, 1)
        layout.run_vertical(3, 4, 5, 1)
        assert layout.render() == ""
        # A real span through the same cells still records, so the guard
        # above rejected the empty interval rather than the coordinates.
        layout.run_vertical(3, 2, 6, 1)
        assert layout.render() != ""

    def test_the_clash_scan_keeps_looking_after_its_first_hit(self) -> None:
        """The reported cell is the earliest, not the first one found.

        Runs are stored in the order they were laid, so a later entry can
        clash further left than an earlier one; the scan has to see every
        run before it names a coordinate.
        """
        from esolangs.tools.circuit_diagram import _Layout

        late_is_earlier = _Layout._clash(  # noqa: SLF001
            [(6, 9, 1), (2, 4, 2)], None, 0, 10, 9
        )
        assert late_is_earlier == (2, True)
        early_stays = _Layout._clash([(2, 4, 1), (6, 9, 2)], None, 0, 10, 9)  # noqa: SLF001
        assert early_stays == (2, True)

    @pytest.mark.parametrize(
        ("dx", "dy"),
        [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)],
    )
    def test_adjacent_junctions_of_different_signals_are_rejected(
        self, dx: int, dy: int
    ) -> None:
        """All eight neighbours, diagonals included, merge and so are refused.

        The message is compared whole rather than by substring: it names
        the offending pair, and the second coordinate is built from the
        same ``dx``/``dy`` the scan walks, so a sign slipped into it points
        the reader at a cell that holds nothing.  Which of the two
        junctions is reported first depends on dictionary order, so both
        readings are accepted -- the guard scans outwards from every
        junction, which is also why negating a loop offset is invisible.
        """
        layout = self._layout()
        layout.junctions[(5, 5)] = 1
        layout.junctions[(5 + dx, 5 + dy)] = 2
        with pytest.raises(AssertionError) as caught:
            layout._check_junction_spacing()  # noqa: SLF001
        assert str(caught.value) in (
            f"junctions of different signals touch at (5, 5) and ({5 + dx}, {5 + dy})",
            f"junctions of different signals touch at ({5 + dx}, {5 + dy}) and (5, 5)",
        )

    def test_junctions_of_the_same_signal_may_touch(self) -> None:
        """One signal's own junctions are a single wiring already."""
        layout = self._layout()
        layout.junctions[(5, 5)] = 1
        layout.junctions[(6, 6)] = 1
        layout._check_junction_spacing()  # noqa: SLF001

    def test_junctions_one_clear_of_each_other_are_accepted(self) -> None:
        """Distance 2 is what every real layout keeps, and it is legal."""
        layout = self._layout()
        layout.junctions[(5, 5)] = 1
        layout.junctions[(7, 5)] = 2
        layout._check_junction_spacing()  # noqa: SLF001

    @pytest.mark.parametrize(
        ("table", "rows", "columns"),
        [
            ("01", 1, 4),
            ("0001", 11, 17),
            ("0110", 23, 35),
            # 91 columns before gate groups were recycled, and the width is
            # what moves when they stop being: the rows are untouched, since
            # reuse gives back columns and never a band.
            ("00010111", 33, 49),
            # Four inputs, where the two savings compound: 219 columns as a
            # left fold with no reuse, 99 once groups were recycled, and 87
            # once the folds were balanced.  The rows never move -- neither
            # change gives back a band.
            ("0110100110010110", 107, 99),
        ],
    )
    def test_the_drawing_has_exact_dimensions(
        self, table: str, rows: int, columns: int
    ) -> None:
        """The band and column steps place every part of the drawing.

        A bus that starts a row lower, a gate band that advances by one
        step too many, or a signal counter seeded at 1 all draw a *valid*
        circuit -- the wires still connect the same gates and the table
        still comes out right -- at different coordinates.  Nothing else
        here can see that: the truth-table sweeps read the printed bit,
        and the collision guards only fire when the spacing collapses
        entirely rather than merely drifts.  The extents are the cheapest
        observable that moves when any of the layout constants does.
        """
        from esolangs.tools.circuit_diagram import circuit_diagram

        drawing = circuit_diagram(table).split("\n")
        assert len(drawing) == rows
        assert max(len(row) for row in drawing) == columns

    def test_the_online_fold_keeps_the_width_logarithmic(self) -> None:
        """Each extra input doubles the cofactors and costs a bounded step.

        A gate sits right of every bus it reads, so the drawing's width is
        set by the gate network's *depth*.  Folded left that depth is the
        number of parts, and an extra input would roughly double it; folded
        in half it is the logarithm, so an extra input adds one level.

        The pins are what a regression would move.
        """
        widths = {}
        for n in (3, 4, 5, 6):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            drawing = boolean.circuit_diagram(table)
            widths[n] = max(len(row) for row in drawing.splitlines())
        assert widths == {3: 67, 4: 99, 5: 131, 6: 163}
        steps = [widths[n + 1] - widths[n] for n in (3, 4, 5)]
        assert max(steps) <= 32, steps

    def test_the_online_fold_holds_only_one_partial_per_level(self) -> None:
        """Binary carries combine immediately rather than accumulating a level.

        Delaying carries would put every cofactor result on a bus of its own,
        spending in columns what immediate binary carries save.
        """
        # A level-wide fold would need sixteen live buses here.
        table = "".join(str(bin(i).count("1") % 2) for i in range(32))
        drawing = boolean.circuit_diagram(table)
        assert max(len(row) for row in drawing.splitlines()) == 131

    @pytest.mark.slow
    def test_emitted_size_is_linear_in_the_table(self) -> None:
        """A doubled dense table does not increase characters per entry."""
        sizes = []
        for n in (8, 9):
            digest = hashlib.sha256(f"dense:{n}".encode()).digest()
            bits = []
            block = 0
            while len(bits) < 2**n:
                digest = hashlib.sha256(digest + bytes([block & 255])).digest()
                bits.extend(str(byte & 1) for byte in digest)
                block += 1
            sizes.append(len(boolean.circuit_diagram("".join(bits[: 2**n]))))
        assert sizes[1] <= 2 * sizes[0], sizes

    def test_h_layout_reserves_linear_area(self) -> None:
        """Two input levels quarter recursively without overlapping leaves."""
        from esolangs.tools.circuit_diagram import _h_blocks, _h_sites, _h_size

        for n in range(1, 12):
            blocks = _h_blocks(n)
            leaf_depth = n if n % 2 == 0 else n - 1
            leaves = [
                block for prefix, block in blocks.items() if len(prefix) == leaf_depth
            ]
            assert len(leaves) == 2**leaf_depth
            assert len({(block.x, block.y) for block in leaves}) == len(leaves)
            sites = _h_sites(n)
            assert len(sites) == 2**n - 1
            assert len(set(sites.values())) == len(sites)
            assert _h_size(n) ** 2 <= 80_000 * 2**n

    @pytest.mark.slow
    def test_h_layout_executes_every_two_input_table(self) -> None:
        """The routed minterm and reduction trees compute all small functions."""
        from esolangs.interpreters.grid_based.circuit_diagram import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.circuit_diagram import _h_term_layout

        for value in range(1, 15):
            table = format(value, "04b")
            program = _h_term_layout(table).render().splitlines()
            output = []
            for index in range(4):
                bits = format(index, "02b")
                io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
                run(program, io)
                output.append(io.getvalue())
            assert "".join(output) == table

    def test_layout_index_stops_past_the_probe(self) -> None:
        """The interval guard stops once later wires and glyphs are reached."""
        from esolangs.tools.circuit_diagram import _Layout

        assert (
            _Layout._clash(  # noqa: SLF001 - exercise the interval primitive
                [(10, 12, 1)], [10], 0, 5, 0
            )
            is None
        )

    def test_invert_can_start_a_new_band(self) -> None:
        """A complement honors a width already exhausted by its input."""
        from esolangs.tools.circuit_diagram import _Builder

        builder = _Builder()
        source = builder.input_bus()
        builder.limit = 0
        builder.band_start = builder.next_column
        assert builder.invert(source) != source

    def test_real_layouts_never_come_within_one_cell(self) -> None:
        """The generator's spacing keeps every table clear of the guard.

        The guard is a net, not a mechanism -- this is the property that
        makes it never fire, measured rather than assumed, so a spacing
        regression names itself here instead of tripping an assertion deep
        in a render.
        """
        from esolangs.tools.circuit_diagram import _Layout, circuit_diagram

        closest = []
        original = _Layout._check_junction_spacing  # noqa: SLF001

        def record(layout: object) -> None:
            items = list(layout.junctions.items())
            for index, ((x1, y1), first) in enumerate(items):
                for (x2, y2), second in items[index + 1 :]:
                    if first != second:
                        closest.append(max(abs(x1 - x2), abs(y1 - y2)))
            original(layout)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(_Layout, "_check_junction_spacing", record)
            for table_int in range(16):
                circuit_diagram(format(table_int, "04b"))
        assert closest, "no layout carried two signals' junctions"
        assert min(closest) >= 2

    @staticmethod
    def _run_at(table: str, width: int | None) -> str:
        """The banded program's output for every input, in table order."""
        from esolangs.interpreters.grid_based.circuit_diagram import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.circuit_diagram import circuit_diagram

        n = len(table).bit_length() - 1
        program = circuit_diagram(table, width).split("\n")
        results = []
        for index in range(len(table)):
            stdin = "".join(f"{bit}\n" for bit in format(index, f"0{n}b"))
            io = ScriptedIO(stdin)
            run(program, io)
            results.append(io.getvalue())
        return "".join(results)

    @pytest.mark.slow
    def test_a_width_bands_the_drawing_and_it_still_computes(self) -> None:
        """Banding carries the live signals left; the circuit is unchanged.

        A gate must sit right of every bus it reads, so a group freed
        behind the drawing is unusable and the width grows with the
        network's depth.  A band moves what is still live back to the left
        and frees everything behind it -- and a wire that merged with
        another would be wrong in a way only a run would show, so this runs
        every input combination.
        """
        from esolangs.tools.circuit_diagram import circuit_diagram

        # ``00101111`` at 30 is the case that bands on the final ``~``: a
        # dense table is drawn from its zero rows and inverted, and that one
        # gate sits past the whole network, where it used to run over the
        # width because only ``gate`` checked.
        for table in ("01101001", "0110100110010110", "00010111", "00101111"):
            flat = circuit_diagram(table)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in circuit_diagram(table, 1).splitlines())
            for width in (1, 30, 50, 60, 80, wide):
                narrow = circuit_diagram(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                assert self._run_at(table, width) == table, (table, width)

    def test_banding_brings_every_arity_inside_eighty(self) -> None:
        """Which is the point: unbanded, parity clears 80 columns at n == 4.

        The floor is what a band cannot reclaim -- the rails and the
        complements, read by every minterm and so live for the whole
        drawing -- so it grows with the *inputs* rather than with the
        table, which is why it stays well under 80 while the flat drawing
        does not.
        """
        from esolangs.tools.circuit_diagram import circuit_diagram

        for n in (4, 5, 6):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            flat = circuit_diagram(table)
            banded = circuit_diagram(table, 80)
            assert max(len(row) for row in flat.splitlines()) > 80, n
            assert max(len(row) for row in banded.splitlines()) <= 80, n
            # and it costs rows, which is the trade
            assert len(banded.splitlines()) > len(flat.splitlines()), n

    @pytest.mark.slow
    def test_a_band_must_re_carry_what_an_earlier_one_moved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Forgetting a carried signal hands its column away while it is live.

        That is how this first went wrong, and it is the layout guard that
        caught it rather than a wrong answer.  Making ``_band`` forget makes
        it fire again -- so the guard is what licenses the banding, not a
        check that happens to pass.
        """

        from esolangs.tools.circuit_diagram import _Builder

        module = importlib.import_module("esolangs.tools.circuit_diagram")
        original = getattr(_Builder, "_band")  # noqa: B009 - SLF001 otherwise

        def forgetful(self: _Builder) -> None:
            original(self)
            self.live.clear()

        table = "".join(str(bin(i).count("1") % 2) for i in range(32))
        monkeypatch.setattr(_Builder, "_band", forgetful)
        with pytest.raises(AssertionError, match="two signals run vertical"):
            module.circuit_diagram(table, 40)
        monkeypatch.undo()
        # and with the carry kept, the same drawing builds and computes
        assert self._run_at(table, 40) == table


class TestCircuitDiagram:
    """The Circuit Diagram generator (a real gate network, input-reading).

    Circuit Diagram draws boolean circuits, so a truth table is its native
    idiom.  The generator folds adjacent cofactors into fixed mux circuits:
    ``n`` input lines, one shared complement per selector that needs it,
    and a ``:`` that prints the final signal.

    Every assertion here replays the generated program through the real
    interpreter over the table's *whole* input space, which is what makes
    the layout trustworthy: a wire that merges into its neighbour or a gate
    fed a generation late shows up as a wrong bit, and no static check on
    the ASCII would catch either.
    """

    @staticmethod
    def run_table(table: str) -> str:
        """Return the generated program's output for every input, in order."""
        from esolangs.interpreters.grid_based.circuit_diagram import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.circuit_diagram import circuit_diagram

        n = len(table).bit_length() - 1
        program = circuit_diagram(table).split("\n")
        results = []
        for index in range(len(table)):
            bits = format(index, f"0{n}b")
            stdin = "".join(f"{bit}\n" for bit in bits)
            io = ScriptedIO(stdin)
            run(program, io)
            results.append(io.getvalue())
        return "".join(results)

    @pytest.mark.parametrize("table", [format(i, "04b") for i in range(16)])
    def test_every_two_input_table(self, table: str) -> None:
        """All sixteen two-input functions, each over all four inputs."""
        assert self.run_table(table) == table

    @pytest.mark.parametrize("table", ["01", "10", "00", "11"])
    def test_every_one_input_table(self, table: str) -> None:
        assert self.run_table(table) == table

    @pytest.mark.parametrize(
        "table",
        ["00010111", "01101001", "11110000", "00000000", "11111111"],
    )
    def test_three_input_tables(self, table: str) -> None:
        """Majority, parity, a projection, and both constants."""
        assert self.run_table(table) == table

    @pytest.mark.parametrize(
        ("table", "tildes"),
        [
            ("0001", 1),  # selector 0 chooses whether selector 1 matters
            ("01", 0),  # identity: likewise
            ("10", 1),  # NOT is the complemented selector
            ("0110", 2),  # XOR: both inputs appear negated and plain
        ],
    )
    def test_only_needed_complements_are_built(self, table: str, tildes: int) -> None:
        """A ``~`` is drawn only when a mux rule needs the inverse selector."""
        from esolangs.tools.circuit_diagram import circuit_diagram

        assert circuit_diagram(table).count("~") == tildes

    def test_complementary_sparse_tables_have_comparable_drawings(self) -> None:
        """Shannon folding handles a function and its complement symmetrically."""
        from esolangs.tools.circuit_diagram import circuit_diagram

        dense = circuit_diagram("11111110")  # NAND3: seven ones
        sparse = circuit_diagram("00000001")  # its complement: one
        assert len(dense) < 2 * len(sparse)
        # both compute their own table, whichever way they were drawn
        assert self.run_table("11111110") == "11111110"
        assert self.run_table("00000001") == "00000001"

    def test_a_constant_table_is_never_complemented(self) -> None:
        """It is already one gate, so complementing only swaps the glyph.

        An all-ones table is the trap: complementing leaves no minterms at
        all, which is the all-zeros shape, so the result would print the
        wrong constant unless the table is excluded outright.
        """
        assert self.run_table("1111") == "1111"
        assert self.run_table("0000") == "0000"

    def test_four_input_primality(self) -> None:
        """The same function the wiki's own worked example computes.

        The wiki's prime tester is a hand-drawn product of sums; this is the
        generator's sum of minterms for the same table, so the two agree on
        every one of the sixteen inputs by different constructions.
        """
        primes = {n for n in range(2, 16) if all(n % d for d in range(2, n))}
        table = "".join("1" if n in primes else "0" for n in range(16))
        assert self.run_table(table) == table

    def test_each_run_prints_exactly_one_bit(self) -> None:
        """The output wire is live for exactly one generation.

        A ``:`` prints in every generation its wire carries a value, so a
        second driver on any wiring -- or two wirings merged by adjacent
        junctions -- would show up as extra characters even when the value
        happens to be right.
        """
        from esolangs.interpreters.grid_based.circuit_diagram import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.circuit_diagram import circuit_diagram

        for table in ("0001", "0110", "00010111"):
            n = len(table).bit_length() - 1
            program = circuit_diagram(table).split("\n")
            for index in range(len(table)):
                stdin = "".join(f"{b}\n" for b in format(index, f"0{n}b"))
                io = ScriptedIO(stdin)
                run(program, io)
                assert len(io.getvalue()) == 1

    def test_input_lines_start_with_a_dash(self) -> None:
        """Each bit arrives on its own line, which the spec makes an input."""
        from esolangs.tools.circuit_diagram import circuit_diagram

        rows = circuit_diagram("00010111").split("\n")
        starts = [row for row in rows if row.startswith("-")]
        assert len(starts) == 3

    def test_a_malformed_table_is_rejected(self) -> None:
        from esolangs.tools.circuit_diagram import circuit_diagram

        with pytest.raises(ValueError, match="power-of-two"):
            circuit_diagram("010")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            circuit_diagram("012x")
