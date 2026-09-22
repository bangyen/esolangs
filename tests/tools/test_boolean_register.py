"""Unit tests for the register-based boolean generators.

Covers the generators in :mod:`esolangs.tools.register`: Decleq,
AddSubJump, Collatz Multiverse, Sophie, Dig, Qoibl, Polynomial, and Point
Break.
"""

import importlib
import random
from itertools import pairwise

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.tools.helpers import _ASCII_ONE, _ASCII_ZERO
from esolangs.tools.register import (
    _DIG_BRANCH,
    _DIG_RETURN,
    _DIG_STRIDE,
    _polynomial_dag,
    _polynomial_states,
)
from tests.tools.boolean_oracles import (
    _polynomial_tree,
    _sophie_dag,
    _sophie_tree,
)
from tests.tools.boolean_runners import (
    run_addsubjump,
    run_addsubjump_from,
    run_collatz_multiverse,
    run_decleq,
    run_dig,
    run_polynomial,
    run_polynomial_from,
    run_qoibl,
    run_sophie,
    run_sophie_from,
)
from tests.tools.test_boolean_contract import _parity


class TestAddSubJump:
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
        program = boolean.addsubjump(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_addsubjump(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_branch_normalizes_ascii_bits(self) -> None:
        """Each ASCII input contributes its zero-or-one value to the index."""
        program = boolean.addsubjump("0110")
        assert "48" in program
        assert run_addsubjump(program, ["0", "1"]) == "1"
        assert run_addsubjump(program, ["1", "0"]) == "1"

    @pytest.mark.medium
    def test_all_three_input_tables(self) -> None:
        """The packed decoder executes every three-input function."""
        for value in range(256):
            table = format(value, "08b")
            program = boolean.addsubjump(table)
            for row in range(8):
                bits = [str((row >> shift) & 1) for shift in (2, 1, 0)]
                assert run_addsubjump(program, bits) == table[row]

    def test_every_path_reads_each_input_once(self) -> None:
        """A run consumes exactly ``n`` inputs, whatever the table.

        With the reads hoisted this is structural rather than something a
        folded leaf has to drain, but it is the contract callers depend on:
        several programs fed from one stream desync if a path leaves bits
        unconsumed.  An exhaustible iterator proves both directions -- an
        over-read raises, a leftover proves an under-read.
        """
        for table, n in (("01101001", 3), ("11111111", 3), ("10101010", 3)):
            program = boolean.addsubjump(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                feed = iter([str(b) for b in bits])
                got = run_addsubjump_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                assert not list(feed), f"{table} inputs {bits} left input unread"

    def test_packed_growth_is_linear(self) -> None:
        """Wide parity tables grow by at most the table-size ratio."""
        sizes = [
            len(
                boolean.addsubjump(
                    "".join(str(row.bit_count() & 1) for row in range(2**n))
                )
            )
            for n in range(11, 15)
        ]
        assert all(b <= 2 * a for a, b in pairwise(sizes))


class TestQoibl:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("01100110", 3),  # XOR of the last two: the root's halves agree
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.qoibl(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_qoibl(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_structure(self) -> None:
        """An AND function combines the two branches arithmetically."""
        program = boolean.qoibl("0001")
        assert program.startswith("we yee we et")
        assert "ry ee ry" in program
        assert program.endswith("tt")

    def test_constant_truth_table_folds(self) -> None:
        """A constant function needs only one tree assignment."""
        program = boolean.qoibl("0000")
        assert program.count("\nwe ") == 4

    def test_dense_growth_is_linear(self) -> None:
        """A full tree doubles by a bounded additive term."""
        sizes = [
            len(boolean.qoibl("".join(str(row.bit_count() & 1) for row in range(2**n))))
            for n in range(7, 11)
        ]
        assert all(b <= 2 * a + 800 for a, b in pairwise(sizes))


# 4.2s over 72 tests: runs the generated program.
@pytest.mark.medium
class TestPolynomial:
    def test_uncapped_dag_has_matching_text_bound(self) -> None:
        """Pin and execute the construction matching the language lower bound.

        The public generator keeps its resource cap; composing the existing
        DAG emitter and assembler directly is the language-level witness.
        These are structural envelopes, not a fitted size ratio.
        """
        from esolangs.tools.polynomial import _polynomial_assemble
        from tests.tools.test_boolean_contract import _dense

        for n in range(4, 9):
            table = _dense(n)
            levels = _polynomial_states(table, n)
            ceilings = [2 ** min(k, 2 ** (n - k)) for k in range(n + 1)]
            states = sum(map(len, levels))
            assert all(
                len(level) <= ceiling
                for level, ceiling in zip(levels, ceilings, strict=True)
            )
            assert states <= sum(ceilings)
            assert sum(ceilings) * n <= 8 * 2**n

            instructions = _polynomial_dag(table)
            assert len(instructions) <= 6 * states
            assert all(
                (len(instruction) == 1 and instruction[0] <= 2)
                or (
                    len(instruction) == 2
                    and instruction[1] <= 4
                    and abs(instruction[0]) <= 50 * states + n + 3
                )
                for instruction in instructions
            )

        table = _dense(4)
        instructions = _polynomial_dag(table)
        program = _polynomial_assemble(instructions)
        m = len(instructions)
        operand = max(abs(instruction[0]) for instruction in instructions)
        # The m-th prime is below m**2.  This bounds every factor's l1 norm;
        # multiplying l1 norms bounds every expanded coefficient.
        factor_l1_bound = (operand + 1) ** 2 + m**16
        coefficient_digits = m * len(str(factor_l1_bound))
        rendered_bound = 7 + (2 * m + 1) * (coefficient_digits + len(str(2 * m)) + 6)
        assert len(program) <= rendered_bound
        for row in range(16):
            bits = [(row >> (3 - i)) & 1 for i in range(4)]
            assert run_polynomial(program, [str(bit) for bit in bits]) == table[row]

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("00000001", 3),  # AND-3
            ("10000000", 3),  # OR-3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.polynomial(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_wide_table_rejected(self) -> None:
        """The gate is the instruction count, not the input count.

        Each instruction takes a fresh prime and becomes a polynomial
        factor, so what the interpreter cannot afford per row is
        instructions.  A scattered n == 11 table needs 2417 under its
        cheapest construction and is refused; the message names the count
        rather than ``n``.

        The witness has to be re-picked whenever the cap moves: the
        scattered n == 6 witness of the 138 era rendered under the 328 the
        peels bought, and the n == 8 witness of the 328 era renders under
        the 1934 the NTT screens bought, so a stale body silently stops
        exercising the gate.
        """
        import random

        random.seed(0)
        scattered = "".join(random.choice("01") for _ in range(2**11))
        with pytest.raises(ValueError, match="groups instructions onto primes"):
            boolean.polynomial(scattered)

    def test_polynomial_cap_admits_every_n10_table(self) -> None:
        """The cap is the analytic worst case over n == 10 tables.

        Level ``k`` of the machine holds at most ``min(2**k, 2**2**(10-k))``
        states -- reachability bounds it by doubling, the subtable width by
        counting -- at 5 instructions plus at most 2 transitions each, and
        the leaf level 5 each less the final endif.  So the cap admits all
        of n == 10 by construction, and the dense fixture sits under it
        with room that is measured, not assumed.
        """
        from esolangs.tools.register import _POLYNOMIAL_MAX_INSTRS

        states = [min(2**k, 2 ** (2 ** (10 - k))) for k in range(11)]
        # Root level 3, every other level 6 per state, two leaves at 6.
        worst = 3 + 6 * (sum(states[:10]) - 1) + 6 * states[10]
        assert worst == 1659
        # The bound stays at the 1934 the previous builder's worst case set:
        # the interpreter was measured to afford it, and a cheaper spelling
        # per state is no reason to refuse a table that fit before.
        assert (
            worst <= _POLYNOMIAL_MAX_INSTRS == 7 * sum(states[:10]) + 5 * states[10] - 1
        )

    @pytest.mark.slow  # 4.5s: one NTT factorization, then 256 cached rows
    def test_a_dense_eight_input_table_runs_every_row(self) -> None:
        """The arity the old cap refused now builds, and every row answers.

        Dense n == 8 is 462 instructions -- past the old 328, and past
        ``_NTT_MIN_DEGREE`` once rendered, so this is the suite's
        execution-gate witness for the NTT recovery path *and* for the
        per-program parse cache: the first row pays the factorization
        (~3.4s) and the other 255 amortize to under a millisecond each,
        which is what made the cap raisable at all.
        """
        from tests.tools.test_boolean_contract import _dense

        table = _dense(8)
        program = boolean.polynomial(table)
        for row in range(256):
            bits = [(row >> (7 - i)) & 1 for i in range(8)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == table[row], f"row {row}"

    @pytest.mark.slow  # 2.3s
    def test_state_machine_renders_past_the_old_input_gate(self) -> None:
        """Tables the ``n <= 4`` gate refused outright now render and run.

        The gate was on ``n`` because a decision tree doubles with it.  The
        state machine merges prefixes with equal residual subfunctions, so a
        table that collapses is cheap at any width: AND-5 was rejected and
        now builds, and parity -- the tree's worst case, 2553 instructions
        at n == 8 -- is linear here, 11 per input, and renders through
        n == 8.
        """
        and5 = "0" * 31 + "1"
        program = boolean.polynomial(and5)
        assert program.startswith("f(x) = ")
        for combo in range(2**5):
            bits = [(combo >> (4 - i)) & 1 for i in range(5)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == and5[combo], f"inputs {bits}"

        for n in (6, 8):
            parity = "".join(str(bin(row).count("1") % 2) for row in range(2**n))
            assert len(_polynomial_dag(parity)) == 11 * n + 3
            assert boolean.polynomial(parity).startswith("f(x) = ")

    def test_state_machine_merges_what_the_tree_cannot(self) -> None:
        """A subtable that is not constant can still collapse to one state.

        ``10101010`` is NOT of the last input: the tree folds nothing and
        spends an internal node per level, while every prefix leaves the
        same residual subfunction, so the machine needs one state per level
        until the last.  This is the merge that makes the construction
        stronger than the fold, rather than another way to spell it.
        """
        table = "10101010"
        assert [len(level) for level in _polynomial_states(table, 3)] == [1, 1, 1, 2]
        assert len(_polynomial_dag(table)) < len(_polynomial_tree(table))
        program = boolean.polynomial(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_polynomial(program, [str(b) for b in bits]) == table[combo]

    def test_polynomial_hybrid_cost_mirrors_build(self) -> None:
        """The hybrid's cost function is a deliberate mirror of its emitter.

        The dispatch screens on the cost before rendering, so a drift here
        silently skips a table the emitter would have shortened.
        """
        from esolangs.tools.register import (
            _polynomial_hybrid,
            _polynomial_hybrid_cost,
        )

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                for level in range(n + 1):
                    assert _polynomial_hybrid_cost(table, level) == len(
                        _polynomial_hybrid(table, level)
                    ), f"{table} k={level}"

    def test_hybrid_endpoints_are_the_two_old_constructions(self) -> None:
        """``k == n`` is the tree and ``k == 0`` is the machine.

        The family is not a third construction beside two others -- it
        contains both, which is what let the separate emitters go.  The
        machine's identity holds except on a constant table, where the
        hybrid collapses to a leaf before reaching it and comes out
        shorter (4 instructions against 5 at n == 1).
        """
        from esolangs.tools.register import _polynomial_hybrid

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                assert _polynomial_hybrid(table, n) == _polynomial_tree(table), table
                machine = _polynomial_hybrid(table, 0)
                if len(set(table)) == 1:
                    assert len(machine) < len(_polynomial_dag(table)), table
                else:
                    assert machine == _polynomial_dag(table), table

    @pytest.mark.slow
    def test_polynomial_screen_slack(self) -> None:
        """The screen's slack is a measurement, and it is arity-dependent.

        Selection is on rendered characters while the screen is on
        instructions, so the shortest render can sit above the cheapest
        candidate.  Every table at n <= 3 needs at most 1; a slack fitted
        there would emit the worse program at n == 4, where 2000 sampled
        tables reach 6.
        """
        from esolangs.tools.register import (
            _POLYNOMIAL_SCREEN_SLACK,
            _polynomial_assemble,
            _polynomial_hybrid,
            _polynomial_hybrid_cost,
        )

        worst = 0
        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                built = [
                    (_polynomial_hybrid_cost(table, k), _polynomial_hybrid(table, k))
                    for k in range(n + 1)
                ]
                rendered = [
                    (len(_polynomial_assemble(instrs)), cost) for cost, instrs in built
                ]
                shortest = min(length for length, _ in rendered)
                needed = min(cost for length, cost in rendered if length == shortest)
                worst = max(worst, needed - min(cost for cost, _ in built))
        # Pure-``k`` candidates only.
        assert worst == 1
        assert worst <= _POLYNOMIAL_SCREEN_SLACK

    @pytest.mark.parametrize(
        "table",
        ["00000101", "00001010", "01010000", "01011111", "10100000", "11111010"],
    )
    def test_hybrid_shortens_and_still_computes(self, table: str) -> None:
        """A split whose halves merge separately beats both parents.

        ``00000101`` is 45 instructions as a tree and 36 as a state machine,
        but 28 when the first bit branches and each half runs its own
        machine: the residuals merge *within* the top split and not across
        it, so neither parent construction sees the merge.
        """
        from esolangs.tools.register import _polynomial_hybrid

        assert len(_polynomial_hybrid(table, 1)) < len(_polynomial_tree(table))
        program = boolean.polynomial(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_polynomial(program, [str(b) for b in bits]) == table[combo]

    def test_drained_machine_survives_a_one_in_the_drained_bit(self) -> None:
        """The reduction reaches the machine, not just the tree.

        A drain is a bare read and the machine's root level opens with a
        read of its own, so the drained byte is overwritten unlooked-at.
        The previous chain tested for zero and a drained ``1`` fell past
        every state test; the rows with a 1 in the drained bit are still
        the ones that matter here.
        """
        from esolangs.tools.register import _polynomial_drained_dag

        table = "0000010100000101"  # ignores its first input
        assert _polynomial_drained_dag(table) is not None
        program = boolean.polynomial(table)
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize("table", ["00100000", "11011111", "00000010"])
    def test_machine_losing_on_characters_does_not_ship(self, table: str) -> None:
        """Fewer instructions is not fewer characters.

        These three are 35 instructions as a machine against the tree's 36
        and still render longer (4677 characters against 4614 for the
        first), because the machine spends a ``*=`` -- ``p**6`` against a
        ``+=``'s ``p**2`` -- where the tree spends only ``+=``.  The
        dispatch compares *rendered* programs, so they keep the tree's
        emission.  Found by sweeping the n == 3 corpus for tables whose
        fewest-instruction candidate is not the shortest render: five of
        256.
        """
        from esolangs.tools.register import (
            _polynomial_assemble,
            _polynomial_hybrid,
        )

        machine = _polynomial_assemble(_polynomial_hybrid(table, 0))
        tree = _polynomial_assemble(_polynomial_tree(table))
        assert len(_polynomial_hybrid(table, 0)) < len(_polynomial_tree(table))
        assert len(machine) > len(tree)
        assert boolean.polynomial(table) == tree

    def test_every_path_reads_each_input_once(self) -> None:
        """Whichever construction wins, a run consumes exactly ``n`` inputs.

        The reads are the interface: a caller feeding several programs from
        one stream desyncs if a path leaves bits unconsumed.  The tree
        drains the reads a folded leaf skipped; the state machine reads once
        inside the single branch each level's chain fires, so the count is
        structural.  Feeding an exhaustible iterator proves both directions
        -- an over-read raises, and a leftover proves an under-read.
        """
        for table, n in (("0110", 2), ("10101010", 3), ("00001111", 3)):
            program = boolean.polynomial(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                feed = iter([str(b) for b in bits])
                got = run_polynomial_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                assert not list(feed), f"{table} inputs {bits} left input unread"


class TestDig:
    @pytest.mark.medium
    def test_alternating_layout_executes_every_row(self) -> None:
        """The alternating-axis tree computes two dense wide tables."""
        for n in (5, 6):
            size = 1 << n
            tables = (
                ("01101001" * size)[:size],
                "".join(str((row * 73 + row // 3) & 1) for row in range(size)),
            )
            for table in tables:
                program = boolean.dig(table)
                for combo in range(size):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    assert run_dig(program, [str(bit) for bit in bits]) == table[combo]

    def test_alternating_layout_has_linear_area(self) -> None:
        """Two more levels quadruple entries and at most quadruple text."""
        sizes = [len(boolean.dig("01" * (2 ** (n - 1)))) for n in (7, 9)]
        assert sizes[1] <= 4 * sizes[0]

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
        program = boolean.dig(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dig(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_xor_layout(self) -> None:
        """The XOR gate produces the standard two-level decision tree.

        A level is five columns and the blocks abut: the ``#`` a node turns
        on is the cell right before its child's block, so the child's ``>``
        goes in that column and the mole walks straight out of the turn
        into the next ``$``.
        """
        expected = (
            "'         >$30:@\n"
            "     >$3~;#\n"
            "          >$31:@\n"
            ">$3~;#\n"
            "          >$31:@\n"
            "     >$3~;#\n"
            "          >$30:@"
        )
        assert boolean.dig("0110", width=80) == expected

    def test_compact_layout_uses_the_shorter_orientation(self) -> None:
        """The safe turn is useful for size, not only width requests."""
        from esolangs.tools.register import _dig_grid

        table = "0110100110010110"
        n = 4
        flat = _dig_grid(table, n, None)
        banded = _dig_grid(table, n, -(-(n + 2) // 2))
        assert len(banded) < len(flat)
        assert boolean.dig(table) == banded

    def test_a_constant_table_is_one_line(self) -> None:
        """Nothing to branch on, so the whole grid is a single leaf."""
        program = boolean.dig("1111")
        assert program.split("\n") == ["'", ">$5~~1:@"]

    def test_constant_subtrees_prune_their_rows(self) -> None:
        """A folded node's descendants are never written.

        Both tables have four ones, so the difference is arrangement alone:
        ``11110000`` is two constant halves and keeps one row per half,
        while parity has no constant slice above a single row and fills the
        grid.
        """
        folded = boolean.dig("11110000")
        full = boolean.dig("10010110")
        assert len(folded) < len(full)
        assert sum(1 for r in folded.split("\n") if r.strip()) < sum(
            1 for r in full.split("\n") if r.strip()
        )
        assert all(row.strip() for row in folded.splitlines())

    def test_a_long_read_run_chains_its_windows(self) -> None:
        """Past nine cells the ``$`` runs chain rather than growing a digit.

        ``$`` takes its count from the digit beside it, so one window holds
        at most nine cells -- six reads plus the three that print.  A
        constant table at n == 7 needs more than that, and must still run.
        """
        table = "1" * 128  # n == 7, constant
        program = boolean.dig(table)
        assert program.count("$") > 1  # more than one window
        assert esolangs.run("Dig", program, stdin="\n".join(["1"] * 7)).strip() == "1"

    def test_a_width_turns_the_tree_round_and_it_still_computes(self) -> None:
        """A narrower grid is the same walk, folded back over its own columns.

        The deep levels run west through mirrored blocks, so the mole meets
        each ``$`` first either way.  Only running it says the turn kept
        every path intact.
        """
        for table in ("0110", "10010110", "0110100110010110", "00010111"):
            n = len(table).bit_length() - 1
            flat = boolean.dig(table, 10_000)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.dig(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 12, 18, 24, wide):
                narrow = boolean.dig(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    got = run_dig(narrow, [str(b) for b in bits])
                    assert got == str(int(table[combo])), (table, width, bits)

    def test_a_folded_table_keeps_the_flat_layout(self) -> None:
        """Turning round is not always narrower, so the narrower one wins.

        A table that folds has few blocks to spread in the first place, and
        what the turn costs -- a spare column a level, and a leaf padded so
        its digits fall where the other band does not look -- can come to
        more than the fold saved.  ``dig`` lays both out and keeps the
        narrower, so a width it cannot meet still gets the best there is.

        These also drive the banded leaf's chained windows: a constant table
        at ``n == 6`` folds at the root and still owes six reads, one more
        than a single window covers.
        """
        for table in ("1" * 64, "1" * 32 + "0" * 32):
            n = len(table).bit_length() - 1
            flat = boolean.dig(table, 10_000)
            assert boolean.dig(table, 1) == flat, table
            for combo in (0, 2 ** (n - 1), 2**n - 1):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_dig(flat, [str(b) for b in bits])
                assert got == str(int(table[combo])), (table, bits)

    def test_the_turn_mirrors_the_blocks_it_writes(self) -> None:
        """Past the turn a block is written backwards, so its ``$`` comes first.

        A westbound mole meets the block's cells in the opposite order, so
        the block that steers it has to be the reverse of the eastbound one
        -- and the ``<`` that points it in has to sit where the parent's
        ``#`` turned it.
        """
        narrow = boolean.dig("0110100110010110", 1)
        assert _DIG_BRANCH[::-1] in narrow, "no mirrored block: the tree never turned"
        assert _DIG_RETURN in narrow, "nothing points the mole west"
        flat = boolean.dig("0110100110010110", 10_000)
        assert _DIG_BRANCH[::-1] not in flat
        assert _DIG_RETURN not in flat

    def test_the_layout_check_refuses_a_stride_that_collides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The clearance check is what licenses the two bands sharing columns.

        With a stride of six the eastbound hops miss every westbound ``$``,
        ``#`` and digit; with the flat layout's five they do not, and the
        grid that comes out is wrong in a way only a run would show.  So the
        check has to refuse it -- a silent pass here would mean it was
        licensing nothing at all.
        """
        dig_module = importlib.import_module("esolangs.tools.dig")

        monkeypatch.setattr(dig_module, "_DIG_BAND", _DIG_STRIDE)
        for table in ("0110", "10010110", "0110100110010110"):
            with pytest.raises(AssertionError):
                boolean.dig(table, 1)
        monkeypatch.undo()
        # and the stride the rule names still builds
        assert boolean.dig("0110100110010110", 1)


class TestSophie:
    def test_hybrid_subsumes_both_routes(self) -> None:
        """The hybrid is no longer than either prior construction through n=3."""
        from esolangs.tools.register import _sophie_hybrid

        improved = 0
        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                hybrid = _sophie_hybrid(table)
                assert len(hybrid) <= min(
                    len(_sophie_tree(table)), len(_sophie_dag(table))
                )
                improved += len(hybrid) < min(
                    len(_sophie_tree(table)), len(_sophie_dag(table))
                )
        assert improved == 132

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
        program = boolean.sophie(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_sophie(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function is a single conditional pair."""
        assert boolean.sophie("10") == ";@$48{#$49,&}{#$48,&}"

    def test_state_machine_merges_what_the_tree_cannot(self) -> None:
        """A subtable that is not constant can still collapse to one state.

        ``10101010`` is NOT of the last input: the nested tree branches at
        every level, while every prefix leaves the same residual
        subfunction, so the chain needs one state per level until the last.
        The accumulator carries the state label between levels, which is
        what a nested construction cannot express.
        """
        table = "10101010"
        assert [len(level) for level in _polynomial_states(table, 3)] == [1, 1, 1, 2]
        assert len(_sophie_dag(table)) < len(_sophie_tree(table))
        program = boolean.sophie(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_sophie(program, [str(b) for b in bits]) == table[combo]

    def test_merge_only_shrinks(self) -> None:
        """No table comes out longer than the nested tree alone.

        The hybrid inlines unshared states as tree branches, so labels only
        pay for actual merges. At n == 3, 130 of 256 tables shrink.
        """
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.sophie(table))
            tree = len(_sophie_tree(table))
            assert dispatched <= tree, table
            improved += dispatched < tree
        assert improved == 130

    def test_merge_is_linear_where_the_tree_doubles(self) -> None:
        """Parity needs two states per level however wide it gets.

        Parity is the nested tree's worst case at every width -- nothing
        folds, so it branches at all ``2**n - 1`` internal nodes -- and is
        the merge's best, since the running parity is the whole state.  The
        saving therefore grows with ``n`` rather than being a fixed trim.
        """
        previous = None
        for n in (4, 5, 6):
            parity = "".join(str(bin(row).count("1") % 2) for row in range(2**n))
            assert [len(level) for level in _polynomial_states(parity, n)] == [1] + [
                2
            ] * n
            ratio = len(_sophie_dag(parity)) / len(_sophie_tree(parity))
            assert ratio < 1
            if previous is not None:
                assert ratio < previous  # the gap widens with n
            previous = ratio

    def test_every_path_reads_each_input_once(self) -> None:
        """A run consumes exactly ``n`` inputs, whichever build won.

        The tree spends the reads a folded leaf skipped; the state machine
        reads once inside the single block each level's chain fires.  An
        exhaustible feed proves both directions -- an over-read raises, a
        leftover proves an under-read.
        """
        for table, n in (("10101010", 3), ("11111111", 3), ("01101001", 3)):
            program = boolean.sophie(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                feed = iter([str(b) for b in bits])
                got = run_sophie_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                assert not list(feed), f"{table} inputs {bits} left input unread"

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice prints outright, but still reads its inputs.

        Sophie reads *inside* the tree -- a node is ``;`` then its branch
        -- so a folded leaf carries the ``;`` it skipped.  Dropping them
        would make the program's input count depend on its table, which
        :mod:`tests.tools.test_boolean_contract` rejects for every
        generator.
        """
        assert boolean.sophie("1111") == ";;#$49,&"
        assert boolean.sophie("0000") == ";;#$48,&"
        assert boolean.sophie("0110").count(";") == 3  # nothing folds


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

    def test_postorder_tree_structure(self) -> None:
        """The tree reads each input once, reuses registers, and prints once."""
        program = boolean.collatz_multiverse("0110")
        assert program.count("input") == 2
        assert program.count("DO PRINT.") == 1
        assert "r0" in program
        assert "r1" in program

    def test_full_tree_growth_is_linear(self) -> None:
        """Parity folds nothing, but depth-reused names keep source linear."""
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


class TestDecleq:
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
        program = boolean.decleq(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_decleq(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_essential_bits_get_one_chain_each(self) -> None:
        """Each essential bit is decremented 47 times, then tested once.

        An ignored input is read, so the interface holds, but never
        decremented: its chain would normalize a bit no branch and no
        index step ever looks at.
        """
        for table, essential in (("0110", {0, 1}), ("11110000", {0})):
            n = len(table).bit_length() - 1
            program = boolean.decleq(table)
            cells = [int(tok) for tok in program.split()]
            instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
            assert sum(1 for ins in instrs if ins[0] == -1) == n  # one read each
            for i in range(n):
                rc = 18 + i
                decs = sum(1 for ins in instrs if ins[0] == ins[1] == rc)
                assert decs == (48 if i in essential else 0), (table, i)

    def test_constant_subtrees_fold(self) -> None:
        """A constant subtree above the table level is a one-instruction leaf.

        Decleq splits most-significant-first, so its subtrees are
        contiguous runs: at five inputs the tree tests one bit above the
        sixteen-row tables, and ``1 * 16 + 0 * 16`` folds both halves to
        a jump each -- no table at all -- while parity folds nothing and
        carries two tables.
        """
        halves = "1" * 16 + "0" * 16
        parity = "".join(str(bin(row).count("1") & 1) for row in range(32))

        def outputs(table: str) -> int:
            cells = [int(tok) for tok in boolean.decleq(table).split()]
            return cells.count(-2)

        # The two gadgets print; a table leaf carries one more print each.
        assert outputs(halves) == 2
        assert outputs(parity) == 4
        assert len(boolean.decleq(halves)) < len(boolean.decleq(parity))

    def test_size_is_linear_in_the_table(self) -> None:
        """The per-entry cost falls with arity: no leaf names a wide address.

        A full decision tree is ``Theta(T log T)`` in Decleq (``T - 1``
        distinct absolute targets), so the tree stops ``k`` levels short and
        the rest is a table of three-character cells.  Executed at n=6 on
        every row, because a wrong index lands on a plausible cell.
        """
        per_entry = [len(boolean.decleq(_parity(n))) / 2**n for n in (8, 10, 12)]
        assert per_entry[0] > per_entry[1] > per_entry[2]
        assert per_entry[2] < 8
        rng = random.Random(6)
        table = "".join(rng.choice("01") for _ in range(64))
        program = boolean.decleq(table)
        for combo in range(64):
            bits = [(combo >> (5 - i)) & 1 for i in range(6)]
            got = run_decleq(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    def test_folded_leaves_still_print_correctly(self) -> None:
        """Every folded table still prints its entry for every input."""
        for table in ("11111111", "11110000", "11001100", "00001111"):
            program = boolean.decleq(table)
            n = len(table).bit_length() - 1
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_decleq(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"


def _depth_zero_labels(program: str) -> list[int]:
    """Every ``@$N`` block label at the top level of ``program``.

    Sophie dispatches by setting the accumulator with ``#$N`` and falling
    through the top-level ``@$N{...}`` blocks, so two blocks sharing an
    ``N`` means the first also fires.  48 and 49 are excluded: those are the
    bit tests, which are not dispatch labels.
    """
    labels: list[int] = []
    depth = index = 0
    while index < len(program):
        char = program[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "@" and depth == 0 and program[index + 1 : index + 2] == "$":
            end = index + 2
            while end < len(program) and program[end].isdigit():
                end += 1
            value = int(program[index + 2 : end])
            if value not in (_ASCII_ZERO, _ASCII_ONE):
                labels.append(value)
            index = end
            continue
        index += 1
    return labels


class TestSophieLabelsAreUnique:
    """Two blocks with one label make the first fire on the way past.

    Labels used to come from two bands chosen by level parity, on the
    reasoning that a fired block leaves a *next*-level label in the
    accumulator which no remaining test in the chain can match.  That is
    true of consecutive levels and consecutive levels are not the relation
    that matters: unshared states are inlined, so a single top-level block
    carries jumps originating at several depths, and levels 2 and 4 -- same
    parity, same band -- were both targets from inside it.  Level 2 is
    emitted first, so a jump meant for level 4 ran level 2 first and read
    inputs the caller never supplied.

    The failure is *shape*-dependent, not size-dependent, which is why it
    survived: Sophie is correct on all 65536 tables at n <= 4, and collides
    on 35% of random tables at n=7.
    """

    #: The smallest table that collides, found by exhaustive search upward.
    MINIMAL = "00000000000000010000000100000100"

    def test_the_minimal_colliding_table_computes(self) -> None:
        """It raised ``read past the end of input: 5 lines supplied, read 6``."""
        assert boolean.sophie(self.MINIMAL)  # builds, and always did
        for combo in range(32):
            bits = [(combo >> (4 - i)) & 1 for i in range(5)]
            got = run_sophie(boolean.sophie(self.MINIMAL), [str(b) for b in bits])
            assert got == self.MINIMAL[combo], bits

    def test_the_minimal_table_has_no_duplicate_label(self) -> None:
        """Its program carried two ``@$1`` blocks."""
        labels = _depth_zero_labels(boolean.sophie(self.MINIMAL))
        assert len(labels) == len(set(labels)), labels

    @pytest.mark.parametrize("n", [5, 6, 7, 8])
    def test_no_table_collides_at_any_arity(self, n: int) -> None:
        """A structural check, so it reaches arities executing cannot afford.

        Sampled rather than exhaustive, with a fixed seed: at n=8 the old
        scheme collided on 88% of random tables, so twenty is ample to
        catch a regression and cheap enough to run every time.  The shapes
        that first exposed this are included by name, since a random sample
        is exactly what missed it for so long.
        """
        rng = random.Random(n)
        tables = ["".join(rng.choice("01") for _ in range(2**n)) for _ in range(20)]
        tables.append("".join(str(int(bin(r).count("1") == 1)) for r in range(2**n)))
        for table in tables:
            labels = _depth_zero_labels(boolean.sophie(table))
            assert len(labels) == len(set(labels)), (n, table)

    def test_a_label_is_never_a_bit_value(self) -> None:
        """48 and 49 are what a read leaves behind, so a block cannot own one.

        Nothing else is reserved -- the interpreter parses a label as a
        plain digit run -- so this is the whole constraint, and it binds
        only once the count climbs past 47.
        """
        for n in (6, 7, 8):
            table = "".join(str(int(bin(r).count("1") == 1)) for r in range(2**n))
            labels = _depth_zero_labels(boolean.sophie(table))
            assert _ASCII_ZERO not in labels
            assert _ASCII_ONE not in labels

    def test_the_scan_can_actually_see_a_duplicate(self) -> None:
        """The positive control: a checker that never fires guards nothing."""
        assert _depth_zero_labels("@$1{;}@$1{;}") == [1, 1]
        assert _depth_zero_labels("@$1{@$1{;}}") == [1]  # nested is not top level
        assert _depth_zero_labels(";@$48{#$48,&}{#$49,&}") == []  # bit tests only
