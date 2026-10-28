"""collatz_multiverse generator tests."""

import random

import pytest

import esolangs
from esolangs.languages import generators as boolean
from tests.generators.boolean_runners import _runner
from tests.support.generator_support import assert_parity_at_most_doubles
from tests.support.witness_tables import row_bits, witnesses

run_collatz_multiverse = _runner("collatz_multiverse", newline=True)


class TestCollatzMultiverse:
    def test_reads_each_input_once_and_prints_once(self) -> None:
        """The program reads every input once and answers with one print."""
        program = boolean.collatz_multiverse("01101001")
        assert program.count("input") == 3
        assert program.count("DO PRINT.") == 1

    def test_cells_are_addressed_by_line_number(self) -> None:
        """The table sits in cells the writing line's own number addresses."""
        table = "01101001" * 8
        program = boolean.collatz_multiverse(table)
        subscripted = [line for line in program.splitlines() if "[" in line]
        placed = [line for line in subscripted if "[lineNumber]=" in line]
        assert len(placed) <= len(table) // 2
        # What is left is the reader: one indexed read of each array, by a
        # register the inputs summed rather than by a walked pointer.
        assert len(subscripted) - len(placed) == 2

    def test_constant_tables_collapse_but_still_read(self) -> None:
        """A constant table collapses to one output but still reads its inputs."""
        for table in ("0000", "1111"):
            program = boolean.collatz_multiverse(table)
            assert program.count("DO PRINT.") == 1
            assert program.count("input") == 2  # n == 2, read once each

    @pytest.mark.parametrize("n", [4, 5, 6])
    @pytest.mark.medium
    def test_sampled_wider_tables(self, n: int) -> None:
        """Every row of sampled tables, with ignored inputs among them."""
        rng = random.Random(n)
        for _ in range(4):
            table = "".join(rng.choice("01") for _ in range(2**n))
            # An ignored first input, so the essential projection is exercised.
            for shape in (table, table[: 2 ** (n - 1)] * 2):
                program = boolean.collatz_multiverse(shape)
                for combo in range(2**n):
                    bits = row_bits(combo, n)
                    assert run_collatz_multiverse(program, bits) == shape[combo]

    def test_code_zero_follows_the_frequency_ranking(self) -> None:
        """The empty cell takes code 0 only when the ranking gives it."""
        from collections import Counter

        from esolangs.languages.collatz_multiverse.generator import _cm_codes

        codes = _cm_codes(Counter({0: 1, 8: 10, 1: 5}))
        assert codes[8] == 0
        assert codes[0] == 1
        assert codes[1] == 2

    def test_numbered_cells_halve_the_three_input_total(self) -> None:
        """The plain build against the shipped one over every varied table."""
        from esolangs.languages.collatz_multiverse.generator import _cm_build

        varied = [t for v in range(256) if len(set(t := format(v, "08b"))) > 1]
        plain = sum(len(_cm_build(t, 3, [0, 1, 2], numbered=False)) for t in varied)
        built = sum(len(boolean.collatz_multiverse(t)) for t in varied)
        assert (plain, built) == (497493, 273428)

    def test_numbering_never_grows_a_program(self) -> None:
        """Numbered cells beat the retired value-as-code size oracle."""
        from esolangs.languages.collatz_multiverse.generator import _cm_build

        rng = random.Random(0)
        tables = [format(v, "08b") for v in range(1, 255)]
        tables += ["".join(rng.choice("01") for _ in range(2**n)) for n in (4, 5, 6)]
        for table in tables:
            n = len(table).bit_length() - 1
            plain = _cm_build(table, n, list(range(n)), numbered=False)
            assert plain is not None
            assert len(boolean.collatz_multiverse(table)) <= len(plain), table

    @pytest.mark.parametrize("width", [1, 27, 32, 40, 80])
    def test_narrow_statements_keep_array_addresses(self, width: int) -> None:
        """Alias prefixes preserve odd captures and read every input once."""

        for table in ("0000", "1111", "0110", "01101001", "10101010"):
            n = len(table).bit_length() - 1
            plain = boolean.collatz_multiverse(table)
            program = esolangs.generate("Collatz Multiverse", table, width=width)
            assert max(map(len, program.splitlines())) <= max(
                width, max(map(len, plain.splitlines()))
            )
            assert program.count("input") == n
            assert program.count("DO PRINT.") == 1
            for row in range(1 << n):
                assert (
                    run_collatz_multiverse(program, list(f"{row:0{n}b}")) == table[row]
                )

    @pytest.mark.parametrize("width", [1, 27, 29, 30, 40, 80])
    def test_narrow_renaming_preserves_the_witness_tables(self, width: int) -> None:
        for n in range(1, 4):
            for table in witnesses(n):
                program = boolean.collatz_multiverse(table, width)
                assert max(map(len, program.splitlines())) <= max(width, 29)
                assert program.count("input") == n
                for row in range(2**n):
                    bits = list(format(row, f"0{n}b"))
                    assert run_collatz_multiverse(program, bits) == table[row]

    @pytest.mark.parametrize("n", [5, 8, 10])
    def test_narrow_renaming_preserves_larger_decoders(self, n: int) -> None:
        rng = random.Random(20260930 + n)
        for table in (
            "".join(str(row.bit_count() & 1) for row in range(2**n)),
            "".join(rng.choice("01") for _ in range(2**n)),
        ):
            for width in (1, 29, 40, 80):
                program = boolean.collatz_multiverse(table, width)
                for row in rng.sample(range(2**n), 12):
                    bits = list(format(row, f"0{n}b"))
                    assert run_collatz_multiverse(program, bits) == table[row]

    def test_fitting_alias_layout_keeps_its_register_names(self) -> None:
        program = boolean.collatz_multiverse("00", 27)
        assert max(map(len, program.splitlines())) <= 27
        assert "k48" in program
        for bit in ("0", "1"):
            assert run_collatz_multiverse(program, [bit]) == "0"

    def test_narrow_xor_uses_the_complete_statement_floor(self) -> None:
        program = boolean.collatz_multiverse("0110", 1)
        assert max(map(len, program.splitlines())) == 26

    def test_numbered_constants_narrow_complete_statements(self) -> None:
        """The narrow candidate changes source and actually reduces columns."""
        plain = boolean.collatz_multiverse("01101001")
        narrow = boolean.collatz_multiverse("01101001", 1)
        assert "negativeOne" not in narrow
        assert narrow.splitlines()[0].endswith("=zx+lineNumber,NOT PRINT.")
        assert max(map(len, narrow.splitlines())) == 26
        assert max(map(len, narrow.splitlines())) < max(map(len, plain.splitlines()))

    def test_narrow_statement_floor_is_idempotent(self) -> None:
        """Another alias prefix cannot narrow or widen the existing floor."""
        from esolangs.languages.collatz_multiverse.generator import _cm_layout

        table = "01101001"
        narrow = boolean.collatz_multiverse(table, 1)
        relaid = _cm_layout(narrow, 1)
        assert relaid == narrow
        for row, expected in enumerate(table):
            assert run_collatz_multiverse(relaid, list(f"{row:03b}")) == expected

    def test_narrow_cell_source_remains_linear(self) -> None:
        sizes = [
            len(boolean.collatz_multiverse("01101001" * (2 ** (n - 3)), 1))
            for n in (7, 8)
        ]
        assert sizes[1] < 2 * sizes[0] + 256


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.collatz_multiverse, (7, 8), 255)


def test_cm_constants_builds_only_the_bootstrap_for_small_values() -> None:
    """Nothing above k2 is needed, so the plan sieve is never entered."""
    from esolangs.languages.collatz_multiverse.generator import _cm_constants

    lines = _cm_constants([1, 2])
    assert len(lines) == 4
    assert all(line.endswith("NOT PRINT.") for line in lines)
    assert _cm_constants([]) == lines


def _minimal_plan_sizes(maxval: int) -> dict[int, int]:
    """Oracle: the retired exhaustive search, fewest constants building each ``m``."""
    need: dict[int, frozenset[int]] = {1: frozenset(), 2: frozenset()}
    for m in range(3, maxval + 1):
        need[m] = min(
            (
                frozenset({m})
                | need[b]
                | need[a]
                | (need[m - b * a] if m - b * a > 2 else frozenset())
                for b in range(1, m, 2)
                for a in range(1, min(m // b + 1, m))
            ),
            key=len,
        )
    return {m: len(s) for m, s in need.items()}


def test_cm_plan_chain_is_valid_and_near_minimal() -> None:
    """The rule builds each constant from smaller ones, within 3 of the minimum."""
    from esolangs.languages.collatz_multiverse.generator import _cm_chain

    oracle = _minimal_plan_sizes(150)
    for m in range(3, 151):
        plan = _cm_chain([m])
        for n, (b, c) in plan.items():
            assert b % 2 == 1
            assert 2 * b + c == n
            assert 0 <= c <= 3
            assert all(v <= 2 or v in plan for v in (b, c))
        assert len(plan) <= oracle[m] + 3


def test_cm_constants_print_the_right_value() -> None:
    """A constant program prints chr(value) for every byte value above 2."""
    from esolangs.languages.collatz_multiverse.generator import _cm_constant_program

    for value in range(3, 256):
        program = _cm_constant_program(1, value)
        assert run_collatz_multiverse(program, ["0"]) == chr(value)


def _swept_balance(table: str, default: str) -> str:
    """The retired balance: select among the spellings at every fit threshold."""
    from esolangs.generation.helpers import _validate_truth_table, grid_width
    from esolangs.generation.wrap import balance_score
    from esolangs.languages.collatz_multiverse.generator import (
        _cm_candidates,
        _cm_layout_versions,
        _cm_narrow_choice,
        collatz_multiverse,
    )

    n = _validate_truth_table(table)
    wide = collatz_multiverse(table, len(default))
    narrow = _cm_candidates(table, n, narrow=True, expanded=True)
    versions = [
        [(grid_width(source), source) for source in _cm_layout_versions(program)]
        for program in [wide, *narrow]
    ]
    thresholds = {1}
    for spellings in versions:
        for span, _source in spellings:
            thresholds.update((span, max(1, span - 1)))

    def fitted(spellings: list[tuple[int, str]], width: int) -> str:
        return next(
            (source for span, source in spellings if span <= width), spellings[-1][1]
        )

    candidates = [default]
    for width in sorted(thresholds):
        program = fitted(versions[0], width)
        if grid_width(program) > width:
            program = _cm_narrow_choice(
                program, [fitted(item, width) for item in versions[1:]]
            )
        candidates.append(program)
    return min(candidates, key=balance_score)


def test_balance_scores_the_spellings_without_a_threshold_sweep() -> None:
    """Per table, 1..5 inputs: never worse than the retired threshold sweep."""
    from esolangs.generation.wrap import balance_score

    rng = random.Random(3)
    for n in (1, 2, 3, 4, 5):
        for _ in range(6):
            table = format(rng.getrandbits(1 << n), f"0{1 << n}b")
            new = esolangs.generate("Collatz Multiverse", table, balance=True)
            old = _swept_balance(table, esolangs.generate("Collatz Multiverse", table))
            assert balance_score(new) <= balance_score(old), table


@pytest.mark.parametrize(
    ("table", "width", "size"),
    [
        # More than 24 registers get B<i> names after the alphabet.
        (
            "0100001010101000011000010000010010111100100010000000101100100001",
            30,
            2471,
        ),
        # A width request tries a rotated selector order from three inputs.
        ("01000010", 30, 921),
        # Three essential inputs exactly: the rotated order starts here.
        ("00000111", 1, 1468),
        # A wide table of long zero runs and dense blocks, pinned end to end.
        (
            "00000000000000000000011100000111011101110111011101110111011101110000011100000000000000000111011101110111011100000111011100000111",
            None,
            2322,
        ),
    ],
)
def test_layout_sizes(table: str, width: int | None, size: int) -> None:
    assert len(esolangs.generate("collatz_multiverse", table, width=width)) == size
