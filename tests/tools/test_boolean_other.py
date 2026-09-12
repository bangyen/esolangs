r"""Unit tests for the single-language boolean generators."""

import importlib
import itertools
import random

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools import boolean, laserfuck_layout
from tests.tools.boolean_runners import (
    run_algebraic_programming_language,
    run_between,
    run_clockwise,
    run_container,
    run_cvnc,
    run_fargo,
    run_flowchart,
    run_forbin_boolean,
    run_function_x_y,
    run_inject,
    run_laserfuck,
    run_myscript,
    run_nevermind,
    run_suptiftam,
    run_taglate,
    run_ztoalc,
)


class TestInject:
    r"""The decision tree of ``skipq`` guards over stored input blocks."""

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity.
            ("10", 1),  # NOT.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("1000000000000000", 4),  # AND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.inject(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_inject(program, bits)
            assert got == table[combo] + "\n", f"inputs {bits}"

    def test_every_two_input_table(self) -> None:
        r"""All sixteen two-input tables build and compute their function."""
        for table in ("".join(t) for t in itertools.product("01", repeat=4)):
            program = boolean.inject(table)
            for combo in range(4):
                bits = [str((combo >> (1 - i)) & 1) for i in range(2)]
                got = run_inject(program, bits)
                assert got == table[combo] + "\n", f"{table} inputs {bits}"

    def test_constant_subtrees_are_folded(self) -> None:
        r"""A table ignoring its later inputs costs one test, not ``n``."""
        one_dependency = len(boolean.inject("00001111"))
        parity = len(boolean.inject("01101001"))
        assert one_dependency < parity / 2

    def test_reads_every_input_before_branching(self) -> None:
        r"""The reads are hoisted, so every path consumes exactly ``n`` lines."""
        program = boolean.inject("0001").splitlines()
        reads = [i for i, line in enumerate(program) if line.startswith("readto")]
        first_branch = next(
            i for i, line in enumerate(program) if line.startswith("skipq")
        )
        assert len(reads) == 2, "one readto per input, and no more"
        assert max(reads) < first_branch, "every read precedes every branch"

    def test_every_label_occurs_exactly_twice(self) -> None:
        r"""Inject's labels are strictly two-occurrence: an open and a close."""
        from collections import Counter

        for table in ("01", "0001", "0110", "01101001", "11110000"):
            counts = Counter(
                line
                for line in boolean.inject(table).splitlines()
                if line.endswith(";")
            )
            assert all(v == 2 for v in counts.values()), (table, counts)

    def test_an_input_block_starts_empty(self) -> None:
        r"""An empty block is two *adjacent* delimiters, with nothing between."""
        for n, table in ((1, "01"), (2, "0001"), (3, "01101001")):
            lines = boolean.inject(table).splitlines()
            assert lines[: 2 * n] == [f"i{d};" for d in range(n) for _ in (0, 1)]

    def test_the_tree_collapses_on_the_constant_subtree_alone(self) -> None:
        r"""Depth never terminates the recursion; a constant subtree always."""
        from esolangs.tools.boolean.inject import _tree

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
        # And the tree itself is.
        state = {"leaves": 0, "blocks": 0}
        assert _tree("01101001", 0, 3, state, (0, 1, 2)) == _tree(
            "01101001", 0, 3, {"leaves": 0, "blocks": 0}, (0, 1, 2)
        )


class TestSuptiftam:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity.
            ("10", 1),  # NOT.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("1000000000000000", 4),  # AND4.
            ("1111111111111111", 4),  # constant one.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.suptiftam(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_suptiftam(program, bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_minterm_structure(self) -> None:
        r"""The program reads one row per input and sums the minterms."""
        program = boolean.suptiftam("0001")
        assert program.startswith("sum=0\np=1\nfd mulStep :x")
        assert program.count("%-[read]22%") == 2  # one normalized read per input.
        assert program.count("down(:read:)") == 2
        assert program.endswith("term=sum")

    def test_constant_tables_skip_the_minterms(self) -> None:
        r"""A constant-zero table has no minterm rows at all."""
        program = boolean.suptiftam("0000")
        assert "mulStep(:p:)if(p)" not in program

    def test_a_dense_table_is_summed_over_its_zeros(self) -> None:
        r"""More ones than zeros costs less summed the other way and inverted."""
        assert "term=%-[1]sum%" in boolean.suptiftam("1111")
        assert "mulStep(:p:)if(p)" not in boolean.suptiftam("1111")
        assert "term=sum" in boolean.suptiftam("0001")  # sparse: drawn directly.
        # and both still compute their.
        for table in ("1111", "11111110"):
            n = len(table).bit_length() - 1
            program = boolean.suptiftam(table)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_suptiftam(program, bits) == table[combo]

    def test_bit_names_extend_beyond_the_alphabet(self) -> None:
        r"""Identifiers are alphabetical, so past 'z' the names grow a prefix."""
        from esolangs.tools.boolean.other import _suptiftam_bit

        assert _suptiftam_bit(0) == "b"
        assert _suptiftam_bit(24) == "z"
        assert _suptiftam_bit(25) == "bb"
        assert _suptiftam_bit(49) == "bz"
        assert _suptiftam_bit(50) == "bbb"


class TestForbinBoolean:
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
        program = boolean.forbin(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_forbin_boolean(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_uses_the_lsb_of_each_input(self) -> None:
        r"""Each input is read as 8 bits and only the LSB drives the tree."""
        program = boolean.forbin("01")
        # one 8-variable read, then a.
        assert "i0_0,i0_1,i0_2,i0_3,i0_4,i0_5,i0_6,i0_7 = (in 0);" in program

    def test_constant_subtrees_fold(self) -> None:
        r"""A constant slice returns its answer instead of branching further."""
        assert boolean.forbin("11111111").count("return 0;") == 1
        assert boolean.forbin("11110000").count("return 0;") == 2
        assert boolean.forbin("10010110").count("return 0;") == 8


class TestCvnc:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity.
            ("10", 1),  # NOT.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("1000000000000000", 4),  # AND4.
            ("1111111111111111", 4),  # constant one.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.cvnc(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_cvnc(program, bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_a_table_that_folds_nothing_is_a_full_tree(self) -> None:
        r"""Parity folds nowhere, so it keeps a leaf per row."""
        program = boolean.cvnc("01101001")
        assert program.count("fu") == 8  # one leaf per row.
        assert program.count("\u0270\u030ao") == 7  # one branch per interior node.

    def test_a_constant_table_folds_to_one_leaf_but_keeps_its_reads(self) -> None:
        r"""Folding drops the branches, never the reads."""
        for table in ("00000000", "11111111"):
            program = boolean.cvnc(table)
            assert program.count("so") == 3  # still three inputs consumed.
            assert program.count("\u0270\u030ao") == 0  # nothing left to branch on.
            assert program.count("fu") == 1  # one leaf for the whole table.

    def test_a_one_dependency_table_costs_two_leaves(self) -> None:
        r"""Depending on one input collapses the other two levels."""
        program = boolean.cvnc("11110000")
        assert program.count("fu") == 2
        assert program.count("\u0270\u030ao") == 1  # only the root still branches.
        assert program.count("so") == 3  # three inputs, read once each.
        for combo in range(8):
            bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
            assert run_cvnc(program, bits) == "11110000"[combo]

    def test_folding_shortens_the_program(self) -> None:
        assert len(boolean.cvnc("00000000")) < len(boolean.cvnc("01101001"))

    def test_the_halting_goto_covers_every_arity_the_generator_emits(self) -> None:
        r"""The gadget's reach is the generator's arity bound, and is checked."""
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        reach = module._HALT_REACH  # noqa: SLF001

        # parity is the table that.
        for n in range(1, 9):
            table = "01" * (2**n // 2)
            assert len(boolean.cvnc(table)) < reach, f"n={n}"

    def test_a_program_outgrowing_the_goto_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""The guard raises rather than emitting a self-re-entering program."""
        # ``esolangs.tools.boolean.cvnc`.
        # *function*, so the module has.
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        monkeypatch.setattr(module, "_HALT_REACH", 10)
        with pytest.raises(ValueError, match="outgrew"):
            module.cvnc("01")

    def test_every_leaf_ends_by_halting(self) -> None:
        r"""Without the halting goto a then-arm falls into its own loop end."""
        program = boolean.cvnc("0110")
        assert program.count("\u0279i") == program.count("fu")

    def test_a_zero_input_table_is_refused(self) -> None:
        r"""A one-entry table is a constant, not a function of any input."""
        for bit in ("0", "1"):
            with pytest.raises(ValueError, match="at least one input"):
                boolean.cvnc(bit)

    def test_the_hoisted_build_reorders_a_table_the_stream_order_cannot_fold(
        self,
    ) -> None:
        r"""A table folding only on its *last* input is what the reorder is for."""
        program = boolean.cvnc("10101010")
        assert program.count("fu") == 2  # two leaves, as the reorder.
        assert program.count("ɰ̊o") == 1
        # The unreordered node-read.
        # bottom, so it costs a leaf.
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        unreordered = module._tree("10101010", 0)  # noqa: SLF001
        assert unreordered.count("fu") == 8
        assert len(program) < len(unreordered)

    def test_the_hoisted_build_stores_and_fetches_rather_than_rotating(self) -> None:
        r"""The bridge between read order and test order is the deque's ends."""
        program = boolean.cvnc("10101010")
        # Every input is read once and.
        assert program.count("so") == 3
        assert program.count("som") + program.count("son") == 3
        # The one surviving node.
        assert program.count("cuŋ") + program.count("cuɲ") == 1

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_every_table_computes_its_function(self, n: int) -> None:
        r"""Exhaustive over the stream and reordered paths."""
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            program = boolean.cvnc(table)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_cvnc(program, bits) == table[combo], f"{table} {bits}"

    def test_choosing_between_the_builds_never_grows_a_program(self) -> None:
        r"""The hoist has a price, so it is a candidate and not a replacement."""
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        for value in range(2**8):
            table = bin(value)[2:].zfill(8)
            assert len(boolean.cvnc(table)) <= len(module._tree(table, 0))  # noqa: SLF001
        # and parity specifically keeps.
        assert boolean.cvnc("01101001") == module._tree("01101001", 0)  # noqa: SLF001

    def test_an_unservable_order_is_skipped_rather_than_mispriced(self) -> None:
        r"""The deque serves the unimodal orders; the rest return no program."""
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        # (0, 2, 1, 3) is the smallest.
        assert module._deque_schedule((0, 2, 1, 3)) is None  # noqa: SLF001
        assert module._stored_candidate("0" * 16, (0, 2, 1, 3)) == ""  # noqa: SLF001
        # The identity is always.
        assert module._deque_schedule((0, 1, 2, 3)) is not None  # noqa: SLF001

    @pytest.mark.parametrize(
        ("n", "servable"),
        [(1, 1), (2, 2), (3, 6), (4, 20), (5, 70), (6, 252)],
    )
    def test_the_servable_orders_are_counted_exactly(
        self, n: int, servable: int
    ) -> None:
        r"""How many permutations the deque serves, per arity."""
        module = importlib.import_module("esolangs.tools.boolean.cvnc")

        served = sum(
            1
            for perm in itertools.permutations(range(n))
            if module._deque_schedule(perm) is not None  # noqa: SLF001
        )
        assert served == servable

    def test_a_tie_keeps_the_node_read_tree(self) -> None:
        r"""The hoisted build must be strictly shorter to be taken."""
        from esolangs.tools.boolean.helpers import best_input_order

        module = importlib.import_module("esolangs.tools.boolean.cvnc")

        tied = []
        for value in range(2**8):
            table = bin(value)[2:].zfill(8)
            tree = module._tree(table, 0)  # noqa: SLF001
            hoisted = best_input_order(
                table,
                module._stored_candidate,  # noqa: SLF001
            )
            if hoisted and len(hoisted) == len(tree):
                tied.append(table)
        assert len(tied) == 14
        for table in tied:
            assert boolean.cvnc(table) == module._tree(table, 0)  # noqa: SLF001

    def test_a_served_order_pops_from_the_end_holding_its_input(self) -> None:
        r"""The schedule is not merely non-empty; it is the right one."""
        module = importlib.import_module("esolangs.tools.boolean.cvnc")

        for n in (2, 3, 4):
            for perm in itertools.permutations(range(n)):
                schedule = module._deque_schedule(perm)  # noqa: SLF001
                if schedule is None:
                    continue
                pushes, pops = schedule
                assert len(pushes) == n
                assert len(pops) == n
                held: list[int] = []
                for i, push in enumerate(pushes):
                    if push == module._PUSH_FRONT:  # noqa: SLF001
                        held.insert(0, i)
                    else:
                        held.append(i)
                for wanted, pop in zip(perm, pops, strict=True):
                    if pop == module._FETCH_FRONT:  # noqa: SLF001
                        assert held.pop(0) == wanted, (perm, wanted)
                    else:
                        assert held.pop() == wanted, (perm, wanted)
                assert not held

    def test_a_table_folding_at_its_root_normalizes_the_last_read(self) -> None:
        r"""The hoisted build's folded root still holds an unpredictable bit."""
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        program = module._ordered("00", (0,))  # noqa: SLF001
        assert program is not None
        assert "cə" in program
        for bit in ("0", "1"):
            assert run_cvnc(program, [bit]) == "0"


class TestFargo:
    r"""The Fargo boolean generator: an algebraic normal form, not a tree."""

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_every_table_at_small_arity(self, n: int) -> None:
        r"""Exhaustive: every table, every input combination."""
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            program = boolean.fargo(table)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                got = run_fargo(program, bits)
                assert got == table[combo], f"table {table} inputs {bits}"

    @pytest.mark.parametrize("n", [4, 5, 8])
    def test_higher_arity_tables(self, n: int) -> None:
        r"""The construction is uncapped: no arity limit, no search."""
        rng = random.Random(20260830 + n)
        for _ in range(4):
            table = "".join(rng.choice("01") for _ in range(2**n))
            program = boolean.fargo(table)
            for _ in range(10):
                combo = rng.randrange(2**n)
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_fargo(program, bits) == table[combo]

    def test_constant_tables_need_no_reads(self) -> None:
        r"""A constant table is its degree-zero coefficient alone."""
        assert boolean.fargo("00000000") == "% 0 0\n$\n"
        assert boolean.fargo("11111111") == "% 0 1\n$\n"

    def test_parity_is_one_term_per_input(self) -> None:
        r"""Parity's ANF is the sum of the single-variable terms."""
        assert boolean.fargo("01101001") == "% 0 ^ ^ @ 0 @ 1 @ 10\n$\n"

    def test_parity_grows_linearly_not_exponentially(self) -> None:
        r"""The size tracks algebraic complexity, so parity is O(n log n)."""
        sizes = [
            len(boolean.fargo("".join(str(bin(r).count("1") % 2) for r in range(2**n))))
            for n in (2, 4, 6, 8)
        ]
        gaps = [b - a for a, b in itertools.pairwise(sizes)]
        # Each step of two inputs costs.
        # doubling per input a decision.
        assert all(12 <= gap <= 20 for gap in gaps), f"not linear: {sizes}"
        # A decision tree over n == 8.
        assert sizes[-1] < 100, f"growing too fast: {sizes}"

    def test_a_one_dependency_table_folds(self) -> None:
        r"""One term whatever the arity, which is what the catalogue checks."""
        assert boolean.fargo("11110000") == "% 0 ^ 1 @ 10\n$\n"
        assert len(boolean.fargo("11110000")) < len(boolean.fargo("01101001"))


class TestFlowchart:
    r"""The Flowchart boolean generator (works for arbitrary n)."""

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity.
            ("10", 1),  # NOT.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0001", 2),  # AND.
            ("0111", 2),  # OR.
            ("0110", 2),  # XOR.
            ("1110", 2),  # NAND.
            ("01101001", 3),  # XOR3.
            ("11111110", 3),  # NAND3.
            ("0110100110010110", 4),  # XOR4.
            ("1000000000000000", 4),  # AND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        import contextlib

        from esolangs.interpreters.grid_based.flowchart import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_cycle

        program = boolean.flowchart(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_flowchart(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"
        io = ScriptedIO("0\n" * (n + 4))
        with contextlib.suppress(Exception, SystemExit):
            run_until_halt_or_cycle(_Machine(program.splitlines(), io))
        assert io.position() == n, (
            f"table {table} consumed {io.position()} inputs, expected {n}"
        )

    def test_tree_depth_matches_input_count(self) -> None:
        r"""One ``/ /`` read node sits on each path from entry to a leaf."""
        program = boolean.flowchart("0110100110010110")
        assert program.count("< >") == 15  # 2**4 - 1 internal nodes.
        assert program.count("(( ))") == 16  # 2**4 leaves.

    def test_constant_subtrees_fold(self) -> None:
        r"""A constant slice is one leaf, and takes one column band."""
        assert boolean.flowchart("11111111").count("(( ))") == 1
        assert boolean.flowchart("11110000").count("(( ))") == 2
        assert boolean.flowchart("10010110").count("(( ))") == 8  # no fold.
        # a constant table needs no.
        assert boolean.flowchart("11111111").count("< >") == 0
        assert boolean.flowchart("11110000").count("< >") == 1

    @pytest.mark.parametrize(
        "table", ["01", "0001", "01101001", "0110100110010110", "1000000000000000"]
    )
    def test_vertical_rails_meet_node_middles(self, table: str) -> None:
        r"""Every ``│`` connects to the middle of the node above and below it."""
        from esolangs.interpreters.grid_based.flowchart import _Machine

        machine = _Machine(boolean.flowchart(table).splitlines(), IO())
        for row, line in enumerate(machine.grid):
            for col, char in enumerate(line):
                if char != "│":
                    continue
                for neighbour in (row - 1, row + 1):
                    node = machine.nodes.get((neighbour, col))
                    if node is None:
                        continue
                    spelling, start = node
                    middle = start + len(spelling) // 2
                    assert col == middle, (
                        f"rail at ({col}, {row}) meets {spelling!r} at column {col}, "
                        f"but its middle is column {middle}"
                    )

    def test_each_run_reads_exactly_n_bits(self) -> None:
        r"""The drawn read nodes outnumber the reads any one run performs."""
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
        r"""A table whose length is not a power of two is rejected."""
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.flowchart("011")

    def test_a_width_stacks_the_tree_onto_one_column(self) -> None:
        r"""A narrower drawing is the same tree, separated by rows not columns."""
        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            flat = boolean.flowchart(table)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.flowchart(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 12, 20, wide):
                narrow = boolean.flowchart(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    got = run_flowchart(narrow, [str(b) for b in bits])
                    assert got == table[combo], (table, width, bits)

    def test_stacking_costs_rows_and_stops_tracking_the_table(self) -> None:
        r"""The stacked drawing is ``n + 5`` columns whatever the table."""
        for n in (2, 3, 4):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            flat = boolean.flowchart(table)
            stacked = boolean.flowchart(table, 1)
            assert max(len(row) for row in stacked.splitlines()) == n + 5, n
            assert max(len(row) for row in flat.splitlines()) == 5 * 2**n, n
            assert len(stacked.splitlines()) > len(flat.splitlines()), n
        # A table that folds to a.
        # ``(( ))``, and stacking.
        # of that -- so there the flat.
        # and asking for any width.
        assert boolean.flowchart("1111", 1) == boolean.flowchart("1111")

    def test_a_stacked_corridor_belongs_to_its_depth(self) -> None:
        r"""Depth ``d``'s zero-branch falls down column ``d``, and nothing else."""
        table = "0110100110010110"
        n = 4
        drawing = boolean.flowchart(table, 1)
        rows = drawing.splitlines()
        width = max(len(row) for row in rows)
        grid = [row.ljust(width) for row in rows]
        for x in range(n):
            column = {row[x] for row in grid} - {" "}
            assert column <= set("│┌└─"), (x, column)
        assert "┼" not in drawing, "a rail crossed a corridor"


class TestBetween:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1111111111111111", 4),  # constant one.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.between(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_between(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_structure(self) -> None:
        r"""One declare/read/normalize triplet per input, one branch per node."""
        program = boolean.between("0110")
        lines = program.splitlines()
        assert lines[:3] == ["'0'v.", "[0]i.", "[0]s|[0]c.|"]
        # XOR has no constant slice.
        # every combination keeps its.
        assert lines.count(".x.") == 4

    def test_constant_subtrees_fold(self) -> None:
        r"""A constant slice becomes one leaf instead of branching further."""
        assert boolean.between("11111111").count(".x.") == 1
        assert boolean.between("11110000").count(".x.") == 2
        assert boolean.between("10010110").count(".x.") == 8  # parity: no fold.

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
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1000000000000000", 4),  # AND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.nevermind(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_nevermind(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        r"""A one-input function reads one input and branches on it."""
        program = boolean.nevermind("10")
        assert program.startswith("input,?")
        assert "if,$a,==,0" in program
        assert program.count("endif") == 2

    def test_constant_subtrees_fold(self) -> None:
        r"""A constant slice prints its answer instead of branching further."""
        assert boolean.nevermind("11111111").count("print,") == 1
        assert boolean.nevermind("11110000").count("print,") == 2
        assert boolean.nevermind("10010110").count("print,") == 8  # no fold.


class TestContainer:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # NOT.
            ("10", 1),
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1111111111111111", 4),  # constant one.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.container(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_container(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        r"""The program reads n inputs and keeps one survivor per row."""
        program = boolean.container("0110")
        assert program.startswith("T:\n+1 T>=T")
        assert ":" in program.splitlines()[:4]  # the empty-named reader.
        assert program.count("S") >= 4  # a survivor per row.
        assert program.count("PRINT:") == 1

    def test_dense_tables_evaluate_the_complement(self) -> None:
        r"""A dense table is summed from its zero rows and inverted."""
        lengths = [len(boolean.container("1" * k + "0" * (8 - k))) for k in range(9)]
        assert lengths[4] == max(lengths)  # four ones is the worst case.
        assert lengths == lengths[::-1]  # and the curve is symmetric.

    @pytest.mark.parametrize("table", ["11111110", "11111111", "1110", "0111"])
    def test_complemented_tables_still_compute(self, table: str) -> None:
        r"""The inverted form answers the original table."""
        n = (len(table) - 1).bit_length()
        program = boolean.container(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_container(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"


class TestZtoalc:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("00000001", 3),  # AND3.
            ("01101001", 3),  # XOR3.
            ("1111111100000000", 4),  # top half.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.ztoalc_l(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_ztoalc(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to two inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.ztoalc_l(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert run_ztoalc(program, [str(b) for b in bits]) == table[combo]

    def test_structure(self) -> None:
        r"""The program is a branch-free array lookup on a Collatz trajectory."""
        program = boolean.ztoalc_l("0110")
        lines = program.splitlines()
        assert lines[0].strip().isdigit()  # line 1 is the starting value.
        assert any(line.strip().startswith("t = [") for line in lines)
        assert any(line.strip().startswith("print") for line in lines)
        # The construction branches on.
        assert not any("jump" in line for line in lines)

    def test_commands_are_placed_without_collisions(self) -> None:
        r"""Every command occupies its own line, in trajectory order."""
        from esolangs.tools.boolean.ztoalc_l import _commands, _slots

        for table in ("0110", "1010001000011000", "0110100110010110"):
            n = len(table).bit_length() - 1
            cmds = _commands(table, n)
            program = boolean.ztoalc_l(table)
            start, slots = _slots(len(cmds))
            assert len(set(slots)) == len(slots), table
            assert 1 not in slots, table
            emitted = program.splitlines()
            assert int(emitted[0]) == start, table
            assert [emitted[v - 1] for v in slots] == cmds, table

    def test_the_slots_are_the_smallest_usable_values(self) -> None:
        r"""Placement takes the L smallest values, so size is minimal."""
        from esolangs.tools.boolean.ztoalc_l import (
            _MAX_LINES,
            _slots,
            _usable_values,
        )

        for length in (8, 23, 199, 329):
            start, slots = _slots(length)
            usable = _usable_values(start, _MAX_LINES)
            assert len(slots) == length
            assert sorted(slots) == sorted(usable)[:length]
            visit_order = {v: i for i, v in enumerate(usable)}
            assert [visit_order[v] for v in slots] == sorted(
                visit_order[v] for v in slots
            )

    def test_xor4_is_small(self) -> None:
        r"""XOR4 renders compactly, where the old linear fallback was huge."""
        table = "0110100110010110"
        program = boolean.ztoalc_l(table)
        assert len(program.splitlines()) < 1000
        for combo in range(16):
            bits = [str((combo >> (3 - i)) & 1) for i in range(4)]
            assert run_ztoalc(program, bits) == table[combo], f"inputs {bits}"

    def test_dense_non_symmetric_table(self) -> None:
        r"""A dense non-symmetric table renders; it once could not be placed."""
        table = "1010001000011000"
        program = boolean.ztoalc_l(table)
        for combo in range(16):
            bits = [str((combo >> (3 - i)) & 1) for i in range(4)]
            assert run_ztoalc(program, bits) == table[combo], f"inputs {bits}"

    def test_constant_table_skips_the_lookup(self) -> None:
        r"""A constant table prints its constant, still draining its inputs."""
        for n, bit in ((2, "0"), (3, "1")):
            table = bit * (2**n)
            program = boolean.ztoalc_l(table)
            assert "t = [" not in program
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_ztoalc(program, bits) == bit

    def test_zero_input_table_is_refused(self) -> None:
        r"""A single-entry table is a constant, not a function of any input."""
        for bit in ("0", "1"):
            with pytest.raises(ValueError, match="at least one input"):
                boolean.ztoalc_l(bit)

    def test_table_past_the_anchor_capacity_is_refused(self) -> None:
        r"""A table needing more slots than any committed anchor is refused."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.ztoalc_l")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "ANCHORS", [(1, 2), (8, 6)])
            with pytest.raises(ValueError, match="committed anchors offer"):
                module.ztoalc_l("0110")

    def test_a_lower_line_ceiling_shrinks_the_capacity(self) -> None:
        r"""Tightening ``_MAX_LINES`` removes slots, not just lines."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.ztoalc_l")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_MAX_LINES", 8)
            with pytest.raises(ValueError, match="at or below 8"):
                module.ztoalc_l("0110")

    def test_the_anchor_fits_a_length_landing_on_its_capacity(self) -> None:
        r"""A capacity bound is inclusive: ``capacity == length`` still fits."""
        from esolangs.tools.boolean.ztoalc_l import _commands, _slots

        assert len(_commands("0" * 128, 7)) == 8
        assert _slots(8)[0] == 6
        assert _slots(9)[0] == 18
        # The smallest anchor, to show.
        assert _slots(1)[0] == 2

    def test_the_refusal_names_the_length_and_the_capacity(self) -> None:
        r"""The refusal reports the request and the committed ceiling."""
        from esolangs.tools.boolean.ztoalc_l import (
            _MAX_LINES,
            _slots,
            _usable_values,
        )
        from esolangs.tools.ztoalc_starts import ANCHORS

        capacity = max(len(_usable_values(s, _MAX_LINES)) for _, s in ANCHORS)
        assert capacity == 386  # start 511935; the sieved.
        with pytest.raises(ValueError, match="committed anchors offer") as caught:
            _slots(capacity + 1)
        assert str(caught.value) == (
            f"the ZTOALC L boolean generator needs {capacity + 1} command "
            f"lines at or below {_MAX_LINES}; the committed anchors offer "
            f"at most {capacity}"
        )

    def test_lines_off_the_slots_are_left_empty(self) -> None:
        r"""A line no command lands on is blank, not filler."""
        from esolangs.tools.boolean.ztoalc_l import _commands, _slots

        table = "0110"
        program = boolean.ztoalc_l(table)
        lines = program.splitlines()
        _, slots = _slots(len(_commands(table, 2)))
        occupied = {v - 1 for v in slots} | {0}
        assert len(lines) == max(slots)
        assert [i for i, ln in enumerate(lines) if ln != ""] == sorted(occupied)
        assert all(lines[i] == "" for i in range(len(lines)) if i not in occupied)

    def test_the_arrays_are_declared_at_exactly_their_domains(self) -> None:
        r"""``t`` holds one slot per chunk and ``u`` one per code, no more."""
        for table, n in (("0110", 2), ("00010111", 3), ("1010001000011000", 4)):
            program = boolean.ztoalc_l(table)
            assert f"t = [{2 ** (n - 2)}]" in program, table
            assert "u = [16]" in program, table

    def test_a_chunk_set_carries_four_rows_in_one_command(self) -> None:
        r"""The init block spends one command per nonzero chunk, not per row."""
        from esolangs.tools.boolean.ztoalc_l import _commands

        for n in (2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                if len(set(table)) == 1:
                    continue
                cmds = _commands(table, n)
                chunks = [table[c * 4 : (c + 1) * 4] for c in range(2 ** (n - 2))]
                sets = [c for c in cmds if c.startswith("t[")]
                assert len(sets) == sum(1 for c in chunks if "1" in c), table
                assert len(sets) <= 2 ** (n - 2), table

    def test_the_decode_block_builds_each_code_once(self) -> None:
        r"""``u`` gets one entry per *distinct* chunk code, zero included."""
        from esolangs.tools.boolean.ztoalc_l import _commands

        cmds = _commands("01101001", 3)  # parity: chunks 0110, 1001.
        assert [c for c in cmds if c.startswith("u = ")] == ["u = [16]"]
        assert [c for c in cmds if c.startswith("u[") and "= [" in c] == [
            "u[6] = [4]",
            "u[9] = [4]",
        ]

        cmds = _commands("00000001", 3)  # a zero chunk forces u[0].
        assert "u[0] = [4]" in cmds
        assert [c for c in cmds if c.startswith("t[")] == ["t[1] = 1"]

    def test_ten_inputs_build_and_answer(self) -> None:
        r"""Parity at ten inputs builds and answers spot rows correctly."""
        table = "".join(str(bin(i).count("1") % 2) for i in range(1024))
        program = boolean.ztoalc_l(table)
        assert len(program.splitlines()) <= 2**22
        for combo in (0, 1, 5, 137, 512, 682, 1000, 1023):
            bits = [str((combo >> (9 - i)) & 1) for i in range(10)]
            assert run_ztoalc(program, bits) == table[combo], combo

    def test_wrong_length_rejected(self) -> None:
        r"""A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.ztoalc_l("011")

    def test_invalid_chars_rejected(self) -> None:
        r"""A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.ztoalc_l("02")


class TestClockwise:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),
            ("10", 1),
            ("00", 1),
            ("11", 1),
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("00000001", 3),  # AND3.
            ("1000000000000000", 4),  # AND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination prints the result as an ASCII digit."""
        program = boolean.clockwise(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_clockwise(program, bits)
            assert got == table[combo], f"inputs {bits}"

    def test_ring_starts_at_origin(self) -> None:
        r"""The program is a closed ring whose pointer starts at (0, 0)."""
        program = boolean.clockwise("0110")
        lines = program.splitlines()
        assert lines[0][0] == " "
        assert run_clockwise(program, ["1", "0"]) == "1"  # XOR(1, 0).

    @pytest.mark.parametrize(("table", "n"), [("0001", 2), ("01101001", 3)])
    def test_tree_sits_against_the_left_edge(self, table: str, n: int) -> None:
        r"""No column is dead: the spine starts as far left as it can."""
        program = boolean.clockwise(table)
        rows = program.splitlines()
        width = max(len(row) for row in rows)
        grid = [row.ljust(width) for row in rows]
        dead = [x for x in range(width) if all(row[x] == " " for row in grid)]
        assert not dead, f"dead columns {dead}"
        assert width == 2 ** (n + 1) + 1

    def test_constant_subtrees_narrow_the_ring(self) -> None:
        r"""A folded subtree spends no displacement, so the grid narrows."""
        scattered = boolean.clockwise("10010110")
        for table in ("11111111", "11110000"):
            folded = boolean.clockwise(table)
            assert len(folded) < len(scattered), table
        assert len(boolean.clockwise("11001100")) < len(scattered)

    def test_folded_column_still_reads_every_input(self) -> None:
        r"""A folded column keeps the reads it skipped branching on."""
        for table in ("11111111", "11110000", "11001100"):
            n = len(table).bit_length() - 1
            program = boolean.clockwise(table)
            rows = program.splitlines()
            width = max(len(row) for row in rows)
            grid = [row.ljust(width) for row in rows]
            columns = [sum(1 for row in grid if row[x] == ".") for x in range(width)]
            # the deepest column reads.
            assert max(columns) <= 7 * n, table
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_clockwise(program, bits) == table[combo], (table, bits)

    def test_folding_never_grows_the_program(self) -> None:
        r"""The hoist floor: narrowing must not cost more than it saves."""
        for n in (1, 2, 3):
            # the alternating table folds.
            # full-size program every other.
            unfolded = len(boolean.clockwise("10" * (2 ** (n - 1))))
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                assert len(boolean.clockwise(table)) <= unfolded, table

    def test_a_width_stacks_the_tree_and_it_still_computes(self) -> None:
        r"""A narrower ring is the same function, laid out down instead of."""
        for table in ("01101001", "0110100110010110", "00010111"):
            n = len(table).bit_length() - 1
            flat = boolean.clockwise(table)
            wide = max(len(row) for row in flat.splitlines())
            for width in (8, 10, 14, 20):
                narrow = boolean.clockwise(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                floor = max(
                    len(row) for row in boolean.clockwise(table, 1).splitlines()
                )
                assert columns <= max(width, floor), (table, width, columns)
                if columns < wide:
                    assert len(narrow.splitlines()) > len(flat.splitlines()), (
                        f"{table} at {width} narrowed without spending rows"
                    )
                for combo in range(2**n):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    assert run_clockwise(narrow, bits) == table[combo], (
                        table,
                        width,
                        bits,
                    )

    def test_stacked_leaves_leave_by_rows_of_their_own(self) -> None:
        r"""A stacked tree's leaves finish on different rows, and column 0."""
        table = "01101001"
        flat = boolean.clockwise(table)
        stacked = boolean.clockwise(table, 10)

        def exit_rows(program: str) -> list[int]:
            rows = program.splitlines()
            return sorted({y for y, row in enumerate(rows) if row[:1] == "!"})

        assert len(exit_rows(flat)) == 1, "a flat ring closes through one row"
        assert len(exit_rows(stacked)) > 1, "stacking must spread the exits"
        for y in exit_rows(stacked):
            assert stacked.splitlines()[y - 1][:1] == "+", (
                f"exit row {y} has no '+' above it to re-arm the climb"
            )


class TestTaglate:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("00", 1),
            ("01", 1),
            ("10", 1),
            ("11", 1),
            ("0001", 2),  # AND.
            ("0110", 2),  # XOR.
            ("1110", 2),  # NAND.
            ("00000001", 3),  # majority.
            ("0000000000000001", 4),  # 4-AND.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            # Odd n > 1 uses a ghost digit.
            inputs = (
                ["0"] + [str(b) for b in bits]
                if n % 2 == 1 and n > 1
                else [str(b) for b in bits]
            )
            got = run_taglate(program, inputs)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        r"""Every two-input truth table produces the right result."""
        for table in range(16):
            tt = format(table, "04b")
            for combo in range(4):
                bits = [(combo >> 1) & 1, combo & 1]
                got = run_taglate(boolean.taglate(tt), [str(b) for b in bits])
                assert got == tt[combo], f"{tt} inputs {bits}"

    def test_all_three_input_tables(self) -> None:
        r"""Every three-input truth table produces the right result."""
        failures = 0
        for table in range(256):
            tt = format(table, "08b")
            program = boolean.taglate(tt)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                inputs = ["0"] + [str(b) for b in bits]  # ghost digit.
                got = run_taglate(program, inputs)
                if got != tt[combo]:
                    failures += 1
                    if failures <= 3:
                        print(
                            f"  FAIL {tt} inputs {bits}: "
                            f"got {got!r} expected {tt[combo]!r}"
                        )
        assert failures == 0, f"{failures} failures out of 2048 combos"

    def test_tables_ignoring_inputs_shrink(self) -> None:
        r"""A table that ignores inputs is emitted as the smaller table."""
        full = len(boolean.taglate("10010110"))  # depends on all three.
        for table in ("11110000", "11001100", "10101010", "00000000"):
            assert len(boolean.taglate(table)) < full // 10, table

    def test_gapped_dependencies_reduce_without_reordering_inputs(self) -> None:
        r"""Every n=3 function of inputs 0 and 2 uses the small program."""
        tables = (
            "00000101",
            "00001010",
            "01010000",
            "01011010",
            "01011111",
            "10100000",
            "10100101",
            "10101111",
            "11110101",
            "11111010",
        )
        full = len(boolean.taglate("10010110"))
        for table in tables:
            program = boolean.taglate(table)
            assert len(program) < full, table
            assert program.count("h") == 4, table  # ghost plus all three inputs.
            for combo in range(8):
                bits = [str((combo >> shift) & 1) for shift in (2, 1, 0)]
                assert run_taglate(program, ["0", *bits]) == table[combo], (table, bits)

    def test_reduced_programs_still_read_every_input(self) -> None:
        r"""A reduced program consumes the inputs it no longer uses."""
        for n in (1, 2, 3, 4):
            expected = n + (1 if n % 2 == 1 and n > 1 else 0)
            for table in (
                "1" * 2**n,
                "1" * 2 ** (n - 1) + "0" * 2 ** (n - 1),
                ("10" * 2**n)[: 2**n],
            ):
                program = boolean.taglate(table)
                assert program.count("h") == expected, (n, table)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("1111111100000000", 4),  # depends on input 0.
            ("1111000011110000", 4),  # input 1.
            ("1010101010101010", 4),  # input 3.
            ("1111111111111111", 4),  # none at all.
        ],
    )
    def test_reduced_tables_compute_past_three_inputs(self, table: str, n: int) -> None:
        r"""The reduction stays correct deeper than the exhaustive sweep."""
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            ghost = ["0"] if n % 2 == 1 and n > 1 else []
            got = run_taglate(program, ghost + [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            # depends on inputs 0-2, so the.
            ("0000000000000011", 4),
            # depends on inputs 1-3, which.
            # window widens leftward to 0-3.
            ("0000000100000001", 4),
        ],
    )
    def test_odd_dependency_sets_widen_to_stay_even(self, table: str, n: int) -> None:
        r"""An odd-sized window takes one more ignored input, either side."""
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            ghost = ["0"] if n % 2 == 1 and n > 1 else []
            got = run_taglate(program, ghost + [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    def test_wrong_length_truth_table_rejected(self) -> None:
        r"""A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.taglate("011")

    def test_invalid_truth_table_chars_rejected(self) -> None:
        r"""A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.taglate("0120")


class TestThreeX:
    def test_identity_program_structure(self) -> None:
        r"""The 01 table reads a bit and stores it before printing."""
        program = boolean.three_x("01")
        assert program.startswith("?")
        assert program.endswith("!")

    def test_reordering_only_shrinks(self) -> None:
        r"""No table comes out longer than the identity order's program."""
        from esolangs.tools.boolean.other import _three_x_ordered

        for i in range(256):
            table = format(i, "08b")
            identity = _three_x_ordered(table, (0, 1, 2))
            assert len(boolean.three_x(table)) <= len(identity)

    def test_unimproved_tables_keep_their_emission(self) -> None:
        r"""A table no reorder helps emits exactly what it emitted before."""
        from esolangs.tools.boolean.other import _three_x_ordered

        for table in ("0" * 8, "1" * 8):
            assert boolean.three_x(table) == _three_x_ordered(table, (0, 1, 2))

    def test_reads_stay_in_stream_order(self) -> None:
        r"""Only the store target moves, so the input stream is consumed the."""
        from esolangs.tools.boolean.other import _three_x_ordered

        table = "00010111"
        for perm in ((0, 1, 2), (2, 1, 0), (1, 2, 0)):
            program = _three_x_ordered(table, perm)
            head = program[: program.index("(")] if "(" in program else program
            assert head.count("?") == 3
            # the reads are the first thing.
            assert program.startswith("?")

    def test_every_input_order_computes_the_table(self) -> None:
        r"""The permuted build computes the original table on the original."""
        import itertools

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.three_x import run
        from esolangs.tools.boolean.other import _three_x_ordered

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
        r"""A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.three_x("011")

    def test_invalid_truth_table_chars_rejected(self) -> None:
        r"""A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.three_x("02")

    def test_uses_input_variables(self) -> None:
        r"""Each input bit is read into a distinct variable."""
        program = boolean.three_x("0001")
        assert program.count("?") == 2
        assert "333x" in program  # the constant-0 encoding.
        assert "3333x3x" in program  # the constant-1 encoding.

    def test_constant_table_has_no_override_blocks(self) -> None:
        r"""When every row equals the default, no ( ."""
        assert "(" not in boolean.three_x("0" * 4)
        assert "(" not in boolean.three_x("1" * 4)

    def test_majority_default_handles_zero_row(self) -> None:
        r"""A zero row differing from a majority-1 default still overrides it."""
        program = boolean.three_x("0110")  # XOR: two 1s, two 0s.
        assert program.startswith("?")
        assert program.endswith("!")
        assert "(" in program  # the zero row needs an.

    def test_scales_to_more_inputs(self) -> None:
        r"""The generator handles n beyond the built-in constants."""
        program = boolean.three_x("0" * (2**7))
        assert program.count("?") == 7

    def test_shared_tree_prefix_sharing(self) -> None:
        r"""Differing combos share prefix guards instead of repeating them."""
        # top-half n=5: 16 zero-rows.
        # 31 guard nodes; independent.
        program = boolean.three_x("0" * 16 + "1" * 16)
        assert program.count("(") < 40

    def test_digit_constant_encodings(self) -> None:
        r"""The base-3 digit seeds are the closed-form minimal programs."""
        from esolangs.tools.boolean import other

        assert other._const(0) == "333x"  # noqa: SLF001
        assert other._const(1) == "3333x3x"  # noqa: SLF001
        assert other._const(2) == "3333x3x3333x3x3x"  # noqa: SLF001

    def test_base_three_digits_accumulate(self) -> None:
        r"""Each base-3 digit past the first appends the 3v+d affine step."""
        from esolangs.tools.boolean import other

        # 12 is "110" in base 3: seed.
        # adds exactly one `#` (the.
        twelve = other._const(12)  # noqa: SLF001
        assert twelve.startswith(other._const(1))  # noqa: SLF001
        assert twelve.count("#") == 2

    def test_formula_scales_logarithmically(self) -> None:
        r"""The closed form grows with the digit count, not the value."""
        from esolangs.tools.boolean import other

        small, large = other._const(100), other._const(1_000_000)  # noqa: SLF001
        assert len(small) < 120  # 100 is "10201": 5 digits.
        assert len(large) < 350  # 1_000_000 is 13 base-3 digits.
        assert len(large) < len(small) * 4


class TestLaserFuck:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("00000001", 3),  # AND3.
            ("1111111100000000", 4),  # top half.
            ("0110100110010110", 4),  # XOR4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.laserfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == str(int(table[combo])), f"inputs {bits} heading {heading}"

    # n=3 is 256 tables at 2.0s,.
    # n=1 and n=2 are 16 tables.
    @pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.slow)])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.laserfuck(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_laserfuck(program, [str(b) for b in bits], 3)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_funnel_is_heading_independent(self) -> None:
        r"""Every initial heading reaches the tree on the top row."""
        program = boolean.laserfuck("0110")
        for heading in range(4):
            assert run_laserfuck(program, ["1", "0"], heading) == "1"

    def test_input_reordering_folds_a_scattered_table(self) -> None:
        r"""The tree splits in whichever order folds most, not input order."""
        scattered = len(boolean.laserfuck("10101010"))
        aligned = len(boolean.laserfuck("11110000"))
        parity = len(boolean.laserfuck("01101001"))
        assert scattered == aligned
        assert aligned < parity

    def test_input_reordering_never_grows_a_program(self) -> None:
        r"""The identity order is built first and ties keep it."""
        assert ",>,>," in boolean.laserfuck("01101001")

    def test_wide_tables_do_not_search_every_order(self) -> None:
        r"""Past the cap only the identity order is built, not ``n!`` of them."""
        import importlib

        # The package re-exports the.
        # name, so import the module.
        module = importlib.import_module("esolangs.tools.boolean.laserfuck")
        real = module._laserfuck_build  # noqa: SLF001

        for n, table, orders in (
            (3, "01011010", 6),
            (7, ("10" * 64)[:128], 1),
        ):
            built = 0

            def counted(*args: object, _build: object = real, **kwargs: object) -> str:
                nonlocal built
                built += 1
                return _build(*args, **kwargs)  # type: ignore[operator, no-any-return]

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(module, "_laserfuck_build", counted)
                boolean.laserfuck(table)
            assert built == orders, f"n={n} built {built} candidates"

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_reordered_programs_compute_the_table(self, table: str) -> None:
        r"""A reordered program still computes its function, at every heading."""
        program = boolean.laserfuck(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == table[combo], f"{table} inputs {bits} heading {heading}"

    def test_reordering_keeps_the_reads_in_stream_order(self) -> None:
        r"""Reordering moves where a bit is stored, never when it is read."""
        for table in ("10101010", "11110000", "01101001"):
            assert boolean.laserfuck(table).count(",") == 3

    def test_decimal_output_mode(self) -> None:
        r"""No ``\xff`` marker, so the tape dumps as numbers, not bytes."""
        program = boolean.laserfuck("10")
        assert program.splitlines()[0][0] != "\u00ff"
        assert "\u00ff" not in program

    def test_prints_only_the_answer(self) -> None:
        r"""The dump is exactly the result: no input cells, no separators."""
        program = boolean.laserfuck("0001")  # AND2.
        for bits, want in (([0, 1], "0"), ([1, 1], "1")):
            got = run_laserfuck(program, [str(b) for b in bits], 3)
            assert got == want, f"inputs {bits}"

    def test_loop_free_tree(self) -> None:
        r"""The decision tree branches with #, ) and a turning mirror."""
        program = boolean.laserfuck("0110")
        assert "#" in program
        assert ")" in program
        # the tree is mirrored, so a.
        assert "/" in program

    @pytest.mark.parametrize(
        ("table", "n", "width"),
        [
            # The tree is never folded and.
            # narrowest width a table can.
            # roughly 19, 34, and 63.
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
        r"""``width`` bounds the columns and the table still computes."""
        program = boolean.laserfuck(table, width)
        assert max(len(line) for line in program.split("\n")) <= width
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == str(int(table[combo])), f"{bits} heading {heading}"

    def test_a_width_stands_the_reader_on_end(self) -> None:
        r"""A width too narrow for the reader rotates it rather than failing."""
        table = "01101001"  # XOR3.
        natural = max(len(ln) for ln in boolean.laserfuck(table).split("\n"))
        assert natural > 30
        narrow = boolean.laserfuck(table, 30).split("\n")
        assert max(len(ln) for ln in narrow) <= 30
        assert len(narrow) > len(boolean.laserfuck(table).split("\n"))

    def test_the_fold_uses_its_return_rows(self) -> None:
        r"""A same-character run fills the leftward leg, not just the right."""
        grid = [[" "] * 20 for _ in range(2)]
        end_row, end_col = laserfuck_layout.fold(grid, "-" * 30, 0, 3, 20)
        rows = ["".join(line).rstrip() for line in grid]
        assert rows[0].endswith("v")
        assert rows[1].endswith("{")
        assert "-" in rows[1], "the return row should carry the spilled run"
        # 30 ops at width 20: 16 on the.
        # the return row, so the run.
        assert end_row == 2, "a same-character run should not need a third row"
        assert end_col == laserfuck_layout.MARGIN + 1

    def test_return_rows_only_take_a_same_character_run(self) -> None:
        r"""The fill stops at the first character that differs."""
        grid = [[" "] * 20 for _ in range(2)]
        laserfuck_layout.fold(grid, "-" * 30 + ">+++", 0, 3, 20)
        rows = ["".join(line).rstrip() for line in grid]
        body = rows[1][laserfuck_layout.MARGIN + 1 :].rstrip()
        ops = body[:-1].strip() if body.endswith("{") else body.strip()
        assert set(ops) <= {"-"}, f"mixed ops on a return row: {ops!r}"
        # the '>' that broke the run.
        assert ">" in rows[2]

    def test_folded_readers_are_rings(self) -> None:
        r"""The folded reader loops rather than writing 48 '-' per input."""
        rows = boolean.laserfuck("0110", 80).split("\n")
        # columns 0..2 are the funnel;.
        head = rows[0][laserfuck_layout.MARGIN :]
        legs = rows[1][laserfuck_layout.MARGIN :]
        assert head.count("}") == 3, "the reader's own '}' plus one per ring"
        assert head.count("#/)") == 2, "each ring tests its counter"
        assert legs.count("^") == 2, "each ring returns to its own '}'"
        # no 48-'-' run survives.
        assert "-" * 10 not in "\n".join(rows)

    def test_ringed_leaves_sit_on_their_own_descent_rows(self) -> None:
        r"""A leaf needs no corridor: the beam already arrives moving right."""
        # width 50 forces the mirrored.
        rows = boolean.laserfuck("0110", 50).split("\n")
        # 'x' only ever ends a leaf, so.
        leaves = [line for line in rows if "x" in line]
        assert len(leaves) == 4, "one leaf per input combination"
        # the all-zero leaf rides the.
        # mirrored, a one-branch's leaf.
        # leftward, so the 'x' comes.
        # shares the tree's first row,.
        first = min(index for index, line in enumerate(rows) if "x" in line)
        turned = [
            line for index, line in enumerate(rows) if "x" in line and index > first
        ]
        assert len(turned) == 3
        for line in turned:
            assert line.index("x") < line.index("/")
        # nothing below the leaves: no.
        # a leaf's row ends at its turn.
        assert rows[-1].rstrip()[-1] in "x/"

    def test_a_dropping_beam_crosses_no_other_row_s_code(self) -> None:
        r"""A one-branch drops through the rows above its own catcher."""
        for table in ("0110", "01101001", "0110100110010110"):
            rows = boolean.laserfuck(table, 200).split("\n")
            for index, line in enumerate(rows):
                for column, char in enumerate(line):
                    if char != "v" or index < 3:
                        continue  # the funnel and reader steer.
                    # find the '\' that catches.
                    below = [
                        (k, rows[k])
                        for k in range(index + 1, len(rows))
                        if column < len(rows[k])
                    ]
                    for k, lower in below:
                        cell = lower[column]
                        if cell in "\\/":
                            break  # caught, as intended.
                        assert cell == " ", (
                            f"{table}: beam from row {index} column {column} "
                            f"runs {cell!r} on row {k}"
                        )

    def test_a_wide_grid_runs_the_tree_on_the_reader_s_rows(self) -> None:
        r"""Given the width, the tree needs no rows of its own at all."""
        wide = boolean.laserfuck("0110", 80).split("\n")
        narrow = boolean.laserfuck("0110", 50).split("\n")
        assert len(wide) < len(narrow), "sharing rows should cost fewer rows"
        assert max(len(line) for line in wide) > max(len(line) for line in narrow)
        # the reader's own first row.
        assert "#/)" in wide[0], "the reader's last ring is on row 0"
        assert ">#v)" in wide[0], "and the tree's first node follows it there"

    def test_widths_come_in_bands_not_a_cliff(self) -> None:
        r"""Each reader block turns on its own, so widths degrade gradually."""
        seen = {
            max(len(line) for line in boolean.laserfuck("0110", width).split("\n"))
            for width in (45, 40, 30, 25, 18)
        }
        assert len(seen) >= 4, f"expected several distinct widths, got {seen}"
        # asking for less never gives.
        widths = [
            max(len(line) for line in boolean.laserfuck("0110", w).split("\n"))
            for w in (45, 40, 30, 25, 18)
        ]
        assert widths == sorted(widths, reverse=True)

    @pytest.mark.parametrize(
        ("table", "rows", "columns"),
        [
            ("01", 3, 44),
            ("0001", 3, 56),
            ("0110", 4, 56),
            ("11111110", 4, 68),
            ("01101001", 8, 68),
        ],
    )
    def test_the_grid_has_exact_dimensions(
        self, table: str, rows: int, columns: int
    ) -> None:
        r"""The drawing's extents, pinned."""
        grid = boolean.laserfuck(table).split("\n")
        assert len(grid) == rows
        assert max(len(line) for line in grid) == columns

    @pytest.mark.parametrize(
        ("width", "rows", "columns"),
        [
            (18, 47, 18),
            (19, 36, 18),
            (27, 28, 26),
            (28, 25, 27),
            (35, 17, 34),
            (44, 6, 43),
        ],
    )
    def test_the_width_steps_land_where_they_should(
        self, width: int, rows: int, columns: int
    ) -> None:
        r"""XOR's layout at each width where the fit decision changes."""
        grid = boolean.laserfuck("0110", width).split("\n")
        assert len(grid) == rows
        assert max(len(line) for line in grid) == columns

    @pytest.mark.parametrize(
        ("table", "flip", "narrow", "wide"),
        [
            ("11111110", 69, (6, 49), (4, 68)),
            ("01101001", 71, (10, 51), (8, 68)),
        ],
    )
    def test_the_straight_layout_starts_at_its_exact_width(
        self,
        table: str,
        flip: int,
        narrow: tuple[int, int],
        wide: tuple[int, int],
    ) -> None:
        r"""One comparison chooses between the two whole layouts."""
        below = boolean.laserfuck(table, flip - 1).split("\n")
        assert (len(below), max(len(line) for line in below)) == narrow

        at = boolean.laserfuck(table, flip).split("\n")
        assert (len(at), max(len(line) for line in at)) == wide

        # At the flip the constraint.
        # unconstrained build.
        free = boolean.laserfuck(table).split("\n")
        assert (len(free), max(len(line) for line in free)) == wide

    def test_the_grid_uses_only_laserfuck_characters(self) -> None:
        r"""Nothing but the language's own glyphs and layout space."""
        allowed = set(" #)+,-/<>\\^_ovx{|}\n")
        for table in ("01", "0110", "0001", "01101001", "11111110"):
            assert set(boolean.laserfuck(table)) <= allowed, table

    def test_no_row_carries_trailing_space(self) -> None:
        r"""Rows are trimmed, so the grid's width is its content's width."""
        for table in ("01", "0110", "01101001"):
            for row in boolean.laserfuck(table).split("\n"):
                assert row == row.rstrip(), (table, repr(row))

    def test_a_narrow_width_beats_the_old_floor(self) -> None:
        r"""Standing blocks on end reaches widths the flat reader cannot."""
        for table, floor in (("0110", 18), ("01101001", 24)):
            program = boolean.laserfuck(table, floor).split("\n")
            assert max(len(line) for line in program) <= floor

    def test_ringed_leaves_leave_a_zero_answer_alone(self) -> None:
        r"""Cell 0 is the counter *and* the answer, so zero costs nothing."""
        zero = boolean.laserfuck("0000", 80)
        ones = boolean.laserfuck("1111", 80)
        assert ones.count("+") == zero.count("+") + 1, "a one costs exactly one '+'"

    def test_constant_subtrees_fold(self) -> None:
        r"""A constant slice becomes one leaf instead of branching further."""
        assert boolean.laserfuck("11111111").count("x") == 1
        assert boolean.laserfuck("11110000").count("x") == 2
        assert boolean.laserfuck("10010110").count("x") == 8

    def test_a_table_that_folds_nothing_keeps_the_sized_sweep(self) -> None:
        r"""Parity's leaves retire each input by its own bit, not flatly."""
        program = boolean.laserfuck("10010110")
        leaves = program.split("x")[:-1]
        for path in range(8):
            bits = [(path >> (2 - i)) & 1 for i in range(3)]
            want = "".join("-" * (b + 1) + "<" for b in reversed(bits))
            assert any(leaf.endswith(want) or want in leaf for leaf in leaves), (
                f"no leaf retires {bits} with its sized run {want!r}"
            )

    def test_without_a_width_is_unchanged(self) -> None:
        r"""The default stays exactly what the generator always produced."""
        for table in ("01", "10", "0110", "01101001"):
            assert boolean.laserfuck(table) == boolean.laserfuck(table, None)

    def test_too_narrow_a_width_is_ignored(self) -> None:
        r"""A width the tree cannot fit in is ignored rather than raising."""
        program = boolean.laserfuck("01101001", 8)
        assert run_laserfuck(program, ["0", "0", "0"], 3) == "0"


class TestMyScript:
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
            ("1000000000000000", 4),  # AND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.myscript(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_myscript(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_subtrees_fold(self) -> None:
        r"""A constant slice says its answer instead of branching further."""
        assert boolean.myscript("11111111").count("say") == 1
        assert boolean.myscript("11110000").count("say") == 2
        assert boolean.myscript("10010110").count("say") == 8  # parity: no fold.


class TestGeneratorEdgePaths:
    r"""Coverage for validation and helper edge paths in the generators."""

    def test_parameterized_validation(self) -> None:
        r"""bio/back reject malformed truth tables."""
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.bio("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            parameterized.bio("0123")
        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.back("011")

    def test_dimensional_tree_validation(self) -> None:
        r"""The Dimensional decision-tree generator rejects bad truth tables."""
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.dimensional_tree("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.dimensional_tree("0123")

    def test_six_five_helper_edges(self) -> None:
        r"""The +5 tail of the constant encoder."""
        from esolangs.tools.boolean.six_five import _six_five_const

        assert _six_five_const(5) == "5"
        assert _six_five_const(11) == "65"

    def test_six_five_label_rejects_an_unspellable_operand(self) -> None:
        r"""Operands are one character, so the alphabet runs out at 35."""
        from esolangs.tools.boolean.six_five import (
            _SIX_FIVE_MAX_LABEL,
            _six_five_label,
        )

        assert _six_five_label(_SIX_FIVE_MAX_LABEL) == "Z"
        with pytest.raises(ValueError, match="no operand character for 36"):
            _six_five_label(_SIX_FIVE_MAX_LABEL + 1)

        # The range is closed at *both*.
        # a guard reading ``1 <=`` or.
        assert _six_five_label(0) == "0"
        assert _six_five_label(1) == "1"
        with pytest.raises(ValueError, match="no operand character for -1"):
            _six_five_label(-1)

    def test_six_five_move_spells_a_distance_in_pairs(self) -> None:
        r"""Rightward moves go two cells at a time, with a ``3`` for the odd."""
        from esolangs.tools.boolean.six_five import _six_five_move

        assert _six_five_move(2, 2) == ""
        assert _six_five_move(0, 1) == "13"
        assert _six_five_move(0, 2) == "1"
        assert _six_five_move(0, 3) == "113"
        assert _six_five_move(0, 5) == "1113"
        assert _six_five_move(3, 0) == "333"
        assert _six_five_move(5, 0) == "33333"

    def test_six_five_refuses_at_more_than_thirty_five_labels(self) -> None:
        r"""The capacity test is ``> 35``, not ``>= 35``."""
        from esolangs.tools.boolean.six_five import (
            _SIX_FIVE_MAX_LABEL,
            _six_five_label,
        )

        assert _SIX_FIVE_MAX_LABEL == 35
        assert _six_five_label(_SIX_FIVE_MAX_LABEL) == "Z"
        assert len(_six_five_label(_SIX_FIVE_MAX_LABEL)) == 1


class TestAlgebraicProgrammingLanguage:
    r"""The minterm-sum generator, whose whole program is one executed line."""

    @staticmethod
    def _run(program: str, n: int, combo: int) -> str:
        bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
        return run_algebraic_programming_language(program, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity.
            ("10", 1),  # not.
            ("0001", 2),  # AND2.
            ("0111", 2),  # OR2.
            ("0110", 2),  # XOR2.
            ("01101001", 3),  # parity.
            ("1000000000000000", 4),  # AND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.algebraic_programming_language(table)
        for combo in range(2**n):
            got = self._run(program, n, combo)
            assert got == table[combo] + "\n", f"table {table} combo {combo}"

    def test_every_one_and_two_input_table(self) -> None:
        r"""All 4 one-input and 16 two-input tables build and compute."""
        for n in (1, 2):
            for table in ("".join(t) for t in itertools.product("01", repeat=2**n)):
                program = boolean.algebraic_programming_language(table)
                for combo in range(2**n):
                    got = self._run(program, n, combo)
                    assert got == table[combo] + "\n", f"{table} combo {combo}"

    def test_every_three_input_table(self) -> None:
        r"""All 256 three-input tables build and compute their function."""
        for table in ("".join(t) for t in itertools.product("01", repeat=8)):
            program = boolean.algebraic_programming_language(table)
            for combo in range(8):
                got = self._run(program, 3, combo)
                assert got == table[combo] + "\n", f"{table} combo {combo}"

    def test_the_constant_zero_table_still_reads_every_input(self) -> None:
        r"""A table with no minterms names each input so the reads still happen."""
        program = boolean.algebraic_programming_language("0000")
        for name in ("a", "b"):
            assert name in program
        for combo in range(4):
            assert self._run(program, 2, combo) == "0\n"

    def test_reads_are_in_ascending_name_order(self) -> None:
        r"""A variable is read when the line first names it."""
        program = boolean.algebraic_programming_language("01101001")
        line = program.splitlines()[-1]
        firsts = [min(line.index(n) for n in (v,)) for v in "abc"]
        assert firsts == sorted(firsts)

    def test_every_value_stays_zero_or_one(self) -> None:
        r"""The program prints a bit, not an arbitrary truth value."""
        program = boolean.algebraic_programming_language("0110")
        for combo in range(4):
            assert self._run(program, 2, combo).strip() in {"0", "1"}

    def test_the_complement_operator_is_the_wikis_own(self) -> None:
        r"""The header is the wiki's ``!x`` definition, verbatim."""
        program = boolean.algebraic_programming_language("0001")
        assert program.startswith("!x = {\nx & $0\n$1\n}\n")

    def test_a_one_entry_table_is_refused(self) -> None:
        r"""A nullary table is a constant, not a function of any input."""
        with pytest.raises(ValueError, match="a one-entry table is a constant"):
            boolean.algebraic_programming_language("0")

    def test_a_width_spreads_the_sum_over_definitions(self) -> None:
        r"""A narrower program is the same sum, named a piece at a time."""
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
        r"""Naming a term moves it off the one line that reads."""
        table = "0110100110010110"
        narrow = boolean.algebraic_programming_language(table, 30)
        # the ``!x`` header is the.
        # braces; past it, a line.
        # there must be exactly one.
        lines = narrow.splitlines()
        assert lines[:4] == ["!x = {", "x & $0", "$1", "}"], lines[:4]
        executed = [line for line in lines[4:] if "=" not in line]
        assert len(executed) == 1, executed
        line = executed[0]
        assert line.startswith("(a & b & c & d & 0) | "), line
        # and every input is still read.
        assert [ch for ch in line if ch in "abcd"] == ["a", "b", "c", "d"]

    def test_narrowing_below_the_floor_does_not_widen(self) -> None:
        r"""Asking for less than it can do returns its narrowest, not a worse."""
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


class TestAlgebraicProgrammingLanguageShapes:
    r"""The structural corners of the minterm expansion, at four inputs."""

    @staticmethod
    def _check(table: str, n: int = 4) -> None:
        program = boolean.algebraic_programming_language(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_algebraic_programming_language(program, bits)
            assert got == table[combo] + "\n", f"{table} inputs {bits}"

    def test_the_all_zero_table(self) -> None:
        r"""No minterms at all: the constant-zero branch."""
        self._check("0" * 16)

    def test_the_all_one_table(self) -> None:
        r"""Every row set, so the sum carries all sixteen terms."""
        self._check("1" * 16)

    def test_a_single_minterm(self) -> None:
        r"""One term, which is the fewest a non-constant table can have."""
        self._check("0000000000000001")

    def test_four_input_parity(self) -> None:
        r"""Eight terms and no constant subtree anywhere -- nothing folds."""
        self._check("0110100110010110")

    def test_the_all_zero_table_still_reads_every_input(self) -> None:
        r"""The constant needs its reads: the contract wants ``n`` of them."""
        program = boolean.algebraic_programming_language("0" * 16)
        for name in "abcd":
            assert name in program

    def test_the_name_alphabet_is_codepoint_ascending(self) -> None:
        r"""``_order_key`` sorts literals by name to keep reads in order."""
        from esolangs.tools.boolean.algebraic_programming_language import _NAMES

        assert list(_NAMES) == sorted(_NAMES)
        assert len(set(_NAMES)) == len(_NAMES)


class TestFunctionXY:
    r"""A nested-ternary decision tree over inputs read up front."""

    @staticmethod
    def _check(table: str) -> None:
        r"""Execute the program on every row and compare with the table."""
        n = len(table).bit_length() - 1
        program = boolean.function_x_y(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_function_x_y(program, bits) == table[combo], (
                f"table {table} inputs {bits}"
            )

    @pytest.mark.parametrize(
        "table",
        [
            "01",  # identity.
            "10",  # NOT.
            "00",  # constant zero.
            "11",  # constant one.
            "0001",  # AND.
            "0111",  # OR.
            "0110",  # XOR.
            "1110",  # NAND.
            "01101001",  # XOR3.
            "11111110",  # NAND3.
            "1000000000000000",  # AND4.
            "0110100110010110",  # parity4: nothing folds.
        ],
    )
    def test_truth_table(self, table: str) -> None:
        self._check(table)

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_every_table_of_small_arity(self, n: int) -> None:
        r"""Exhaustive over all ``2**(2**n)`` tables, not a sample."""
        for value in range(2 ** (2**n)):
            self._check(bin(value)[2:].zfill(2**n))

    @pytest.mark.parametrize("n", [4, 5])
    def test_a_sample_of_wider_tables(self, n: int) -> None:
        r"""The claimed arities run; 2**16 and 2**32 tables are sampled."""
        rng = random.Random(n)
        for _ in range(12):
            table = "".join(rng.choice("01") for _ in range(2**n))
            self._check(table)

    def test_a_constant_table_still_reads_every_input(self) -> None:
        r"""The reads are the interface, so a constant must not skip them."""
        for table in ("0000", "1111"):
            program = boolean.function_x_y(table)
            assert program.count("[~]") == 2
            # and it still answers.
            assert run_function_x_y(program, ["0", "0"]) == table[0]

    def test_a_constant_table_folds_to_a_literal(self) -> None:
        r"""Nothing branches when the whole table is one value."""
        program = boolean.function_x_y("1111")
        assert "<" not in program.split("\n")[-1].replace('`"1"', "")
        assert program.endswith('`"1"')

    def test_the_tree_folds_a_constant_subtree(self) -> None:
        r"""``0011`` depends only on the second input, so one test suffices."""
        program = boolean.function_x_y("0011")
        assert program.count("==") == 1

    def test_reads_stay_in_input_order(self) -> None:
        r"""Reordering moves which input a node tests, never the reads."""
        program = boolean.function_x_y("0110100110010110")
        reads = [ln for ln in program.split("\n") if ln.startswith("var ")]
        assert reads == [f"var b{i}: [~]" for i in range(4)]

    def test_a_malformed_table_is_refused(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.function_x_y("011")
        # a nullary table is a.
        with pytest.raises(ValueError, match="at least one input"):
            boolean.function_x_y("0")

    def test_a_width_names_the_subtrees_and_it_still_computes(self) -> None:
        r"""A narrower program is the same tree with its nesting spread down."""
        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            flat = boolean.function_x_y(table)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.function_x_y(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 30, 45, 80, wide):
                narrow = boolean.function_x_y(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    got = run_function_x_y(narrow, bits)
                    assert got == table[combo], (table, width, bits)

    def test_naming_a_subtree_keeps_the_reads_out_of_it(self) -> None:
        r"""The reads stay above the tree, one per input, however much is named."""
        table = "0110100110010110"
        for width in (None, 1, 30, 80):
            program = boolean.function_x_y(table, width)
            lines = program.splitlines()
            reads = [line for line in lines if "[~]" in line]
            assert reads == [f"var b{i}: [~]" for i in range(4)], width
            assert program.count("[~]") == 4, width
