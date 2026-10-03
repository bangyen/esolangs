"""decleq generator tests."""

from esolangs import tools as boolean
from tests.tools.test_boolean_contract import _parity


class TestDecleq:
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

    def test_untaken_jumps_target_zero(self) -> None:
        """A jump no run can take is spelt ``0``, not the next address.

        A read falls through, a normalization chain stops at 1 or 2, the
        index counter at 1, and a leaf's address operand far above 0, so
        none of their targets is ever used.  Spelling them ``pc + 3`` cost
        the 256 three-input tables 394,316 characters; ``0`` costs 327,842.
        """
        cells = [int(tok) for tok in boolean.decleq("01101001").split()]
        instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
        assert [c for a, _b, c in instrs if a == -1] == [0, 0, 0]  # the reads
        for rc in (18, 19, 20):  # each chain, then its one branch
            assert instrs.count([rc, rc, 0]) == 47
        assert instrs.count([17, 17, 0]) == 4 + 2 + 1  # the index weights
        tables = [format(i, "08b") for i in range(256)]
        assert sum(len(boolean.decleq(t)) for t in tables) == 327_842
