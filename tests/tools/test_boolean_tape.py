"""Unit tests for the tape-based boolean generators.

Covers the generators in :mod:`esolangs.tools.boolean.tape` plus the
single-language modules that share its tape-machine shape: ``rotfuck``,
``six_five``, ``dimensional``, and ``streetcode``.
"""

import pytest

from esolangs.tools import boolean
from tests.tools.boolean_runners import (
    run_bf,
    run_bit_tilde,
    run_brainif,
    run_circlefuck,
    run_dimensional,
    run_factor,
    run_jaune,
    run_painfuck,
    run_rotfuck,
    run_sbleq,
    run_six_five,
    run_streetcode,
    run_suffolk,
    run_three_d_brainfuck,
)


def _columns(program: str) -> int:
    """The widest row of a grid program, which is what a width bounds."""
    return max(len(line) for line in program.split("\n"))


class TestSixFive:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.six_five(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_branch_structure(self) -> None:
        """Each level reads a bit and branches to a 4 marker."""
        program = boolean.six_five("0110")
        assert program.startswith("B" + "2" * 8)
        assert "78" in program
        assert program.endswith("A0")

    def test_arithmetic_fallback_path(self) -> None:
        """n > 5 falls back to the arithmetic kernel instead of the tree."""
        program = boolean.six_five("1" + "0" * 63)  # f(x) = (x == 0): T == 1
        assert "8" in program  # loops use 8n jumps
        assert "70" in program  # loop conditionals
        assert program.count("4") <= 35  # within the label budget

    @pytest.mark.slow
    @pytest.mark.parametrize("n", [6, 7, 8])
    @pytest.mark.parametrize("table", ["10", "1100"])
    def test_arithmetic_fallback_table(self, n: int, table: str) -> None:
        """The fallback computes every combination for small-T tables."""
        table = table + "0" * (2**n - len(table))  # ones only at low indices
        program = boolean.six_five(table)
        assert len(program) < 2000  # the small-T setup stays short
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_arithmetic_fallback_constant_markers(self) -> None:
        """A loop-based x build keeps the marker count constant in n."""
        markers = {
            n: boolean.six_five("1" + "0" * (2**n - 1)).count("4")
            for n in (6, 9, 12, 16)
        }
        assert markers == {6: markers[6], 9: markers[6], 12: markers[6], 16: markers[6]}
        assert markers[6] <= 35  # well within the label budget

    def test_arithmetic_fallback_refuses_large_t(self) -> None:
        """AND-n is the worst case: T == 2**(2**n - 1) blows up the setup."""
        with pytest.raises(ValueError, match="~2 MB setup"):
            boolean.six_five("0" * 63 + "1")  # AND6: T == 2**63

    @pytest.mark.slow
    @pytest.mark.parametrize("n", [6, 8])
    def test_arithmetic_fallback_complement(self, n: int) -> None:
        """Tables whose complement is cheap use it instead of a huge T."""
        table = "00" + "1" * (2**n - 2)  # zeros only at indices 0,1: T' == 3
        program = boolean.six_five(table)
        assert len(program) < 2000
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_arithmetic_fallback_compact_setup(self) -> None:
        """+6 runs make the setup ~T/6, far below the naive 2T pairs."""
        program = boolean.six_five("1" * 20 + "0" * 44)  # T == 2**20 - 1
        assert len(program) < 500_000  # ~T/6, not ~2T
        assert program[:32].count("6") > program[:32].count("62")  # uses +6 runs

    def test_arithmetic_fallback_complement_marker_budget(self) -> None:
        """The complement output branch stays inside the label budget."""
        program = boolean.six_five("00" + "1" * 62)
        assert program.count("4") <= 35


class TestStreetcode:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.streetcode(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_streetcode(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_width_is_a_shape_choice(self) -> None:
        """A width picks a narrower shape, and that shape still computes.

        The shapes differ in aspect -- the ring is the shortest program but
        the widest -- so a width the default overruns is met by a shape that
        was built anyway, at the cost of rows.  A Streetcode program cannot
        be reflowed after the fact, so this is the only way a width is met.
        """
        table = "10"
        default = boolean.streetcode(table)
        narrow = boolean.streetcode(table, 25)
        assert _columns(narrow) <= 25 < _columns(default)
        assert narrow.count("\n") > default.count("\n")
        for bit in ("0", "1"):
            assert run_streetcode(narrow, [bit]) == table[int(bit)]

    def test_width_takes_the_narrowest_when_none_fits(self) -> None:
        """Below every shape's width the narrowest one is returned.

        The generator has no shape narrower than its own decision tree, so
        an impossible width is a preference it cannot honour rather than an
        error; returning the best available beats returning nothing.
        """
        table = "10"
        program = boolean.streetcode(table, 1)
        assert _columns(program) == min(
            _columns(boolean.streetcode(table, w)) for w in (1, 25, 100)
        )
        for bit in ("0", "1"):
            assert run_streetcode(program, [bit]) == table[int(bit)]

    def test_width_none_is_unchanged(self) -> None:
        """Passing no width builds exactly what the generator always built."""
        for table in ("10", "0110", "11111110"):
            assert boolean.streetcode(table, None) == boolean.streetcode(table)


class TestDimensional:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.dimensional(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dimensional(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_moves_are_pinned_to_dimension_zero(self) -> None:
        """A bare >/< would take its dimension from the cell's value."""
        program = boolean.dimensional("0110")
        rest = program.replace(">0", "").replace("<0", "")
        assert ">" not in rest
        assert "<" not in rest

    def test_scales_beyond_the_old_reference_cap(self) -> None:
        """The v3.0 interpreter's unbounded cells lift the old n <= 12 cap."""
        program = boolean.dimensional("0" * 4095 + "1")
        got = run_dimensional(program, ["1"] * 12)
        assert got == "1"

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.dimensional("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.dimensional("02")


class TestDimensionalTree:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111100000000", 4),
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.dimensional_tree(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dimensional(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_small_on_dense_tables(self) -> None:
        """The tree shares bit tests, so dense tables stay small."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.dimensional_tree(xor6)) < 10_000  # vs ~34K survivor

    def test_dimensional_dispatches(self) -> None:
        """dimensional picks the survivor for sparse and the tree for dense."""
        sparse = boolean.dimensional("0" * 15 + "1")  # AND4
        assert len(sparse) < len(boolean.dimensional_tree("0" * 15 + "1"))
        xor = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        assert boolean.dimensional(xor) == boolean.dimensional_tree(xor)


class TestCirclefuck:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.circlefuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize(
        ("values", "n"),
        [
            ([0, 255], 1),
            ([48, 49, 50, 51], 2),
        ],
    )
    def test_byte_values(self, values: list[int], n: int) -> None:
        """circlefuck_byte outputs the given byte per input combination."""
        program = boolean.circlefuck_byte(values)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == chr(values[combo]), f"inputs {bits}"

    def test_byte_values_require_a_power_of_two_table(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.circlefuck_byte([1, 2, 3])


class TestBf:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.brainfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_bf_sparse_uses_the_minterm(self) -> None:
        """bf picks the minterm for sparse tables (shorter than the tree)."""
        program = boolean.brainfuck("0" * 15 + "1")  # AND4: one one-row
        assert len(program) < len(boolean.bf_tree("0" * 15 + "1"))

    def test_bf_dense_uses_the_tree(self) -> None:
        """bf picks the decision tree for dense tables."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert boolean.brainfuck(xor6) == boolean.bf_tree(xor6)

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.brainfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.brainfuck("02")


class TestBfTree:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bf_tree(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_small_on_dense_tables(self) -> None:
        """The tree shares bit tests, so dense tables stay small."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.bf_tree(xor6)) < 10_000  # vs the minterm's ~1.2M

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.bf_tree("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.bf_tree("02")


class TestThreeDBf:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.three_d_brainfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_three_d_brainfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_array_moves_use_the_3d_axes(self) -> None:
        """3D Brainfuck's >/< are no-ops, so the array moves with e/w."""
        program = boolean.three_d_brainfuck("0110")
        assert ">" not in program
        assert "<" not in program
        assert "e" in program
        assert "w" in program

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.three_d_brainfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.three_d_brainfuck("02")


class TestFactor:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.factor(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_factor(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_is_the_decimal_encoding_of_the_bf_program(self) -> None:
        """factor delegates to the brainfuck generator and encodes its
        output, same as the text generator's factor()."""
        from esolangs.tools.text.tape import _factor_encode

        table = "0110"
        assert boolean.factor(table) == str(_factor_encode(boolean.brainfuck(table)))

    def test_sparse_tables_stay_small_at_n_four(self) -> None:
        """Sparse tables (few one-rows) encode a short brainfuck program,
        so they stay well under the digit cap even at n == 4."""
        assert boolean.factor("0" * 16).isdigit()
        assert boolean.factor("1" * 16).isdigit()

    def test_dense_table_past_the_digit_cap_is_rejected(self) -> None:
        """A dense n == 4 table (XOR4) encodes a brainfuck program whose
        Factor integer exceeds CPython's int-to-string digit limit; the
        generator raises instead of letting that ValueError leak from
        str() with its raw CPython wording."""
        xor4 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        with pytest.raises(ValueError, match="digit limit"):
            boolean.factor(xor4)

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.factor("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.factor("02")


class TestSuffolk:
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
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.suffolk(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_suffolk(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_tables_need_no_reads(self) -> None:
        """An all-zero or all-one table never touches ','."""
        assert "," not in boolean.suffolk("00")
        assert "," not in boolean.suffolk("11")

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.suffolk("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.suffolk("02")


class TestPainfuck:
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
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.painfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_painfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_commands_are_preshifted_for_the_trans_table(self) -> None:
        """The interpreter shifts commands through its cycles, so the source
        must be the inverse shift; the translated commands are the BF moves."""
        from esolangs.interpreters.tape_based.painfuck import _translate

        program = boolean.painfuck("0110")
        translated = _translate(program)
        assert "a" in translated  # [ loops
        assert "b" in translated  # ] loops
        assert translated.count("a") == translated.count("b")
        assert "rl" in translated or "l" in translated  # pointer moves

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.painfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.painfuck("02")


class TestBitTilde:
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
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bit_tilde(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bit_tilde(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_single_read_and_output(self) -> None:
        """One read per input and a single final output."""
        program = boolean.bit_tilde("0110")
        assert program.startswith(")")
        assert program.count(")") == 2
        assert program.count("(") == 1
        assert program.endswith("(")

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.bit_tilde("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.bit_tilde("02")


class TestJaune:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("00", 1),  # constant zero
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.jaune(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_jaune(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.jaune(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_jaune(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.jaune("011")

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            (0, 5),
            (5, 0),
            (0, 0),
            (3, 4),
            (12, 34),
            (99, 99),
            (100, 7),
            (7, 100),
            (7, 123),
            (123, 456),
            (12345, 6789),
            (99999, 99999),
        ],
    )
    def test_multiply(self, a: int, b: int) -> None:
        """The sentinel-delimited multiply reads any-length operands."""
        program = boolean.jaune_multiply()
        lines = [*list(str(a)), "*", *list(str(b)), "#"]
        got = run_jaune(program, lines)
        assert got == str(a * b), f"{a} * {b}"

    def test_multiply_all_small_operands(self) -> None:
        """Every single-digit pair produces the right product."""
        program = boolean.jaune_multiply()
        for a in range(10):
            for b in range(10):
                lines = [*list(str(a)), "*", *list(str(b)), "#"]
                got = run_jaune(program, lines)
                assert got == str(a * b), f"{a} * {b}"


class TestBasicfuck:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_program_shape(self, table: str, n: int) -> None:
        """The program declares its cells, reads n inputs, and prints once."""
        program = boolean.basicfuck(table)
        assert program.startswith("#basicfuck t=unbounded r=0~255 o=wrap")
        assert (
            program.splitlines()[1]
            == "#allocate " + ", ".join(f"a{i}" for i in range(1, n + 1)) + ", out"
        )
        assert program.count("read ->") == n  # one read per input
        assert program.count("write <- out ;") == 2**n  # one leaf per row

    def test_decision_tree(self) -> None:
        """Each internal node branches both ways with the wiki's if!(...)."""
        program = boolean.basicfuck("0110")
        assert program.count("if (a1) {") == 1
        assert program.count("if !(a1) {") == 1
        assert program.count("if (a2) {") == 2
        assert program.count("if !(a2) {") == 2

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.basicfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.basicfuck("02")


class TestSbleq:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("0000000000000000", 4),  # constant zero
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.sbleq(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_sbleq(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_structure(self) -> None:
        """The root reads and normalizes, then every leaf outputs and halts."""
        program = boolean.sbleq("0110")
        cells = [int(tok) for tok in program.split()]
        data_base = len(cells) - 13
        assert cells[:3] == [data_base + 4, -2, data_base + 7]  # root read
        assert cells[3:6] == [  # root normalize
            data_base + 4,
            data_base,
            data_base + 10,
        ]
        assert cells[-13:-9] == [-49, 48, 49, -1]  # NEG49, D48, D49, HALT
        code = cells[:data_base]
        triples = [tuple(code[i : i + 3]) for i in range(0, len(code), 3)]
        outputs = [
            t for t in triples if t[0] == -3
        ]  # one output per leaf, in combo order
        assert outputs == [
            (-3, data_base + 1, 0),
            (-3, data_base + 2, 0),
            (-3, data_base + 2, 0),
            (-3, data_base + 1, 0),
        ]
        assert [t for t in triples if t == (0, 0, data_base + 3)] == 4 * [
            (0, 0, data_base + 3)
        ]  # one halt per leaf

    def test_constant_table_has_no_reads(self) -> None:
        """A constant table collapses to an output and a halt."""
        program = boolean.sbleq("0000")
        cells = [int(tok) for tok in program.split()]
        assert cells == [-3, 7, 0, 0, 0, 9, -49, 48, 49, -1]

    def test_mismatched_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.sbleq("011")

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.sbleq("0123")


class TestBrainIf:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.brainif(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_brainif(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input then branches on it."""
        program = boolean.brainif("10")
        assert program.startswith("if 0 input")
        assert "if 48 goto" in program


class TestRotfuck:
    """The ROTfuck boolean generator.

    ROTfuck rotates the program after every command, so the generator lays
    out ``[ body ]`` blocks whose ``]`` is a phantom encoded at the ``[``-fire
    seek state; both the skip and body paths re-converge in the same rotation
    state because every body length is 7 (mod 8).
    """

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0111", 2),  # OR
            ("0110", 2),  # XOR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),  # high half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.rotfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_rotfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_round_trips_every_table_at_n_2(self) -> None:
        """Every two-input table produces the right result."""
        for table_int in range(2 ** (2**2)):
            table = format(table_int, "04b")
            program = boolean.rotfuck(table)
            for combo in range(4):
                bits = [(combo >> (1 - i)) & 1 for i in range(2)]
                got = run_rotfuck(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.rotfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.rotfuck("02")
