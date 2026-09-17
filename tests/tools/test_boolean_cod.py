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
        from esolangs.tools.cod import cod_setters

        # each input's one-cell run sets the cod's value to the bit: ')'
        # for one, '_' (a no-op crossed sideways) for zero, read at the
        # start of its '+' fork
        return fill_runs(tpl, TEMPLATE_CHAR, cod_setters(tpl, len(bits)), bits)

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
        from esolangs.tools.cod import cod_setters

        template = parameterized.cod("0110")
        assert "{X" not in template
        assert template.count(TEMPLATE_CHAR) == 2
        assert len(runs(template, TEMPLATE_CHAR, cod_setters(template, 2))) == 2

    def test_each_input_is_embedded_once(self) -> None:
        """The routing embeds each input exactly once, not per leaf."""
        from esolangs.tools import parameterized
        from esolangs.tools.cod import cod_setters

        template = parameterized.cod("0110")
        setters = cod_setters(template, 2)
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

        one = _cod_dead_box(3, [0]).split("\n")
        assert one == ["~~~", "~$~", "~~~"]

        two = _cod_dead_box(3, [0, 1]).split("\n")
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
