"""Covers :mod:`esolangs.tools.taglate`."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_taglate,
)


class TestTaglate:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("00", 1),
            ("01", 1),
            ("10", 1),
            ("11", 1),
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("1110", 2),  # NAND
            ("00000001", 3),  # majority
            ("0000000000000001", 4),  # 4-AND
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            # Odd n > 1 uses a ghost digit (fake zero first input)
            inputs = (
                ["0"] + [str(b) for b in bits]
                if n % 2 == 1 and n > 1
                else [str(b) for b in bits]
            )
            got = run_taglate(program, inputs)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        """Every two-input truth table produces the right result."""
        for table in range(16):
            tt = format(table, "04b")
            for combo in range(4):
                bits = [(combo >> 1) & 1, combo & 1]
                got = run_taglate(boolean.taglate(tt), [str(b) for b in bits])
                assert got == tt[combo], f"{tt} inputs {bits}"

    @pytest.mark.medium
    def test_all_three_input_tables(self) -> None:
        """Every three-input truth table produces the right result."""
        failures = 0
        for table in range(256):
            tt = format(table, "08b")
            program = boolean.taglate(tt)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                inputs = ["0"] + [str(b) for b in bits]  # ghost digit
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
        """A table that ignores inputs is emitted as the smaller table.

        Taglate's cost is almost all fixed overhead scaled by the input
        count -- the seed alone is ``2**(n_eff + 2)`` cells -- so dropping
        an input drops a whole tier.  Every table of a given ``n`` used to
        be the same length; now the ones that depend on fewer inputs are
        dramatically shorter.
        """
        full = len(boolean.taglate("10010110"))  # depends on all three
        for table in ("11110000", "11001100", "10101010", "00000000"):
            assert len(boolean.taglate(table)) < full // 10, table

    def test_gapped_dependencies_reduce_without_reordering_inputs(self) -> None:
        """Every n=3 function of inputs 0 and 2 uses the small program.

        The discarded middle input is read after the reduced program's first
        read.  Its rotate-and-drop restores that exact intermediate queue,
        rather than shifting the arithmetic slots a later reduce addresses.
        """
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
            assert program.count("h") == 4, table  # ghost plus all three inputs
            for combo in range(8):
                bits = [str((combo >> shift) & 1) for shift in (2, 1, 0)]
                assert run_taglate(program, ["0", *bits]) == table[combo], (table, bits)

    def test_reduced_programs_still_read_every_input(self) -> None:
        """A reduced program consumes the inputs it no longer uses.

        The ignored ones are read and discarded (``h`` appends to the
        queue's tail, ``e`` once per queued cell rotates it to the front,
        ``f`` drops it), so the queue is left exactly as it was and a caller
        feeding several programs from one stream stays in sync.  Odd ``n``
        above 1 also takes a leading ghost digit, which is one more read.
        """
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
            ("1111111100000000", 4),  # depends on input 0
            ("1111000011110000", 4),  # input 1
            ("1010101010101010", 4),  # input 3
            ("1111111111111111", 4),  # none at all
        ],
    )
    def test_reduced_tables_compute_past_three_inputs(self, table: str, n: int) -> None:
        """The reduction stays correct deeper than the exhaustive sweep."""
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            ghost = ["0"] if n % 2 == 1 and n > 1 else []
            got = run_taglate(program, ghost + [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            # depends on inputs 0-2, so the window widens rightward to 0-3
            ("0000000000000011", 4),
            # depends on inputs 1-3, which has no room on the right, so the
            # window widens leftward to 0-3 instead
            ("0000000100000001", 4),
        ],
    )
    def test_odd_dependency_sets_widen_to_stay_even(self, table: str, n: int) -> None:
        """An odd-sized window takes one more ignored input, either side.

        The reduced program ghost-pads itself at odd arity, so it would
        expect an input the caller's stream does not carry.  Widening the
        window by one adjacent *ignored* input keeps the reduced table even
        and the read count honest -- and it has to work at both ends, since
        a set already touching the last input has no room on the right.
        """
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            ghost = ["0"] if n % 2 == 1 and n > 1 else []
            got = run_taglate(program, ghost + [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    def test_wrong_length_truth_table_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.taglate("011")

    def test_invalid_truth_table_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.taglate("0120")
