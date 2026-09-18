"""Covers :mod:`esolangs.tools.cod`."""

import pytest

from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs, runs


class TestParameterizedCOD:
    """Input-by-substitution boolean generator for the no-input language COD."""

    def run_cod(self, prog: str) -> str:
        from esolangs.interpreters.grid_based.cod import run
        from esolangs.interpreters.io import ScriptedIO

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.cod import PAIR

        # each input's one-cell run sets the cod's value to the bit: ')'
        # for one, '_' (a no-op crossed sideways) for zero, read at the
        # start of its '+' fork
        return fill_runs(tpl, TEMPLATE_CHAR, (PAIR,) * len(bits), bits)

    @pytest.mark.parametrize(
        "table",
        [
            "0000",  # constant zero
            "1111",  # constant one
            "0001",  # AND
            "0111",  # OR
            "0110",  # XOR
            "1001",  # XNOR
            "1110",  # NAND
            "1000",  # NOR
            "0100",  # A and not B
            "1101",  # A or not B
        ],
    )
    def test_truth_table(self, table: str) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools import parameterized

        template = parameterized.cod(table)
        for combo in range(4):
            bits = [(combo >> (2 - 1 - i)) & 1 for i in range(2)]
            got = self.run_cod(self.instantiate(template, bits))
            assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        """Every one of the sixteen two-input tables produces the right result."""
        from esolangs.tools import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.cod(table)
            for combo in range(4):
                bits = [(combo >> (2 - 1 - i)) & 1 for i in range(2)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    @pytest.mark.slow  # 1.1s: all 256 three-input tables through COD
    def test_all_three_input_tables(self) -> None:
        """Every one of the 256 three-input tables produces the right result.

        Unlike the two-input template, whose forks always split directly
        into leaves, the three-input template has forks whose zero-branch
        is itself an internal node -- so a cod can rejoin an earlier
        junction's row after a deeper fork, and that junction's own reset
        gauntlet is what stops it from circulating forever instead of
        halting.  This test is the only thing that would have caught that
        class of bug (a "backflow" cod wandering junctions indefinitely),
        since it is invisible from reading the grid.
        """
        from esolangs.tools import parameterized

        for table_int in range(256):
            table = format(table_int, "08b")
            template = parameterized.cod(table)
            for combo in range(8):
                bits = [(combo >> (3 - 1 - i)) & 1 for i in range(3)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    def test_program_always_terminates_with_one_value(self) -> None:
        """Every run prints exactly one value and leaves no cod alive."""
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools import parameterized

        template = parameterized.cod("0110")
        for combo in range(4):
            bits = [(combo >> (2 - 1 - i)) & 1 for i in range(2)]
            code = self.instantiate(template, bits)
            io_ = ScriptedIO("")
            machine = _Machine(code, io_)
            for _ in range(500):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            # one print, so one character: the answer, no separator
            assert len(io_.getvalue()) == 1

    def test_three_input_program_always_terminates_with_one_value(self) -> None:
        """Every three-input run prints exactly one value and halts."""
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools import parameterized

        template = parameterized.cod("01101001")
        for combo in range(8):
            bits = [(combo >> (3 - 1 - i)) & 1 for i in range(3)]
            code = self.instantiate(template, bits)
            io_ = ScriptedIO("")
            machine = _Machine(code, io_)
            for _ in range(500):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            # one print, so one character: the answer, no separator
            assert len(io_.getvalue()) == 1

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs.tools import parameterized
        from esolangs.tools.cod import PAIR

        template = parameterized.cod("0110")
        assert "{X" not in template
        assert template.count(TEMPLATE_CHAR) == 2
        assert len(runs(template, TEMPLATE_CHAR, (PAIR,) * 2)) == 2

    def test_each_input_is_embedded_once(self) -> None:
        """The routing embeds each input exactly once, not per leaf."""
        from esolangs.tools import parameterized
        from esolangs.tools.cod import PAIR

        template = parameterized.cod("0110")
        setters = (PAIR,) * 2
        assert template.count(TEMPLATE_CHAR) == sum(len(zero) for zero, _ in setters)
        spans = runs(template, TEMPLATE_CHAR, setters)
        assert [end - start for start, end in spans] == [1, 1]

    @pytest.mark.parametrize(
        ("table", "rows", "columns"),
        [
            ("01", 5, 17),
            ("0110", 9, 38),
            ("0001", 9, 38),
            ("11110000", 8, 17),
            ("01101001", 17, 87),
        ],
    )
    def test_the_template_has_exact_dimensions(
        self, table: str, rows: int, columns: int
    ) -> None:
        """The drawing's extents, per table.

        COD's template is a grid of boxes: walls sized from their contents,
        rows padded to a common width, blocks stacked and joined.  Every
        one of those is arithmetic on a length, and getting one wrong
        leaves a *working* program -- the cod still routes to the same
        leaf, the box is just a character wider or the padding lands on
        the other side.  The truth-table sweeps in this class read the
        printed bit and see none of it.

        ``11110000`` is the reduction case: it depends on one of its three
        inputs and draws at 8 by 17 where a real three-input table needs
        17 by 87.  A run is one cell, so these are the filled program's
        extents too.
        """
        from esolangs.tools import parameterized

        grid = parameterized.cod(table).split("\n")
        assert len(grid) == rows
        assert max(len(row) for row in grid) == columns

    def test_a_dead_box_wall_frames_its_contents(self) -> None:
        """The wall is two wider than the names it encloses.

        One name gives ``~~~`` and two give ``~~~~``: a wall that grew or
        shrank by one would still draw a box, and the cod would still be
        trapped in it, since what stops the cod is meeting a wall at all
        rather than the wall's length.  Each name is its one-cell run.
        """
        from esolangs.tools.cod import _cod_dead_box

        one = _cod_dead_box([0]).split("\n")
        assert one == ["~~~", "~$~", "~~~"]

        two = _cod_dead_box([0, 1]).split("\n")
        assert two == ["~~~~", "~$$~", "~~~~"]

    def test_the_grid_uses_only_cod_characters(self) -> None:
        """Nothing but the language's glyphs, the runs, and layout space."""
        from esolangs.tools import parameterized

        allowed = set(" ()+-<>~\n" + TEMPLATE_CHAR)
        for table in ("01", "0110", "01101001", "11110000"):
            assert set(parameterized.cod(table)) <= allowed, table

    def test_no_row_carries_trailing_space(self) -> None:
        """Rows are trimmed, so a row's length is its content's length."""
        from esolangs.tools import parameterized

        for table in ("01", "0110", "01101001"):
            for row in parameterized.cod(table).split("\n"):
                assert row == row.rstrip(), (table, repr(row))

    def test_a_table_ignoring_inputs_takes_the_reduced_build(self) -> None:
        """The reduction is kept only when it is strictly shorter.

        Both builds compute the table, so no truth-table assertion can see
        which was taken; the choice is a single length comparison.  Of the
        276 tables through three inputs, 46 have a reduction available at
        all.  The lengths are exact rather than bounded: a bound catches an
        inflating mutant only when the inflation happens to cross it, and
        says nothing about one that changes the drawing without growing it.
        """
        from esolangs.tools import parameterized

        for table in ("11110000", "00001111", "10101010"):
            assert len(parameterized.cod(table)) == 104, table
        assert len(parameterized.cod("01101001")) == 1495

    def test_constant_table_rejected(self) -> None:
        """n == 0 (a single-entry table, no inputs) is not supported."""
        from esolangs.tools import parameterized

        with pytest.raises(ValueError, match="n >= 1"):
            parameterized.cod("0")

    def test_four_input_tables(self) -> None:
        """n == 4 (beyond the old n <= 3 cap) produces the right result."""
        from esolangs.tools import parameterized

        for table in ("1111111011111110", "0110100110010110", "1000000000000000"):
            template = parameterized.cod(table)
            for combo in range(16):
                bits = [(combo >> (4 - 1 - i)) & 1 for i in range(4)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    @pytest.mark.parametrize("table", ["10", "01", "00", "11"])
    def test_one_input_truth_table(self, table: str) -> None:
        """n == 1 has no fork of its own: a bare entry into the leaf cascade."""
        from esolangs.tools import parameterized

        template = parameterized.cod(table)
        assert template.count(TEMPLATE_CHAR) == 1
        for x0 in range(2):
            got = self.run_cod(self.instantiate(template, [x0]))
            assert got == f"{table[x0]}", f"table {table} input {x0}"

    def test_a_width_turns_the_drawing_a_quarter_turn(self) -> None:
        """Turning beats banding, because the blocks are joined left to right.

        Banding trades width for height one block at a time; turning trades
        the whole drawing's width for its height at once, and the width
        becomes the *tallest* block rather than the widest.  At five inputs
        that is 65 columns against banding's 148.
        """
        from esolangs.tools import cod as cod_module

        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            zeros = [0] * n
            flat = self.instantiate(cod_module(table), zeros)
            wide = max(len(row) for row in flat.splitlines())
            turned = self.instantiate(cod_module(table, 1), zeros)
            floor = max(len(row) for row in turned.splitlines())
            assert floor == 2 ** (n + 1) + 1, (table, floor)
            assert floor < wide, table
            for width in (1, 20, 40, 80, wide):
                template = cod_module(table, width)
                columns = max(
                    len(row) for row in self.instantiate(template, zeros).splitlines()
                )
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    got = self.run_cod(self.instantiate(template, bits))
                    assert got.strip() == table[combo], (table, width, bits)

    def test_the_turn_re_attaches_every_print(self) -> None:
        """``---`` prints only as a *horizontal* run touching an edge.

        Turned, each of the cascade's ``2 ** n`` prints would be three
        vertical dashes -- three ``-`` removals -- and the cod would die
        with nothing printed, which is the worst way for this to be wrong.
        So each gets a corridor to a ``---`` at the left edge, and there
        must still be one per table row.

        The run has to be *exactly* three: the interpreter only counts a
        run of three, so a fourth dash would turn a print into four
        removals.  (Those runs stack vertically down column 0, which is
        fine -- prints are found by scanning rows, and no cod ever swims
        down that column; each arrives heading west and prints at once.)
        """
        from esolangs.tools import cod as cod_module

        table = "01101001"
        turned = self.instantiate(cod_module(table, 1), [0, 0, 0])
        rows = turned.splitlines()
        prints = [row for row in rows if row.startswith("-")]
        assert len(prints) == len(table), (len(prints), len(table))
        for row in prints:
            assert row.startswith("---"), row
            assert not row.startswith("----"), row


def _grid(picture: str) -> str:
    """A COD grid drawn with ``.`` for water, so no editor strips it."""
    return picture.strip("\n").replace(".", " ")


def _run_counting(program: str, steps: int = 60) -> tuple[bool, str, int]:
    """Run ``program`` for at most ``steps`` ticks: halted, output, peak cods."""
    from esolangs.interpreters.grid_based.cod import _Machine
    from esolangs.interpreters.io import ScriptedIO

    machine = _Machine(program, ScriptedIO(""))
    peak = 0
    for _ in range(steps):
        if machine.halted:
            break
        machine.step()
        peak = max(peak, len(machine.cods))
    return machine.halted, machine.io.getvalue(), peak


class TestCODModelFacts:
    """The interpreter facts ``docs/limitations.md``'s COD paragraph rests on.

    Each pins one sentence: a four-way plain cell is a crossing, a join
    at ``+`` leaks a backward copy, a ``_`` reflection retraces, and the
    one-lane N-bound node halts and prints once on both bits.
    """

    def test_a_plain_four_way_cell_is_a_crossing(self) -> None:
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine(_grid("~~~.~~~\n>......\n~~~.~~~\n~~~.~~~"), ScriptedIO(""))
        for _ in range(4):
            machine.step()
        assert [(c.r, c.c, c.d) for c in machine.cods] == [(1, 4, "E")]

    def test_a_join_at_plus_copies_backward(self) -> None:
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine(_grid("~~~~~~~\n~..+..~\n~~~.~~~\n~~~>~~~"), ScriptedIO(""))
        machine.step()
        machine.step()
        assert sorted(c.d for c in machine.cods) == ["E", "W"]

    def test_a_reflection_retraces_the_arrival_path(self) -> None:
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine(_grid("~_~\n~.~\n~)~\n~.~\n~>~"), ScriptedIO(""))
        seen = []
        for _ in range(6):
            machine.step()
            seen.extend((c.r, c.d) for c in machine.cods)
        assert seen == [(3, "N"), (2, "N"), (1, "N"), (0, "S"), (1, "S"), (2, "S")]

    def test_the_start_cannot_be_a_deterministic_return_diode(self) -> None:
        """A second exit at ``>`` is also a second random launch heading.

        A tempting constant-size zero test sends a cod north into ``_``:
        zero reaches the top print and a nonzero cod reflects back to ``>``
        to take its north exit.  That exit must already be open at launch,
        though.  The two possible first draws therefore take different
        paths before the value test.  A reusable ingress needs an ordinary
        cell with the same issue, so ``>`` cannot supply the missing diode.
        """
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw

        diode = _grid("~~~---\n~~~)~~\n~~~_~~\n~~~.~~\n---.~~\n~~>.~~\n~~~~~~")
        outputs = []
        for first in (0, 1):
            io_ = ScriptedIO("")
            machine = _Machine(diode, io_, rng=FirstDraw(first))
            while not machine.halted:
                machine.step()
            outputs.append(io_.getvalue())
        assert outputs == ["0", "1"]

    @pytest.mark.parametrize("gate", ["<", "_"])
    def test_a_value_gate_is_open_when_the_start_chooses_a_heading(
        self, gate: str
    ) -> None:
        """``<`` and ``_`` act after launch, not while choosing its exit."""
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.randomness import FirstDraw

        grid = f"~{gate}~\n~> "
        headings = [
            _Machine(grid, ScriptedIO(""), rng=FirstDraw(first)).cods[0].d
            for first in (0, 1)
        ]
        assert headings == ["N", "E"]

    @pytest.mark.parametrize("fill", ["_", ")"])
    def test_the_one_lane_node_halts_and_prints_once(self, fill: str) -> None:
        """Eight commands: ``))<((`` valve, ``+``, ``<`` sibling, ``)`` trunk.

        The lane's value is known (0), so the valve kills the backward
        copy (value 2) and the sibling ``<`` the unconditional one (0);
        both bits leave exactly one cod, on different prints.
        """
        node = _grid(
            "~~~~~~~~~~~~~\n"
            "~~~~~~~~~.---\n"
            "~~~~~~~~~X~~~\n"
            "~~~~~~~~~)~~~\n"
            "~>))<((..+<.~\n"
            "~~~~~~~~~~~.~\n"
            "~~~~~~~~~~~.~\n"
            "~~~~~~~~~~~.~\n"
            "---.........."
        ).replace("X", fill)
        halted, output, peak = _run_counting(node)
        assert (halted, output, peak) == (True, "2", 2)

    @pytest.mark.parametrize("offset", [1, 2, 3, 5])
    def test_the_valve_only_works_on_a_compile_time_known_value(
        self, offset: int
    ) -> None:
        """The one-lane node's valve does not generalize to a runtime offset.

        The pinned node above relies on the lane's value being compile-time
        0 (the cod's very first read).  A shared corridor cannot offer that:
        station ``k``'s stray carries ``v - k``, known only at runtime.
        Feeding the identical valve/fork/sibling shape a compile-time
        *nonzero* value (``offset`` extra ``)`` cells before the valve, same
        eight commands after) breaks both halves at once -- the valve's
        ``<`` no longer discriminates (it only ever excludes ``-2``, never
        the actual value), so the north branch's ``_`` now reflects instead
        of passing through, re-entering the shared ``+`` and re-forking
        forever: still unhalted and printing 700+ characters after 3,000
        ticks, for every offset tried.  A per-station valve substitution
        (this round's idea (b)) needs the arriving value to be a compile-time
        constant at every station, which only station 0 ever has.
        """
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO

        main = ">" + ")" * offset + "))<((..+<."
        width = len(main) + 2
        fork_col = main.index("+") + 1
        trunk_dot_col = width - 2

        def wall() -> str:
            return "~" * width

        def with_char(col: str, ch: str) -> str:
            row = list(wall())
            row[col] = ch
            return "".join(row)

        row1 = list(wall())
        row1[fork_col : fork_col + 4] = list(".---")
        rows = [
            wall(),
            "".join(row1),
            with_char(fork_col, "_"),
            with_char(fork_col, ")"),
            "~" + main + "~",
            with_char(trunk_dot_col, "."),
            with_char(trunk_dot_col, "."),
            with_char(trunk_dot_col, "."),
            "-" * 3 + " " * (width - 3),
        ]
        node = "\n".join(rows)

        machine = _Machine(node, ScriptedIO(""))
        for _ in range(3000):
            machine.step()
        assert not machine.halted
        assert len(machine.io.getvalue()) > 100

    def test_the_shared_lane_zero_test_fails_on_every_nonzero_residual(self) -> None:
        """Lead 1: the 8-command node cannot serve an R=4 block on one lane.

        Valve ``))<((``, one ``+`` fork, one sibling ``<``, one trunk ``)``
        -- eight commands, both ``<`` kills single shared cells -- fed
        residuals 0..3 (``len`` 125 + 9 per setter).  Offset 0 halts with
        one print and peak 2; each nonzero offset re-enters the shared
        ``+`` from the opposite heading every cycle, printing a walking
        value per cycle (600+ chars at 3000 ticks, steady peak 3).
        """
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO

        for offset in range(4):
            main = ">" + ")" * offset + "))<((..+<."
            width = len(main) + 2
            fork_col = main.index("+") + 1
            trunk_dot_col = width - 2

            def wall(w: int = width) -> str:
                return "~" * w

            def with_char(col: int, ch: str) -> str:
                row = list(wall())
                row[col] = ch
                return "".join(row)

            row1 = list(wall())
            row1[fork_col : fork_col + 4] = list(".---")
            program = "\n".join(
                [
                    wall(),
                    "".join(row1),
                    with_char(fork_col, "_"),
                    with_char(fork_col, ")"),
                    "~" + main + "~",
                    with_char(trunk_dot_col, "."),
                    with_char(trunk_dot_col, "."),
                    with_char(trunk_dot_col, "."),
                    "-" * 3 + " " * (width - 3),
                ]
            )
            assert len(program) == 125 + 9 * offset
            assert program.count("+") == 1
            assert program.count("<") == 2

            machine = _Machine(program, ScriptedIO(""))
            peak = 0
            for _ in range(3000):
                if machine.halted:
                    break
                machine.step()
                peak = max(peak, len(machine.cods))
            if offset == 0:
                assert machine.halted
                assert machine.io.getvalue() == "2"
                assert peak == 2
            else:
                assert not machine.halted
                assert len(machine.io.getvalue()) >= 600
                assert peak == 3

    def test_a_shared_decrement_column_with_plain_fork_taps_explodes(self) -> None:
        """Round 3: a shared corridor with an ungated (no-valve) ``+`` tap.

        Each station is ``+`` (fork: north continues, west taps off), a
        west jog forced-turned north into ``_``, then a bit-adjust and a
        private dash reaching the left edge -- O(1) width per station, no
        gauntlet.  The idea (this round's (b)) was that strays are
        tolerable since only size, not execution, is the target.

        They are not tolerable: a copy ``_`` reflects (any station before
        the true index, value nonzero) re-enters the same ``+`` heading
        the *opposite* way it left, and ``+``'s entry exclusion only
        blocks the one direction it is *now* arriving from -- both the
        original entry and the original continue direction are open
        again, so it re-forks into both.  Every round trip through
        ``+``/jog/``_`` doubles the live population: 1, 2, 2, 2, 2, 2, 4,
        4, 4, 4, 8, ... (executed, n=2, the simplest case: value 0 at the
        very first station).  128 cods alive and unhalted at tick 26,
        nothing ever printed.  A plain ``+`` cannot host an ungated tap on
        a shared corridor at all -- the valve (round 2) or an O(distance)
        gauntlet (the shipped generator) are the only ways found to keep a
        stray from re-entering live.
        """
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO

        width = 8  # 0-2 dash zone, 3 lead-in, 4 wall, 5 tap column, 6 main

        def wall_row() -> list[str]:
            return list("~" * width)

        rows: list[list[str]] = []
        top = wall_row()
        top[5] = "."  # bit for the bare final leaf (unused by this probe)
        rows.append(top)
        turn = wall_row()
        turn[3] = turn[5] = "."
        rows.append(turn)
        rows.append(list("-" * 3 + "~" * (width - 3)))
        for _ in range(3):  # n=2: 3 gated stations plus the bare leaf above
            r0 = wall_row()
            r0[5] = "."
            rows.append(r0)
            turn0 = wall_row()
            turn0[3] = turn0[5] = "."
            rows.append(turn0)
            rows.append(list("-" * 3 + "~" * (width - 3)))
            r1 = wall_row()
            r1[5], r1[6] = "_", "<"
            rows.append(r1)
            r2 = wall_row()
            r2[5], r2[6] = ".", "+"
            rows.append(r2)
            r3 = wall_row()
            r3[6] = "("
            rows.append(r3)
        bottom = wall_row()
        bottom[6] = ">"
        rows.append(bottom)
        program = "\n".join("".join(r) for r in reversed(rows))

        machine = _Machine(program, ScriptedIO(""))
        for _ in range(26):
            machine.step()
        assert not machine.halted
        assert len(machine.cods) == 128
        assert machine.io.getvalue() == ""

    def test_the_t_squared_wall_is_concurrent_strays_not_walk_length(self) -> None:
        """The shipped cascade's cost is *width* (live strays), not *depth*.

        At n=7 (T=128) the single-one table's worst index drives peak live
        cods to T -- one stray per still-open row, all converging on the
        same tick since row ``j``'s stray needs exactly ``V - j`` steps to
        die and rows are peeled off one tick apart.  Tick count itself
        (7,713) stays far under ``T**2`` (16,384): the interpreter's cost is
        ``ticks * live-cod-count``, not ticks alone.  Index 0 never builds
        that population (every stray dies within a tick or two of birth).
        This is why idea (3) -- keep the ``T**2`` grid, shrink the live
        walk -- does not escape the row's open question: an O(1)-per-stray
        kill needs a zero test independent of ``|V - j|``, and COD's four
        value ops (``)`` ``(`` ``<`` ``_``) only test distance to zero by
        walking it.
        """
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools import parameterized
        from esolangs.tools.cod import PAIR
        from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs

        n = 7
        total = 2**n
        table = "0" * (total - 1) + "1"
        template = parameterized.cod(table)

        def run(bits: list[int]) -> tuple[int, bool, str, int]:
            code = fill_runs(template, TEMPLATE_CHAR, (PAIR,) * n, bits)
            machine = _Machine(code, ScriptedIO(""))
            steps = 0
            peak = 0
            while not machine.halted:
                machine.step()
                steps += 1
                peak = max(peak, len(machine.cods))
            return steps, machine.halted, machine.io.getvalue(), peak

        assert run([1] * n) == (7713, True, "1", total)
        assert run([0] * n) == (7820, True, "0", 2)

    @pytest.mark.parametrize("n", range(1, 9))
    def test_disjoint_unary_zero_tests_pay_the_residual_sum(self, n: int) -> None:
        """A scoped floor for the routed-cascade model, not a language bound.

        In an arm that owns its cells, ``<`` can kill a stray only at value
        zero.  With no value operation besides unit ``(``/``)``, a stray
        arriving at residual ``r`` therefore needs at least ``r`` net
        decrements before that kill.  A selected index ``T - 1`` leaves
        residuals ``T - 1, ..., 0`` in the independent arms, so their
        disjoint decrement cells total ``T * (T - 1) / 2``.  Shared lanes
        are outside this lemma; their failed re-entry construction is pinned
        by ``test_a_shared_decrement_column_with_plain_fork_taps_explodes``.
        """
        total = 2**n
        residuals = range(total - 1, -1, -1)
        assert sum(residuals) == total * (total - 1) // 2

        # A shorter unary descent leaves a nonzero residue, so ``<`` cannot
        # kill the stray.  Execute the witness rather than treating the
        # arithmetic as a source-size claim.
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO

        residual = total - 1
        descent = "(" * (residual - 1)
        row = ">" + ")" * residual + descent + "<"
        width = len(row)
        code = "~" * width + "\n" + row + "\n" + "~" * width
        machine = _Machine(code, ScriptedIO(""))
        for _ in range(2 * residual):
            machine.step()
        assert machine.cods[0].value == 1
        assert not machine.halted

    @pytest.mark.parametrize("bits", range(1, 9))
    def test_scalar_residues_have_no_packed_low_bit_probe(self, bits: int) -> None:
        """A scalar COD value needs unary work to expose a binary residue.

        Values ``2**bits`` and ``2**bits + 1`` have identical zero/nonzero
        control until the first has been decremented to zero.  A short probe
        therefore leaves both cods live, while the exact probe distinguishes
        them only after ``2**bits`` cells.  This rules out a packed residual
        gadget using the language's scalar value operations; it does not
        rule out sharing those unary cells between independent cods.
        """
        from dataclasses import replace

        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO

        magnitude = 2**bits

        def probe(length: int, value: int) -> tuple[bool, int | None]:
            row = ">" + "(" * length + "<~"
            width = len(row)
            code = "~" * width + "\n" + row + "\n" + "~" * width
            machine = _Machine(code, ScriptedIO(""))
            machine.cods = (replace(machine.cods[0], value=value),)
            for _ in range(length + 1):
                if machine.halted:
                    return True, None
                machine.step()
            return (machine.halted, None if machine.halted else machine.cods[0].value)

        assert probe(bits, magnitude) == (False, magnitude - bits)
        assert probe(bits, magnitude + 1) == (False, magnitude + 1 - bits)
        assert probe(magnitude, magnitude) == (True, None)
        assert probe(magnitude, magnitude + 1) == (False, 1)
