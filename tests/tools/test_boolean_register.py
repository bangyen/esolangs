"""Unit tests for the register-based boolean generators.

Covers the generators in :mod:`esolangs.tools.boolean.register`: Decleq,
AddSubJump, Collatz Multiverse, Sophie, Dig, Qoibl, Polynomial, and Point
Break.
"""

import pytest

import esolangs
from esolangs.tools import boolean
from tests.tools.boolean_runners import (
    _PB_CONSTANTS,
    _PB_TABLES,
    _pb_combo_bits,
    _pb_random_tables,
    point_break_result,
    run_addsubjump,
    run_collatz_multiverse,
    run_decleq,
    run_dig,
    run_polynomial,
    run_qoibl,
    run_sophie,
)


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

    def test_rejects_bad_table(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            boolean.addsubjump("011")

    def test_rejects_non_binary(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.addsubjump("02")


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

    def test_is_polynomial(self) -> None:
        """The program is a polynomial function."""
        assert boolean.polynomial("0110").startswith("f(x) = ")

    def test_supports_three_inputs(self) -> None:
        """A 3-input table is factored exactly by the interpreter."""
        assert boolean.polynomial("00000001").startswith("f(x) = ")

    def test_five_inputs_rejected(self) -> None:
        with pytest.raises(ValueError, match="n <= 4"):
            boolean.polynomial("0" * 31 + "1")


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
        """The XOR gate produces the standard two-level decision tree."""
        expected = (
            "'           > >$30:@\n"
            "     > >2$~;#@\n"
            "            > >$31:@\n"
            ">2$~;#@\n"
            "            > >$31:@\n"
            "     > >2$~;#@\n"
            "            > >$30:@"
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
        program = boolean.sophie(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_sophie(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function is a single conditional pair."""
        assert boolean.sophie("10") == ";@$48{#$49,&}{#$48,&}"

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

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.collatz_multiverse("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.collatz_multiverse("02")


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

    def test_branch_normalizes_bits_to_one_and_two(self) -> None:
        """Each bit gets a 47-step decrement chain, then one branch."""
        program = boolean.decleq("0110")
        cells = [int(tok) for tok in program.split()]
        instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
        # count a==b>0 instructions: the 47 normalization steps plus the
        # decision-tree branches (2**n - 1 of them)
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
        assert len(decs) == 47 * 3 + 1  # three normalize chains, one branch
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

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.decleq("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.decleq("02")


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
