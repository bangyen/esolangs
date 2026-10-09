"""Super SNUSP through the shared API, CLI and machinery."""

import pytest

from esolangs import tools as boolean


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
            # A westward row reads right to left on the page.
            assert "48" in narrow or "84" in narrow, (width, narrow)


@pytest.mark.parametrize("inputs", [1, 3, 5, 8])
@pytest.mark.parametrize("width", [1, 3, 4])
def test_super_snusp_arithmetic_literals_preserve_stack_and_floor(
    inputs: int, width: int
) -> None:
    import esolangs

    table = "".join(str(row.bit_count() % 2) for row in range(1 << inputs))
    program = esolangs.generate("Super SNUSP", table, width=width)
    assert max(map(len, program.splitlines())) <= max(3, width)
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        stdin = esolangs.encode_inputs("Super SNUSP", bits)
        assert esolangs.run("Super SNUSP", program, stdin=stdin) == table[row]


class TestSuperSNUSP:
    """The Super SNUSP generator (a packed lookup)."""

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

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("1010", 47),  # one dependency at two inputs
            ("1111", 30),  # constant at two
            ("00000000", 32),  # constant at three
            ("00000011", 68),  # depends on the last two of three
        ],
    )
    def test_the_lookup_length_is_pinned(self, table: str, length: int) -> None:
        """Ignored inputs are read but not dropped: the lookup is the whole table."""
        from esolangs.tools.super_snusp import super_snusp

        assert len(super_snusp(table)) == length
