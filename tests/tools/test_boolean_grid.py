"""The Super SNUSP generator."""

import pytest


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
