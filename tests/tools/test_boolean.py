"""Unit tests for the boolean-function program generators."""

import io
from contextlib import redirect_stdout, suppress
from unittest.mock import patch

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools import boolean


def run_dig(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.dig import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


def run_six_five(program: str, inputs: list[str]) -> str:
    import importlib

    run = importlib.import_module("esolangs.interpreters.tape_based.6-5").run
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_dimensional(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.dimensional import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_bf(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.bf import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


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
        program = boolean.six_five(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_branch_structure(self) -> None:
        """Each level reads a bit and branches to a 4 marker."""
        program = boolean.six_five("0110", 2)
        assert program.startswith("B" + "2" * 8)
        assert "78" in program
        assert program.endswith("A0")

    def test_arithmetic_fallback_path(self) -> None:
        """n > 5 falls back to the arithmetic kernel instead of the tree."""
        program = boolean.six_five("1" + "0" * 63, 6)  # f(x) = (x == 0): T == 1
        assert "8" in program  # loops use 8n jumps
        assert "70" in program  # loop conditionals
        assert program.count("4") <= 35  # within the label budget

    @pytest.mark.parametrize("n", [6, 7, 8, 9])
    @pytest.mark.parametrize("table", ["10", "1100"])
    def test_arithmetic_fallback_table(self, n: int, table: str) -> None:
        """The fallback computes every combination for small-T tables."""
        table = table + "0" * (2**n - len(table))  # ones only at low indices
        program = boolean.six_five(table, n)
        assert len(program) < 2000  # the small-T setup stays short
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_arithmetic_fallback_constant_markers(self) -> None:
        """A loop-based x build keeps the marker count constant in n."""
        markers = {
            n: boolean.six_five("1" + "0" * (2**n - 1), n).count("4")
            for n in (6, 9, 12, 16)
        }
        assert markers == {6: markers[6], 9: markers[6], 12: markers[6], 16: markers[6]}
        assert markers[6] <= 35  # well within the label budget

    def test_arithmetic_fallback_refuses_large_t(self) -> None:
        """AND-n is the worst case: T == 2**(2**n - 1) blows up the setup."""
        with pytest.raises(ValueError, match="~2 MB setup"):
            boolean.six_five("0" * 63 + "1", 6)  # AND6: T == 2**63

    @pytest.mark.parametrize("n", [6, 8, 10])
    def test_arithmetic_fallback_complement(self, n: int) -> None:
        """Tables whose complement is cheap use it instead of a huge T."""
        table = "00" + "1" * (2**n - 2)  # zeros only at indices 0,1: T' == 3
        program = boolean.six_five(table, n)
        assert len(program) < 2000
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_arithmetic_fallback_compact_setup(self) -> None:
        """+6 runs make the setup ~T/6, far below the naive 2T pairs."""
        program = boolean.six_five("1" * 20 + "0" * 44, 6)  # T == 2**20 - 1
        assert len(program) < 500_000  # ~T/6, not ~2T
        assert program[:32].count("6") > program[:32].count("62")  # uses +6 runs

    def test_arithmetic_fallback_complement_marker_budget(self) -> None:
        """The complement output branch stays inside the label budget."""
        program = boolean.six_five("00" + "1" * 62, 6)
        assert program.count("4") <= 35


def run_qoibl(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.qoibl import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


class TestQoibl:
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
        program = boolean.qoibl(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_qoibl(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_minterm_structure(self) -> None:
        """An AND function stores the minterm product and prints 48 + sum."""
        program = boolean.qoibl("0001", 2)
        assert program.startswith("we e we et")
        assert "ry ye ry" in program  # a minterm product
        assert program.endswith("tt")

    def test_empty_truth_table(self) -> None:
        """A constant-zero function skips all minterms."""
        program = boolean.qoibl("0000", 2)
        assert "ry ye ry" not in program


def run_ascii_art(program: str, inputs: list[str]) -> str:
    import importlib

    run = importlib.import_module("esolangs.interpreters.tape_based.ascii-art").run
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


class TestAsciiArt:
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
        program = boolean.ascii_art(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_ascii_art(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_is_art(self) -> None:
        """The program is ASCII art, not raw brainfuck."""
        program = boolean.ascii_art("0110", 2)
        assert "[" not in program
        assert "|" in program


def run_polynomial(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.polynomial import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_bfstack(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.stack_based.bfstack import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


class TestPolynomial:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.polynomial(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_is_polynomial(self) -> None:
        """The program is a polynomial function."""
        assert boolean.polynomial("0110", 2).startswith("f(x) = ")

    def test_only_supports_two_inputs(self) -> None:
        with pytest.raises(ValueError, match="n == 2"):
            boolean.polynomial("11111110", 3)


class TestUnsquare:
    def test_program_shape(self) -> None:
        """The program reads n inputs and prints once."""
        program = boolean.unsquare("0110", 2)
        assert program.startswith("iA>-<P" * 2)
        assert program.count("iA>-<P") == 2  # one read per input
        assert program.endswith("o")

    def test_decision_tree(self) -> None:
        """Each internal node branches on a bit with the flip primitive."""
        program = boolean.unsquare("0110", 2)
        assert "x->IA<" in program  # the stack-clean flip
        assert program.count("x>") >= 3  # one guard per branch

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.unsquare("011", 1)

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.unsquare("02", 1)


class TestBfstack:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bfstack(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bfstack(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_encode_decode_structure(self) -> None:
        """The program encodes the inputs then tests the zero rows."""
        program = boolean.bfstack("0110", 2)
        assert program.startswith(">>+,")  # result cell, accumulator, first input
        assert program.count(",") == 2  # one read per input
        assert program.endswith("+" * 48 + ".")  # print 48 + result


class TestDig:
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
        program = boolean.dig(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dig(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_xor_layout(self) -> None:
        """The XOR gate produces the standard two-level decision tree."""
        expected = (
            "'           > >$30:@\n"
            "     > >2$~;#@\n"
            "            > >$31:@\n"
            ">2$~;#@       \n"
            "            > >$31:@\n"
            "     > >2$~;#@\n"
            "            > >$30:@"
        )
        assert boolean.dig("0110", 2) == expected


def run_sophie(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.sophie import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


class TestForth:
    def test_program_structure(self) -> None:
        """The program defines one function per tree node and reads n bits."""
        program = boolean.forth("0001", 2)
        assert program.endswith("1+;.")
        assert program.count("{") == program.count("}") == 6  # 6 nodes
        assert program.count(",68*-") == 2  # read and normalize 2 inputs

    def test_leaf_results_are_the_byte(self) -> None:
        """Each leaf pushes 48 + its table entry."""
        program = boolean.forth("0001", 2)
        assert "3F*3+" in program  # '0' leaves push 48 = 3*15+3
        assert "3F*4+" in program  # the '1' leaf pushes 49 = 3*15+4

    def test_scales(self) -> None:
        """More inputs mean more tree functions."""
        program = boolean.forth("0" * 16 + "1" * 16, 5)
        assert program.count("{") == 2 ** (5 + 1) - 2
        assert program.count(",68*-") == 5

    def test_const_large(self) -> None:
        """Constants above 225 need multiple base-15 digits."""
        from esolangs.tools.booleans.stack import _forth_const

        assert _forth_const(0) == "0"
        assert len(_forth_const(300)) > len(_forth_const(48))


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
        program = boolean.dimensional(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dimensional(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_moves_are_pinned_to_dimension_zero(self) -> None:
        """A bare >/< would take its dimension from the cell's value."""
        program = boolean.dimensional("0110", 2)
        rest = program.replace(">0", "").replace("<0", "")
        assert ">" not in rest
        assert "<" not in rest

    def test_scales_beyond_the_old_reference_cap(self) -> None:
        """The v3.0 interpreter's unbounded cells lift the old n <= 12 cap."""
        program = boolean.dimensional("0" * 4095 + "1", 12)
        got = run_dimensional(program, ["1"] * 12)
        assert got == "1"

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.dimensional("011", 1)

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.dimensional("02", 1)


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
        program = boolean.dimensional_tree(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dimensional(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_small_on_dense_tables(self) -> None:
        """The tree shares bit tests, so dense tables stay small."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.dimensional_tree(xor6, 6)) < 10_000  # vs ~34K survivor

    def test_dimensional_dispatches(self) -> None:
        """dimensional picks the survivor for sparse and the tree for dense."""
        sparse = boolean.dimensional("0" * 15 + "1", 4)  # AND4
        assert len(sparse) < len(boolean.dimensional_tree("0" * 15 + "1", 4))
        xor = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        assert boolean.dimensional(xor, 4) == boolean.dimensional_tree(xor, 4)


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
        program = boolean.bf(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_bf_sparse_uses_the_minterm(self) -> None:
        """bf picks the minterm for sparse tables (shorter than the tree)."""
        program = boolean.bf("0" * 15 + "1", 4)  # AND4: one one-row
        assert len(program) < len(boolean.bf_tree("0" * 15 + "1", 4))

    def test_bf_dense_uses_the_tree(self) -> None:
        """bf picks the decision tree for dense tables."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert boolean.bf(xor6, 6) == boolean.bf_tree(xor6, 6)

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.bf("011", 1)

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.bf("02", 1)


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
        program = boolean.bf_tree(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_small_on_dense_tables(self) -> None:
        """The tree shares bit tests, so dense tables stay small."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.bf_tree(xor6, 6)) < 10_000  # vs the minterm's ~1.2M

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.bf_tree("011", 1)

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.bf_tree("02", 1)


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
        program = boolean.basicfuck(table, n)
        assert program.startswith("#basicfuck t=unbounded r=0~255 o=wrap")
        assert (
            program.splitlines()[1]
            == "#allocate " + ", ".join(f"a{i}" for i in range(1, n + 1)) + ", out"
        )
        assert program.count("read ->") == n  # one read per input
        assert program.count("write <- out ;") == 2**n  # one leaf per row

    def test_decision_tree(self) -> None:
        """Each internal node branches both ways with the wiki's if!(...)."""
        program = boolean.basicfuck("0110", 2)
        assert program.count("if (a1) {") == 1
        assert program.count("if !(a1) {") == 1
        assert program.count("if (a2) {") == 2
        assert program.count("if !(a2) {") == 2

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.basicfuck("011", 1)

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.basicfuck("02", 1)


class TestSophie:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111110", 4),  # NAND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.sophie(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_sophie(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function is a single conditional pair."""
        assert boolean.sophie("10", 1) == ";@$48{#$49,&}{#$48,&}"


def run_modulous(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.stack_based.modulous import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


class TestModulous:
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
        program = boolean.modulous(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_modulous(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input then branches on it."""
        assert boolean.modulous("10", 1).startswith("[INP INT]")
        assert "[JMP F 2 IF 0]" in boolean.modulous("10", 1)


def run_brainif(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.brainif import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


def run_nevermind(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.other.nevermind import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


def run_container(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.other.container import run

    buffer = io.StringIO()
    with (
        patch("builtins.input", side_effect=inputs),
        redirect_stdout(buffer),
        suppress(SystemExit),  # EXIT halts via sys.exit
    ):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


class TestNevermind:
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
        program = boolean.nevermind(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_nevermind(program, [str(b) for b in bits])
            assert got == str(int(table[combo])) + "\n", f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input and branches on it."""
        program = boolean.nevermind("10", 1)
        assert program.startswith("input,?")
        assert "if,$a,==,0" in program
        assert program.count("endif") == 2


class TestContainer:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # NOT
            ("10", 1),
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.container(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_container(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """The program reads n inputs and keeps one survivor per row."""
        program = boolean.container("0110", 2)
        assert program.startswith("T:\n+1 T>=T")
        assert ":" in program.splitlines()[:4]  # the empty-named reader
        assert program.count("S") >= 4  # a survivor per row
        assert program.count("PRINT:") == 1

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.container("011", 1)

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.container("02", 1)


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
        program = boolean.brainif(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_brainif(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input then branches on it."""
        program = boolean.brainif("10", 1)
        assert program.startswith("if 0 input")
        assert "if 48 goto" in program


def run_taglate(program: str, inputs: list[str]) -> str:
    import esolangs

    return esolangs.run("Taglate", program, stdin="\n".join(inputs))


def run_clockwise(program: str, inputs: list[str]) -> str:
    import esolangs

    # Clockwise reads the whole input as one line (7 bits per char)
    return esolangs.run("Clockwise", program, stdin="".join(inputs))


def run_ztoalc(program: str, inputs: list[str]) -> str:
    import esolangs

    return esolangs.run("ZTOALC", program, stdin="\n".join(inputs))


class TestParameterizedBIO:
    """Input-by-substitution generators for the no-input language BIO."""

    def run_bio(self, prog: str, bits: list[int]) -> str:
        import importlib

        from esolangs.interpreters.io import IO

        run = importlib.import_module("esolangs.interpreters.register_based.bio").run
        buffer = io.StringIO()
        with (
            patch("builtins.input", side_effect=[str(b) for b in bits]),
            redirect_stdout(buffer),
        ):
            run(prog, io=IO())
        return buffer.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.booleans import parameterized

        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: "0ox" * b,
            lambda _i, _b: "0oy0ix1oy1ox}",
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.booleans import parameterized

        template = parameterized.bio(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bio(self.instantiate(template, bits), bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi}/{Ci} placeholders, not hardcoded bits."""
        from esolangs.tools.booleans import parameterized

        template = parameterized.bio("0110", 2)
        assert "{X0}" in template
        assert "{X1}" in template
        assert "{C0}" in template

    def test_runtime_complement(self) -> None:
        """The {Ci} placeholder computes 1 - x in the program, not a constant."""
        from esolangs.tools.booleans import parameterized

        template = parameterized.bio("10", 1)
        assert "0ix" in template  # the complement computation is emitted, not a literal


class TestParameterizedBack:
    """Input-by-substitution generators for the no-input language Back."""

    def run_back(self, prog: str) -> str:
        from esolangs.interpreters.io import IO
        from esolangs.interpreters.tape_based.back import run

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(prog.splitlines(), io=IO())
        return buffer.getvalue().strip()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.booleans import parameterized

        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: "\\" if b else "/",
            lambda _i, _b: "/",
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
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
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.booleans import parameterized

        template = parameterized.back(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_back(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.booleans import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.back(table, n)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_back(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.booleans import parameterized

        template = parameterized.back("0110", 2)
        assert "{X0}" in template
        assert "{X1}" in template

    def test_mirror_routing(self) -> None:
        """Each node is a mirror: backslash for a one, slash for a zero."""
        from esolangs.tools.booleans import parameterized

        template = parameterized.back("0110", 2)
        # XOR has three internal nodes (X0, X1, X1)
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 2

    def test_leaf_sets_tape_bit(self) -> None:
        """A one-result leaf flips the tape bit; a zero-result leaf halts bare."""
        from esolangs.tools.booleans import parameterized

        template = parameterized.back("0110", 2)
        assert "-*" in template
        assert "*" in template


class TestZtoalc:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("00000001", 3),  # AND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.ztoalc_boolean(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_ztoalc(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to two inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.ztoalc_boolean(table, n)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert run_ztoalc(program, [str(b) for b in bits]) == table[combo]

    def test_structure(self) -> None:
        """The program rides a Collatz descent with jumps and prints."""
        program = boolean.ztoalc_boolean("0110", 2)
        lines = program.splitlines()
        assert lines[0].strip().isdigit()  # line 1 is the starting value
        assert any("jump" in line for line in lines)
        assert any(line.strip().startswith("print") for line in lines)

    def test_xor4_linear_fallback(self) -> None:
        """Dense symmetric tables fall back to a huge linear program."""
        program = boolean.ztoalc_boolean("0110100110010110", 4)  # XOR4 = parity
        assert len(program.splitlines()) > 100_000  # linear, not the small tree
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            got = run_ztoalc(program, [str(b) for b in bits])
            assert got == str(int("0110100110010110"[combo])), f"inputs {bits}"

    def test_dense_non_symmetric_raises(self) -> None:
        """A dense non-symmetric n=4 tree cannot be placed and is rejected."""
        with pytest.raises(ValueError, match="no collision-free placement"):
            # tree fails, and the table is not popcount-symmetric, so the
            # linear fallback cannot help either
            boolean.ztoalc_boolean("1010001000011000", 4)

    def test_wrong_length_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.ztoalc_boolean("011", 1)

    def test_invalid_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.ztoalc_boolean("02", 1)


class TestClockwise:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),
            ("10", 1),
            ("00", 1),
            ("11", 1),
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("00000001", 3),  # AND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination prints the result bit seven times."""
        program = boolean.clockwise(table, n)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_clockwise(program, bits)
            assert got == chr(127 * int(table[combo])), f"inputs {bits}"

    def test_ring_starts_at_origin(self) -> None:
        """The program is a closed ring whose pointer starts at (0, 0)."""
        program = boolean.clockwise("0110", 2)
        lines = program.splitlines()
        assert lines[0][0] == " "
        assert run_clockwise(program, ["1", "0"]) == "\x7f"


class TestTaglate:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("00", 1),
            ("01", 1),
            ("10", 1),
            ("11", 1),
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("1110", 2),  # NAND
            ("00000001", 3),  # majority
            ("0000000000000001", 4),  # 4-AND
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.taglate(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            # Odd n > 1 uses a ghost digit (fake zero first input)
            inputs = (
                ["0"] + [str(b) for b in bits]
                if n % 2 == 1 and n > 1
                else [str(b) for b in bits]
            )
            got = run_taglate(program, inputs)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        """Every two-input truth table produces the right result."""
        for table in range(16):
            tt = format(table, "04b")
            for combo in range(4):
                bits = [(combo >> 1) & 1, combo & 1]
                got = run_taglate(boolean.taglate(tt, 2), [str(b) for b in bits])
                assert got == tt[combo], f"{tt} inputs {bits}"

    def test_all_three_input_tables(self) -> None:
        """Every three-input truth table produces the right result."""
        failures = 0
        for table in range(256):
            tt = format(table, "08b")
            program = boolean.taglate(tt, 3)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                inputs = ["0"] + [str(b) for b in bits]  # ghost digit
                got = run_taglate(program, inputs)
                if got != tt[combo]:
                    failures += 1
                    if failures <= 3:
                        print(
                            f"  FAIL {tt} inputs {bits}: "
                            f"got {got!r} expected {tt[combo]!r}"
                        )
        assert failures == 0, f"{failures} failures out of 2048 combos"

    def test_wrong_length_truth_table_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.taglate("011", 2)

    def test_invalid_truth_table_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.taglate("0120", 2)


class TestThreeX:
    def test_identity_program_structure(self) -> None:
        """The 01 table reads a bit and stores it before printing."""
        program = boolean.three_x("01", 1)
        assert program.startswith("?")
        assert program.endswith("!")

    def test_wrong_length_truth_table_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.three_x("011", 1)

    def test_invalid_truth_table_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.three_x("02", 1)

    def test_uses_input_variables(self) -> None:
        """Each input bit is read into a distinct variable."""
        program = boolean.three_x("0001", 2)
        assert program.count("?") == 2
        assert "333x" in program  # the constant-0 encoding appears
        assert "3333x3x" in program  # the constant-1 encoding appears

    def test_constant_table_has_no_override_blocks(self) -> None:
        """When every row equals the default, no ( ... ) guards are emitted."""
        assert "(" not in boolean.three_x("0" * 4, 2)
        assert "(" not in boolean.three_x("1" * 4, 2)

    def test_majority_default_handles_zero_row(self) -> None:
        """A zero row differing from a majority-1 default still overrides it."""
        program = boolean.three_x("0110", 2)  # XOR: two 1s, two 0s
        assert program.startswith("?")
        assert program.endswith("!")
        assert "(" in program  # the zero row needs an override block

    def test_scales_to_more_inputs(self) -> None:
        """The generator handles n beyond the built-in constants."""
        program = boolean.three_x("0" * (2**7), 7)
        assert program.count("?") == 7

    def test_shared_tree_prefix_sharing(self) -> None:
        """Differing combos share prefix guards instead of repeating them."""
        # top-half n=5: 16 zero-rows all share MSB=0.  A full tree has
        # 31 guard nodes; independent chains would emit 16 * 5 = 80.
        program = boolean.three_x("0" * 16 + "1" * 16, 5)
        assert program.count("(") < 40

    def test_digit_constant_encodings(self) -> None:
        """The base-3 digit seeds are the closed-form minimal programs."""
        from esolangs.tools.booleans import other

        assert other._const(0) == "333x"  # noqa: SLF001
        assert other._const(1) == "3333x3x"  # noqa: SLF001
        assert other._const(2) == "3333x3x3333x3x3x"  # noqa: SLF001

    def test_base_three_digits_accumulate(self) -> None:
        """Each base-3 digit past the first appends the 3v+d affine step."""
        from esolangs.tools.booleans import other

        # 12 is "110" in base 3: seed 1, then d=1, then d=0.  Each transform
        # adds exactly one `#` (the swap before the `x`), and no seed has one.
        twelve = other._const(12)  # noqa: SLF001
        assert twelve.startswith(other._const(1))  # noqa: SLF001
        assert twelve.count("#") == 2

    def test_formula_scales_logarithmically(self) -> None:
        """The closed form grows with the digit count, not the value."""
        from esolangs.tools.booleans import other

        small, large = other._const(100), other._const(1_000_000)  # noqa: SLF001
        assert len(small) < 120  # 100 is "10201": 5 digits
        assert len(large) < 350  # 1_000_000 is 13 base-3 digits
        assert len(large) < len(small) * 4


def run_laserfuck(program: str, inputs: list[str], heading: int) -> str:
    import re

    from esolangs.interpreters.io import IO
    from esolangs.interpreters.other.laserfuck import run

    buffer = io.StringIO()

    class FakeIO(IO):
        def __init__(self, ins: list[str]) -> None:
            self._ins = list(ins)

        def input_str(self, prompt: str = "Input: ") -> str:  # noqa: ARG002
            return self._ins.pop(0)

        def print_char(self, char: str) -> None:
            buffer.write(char)

        def print_line(self, text: str = "") -> None:
            buffer.write(text + "\n")

        def print_num(self, num: int) -> None:
            buffer.write(str(num))

    with redirect_stdout(buffer):
        run(program.splitlines(), FakeIO(inputs), heading=heading)
    # byte output mode prints every touched cell; the 0/1 input cells print as
    # NUL/SOH, so filtering to '0'/'1' leaves exactly the 48/49 result cell
    return re.sub("[^01]", "", buffer.getvalue())


class TestLaserFuck:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("00000001", 3),  # AND3
            ("1111111100000000", 4),  # top half
            ("0110100110010110", 4),  # XOR4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.laserfuck(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == str(int(table[combo])), f"inputs {bits} heading {heading}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.laserfuck(table, n)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_laserfuck(program, [str(b) for b in bits], 3)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_funnel_is_heading_independent(self) -> None:
        """Every initial heading reaches the tree on the top row."""
        program = boolean.laserfuck("0110", 2)
        for heading in range(4):
            assert run_laserfuck(program, ["1", "0"], heading) == "1"

    def test_byte_output_mode(self) -> None:
        """The first grid cell selects byte output (no separators)."""
        program = boolean.laserfuck("10", 1)
        assert program.splitlines()[0][0] == "\u00ff"

    def test_loop_free_tree(self) -> None:
        """The decision tree uses the #/)/\\ branch, not loop rings."""
        program = boolean.laserfuck("0110", 2)
        assert "#" in program
        assert ")" in program
        assert "\\" in program

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.laserfuck("011", 1)

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.laserfuck("02", 1)
