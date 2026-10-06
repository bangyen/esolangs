"""The grid generators whose tests are short: Super SNUSP and Alight."""

import pytest

from esolangs import tools as boolean


class TestSuperSNUSP:
    """The Super SNUSP generator (bounded ANF or a packed lookup)."""

    def test_cost_model_selects_the_smallest_form(self) -> None:
        """The selector prices both ANF layouts and the lookup exactly."""
        from esolangs.tools.helpers import essential_inputs, read_at
        from esolangs.tools.super_snusp import (
            _TWO_INPUT_SHORT,
            _anf_cost,
            _emit_anf,
            _emit_lookup,
            _polarity,
            super_snusp,
        )

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                used = essential_inputs(table, n)
                reduced = read_at(table, used, n)
                full = list(range(n))
                for shape, retained in ((table, full), (reduced, used)):
                    for negated in range(1 << len(retained)):
                        assert _anf_cost(n, shape, retained, negated=negated) == len(
                            _emit_anf(n, shape, retained, negated=negated)
                        )
                full_cost = _polarity(n, table, full)[1]
                reduced_cost = _polarity(n, reduced, used)[1]
                if table not in _TWO_INPUT_SHORT:
                    assert len(super_snusp(table)) == min(
                        full_cost, reduced_cost, len(_emit_lookup(table))
                    )

    def test_choosing_polarity_never_grows_a_program(self) -> None:
        """Every table to three inputs is no longer than its all-positive build."""
        from esolangs.tools.helpers import essential_inputs, read_at
        from esolangs.tools.super_snusp import (
            _TWO_INPUT_SHORT,
            _anf_cost,
            _emit_lookup,
            super_snusp,
        )

        before = after = 0
        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                built = len(super_snusp(table))
                if table in _TWO_INPUT_SHORT and n == 2:
                    old = built
                else:
                    used = essential_inputs(table, n)
                    old = min(
                        len(_emit_lookup(table)),
                        _anf_cost(n, table, list(range(n))),
                        _anf_cost(n, read_at(table, used, n), used),
                    )
                assert built <= old, table
                if n == 3:
                    before += old
                    after += built
        assert (before, after) == (19786, 16567)

    @pytest.mark.parametrize(
        ("table", "program"),
        [
            # NOR3: every product of the positive literals, one of the negated.
            ("10000000", '"49{,->,->,->>1<<<<{>>>>&<<<{>>>&<<{>>&{<^>48{<+.'),
            # x0 and not x1: the minority input pays one ``(``.
            ("00001100", '"48{,->,-(>,-0>1<<<{>>>&<<{>>&{<^>48{<+.'),
        ],
    )
    def test_a_negated_input_is_read_against_49(self, table: str, program: str) -> None:
        """A cell read against 49 holds -1 or 0, the complement for ``&``."""
        from esolangs.tools.super_snusp import super_snusp

        assert super_snusp(table) == program
        assert self.run_table(table) == table

    @staticmethod
    def run_table(table: str) -> str:
        """Return the generated program's output for every input, in order."""
        from esolangs.interpreters.grid_based.super_snusp import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.super_snusp import super_snusp

        n = len(table).bit_length() - 1
        program = super_snusp(table).splitlines()
        results = []
        for index in range(len(table)):
            bits = format(index, f"0{n}b")
            stdin = "".join(f"{bit}" for bit in bits)
            scripted = ScriptedIO(stdin)
            run(program, scripted)
            results.append(scripted.getvalue().strip())
        return "".join(results)

    @pytest.mark.parametrize(
        "table",
        ["11110000", "00001111", "11001100", "00110011", "10101010", "01010101"],
    )
    def test_a_table_ignoring_inputs_still_computes_it(self, table: str) -> None:
        """Dependency reduction keeps the answer over the full input space."""
        assert self.run_table(table) == table

    def test_a_four_input_table_builds_and_runs(self) -> None:
        """The construction is not two- and three-input special cases."""
        assert self.run_table("0110100110010110") == "0110100110010110"

    def test_the_lookup_scales_linearly_and_runs(self) -> None:
        """The unbounded path approaches its one-or-two commands per row."""
        from esolangs.tools.super_snusp import super_snusp

        ratios = []
        for n in range(5, 13):
            table = "".join(str(i.bit_count() & 1) for i in range(2**n))
            ratios.append(len(super_snusp(table)) / len(table))
        assert ratios == sorted(ratios, reverse=True)
        assert ratios[-1] < 1.6

        n = 6
        table = "".join(str(i.bit_count() & 1) for i in range(2**n))
        assert self.run_table(table) == table

    @pytest.mark.parametrize(
        "table", ["01", "0110", "0001", "01101001", "11110000", "00010111"]
    )
    def test_every_input_is_consumed(self, table: str) -> None:
        """One ``,`` per input, including inputs the answer ignores."""
        from esolangs.tools.super_snusp import super_snusp

        n = len(table).bit_length() - 1
        assert super_snusp(table).count(",") == n

    @pytest.mark.parametrize("table", ["01", "0000", "0110", "01101001", "11110000"])
    def test_every_program_starts_with_the_marker(self, table: str) -> None:
        """``"`` pins the entry point rather than inheriting the default."""
        from esolangs.tools.super_snusp import super_snusp

        assert super_snusp(table).startswith('"')

    def test_the_short_forms_are_what_the_generator_emits(self) -> None:
        """The five hand-written two-input forms are used verbatim."""
        from esolangs.tools.super_snusp import _TWO_INPUT_SHORT, super_snusp

        for table, form in _TWO_INPUT_SHORT.items():
            assert super_snusp(table) == '"' + form

    def test_the_general_build_is_used_off_the_short_table(self) -> None:
        """A two-input table with no short form is built by the evaluator."""
        from esolangs.tools.super_snusp import _TWO_INPUT_SHORT, super_snusp

        assert "0001" not in _TWO_INPUT_SHORT
        assert super_snusp("0001") == '"48{,->,->>1<<<{>>>&<<{>>&{<^>48{<+.'

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("1010", 27),  # one dependency at two inputs, read negated
            ("1111", 17),  # constant: the reduction drops both inputs
            ("00000000", 18),  # constant at three
            ("00000011", 39),  # depends on the last two of three
        ],
    )
    def test_the_reduced_build_is_the_one_emitted(
        self, table: str, length: int
    ) -> None:
        """A table that ignores an input is emitted over its essential ones."""
        from esolangs.tools.super_snusp import super_snusp

        assert len(super_snusp(table)) == length

    def test_a_malformed_table_is_rejected(self) -> None:
        from esolangs.tools.super_snusp import super_snusp

        with pytest.raises(ValueError, match="power-of-two"):
            super_snusp("010")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            super_snusp("012x")


class TestSuperSNUSPWidth:
    """SNUSP's mirrors, which make this the cheapest fold of any generator here."""

    @staticmethod
    def _run(program: str, bits: list[str]) -> str:
        import esolangs

        stdin = "".join(f"{bit}" for bit in bits)
        return esolangs.run("Super SNUSP", program, stdin=stdin, timeout=5.0).strip()

    def test_a_width_folds_the_line_and_it_still_computes(self) -> None:
        """The folded pointer computes what the straight one did."""
        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            flat = boolean.super_snusp(table)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.super_snusp(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 6, 12, 20, wide):
                narrow = boolean.super_snusp(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    assert self._run(narrow, bits) == table[combo], (table, width)

    def test_both_mirrors_are_used(self) -> None:
        """A program long enough to fold twice turns round and back again."""
        table = "".join(str(bin(i).count("1") % 2) for i in range(32))
        narrow = boolean.super_snusp(table, 12)
        assert "\\" in narrow, narrow
        assert "/" in narrow, narrow
        assert narrow.count("\\") >= 2, "an east-to-west turn is two mirrors"
        assert narrow.count("/") >= 2, "so is a west-to-east one"

    def test_a_digit_run_is_never_split_by_a_fold(self) -> None:
        """``48`` has to stay on one row: a mirror in between would make it 4, 8."""
        for width in range(4, 20):
            narrow = boolean.super_snusp("0110100110010110", width)
            assert "48" in narrow, (width, narrow)


class TestAlightWidth:
    """Alight minimizes its longer dimension under the width bound."""

    @staticmethod
    def _run(program: str, bits: list[str]) -> str:
        import esolangs

        stdin = "".join(f"{bit}" for bit in bits)
        return esolangs.run("Alight", program, stdin=stdin, timeout=5.0).strip()

    def test_a_width_turns_the_straight_walk_vertical(self) -> None:
        """A narrow program is one column and has no padding."""
        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            flat = boolean.alight(table)
            wide = max(len(row) for row in flat.splitlines())
            assert max(len(row) for row in boolean.alight(table, 1).splitlines()) == 1
            for width in (1, 40, 60, wide):
                narrow = boolean.alight(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= width, (table, width, columns)
                for combo in range(2**n):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    assert self._run(narrow, bits) == table[combo], (table, width)

    @pytest.mark.slow
    def test_a_width_is_met_at_every_arity(self) -> None:
        """Every requested width holds at every practical arity."""
        for n in (4, 5, 6, 7):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            for width in (60, 80):
                narrow = boolean.alight(table, width)
                assert max(len(row) for row in narrow.splitlines()) <= width, (n, width)

    @pytest.mark.parametrize(
        ("table", "width", "dimensions"),
        [
            ("0001", 30, (1, 75)),
            ("0001", 40, (36, 43)),
            ("0001", 80, (43, 33)),
            ("01101001", 80, (43, 43)),
            ("0110100110010110", 80, (49, 43)),
        ],
    )
    def test_the_longer_dimension_is_minimal(
        self, table: str, width: int, dimensions: tuple[int, int]
    ) -> None:
        """Pin each transition between the vertical and folded optima."""
        rows = boolean.alight(table, width).splitlines()
        assert (max(map(len, rows)), len(rows)) == dimensions

    def test_width_must_have_one_column(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            boolean.alight("0001", 0)


@pytest.mark.parametrize("inputs", [1, 3, 5, 8])
@pytest.mark.parametrize("width", [1, 3, 4])
def test_super_snusp_arithmetic_literals_preserve_stack_and_floor(
    inputs: int, width: int
) -> None:
    import esolangs

    table = "".join(str(row.bit_count() % 2) for row in range(1 << inputs))
    program = esolangs.generate("Super SNUSP", table, width)
    assert max(map(len, program.splitlines())) <= max(3, width)
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        stdin = esolangs.encode_inputs("Super SNUSP", bits)
        assert esolangs.run("Super SNUSP", program, stdin) == table[row]
