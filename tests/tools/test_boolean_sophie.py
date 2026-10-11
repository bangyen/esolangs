"""Sophie's generator: leaves, character spelling, merged states, labels."""

import random
import re

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import _ASCII_ONE, _ASCII_ZERO
from tests.support.witness_tables import row_bits
from tests.tools.boolean_runners import run_sophie, run_sophie_from
from tests.tools.sophie_support import _residual_levels, _sophie_dag, _sophie_tree


def _printed_once(program: str) -> str:
    """Respell a retired Sophie build's leaves as the shipped one does."""
    program = program.replace(",&", "").replace(";@$48{#$48}{#$49}", ";")
    char = {"48": "0", "49": "1"}
    return re.sub(r"\$(\d+)", lambda m: char.get(m[1], "L"), program) + ","


class TestSophie:
    def test_character_spelling_and_constant_folding(self) -> None:
        """A leaf loads its digit and one ``,`` prints it; characters compact."""
        assert boolean.sophie("01") == ";,"
        assert boolean.sophie("0110") == ";@0{;}{;@0{#1}{#0}},"
        assert boolean.sophie("1010") == ";;@0{#1}{#0},"
        assert boolean.sophie("1111") == ";;#1,"
        assert boolean.sophie("0000") == ";;#0,"
        assert sum(len(boolean.sophie(f"{v:08b}")) for v in range(256)) == 8460

    def test_labels_fall_back_to_numbers(self) -> None:
        """Past the single characters, labels are ``$`` numbers that are not."""
        rng = random.Random(5)
        weights = [rng.choice("01") for _ in range(19)]
        table = "".join(weights[row.bit_count()] for row in range(1 << 18))
        program = boolean.sophie(table)
        assert "@$1{" in program
        for row in rng.sample(range(1 << 18), 20):
            bits = [str((row >> (17 - i)) & 1) for i in range(18)]
            assert run_sophie(program, bits) == table[row]

    def test_state_machine_merges_what_the_tree_cannot(self) -> None:
        """A subtable that is not constant can still collapse to one state."""
        table = "10101010"
        assert [len(level) for level in _residual_levels(table, 3)] == [1, 1, 1, 2]
        assert len(_sophie_dag(table)) < len(_sophie_tree(table))

    def test_merge_only_shrinks(self) -> None:
        """No table comes out longer than the nested tree alone."""
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.sophie(table))
            tree = len(_printed_once(_sophie_tree(table)))
            assert dispatched <= tree, table
            improved += dispatched < tree
        assert improved == 102

    def test_every_path_reads_each_input_once(self) -> None:
        """A run consumes exactly ``n`` inputs, whichever build won."""
        for table, n in (("10101010", 3), ("11111111", 3), ("01101001", 3)):
            program = boolean.sophie(table)
            for combo in range(2**n):
                bits = row_bits(combo, n)
                feed = iter([str(b) for b in bits])
                assert run_sophie_from(program, feed) == table[combo], (table, bits)
                assert not list(feed), (table, bits)


def _depth_zero_labels(program: str) -> list[int]:
    """Every ``@$N`` or ``@c`` block label at the top level of ``program``."""
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
    """Two blocks with one label make the first fire on the way past."""

    #: The smallest table that collides, found by exhaustive search upward.
    MINIMAL = "00000000000000010000000100000100"

    def test_the_minimal_colliding_table_computes(self) -> None:
        """It raised ``read past the end of input: 5 lines supplied, read 6``."""
        assert boolean.sophie(self.MINIMAL)  # builds, and always did
        for combo in range(32):
            bits = [str((combo >> (4 - i)) & 1) for i in range(5)]
            got = run_sophie(boolean.sophie(self.MINIMAL), bits)
            assert got == self.MINIMAL[combo], bits

    def test_the_scan_can_actually_see_a_duplicate(self) -> None:
        """The positive control: a checker that never fires guards nothing."""
        assert _depth_zero_labels("@$1{;}@$1{;}") == [1, 1]
        assert _depth_zero_labels("@$1{@$1{;}}") == [1]  # nested is not top level
        assert _depth_zero_labels('@"{#@}@@{;}@"{;}') == [34, 64, 34]
        assert _depth_zero_labels(";@$48{#$48,&}{#$49,&}") == []  # bit tests only


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 12])
def test_shared_residual_ids_execute_at_scale(n: int) -> None:
    rng = random.Random(929 + n)
    table = "".join(rng.choice("01") for _ in range(1 << n))
    program = boolean.sophie(table)
    for row in (0, (1 << n) - 1, *[rng.randrange(1 << n) for _ in range(6)]):
        assert run_sophie(program, list(format(row, f"0{n}b"))) == table[row]
