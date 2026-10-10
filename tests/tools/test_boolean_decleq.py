"""decleq generator tests."""

import random

from esolangs import tools as boolean
from esolangs.tools.wrap import balance_program, balance_score, wrap_program
from tests.tools.boolean_runners import (
    run_decleq,
)
from tests.witness_tables import parity as _parity
from tests.witness_tables import row_bits


class TestDecleq:
    def test_essential_bits_get_one_chain_each(self) -> None:
        """Each essential bit is decremented 47 times, then tested once."""
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
        """A constant subtree above the table level is a one-instruction leaf."""
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
        """The per-entry cost falls with arity: no leaf names a wide address."""
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
                bits = row_bits(combo, n)
                got = run_decleq(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_a_repeated_subtree_is_emitted_once(self) -> None:
        """Two equal quarters share one copy and still print every entry."""
        rng = random.Random(8)
        block, other = ("".join(rng.choice("01") for _ in range(64)) for _ in "ab")
        table = block + other + block + block
        program = boolean.decleq(table)
        assert len(program) < 0.9 * len(
            boolean.decleq(block + other + other[::-1] + block[::-1])
        )
        for combo in rng.sample(range(256), 48):
            bits = [(combo >> (7 - i)) & 1 for i in range(8)]
            assert run_decleq(program, [str(b) for b in bits]) == table[combo]

    def test_untaken_jumps_target_zero(self) -> None:
        """A jump no run can take is spelt ``0``, not the next address."""
        cells = [int(tok) for tok in boolean.decleq("01101001").split()]
        instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
        assert [c for a, _b, c in instrs if a == -1] == [0, 0, 0]  # the reads
        for rc in (18, 19, 20):  # each chain, then its one branch
            assert instrs.count([rc, rc, 0]) == 47
        assert instrs.count([17, 17, 0]) == 4 + 2 + 1  # the index weights
        tables = [format(i, "08b") for i in range(256)]
        assert sum(len(boolean.decleq(t)) for t in tables) == 326_910


def test_mixed_digit_operands_share_one_grid_cell():
    # All three subleq OISCs share wrap_grid, so the language is not an axis.
    language = "decleq"
    for count in range(3, 65):
        program = " ".join(("1", "22", "333")[index % 3] for index in range(count))
        balanced = balance_program(program, language)
        optimum = min(
            [program]
            + [
                wrap_program(program, language, width)
                for width in range(1, len(program) + 1)
            ],
            key=balance_score,
        )
        assert balance_score(balanced) == balance_score(optimum)
        assert balanced.split() == program.split()
