"""Unit tests for the register-based boolean generators.

Covers the generators in :mod:`esolangs.tools.boolean.register`: Decleq,
AddSubJump, Collatz Multiverse, Sophie, Dig, Qoibl, Polynomial, and Point
Break.
"""

import pytest

import esolangs
from esolangs.tools import boolean
from esolangs.tools.boolean.register import (
    _DIG_BRANCH,
    _DIG_RETURN,
    _DIG_STRIDE,
    _addsubjump_ordered,
    _polynomial_dag,
    _polynomial_states,
)
from tests.tools.boolean_oracles import (
    _polynomial_tree,
    _sophie_dag,
    _sophie_tree,
)
from tests.tools.boolean_runners import (
    _PB_CONSTANTS,
    _PB_TABLES,
    _pb_combo_bits,
    _pb_random_tables,
    point_break_result,
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


def _asj_normalize_sites(program: str) -> int:
    """How many instructions add the ``-48`` constant cell to something.

    One per *stored input* once the reads are hoisted, against one per
    internal node when they sat at the nodes.  The constant lives in a data
    cell, so this finds that cell's address and counts the instructions
    whose ``b`` operand names it.
    """
    mem = [int(tok) for tok in program.split()]
    const = mem.index(-48)
    return sum(1 for i in range(0, len(mem) - 3, 4) if mem[i + 1] == const)


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

    def test_branch_normalizes_bits_to_zero_and_four(self) -> None:
        """Each bit is normalized to {0, 4} and added to a jump cell."""
        program = boolean.addsubjump("0110")
        assert "-48" in program  # the normalization constant
        assert run_addsubjump(program, ["0", "1"]) == "1"
        assert run_addsubjump(program, ["1", "0"]) == "1"

    def test_normalizes_once_per_input_not_once_per_node(self) -> None:
        """The reads and their normalization are hoisted out of the tree.

        Reading at the node repeated the four-instruction normalization at
        every internal node; hoisting spends it once per *stored input*, so
        the count tracks ``n`` rather than the tree's width.  ``-48`` is the
        normalization constant and appears once in the data section, so the
        instructions referencing its cell are what to count.
        """
        # XOR-3 has 7 internal nodes but only 3 inputs.
        cells = _asj_normalize_sites(boolean.addsubjump("01101001"))
        assert cells == 3

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

    def test_reordering_only_shrinks(self) -> None:
        """No table comes out longer than the identity order's program.

        ``best_input_order`` tries the identity first and ties keep it, so
        this is a property of the dispatch rather than of the language; the
        sweep pins it against a build that cannot silently regress.
        """
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.addsubjump(table))
            identity = len(_addsubjump_ordered(table, (0, 1, 2)))
            assert dispatched <= identity, table
            improved += dispatched < identity
        assert improved == 118  # the rest tie, keeping the identity order


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
        program = boolean.qoibl(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_qoibl(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_minterm_structure(self) -> None:
        """An AND function stores the minterm product and prints 48 + sum."""
        program = boolean.qoibl("0001")
        assert program.startswith("we e we et")
        assert "ry ye ry" in program  # a minterm product
        assert program.endswith("tt")

    def test_empty_truth_table(self) -> None:
        """A constant-zero function skips all minterms."""
        program = boolean.qoibl("0000")
        assert "ry ye ry" not in program


class TestPolynomial:
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
        instructions.  A scattered n == 11 table needs 2874 under its
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
        with pytest.raises(ValueError, match="one instruction per prime"):
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
        from esolangs.tools.boolean.register import _POLYNOMIAL_MAX_INSTRS

        states = [min(2**k, 2 ** (2 ** (10 - k))) for k in range(11)]
        assert 7 * sum(states[:10]) + 5 * states[10] - 1 == _POLYNOMIAL_MAX_INSTRS

    @pytest.mark.slow  # 4.5s: one NTT factorization, then 256 cached rows
    def test_a_dense_eight_input_table_runs_every_row(self) -> None:
        """The arity the old cap refused now builds, and every row answers.

        Dense n == 8 is 541 instructions -- past the old 328, and past
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
        is 63 instructions, and parity -- the tree's worst case, 2298
        instructions at n == 8 -- is linear here and renders through n == 8.
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
            assert len(_polynomial_dag(parity)) == 13 * n + 2
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

    def test_dag_cost_mirrors_its_emitter(self) -> None:
        """``_polynomial_hybrid_cost`` prices a residual through this."""
        from esolangs.tools.boolean.register import _polynomial_dag_cost

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                assert _polynomial_dag_cost(table) == len(_polynomial_dag(table))

    def test_polynomial_hybrid_cost_mirrors_build(self) -> None:
        """The hybrid's cost function is a deliberate mirror of its emitter.

        The dispatch screens on the cost before rendering, so a drift here
        silently skips a table the emitter would have shortened.
        """
        from esolangs.tools.boolean.register import (
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
        shorter (5 instructions against 10 at n == 1).
        """
        from esolangs.tools.boolean.register import _polynomial_hybrid

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                assert _polynomial_hybrid(table, n) == _polynomial_tree(table), table
                machine = _polynomial_hybrid(table, 0)
                if len(set(table)) == 1:
                    assert len(machine) < len(_polynomial_dag(table)), table
                else:
                    assert machine == _polynomial_dag(table), table

    def test_polynomial_screen_slack(self) -> None:
        """The screen's slack is a measurement, and it is arity-dependent.

        Selection is on rendered characters while the screen is on
        instructions, so the shortest render can sit above the cheapest
        candidate.  Every table at n <= 3 needs at most 6; a slack fitted
        there would emit the worse program at n == 4, which reaches 9.
        """
        from esolangs.tools.boolean.register import (
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
        # Pure-``k`` candidates only; the drained variants were measured
        # separately and reach the same 6 here, so widening this sweep
        # would not raise the bound.
        assert worst == 6
        assert worst <= _POLYNOMIAL_SCREEN_SLACK

    @pytest.mark.parametrize(
        "table",
        ["00000101", "00001010", "01010000", "01011111", "10100000", "11111010"],
    )
    def test_hybrid_shortens_and_still_computes(self, table: str) -> None:
        """A split whose halves merge separately beats both parents.

        ``00000101`` is 43 instructions as a tree and 39 as a state machine,
        but 36 when the first bit branches and each half runs its own
        machine: the residuals merge *within* the top split and not across
        it, so neither parent construction sees the merge.  Measured over
        the n == 3 corpus these tables render 24-30% shorter, and no table
        grows.
        """
        from esolangs.tools.boolean.register import _polynomial_hybrid

        assert len(_polynomial_hybrid(table, 1)) < len(_polynomial_tree(table))
        program = boolean.polynomial(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_polynomial(program, [str(b) for b in bits]) == table[combo]

    def test_drained_machine_survives_a_one_in_the_drained_bit(self) -> None:
        """The reduction reaches the machine, not just the tree.

        Draining with ``-= 48`` leaves 0 or 1 and the machine's entry chain
        tests for zero, so a drained ``1`` fell past every state test -- the
        failure that made this pairing look impossible.  ``//= 50`` lands on
        0 either way, so the rows with a 1 in the drained bit are the ones
        that matter here.
        """
        from esolangs.tools.boolean.register import _polynomial_drained_dag

        table = "0000010100000101"  # ignores its first input
        assert _polynomial_drained_dag(table) is not None
        program = boolean.polynomial(table)
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize("table", ["01100000", "01101111", "10010000", "10011111"])
    def test_hybrid_losing_on_characters_does_not_ship(self, table: str) -> None:
        """Fewer instructions is not fewer characters.

        These four are 42 instructions against the tree's 43 and still
        render 11008 characters against 9507, because a longer program's
        later instructions consume larger primes.  The dispatch compares
        *rendered* programs, so they keep the tree's emission.
        """
        from esolangs.tools.boolean.register import (
            _polynomial_assemble,
            _polynomial_hybrid,
        )

        hybrid = _polynomial_assemble(_polynomial_hybrid(table, 1))
        tree = _polynomial_assemble(_polynomial_tree(table))
        assert len(_polynomial_hybrid(table, 1)) < len(_polynomial_tree(table))
        assert len(hybrid) > len(tree)
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
        assert boolean.dig("0110") == expected

    def test_a_constant_table_is_one_line(self) -> None:
        """Nothing to branch on, so the whole grid is a single leaf."""
        program = boolean.dig("1111")
        assert [line for line in program.split("\n") if line.strip()] == [
            "'",
            ">$5~~1:@",
        ]

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
            flat = boolean.dig(table)
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
            flat = boolean.dig(table)
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
        flat = boolean.dig("0110100110010110")
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
        from esolangs.tools.boolean import register

        monkeypatch.setattr(register, "_DIG_BAND", _DIG_STRIDE)
        for table in ("0110", "10010110", "0110100110010110"):
            with pytest.raises(AssertionError):
                boolean.dig(table, 1)
        monkeypatch.undo()
        # and the stride the rule names still builds
        assert boolean.dig("0110100110010110", 1)


class TestSophie:
    def test_hybrid_subsumes_both_routes(self) -> None:
        """The hybrid is no longer than either prior construction through n=3."""
        from esolangs.tools.boolean.register import _sophie_hybrid

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

    def test_minterm_structure(self) -> None:
        """The program reads one input per line and prints once."""
        program = boolean.collatz_multiverse("0110")
        assert program.count("input") == 2
        assert program.count("DO PRINT.") == 1

    def test_a_dense_table_selects_its_zero_rows(self) -> None:
        """More ones than zeros costs less built the other way.

        Inverting is free here rather than one operation: the OR ends on a
        ``flip`` turning ``prod(1 - minterm)`` into the answer, so a
        complemented table keeps the accumulator instead.  A dense table is
        therefore *shorter* than its sparse complement, not merely equal.
        """
        dense = boolean.collatz_multiverse("11111110")  # one zero row
        sparse = boolean.collatz_multiverse("00000001")  # one one row
        assert len(dense) < len(sparse)
        for table in ("11111110", "00000001"):
            program = boolean.collatz_multiverse(table)
            for combo in range(8):
                bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
                assert run_collatz_multiverse(program, bits) == table[combo]

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

    def test_branch_normalizes_essential_bits_to_one_and_two(self) -> None:
        """Each essential bit gets a 47-step decrement chain, then one branch."""
        program = boolean.decleq("0110")
        cells = [int(tok) for tok in program.split()]
        instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
        # Count a==b>0 instructions: the 47 normalization steps per
        # essential input plus the decision-tree branches (2**n - 1 here).
        decs = [ins for ins in instrs if ins[0] == ins[1] and ins[0] > 0]
        assert len(decs) == 47 * 2 + 3
        assert sum(1 for ins in instrs if ins[0] == -1) == 2  # one read each

    def test_constant_subtrees_fold(self) -> None:
        """A constant subtree becomes a leaf instead of branching further.

        Decleq splits most-significant-first, so its subtrees are
        contiguous runs: ``11110000`` is two constant halves and folds to
        one branch, while ``10101010`` is constant over no run at all and
        keeps the full tree.
        """
        program = boolean.decleq("11110000")
        cells = [int(tok) for tok in program.split()]
        instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
        decs = [ins for ins in instrs if ins[0] == ins[1] and ins[0] > 0]
        # The table depends only on its first input.  Both other inputs are
        # still read, but their folded branches never need normalizing.
        assert len(decs) == 47 + 1
        assert sum(1 for ins in instrs if ins[0] == -1) == 3
        assert len(boolean.decleq("11110000")) < len(boolean.decleq("10101010"))

    def test_folding_leaves_no_dead_cells(self) -> None:
        """Every cell is an instruction or live data -- none is filler.

        ``data_base`` is computed before emitting, so the tree has to be
        *counted* before it is walked.  When that count is right the code
        ends exactly at ``data_base`` and the only zero cells in the
        finished program are the ``n`` read cells, which the reads fill in
        at runtime.

        A count that assumed nothing folded would still produce a working
        program -- the allocation fills out to the reserved address, so
        every leaf resolves -- with a run of dead zero cells wedged in
        between (63 at ``n == 3``).  Nothing about the output reveals
        that, so the cell count is what has to be pinned.
        """
        for table in ("11111111", "11110000", "11001100"):
            n = len(table).bit_length() - 1
            cells = [int(tok) for tok in boolean.decleq(table).split()]
            zeros_at_end = 0
            for value in reversed(cells[:-2]):  # the two output cells hold 48/49
                if value:
                    break
                zeros_at_end += 1
            assert zeros_at_end == n, f"{table} carries {zeros_at_end - n} dead cells"

    def test_folded_leaves_still_print_correctly(self) -> None:
        """Every folded table still prints its entry for every input."""
        for table in ("11111111", "11110000", "11001100", "00001111"):
            program = boolean.decleq(table)
            n = len(table).bit_length() - 1
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_decleq(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"


class TestPointBreak:
    @pytest.mark.parametrize(("table", "n"), sorted(_PB_TABLES.items()))
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination halts or loops per its table entry."""
        program = boolean.point_break(table)
        for combo in range(2**n):
            got = point_break_result(program, _pb_combo_bits(combo, n))
            assert got == table[combo], f"inputs {_pb_combo_bits(combo, n)}"

    @pytest.mark.parametrize("table", _PB_CONSTANTS)
    def test_constant_tables(self, table: str) -> None:
        """A constant table skips the tree but still consumes its inputs.

        The body may shrink to the bare template -- there is no sum to
        build -- but the reads are the interface: a program whose input
        count depended on its truth table would leave the caller's
        remaining bits on the stream for whatever ran next.  These tables
        take the short-circuit path that bypasses the tree entirely, so
        they are where a lost read would hide.
        """
        import contextlib

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.point_break import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        n = len(table).bit_length() - 1
        program = boolean.point_break(table)
        for combo in range(2**n):
            got = point_break_result(program, _pb_combo_bits(combo, n))
            assert got == table[combo], (
                f"table {table} inputs {_pb_combo_bits(combo, n)}"
            )
        io = ScriptedIO("0\n" * (n + 4))
        with contextlib.suppress(Exception, SystemExit):
            run_until_halt_or_cycle(_Machine(program.splitlines(), io))
        assert io.position() == n, (
            f"table {table} consumed {io.position()} inputs, expected {n}"
        )

    def test_random_tables(self) -> None:
        for table in _pb_random_tables():
            n = len(table).bit_length() - 1
            program = boolean.point_break(table)
            for combo in range(2**n):
                got = point_break_result(program, _pb_combo_bits(combo, n))
                assert got == table[combo], (
                    f"table {table} inputs {_pb_combo_bits(combo, n)}"
                )

    def test_program_structure(self) -> None:
        """One read per input, complemented bits, a minterm sum, the template."""
        program = boolean.point_break("0110").splitlines()
        assert program[:3] == ["LET a:=1", "LET b:=?", "LET c:=?"]
        assert program[3:5] == ["LET d:=a-b", "LET e:=a-c"]
        assert sum(":=?" in line for line in program) == 2  # one read per input
        assert program.count("LET f:=f+g") == 2  # one minterm per 1 row
        assert program[-3:] == ["POINT loop", "IF h BREAK loop", "END loop"]

    def test_a_dense_table_sums_its_zero_rows(self) -> None:
        """More ones than zeros costs less summed the other way.

        The guard breaks the loop on a nonzero, so it is already the
        complement of the answer -- which makes inverting free here: the
        complemented sum *is* the guard, and the ``one-f`` subtraction is
        dropped rather than added to.
        """
        dense = boolean.point_break("11111110").splitlines()
        sparse = boolean.point_break("00000001").splitlines()
        # one minterm each: summing the dense table's ones would be seven
        assert dense.count("LET h:=h+i") == 1
        assert sparse.count("LET h:=h+i") == 1
        # the dense one aliases the guard instead of subtracting for it
        assert "LET j:=h" in dense
        assert "LET j:=a-h" in sparse
        for table in ("11111110", "00000001"):
            program = boolean.point_break(table)
            for combo in range(8):
                bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
                assert point_break_result(program, bits) == table[combo]

    def test_mismatched_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.point_break("011")

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.point_break("0123")
