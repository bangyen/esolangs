"""The tape-family generators whose tests are short.

The longer suites have files of their own: test_boolean_circlefuck,
test_boolean_jaune, test_boolean_sbleq, test_boolean_six_five,
test_boolean_slow_acv_mammalian and test_boolean_streetcode_gen.
"""

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
    run_painfuck,
    run_rotfuck,
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
            ("1111111100000000", 4),
        ],
    )
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.dimensional(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dimensional(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_a_bare_move_is_the_addressing(self) -> None:
        """A bare >/< takes its dimension from the cell, which is the point.

        One per read -- ``d>`` steps along dimension 1 for a one bit and 0
        for a zero -- and one per painted one-cell, whose ``+`` leaves the
        1 the following ``>`` reads.  ``0110`` paints as far as its last
        one at index 2, so that is two reads and one one-cell before it.
        """
        program = boolean.dimensional("0110")
        bare = [
            i
            for i, c in enumerate(program)
            if c in "><" and not program[i + 1 :][:1].isdigit()
        ]
        assert len(bare) == 3, program

    def test_the_table_costs_two_characters_an_entry(self) -> None:
        """One painted cell an entry, whichever bit it is.

        A zero-cell steps with ``>1`` and a one-cell with ``+`` and a bare
        ``>``; both are two characters, so the emitted length does not
        carry the table's contents.
        """
        full = "1" * 64
        one = "0" * 63 + "1"
        assert len(boolean.dimensional(full)) == len(boolean.dimensional(one))
        parity = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.dimensional(parity)) < 10_000

    def test_a_sparse_table_pays_only_for_its_prefix(self) -> None:
        """An unvisited cell already reads 0, so painting stops at the last one."""
        early = "1" + "0" * 15
        late = "0" * 15 + "1"
        assert len(boolean.dimensional(early)) < len(boolean.dimensional(late))

    def test_scales_beyond_the_old_reference_cap(self) -> None:
        """The v3.0 interpreter's unbounded cells lift the old n <= 12 cap."""
        program = boolean.dimensional("0" * 4095 + "1")
        got = run_dimensional(program, ["1"] * 12)
        assert got == "1"


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
    @pytest.mark.medium
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
    @pytest.mark.medium
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
    @pytest.mark.medium
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

    def test_a_constant_zero_side_needs_no_flag(self) -> None:
        """Pin the three-input total: 35,488 characters before, 28,734 after.

        A node whose zero-side is constant adds it up front and keeps only
        the bit's loop, so AND is two nested loops; the run starts on the
        multiplier rather than walking to it.
        """
        assert boolean.three_d_brainfuck("0001").endswith("e[-n[-e+w]s]ne.")
        tables = [f"{value:08b}" for value in range(256)]
        assert sum(len(boolean.three_d_brainfuck(t)) for t in tables) == 28734


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
    @pytest.mark.medium
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
        """XOR7 exceeds CPython's 4300-digit rendering guard.

        Terminal transfers brought XOR6 below it; use the next arity to
        keep exercising the temporary limit increase.
        """
        xor7 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(128))
        program = boolean.factor(xor7)
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
    @pytest.mark.cost_evidence("Factor's dense n=13 render stops beyond 500000 digits")
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
    @pytest.mark.medium
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
    @pytest.mark.medium
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
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bit_tilde(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bit_tilde(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    @pytest.mark.medium
    def test_every_small_table(self, n: int) -> None:
        """Execute every table and row through three inputs."""
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            program = boolean.bit_tilde(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert run_bit_tilde(program, [str(b) for b in bits]) == table[combo]

    def test_full_table_growth_is_linear(self) -> None:
        """Parity folds nothing, but one cell an entry stays linear."""
        sizes = []
        for n in (7, 8):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(boolean.bit_tilde(table)))
        assert sizes[1] < 2 * sizes[0] + 256

    def test_single_read_and_output(self) -> None:
        """One read per input and a single final output."""
        program = boolean.bit_tilde("0110")
        # The prologue paints the table and walks to the top of it, so the
        # opening is moves and flips -- no loop, read or print among them.
        assert set(program[: program.index(")")]) <= {">", "~"}
        assert program.count(")") == 2
        assert program.count("(") == 1
        assert program.endswith("(")


class TestBrainIf:
    """The DAG selector and the retained width-constrained tree/spatial route."""

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
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.brainif(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_brainif(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """An entry trampoline precedes the answer build and input tree."""
        program = boolean.brainif("10", width=1000)
        assert program.startswith("if 0 goto 4\nif 48 goto")
        assert "if 0 input" in program
        # The one leaf, a 0, joins the trampoline line its byte (48) passes.
        assert program.count("goto 2") == 1

    def test_the_answer_byte_is_built_once(self) -> None:
        """The climb to 48 is paid before the tree, not once per digit.

        Two per-digit output routines cost 48 + 49 increments and dominated
        the program; building the byte ahead of the branch leaves the tree
        deciding only whether to add one, so the count is 48 plus one line
        for the ``1`` leaf: every other ``1`` leaf jumps to that one.
        """
        for table in ("10", "0110", "11111110", "01101001"):
            assert boolean.brainif(table, width=1000).count("increment") == 49
        assert boolean.brainif("00000000", width=1000).count("increment") == 48

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
        assert len(boolean.brainif("11111111", width=1000)) < len(
            boolean.brainif("11110000", width=1000)
        )
        assert len(boolean.brainif("11110000", width=1000)) < len(
            boolean.brainif("10010110", width=1000)
        )

    @staticmethod
    def _tests(program: str) -> int:
        """Count branch tests: an ``if 49 goto`` straight after a read."""
        lines = program.splitlines()
        return sum(
            a == "if 0 input" and b.startswith("if 49 goto") for a, b in pairwise(lines)
        )

    @staticmethod
    def _reads(program: str, stdin: str) -> tuple[str, int]:
        """Run ``program`` and return its answer and how many inputs it read."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.brainif import run

        io = ScriptedIO(stdin)
        run(program.splitlines(), io)
        return io.getvalue(), io.reads

    def test_constants_test_nothing(self) -> None:
        """The positive control: a constant reads its inputs and prints."""
        for table in ("0" * 8, "1" * 8, "0" * 32):
            program = boolean.brainif(table, width=1000)
            n = len(table).bit_length() - 1
            assert self._tests(program) == 0
            assert program.count("if 0 input") == n
            for row in range(2**n):
                bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_brainif(program, bits) == table[0]
        assert len(boolean.brainif("0" * 8, width=1000)) == 1015  # 1028 before
        assert (
            len(boolean.brainif("0" * 32, width=1000)) < 1200
        )  # a 2,864-character lookup before

    def test_only_dependent_levels_are_tested(self) -> None:
        """A level whose halves agree is read and stepped past, never tested."""
        assert (
            self._tests(boolean.brainif("00001111", width=1000)) == 1
        )  # the first input
        assert (
            self._tests(boolean.brainif("01010101", width=1000)) == 1
        )  # the last input
        assert (
            self._tests(boolean.brainif("00110011", width=1000)) == 1
        )  # the middle one
        assert (
            self._tests(boolean.brainif("00010011", width=1000)) == 4
        )  # the full tree has 7
        for table in ("00110011", "00010011", "01011010"):
            program = boolean.brainif(table, width=1000)
            for row in range(8):
                bits = "".join(f"{(row >> (2 - i)) & 1}\n" for i in range(3))
                assert self._reads(program, bits) == (table[row], 3)

    def test_equal_spans_share_their_code(self) -> None:
        """Parity has two distinct spans per level, so two tests a level."""
        assert self._tests(boolean.brainif("01101001", width=1000)) == 5
        assert self._tests(boolean.brainif("0110100110010110", width=1000)) == 7

    def test_wide_tables_on_few_inputs_stay_a_tree(self) -> None:
        """Ignored inputs no longer push a table onto the linear lookup."""
        table = "0110" * 16  # six inputs, depending on the last two
        program = boolean.brainif(table, width=1000)
        assert self._tests(program) == 3
        assert len(program) < len(boolean.brainif("0110", width=1000)) + 400
        for row in (0, 1, 2, 3, 21, 42, 63):
            bits = "".join(f"{(row >> (5 - i)) & 1}\n" for i in range(6))
            assert self._reads(program, bits) == (table[row], 6)

    def test_pruning_never_grows_a_table(self) -> None:
        """No table through four inputs is longer than its unpruned tree.

        ``prune=False`` is the previous build less each leaf's dead second
        ``goto``: 364,700 characters over the 256 three-input tables, then
        345,486, and 319,576 with levels skipped and spans shared.
        """
        from esolangs.tools.brainif import _brainif_tree

        for n in (1, 2, 3, 4):
            for i in range(0, 1 << (1 << n), 1 if n < 4 else 257):
                table = format(i, f"0{1 << n}b")
                unpruned = _brainif_tree(table, None, prune=False)
                assert len(boolean.brainif(table)) <= len(unpruned)
        tables = [format(i, "08b") for i in range(256)]
        assert sum(len(boolean.brainif(t)) for t in tables) == 292_492
        assert sum(len(_brainif_tree(t, None, prune=False)) for t in tables) == 345_486

    def test_spatial_lookup_executes_wide_rows(self) -> None:
        """Fresh scratch cells route sampled six-input rows."""
        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        program = boolean.brainif(table, width=1000)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_brainif(program, bits) == table[row]

    def test_spatial_lookup_growth_is_linear(self) -> None:
        """Wide parity programs grow by at most the table-size ratio."""
        sizes = []
        for n in range(8, 12):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            sizes.append(len(boolean.brainif(table, width=1000)))
        assert all(b <= 2 * a for a, b in pairwise(sizes))


class TestRotfuck:
    """The ROTfuck boolean generator.

    ROTfuck rotates the program after every command, so a loop only works if
    its every pass reads the same commands: the generator pins each loop's
    cycle to 0 (mod 8) and reaches its back-jump target through a phantom
    that is never executed.  On that it builds a tape lookup -- the table in
    the even cells, a variable-distance pointer walk over the odd ones.
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
    @pytest.mark.medium
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

    @pytest.mark.parametrize("n", [6, 7, 8])
    def test_a_second_index_digit_still_selects_the_right_entry(self, n: int) -> None:
        """The arity where the index stops fitting in one walk.

        A cell is a byte, so the index is carried six bits at a time: one
        walk per digit, each read only once the walk before it has landed.
        Six inputs still fit in one digit and seven do not, so this brackets
        the boundary -- and it is not a boundary any smaller table can
        reach, which is why the truth-table sweeps above cannot see it.
        """
        table = "".join(str(bin(row).count("1") & 1) for row in range(2**n))
        program = boolean.rotfuck(table)
        for combo in (0, 1, 2**n - 1, 2**n - 2, 2 ** (n - 1), 2 ** (n - 1) - 1):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_rotfuck(program, [str(b) for b in bits])
            assert got == table[combo], f"n={n} inputs {bits}"

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

    def test_a_command_never_shows_as_a_bracket_inside_a_seek(self) -> None:
        """A command's rotation, seen from a seek's, must not be a bracket.

        A seek reads the whole program at one fixed rotation, so a command
        that executes ``d`` steps after that rotation shows there as
        ``rot^-d`` of itself.  Showing as a bracket moves the seek's depth
        count and pairs the loop with the wrong character, which leaves a
        program that still runs and computes something else.  The two
        offsets that matter most are 2 and 3, where only two of the four
        commands survive -- and they exclude *different* ones, which is what
        makes the padding necessary rather than cosmetic.
        """
        from esolangs.tools.rotfuck import _rotfuck_rot, _shows

        for seek in range(8):
            for rot in range(8):
                for cmd in "+-><":
                    assert _shows(cmd, seek, rot) == (
                        _rotfuck_rot(cmd, seek - rot) in "[]"
                    ), (cmd, seek, rot)
        assert [c for c in "+-><" if not _shows(c, 0, 2)] == [">", "<"]
        assert [c for c in "+-><" if not _shows(c, 0, 3)] == ["+", "<"]
        assert [c for c in "+-><" if not _shows(c, 0, 4)] == ["+", "-"]

    def test_every_pad_is_invisible_and_they_are_shortest_first(self) -> None:
        """Padding shifts the rotation without shifting anything else.

        A pad is what moves a command off a rotation where it would read as
        a bracket, so it has to leave every cell and the pointer where it
        found them -- and never step left of where it started, because
        ``<`` clamps at cell zero and a pad that reached past the caller's
        cell would not be neutral there.  Length runs shortest first, since
        padding is pure cost.
        """
        from esolangs.tools.rotfuck import _PADS

        assert _PADS[0] in ("+-", "-+", "><")
        assert list(_PADS) == sorted(_PADS, key=len)
        for pad in _PADS:
            cells: dict[int, int] = {}
            at = low = 0
            for char in pad:
                assert char in "+-><", pad
                at += (char == ">") - (char == "<")
                low = min(low, at)
                cells[at] = cells.get(at, 0) + (char == "+") - (char == "-")
            assert at == 0, pad
            assert low == 0, pad
            assert not any(cells.values()), pad

    @pytest.mark.parametrize("trips", range(7))
    def test_a_loop_leaves_the_rotation_where_it_found_it(self, trips: int) -> None:
        """The invariant every loop rests on, checked by running one.

        A loop's trip count is data, so the rotation it exits at must not
        depend on it -- otherwise every command after the loop means
        something else for a different input.  The generator gets that by
        padding each loop's cycle to 0 (mod 8).  Here a drain loop runs
        ``trips`` times and the *same* trailing ``+`` run and ``.`` follow
        it: if the exit rotation moved with the trip count, that tail would
        not still be a print of the right character.
        """
        from esolangs.tools.helpers import _ASCII_ZERO
        from esolangs.tools.rotfuck import _Builder

        out = _Builder()
        out.travel(2)
        out.emit("+" * trips)
        out.travel(4)
        out.drain("-<<+>>>>++")
        out.travel(0)
        out.emit("+" * _ASCII_ZERO)
        out.emit(".")
        assert run_rotfuck(out.text(), []) == str(trips)

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
            ("01", 224),
            ("10", 224),
            ("0001", 390),
            ("0110", 391),
            ("11110000", 228),
            ("01101001", 571),
        ],
    )
    def test_the_emitted_length_is_exact(self, table: str, length: int) -> None:
        """The layout is deterministic down to the character.

        Several ways of getting this wrong leave a *correct* program: a
        pad taken at four characters where two would have hidden, a cycle
        padded to 8 (mod 8) rather than 0 (which is the same rotation and
        so still runs), or a travel that walks the pointer home when it is
        already there.  None of them changes an answer, and a loose size
        bound only catches them by luck, so the lengths are pinned.

        ``11110000`` also carries dependency reduction: it lays out a
        two-entry table, 228 characters against ``01101001``'s 571.
        """
        assert len(boolean.rotfuck(table)) == length


@pytest.mark.parametrize("width", [1, 11, 12, 13, 40, 80])
def test_brainif_zero_landing_executes_all_small_tables(width: int) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.brainif import run

    for n in range(1, 4):
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            program = boolean.brainif(table, width)
            for row, expected in enumerate(table):
                bits = list(format(row, f"0{n}b"))
                io = ScriptedIO("\n".join([*bits, "sentinel"]))
                run(program.splitlines(), io)
                assert io.getvalue() == expected
                assert io.input_str() == "sentinel"


def test_brainif_zero_landing_output_floor_and_corpus_size() -> None:
    program = boolean.brainif("0110", 1)
    assert max(map(len, program.splitlines())) == 12
    assert len(program) == 818
    assert (
        sum(len(boolean.brainif(format(value, "08b"), 1)) for value in range(256))
        == 225958
    )
    for row, expected in enumerate("0110"):
        assert run_brainif(program, list(format(row, "02b"))) == expected


@pytest.mark.parametrize("width", [1, 12, 80])
def test_brainif_zero_landing_public_and_larger_samples(width: int) -> None:
    import esolangs

    for n in range(2, 7):
        table = "".join(str((row * 73 + row // 3) % 2) for row in range(2**n))
        program = esolangs.generate("BrainIf", table, width)
        for row in [0, 1, 2**n // 3, 2**n - 1]:
            stdin = "\n".join(format(row, f"0{n}b")) + "\n"
            assert esolangs.run("BrainIf", program, stdin) == table[row]
            assert esolangs.run("BrainIf", str(program), stdin) == table[row]


def test_brainif_unpruned_large_tree_uses_spatial_fallback() -> None:
    from esolangs.tools.brainif import _brainif_tree

    table = "".join(str(row.bit_count() % 2) for row in range(32))
    program = _brainif_tree(table, 1, prune=False)
    for row in [0, 1, 7, 13, 31]:
        assert run_brainif(program, list(format(row, "05b"))) == table[row]


def test_rotfuck_loop_does_not_swallow_an_invariant_failure() -> None:
    from esolangs.tools.rotfuck import _Builder

    def broken() -> None:
        raise AssertionError("broken body invariant")

    with pytest.raises(AssertionError, match="broken body invariant"):
        _Builder().loop(broken, lambda: None)
