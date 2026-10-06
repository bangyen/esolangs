"""Covers :mod:`esolangs.tools.circuit_diagram` and its layout guards."""

import hashlib
import importlib

import pytest

from esolangs import tools as boolean
from tests.witness_tables import witnesses


# 6.2s over 99 tests: builds and runs banded drawings.
@pytest.mark.medium
class TestCircuitDiagramLayoutGuards:
    """The layout's collision checks, reached by constructing the state."""

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
        """The span is exclusive, so neighbours leave no cell to claim."""
        layout = self._layout()
        layout.run_vertical(3, 4, 4, 1)
        layout.run_vertical(3, 4, 5, 1)
        assert layout.render() == ""
        # A real span through the same cells still records, so the guard
        # above rejected the empty interval rather than the coordinates.
        layout.run_vertical(3, 2, 6, 1)
        assert layout.render() != ""

    def test_the_clash_scan_keeps_looking_after_its_first_hit(self) -> None:
        """The reported cell is the earliest, not the first one found."""
        from esolangs.tools.circuit_diagram import _Layout

        late_is_earlier = _Layout._clash(  # noqa: SLF001
            [(6, 9, 1), (2, 4, 2)], None, 0, 10, 9
        )
        assert late_is_earlier == (2, True)
        early_stays = _Layout._clash([(2, 4, 1), (6, 9, 2)], None, 0, 10, 9)  # noqa: SLF001
        assert early_stays == (2, True)

    def test_interval_primitives_keep_order_and_the_earliest_clash(self) -> None:
        """Guard-only insertion and a later glyph preserve the first hit."""
        from esolangs.tools.circuit_diagram import _Layout

        runs = [(6, 9, 2)]
        _Layout._record(runs, (2, 4, 1))  # noqa: SLF001
        assert runs == [(2, 4, 1), (6, 9, 2)]
        assert _Layout._clash(runs, [7], 0, 10, 9) == (2, True)  # noqa: SLF001

    @pytest.mark.parametrize(
        ("dx", "dy"),
        [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)],
    )
    def test_adjacent_junctions_of_different_signals_are_rejected(
        self, dx: int, dy: int
    ) -> None:
        """All eight neighbours, diagonals included, merge and so are refused."""
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

    def test_the_online_fold_keeps_the_width_logarithmic(self) -> None:
        """Each extra input doubles the cofactors and costs a bounded step."""
        widths = {}
        for n in (3, 4, 5, 6):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            drawing = boolean.circuit_diagram(table)
            widths[n] = max(len(row) for row in drawing.splitlines())
        assert widths == {3: 67, 4: 99, 5: 131, 6: 163}
        steps = [widths[n + 1] - widths[n] for n in (3, 4, 5)]
        assert max(steps) <= 32, steps

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
        from esolangs.tools.circuit_diagram.hlayout import _h_blocks, _h_sites, _h_size

        for n in range(1, 12):
            blocks = _h_blocks(n)
            leaf_depth = n if n % 2 == 0 else n - 1
            leaves = [
                block
                for prefix, block in blocks.items()
                if prefix.bit_length() - 1 == leaf_depth
            ]
            assert len(leaves) == 2**leaf_depth
            assert len({(block.x, block.y) for block in leaves}) == len(leaves)
            sites = _h_sites(n)
            assert len(sites) == 2**n - 1
            assert len(set(sites.values())) == len(sites)
            assert _h_size(n) ** 2 <= 10_000 * 2**n

    def test_h_depth_buckets_bound_literal_anchor_visits(self) -> None:
        from esolangs.tools.circuit_diagram.hlayout import _h_term_plan

        for n in range(2, 13):
            plan = _h_term_plan("01" * (1 << (n - 1)))
            assert len(plan.levels) == n + 1
            assert sum(map(len, plan.levels)) == len(plan.sites) == 2 ** (n + 1) - 1
            for depth, nodes in enumerate(plan.levels):
                assert len(nodes) == 1 << depth
                assert set(nodes) == set(range(1 << depth, 1 << (depth + 1)))
            visits = 2 * sum(
                (n - depth) * len(nodes) for depth, nodes in enumerate(plan.levels)
            )
            assert visits == 4 * (1 << n) - 2 * n - 4

    @pytest.mark.slow
    def test_h_layout_executes_every_two_input_table(self) -> None:
        """The routed minterm and reduction trees compute all small functions."""
        from esolangs.interpreters.grid_based.circuit_diagram import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.circuit_diagram.hlayout import _h_term_layout

        for value in range(1, 15):
            table = format(value, "04b")
            program = _h_term_layout(table).render().splitlines()
            output = []
            for index in range(4):
                bits = format(index, "02b")
                io = ScriptedIO("".join(f"{bit}" for bit in bits))
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
        """The generator's spacing keeps every table clear of the guard."""
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
            stdin = "".join(f"{bit}" for bit in format(index, f"0{n}b"))
            io = ScriptedIO(stdin)
            run(program, io)
            results.append(io.getvalue())
        return "".join(results)

    @pytest.mark.slow
    def test_a_width_bands_the_drawing_and_it_still_computes(self) -> None:
        """Banding carries the live signals left; the circuit is unchanged."""
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

    def test_narrow_gate_groups_preserve_every_small_table(self) -> None:
        """Compact groups and native XOR gates preserve every small table."""
        from esolangs.tools.circuit_diagram import circuit_diagram

        program = circuit_diagram("0110", 1)
        assert max(map(len, program.splitlines())) == 4
        for n in range(1, 4):
            for table in witnesses(n):
                assert self._run_at(table, 1) == table

    def test_affine_floor_uses_native_xor_in_public_programs(self) -> None:
        """The output returns beneath the native XOR gate."""
        import esolangs

        program = esolangs.generate("Circuit Diagram", "0110", 1)
        assert max(map(len, program.splitlines())) == 4
        assert len(program) == 32
        assert "x" in program
        # The old six-column gate already fits this request.
        assert "x.-:" in str(esolangs.generate("Circuit Diagram", "0110", 6))
        for table in ("0110", "1001"):
            for width in (1, 4, 5, 6, 9, 11, 19):
                assert self._run_at(table, width) == table

    def test_native_affine_chains_verify_constants_and_complements(self) -> None:
        from esolangs.interpreters.grid_based.circuit_diagram import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.circuit_diagram import _affine_circuit

        for n in range(1, 4):
            for table in witnesses(n):
                program = _affine_circuit(table, 1)
                if program is None:
                    continue
                for row, expected in enumerate(table):
                    io = ScriptedIO(format(row, f"0{n}b"))
                    run(program.splitlines(), io)
                    assert io.getvalue() == expected
                    assert io.reads == n

    def test_output_columns_fit_the_affine_and_mux_boundary(self) -> None:
        from esolangs.tools.circuit_diagram import circuit_diagram

        for table in ("00000001", "01101001", "0110100110010110"):
            floor = max(map(len, circuit_diagram(table, 1).splitlines()))
            for width in range(1, 25):
                program = circuit_diagram(table, width)
                assert max(map(len, program.splitlines())) <= max(width, floor)
                assert self._run_at(table, width) == table

    def test_banding_brings_every_arity_inside_eighty(self) -> None:
        """Which is the point: unbanded, parity clears 80 columns at n == 4."""
        from esolangs.tools.circuit_diagram import circuit_diagram

        for n in (4, 5, 6):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            flat = circuit_diagram(table)
            banded = circuit_diagram(table, 80)
            assert max(len(row) for row in flat.splitlines()) > 80, n
            assert max(len(row) for row in banded.splitlines()) <= 80, n
            # Compact groups can fit without a band; actual bands add rows.
            assert len(banded.splitlines()) >= len(flat.splitlines()), n
            assert self._run_at(table, 80) == table

    @pytest.mark.slow
    def test_a_band_must_re_carry_what_an_earlier_one_moved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Forgetting a carried signal hands its column away while it is live."""

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
    """The Circuit Diagram generator (a real gate network, input-reading)."""

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
            stdin = "".join(f"{bit}" for bit in bits)
            io = ScriptedIO(stdin)
            run(program, io)
            results.append(io.getvalue())
        return "".join(results)

    @pytest.mark.parametrize(
        ("table", "tildes"),
        [
            ("0001", 0),  # AND: ``0/x`` and ``0/1`` read plain rails only
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
        assert [dense.count(glyph) for glyph in "ao~"] == [0, 2, 3]
        assert [sparse.count(glyph) for glyph in "ao~"] == [2, 0, 0]
        # both compute their own table, whichever way they were drawn
        assert self.run_table("11111110") == "11111110"
        assert self.run_table("00000001") == "00000001"

    def test_a_constant_table_is_never_complemented(self) -> None:
        """It is already one gate, so complementing only swaps the glyph."""
        assert self.run_table("1111") == "1111"
        assert self.run_table("0000") == "0000"

    @pytest.mark.parametrize("table", ["0000111100010001", "0000111101110111"])
    def test_equal_cofactors_from_different_gates_still_get_a_complement(
        self, table: str
    ) -> None:
        """The fold compares signals, not functions, so ``0001|0001`` muxes."""
        assert self.run_table(table) == table

    def test_four_input_primality(self) -> None:
        """The same function the wiki's own worked example computes."""
        primes = {n for n in range(2, 16) if all(n % d for d in range(2, n))}
        table = "".join("1" if n in primes else "0" for n in range(16))
        assert self.run_table(table) == table

    @pytest.mark.slow  # ~3s: 256 builds of up to four orders, eight rows each
    def test_every_three_input_table_under_its_chosen_order(self) -> None:
        """A reordered fold still reads its rails in input order."""
        for table in witnesses(3):
            assert self.run_table(table) == table

    @pytest.mark.parametrize(
        ("table", "winner"),
        [
            # One four-input table per candidate that alone is shortest.
            ("1001111101010101", 0),  # identity
            ("1001100001000001", 1),  # constant-cofactor greedy
            ("0010000101100011", 2),  # mux-cost greedy
            ("0111100101011011", 3),  # reversed identity
        ],
    )
    def test_the_shortest_candidate_order_ships(self, table: str, winner: int) -> None:
        """Each named order wins somewhere, and the winner still computes."""
        from esolangs.tools.circuit_diagram import (
            _circuit_diagram_at,
            _selector_orders,
            circuit_diagram,
        )

        orders = _selector_orders(table)
        assert len(orders) == 4
        sizes = [len(_circuit_diagram_at(table, None, order)) for order in orders]
        assert sizes.index(min(sizes)) == winner
        assert sizes.count(min(sizes)) == 1
        compact = _selector_orders(table, compact=True)
        assert len(circuit_diagram(table)) == min(
            len(_circuit_diagram_at(table, None, order)) for order in compact
        )
        assert self.run_table(table) == table

    def test_each_run_prints_exactly_one_bit(self) -> None:
        """The output wire is live for exactly one generation."""
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

    def test_a_route_may_cross_a_hold_but_not_corner_beside_it(self) -> None:
        """A held cell keeps corners out of its neighbourhood, not wires."""
        from esolangs.tools.circuit_diagram import _HOLD, _RoutingLayout

        layout = _RoutingLayout()
        layout.reserve((1, 10), _HOLD)  # beside the ``down`` corner
        with pytest.raises(AssertionError, match=r"down route .* collides"):
            layout.route((0, 0), (20, 10), 5, "down")
        layout.route((0, 0), (20, 10), 5, "across")  # crosses column 1
        assert (20, 0) in layout.junctions
        layout.route((0, 12), (20, 22), 6, "under")
        assert (0, 24) in layout.junctions
        assert (20, 24) in layout.junctions
        layout.release(_HOLD)
        assert not layout._reserved  # noqa: SLF001

    @pytest.mark.parametrize("collision", ["endpoint", "neighbour", "interior"])
    def test_a_route_refuses_each_kind_of_claimed_cell(self, collision: str) -> None:
        """Endpoints, their neighbours and run interiors are all guarded."""
        from esolangs.tools.circuit_diagram import _RoutingLayout

        layout = _RoutingLayout()
        if collision == "endpoint":
            layout.glyphs[(0, 0)] = "x"
        elif collision == "neighbour":
            layout.junctions[(1, 1)] = 2
        else:
            layout.run_horizontal(0, 2, 0, 2)  # another signal covers (1, 0)
        assert not layout._route_is_free([(0, 0), (2, 0)], 1)  # noqa: SLF001

    @pytest.mark.slow  # ~6s: three n=4 builds, sixteen interpreted rows each
    def test_h_layout_lanes_execute_at_four_inputs(self) -> None:
        """Fixed lanes lay a correct circuit where every wire class meets."""
        import random

        from esolangs.interpreters.grid_based.circuit_diagram import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.circuit_diagram.hlayout import _h_term_layout

        rng = random.Random(4)
        for _ in range(3):
            table = "".join(rng.choice("01") for _ in range(16))
            if "1" not in table:
                continue
            program = _h_term_layout(table).render().splitlines()
            for index in range(16):
                io = ScriptedIO("".join(f"{bit}" for bit in format(index, "04b")))
                run(program, io)
                assert io.getvalue() == table[index], (table, index)


class TestCircuitDiagramSelectorOrder:
    """Which rail each Shannon level selects, chosen among four named orders."""

    def test_the_mux_cost_order_keeps_the_identity_on_a_tie(self) -> None:
        """Parity costs every level the same, whichever rail it selects."""
        from esolangs.tools.circuit_diagram import _cheapest_selector_order

        assert _cheapest_selector_order("01101001", 3) == (0, 1, 2)
        assert _cheapest_selector_order("0110", 2) == (0, 1)
        assert _cheapest_selector_order("01", 1) == (0,)

    def test_orders_stop_at_the_flat_routes_last_arity(self) -> None:
        """From eight inputs only the identity is built: bounded scoring."""
        from esolangs.tools.circuit_diagram import _selector_orders

        seven = "0001" * 32
        assert len(_selector_orders(seven)) > 1
        assert _selector_orders("0001" * 64) == [None]
