"""brainif generator tests."""

from itertools import pairwise

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_brainif,
)
from tests.witness_tables import witnesses


class TestBrainIf:
    """The DAG selector and the retained width-constrained tree/spatial route."""

    def test_structure(self) -> None:
        """An entry trampoline precedes the answer build and input tree."""
        program = boolean.brainif("10", width=1000)
        assert program.startswith("if 0 goto 4\nif 48 goto")
        assert "if 0 input" in program
        # The one leaf, a 0, joins the trampoline line its byte (48) passes.
        assert program.count("goto 2") == 1

    def test_the_answer_byte_is_built_once(self) -> None:
        """The climb to 48 is paid before the tree, not once per digit."""
        for table in ("10", "0110", "11111110", "01101001"):
            assert boolean.brainif(table, width=1000).count("increment") == 49
        assert boolean.brainif("00000000", width=1000).count("increment") == 48

    def test_one_shared_output_tail(self) -> None:
        """Both answers print from the same two lines."""
        program = boolean.brainif("0110")
        assert program.count("output") == 2

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice stops the branching, though not the reads."""
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
                bits = "".join(f"{(row >> (2 - i)) & 1}" for i in range(3))
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
            bits = "".join(f"{(row >> (5 - i)) & 1}" for i in range(6))
            assert self._reads(program, bits) == (table[row], 6)

    def test_pruning_never_grows_a_table(self) -> None:
        """No table through four inputs is longer than its unpruned tree."""
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


@pytest.mark.parametrize("width", [1, 11, 12, 13, 40, 80])
def test_brainif_zero_landing_executes_all_small_tables(width: int) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.brainif import run

    for n in range(1, 4):
        for table in witnesses(n):
            program = boolean.brainif(table, width)
            for row, expected in enumerate(table):
                bits = list(format(row, f"0{n}b"))
                io = ScriptedIO("".join(bits) + "sentinel")
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
            stdin = format(row, f"0{n}b")
            assert esolangs.run("BrainIf", program, stdin) == table[row]
            assert esolangs.run("BrainIf", str(program), stdin) == table[row]


def test_brainif_unpruned_large_tree_uses_spatial_fallback() -> None:
    from esolangs.tools.brainif import _brainif_tree

    table = "".join(str(row.bit_count() % 2) for row in range(32))
    program = _brainif_tree(table, 1, prune=False)
    for row in [0, 1, 7, 13, 31]:
        assert run_brainif(program, list(format(row, "05b"))) == table[row]
