"""Covers :mod:`esolangs.languages.streetcode.generator`."""

import itertools
import random
from importlib import import_module

import pytest

from esolangs.languages import generators as boolean
from esolangs.runtime._evaluate import _evaluate
from tests.generators.boolean_runners import _runner
from tests.support.witness_tables import row_bits

run_streetcode = _runner("streetcode", lines=True)


def _columns(program: str) -> int:
    """The widest row of a grid program, which is what a width bounds."""
    return max(len(line) for line in program.split("\n"))


# 2.3s over 84 tests: runs the generated program.
@pytest.mark.medium
class TestStreetcode:
    # One case per row, because each run rebuilds the machine and revalidates
    # the whole grid: nine in one test is 2.5s locally and over the band on a
    # slower runner.  The build is 0.03s of that, so splitting costs nothing.
    # Between them every input is read as both a 0 and a 1.
    @pytest.mark.parametrize("combo", [0, 31, 32, 63])
    def test_the_flat_lookup_addresses_every_entry(self, combo: int) -> None:
        """Each input's room walks the pointer by its own weight."""
        n = 6
        table = "".join(str(index.bit_count() & 1) for index in range(2**n))
        program = boolean.streetcode(table)
        bits = row_bits(combo, n)
        assert run_streetcode(program, [str(bit) for bit in bits]) == table[combo]

    def test_the_flat_lookup_is_nine_rows_at_every_arity(self) -> None:
        """The layout is a street, so the rectangle is linear by its height."""
        for n in range(6, 12):
            table = "".join(str(index.bit_count() & 1) for index in range(2**n))
            program = boolean.streetcode(table)
            rows = program.splitlines()
            assert len(rows) == 9, n
            assert len(rows) * max(map(len, rows)) <= 18 * 2**n + 3660, n

    def test_default_uses_only_shared_layouts(self) -> None:
        """Per-input loops are width fallbacks, never default candidates."""
        module = import_module("esolangs.languages.streetcode.generator")

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                tree = module._streetcode_tree(table)  # noqa: SLF001
                shared = module._streetcode_shared_program(n, tree)  # noqa: SLF001
                assert boolean.streetcode(table) == shared

    @pytest.mark.parametrize("table", ["01100110", "00010101"])
    def test_equal_siblings_share_one_drawing(self, table: str) -> None:
        """A redundant selector preserves every input row and shrinks the grid."""
        module = import_module("esolangs.languages.streetcode.generator")
        half = table[: len(table) // 2]
        if table == half * 2:
            shared = module._streetcode_tree(table)  # noqa: SLF001
            repeated = module._streetcode_join(  # noqa: SLF001
                module._streetcode_tree(half),  # noqa: SLF001
                module._streetcode_tree(half),  # noqa: SLF001
            )
            assert len(shared) * max(map(len, shared)) < len(repeated) * max(
                map(len, repeated)
            )
        program = boolean.streetcode(table)
        n = len(table).bit_length() - 1
        for combo in range(1 << n):
            assert (
                run_streetcode(program, [str(bit) for bit in row_bits(combo, n)])
                == table[combo]
            )

    def test_constant_subtrees_fold(self) -> None:
        """A subtree whose rows agree prints instead of driving down halls."""
        constant = len(boolean.streetcode("11111111"))
        halves = len(boolean.streetcode("11110000"))
        scattered = len(boolean.streetcode("10101010"))
        assert constant < scattered
        assert halves < scattered
        # a folded leaf still prints the right digit for every input
        for table in ("11111111", "11110000", "11001100"):
            program = boolean.streetcode(table)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = run_streetcode(program, [str(b) for b in bits])
                assert got == table[combo], f"{table} inputs {bits}"

    def test_folded_leaf_keeps_the_cell_pointer_advances(self) -> None:
        """A folded leaf spends the ``=`` its skipped halls would have."""
        program = boolean.streetcode("00000000")
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_streetcode(program, [str(b) for b in bits]) == "0"

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_scattered_programs_compute_the_table(self, table: str) -> None:
        """A scattered table still computes its function."""
        program = boolean.streetcode(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = run_streetcode(program, [str(b) for b in bits])
            assert got == table[combo], f"{table} inputs {bits}"

    def test_reads_stay_in_stream_order(self) -> None:
        """Every input is read once, in stream order."""
        for table in ("10101010", "11110000", "01101001"):
            assert boolean.streetcode(table).count("I") == 3

    def test_width_is_a_shape_choice(self) -> None:
        """A width picks a narrower shape, and that shape still computes."""
        table = "10"
        default = boolean.streetcode(table)
        narrow = boolean.streetcode(table, 25)
        assert _columns(narrow) <= 25 < _columns(default)
        assert narrow.count("\n") > default.count("\n")
        for bit in ("0", "1"):
            assert run_streetcode(narrow, [bit]) == table[int(bit)]

    def test_width_takes_the_narrowest_when_none_fits(self) -> None:
        """Below every shape's width the narrowest one is returned."""
        table = "10"
        program = boolean.streetcode(table, 1)
        assert _columns(program) == min(
            _columns(boolean.streetcode(table, w)) for w in (1, 25, 100)
        )
        for bit in ("0", "1"):
            assert run_streetcode(program, [bit]) == table[int(bit)]

    def test_width_none_is_unchanged(self) -> None:
        """Passing no width builds exactly what the generator always built."""
        for table in ("10", "0110", "11111110"):
            assert boolean.streetcode(table, None) == boolean.streetcode(table)

    def test_a_requested_width_is_never_overrun(self) -> None:
        """A width that *can* be met is met, measured on the emitted columns."""
        for table, width in (("0001", 33), ("0110", 33), ("01", 29)):
            program = boolean.streetcode(table, width)
            assert _columns(program) <= width, (table, width)

    def test_the_narrowest_fallback_is_really_the_narrowest(self) -> None:
        """Below every shape's width, the narrowest shape comes back."""
        program = boolean.streetcode("0100", 1)
        assert _columns(program) == 7
        for combo in range(4):
            bits = [str((combo >> 1) & 1), str(combo & 1)]
            assert run_streetcode(program, bits) == "0100"[combo]

    def test_a_width_equal_to_a_shape_is_wide_enough(self) -> None:
        """The fit test is inclusive: exactly the shape's width fits it."""
        default = boolean.streetcode("01")
        assert _columns(default) == 29
        assert boolean.streetcode("01", 29) == default
        assert boolean.streetcode("01", 30) == default

    @pytest.mark.parametrize(
        ("table", "length"),
        [("01", 302), ("0000", 340), ("0101", 348)],
    )
    def test_the_emitted_program_has_an_exact_length(
        self, table: str, length: int
    ) -> None:
        """The layout is deterministic down to the character."""
        assert len(boolean.streetcode(table)) == length

    def test_no_trailing_blank_row(self) -> None:
        """The grid ends on its last real row."""
        for table in ("01", "0101", "0110", "11111110"):
            program = boolean.streetcode(table)
            assert not program.endswith("\n"), table
            assert program.split("\n")[-1].strip(), table

    def test_the_program_is_only_streetcode_characters(self) -> None:
        """Only the glyphs Streetcode reads, plus layout space."""
        allowed = set(" +-;=CIOU^_|~\n")
        for table in ("01", "0000", "0110", "11111110"):
            assert set(boolean.streetcode(table)) <= allowed, table
        for width in (1, 20, 29, 33):
            assert set(boolean.streetcode("0110", width)) <= allowed, width


def test_a_width_past_the_crossover_still_chooses_a_shape() -> None:
    """Past the crossover a quarter turn gives the shared seven-column floor."""
    table = "0110100110010110" * 4
    both = (boolean.streetcode(table), _columns(boolean.streetcode(table)))
    assert boolean.streetcode(table, 10_000) == both[0]
    assert _columns(boolean.streetcode(table, 1)) == 7


@pytest.mark.parametrize("n", [1, 3, 6])
@pytest.mark.parametrize("row", [0, 1, -1])
def test_quarter_turned_lookup_preserves_input_order(n: int, row: int) -> None:
    from esolangs.languages.streetcode.interpreter import run
    from esolangs.runtime.io import ScriptedIO

    table = "".join(str((value * 73 + value // 3) & 1) for value in range(1 << n))
    row %= len(table)
    # Every width under 9 builds this same seven-column program.
    program = boolean.streetcode(table, 1)
    assert _columns(program) == 7
    io = ScriptedIO(f"{row:0{n}b}")
    run(program.splitlines(), io)
    assert (io.getvalue(), io.reads) == (table[row], n)


def test_quarter_turned_rendered_size_is_linear() -> None:
    from itertools import pairwise

    sizes = [
        len(boolean.streetcode("01101001" * (2 ** (n - 3)), 1)) for n in (5, 6, 7, 8)
    ]
    assert all(later < 2 * earlier for earlier, later in pairwise(sizes))


@pytest.mark.parametrize("row", [0, 37, 63])
def test_balance_folds_the_lookup_into_strips(row: int) -> None:
    import esolangs

    table = "".join(str((value * 73 + value // 3) & 1) for value in range(64))
    program = str(esolangs.generate("Streetcode", table, balance=True))
    rows = program.splitlines()
    # 409x9 flat; the fold is about square.
    assert max(map(len, rows)) < 2 * 2 * len(rows) < 409
    assert run_streetcode(program, [str(bit) for bit in row_bits(row, 6)]) == table[row]


def test_the_oracle_rejects_a_bend_read_as_a_junction() -> None:
    """Positive control: the shared-sill fold's strip end frames a mouth."""
    from esolangs.languages.streetcode.tests.fold_oracle import (
        drives_alike,
        shared_sill_fold,
    )
    from esolangs.runtime.io import ScriptedIO

    generator = import_module("esolangs.languages.streetcode.generator")
    run = import_module("esolangs.languages.streetcode.interpreter").run
    table = "0" * 64 + "1" * 64
    flat = generator._streetcode_flat(table, 7)  # noqa: SLF001
    fold, origin = shared_sill_fold(flat, 30, east=True)
    assert not drives_alike(flat, fold, origin)
    io = ScriptedIO("0" * 7)
    with pytest.raises(Exception, match="read past the end of input"):
        run(fold.splitlines(), io)
    # The same target, folded with a gap and wide margins, drives alike.
    sound, origin = generator._streetcode_fold(flat, 30, east=True)  # noqa: SLF001
    assert drives_alike(flat, sound, origin)


def _random_table(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("01") for _ in range(1 << n))


def _assert_every_fold_drives_alike(n: int, tables: int, step: int) -> None:
    """Every ``step``-th target, both cut directions, random tables."""
    from esolangs.languages.streetcode.tests.fold_oracle import drives_alike

    generator = import_module("esolangs.languages.streetcode.generator")
    rng = random.Random(n)
    for _ in range(tables):
        flat = generator._streetcode_flat(_random_table(rng, n), n)  # noqa: SLF001
        span = max(map(len, flat.splitlines()))
        for target in range(8, span + 1, step):
            for east in (False, True):
                fold, origin = generator._streetcode_fold(flat, target, east=east)  # noqa: SLF001
                assert drives_alike(flat, fold, origin), (n, target, east)


@pytest.mark.medium
@pytest.mark.parametrize(("n", "step"), [(3, 9), (4, 23), (5, 43)])
def test_folds_drive_like_the_flat_street(n: int, step: int) -> None:
    """Folds are sound by construction; the drive check is only the oracle."""
    _assert_every_fold_drives_alike(n, 1, step)


@pytest.mark.slow
@pytest.mark.parametrize(("n", "step"), [(6, 29), (7, 41), (8, 61)])
def test_folds_drive_like_the_flat_street_at_scale(n: int, step: int) -> None:
    _assert_every_fold_drives_alike(n, 3, step)


@pytest.mark.parametrize(
    "n",
    [
        pytest.param(1, marks=pytest.mark.medium),
        pytest.param(2, marks=pytest.mark.medium),
        pytest.param(3, marks=pytest.mark.slow),
    ],
)
def test_the_folded_street_computes_every_table(n: int) -> None:
    generator = import_module("esolangs.languages.streetcode.generator")
    for bits in itertools.product("01", repeat=1 << n):
        table = "".join(bits)
        fold = generator._streetcode_folded(generator._streetcode_flat(table, n))  # noqa: SLF001
        assert _evaluate("Streetcode", fold, inputs=n) == table


@pytest.mark.medium
@pytest.mark.parametrize(("n", "count"), [(4, 4), (5, 4), (6, 2), (7, 1)])
def test_the_folded_street_computes_random_tables(n: int, count: int) -> None:
    import esolangs

    generator = import_module("esolangs.languages.streetcode.generator")
    rng = random.Random(100 + n)
    for _ in range(count):
        table = _random_table(rng, n)
        fold = generator._streetcode_folded(generator._streetcode_flat(table, n))  # noqa: SLF001
        assert len(fold.splitlines()) > 9
        assert _evaluate("Streetcode", fold, inputs=n) == table
        balanced = esolangs.generate("Streetcode", table, balance=True)
        assert _evaluate("Streetcode", balanced, inputs=n) == table
