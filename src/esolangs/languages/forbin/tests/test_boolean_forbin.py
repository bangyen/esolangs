"""forbin generator tests."""

import inspect
import itertools
import random
import sys
from collections.abc import Callable

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.languages import generators as boolean
from tests.generators.boolean_runners import _runner
from tests.support.witness_tables import witnesses

run_forbin_boolean = _runner("forbin")


class TestForbinBoolean:
    @pytest.mark.parametrize("width", [1, 4, 7, 13, 40, 80])
    def test_narrow_small_tables(self, width: int) -> None:
        """The witness tables execute with a four-column grammar floor."""
        for n in range(1, 4):
            for table in witnesses(n):
                program = esolangs.generate("Forbin", table, width=width)
                assert isinstance(program, str)
                assert max(map(len, program.splitlines())) <= max(width, 4)
                for row in range(2**n):
                    bits = list(format(row, f"0{n}b"))
                    assert run_forbin_boolean(program, bits) == table[row]

    @pytest.mark.parametrize("width", [1, 4, 13, 80])
    def test_narrow_block_guards(self, width: int) -> None:
        """Both block guards and constant spans emit exactly one answer."""
        rng = random.Random(20260930)
        for n in (8, 9):
            tables = [
                "0" * (2 ** (n - 1)) + "1" * (2 ** (n - 1)),
                "".join(str(row.bit_count() & 1) for row in range(2**n)),
                "".join(rng.choice("01") for _ in range(2**n)),
            ]
            for table in tables:
                program = esolangs.generate("Forbin", table, width=width)
                assert isinstance(program, str)
                assert max(map(len, program.splitlines())) <= max(width, 4)
                for row in [0, 2**n - 1, *rng.sample(range(2**n), 16)]:
                    bits = list(format(row, f"0{n}b"))
                    assert run_forbin_boolean(program, bits) == table[row]

    def test_a_fitting_program_keeps_its_source(self) -> None:
        program = boolean.forbin("01101001")
        width = max(map(len, program.splitlines()))
        assert boolean.forbin("01101001", width) == program

    def test_uses_the_lsb_of_each_input(self) -> None:
        """Each input is read as 8 bits and only the LSB is kept."""
        program = boolean.forbin("01")
        assert "e,e,e,e,e,e,e,a=(in 0);" in program

    def test_small_program_uses_one_character_variables(self) -> None:
        """The first 52 variables do not carry widening decimal suffixes."""
        targets = [
            line.split("=", 1)[0]
            for line in boolean.forbin("01101001").splitlines()
            if line.endswith("=(in 0);")
        ]
        assert targets
        assert all(len(name) == 1 for group in targets for name in group.split(","))

    def test_the_block_is_painted_as_a_literal_argument_list(self) -> None:
        """A table inside one block is emitted verbatim, two characters an entry."""
        program = boolean.forbin("01101001")
        assert "0,1,1,0,1,0,0,1)" in program

    def test_compact_variables_skip_keywords_without_duplicates(self) -> None:
        """Filtering a reserved word does not reuse its successor's name."""
        from esolangs.languages.forbin.generator import _FORBIN_RESERVED, _forbin_names

        names = list(itertools.islice(_forbin_names(), 600))
        assert len(set(names)) == len(names)
        assert not set(names) & _FORBIN_RESERVED

    def test_constant_spans_fold_above_the_block(self) -> None:
        """A constant span of blocks calls a printer instead of painting."""
        from esolangs.languages.forbin.generator import _BLOCK_BITS, _Names

        arity = _BLOCK_BITS + 2
        wide = 2**arity
        register = _Names(arity, 1 << _BLOCK_BITS).table + " "
        whole = boolean.forbin("1" * wide)
        assert whole.count("return(") == 1
        # The constant table paints no block, so defines no shift register.
        assert register not in whole
        # Two constant spans call printers beside the one painted quarter.
        parity = "".join(str(i.bit_count() & 1) for i in range(wide // 4))
        mixed = boolean.forbin("0" * (wide // 2) + "1" * (wide // 4) + parity)
        assert mixed.count("return(") == 3

    def test_full_tree_growth_is_linear(self) -> None:
        """Names and indentation add only a geometric cost to the tree."""
        sizes = []
        for n in range(11, 15):
            parity = "".join(str(i.bit_count() & 1) for i in range(2**n))
            sizes.append(len(boolean.forbin(parity)))
        assert all(later < 2 * earlier for earlier, later in itertools.pairwise(sizes))

    def test_a_repeated_block_is_painted_once(self) -> None:
        """Blocks a b b a share one function per distinct block."""
        from esolangs.languages.forbin.generator import _BLOCK_BITS

        rng = random.Random(7)
        a, b = (
            ",".join(rng.choice("01") for _ in range(2**_BLOCK_BITS)) for _ in range(2)
        )
        table = "".join(block.replace(",", "") for block in (a, b, b, a))
        program = boolean.forbin(table)
        assert program.count(a) == program.count(b) == 1
        for row in (0, 127, 128, 300, 400, 511):
            bits = list(format(row, "09b"))
            assert run_forbin_boolean(program, bits) == table[row]

    @pytest.mark.parametrize(
        ("layout", "size"), [("XXXYXYXY", 1938), ("XXXYXXYX", 1984)]
    )
    def test_nested_repeats_share_once(self, layout: str, size: int) -> None:
        """A repeated subtree costs one function; its insides are not repeats."""
        from esolangs.languages.forbin.generator import _BLOCK_BITS

        rng = random.Random(3)
        blocks = {
            c: "".join(rng.choice("01") for _ in range(2**_BLOCK_BITS)) for c in "XY"
        }
        table = "".join(blocks[c] for c in layout)
        program = boolean.forbin(table)
        assert len(program) == size
        for row in (0, 127, 128, 300, 511, 512, 700, 1023):
            bits = list(format(row, "010b"))
            assert run_forbin_boolean(program, bits) == table[row]


def test_forbin_skips_keywords_at_length_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    from esolangs.languages.forbin.generator import _forbin_names

    module = importlib.import_module("esolangs.languages.forbin.generator")
    monkeypatch.setattr(module, "_FORBIN_ALPHABET", "ab")
    monkeypatch.setattr(module, "_FORBIN_RESERVED", {"a", "ab", "bbb"})
    names = list(itertools.islice(_forbin_names(), 12))
    assert names == [
        "b",
        "aa",
        "ba",
        "bb",
        "aaa",
        "aab",
        "aba",
        "abb",
        "baa",
        "bab",
        "bba",
        "aaaa",
    ]


def _frames_needed(attempt: Callable[[], object], answer: object) -> int:
    """Fewest stack frames above this call that ``attempt`` completes in."""
    depth = len(inspect.stack(0))

    def fits(extra: int) -> bool:
        old = sys.getrecursionlimit()
        sys.setrecursionlimit(depth + extra)
        try:
            return attempt() == answer
        except (RecursionError, HaltError):
            return False
        finally:
            sys.setrecursionlimit(old)

    low, high = 1, 400
    assert fits(high)
    while low < high:
        mid = (low + high) // 2
        low, high = (low, mid) if fits(mid) else (mid + 1, high)
    return low


def test_host_recursion_fits_the_claimed_scaling_range() -> None:
    """Frames for the all-ones row grow per input; n = 134 stays under the limit.

    Measured at n = 9 and 13 (slope 2.5 interpreter, 2 generator frames per
    input), projected linearly: the 2^134-bit table itself cannot be built.
    """
    claimed = 134
    limit = sys.getrecursionlimit() - len(inspect.stack(0)) - 100  # harness slack
    for kind in ("run", "generate"):
        frames = {}
        for n in (9, 13):
            table = "".join(format(j + 1, "0128b") for j in range(1 << (n - 7)))
            if kind == "generate":
                frames[n] = _frames_needed(
                    lambda t=table: esolangs.generate("Forbin", t) and 1, 1
                )
            else:
                program = esolangs.generate("Forbin", table)
                bits = ["1"] * n
                frames[n] = _frames_needed(
                    lambda p=program, b=bits: run_forbin_boolean(p, b), table[-1]
                )
        slope = -(-(frames[13] - frames[9]) // 4)
        projected = frames[13] + slope * (claimed - 13)
        assert 0 < slope <= 6, (kind, frames)
        assert projected < limit, (kind, frames, projected, limit)
