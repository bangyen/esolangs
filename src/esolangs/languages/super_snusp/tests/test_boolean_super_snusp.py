"""Super SNUSP through the shared API, CLI and machinery."""

from unittest.mock import patch

import pytest

import esolangs
from esolangs import run as execute
from esolangs.languages.super_snusp import generator as boolean
from esolangs.languages.super_snusp.generator import balance_super_snusp, super_snusp
from esolangs.runtime.io import ScriptedIO
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_constant_roots,
    assert_saved_rows,
    measure_run,
    three_input_corpus_size,
)


class TestSuperSNUSPWidth:
    """SNUSP's mirrors, which make this the cheapest fold of any generator here."""

    @staticmethod
    def _run(program: str, bits: list[str]) -> str:

        stdin = "".join(f"{bit}" for bit in bits)
        return execute("Super SNUSP", program, stdin=stdin, timeout=5.0).output.strip()

    def test_a_width_folds_the_line_and_it_still_computes(self) -> None:
        """The folded pointer computes what the straight one did."""
        language = esolangs.Language("Super SNUSP")
        cases = construction_boundaries(language.name)
        for witness in cases["two_input_xor_short_form"]:
            table = witness.table()
            with patch.object(
                boolean, "_emit_lookup", wraps=boolean._emit_lookup
            ) as lookup:
                artifact = language.generate(table)
            assert lookup.call_count == int(witness.arity == 3)
            assert_saved_rows(language, artifact, table, range(len(table)))

        for witness in cases["vertical_to_fold_width_floor"]:
            table = witness.table()
            floor = boolean._fold_floor(boolean.super_snusp(table))
            for width in (floor - 1, floor):
                with patch.object(
                    boolean, "_super_snusp_folded", wraps=boolean._super_snusp_folded
                ) as fold:
                    artifact = language.generate(table, width=width)
                assert fold.call_count == int(width == floor)
                assert_saved_rows(language, artifact, table, range(len(table)))

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
        table = "".join(str((i).bit_count() % 2) for i in range(32))
        narrow = boolean.super_snusp(table, 12)
        assert "\\" in narrow, narrow
        assert "/" in narrow, narrow
        assert narrow.count("\\") >= 2, "an east-to-west turn is two mirrors"
        assert narrow.count("/") >= 2, "so is a west-to-east one"

    def test_a_digit_run_is_never_split_by_a_fold(self) -> None:
        """``48`` has to stay on one row: a mirror in between would make it 4, 8."""
        for width in range(4, 20):
            narrow = boolean.super_snusp("0110100110010110", width)
            # A westward row reads right to left on the page; a column of
            # one reads bottom to top.
            rows = narrow.split("\n")
            text = "".join(rows) if max(map(len, rows)) == 1 else narrow
            assert "48" in text or "84" in text, (width, narrow)


@pytest.mark.parametrize("inputs", [1, 3, 5, 8])
@pytest.mark.parametrize("width", [1, 3, 4])
def test_super_snusp_arithmetic_literals_preserve_stack_and_floor(
    inputs: int, width: int
) -> None:
    import esolangs

    table = "".join(str(row.bit_count() % 2) for row in range(1 << inputs))
    program = esolangs.generate("Super SNUSP", table, width=width).source
    assert max(map(len, program.splitlines())) <= max(3, width)
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        stdin = esolangs.encode_inputs("Super SNUSP", bits)
        assert execute("Super SNUSP", program, stdin=stdin).output == table[row]


class TestSuperSNUSP:
    """The Super SNUSP generator (a packed lookup)."""

    @staticmethod
    def run_table(table: str) -> str:
        """Return the generated program's output for every input, in order."""
        from esolangs.languages.super_snusp.interpreter import run

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
        n = len(table).bit_length() - 1
        assert super_snusp(table).count(",") == n

    @pytest.mark.parametrize("table", ["01", "0000", "0110", "01101001", "11110000"])
    def test_every_program_starts_with_the_marker(self, table: str) -> None:
        """``"`` pins the entry point rather than inheriting the default."""
        assert super_snusp(table).startswith('"')

    def test_the_short_forms_are_what_the_generator_emits(self) -> None:
        """The four intrinsic two-input forms retain their independent spellings."""
        from esolangs.languages.super_snusp.interpreter import run

        assert_analysis_complement("Super SNUSP", "input_weights", "00100010")
        assert_constant_roots("Super SNUSP", run, split=True)
        assert not hasattr(boolean, "_TWO_INPUT_SHORT")
        _check_stacked_operands()
        for table, form in {
            "0011": "48{,-> ,-<^.",
            "0101": "48{,-> ,-<>^.",
            "0110": "48{,-> ,-<^{>^.",
            "0111": "48{,-> ,-<^{>|.",
        }.items():
            assert super_snusp(table) == '"' + form

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("1010", 31),  # one dependency at two inputs
            ("1111", 6),  # constant at two
            ("00000000", 7),  # constant at three
            ("00000011", 39),  # depends on the last two of three
        ],
    )
    def test_the_lookup_length_is_pinned(self, table: str, length: int) -> None:
        """Ignored inputs are read but not dropped: the lookup is the whole table."""
        assert len(super_snusp(table)) == length


def test_super_snusp_balance_keeps_a_long_literal_whole() -> None:
    """A fold cannot split a digit run, so the balanced layout holds it on one line."""
    flat = '"' + "1234567890123456789" + "."
    rows = balance_super_snusp(flat).split("\n")
    assert any(
        "1234567890123456789" in row or "9876543210987654321" in row for row in rows
    )


def test_balanced_chunked_literal_computes_the_table() -> None:
    """The balance hook's Horner-chunked literal (a ``[`` shift) is the same table."""
    table = "".join(str((r * 2654435761 >> 7) & 1) for r in range(1 << 7))
    program = esolangs.generate("Super SNUSP", table, balance=True).source
    assert "[" in program
    for row in range(1 << 7):
        bits = [(row >> (6 - i)) & 1 for i in range(7)]
        stdin = esolangs.encode_inputs("Super SNUSP", bits, truth_table=table)
        assert (
            execute("Super SNUSP", program, stdin=stdin).output.strip()[-1]
            == table[row]
        )


def test_xor_has_one_column() -> None:
    xor = esolangs.generate("Super SNUSP", "0110", width=1).source
    assert max(map(len, xor.splitlines())) == 1


@pytest.mark.parametrize("token", ["1_0", "٣"])
def test_a_number_read_is_ascii_decimal(token: str) -> None:
    """``@`` took Python's int() spellings: "1_0" read 10, "٣" read 3."""
    with pytest.raises(esolangs.ArgumentError, match="must be an integer"):
        execute("Super SNUSP", '"@#', stdin=token)


class TestSuperSNUSPSweepPins:
    """Pins from the mutation sweep: the width-zero floor, the
    exact-fit shortcut and the balance candidate window."""

    def test_width_zero_returns_the_floor_fold_not_the_vertical(self) -> None:
        program = boolean.super_snusp("0110", width=0)
        assert program == ('"48\\\n/,{/\n\\->\\\n/, /\n\\-<\\\n/{^/\n\\>^\\\n  ./')

    def test_a_width_equal_to_the_flat_length_returns_the_flat_program(self) -> None:
        flat = boolean.super_snusp("0010")
        assert boolean.super_snusp("0010", width=len(flat)) == flat
        assert "\n" not in flat

    @pytest.mark.parametrize(
        ("table", "shape"),
        [("1100", (43, 5, 8)), ("1111", (11, 2, 5))],
    )
    def test_balanced_shapes_are_pinned(self, table: str, shape: tuple) -> None:
        program = str(esolangs.generate("Super SNUSP", table, balance=True).source)
        assert (
            len(program),
            program.count("\n") + 1,
            max(map(len, program.split("\n"))),
        ) == shape


def _check_stacked_operands() -> None:
    from esolangs.languages.super_snusp.interpreter import _Machine

    tables = ["00110110", "01111111", "00000011"]
    tables.extend(
        "".join(str(row.bit_count() % 2) for row in range(1 << n)) for n in (5, 6)
    )
    for table in tables:
        n = len(table).bit_length() - 1
        flat = str(esolangs.generate("Super SNUSP", table).source)
        encoding = 49 if flat.startswith('"49{') else 48
        for options in ({}, {"width": 1}, {"width": 17}, {"balance": True}):
            program = str(esolangs.generate("Super SNUSP", table, **options).source)
            for row in (0, (1 << n) // 3, (1 << n) - 1):
                io = ReadFirstIO(f"{row:0{n}b}" + "Q", expected=n)
                machine = _Machine(program.splitlines(), io)
                steps, written = measure_run(machine)
                assert io.getvalue() == table[row]
                assert io.past_end == 0
                assert io.input_char() == ord("Q")
                assert machine.stack == [encoding]
                if not options:
                    assert steps == len(flat)
                    if n >= 5:
                        bound = (
                            (1 << n)
                            + 2 * n
                            + 14
                            + len(flat).bit_length()
                            + n.bit_length()
                        )
                        assert written.bits <= bound
    assert three_input_corpus_size("Super SNUSP") == 11236
