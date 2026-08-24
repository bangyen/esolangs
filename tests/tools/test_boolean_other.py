"""Unit tests for the single-language boolean generators.

Covers the generators in :mod:`esolangs.tools.boolean.other` and
:mod:`esolangs.tools.boolean.ztoalc_l`, plus the shared validation and
helper edge paths exercised across generator modules.
"""

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools import boolean
from tests.tools.boolean_runners import (
    run_between,
    run_clockwise,
    run_container,
    run_flowchart,
    run_forbin_boolean,
    run_laserfuck,
    run_myscript,
    run_nevermind,
    run_suptiftam,
    run_taglate,
    run_ztoalc,
)


class TestSuptiftam:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # AND4
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.suptiftam(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_suptiftam(program, bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_minterm_structure(self) -> None:
        """The program reads one row per input and sums the minterms."""
        program = boolean.suptiftam("0001")
        assert program.startswith("sum=0\np=1\nfd mulStep :x")
        assert program.count("%-[read]22%") == 2  # one normalized read per input
        assert program.count("down(:read:)") == 2
        assert program.endswith("term=sum")

    def test_constant_tables_skip_the_minterms(self) -> None:
        """A constant-zero table has no minterm rows at all."""
        program = boolean.suptiftam("0000")
        assert "mulStep(:p:)if(p)" not in program

    def test_bit_names_extend_beyond_the_alphabet(self) -> None:
        """Identifiers are alphabetical, so past 'z' the names grow a prefix."""
        from esolangs.tools.boolean.other import _suptiftam_bit

        assert _suptiftam_bit(0) == "b"
        assert _suptiftam_bit(24) == "z"
        assert _suptiftam_bit(25) == "bb"
        assert _suptiftam_bit(49) == "bz"
        assert _suptiftam_bit(50) == "bbb"

    def test_rejects_bad_table(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            boolean.suptiftam("011")

    def test_rejects_non_binary(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.suptiftam("02")


class TestForbinBoolean:
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
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.forbin_boolean(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_forbin_boolean(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_uses_the_lsb_of_each_input(self) -> None:
        """Each input is read as 8 bits and only the LSB drives the tree."""
        program = boolean.forbin_boolean("01")
        # one 8-variable read, then a decision tree that prints '1' for bit 1
        assert "i0_0,i0_1,i0_2,i0_3,i0_4,i0_5,i0_6,i0_7 = (in 0);" in program

    def test_rejects_bad_table(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            boolean.forbin_boolean("011")

    def test_rejects_non_binary(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.forbin_boolean("02")


class TestFlowchart:
    """The Flowchart boolean generator (works for arbitrary n)."""

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
            ("01101001", 3),  # XOR3
            ("11111110", 3),  # NAND3
            ("0110100110010110", 4),  # XOR4
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.flowchart(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_flowchart(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_depth_matches_input_count(self) -> None:
        """One ``/ /`` read node sits on each path from entry to a leaf."""
        program = boolean.flowchart("0110100110010110")
        assert program.count("< >") == 15  # 2**4 - 1 internal nodes
        assert program.count("(( ))") == 16  # 2**4 leaves

    def test_each_run_reads_exactly_n_bits(self) -> None:
        """The drawn read nodes outnumber the reads any one run performs.

        A depth-4 tree draws 15 ``/ /`` nodes, but a run walks a single
        root-to-leaf path and consumes exactly 4 bits, so the duplication is
        spatial rather than a bit being read more than once (see the
        generator's docstring on why the parameterized once-only embedding
        rule does not apply to an input-reading generator).
        """
        program = boolean.flowchart("0110100110010110")
        assert program.count("/ /") == 15

        consumed = 0

        class _CountingIO(IO):
            def input_str(self, _prompt: str = "Input: ") -> str:
                nonlocal consumed
                consumed += 1
                return "1"

            def print_str(self, text: str) -> None:
                pass

        from esolangs.interpreters.grid_based.flowchart import run as fc_run

        fc_run(program.splitlines(), _CountingIO())
        assert consumed == 4

    def test_rejects_a_malformed_table(self) -> None:
        """A table whose length is not a power of two is rejected."""
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.flowchart("011")


class TestBetween:
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
        program = boolean.between(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_between(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_structure(self) -> None:
        """One declare/read/normalize triplet per input, one branch per node."""
        program = boolean.between("0110")
        lines = program.splitlines()
        assert lines[:3] == ["'0'v.", "[0]i.", "[0]s|[0]c.|"]
        assert lines.count(".x.") == 4  # one leaf per input combination

    def test_mismatched_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.between("011")

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.between("0123")


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
        program = boolean.nevermind(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_nevermind(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input and branches on it."""
        program = boolean.nevermind("10")
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
        program = boolean.container(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_container(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """The program reads n inputs and keeps one survivor per row."""
        program = boolean.container("0110")
        assert program.startswith("T:\n+1 T>=T")
        assert ":" in program.splitlines()[:4]  # the empty-named reader
        assert program.count("S") >= 4  # a survivor per row
        assert program.count("PRINT:") == 1

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.container("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.container("02")


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
        program = boolean.ztoalc_l_boolean(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_ztoalc(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to two inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.ztoalc_l_boolean(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert run_ztoalc(program, [str(b) for b in bits]) == table[combo]

    def test_structure(self) -> None:
        """The program rides a Collatz descent with jumps and prints."""
        program = boolean.ztoalc_l_boolean("0110")
        lines = program.splitlines()
        assert lines[0].strip().isdigit()  # line 1 is the starting value
        assert any("jump" in line for line in lines)
        assert any(line.strip().startswith("print") for line in lines)

    def test_xor4_linear_fallback(self) -> None:
        """Dense symmetric tables fall back to a huge linear program."""
        program = boolean.ztoalc_l_boolean("0110100110010110")  # XOR4 = parity
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
            boolean.ztoalc_l_boolean("1010001000011000")

    def test_wrong_length_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.ztoalc_l_boolean("011")

    def test_invalid_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.ztoalc_l_boolean("02")


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
        """Every input combination prints the result as an ASCII digit."""
        program = boolean.clockwise(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_clockwise(program, bits)
            assert got == table[combo], f"inputs {bits}"

    def test_ring_starts_at_origin(self) -> None:
        """The program is a closed ring whose pointer starts at (0, 0)."""
        program = boolean.clockwise("0110")
        lines = program.splitlines()
        assert lines[0][0] == " "
        assert run_clockwise(program, ["1", "0"]) == "1"  # XOR(1, 0)

    @pytest.mark.parametrize(("table", "n"), [("0001", 2), ("01101001", 3)])
    def test_tree_sits_against_the_left_edge(self, table: str, n: int) -> None:
        """No column is dead: the spine starts as far left as it can.

        The tree's turns are relative, so its absolute column never
        matters; a spine further right is pure padding.  It only has to
        clear the ``2**(n + 1) - 1`` columns its leftward branches span,
        leaving column 0 for the closing corner.
        """
        program = boolean.clockwise(table)
        rows = program.splitlines()
        width = max(len(row) for row in rows)
        grid = [row.ljust(width) for row in rows]
        dead = [x for x in range(width) if all(row[x] == " " for row in grid)]
        assert not dead, f"dead columns {dead}"
        assert width == 2 ** (n + 1) + 1


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
        program = boolean.taglate(table)
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
                got = run_taglate(boolean.taglate(tt), [str(b) for b in bits])
                assert got == tt[combo], f"{tt} inputs {bits}"

    def test_all_three_input_tables(self) -> None:
        """Every three-input truth table produces the right result."""
        failures = 0
        for table in range(256):
            tt = format(table, "08b")
            program = boolean.taglate(tt)
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
            boolean.taglate("011")

    def test_invalid_truth_table_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.taglate("0120")


class TestThreeX:
    def test_identity_program_structure(self) -> None:
        """The 01 table reads a bit and stores it before printing."""
        program = boolean.three_x("01")
        assert program.startswith("?")
        assert program.endswith("!")

    def test_wrong_length_truth_table_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.three_x("011")

    def test_invalid_truth_table_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.three_x("02")

    def test_uses_input_variables(self) -> None:
        """Each input bit is read into a distinct variable."""
        program = boolean.three_x("0001")
        assert program.count("?") == 2
        assert "333x" in program  # the constant-0 encoding appears
        assert "3333x3x" in program  # the constant-1 encoding appears

    def test_constant_table_has_no_override_blocks(self) -> None:
        """When every row equals the default, no ( ... ) guards are emitted."""
        assert "(" not in boolean.three_x("0" * 4)
        assert "(" not in boolean.three_x("1" * 4)

    def test_majority_default_handles_zero_row(self) -> None:
        """A zero row differing from a majority-1 default still overrides it."""
        program = boolean.three_x("0110")  # XOR: two 1s, two 0s
        assert program.startswith("?")
        assert program.endswith("!")
        assert "(" in program  # the zero row needs an override block

    def test_scales_to_more_inputs(self) -> None:
        """The generator handles n beyond the built-in constants."""
        program = boolean.three_x("0" * (2**7))
        assert program.count("?") == 7

    def test_shared_tree_prefix_sharing(self) -> None:
        """Differing combos share prefix guards instead of repeating them."""
        # top-half n=5: 16 zero-rows all share MSB=0.  A full tree has
        # 31 guard nodes; independent chains would emit 16 * 5 = 80.
        program = boolean.three_x("0" * 16 + "1" * 16)
        assert program.count("(") < 40

    def test_digit_constant_encodings(self) -> None:
        """The base-3 digit seeds are the closed-form minimal programs."""
        from esolangs.tools.boolean import other

        assert other._const(0) == "333x"  # noqa: SLF001
        assert other._const(1) == "3333x3x"  # noqa: SLF001
        assert other._const(2) == "3333x3x3333x3x3x"  # noqa: SLF001

    def test_base_three_digits_accumulate(self) -> None:
        """Each base-3 digit past the first appends the 3v+d affine step."""
        from esolangs.tools.boolean import other

        # 12 is "110" in base 3: seed 1, then d=1, then d=0.  Each transform
        # adds exactly one `#` (the swap before the `x`), and no seed has one.
        twelve = other._const(12)  # noqa: SLF001
        assert twelve.startswith(other._const(1))  # noqa: SLF001
        assert twelve.count("#") == 2

    def test_formula_scales_logarithmically(self) -> None:
        """The closed form grows with the digit count, not the value."""
        from esolangs.tools.boolean import other

        small, large = other._const(100), other._const(1_000_000)  # noqa: SLF001
        assert len(small) < 120  # 100 is "10201": 5 digits
        assert len(large) < 350  # 1_000_000 is 13 base-3 digits
        assert len(large) < len(small) * 4


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
        program = boolean.laserfuck(table)
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
            program = boolean.laserfuck(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_laserfuck(program, [str(b) for b in bits], 3)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_funnel_is_heading_independent(self) -> None:
        """Every initial heading reaches the tree on the top row."""
        program = boolean.laserfuck("0110")
        for heading in range(4):
            assert run_laserfuck(program, ["1", "0"], heading) == "1"

    def test_decimal_output_mode(self) -> None:
        """No ``\\xff`` marker, so the tape dumps as numbers, not bytes.

        Byte mode would print the answer as ``chr(result)``, which is why
        the leaves used to add 48 to reach ASCII ``'0'``/``'1'``.  In decimal
        mode the leaf writes the result itself.
        """
        program = boolean.laserfuck("10")
        assert program.splitlines()[0][0] != "\u00ff"
        assert "\u00ff" not in program

    def test_prints_only_the_answer(self) -> None:
        """The dump is exactly the result: no input cells, no separators.

        The input cells are driven negative by the leaf, and ``dump`` skips
        negative cells, so nothing but the answer survives.
        """
        program = boolean.laserfuck("0001")  # AND2
        for bits, want in (([0, 1], "0"), ([1, 1], "1")):
            got = run_laserfuck(program, [str(b) for b in bits], 3)
            assert got == want, f"inputs {bits}"

    def test_loop_free_tree(self) -> None:
        """The decision tree uses the #/)/\\ branch, not loop rings."""
        program = boolean.laserfuck("0110")
        assert "#" in program
        assert ")" in program
        assert "\\" in program

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.laserfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.laserfuck("02")

    @pytest.mark.parametrize(
        ("table", "n", "width"),
        [
            # The tree is never folded and grows six columns per node, so the
            # narrowest width a table can honour rises with its input count:
            # roughly 19, 34, and 63 columns for one, two, and three inputs.
            ("01", 1, 20),
            ("01", 1, 40),
            ("10", 1, 80),
            ("0110", 2, 34),
            ("0110", 2, 80),
            ("1000", 2, 120),
            ("01101001", 3, 63),
            ("01101001", 3, 80),
            ("11111110", 3, 120),
        ],
    )
    def test_honours_a_width(self, table: str, n: int, width: int) -> None:
        """``width`` bounds the columns and the table still computes.

        The grid's width is dominated by its straight runs -- 49 columns per
        input reader and another 49 per leaf -- so those fold into zigzags
        that cost rows instead.  The decision tree is not folded: its
        columns carry the descent paths.  Every heading is checked, since
        the fold adds cells the funnel's beam could otherwise land on.
        """
        program = boolean.laserfuck(table, width)
        assert max(len(line) for line in program.split("\n")) <= width
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == str(int(table[combo])), f"{bits} heading {heading}"

    def test_width_is_narrower_than_the_unfolded_grid(self) -> None:
        """Folding buys columns, rather than only reshaping the grid."""
        table = "01101001"  # XOR3
        unfolded = max(len(ln) for ln in boolean.laserfuck(table).split("\n"))
        assert unfolded > 80  # the reader run alone is 49 columns per input
        assert max(len(ln) for ln in boolean.laserfuck(table, 80).split("\n")) <= 80

    @pytest.mark.parametrize(("table", "n"), [("0001", 2), ("01101001", 3)])
    def test_tree_columns_are_linear_in_the_input_count(
        self, table: str, n: int
    ) -> None:
        """The staircase shares a column per level, not one per node.

        Rows are handed out depth-first, so a subtree owns a contiguous
        band and two nodes on the same level never share a row -- which is
        what lets them share a column.  The tree therefore spans ``6 * n``
        columns rather than ``6 * (2**(n + 1) - 1)``.
        """
        program = boolean.laserfuck(table)
        rows = program.split("\n")
        width = max(len(line) for line in rows)
        # Row 0 is the reader run (49 columns per input) and row 3 the leg
        # that carries the beam back to the margin; the tree starts below.
        tree_width = max(len(line) for line in rows[4:])
        assert tree_width < width
        # Six columns per level, plus the leaf run's sweep and answer.
        assert tree_width <= 6 * n + 4 * n + 20

    def test_without_a_width_is_unchanged(self) -> None:
        """The default stays exactly what the generator always produced."""
        for table in ("01", "10", "0110", "01101001"):
            assert boolean.laserfuck(table) == boolean.laserfuck(table, None)

    def test_too_narrow_a_width_is_ignored(self) -> None:
        """A width the tree cannot fit in is ignored rather than raising.

        The tree grows six columns per node and is never folded, so below
        some width there is nothing the fold can do; the generator emits the
        grid it can build instead of failing, matching the rest of the
        width plumbing.
        """
        program = boolean.laserfuck("01101001", 8)
        assert run_laserfuck(program, ["0", "0", "0"], 3) == "0"


class TestMyScript:
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
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.myscript(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_myscript(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_rejects_bad_table(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            boolean.myscript("011")

    def test_rejects_non_binary(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.myscript("02")


class TestGeneratorEdgePaths:
    """Coverage for validation and helper edge paths in the generators."""

    def test_parameterized_validation(self) -> None:
        """bio/back reject malformed truth tables."""
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.bio("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            parameterized.bio("0123")
        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.back("011")

    def test_dimensional_tree_validation(self) -> None:
        """The Dimensional decision-tree generator rejects bad truth tables."""
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.dimensional_tree("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.dimensional_tree("0123")

    def test_six_five_helper_edges(self) -> None:
        """Same-cell navigation and the +5 tail of the constant encoder."""
        from esolangs.tools.boolean.six_five import _six_five_const, _six_five_nav

        assert _six_five_nav(3, 3) == ""
        assert _six_five_const(5) == "5"
        assert _six_five_const(11) == "65"

    def test_ztoalc_simulator_rejects_bad_program(self) -> None:
        """An empty or non-numeric first line fails the fast simulator."""
        from esolangs.tools.boolean.ztoalc_l import _ztoalc_ok

        assert _ztoalc_ok({}, 0, "", "") is False
        assert _ztoalc_ok({0: "not-a-number"}, 0, "", "") is False

    def test_ztoalc_simulator_input_exhausted(self) -> None:
        """A '=' instruction with no input left fails the fast simulator."""
        from esolangs.tools.boolean.ztoalc_l import _ztoalc_ok

        assert _ztoalc_ok({0: "2", 1: "a = 1"}, 1, "", "") is False
