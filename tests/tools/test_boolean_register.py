r"""Unit tests for the register-based boolean generators."""

import random

import pytest

import esolangs
from esolangs.tools import boolean
from esolangs.tools.boolean.helpers import _ASCII_ONE, _ASCII_ZERO
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
    r"""How many instructions add the ``-48`` constant cell to something."""
    mem = [int(tok) for tok in program.split()]
    const = mem.index(-48)
    return sum(1 for i in range(0, len(mem) - 3, 4) if mem[i + 1] == const)


class TestAddSubJump:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.addsubjump(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_addsubjump(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_branch_normalizes_bits_to_zero_and_four(self) -> None:
        r"""Each bit is normalized to {0, 4} and added to a jump cell."""
        program = boolean.addsubjump("0110")
        assert "-48" in program  # the normalization constant.
        assert run_addsubjump(program, ["0", "1"]) == "1"
        assert run_addsubjump(program, ["1", "0"]) == "1"

    def test_normalizes_once_per_input_not_once_per_node(self) -> None:
        r"""The reads and their normalization are hoisted out of the tree."""
        # XOR-3 has 7 internal nodes.
        cells = _asj_normalize_sites(boolean.addsubjump("01101001"))
        assert cells == 3

    def test_every_path_reads_each_input_once(self) -> None:
        r"""A run consumes exactly ``n`` inputs, whatever the table."""
        for table, n in (("01101001", 3), ("11111111", 3), ("10101010", 3)):
            program = boolean.addsubjump(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                feed = iter([str(b) for b in bits])
                got = run_addsubjump_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                assert not list(feed), f"{table} inputs {bits} left input unread"

    def test_reordering_only_shrinks(self) -> None:
        r"""No table comes out longer than the identity order's program."""
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.addsubjump(table))
            identity = len(_addsubjump_ordered(table, (0, 1, 2)))
            assert dispatched <= identity, table
            improved += dispatched < identity
        assert improved == 118  # the rest tie, keeping the.


class TestQoibl:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1000000000000000", 4),  # AND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.qoibl(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_qoibl(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_minterm_structure(self) -> None:
        r"""An AND function stores the minterm product and prints 48 + sum."""
        program = boolean.qoibl("0001")
        assert program.startswith("we e we et")
        assert "ry ye ry" in program  # a minterm product.
        assert program.endswith("tt")

    def test_empty_truth_table(self) -> None:
        r"""A constant-zero function skips all minterms."""
        program = boolean.qoibl("0000")
        assert "ry ye ry" not in program


# 4.2s over 72 tests: runs the.
@pytest.mark.medium
class TestPolynomial:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("00000001", 3),  # AND-3.
            ("10000000", 3),  # OR-3.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.polynomial(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_wide_table_rejected(self) -> None:
        r"""The gate is the instruction count, not the input count."""
        import random

        random.seed(0)
        scattered = "".join(random.choice("01") for _ in range(2**11))
        with pytest.raises(ValueError, match="one instruction per prime"):
            boolean.polynomial(scattered)

    def test_polynomial_cap_admits_every_n10_table(self) -> None:
        r"""The cap is the analytic worst case over n == 10 tables."""
        from esolangs.tools.boolean.register import _POLYNOMIAL_MAX_INSTRS

        states = [min(2**k, 2 ** (2 ** (10 - k))) for k in range(11)]
        assert 7 * sum(states[:10]) + 5 * states[10] - 1 == _POLYNOMIAL_MAX_INSTRS

    @pytest.mark.slow  # 4.5s: one NTT factorization,.
    def test_a_dense_eight_input_table_runs_every_row(self) -> None:
        r"""The arity the old cap refused now builds, and every row answers."""
        from tests.tools.test_boolean_contract import _dense

        table = _dense(8)
        program = boolean.polynomial(table)
        for row in range(256):
            bits = [(row >> (7 - i)) & 1 for i in range(8)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == table[row], f"row {row}"

    @pytest.mark.slow  # 2.3s.
    def test_state_machine_renders_past_the_old_input_gate(self) -> None:
        r"""Tables the ``n <= 4`` gate refused outright now render and run."""
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
        r"""A subtable that is not constant can still collapse to one state."""
        table = "10101010"
        assert [len(level) for level in _polynomial_states(table, 3)] == [1, 1, 1, 2]
        assert len(_polynomial_dag(table)) < len(_polynomial_tree(table))
        program = boolean.polynomial(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_polynomial(program, [str(b) for b in bits]) == table[combo]

    def test_dag_cost_mirrors_its_emitter(self) -> None:
        r"""``_polynomial_hybrid_cost`` prices a residual through this."""
        from esolangs.tools.boolean.register import _polynomial_dag_cost

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                assert _polynomial_dag_cost(table) == len(_polynomial_dag(table))

    def test_polynomial_hybrid_cost_mirrors_build(self) -> None:
        r"""The hybrid's cost function is a deliberate mirror of its emitter."""
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
        r"""``k == n`` is the tree and ``k == 0`` is the machine."""
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
        r"""The screen's slack is a measurement, and it is arity-dependent."""
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
        # Pure-``k`` candidates only;.
        # separately and reach the same.
        # would not raise the bound.
        assert worst == 6
        assert worst <= _POLYNOMIAL_SCREEN_SLACK

    @pytest.mark.parametrize(
        "table",
        ["00000101", "00001010", "01010000", "01011111", "10100000", "11111010"],
    )
    def test_hybrid_shortens_and_still_computes(self, table: str) -> None:
        r"""A split whose halves merge separately beats both parents."""
        from esolangs.tools.boolean.register import _polynomial_hybrid

        assert len(_polynomial_hybrid(table, 1)) < len(_polynomial_tree(table))
        program = boolean.polynomial(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_polynomial(program, [str(b) for b in bits]) == table[combo]

    def test_drained_machine_survives_a_one_in_the_drained_bit(self) -> None:
        r"""The reduction reaches the machine, not just the tree."""
        from esolangs.tools.boolean.register import _polynomial_drained_dag

        table = "0000010100000101"  # ignores its first input.
        assert _polynomial_drained_dag(table) is not None
        program = boolean.polynomial(table)
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            got = run_polynomial(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize("table", ["01100000", "01101111", "10010000", "10011111"])
    def test_hybrid_losing_on_characters_does_not_ship(self, table: str) -> None:
        r"""Fewer instructions is not fewer characters."""
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
        r"""Whichever construction wins, a run consumes exactly ``n`` inputs."""
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
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1000000000000000", 4),  # AND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.dig(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dig(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_xor_layout(self) -> None:
        r"""The XOR gate produces the standard two-level decision tree."""
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
        r"""Nothing to branch on, so the whole grid is a single leaf."""
        program = boolean.dig("1111")
        assert [line for line in program.split("\n") if line.strip()] == [
            "'",
            ">$5~~1:@",
        ]

    def test_constant_subtrees_prune_their_rows(self) -> None:
        r"""A folded node's descendants are never written."""
        folded = boolean.dig("11110000")
        full = boolean.dig("10010110")
        assert len(folded) < len(full)
        assert sum(1 for r in folded.split("\n") if r.strip()) < sum(
            1 for r in full.split("\n") if r.strip()
        )

    def test_a_long_read_run_chains_its_windows(self) -> None:
        r"""Past nine cells the ``$`` runs chain rather than growing a digit."""
        table = "1" * 128  # n == 7, constant.
        program = boolean.dig(table)
        assert program.count("$") > 1  # more than one window.
        assert esolangs.run("Dig", program, stdin="\n".join(["1"] * 7)).strip() == "1"

    def test_a_width_turns_the_tree_round_and_it_still_computes(self) -> None:
        r"""A narrower grid is the same walk, folded back over its own columns."""
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
        r"""Turning round is not always narrower, so the narrower one wins."""
        for table in ("1" * 64, "1" * 32 + "0" * 32):
            n = len(table).bit_length() - 1
            flat = boolean.dig(table)
            assert boolean.dig(table, 1) == flat, table
            for combo in (0, 2 ** (n - 1), 2**n - 1):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_dig(flat, [str(b) for b in bits])
                assert got == str(int(table[combo])), (table, bits)

    def test_the_turn_mirrors_the_blocks_it_writes(self) -> None:
        r"""Past the turn a block is written backwards, so its ``$`` comes."""
        narrow = boolean.dig("0110100110010110", 1)
        assert _DIG_BRANCH[::-1] in narrow, "no mirrored block: the tree never turned"
        assert _DIG_RETURN in narrow, "nothing points the mole west"
        flat = boolean.dig("0110100110010110")
        assert _DIG_BRANCH[::-1] not in flat
        assert _DIG_RETURN not in flat

    def test_the_layout_check_refuses_a_stride_that_collides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""The clearance check is what licenses the two bands sharing columns."""
        from esolangs.tools.boolean import register

        monkeypatch.setattr(register, "_DIG_BAND", _DIG_STRIDE)
        for table in ("0110", "10010110", "0110100110010110"):
            with pytest.raises(AssertionError):
                boolean.dig(table, 1)
        monkeypatch.undo()
        # and the stride the rule names.
        assert boolean.dig("0110100110010110", 1)


class TestSophie:
    def test_hybrid_subsumes_both_routes(self) -> None:
        r"""The hybrid is no longer than either prior construction through n=3."""
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
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1111111111111110", 4),  # NAND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.sophie(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_sophie(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        r"""A one-input function is a single conditional pair."""
        assert boolean.sophie("10") == ";@$48{#$49,&}{#$48,&}"

    def test_state_machine_merges_what_the_tree_cannot(self) -> None:
        r"""A subtable that is not constant can still collapse to one state."""
        table = "10101010"
        assert [len(level) for level in _polynomial_states(table, 3)] == [1, 1, 1, 2]
        assert len(_sophie_dag(table)) < len(_sophie_tree(table))
        program = boolean.sophie(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_sophie(program, [str(b) for b in bits]) == table[combo]

    def test_merge_only_shrinks(self) -> None:
        r"""No table comes out longer than the nested tree alone."""
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.sophie(table))
            tree = len(_sophie_tree(table))
            assert dispatched <= tree, table
            improved += dispatched < tree
        assert improved == 130

    def test_merge_is_linear_where_the_tree_doubles(self) -> None:
        r"""Parity needs two states per level however wide it gets."""
        previous = None
        for n in (4, 5, 6):
            parity = "".join(str(bin(row).count("1") % 2) for row in range(2**n))
            assert [len(level) for level in _polynomial_states(parity, n)] == [1] + [
                2
            ] * n
            ratio = len(_sophie_dag(parity)) / len(_sophie_tree(parity))
            assert ratio < 1
            if previous is not None:
                assert ratio < previous  # the gap widens with n.
            previous = ratio

    def test_every_path_reads_each_input_once(self) -> None:
        r"""A run consumes exactly ``n`` inputs, whichever build won."""
        for table, n in (("10101010", 3), ("11111111", 3), ("01101001", 3)):
            program = boolean.sophie(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                feed = iter([str(b) for b in bits])
                got = run_sophie_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                assert not list(feed), f"{table} inputs {bits} left input unread"

    def test_constant_subtrees_fold(self) -> None:
        r"""A constant slice prints outright, but still reads its inputs."""
        assert boolean.sophie("1111") == ";;#$49,&"
        assert boolean.sophie("0000") == ";;#$48,&"
        assert boolean.sophie("0110").count(";") == 3  # nothing folds.


class TestCollatzMultiverse:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("1111111100000000", 4),  # top half.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.collatz_multiverse(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_collatz_multiverse(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_minterm_structure(self) -> None:
        r"""The program reads one input per line and prints once."""
        program = boolean.collatz_multiverse("0110")
        assert program.count("input") == 2
        assert program.count("DO PRINT.") == 1

    def test_a_dense_table_selects_its_zero_rows(self) -> None:
        r"""More ones than zeros costs less built the other way."""
        dense = boolean.collatz_multiverse("11111110")  # one zero row.
        sparse = boolean.collatz_multiverse("00000001")  # one one row.
        assert len(dense) < len(sparse)
        for table in ("11111110", "00000001"):
            program = boolean.collatz_multiverse(table)
            for combo in range(8):
                bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
                assert run_collatz_multiverse(program, bits) == table[combo]

    def test_constant_tables_collapse_but_still_read(self) -> None:
        r"""A constant table collapses to one output but still reads its inputs."""
        for table in ("0000", "1111"):
            program = boolean.collatz_multiverse(table)
            assert program.count("DO PRINT.") == 1
            assert program.count("input") == 2  # n == 2, read once each.


class TestDecleq:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.decleq(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_decleq(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_branch_normalizes_essential_bits_to_one_and_two(self) -> None:
        r"""Each essential bit gets a 47-step decrement chain, then one branch."""
        program = boolean.decleq("0110")
        cells = [int(tok) for tok in program.split()]
        instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
        # Count a==b>0 instructions:.
        # essential input plus the.
        decs = [ins for ins in instrs if ins[0] == ins[1] and ins[0] > 0]
        assert len(decs) == 47 * 2 + 3
        assert sum(1 for ins in instrs if ins[0] == -1) == 2  # one read each.

    def test_constant_subtrees_fold(self) -> None:
        r"""A constant subtree becomes a leaf instead of branching further."""
        program = boolean.decleq("11110000")
        cells = [int(tok) for tok in program.split()]
        instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
        decs = [ins for ins in instrs if ins[0] == ins[1] and ins[0] > 0]
        # The table depends only on its.
        # still read, but their folded.
        assert len(decs) == 47 + 1
        assert sum(1 for ins in instrs if ins[0] == -1) == 3
        assert len(boolean.decleq("11110000")) < len(boolean.decleq("10101010"))

    def test_folding_leaves_no_dead_cells(self) -> None:
        r"""Every cell is an instruction or live data -- none is filler."""
        for table in ("11111111", "11110000", "11001100"):
            n = len(table).bit_length() - 1
            cells = [int(tok) for tok in boolean.decleq(table).split()]
            zeros_at_end = 0
            for value in reversed(cells[:-2]):  # the two output cells hold.
                if value:
                    break
                zeros_at_end += 1
            assert zeros_at_end == n, f"{table} carries {zeros_at_end - n} dead cells"

    def test_folded_leaves_still_print_correctly(self) -> None:
        r"""Every folded table still prints its entry for every input."""
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
        r"""Every input combination halts or loops per its table entry."""
        program = boolean.point_break(table)
        for combo in range(2**n):
            got = point_break_result(program, _pb_combo_bits(combo, n))
            assert got == table[combo], f"inputs {_pb_combo_bits(combo, n)}"

    @pytest.mark.parametrize("table", _PB_CONSTANTS)
    def test_constant_tables(self, table: str) -> None:
        r"""A constant table skips the tree but still consumes its inputs."""
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
        r"""One read per input, complemented bits, a minterm sum, the template."""
        program = boolean.point_break("0110").splitlines()
        assert program[:3] == ["LET a:=1", "LET b:=?", "LET c:=?"]
        assert program[3:5] == ["LET d:=a-b", "LET e:=a-c"]
        assert sum(":=?" in line for line in program) == 2  # one read per input.
        assert program.count("LET f:=f+g") == 2  # one minterm per 1 row.
        assert program[-3:] == ["POINT loop", "IF h BREAK loop", "END loop"]

    def test_a_dense_table_sums_its_zero_rows(self) -> None:
        r"""More ones than zeros costs less summed the other way."""
        dense = boolean.point_break("11111110").splitlines()
        sparse = boolean.point_break("00000001").splitlines()
        # one minterm each: summing the.
        assert dense.count("LET h:=h+i") == 1
        assert sparse.count("LET h:=h+i") == 1
        # the dense one aliases the.
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


def _depth_zero_labels(program: str) -> list[int]:
    r"""Every ``@$N`` block label at the top level of ``program``."""
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
    r"""Two blocks with one label make the first fire on the way past."""

    # : The smallest table that.
    MINIMAL = "00000000000000010000000100000100"

    def test_the_minimal_colliding_table_computes(self) -> None:
        r"""It raised ``read past the end of input: 5 lines supplied, read 6``."""
        assert boolean.sophie(self.MINIMAL)  # builds, and always did.
        for combo in range(32):
            bits = [(combo >> (4 - i)) & 1 for i in range(5)]
            got = run_sophie(boolean.sophie(self.MINIMAL), [str(b) for b in bits])
            assert got == self.MINIMAL[combo], bits

    def test_the_minimal_table_has_no_duplicate_label(self) -> None:
        r"""Its program carried two ``@$1`` blocks."""
        labels = _depth_zero_labels(boolean.sophie(self.MINIMAL))
        assert len(labels) == len(set(labels)), labels

    @pytest.mark.parametrize("n", [5, 6, 7, 8])
    def test_no_table_collides_at_any_arity(self, n: int) -> None:
        r"""A structural check, so it reaches arities executing cannot afford."""
        rng = random.Random(n)
        tables = ["".join(rng.choice("01") for _ in range(2**n)) for _ in range(20)]
        tables.append("".join(str(int(bin(r).count("1") == 1)) for r in range(2**n)))
        for table in tables:
            labels = _depth_zero_labels(boolean.sophie(table))
            assert len(labels) == len(set(labels)), (n, table)

    def test_a_label_is_never_a_bit_value(self) -> None:
        r"""48 and 49 are what a read leaves behind, so a block cannot own one."""
        for n in (6, 7, 8):
            table = "".join(str(int(bin(r).count("1") == 1)) for r in range(2**n))
            labels = _depth_zero_labels(boolean.sophie(table))
            assert _ASCII_ZERO not in labels
            assert _ASCII_ONE not in labels

    def test_the_scan_can_actually_see_a_duplicate(self) -> None:
        r"""The positive control: a checker that never fires guards nothing."""
        assert _depth_zero_labels("@$1{;}@$1{;}") == [1, 1]
        assert _depth_zero_labels("@$1{@$1{;}}") == [1]  # nested is not top level.
        assert _depth_zero_labels(";@$48{#$48,&}{#$49,&}") == []  # bit tests only.
