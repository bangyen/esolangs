"""The tape-family generators whose tests are short.

The longer suites have files of their own: test_boolean_circlefuck,
test_boolean_six_five, test_boolean_slow_acv_mammalian and
test_boolean_streetcode_gen.
"""

import contextlib
import sys
from itertools import pairwise

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_bf,
    run_bit_tilde,
    run_brainif,
    run_dimensional,
    run_factor,
    run_jaune,
    run_painfuck,
    run_rotfuck,
    run_sbleq,
    run_suffolk,
    run_three_d_brainfuck,
)


def _leaves(table: str) -> int:
    """How many leaves a tree that folds constant subtrees spends on ``table``.

    One per maximal constant slice: the walk stops as soon as the rows it
    covers agree, so this is ``2**n`` only when no slice above a single row
    is constant.
    """
    if len(set(table)) == 1:
        return 1
    half = len(table) // 2
    return _leaves(table[:half]) + _leaves(table[half:])


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

    def test_every_move_names_its_dimension(self) -> None:
        """A bare >/< would take its dimension from the cell's value.

        The generator gives each input its own dimension, so the digits
        vary; what has to hold is that no move is left bare.
        """
        program = boolean.dimensional("0110")
        for index, char in enumerate(program):
            if char in "><":
                assert program[index + 1 :][:1].isdigit(), f"bare move at {index}"

    def test_scales_beyond_the_old_reference_cap(self) -> None:
        """The v3.0 interpreter's unbounded cells lift the old n <= 12 cap."""
        program = boolean.dimensional("0" * 4095 + "1")
        got = run_dimensional(program, ["1"] * 12)
        assert got == "1"


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
        assert len(boolean.dimensional_tree(xor6)) < 10_000

    def test_dimensional_is_the_tree(self) -> None:
        """dimensional is the tree, sparse or dense.

        A survivor evaluator used to sit beside it, chosen when it came out
        shorter.  Folding constant subtrees put the tree ahead on every
        table at n <= 4, so the survivor was unreachable and was removed.
        """
        sparse = "0" * 15 + "1"  # AND4
        assert boolean.dimensional(sparse) == boolean.dimensional_tree(sparse)
        xor = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        assert boolean.dimensional(xor) == boolean.dimensional_tree(xor)


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

    def test_bf_is_the_tree(self) -> None:
        """bf is the folded tree, for constant and sparse tables alike.

        There used to be a minterm construction here and ``bf`` returned
        whichever was shorter.  Folding left the tree ahead on every table
        but the two constant ones -- where it costs about 2.5x, a bounded
        factor on two tables out of 65536 -- so the minterm went away and
        the constant tables go to the tree with everything else.
        """
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        for table in ("0" * 16, "0" * 15 + "1", xor6):  # constant, AND4, dense
            assert boolean.brainfuck(table) == boolean.bf_tree(table)


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
        assert len(boolean.bf_tree(xor6)) < 10_000

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice emits a leaf instead of branching on more bits.

        Both tables have the same number of ones, so the difference is the
        arrangement alone: ``11110000`` is two constant halves and folds to
        one leaf each, while the parity table has no constant subtree above
        a single row and emits the full tree.
        """
        assert len(boolean.bf_tree("11110000")) < len(boolean.bf_tree("10010110"))

    def test_parity_table_is_unfolded(self) -> None:
        """A table with no constant subtree still spends a leaf per row.

        The guard against a fold that fires too eagerly: parity has no
        constant slice above one row, so the tree keeps all ``2**n - 1``
        nodes and every one of the ``2**n`` rows keeps its own leaf.

        Counted through the arm-opening ``[-`` rather than through ``.``:
        leaves no longer print, they record a bit for the single print below
        the tree, so a ``'0'`` leaf emits nothing at all and counting leaves
        directly is not possible.  Every loop in the tree opens by clearing
        what it tested, and each of the 7 nodes opens two -- one for the bit
        and one for the flag -- giving 14; the same table folded to a single
        node (``11110000``) gives 2.
        """
        xor3 = "10010110"
        assert boolean.bf_tree(xor3).count("[-") == 14
        assert boolean.bf_tree("11110000").count("[-") == 2


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


class TestFactor:
    def test_prime_search_is_exact_across_segments(self) -> None:
        """The uncapped encoder uses an arbitrary-precision exact sieve."""
        import sympy

        from esolangs.factor_primes import prime_segments

        segments = prime_segments(40)
        first = next(segments)
        second = next(segments)
        assert first == (2, 42, list(sympy.primerange(2, 42)))
        assert second == (42, 82, list(sympy.primerange(42, 82)))

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

    def test_factors_back_into_a_working_bf_program(self) -> None:
        """The integer's factorization is a brainfuck program for the table.

        This used to assert the stronger ``factor(t) ==
        _factor_encode(brainfuck(t))``, which pinned *which* brainfuck
        program was encoded.  Factor pays a prime per run rather than a
        character per command, so it builds for that objective instead and no
        longer emits brainfuck's shortest program; what has to hold is the
        encoding itself, which is what this decodes and runs.
        """
        import sympy

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainfuck import run as run_bf
        from esolangs.tools.factor import _BF_RESIDUE

        table = "0110"
        n = 2
        command = {residue: char for char, residue in _BF_RESIDUE.items()}
        factors = sorted(sympy.factorint(int(boolean.factor(table))).items())
        code = "".join(command[prime % 11] * power for prime, power in factors)

        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
            run_bf(code, io)
            assert io.getvalue() == table[combo], f"inputs {bits}"

    def test_builds_above_the_greedy_order_cap(self) -> None:
        """Past ``_GREEDY_ORDER_MAX_ARITY`` only the identity order is built.

        The generator scores two input orders by digits and keeps the better;
        above the cap the greedy order is not searched at all, which is a path
        of its own.  AND11 takes it cheaply -- the tree folds to one leaf, so
        this is 1330 digits and a 2ms build rather than parity's 425ms.
        """
        from esolangs.tools.helpers import _GREEDY_ORDER_MAX_ARITY

        n = _GREEDY_ORDER_MAX_ARITY + 1
        table = "0" * (2**n - 1) + "1"
        program = boolean.factor(table)
        assert program.isdigit()
        assert run_factor(program, ["1"] * n) == "1"
        assert run_factor(program, ["0"] * n) == "0"

    def test_sparse_tables_stay_small_at_n_four(self) -> None:
        """Sparse tables (few one-rows) encode a short brainfuck program,
        so they stay well under the digit cap even at n == 4."""
        assert boolean.factor("0" * 16).isdigit()
        assert boolean.factor("1" * 16).isdigit()

    def test_a_table_past_cpythons_own_limit_still_renders(self) -> None:
        """XOR6 encodes to 5343 digits, past CPython's 4300-digit default.

        That default is a DoS guard on quadratic int-to-str conversion, not
        anything Factor says, so it is raised for the render rather than
        reported as a property of the language -- which is what used to cap
        this generator at n=3.

        The table here keeps climbing as the tree gets smaller: XOR4 (6390
        digits) until the print-once leaf took it to 2842, then XOR5 until
        dropping the complement construction took that to 3107.  Both fell
        back under the default, so the check moves up rather than losing the
        raise it exists to exercise.  Folding the ASCII offsets took XOR6
        from 5934 to 5343, which is an O(n) saving against a tree that
        doubles, so it stays clear of the default rather than moving again.
        """
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        program = boolean.factor(xor6)
        assert program.isdigit()
        assert len(program) > sys.get_int_max_str_digits()

    def test_the_render_leaves_the_global_limit_alone(self) -> None:
        """The digit limit is process-global, so it is borrowed, not kept.

        A generator that raised it and walked away would silently disarm
        the guard for everything else in the process.
        """
        before = sys.get_int_max_str_digits()
        boolean.factor(
            "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        )
        assert sys.get_int_max_str_digits() == before

    def test_the_render_works_under_an_unlimited_global(self) -> None:
        """``sys.set_int_max_str_digits(0)`` means unlimited, not zero.

        Read as a ceiling, 0 sent every render over it and then asked for
        a limit below CPython's 640 floor, a ``ValueError`` on every table.
        """
        before = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(0)
        try:
            assert boolean.factor("0110").isdigit()
        finally:
            sys.set_int_max_str_digits(before)

    @pytest.mark.slow
    @pytest.mark.weekly
    def test_total_past_the_retired_digit_budget(self) -> None:
        """No digit budget: the 500000-digit refusal is gone (dense n=13).

        703447 digits, and the interpreter decodes it to the program the
        generator encoded.  That decode is the whole load cost (n=12
        parity's 460824 took 43s), so the rows run on
        the decoded machine -- the object ``_Machine.step`` drives --
        rather than through 8192 re-factorizations; ``weekly`` like the
        other high-arity probes.
        """
        from esolangs.interpreters.tape_based.factor import _parse, decode
        from esolangs.tools.factor import _encode
        from tests.tools.test_boolean_contract import _dense

        n = 13
        table = _dense(n)
        program = boolean.factor(table)
        assert len(program) > 500_000
        code = decode(_parse(program))
        # Re-encoding rather than comparing against brainfuck's program: the
        # construction Factor encodes is its own now, and the contract is the
        # round trip, which holds whatever it builds.  The digit limit guards
        # str -> int too, so it is raised here as the generator raises it for
        # its own render.
        limit = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(len(program) + 1)
        try:
            assert _encode(code) == int(program)
        finally:
            sys.set_int_max_str_digits(limit)
        for row in (0, 1, 2**12, 2**13 - 2, 2**13 - 1):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_bf(code, bits) == table[row], row


class TestSuffolk:
    def test_streaming_fold_scales_linearly(self) -> None:
        """Doubling a dense table stays below twice plus fixed setup."""
        sizes = []
        for n in (8, 9, 10):
            table = "".join(str((i * 73 + i.bit_count()) & 1) for i in range(2**n))
            sizes.append(len(boolean.suffolk(table)))
        assert sizes == [2211, 3224, 5087]
        assert sizes[2] < 2 * sizes[1]

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

    def test_constant_tables_collapse_but_still_read(self) -> None:
        """A constant table skips the minterms but still reads its inputs.

        Dropping the evaluation is the win; the reads are the language's
        interface and have to stay, or the caller's bits are left unread on
        the input stream for whatever runs next.
        """
        for table in ("00", "11"):
            assert boolean.suffolk(table).count(",") == 1  # n == 1

    def test_size_tracks_steps_rather_than_ones(self) -> None:
        """Cost is one op per *step* of a half-table, not per one-row.

        The countdown sweep emits an op only where consecutive rows differ,
        counting the drop off the end of each half, so the ones-count does
        not price a table: the step profile fixes the length exactly, and
        one one and seven ones land in different groups only because their
        steps fall in different halves.  This replaces a pin on the retired
        minterm route, whose cost rose with the evaluated row-set instead.

        **Every table here depends on all three inputs**, which the prefix
        family ``1^k 0^(8-k)`` does not: ``11110000`` ignores two of them,
        so dependency reduction rather than the sweep would be measured.
        """
        tables = (
            "10000000",  # 1 one
            "10010000",  # 2 ones
            "11100000",  # 3 ones
            "11101000",  # 4 ones
            "11111000",  # 5 ones
            "11111001",  # 6 ones
            "11111110",  # 7 ones
        )
        groups: dict[tuple[int, ...], set[int]] = {}
        for table in tables:
            half = len(table) // 2
            profile = tuple(
                sum(a != b for a, b in zip(part, f"{part[1:]}0", strict=True))
                for part in (table[:half], table[half:])
            )
            groups.setdefault(profile, set()).add(len(boolean.suffolk(table)))
        assert sorted(groups) == [(1, 0), (1, 1), (1, 3), (3, 0)]
        assert all(len(sizes) == 1 for sizes in groups.values())  # profile fixes it
        assert min(groups[(1, 0)]) < min(groups[(3, 0)])  # more steps cost more
        assert min(groups[(1, 1)]) < min(groups[(1, 3)])

    @pytest.mark.parametrize(
        "table",
        ["11111110", "1111111111111110", "0111111111111111", "11111100"],
    )
    def test_complemented_tables_still_compute(self, table: str) -> None:
        """The inverted print stage answers the original table, not its flip.

        ``.`` emits ``chr(acc - 1)`` and ``!`` computes
        ``max(0, cell + 1 - acc)``, so the constant the flip cell carries has
        to account for both; preloading it one low prints ``'/'`` instead of
        ``'0'``, which is how an earlier attempt failed.
        """
        n = (len(table) - 1).bit_length()
        program = boolean.suffolk(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_suffolk(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"


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

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_every_small_table(self, n: int) -> None:
        """Execute every table and row through three inputs."""
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            program = boolean.bit_tilde(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert run_bit_tilde(program, [str(b) for b in bits]) == table[combo]

    def test_full_tree_growth_is_linear(self) -> None:
        """Parity folds nothing, but depth-local movement stays linear."""
        sizes = []
        for n in (7, 8):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(boolean.bit_tilde(table)))
        assert sizes[1] < 2 * sizes[0] + 256

    def test_single_read_and_output(self) -> None:
        """One read per input and a single final output."""
        program = boolean.bit_tilde("0110")
        # Nothing but pointer moves before the first read: the reads descend
        # from the top of the input area, so the program opens with a walk.
        assert set(program[: program.index(")")]) <= {">"}
        assert program.count(")") == 2
        assert program.count("(") == 1
        assert program.endswith("(")


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

    def test_reads_every_input_whatever_the_table(self) -> None:
        """Every table consumes exactly ``n`` inputs, folds included.

        This is the cross-cutting contract in
        ``test_boolean_contract.py``, pinned here because that sweep
        cannot see Jaune: it iterates the generators registered in
        ``BY_FUNCTION``, and Jaune is not one of them.  The reads used to
        sit *at* the tree's nodes, so a folded tree skipped them and a
        constant table consumed no input at all -- making the program's
        stream consumption a function of its truth table.  Without this
        test nothing would catch that coming back.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.jaune import run

        n = 3
        for table in ("11111111", "00000000", "11110000", "10101010", "10010110"):
            io = ScriptedIO("0\n" * n)
            with contextlib.suppress(Exception, SystemExit):
                run(boolean.jaune(table), io=io)
            assert io.position() == n, (
                f"{table} consumed {io.position()} inputs, expected {n}"
            )

    def test_unused_inputs_are_clobbered_not_stored(self) -> None:
        """An input no node branches on is read without keeping a cell.

        ``10101010`` depends only on its last input, so the first two
        reads need no cell of their own and the tree navigates a
        one-cell block instead of a three-cell one.
        """
        assert boolean.jaune("10101010").startswith("vvv")
        # every input matters here, so every read keeps its cell
        assert boolean.jaune("10010110").startswith("v>v>v>")

    def test_each_leaf_terminates_without_a_shared_label(self) -> None:
        """Leaves use ``.`` instead of repeating a widening end label."""
        program = boolean.jaune("0110")
        assert program.count(".") == 4
        assert program.endswith("^.")

    def test_spatial_lookup_executes_wide_rows(self) -> None:
        """The travelling counter returns sampled six-input rows."""
        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        program = boolean.jaune(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_jaune(program, bits) == table[row]

    def test_spatial_lookup_growth_is_linear(self) -> None:
        """Wide parity programs grow by at most the table-size ratio."""
        sizes = []
        for n in range(11, 15):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            sizes.append(len(boolean.jaune(table)))
        assert all(b <= 2 * a for a, b in pairwise(sizes))


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
        """Low-address data precedes the root reads and branch."""
        program = boolean.sbleq("0110")
        cells = [int(tok) for tok in program.split()]
        data_base = 9
        code_base = cells[6]
        assert cells[:6] == [0, 0, 6, -1, 0, 0]
        assert cells[7:9] == [0, 0]
        assert cells[data_base : data_base + 4] == [-49, 48, 49, -1]
        assert cells[code_base : code_base + 3] == [
            data_base + 4,
            -2,
            data_base + 6,
        ]
        assert cells[code_base + 6 : code_base + 9] == [
            data_base + 4,
            data_base,
            data_base + 8,
        ]
        code = cells[code_base:]
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
        assert [t for t in triples if t == (0, 0, 3)] == 4 * [(0, 0, 3)]

    def test_only_the_hoisted_route_remains(self) -> None:
        """The former node-read builder is gone, not merely bypassed."""
        import esolangs.tools.tape as module

        assert not hasattr(module, "_sbleq_node_read")

    def test_hoisted_build_reads_every_input_once_up_front(self) -> None:
        """The read block is 2n instructions and precedes every branch."""
        from esolangs.tools.tape import _sbleq_hoisted

        program = _sbleq_hoisted("00010111", (0, 1, 2))
        cells = [int(tok) for tok in program.split()]
        code_base = cells[6]
        code = cells[code_base:]
        triples = [tuple(code[i : i + 3]) for i in range(0, len(code), 3)]
        reads = [t for t in triples[:3] if t[1] == -2]
        assert len(reads) == 3  # one read per input, all before the tree
        assert [t[0] for t in reads] == sorted({t[0] for t in reads})  # input order

    def test_packed_decoder_executes_wide_rows(self) -> None:
        """Rows on both sides of chunk boundaries decode correctly."""
        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        program = boolean.sbleq(table)
        for row in (0, 1, 5, 6, 7, 31, 32, 62, 63):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_sbleq(program, bits) == table[row]

    def test_packed_growth_is_linear(self) -> None:
        """Wide parity tables grow by at most the table-size ratio."""
        sizes = []
        for n in range(11, 15):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            sizes.append(len(boolean.sbleq(table)))
        assert all(b <= 2 * a for a, b in pairwise(sizes))

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
        """An entry trampoline precedes the answer build and input tree."""
        program = boolean.brainif("10")
        assert program.startswith("if 0 goto 4\nif 48 goto")
        assert "if 0 input" in program
        assert program.count("goto 2") == 4

    def test_the_answer_byte_is_built_once(self) -> None:
        """The climb to 48 is paid before the tree, not once per digit.

        Two per-digit output routines cost 48 + 49 increments and dominated
        the program; building the byte ahead of the branch leaves the tree
        deciding only whether to add one, so the count is 48 plus one line
        per ``1`` *leaf*.  Leaves, not rows: a constant slice folds to one
        leaf, so ``11111110`` spends three rather than seven.
        """
        for table, one_leaves in (("10", 1), ("0110", 2), ("11111110", 3)):
            assert boolean.brainif(table).count("increment") == 48 + one_leaves

    def test_one_shared_output_tail(self) -> None:
        """Both answers print from the same two lines."""
        program = boolean.brainif("0110")
        assert program.count("output") == 2

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice stops the branching, though not the reads.

        Reads carry the pointer home, so a leaf spends no moves reaching
        the answer and the fold is not handed back -- which is what an
        earlier layout, with the answer past the inputs, did.
        """
        assert len(boolean.brainif("11111111")) < len(boolean.brainif("11110000"))
        assert len(boolean.brainif("11110000")) < len(boolean.brainif("10010110"))

    def test_spatial_lookup_executes_wide_rows(self) -> None:
        """Fresh scratch cells route sampled six-input rows."""
        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        program = boolean.brainif(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_brainif(program, bits) == table[row]

    def test_spatial_lookup_growth_is_linear(self) -> None:
        """Wide parity programs grow by at most the table-size ratio."""
        sizes = []
        for n in range(8, 12):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            sizes.append(len(boolean.brainif(table)))
        assert all(b <= 2 * a for a, b in pairwise(sizes))


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

    def test_the_rotation_cycle_is_the_documented_one(self) -> None:
        """``+ -> - -> > -> < -> , -> . -> [ -> ] -> +``, and it is a cycle.

        Everything else here is arithmetic on this order: which commands a
        body may use at an offset, which character encodes a phantom ``]``,
        and how far a pad shifts the rest of a block.  A rotation that is
        off by one, or runs backwards, still emits a program -- one whose
        every command means something else.
        """
        from esolangs.tools.rotfuck import _ROTFUCK_CHAIN, _rotfuck_rot

        assert _ROTFUCK_CHAIN == "+-><,.[]"
        for i, char in enumerate(_ROTFUCK_CHAIN):
            forward = _ROTFUCK_CHAIN[(i + 1) % 8]
            assert _rotfuck_rot(char, 1) == forward, char
            assert _rotfuck_rot(forward, -1) == char, char
            assert _rotfuck_rot(char, 8) == char, char
            assert _rotfuck_rot(char, 0) == char, char

    def test_a_body_command_never_shows_as_a_bracket(self) -> None:
        """The allowed set at each offset is exactly the non-bracket rotations.

        A body command at relative offset ``j`` is read as
        ``rot^-j(cmd)`` while the ``[`` seeks its partner, so a command
        that shows as ``[`` or ``]`` there would move the seek's depth
        count and the block would pair with the wrong bracket.  The two
        offsets that matter most are 2 and 3, where only two of the four
        commands survive -- and they exclude *different* ones, which is
        what makes the padding necessary rather than cosmetic.
        """
        from esolangs.tools.rotfuck import _rotfuck_allowed, _rotfuck_rot

        for offset in range(8):
            allowed = _rotfuck_allowed(offset)
            assert allowed == [
                c for c in "+-><" if _rotfuck_rot(c, -offset) not in "[]"
            ], offset
        assert _rotfuck_allowed(2) == [">", "<"]
        assert _rotfuck_allowed(3) == ["+", "<"]
        assert _rotfuck_allowed(4) == ["+", "-"]

    def test_a_neutral_pad_exists_and_is_net_zero_at_every_offset(self) -> None:
        """Padding shifts the offset by two without moving the tape.

        Both characters have to be legal *at their own* offsets, and at
        offsets 2 and 3 exactly one of the four candidate pairs qualifies,
        so the choice is forced there rather than preferred.  The pair is
        also net-neutral by construction -- ``+-`` and ``><`` undo
        themselves -- which is what lets it be inserted anywhere.
        """
        from esolangs.tools.rotfuck import _rotfuck_allowed, _rotfuck_neutral

        for offset in range(8):
            pad = _rotfuck_neutral(offset)
            assert pad in ("+-", "-+", "><", "<>"), offset
            assert set(pad) in ({"+", "-"}, {"<", ">"}), offset
            for i, char in enumerate(pad):
                assert char in _rotfuck_allowed((offset + i) % 8), (offset, char)
        # Forced where only one candidate is legal, so these are the pad.
        assert _rotfuck_neutral(2) == "><"
        assert _rotfuck_neutral(3) == "+-"

    def test_every_body_is_seven_mod_eight_and_offset_legal(self) -> None:
        """The two invariants the block layout rests on, over many bodies.

        A body of length ``L`` with ``L + 1 == 0 (mod 8)`` puts the skip
        path and the body path in the same rotation state after the block,
        which is what lets the blocks be laid end to end.  Every command in
        it must also sit at an offset where it does not read as a bracket.
        Neither is visible in a truth-table check: a body that breaks
        either still runs, it just re-converges in the wrong state.
        """
        from esolangs.tools.rotfuck import _rotfuck_allowed, _rotfuck_body

        for guard in range(6):
            for target in range(6):
                if guard == target:
                    continue
                for op in ("+", "-"):
                    body = _rotfuck_body(guard, target, op)
                    assert (len(body) + 1) % 8 == 0, (guard, target, op)
                    for j, char in enumerate(body):
                        assert char in _rotfuck_allowed(j % 8), (guard, target, j)
                    assert body.count(">") - body.count("<") == 0, (guard, target)
                    assert op in body, (guard, target, op)

    def test_the_program_is_only_command_characters(self) -> None:
        """Nothing but the eight commands is emitted.

        ROTfuck treats a character outside its alphabet as a comment that
        neither executes *nor advances the rotation*, so stray text is
        invisible to any behavioural check -- a program with padding
        between every command computes the same table.  The alphabet is
        therefore asserted directly rather than inferred from the answer.
        """
        for table in ("01", "0110", "11110000", "01101001"):
            assert set(boolean.rotfuck(table)) <= set("+-><,.[]"), table

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("01", 193),
            ("10", 191),
            ("0001", 340),
            ("0110", 371),
            ("11110000", 299),
            ("01101001", 660),
        ],
    )
    def test_the_emitted_length_is_exact(self, table: str, length: int) -> None:
        """The layout is deterministic down to the character.

        Several ways of getting this wrong leave a *correct* program: a
        move loop that emits a redundant ``><`` when the pointer is
        already home, a pad count taken mod 9 rather than mod 8 (which
        adds a whole 8-cycle and so preserves the length invariant), or a
        stray separator the interpreter reads as a comment.  None of them
        changes an answer, and a loose size bound only catches them by
        luck, so the lengths are pinned exactly.

        ``11110000`` also carries dependency reduction: it builds a one-input
        Gray walk, 299 characters against ``01101001``'s 660.
        """
        assert len(boolean.rotfuck(table)) == length
