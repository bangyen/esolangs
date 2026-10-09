"""Sophie's generator: leaves, character spelling, merged states, labels."""

import random
import re

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import _ASCII_ONE, _ASCII_ZERO
from esolangs.tools.polynomial import _polynomial_states
from esolangs.tools.sophie import _SOPHIE_CHARACTERS, _SOPHIE_RESERVED
from tests.tools.boolean_runners import (
    run_sophie,
    run_sophie_from,
)
from tests.tools.polynomial_support import (
    _sophie_dag,
    _sophie_tree,
)
from tests.tools.test_wrap_preserves_meaning import _WIDTHS, _evaluate
from tests.witness_tables import row_bits


def _printed_once(program: str) -> str:
    """Respell a retired Sophie build's leaves as the shipped one does."""
    program = program.replace(",&", "").replace(";@$48{#$48}{#$49}", ";")
    char = {"48": "0", "49": "1"}
    return re.sub(r"\$(\d+)", lambda m: char.get(m[1], "L"), program) + ","


def _numeric(program: str, *, keep_10: bool = False) -> str:
    """Respell a Sophie build in the ``$`` form it had before characters."""
    single = sorted(_SOPHIE_CHARACTERS - _SOPHIE_RESERVED)
    if keep_10:
        program = program.replace(";@0{#1}{#0}", "\0")

    def respell(match: re.Match[str]) -> str:
        value = ord(match[2])
        number = value if value in _SOPHIE_RESERVED else single.index(value) + 1
        return f"{match[1]}${number}"

    return re.sub(r"([#@])([^$])", respell, program).replace("\0", ";@0{#1}{#0}")


class TestSophie:
    def test_hybrid_subsumes_both_routes(self) -> None:
        """The hybrid is no longer than either prior construction through n=3."""
        from esolangs.tools.sophie import sophie

        improved = 0
        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                hybrid = sophie(table)
                best = min(
                    len(_printed_once(_sophie_tree(table))),
                    len(_printed_once(_sophie_dag(table))),
                )
                assert len(hybrid) <= best
                improved += len(hybrid) < best
        assert improved == 104

    def test_leaves_share_one_print_and_01_is_its_read(self) -> None:
        """A leaf loads its digit, and the one ``,`` at the end prints it."""
        assert boolean.sophie("01") == ";,"
        assert boolean.sophie("0110") == ";@0{;}{;@0{#1}{#0}},"
        assert boolean.sophie("00010100") == ";@0{;@0{;#0}{;}}{;@0{;}{;#0}},"
        old = sum(len(_numeric(boolean.sophie(f"{v:08b}"))) for v in range(256))
        assert old == 11728

    def test_10_tests_its_read_in_the_character_form(self) -> None:
        """A last-level ``10`` is ``;@0{#1}{#0}``, six under the ``$`` form."""
        assert boolean.sophie("1010") == ";;@0{#1}{#0},"
        old = new = 0
        for value in range(256):
            program = _numeric(boolean.sophie(f"{value:08b}"), keep_10=True)
            before = program.replace(";@0{#1}{#0}", ";@$48{#$49}{#$48}")
            assert len(program) <= len(before)
            old, new = old + len(before), new + len(program)
        assert (old, new) == (11728, 10678)

    def test_every_value_is_its_character(self) -> None:
        """``#c`` and ``@c{`` spell every bit and label in one character."""
        program = boolean.sophie("10010110")
        assert program == ';@0{;@0{#"}{;}}{;@0{;}{#"}}@"{;@0{#1}{#0}},'
        old = new = 0
        for value in range(256):
            program = boolean.sophie(f"{value:08b}")
            before = _numeric(program, keep_10=True)
            assert len(program) <= len(before)
            old, new = old + len(before), new + len(program)
        assert (old, new) == (10678, 8460)

    def test_labels_fall_back_to_numbers(self) -> None:
        """Past the single characters, labels are ``$`` numbers that are not."""
        rng = random.Random(5)
        weights = [rng.choice("01") for _ in range(19)]
        table = "".join(weights[row.bit_count()] for row in range(1 << 18))
        program = boolean.sophie(table)
        assert "@$1{" in program
        for row in rng.sample(range(1 << 18), 40):
            bits = [str((row >> (17 - i)) & 1) for i in range(18)]
            assert run_sophie(program, bits) == table[row]

    def test_state_machine_merges_what_the_tree_cannot(self) -> None:
        """A subtable that is not constant can still collapse to one state."""
        table = "10101010"
        assert [len(level) for level in _polynomial_states(table, 3)] == [1, 1, 1, 2]
        assert len(_sophie_dag(table)) < len(_sophie_tree(table))
        program = boolean.sophie(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_sophie(program, [str(b) for b in bits]) == table[combo]

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

    def test_merge_is_linear_where_the_tree_doubles(self) -> None:
        """Parity needs two states per level however wide it gets."""
        previous = None
        for n in (4, 5, 6):
            parity = "".join(str(bin(row).count("1") % 2) for row in range(2**n))
            assert [len(level) for level in _polynomial_states(parity, n)] == [1] + [
                2
            ] * n
            ratio = len(_sophie_dag(parity)) / len(_sophie_tree(parity))
            assert ratio < 1
            if previous is not None:
                assert ratio < previous  # the gap widens with n
            previous = ratio

    def test_every_path_reads_each_input_once(self) -> None:
        """A run consumes exactly ``n`` inputs, whichever build won."""
        for table, n in (("10101010", 3), ("11111111", 3), ("01101001", 3)):
            program = boolean.sophie(table)
            for combo in range(2**n):
                bits = row_bits(combo, n)
                feed = iter([str(b) for b in bits])
                got = run_sophie_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                assert not list(feed), f"{table} inputs {bits} left input unread"

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice prints outright, but still reads its inputs."""
        assert boolean.sophie("1111") == ";;#1,"
        assert boolean.sophie("0000") == ";;#0,"
        assert boolean.sophie("0110").count(";") == 3  # nothing folds


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
            bits = [(combo >> (4 - i)) & 1 for i in range(5)]
            got = run_sophie(boolean.sophie(self.MINIMAL), [str(b) for b in bits])
            assert got == self.MINIMAL[combo], bits

    def test_the_minimal_table_has_no_duplicate_label(self) -> None:
        """Its program carried two ``@$1`` blocks."""
        labels = _depth_zero_labels(boolean.sophie(self.MINIMAL))
        assert len(labels) == len(set(labels)), labels

    @pytest.mark.parametrize("n", [5, 6, 7, 8])
    def test_no_table_collides_at_any_arity(self, n: int) -> None:
        """A structural check, so it reaches arities executing cannot afford."""
        rng = random.Random(n)
        tables = ["".join(rng.choice("01") for _ in range(2**n)) for _ in range(20)]
        tables.append("".join(str(int(bin(r).count("1") == 1)) for r in range(2**n)))
        for table in tables:
            labels = _depth_zero_labels(boolean.sophie(table))
            assert len(labels) == len(set(labels)), (n, table)

    def test_a_label_is_never_a_bit_value(self) -> None:
        """48 and 49 are what a read leaves behind, so a block cannot own one."""
        for n in (6, 7, 8):
            table = "".join(str(int(bin(r).count("1") == 1)) for r in range(2**n))
            labels = _depth_zero_labels(boolean.sophie(table))
            assert _ASCII_ZERO not in labels
            assert _ASCII_ONE not in labels

    def test_the_scan_can_actually_see_a_duplicate(self) -> None:
        """The positive control: a checker that never fires guards nothing."""
        assert _depth_zero_labels("@$1{;}@$1{;}") == [1, 1]
        assert _depth_zero_labels("@$1{@$1{;}}") == [1]  # nested is not top level
        assert _depth_zero_labels('@"{#@}@@{;}@"{;}') == [34, 64, 34]  # characters
        assert _depth_zero_labels(";@$48{#$48,&}{#$49,&}") == []  # bit tests only


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 10, 12])
def test_shared_residual_ids_execute_at_scale(n: int) -> None:
    rng = random.Random(929 + n)
    table = "".join(rng.choice("01") for _ in range(1 << n))
    program = boolean.sophie(table)
    for row in (0, (1 << n) - 1, *[rng.randrange(1 << n) for _ in range(6)]):
        assert run_sophie(program, list(format(row, f"0{n}b"))) == table[row]


@pytest.mark.slow
@pytest.mark.parametrize("width", _WIDTHS)
def test_sophie_survives_the_widths_that_used_to_break_it(width: int) -> None:
    """The regression itself, kept separate so it names the language."""
    assert _evaluate("Sophie", "0110", width) == "0110"
