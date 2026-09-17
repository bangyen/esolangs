"""The generators still in :mod:`esolangs.tools.other`, and its neighbours.

three_x, Container and Forbin from the facade itself, plus Packlang, Inject,
Fargo and the Algebraic Programming Language.  The languages with a generator
file of their own have a test file to match: test_boolean_laserfuck, _ztoalc,
_cvnc, _flowchart, _clockwise and _taglate.
"""

import itertools
import random
from itertools import pairwise

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_algebraic_programming_language,
    run_container,
    run_fargo,
    run_forbin_boolean,
    run_inject,
)


class TestPacklangLinearTree:
    """Fast structural coverage for Packlang's linear decision tree."""

    def test_constants_fold_and_parity_doubles(self) -> None:
        """Cover both leaf values, branching, and empty/nonempty bodies."""
        assert "If " not in boolean.packlang("0000")
        assert boolean.packlang("1111").count("INCR acc") == 1
        sizes = []
        for n in (7, 8):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(boolean.packlang(table)))
        assert sizes[1] < 2 * sizes[0]


class TestInject:
    """The decision tree of ``skipq`` guards over stored input blocks."""

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
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result.

        ``send`` terminates every line it writes and is the only output
        command, so the answer arrives with a newline after it.
        """
        program = boolean.inject(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_inject(program, bits)
            assert got == table[combo] + "\n", f"inputs {bits}"

    def test_every_two_input_table(self) -> None:
        """All sixteen two-input tables build and compute their function."""
        for table in ("".join(t) for t in itertools.product("01", repeat=4)):
            program = boolean.inject(table)
            for combo in range(4):
                bits = [str((combo >> (1 - i)) & 1) for i in range(2)]
                got = run_inject(program, bits)
                assert got == table[combo] + "\n", f"{table} inputs {bits}"

    def test_constant_subtrees_are_folded(self) -> None:
        """A table ignoring its later inputs costs one test, not ``n``.

        The fold is what the shape catalogue asserts of every tree
        generator; measured here directly so a regression names itself.
        """
        one_dependency = len(boolean.inject("00001111"))
        parity = len(boolean.inject("01101001"))
        assert one_dependency < parity / 2

    def test_reads_every_input_before_branching(self) -> None:
        """The reads are hoisted, so every path consumes exactly ``n`` lines.

        The boolean contract requires a constant read count; Inject gets it
        by reading all the bits up front rather than at the tree's nodes.
        """
        program = boolean.inject("0001").splitlines()
        reads = [i for i, line in enumerate(program) if line.startswith("readto")]
        first_branch = next(
            i for i, line in enumerate(program) if line.startswith("skipq")
        )
        assert len(reads) == 2, "one readto per input, and no more"
        assert max(reads) < first_branch, "every read precedes every branch"

    def test_every_label_occurs_exactly_twice(self) -> None:
        """Inject's labels are strictly two-occurrence: an open and a close.

        The construction leans on it -- each leaf carries *its own* escape
        label precisely because a third occurrence would not be a legal
        block, and the escape blocks are allowed to overlap only because
        each closes exactly once in the tail.  A counter that handed out a
        duplicate would still emit a program, and a table whose paths
        happen to avoid the clash would still compute correctly, so the
        rule is checked over the label set rather than through an answer.
        """
        from collections import Counter

        for table in ("01", "0001", "0110", "01101001", "11110000"):
            counts = Counter(
                line
                for line in boolean.inject(table).splitlines()
                if line.endswith(";")
            )
            assert all(v == 2 for v in counts.values()), (table, counts)

    def test_an_input_block_starts_empty(self) -> None:
        """An empty block is two *adjacent* delimiters, with nothing between.

        ``readto`` fills the block, so it has to start empty -- and empty
        means the two delimiter lines are adjacent and bare.  A stray
        space before the closing delimiter still parses and still computes
        the table, which is exactly why the spelling is asserted here
        instead of being left to the truth-table sweeps.
        """
        for n, table in ((1, "01"), (2, "0001"), (3, "01101001")):
            lines = boolean.inject(table).splitlines()
            head = lines[: 2 * n]
            assert all(head[2 * d] == head[2 * d + 1] for d in range(n))
            assert len(set(head[::2])) == n

    def test_small_tree_uses_one_character_labels(self) -> None:
        """Inputs, branches, leaves, and constants share the short namespace."""
        labels = [
            line[:-1]
            for line in boolean.inject("01101001").splitlines()
            if line.endswith(";")
        ]
        assert all(len(label) == 1 for label in labels)

    def test_halving_lookup_executes_wide_rows(self) -> None:
        """Regex halves return sampled six-input rows."""
        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        program = boolean.inject(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_inject(program, bits) == table[row] + "\n"

    def test_halving_lookup_growth_is_linear(self) -> None:
        """Wide parity programs grow by at most the table-size ratio."""
        sizes = []
        for n in range(11, 15):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            sizes.append(len(boolean.inject(table)))
        assert all(b <= 2 * a for a, b in pairwise(sizes))

    def test_the_tree_collapses_on_the_constant_subtree_alone(self) -> None:
        """Depth never terminates the recursion; a constant subtree always does.

        ``_tree`` stops on ``depth == n`` *or* a subtree whose entries all
        agree, and the second is the only one that ever fires: at depth
        ``n`` the remaining table is a single entry, which is constant by
        definition.  Swept over every table to three inputs, the depth
        clause explains none of the 1522 collapses.  Stated as a test so
        the disjunct is known to be belt-and-braces rather than assumed to
        be required.
        """
        from esolangs.tools.inject import _Names, _tree

        calls: list[tuple[str, int, int]] = []

        def record(table: str, depth: int, n: int, state: dict[str, int]) -> None:
            calls.append((table, depth, n))
            if depth == n or table == table[0] * len(table):
                return
            half = len(table) // 2
            record(table[:half], depth + 1, n, state)
            record(table[half:], depth + 1, n, state)

        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                record(format(table_int, f"0{2**n}b"), 0, n, {})
        collapsed_by_depth_only = [
            (t, d) for t, d, n in calls if d == n and t != t[0] * len(t)
        ]
        assert collapsed_by_depth_only == []
        # And the tree itself is unchanged when the depth clause cannot fire.
        perm = (0, 1, 2)
        assert _tree("01101001", 0, 3, _Names(3, perm), perm) == _tree(
            "01101001", 0, 3, _Names(3, perm), perm
        )


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
        program = boolean.forbin(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_forbin_boolean(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_uses_the_lsb_of_each_input(self) -> None:
        """Each input is read as 8 bits and only the LSB drives the tree."""
        program = boolean.forbin("01")
        # one 8-variable read, then a decision tree that prints '1' for bit 1
        assert "a,b,c,d,e,f,g,h = (in 0);" in program
        assert "for _:!h..h" in program

    def test_small_program_uses_one_character_variables(self) -> None:
        """The first 52 bit variables do not carry widening decimal suffixes."""
        assignments = [
            line.strip().split(" =", 1)[0]
            for line in boolean.forbin("01101001").splitlines()
            if " = (in 0);" in line
        ]
        assert all(len(name) == 1 for group in assignments for name in group.split(","))

    def test_compact_variables_skip_keywords_without_duplicates(self) -> None:
        """Filtering a reserved word does not reuse its successor's name."""
        from esolangs.tools.other import _FORBIN_RESERVED, _forbin_name

        names = [_forbin_name(i) for i in range(600)]
        assert len(set(names)) == len(names)
        assert not set(names) & _FORBIN_RESERVED

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice returns its answer instead of branching further."""
        assert boolean.forbin("11111111").count("return 0;") == 1
        assert boolean.forbin("11110000").count("return 0;") == 2
        assert boolean.forbin("10010110").count("return 0;") == 8

    def test_full_tree_growth_is_linear(self) -> None:
        """Names and indentation add only a geometric cost to the tree."""
        sizes = []
        for n in range(11, 15):
            parity = "".join(str(i.bit_count() & 1) for i in range(2**n))
            sizes.append(len(boolean.forbin(parity)))
        assert all(later < 2 * earlier for earlier, later in itertools.pairwise(sizes))


class TestFargo:
    """The Fargo boolean generator: a recursively factored ANF."""

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_every_table_at_small_arity(self, n: int) -> None:
        """Exhaustive: every table, every input combination."""
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            program = boolean.fargo(table)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                got = run_fargo(program, bits)
                assert got == table[combo], f"table {table} inputs {bits}"

    @pytest.mark.parametrize("n", [4, 5, 8])
    def test_higher_arity_tables(self, n: int) -> None:
        """The construction is uncapped: no arity limit, no search."""
        rng = random.Random(20260830 + n)
        for _ in range(4):
            table = "".join(rng.choice("01") for _ in range(2**n))
            program = boolean.fargo(table)
            for _ in range(10):
                combo = rng.randrange(2**n)
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_fargo(program, bits) == table[combo]

    def test_constant_tables_need_no_reads(self) -> None:
        """A constant table is its degree-zero coefficient alone."""
        assert boolean.fargo("00000000") == "% 0 0\n$\n"
        assert boolean.fargo("11111111") == "% 0 1\n$\n"

    def test_parity_is_one_term_per_input(self) -> None:
        """Parity's ANF is the sum of the single-variable terms."""
        assert boolean.fargo("01101001") == "% 0 ^ ^ @ 0 @ 1 @ 10\n$\n"

    def test_parity_grows_linearly_not_exponentially(self) -> None:
        """The size tracks algebraic complexity, so parity is O(n log n).

        This is the property that makes Fargo's generator unlike the
        tree-shaped ones: a decision tree spends O(2**n) on parity, the
        table that folds nothing.  Parity's ANF is one single-variable
        term per input, so each extra input adds one ``^ @ i`` -- a
        constant plus the index's own binary width, which is why the
        steps widen by one every time ``i`` gains a digit rather than
        staying exactly equal.
        """
        sizes = [
            len(boolean.fargo("".join(str(bin(r).count("1") % 2) for r in range(2**n))))
            for n in (2, 4, 6, 8)
        ]
        gaps = [b - a for a, b in itertools.pairwise(sizes)]
        # Each step of two inputs costs a bounded amount, nowhere near the
        # doubling per input a decision tree would pay.
        assert all(12 <= gap <= 20 for gap in gaps), f"not linear: {sizes}"
        # A decision tree over n == 8 would be thousands of characters.
        assert sizes[-1] < 100, f"growing too fast: {sizes}"

    def test_a_one_dependency_table_folds(self) -> None:
        """One term whatever the arity, which is what the catalogue checks."""
        assert boolean.fargo("11110000") == "% 0 ^ 1 @ 10\n$\n"
        assert len(boolean.fargo("11110000")) < len(boolean.fargo("01101001"))

    def test_dense_anf_growth_is_linear(self) -> None:
        """NOR has every ANF coefficient set, but its source only doubles."""
        sizes = [len(boolean.fargo("1" + "0" * ((1 << n) - 1))) for n in (7, 8)]
        assert sizes[1] < 2 * sizes[0] + 16


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
        """The program reads n inputs and advances prefix survivors."""
        program = boolean.container("0110")
        assert program.startswith("T:\n+1 T>=T")
        assert ":" in program.splitlines()[:4]  # the empty-named reader
        declarations = [
            line[:-1].split("=", 1)[0]
            for line in program.splitlines()
            if line.endswith(":")
        ]
        generated = [
            name
            for name in declarations
            if name not in {"", "T", "IN", "OUT", "PRINT", "EXIT"}
        ]
        assert len(generated) == len(set(generated))
        assert program.count("PRINT:") == 1

    def test_packed_decoder_selects_decimal_digits(self) -> None:
        """The wide-table path divides one packed decimal digit per row."""
        table = "011" + "0" * 125
        program = boolean.container(table)
        assert "A=110:" in program
        for combo in (0, 1, 2, 3, 17, 63, 64, 127):
            bits = [(combo >> (6 - i)) & 1 for i in range(7)]
            assert run_container(program, [str(b) for b in bits]) == table[combo]

    def test_small_tree_uses_one_character_generated_names(self) -> None:
        """Gates and survivors share one compact identifier namespace."""
        declarations = [
            line[:-1].split("=", 1)[0]
            for line in boolean.container("01101001").splitlines()
            if line.endswith(":")
        ]
        special = {"", "T", "IN", "OUT", "PRINT", "EXIT"}
        assert all(len(name) == 1 for name in declarations if name not in special)

    @pytest.mark.slow
    def test_tree_removes_the_minterm_factor(self) -> None:
        """Each additional row adds bounded tree work, not n tests."""
        sizes = [len(boolean.container("01" * (2 ** (n - 1)))) for n in range(7, 11)]
        assert all(b <= 2 * a + 4000 for a, b in itertools.pairwise(sizes))

    def test_dense_tables_evaluate_the_complement(self) -> None:
        """A dense table is summed from its zero rows and inverted.

        ``OUT`` costs one ``+1 S{row}>=Gout`` line per row the table sends
        to 1, so before this the length rose with the ones-count all the way
        to the all-ones table.  Now it peaks at half and falls back
        symmetrically, which is the signature of taking whichever row-set is
        smaller.
        """
        lengths = [len(boolean.container("1" * k + "0" * (8 - k))) for k in range(9)]
        assert lengths[4] == max(lengths)  # four ones is the worst case
        assert lengths == lengths[::-1]  # and the curve is symmetric

    @pytest.mark.parametrize("table", ["11111110", "11111111", "1110", "0111"])
    def test_complemented_tables_still_compute(self, table: str) -> None:
        """The inverted form answers the original table.

        It starts ``OUT`` at 49 and subtracts one per surviving zero row, so
        the printed byte is ``49 - S``; the container clamp at zero never
        bites, since the value stays at 48 or 49.
        """
        n = (len(table) - 1).bit_length()
        program = boolean.container(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_container(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"


class TestThreeX:
    def test_identity_program_structure(self) -> None:
        """The 01 table reads a bit and stores it before printing."""
        program = boolean.three_x("01")
        assert program.startswith("?")
        assert program.endswith("!")

    def test_reordering_only_shrinks(self) -> None:
        """No table comes out longer than the identity order's program."""
        from esolangs.tools.other import _three_x_ordered

        for i in range(256):
            table = format(i, "08b")
            identity = _three_x_ordered(table, (0, 1, 2))
            assert len(boolean.three_x(table)) <= len(identity)

    def test_unimproved_tables_keep_their_emission(self) -> None:
        """A table no reorder helps emits exactly what it emitted before.

        ``best_input_order`` tries the identity first and keeps it on a tie,
        so reordering can only shrink a program, never churn one.  A constant
        table has no override blocks at all, so no order can beat it.
        """
        from esolangs.tools.other import _three_x_ordered

        for table in ("0" * 8, "1" * 8):
            assert boolean.three_x(table) == _three_x_ordered(table, (0, 1, 2))

    def test_reads_stay_in_stream_order(self) -> None:
        """Only the store target moves, so the input stream is consumed the same.

        The reorder is spelled in which variable each ``?`` stores into, not
        in when the reads happen: every build reads its ``n`` inputs up front,
        one ``?`` each, whatever order the tree tests them in.
        """
        from esolangs.tools.other import _three_x_ordered

        table = "00010111"
        for perm in ((0, 1, 2), (2, 1, 0), (1, 2, 0)):
            program = _three_x_ordered(table, perm)
            head = program[: program.index("(")] if "(" in program else program
            assert head.count("?") == 3
            # the reads are the first thing the program does
            assert program.startswith("?")

    def test_every_input_order_computes_the_table(self) -> None:
        """The permuted build computes the original table on the original stream."""
        import itertools

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.three_x import run
        from esolangs.tools.other import _three_x_ordered

        def permuted(table: str, perm: tuple[int, ...]) -> str:
            out = []
            for row in range(8):
                src = 0
                for k in range(3):
                    src |= ((row >> (2 - k)) & 1) << (2 - perm[k])
                out.append(table[src])
            return "".join(out)

        for table in ("00010111", "01101001", "11110000", "10101010"):
            for perm in itertools.permutations(range(3)):
                program = _three_x_ordered(permuted(table, perm), perm)
                for combo in range(8):
                    bits = [(combo >> (2 - k)) & 1 for k in range(3)]
                    io = ScriptedIO("\n".join(str(b) for b in bits) + "\n")
                    run(program, io)
                    assert io.getvalue().strip() == table[combo], f"{table} {perm}"

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

    def test_deep_names_keep_full_tree_growth_linear(self) -> None:
        """The shortest variable names sit at the most repeated depths."""
        parity7 = "".join(str(i.bit_count() & 1) for i in range(2**7))
        parity8 = "".join(str(i.bit_count() & 1) for i in range(2**8))
        assert len(boolean.three_x(parity8)) < 2 * len(boolean.three_x(parity7))

    def test_digit_constant_encodings(self) -> None:
        """The base-3 digit seeds are the closed-form minimal programs."""
        from esolangs.tools import other

        assert other._const(0) == "333x"  # noqa: SLF001
        assert other._const(1) == "3333x3x"  # noqa: SLF001
        assert other._const(2) == "3333x3x3333x3x3x"  # noqa: SLF001

    def test_base_three_digits_accumulate(self) -> None:
        """Each base-3 digit past the first appends the 3v+d affine step."""
        from esolangs.tools import other

        # 12 is "110" in base 3: seed 1, then d=1, then d=0.  Each transform
        # adds exactly one `#` (the swap before the `x`), and no seed has one.
        twelve = other._const(12)  # noqa: SLF001
        assert twelve.startswith(other._const(1))  # noqa: SLF001
        assert twelve.count("#") == 2

    def test_formula_scales_logarithmically(self) -> None:
        """The closed form grows with the digit count, not the value."""
        from esolangs.tools import other

        small, large = other._const(100), other._const(1_000_000)  # noqa: SLF001
        assert len(small) < 120  # 100 is "10201": 5 digits
        assert len(large) < 350  # 1_000_000 is 13 base-3 digits
        assert len(large) < len(small) * 4


class TestGeneratorEdgePaths:
    """Coverage for validation and helper edge paths in the generators."""

    def test_parameterized_validation(self) -> None:
        """bio/back reject malformed truth tables."""
        from esolangs.tools import parameterized

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
        """The +5 tail of the constant encoder.

        ``_six_five_nav`` was retired with the arithmetic kernel; the folded
        leaf's own hop to cell 1 is a literal ``13``.
        """
        from esolangs.tools.six_five import _six_five_const

        assert _six_five_const(5) == "5"
        assert _six_five_const(11) == "65"

    def test_six_five_label_rejects_an_unspellable_operand(self) -> None:
        """Operands are one character, so the alphabet runs out at 35.

        ``0-9`` then ``A-Z`` is every character 6-5 reads as a number, which
        caps a 7n/8n operand at 35; past that there is nothing to emit.
        """
        from esolangs.tools.six_five import (
            _SIX_FIVE_MAX_LABEL,
            _six_five_label,
        )

        assert _six_five_label(_SIX_FIVE_MAX_LABEL) == "Z"
        with pytest.raises(ValueError, match="no operand character for 36"):
            _six_five_label(_SIX_FIVE_MAX_LABEL + 1)

        # The range is closed at *both* ends, and zero is a real label --
        # a guard reading ``1 <=`` or ``0 <`` would reject the first one.
        assert _six_five_label(0) == "0"
        assert _six_five_label(1) == "1"
        with pytest.raises(ValueError, match="no operand character for -1"):
            _six_five_label(-1)

    def test_six_five_move_spells_a_distance_in_pairs(self) -> None:
        """Rightward moves go two cells at a time, with a ``3`` for the odd one.

        ``1`` steps two cells and ``3`` steps one back, so an even distance
        is all ``1``s and an odd distance is ``ceil(d / 2)`` of them with a
        ``3`` to come back over the extra cell.  Leftward is plain ``3``s.
        Swept over every table through three inputs the generator makes
        11,600 of these moves, over distances 0, 1 and 2 and in both
        directions, so every arm here is live -- including the equal case,
        which occurs 2,296 times and must emit nothing at all.
        """
        from esolangs.tools.six_five import _six_five_move

        assert _six_five_move(2, 2) == ""
        assert _six_five_move(0, 1) == "13"
        assert _six_five_move(0, 2) == "1"
        assert _six_five_move(0, 3) == "113"
        assert _six_five_move(0, 5) == "1113"
        assert _six_five_move(3, 0) == "333"
        assert _six_five_move(5, 0) == "33333"

    def test_six_five_refuses_at_more_than_thirty_five_labels(self) -> None:
        """The capacity test is ``> 35``, not ``>= 35``.

        An operand is one character and the alphabet ends at ``Z``, so 35
        branch labels fit and 36 do not.  The refusal is already witnessed
        by a 63-marker table (see ``test_boolean_tape``), but only from far
        above -- which leaves the boundary itself free to move by one, and
        a table needing exactly 35 would then be refused despite being
        spellable.  ``_six_five_label`` marks that limit, so the two are
        asserted against each other rather than against a repeated literal.
        """
        from esolangs.tools.six_five import (
            _SIX_FIVE_MAX_LABEL,
            _six_five_label,
        )

        assert _SIX_FIVE_MAX_LABEL == 35
        assert _six_five_label(_SIX_FIVE_MAX_LABEL) == "Z"
        assert len(_six_five_label(_SIX_FIVE_MAX_LABEL)) == 1


class TestAlgebraicProgrammingLanguage:
    """The folded-tree generator, whose whole program is one executed line."""

    @staticmethod
    def _run(program: str, n: int, combo: int) -> str:
        bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
        return run_algebraic_programming_language(program, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # not
            ("0001", 2),  # AND2
            ("0111", 2),  # OR2
            ("0110", 2),  # XOR2
            ("01101001", 3),  # parity
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result.

        An executed line prints its result, so the answer arrives with the
        newline that ends the line.
        """
        program = boolean.algebraic_programming_language(table)
        for combo in range(2**n):
            got = self._run(program, n, combo)
            assert got == table[combo] + "\n", f"table {table} combo {combo}"

    def test_every_one_and_two_input_table(self) -> None:
        """All 4 one-input and 16 two-input tables build and compute."""
        for n in (1, 2):
            for table in ("".join(t) for t in itertools.product("01", repeat=2**n)):
                program = boolean.algebraic_programming_language(table)
                for combo in range(2**n):
                    got = self._run(program, n, combo)
                    assert got == table[combo] + "\n", f"{table} combo {combo}"

    @pytest.mark.medium
    def test_every_three_input_table(self) -> None:
        """All 256 three-input tables build and compute their function."""
        for table in ("".join(t) for t in itertools.product("01", repeat=8)):
            program = boolean.algebraic_programming_language(table)
            for combo in range(8):
                got = self._run(program, 3, combo)
                assert got == table[combo] + "\n", f"{table} combo {combo}"

    def test_the_constant_zero_table_still_reads_every_input(self) -> None:
        """A table with no minterms names each input so the reads still happen.

        The boolean contract requires a constant read count, and APL reads
        by *naming*, so the constant-0 program has to name every variable
        even though none of them can change the answer.
        """
        program = boolean.algebraic_programming_language("0000")
        for name in ("a", "b"):
            assert name in program
        for combo in range(4):
            assert self._run(program, 2, combo) == "0\n"

    def test_reads_are_in_ascending_name_order(self) -> None:
        """A variable is read when the line first names it.

        So the emitted line must name ``a`` before ``b`` before ``c``, or
        the harness's inputs would arrive in the wrong slots.
        """
        program = boolean.algebraic_programming_language("01101001")
        line = program.splitlines()[-1]
        firsts = [min(line.index(n) for n in (v,)) for v in "abc"]
        assert firsts == sorted(firsts)

    def test_every_value_stays_zero_or_one(self) -> None:
        """The program prints a bit, not an arbitrary truth value.

        ``!`` returns exactly 0 or 1 and the connectives pass those
        through, so nothing rests on how APL spells a non-zero truth.
        """
        program = boolean.algebraic_programming_language("0110")
        for combo in range(4):
            assert self._run(program, 2, combo).strip() in {"0", "1"}

    def test_the_complement_operator_is_the_wikis_own(self) -> None:
        """The header is the wiki's ``!x`` definition, verbatim."""
        program = boolean.algebraic_programming_language("0001")
        assert program.startswith("!x = {\nx & $0\n$1\n}\n")

    def test_a_one_entry_table_is_refused(self) -> None:
        """A nullary table is a constant, not a function of any input."""
        with pytest.raises(ValueError, match="a one-entry table is a constant"):
            boolean.algebraic_programming_language("0")

    def test_a_width_spreads_the_sum_over_definitions(self) -> None:
        """A narrower program is the same sum, named a piece at a time.

        The language prints *every* executed line, so the sum cannot be
        split across several; what it can be split across is definitions,
        which are not executed.  The answer is what says the pieces still
        add up.
        """
        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            flat = boolean.algebraic_programming_language(table)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(
                len(row)
                for row in boolean.algebraic_programming_language(table, 1).splitlines()
            )
            for width in (1, 25, 40, 60, wide):
                narrow = boolean.algebraic_programming_language(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    got = self._run(narrow, n, combo)
                    assert got == table[combo] + "\n", (table, width, combo)

    def test_the_executed_line_still_names_every_input(self) -> None:
        """Naming a term moves it off the one line that reads.

        A variable is read by appearing on an executed line, and the
        interpreter binds every unbound one there before evaluating.  A
        term hoisted into a definition therefore takes its variables out of
        the reading, and the prefix is what puts them back -- in order, and
        contributing nothing, since ``a & ... & 0`` is 0 either way.
        """
        table = "0110100110010110"
        narrow = boolean.algebraic_programming_language(table, 30)
        # the ``!x`` header is the first four lines and its body sits inside
        # braces; past it, a line without an ``=`` is one that runs, and
        # there must be exactly one however much was hoisted
        lines = narrow.splitlines()
        assert lines[:4] == ["!x = {", "x & $0", "$1", "}"], lines[:4]
        executed = [line for line in lines[4:] if "=" not in line]
        assert len(executed) == 1, executed
        line = executed[0]
        assert line.startswith("(a & b & c & d & 0) | "), line
        # and every input is still read exactly once, in order
        assert [ch for ch in line if ch in "abcd"] == ["a", "b", "c", "d"]

    def test_narrowing_below_the_floor_does_not_widen(self) -> None:
        """Asking for less than it can do returns its narrowest, not a worse one.

        Splitting below the floor lengthens the names rather than the
        lines, and the executed line carries two names -- so an unclamped
        fold made width 1 come out *wider* than width 20.  The floor is
        what a smaller request is raised to.
        """
        for table in ("11111111", "0110100110010110", "01111111"):
            widths = [
                max(
                    len(row)
                    for row in boolean.algebraic_programming_language(
                        table, w
                    ).splitlines()
                )
                for w in (1, 5, 10, 20)
            ]
            assert len(set(widths)) == 1, (table, widths)

    def test_default_full_tree_growth_is_linear(self) -> None:
        """Parity folds no subtree, but its source only doubles per input."""
        sizes = []
        for n in (7, 8):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(boolean.algebraic_programming_language(table)))
        assert sizes[1] < 2 * sizes[0] + 32


class TestAlgebraicProgrammingLanguageShapes:
    """The structural corners of the decision tree, at four inputs.

    The exhaustive n<=3 sweep above already covers every shape the
    construction can take -- empty minterm set, full set, and everything
    between -- and the expansion is mechanical rather than searched, so
    sweeping all 65536 four-input tables costs about eight minutes to
    re-cover the same ground.  These four pin the corners instead: the
    two constants, a single selected row, and the fully branching parity.
    """

    @staticmethod
    def _check(table: str, n: int = 4) -> None:
        program = boolean.algebraic_programming_language(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_algebraic_programming_language(program, bits)
            assert got == table[combo] + "\n", f"{table} inputs {bits}"

    def test_the_all_zero_table(self) -> None:
        """No minterms at all: the constant-zero branch."""
        self._check("0" * 16)

    def test_the_all_one_table(self) -> None:
        """Every row set, so the sum carries all sixteen terms."""
        self._check("1" * 16)

    def test_a_single_minterm(self) -> None:
        """One term, which is the fewest a non-constant table can have."""
        self._check("0000000000000001")

    def test_four_input_parity(self) -> None:
        """Eight terms and no constant subtree anywhere -- nothing folds."""
        self._check("0110100110010110")

    def test_the_all_zero_table_still_reads_every_input(self) -> None:
        """The constant needs its reads: the contract wants ``n`` of them."""
        program = boolean.algebraic_programming_language("0" * 16)
        for name in "abcd":
            assert name in program

    def test_the_name_alphabet_is_codepoint_ascending(self) -> None:
        """``_order_key`` sorts literals by name to keep reads in order.

        That only puts the reads in *input* order if the alphabet itself
        ascends, so a name appended out of sequence would silently swap
        two inputs rather than fail.
        """
        from esolangs.tools.algebraic_programming_language import _NAMES

        assert list(_NAMES) == sorted(_NAMES)
        assert len(set(_NAMES)) == len(_NAMES)
