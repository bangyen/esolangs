"""inject generator tests."""

import random
import re
from collections import Counter
from itertools import pairwise

import pytest

import esolangs
from esolangs.generation.helpers import read_at
from esolangs.generation.wrap import balance_score
from esolangs.languages.inject import generator as boolean
from esolangs.languages.inject.generator import _half_pattern, _Names, _tree
from tests.generators.boolean_runners import _runner
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_an_ignored_input_costs,
    assert_parity_at_most_doubles,
    constant_programs,
    evaluate_generated,
    measure_run,
    three_input_corpus_size,
)

run_inject = _runner("inject", newline=True)


class TestInject:
    """The decision tree of ``skipq`` guards over stored input blocks."""

    def test_balanced_parity_chunks_the_table_square(self) -> None:
        """Parity n=10: ~sqrt(T)-wide chunks, ~sqrt(T) lines (default: 1024 wide)."""
        table = "".join(str((i).bit_count() % 2) for i in range(1 << 10))
        program = esolangs.generate("inject", table, balance=True).source
        assert balance_score(str(program)) == (298, 1968, 142)

    def test_constant_subtrees_are_folded(self) -> None:
        """A table ignoring its later inputs costs one test, not ``n``."""
        assert_analysis_complement("Inject", "subtree_ids", "00010111")
        one_dependency = len(boolean.inject("00001111"))
        parity = len(boolean.inject("01101001"))
        assert one_dependency < parity * 3 / 4

    def test_reads_every_input_before_branching(self) -> None:
        """The reads are hoisted, so every path consumes exactly ``n`` lines."""
        program = boolean.inject("0001").splitlines()
        reads = [i for i, line in enumerate(program) if line.startswith("readto")]
        first_branch = next(
            i for i, line in enumerate(program) if line.startswith("skipq")
        )
        assert len(reads) == 2, "one readto per input, and no more"
        assert max(reads) < first_branch, "every read precedes every branch"

    def test_every_label_occurs_exactly_twice(self) -> None:
        """Inject's labels are strictly two-occurrence: an open and a close."""
        for table in ("01", "0001", "0110", "01101001", "11110000"):
            counts = Counter(
                line
                for line in boolean.inject(table).splitlines()
                if line.endswith(";")
            )
            assert all(v == 2 for v in counts.values()), (table, counts)
            assert all(len(label) == 2 for label in counts)

    def test_an_input_block_starts_empty(self) -> None:
        """An empty block is two *adjacent* delimiters, after all executed code."""
        for n, table in ((1, "01"), (2, "0001"), (3, "01101001")):
            lines = boolean.inject(table).splitlines()
            tail = lines[-2 * n :]
            assert all(tail[2 * d] == tail[2 * d + 1] for d in range(n))
            assert len(set(tail[::2])) == n

    def test_halving_lookup_executes_wide_rows(self) -> None:
        """Regex halves return sampled six-input rows."""
        assert_analysis_complement("Inject", "input_weights", "0011" * 8)
        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        program = boolean.inject(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_inject(program, bits) == table[row] + "\n"

    @pytest.mark.parametrize("width", [1, 40, 80])
    def test_chunked_lookup_executes_every_row(self, width: int) -> None:
        """Leaf escapes join one postlude without losing the selected chunk."""

        for n in (5, 6, 7):
            table = "".join(str((row * 73 + row // 3) & 1) for row in range(1 << n))
            plain = boolean.inject(table)
            program = esolangs.generate("Inject", table, width=width).source
            assert max(map(len, program.splitlines())) <= max(width, 22)
            assert program.count("readto ") == n
            if max(map(len, plain.splitlines())) <= width:
                assert program == plain
            for row in range(1 << n):
                assert run_inject(program, list(f"{row:0{n}b}")) == table[row] + "\n"

    def test_chunked_lookup_drops_ignored_inputs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Input 2 of 7 is read and never tested; the table is indexed without it."""
        small = "".join(str((row * 73 + row // 3) & 1) for row in range(64))
        table = "".join(small[r >> 1 & 32 | r & 31] for r in range(128))
        program = esolangs.generate("Inject", table, width=1).source
        assert program.count("readto ") == 7
        assert len(program) < 0.7 * len(
            esolangs.generate("Inject", small + small[::-1], width=1).source
        )
        for row in range(128):
            assert run_inject(program, list(f"{row:07b}")) == table[row] + "\n"
        assert boolean.read_at is read_at
        monkeypatch.setattr(
            boolean,
            "read_at",
            lambda table, order, n: read_at(
                table.translate(str.maketrans("01", "10")), order, n
            ),
        )
        assert evaluate_generated("Inject", table, width=1) == table.translate(
            str.maketrans("01", "10")
        )

    def test_chunked_source_growth_is_linear(self) -> None:
        sizes = [
            len(boolean.inject("01101001" * (2 ** (n - 3)), 1)) for n in (9, 10, 11)
        ]
        assert all(b <= 2 * a for a, b in pairwise(sizes))

    def test_the_tree_collapses_on_the_constant_subtree_alone(self) -> None:
        """Depth never terminates the recursion; a constant subtree always does."""
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
        # And the tree itself is unchanged when the depth clause cannot fire.
        assert _tree("01101001", 0, 3, _Names(3)) == _tree("01101001", 0, 3, _Names(3))


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """Its declaration and ``readto``."""
    assert_an_ignored_input_costs("Inject", 6, 15)


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.inject, range(11, 15))


def test_a_width_the_program_exactly_fills_keeps_the_program() -> None:
    rng = random.Random(6)
    table = "".join(rng.choice("01") for _ in range(64))
    program = esolangs.generate("Inject", table).source
    widest = max(map(len, program.splitlines()))
    assert widest == 64
    assert esolangs.generate("Inject", table, width=widest).source == program
    assert len(esolangs.generate("Inject", table, width=widest - 1).source) == 686


def test_counted_halving_keeps_the_exact_offset() -> None:
    table = "0" * 32 + "1" + "0" * 31
    program = boolean.inject(table)
    assert ".{32}" in program
    for row, expected in enumerate(table):
        assert run_inject(program, list(f"{row:06b}")) == expected + "\n"
    broken = program.replace(".{32}", ".{31}", 1)
    assert run_inject(broken, list("100000")) != "1\n"


def test_counted_halving_splits_unrepresentable_repeat_counts() -> None:
    from esolangs.languages.inject.proof_formulas import _regex_chars

    width = 0
    for exponent in range(41):
        assert _regex_chars(exponent) == width
        width += len(_half_pattern(1 << exponent))
    for half in (1, 2, 4, 8, 16):
        pattern = _half_pattern(half)
        assert re.fullmatch(pattern, "x" * half)
        assert re.fullmatch(pattern, "x" * (half - 1)) is None
        assert re.fullmatch(pattern, "x" * (half + 1)) is None
    half = 1 << 32
    pattern = _half_pattern(half)
    assert re.fullmatch(r"(?:\.\{\d+\})+", pattern)
    counts = [int(value) for value in re.findall(r"\{(\d+)\}", pattern)]
    assert sum(counts) == half
    assert max(counts) < half
    assert re.compile(pattern).fullmatch("") is None
    with pytest.raises(OverflowError):
        re.compile(f".{{{half}}}")


@pytest.mark.medium
def test_constant_scratch_reuse_reads_first_and_preserves_the_next_line() -> None:
    from esolangs.languages.inject.interpreter import _Machine
    from esolangs.languages.inject.proof_formulas import workspace

    for n, bit, _options, program in constant_programs("Inject", range(1, 13)):
        assert len(program) == 9 * n + 20
        assert program.splitlines().count("readto a") == n
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs(
                "Inject", list(map(int, format(row, f"0{n}b")))
            )
            stream = ReadFirstIO(stdin + "Q\n", expected=n)
            machine = _Machine(program, stream)
            steps, written = measure_run(machine, limit=n + 7)
            assert machine.halted
            assert steps == n + 7
            assert written.bits == workspace(n, program)
            assert stream.getvalue() == bit + "\n"
            assert stream.input_str() == "Q"
    assert three_input_corpus_size("Inject") == 47658
