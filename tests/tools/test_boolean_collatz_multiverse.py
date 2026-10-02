"""collatz_multiverse generator tests."""

import random

import pytest

import esolangs
from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_collatz_multiverse,
)


class TestCollatzMultiverse:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),  # top half
        ],
    )
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.collatz_multiverse(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_collatz_multiverse(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    # 256 tables at eight rows each, all of it in the interpreter.
    @pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.medium)])
    def test_every_small_table(self, n: int) -> None:
        """Execute every table and row through three inputs."""
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            program = boolean.collatz_multiverse(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert run_collatz_multiverse(program, bits) == table[combo]

    def test_reads_each_input_once_and_prints_once(self) -> None:
        """The program reads every input once and answers with one print."""
        program = boolean.collatz_multiverse("01101001")
        assert program.count("input") == 3
        assert program.count("DO PRINT.") == 1

    def test_cells_are_addressed_by_line_number(self) -> None:
        """The table sits in cells the writing line's own number addresses.

        What is pinned is that the rows are *placed and indexed* rather than
        walked: the fill block spends one line a cell and no line advancing a
        pointer, and the reader subscripts those arrays instead of branching.
        A quarter of the rows per cell is the construction's own choice and is
        not pinned here; one line per cell is what the size constant rides on.
        """
        table = "01101001" * 8
        program = boolean.collatz_multiverse(table)
        subscripted = [line for line in program.splitlines() if "[" in line]
        placed = [line for line in subscripted if "[lineNumber]=" in line]
        assert len(placed) <= len(table) // 2
        # What is left is the reader: one indexed read of each array, by a
        # register the inputs summed rather than by a walked pointer.
        assert len(subscripted) - len(placed) == 2

    def test_full_tree_growth_is_linear(self) -> None:
        """Parity folds nothing, but one line a cell keeps source linear."""
        sizes = []
        for n in (7, 8):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(boolean.collatz_multiverse(table)))
        assert sizes[1] < 2 * sizes[0] + 256

    def test_constant_tables_collapse_but_still_read(self) -> None:
        """A constant table collapses to one output but still reads its inputs.

        Collapsing the evaluation is the win; the reads are the language's
        interface and have to stay, or the caller's bits are left unread on the
        input stream for whatever runs next.
        """
        for table in ("0000", "1111"):
            program = boolean.collatz_multiverse(table)
            assert program.count("DO PRINT.") == 1
            assert program.count("input") == 2  # n == 2, read once each

    @pytest.mark.parametrize("n", [4, 5, 6])
    @pytest.mark.medium
    def test_sampled_wider_tables(self, n: int) -> None:
        """Every row of sampled tables, with ignored inputs among them."""
        rng = random.Random(n)
        for _ in range(4):
            table = "".join(rng.choice("01") for _ in range(2**n))
            # An ignored first input, so the essential projection is exercised.
            for shape in (table, table[: 2 ** (n - 1)] * 2):
                program = boolean.collatz_multiverse(shape)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    assert run_collatz_multiverse(program, bits) == shape[combo]

    def test_numbered_cells_halve_the_three_input_total(self) -> None:
        """The plain build against the shipped one over every varied table.

        The plain build stores each cell's value, so its decoder spans every
        value up to the largest; the generator before numbering totalled
        460296 over all 256 tables, the plain build now 450156 of the 254
        varied ones (one-letter aliases only where they pay).
        """
        from esolangs.tools.collatz_multiverse import _cm_build

        varied = [t for v in range(256) if len(set(t := format(v, "08b"))) > 1]
        plain = sum(len(_cm_build(t, 3, [0, 1, 2], zero_top=None)) for t in varied)
        built = sum(len(boolean.collatz_multiverse(t)) for t in varied)
        assert (plain, built) == (450156, 228694)

    def test_numbering_never_grows_a_program(self) -> None:
        """Numbered cells beat the retired value-as-code size oracle."""
        from esolangs.tools.collatz_multiverse import _cm_build

        rng = random.Random(0)
        tables = [format(v, "08b") for v in range(1, 255)]
        tables += ["".join(rng.choice("01") for _ in range(2**n)) for n in (4, 5, 6)]
        for table in tables:
            n = len(table).bit_length() - 1
            plain = _cm_build(table, n, list(range(n)), zero_top=None)
            assert plain is not None
            assert len(boolean.collatz_multiverse(table)) <= len(plain), table

    @pytest.mark.parametrize("width", [1, 27, 32, 40, 80])
    def test_narrow_statements_keep_array_addresses(self, width: int) -> None:
        """Alias prefixes preserve odd captures and read every input once."""

        for table in ("0000", "1111", "0110", "01101001", "10101010"):
            n = len(table).bit_length() - 1
            plain = boolean.collatz_multiverse(table)
            program = esolangs.generate("Collatz Multiverse", table, width)
            assert max(map(len, program.splitlines())) <= max(
                width, max(map(len, plain.splitlines()))
            )
            assert program.count("input") == n
            assert program.count("DO PRINT.") == 1
            for row in range(1 << n):
                assert (
                    run_collatz_multiverse(program, list(f"{row:0{n}b}")) == table[row]
                )

    @pytest.mark.parametrize("width", [1, 27, 29, 30, 40, 80])
    def test_narrow_renaming_preserves_every_small_table(self, width: int) -> None:
        for n in range(1, 4):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                program = boolean.collatz_multiverse(table, width)
                assert max(map(len, program.splitlines())) <= max(width, 29)
                assert program.count("input") == n
                for row in range(2**n):
                    bits = list(format(row, f"0{n}b"))
                    assert run_collatz_multiverse(program, bits) == table[row]

    @pytest.mark.parametrize("n", [5, 8, 10])
    def test_narrow_renaming_preserves_larger_decoders(self, n: int) -> None:
        rng = random.Random(20260930 + n)
        for table in (
            "".join(str(row.bit_count() & 1) for row in range(2**n)),
            "".join(rng.choice("01") for _ in range(2**n)),
        ):
            for width in (1, 29, 40, 80):
                program = boolean.collatz_multiverse(table, width)
                for row in rng.sample(range(2**n), 12):
                    bits = list(format(row, f"0{n}b"))
                    assert run_collatz_multiverse(program, bits) == table[row]

    def test_fitting_alias_layout_keeps_its_register_names(self) -> None:
        program = boolean.collatz_multiverse("00", 27)
        assert max(map(len, program.splitlines())) <= 27
        assert "k48" in program
        for bit in ("0", "1"):
            assert run_collatz_multiverse(program, [bit]) == "0"

    def test_narrow_xor_uses_the_complete_statement_floor(self) -> None:
        program = boolean.collatz_multiverse("0110", 1)
        assert max(map(len, program.splitlines())) == 26

    def test_numbered_constants_narrow_complete_statements(self) -> None:
        """The narrow candidate changes source and actually reduces columns."""
        plain = boolean.collatz_multiverse("01101001")
        narrow = boolean.collatz_multiverse("01101001", 1)
        assert "negativeOne" not in narrow
        assert narrow.splitlines()[0].endswith("=zx+lineNumber,NOT PRINT.")
        assert max(map(len, narrow.splitlines())) == 26
        assert max(map(len, narrow.splitlines())) < max(map(len, plain.splitlines()))

    def test_narrow_statement_floor_is_idempotent(self) -> None:
        """Another alias prefix cannot narrow or widen the existing floor."""
        from esolangs.tools.collatz_multiverse import _cm_layout

        table = "01101001"
        narrow = boolean.collatz_multiverse(table, 1)
        relaid = _cm_layout(narrow, 1)
        assert relaid == narrow
        for row, expected in enumerate(table):
            assert run_collatz_multiverse(relaid, list(f"{row:03b}")) == expected

    def test_narrow_cell_source_remains_linear(self) -> None:
        sizes = [
            len(boolean.collatz_multiverse("01101001" * (2 ** (n - 3)), 1))
            for n in (7, 8)
        ]
        assert sizes[1] < 2 * sizes[0] + 256
