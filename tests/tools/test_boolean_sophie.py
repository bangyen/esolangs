"""Sophie's emitted size, shared prints, folded reads, and unique labels."""

import random
import re

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import _ASCII_ONE, _ASCII_ZERO


class TestSophie:
    def test_leaves_share_one_print_and_01_is_its_read(self) -> None:
        for table in ("01", "10", "0110", "00010100"):
            program = boolean.sophie(table)
            assert program.count(",") == 1
            assert program.endswith(",")
        identity = boolean.sophie("01")
        assert identity.count(";") == 1
        assert "@" not in identity
        assert len(identity) == 2

    def test_every_value_is_its_character(self) -> None:
        programs = [boolean.sophie(format(value, "08b")) for value in range(256)]
        assert all("$" not in program for program in programs)
        assert sum(map(len, programs)) == 8460

    def test_merge_is_linear_where_the_tree_doubles(self) -> None:
        # Executed parity tables add 30 emitted characters per extra input.
        for n in range(4, 9):
            table = "".join(str(row.bit_count() % 2) for row in range(1 << n))
            assert len(boolean.sophie(table)) == 30 * n - 47

    def test_constant_subtrees_fold(self) -> None:
        for n in range(1, 7):
            for value in "01":
                program = boolean.sophie(value * (1 << n))
                assert program.count(";") == n
                assert program.count("#") == 1
                assert program.count(",") == 1
                assert "@" not in program


def _depth_zero_labels(program: str) -> list[int]:
    """Return top-level dispatch labels, excluding input-bit tests."""
    labels: list[int] = []
    depth = index = 0
    while index < len(program):
        char = program[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "#":
            index += 2
            continue
        elif char == "@" and depth == 0:
            match = re.match(r"@(?:\$(\d+)|([^$]))\{", program[index:])
            assert match is not None, program[index:]
            value = int(match[1]) if match[1] else ord(match[2])
            if value not in (_ASCII_ZERO, _ASCII_ONE):
                labels.append(value)
            index += match.end() - 1
            continue
        index += 1
    return labels


class TestSophieLabelsAreUnique:
    MINIMAL = "00000000000000010000000100000100"

    @pytest.mark.parametrize("n", [5, 6, 7, 8])
    def test_no_table_collides_at_any_arity(self, n: int) -> None:
        rng = random.Random(n)
        tables = ["".join(rng.choice("01") for _ in range(1 << n)) for _ in range(20)]
        tables.append("".join(str(int(row.bit_count() == 1)) for row in range(1 << n)))
        if n == 5:
            tables.append(self.MINIMAL)
        for table in tables:
            labels = _depth_zero_labels(boolean.sophie(table))
            assert len(labels) == len(set(labels)), (n, table)

    def test_a_label_is_never_a_bit_value(self) -> None:
        rng = random.Random(5)
        weights = [rng.choice("01") for _ in range(19)]
        table = "".join(weights[row.bit_count()] for row in range(1 << 18))
        labels = _depth_zero_labels(boolean.sophie(table))
        assert 1 in labels  # The numeric fallback is exercised.
        assert _ASCII_ZERO not in labels
        assert _ASCII_ONE not in labels

    def test_the_scan_can_actually_see_a_duplicate(self) -> None:
        assert _depth_zero_labels("@$1{;}@$1{;}") == [1, 1]
        assert _depth_zero_labels("@$1{@$1{;}}") == [1]
        assert _depth_zero_labels('@"{#@}@@{;}@"{;}') == [34, 64, 34]
        assert _depth_zero_labels(";@$48{#$48,&}{#$49,&}") == []
