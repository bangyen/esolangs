"""Sophie's generator: leaves, character spelling, merged states, labels."""

import random
import re

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import _ASCII_ONE, _ASCII_ZERO
from esolangs.tools.register import (
    _SOPHIE_CHARACTERS,
    _SOPHIE_RESERVED,
    _polynomial_states,
)
from tests.tools.boolean_oracles import (
    _sophie_dag,
    _sophie_tree,
)
from tests.tools.boolean_runners import (
    run_sophie,
    run_sophie_from,
)


def _printed_once(program: str) -> str:
    """Respell a retired Sophie build's leaves as the shipped one does.

    The oracles halt in every leaf (``,&``) and branch on a last-level
    ``01``; the generator loads the digit, prints once at the end, and lets
    that read stand, and a ``10`` there tests it in the character form.
    Every value is one character, as the generator spells its first 85.
    Respelling them keeps the merge the only difference.
    """
    program = program.replace(",&", "").replace(";@$48{#$48}{#$49}", ";")
    char = {"48": "0", "49": "1"}
    return re.sub(r"\$(\d+)", lambda m: char.get(m[1], "L"), program) + ","


def _numeric(program: str, *, keep_10: bool = False) -> str:
    """Respell a Sophie build in the ``$`` form it had before characters.

    Labels were numbered from 1 in the order the characters now run; with
    ``keep_10`` a last-level ``10`` keeps the character form it had first.
    """
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
        from esolangs.tools.register import _sophie_hybrid

        improved = 0
        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                hybrid = _sophie_hybrid(table)
                best = min(
                    len(_printed_once(_sophie_tree(table))),
                    len(_printed_once(_sophie_dag(table))),
                )
                assert len(hybrid) <= best
                improved += len(hybrid) < best
        assert improved == 104

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111110", 4),  # NAND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.sophie(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_sophie(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function is a single conditional pair."""
        assert boolean.sophie("10") == ";@0{#1}{#0},"

    def test_leaves_share_one_print_and_01_is_its_read(self) -> None:
        """A leaf loads its digit, and the one ``,`` at the end prints it.

        Every later ``@L`` tests a label, which 48 and 49 never are, so a
        leaf runs on to the end instead of printing and halting there.  A
        last-level ``01`` is the read itself, never worth a label.  Over
        every three-input table the program falls from 16,960 characters to
        11,728.
        """
        assert boolean.sophie("01") == ";,"
        assert boolean.sophie("0110") == ";@0{;}{;@0{#1}{#0}},"
        assert boolean.sophie("00010100") == ";@0{;@0{;#0}{;}}{;@0{;}{;#0}},"
        old = sum(len(_numeric(boolean.sophie(f"{v:08b}"))) for v in range(256))
        assert old == 11728

    def test_10_tests_its_read_in_the_character_form(self) -> None:
        """A last-level ``10`` is ``;@0{#1}{#0}``, six under the ``$`` form.

        ``@0`` and ``#1`` test and load the codes ``$48`` and ``$49`` spell,
        so no table grows, and over every three-input table the program
        falls from 11,728 characters to 10,678.
        """
        assert boolean.sophie("1010") == ";;@0{#1}{#0},"
        old = new = 0
        for value in range(256):
            program = _numeric(boolean.sophie(f"{value:08b}"), keep_10=True)
            before = program.replace(";@0{#1}{#0}", ";@$48{#$49}{#$48}")
            assert len(program) <= len(before)
            old, new = old + len(before), new + len(program)
        assert (old, new) == (11728, 10678)

    def test_every_value_is_its_character(self) -> None:
        """``#c`` and ``@c{`` spell every bit and label in one character.

        The interpreter reads ``#$?(.)`` and ``@$?(.){`` as a character's
        code, the form its ``#A,&`` tests use, so ``@0``/``#1`` are the bits
        and labels take the safe printable characters before ``$`` numbers.
        No table grows through four inputs; over every three-input table the
        program falls from 10,678 characters to 8,460.
        """
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
        """Past the single characters, labels are ``$`` numbers that are not.

        A symmetric 18-input table keeps 105 labels; sampled rows execute.
        """
        rng = random.Random(5)
        weights = [rng.choice("01") for _ in range(19)]
        table = "".join(weights[row.bit_count()] for row in range(1 << 18))
        program = boolean.sophie(table)
        assert "@$1{" in program
        for row in rng.sample(range(1 << 18), 40):
            bits = [str((row >> (17 - i)) & 1) for i in range(18)]
            assert run_sophie(program, bits) == table[row]

    def test_state_machine_merges_what_the_tree_cannot(self) -> None:
        """A subtable that is not constant can still collapse to one state.

        ``10101010`` is NOT of the last input: the nested tree branches at
        every level, while every prefix leaves the same residual
        subfunction, so the chain needs one state per level until the last.
        The accumulator carries the state label between levels, which is
        what a nested construction cannot express.
        """
        table = "10101010"
        assert [len(level) for level in _polynomial_states(table, 3)] == [1, 1, 1, 2]
        assert len(_sophie_dag(table)) < len(_sophie_tree(table))
        program = boolean.sophie(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_sophie(program, [str(b) for b in bits]) == table[combo]

    def test_merge_only_shrinks(self) -> None:
        """No table comes out longer than the nested tree alone.

        The hybrid inlines unshared states as tree branches, so labels only
        pay for actual merges. At n == 3, 102 of 256 tables shrink.
        """
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.sophie(table))
            tree = len(_printed_once(_sophie_tree(table)))
            assert dispatched <= tree, table
            improved += dispatched < tree
        assert improved == 102

    def test_merge_is_linear_where_the_tree_doubles(self) -> None:
        """Parity needs two states per level however wide it gets.

        Parity is the nested tree's worst case at every width -- nothing
        folds, so it branches at all ``2**n - 1`` internal nodes -- and is
        the merge's best, since the running parity is the whole state.  The
        saving therefore grows with ``n`` rather than being a fixed trim.
        """
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
        """A run consumes exactly ``n`` inputs, whichever build won.

        The tree spends the reads a folded leaf skipped; the state machine
        reads once inside the single block each level's chain fires.  An
        exhaustible feed proves both directions -- an over-read raises, a
        leftover proves an under-read.
        """
        for table, n in (("10101010", 3), ("11111111", 3), ("01101001", 3)):
            program = boolean.sophie(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                feed = iter([str(b) for b in bits])
                got = run_sophie_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                assert not list(feed), f"{table} inputs {bits} left input unread"

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice prints outright, but still reads its inputs.

        Sophie reads *inside* the tree -- a node is ``;`` then its branch
        -- so a folded leaf carries the ``;`` it skipped.  Dropping them
        would make the program's input count depend on its table, which
        :mod:`tests.tools.test_boolean_contract` rejects for every
        generator.
        """
        assert boolean.sophie("1111") == ";;#1,"
        assert boolean.sophie("0000") == ";;#0,"
        assert boolean.sophie("0110").count(";") == 3  # nothing folds


def _depth_zero_labels(program: str) -> list[int]:
    """Every ``@$N`` or ``@c`` block label at the top level of ``program``.

    Sophie dispatches by setting the accumulator with ``#$N`` (or ``#c``)
    and falling through the top-level ``@$N{...}`` blocks, so two blocks
    sharing an ``N`` means the first also fires.  48 and 49 are excluded:
    those are the bit tests, which are not dispatch labels.  A ``#`` load's
    character is data, so it is skipped with the ``#``.
    """
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
    """Two blocks with one label make the first fire on the way past.

    Labels used to come from two bands chosen by level parity, on the
    reasoning that a fired block leaves a *next*-level label in the
    accumulator which no remaining test in the chain can match.  That is
    true of consecutive levels and consecutive levels are not the relation
    that matters: unshared states are inlined, so a single top-level block
    carries jumps originating at several depths, and levels 2 and 4 -- same
    parity, same band -- were both targets from inside it.  Level 2 is
    emitted first, so a jump meant for level 4 ran level 2 first and read
    inputs the caller never supplied.

    The failure is *shape*-dependent, not size-dependent, which is why it
    survived: Sophie is correct on all 65536 tables at n <= 4, and collides
    on 35% of random tables at n=7.
    """

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
        """A structural check, so it reaches arities executing cannot afford.

        Sampled rather than exhaustive, with a fixed seed: at n=8 the old
        scheme collided on 88% of random tables, so twenty is ample to
        catch a regression and cheap enough to run every time.  The shapes
        that first exposed this are included by name, since a random sample
        is exactly what missed it for so long.
        """
        rng = random.Random(n)
        tables = ["".join(rng.choice("01") for _ in range(2**n)) for _ in range(20)]
        tables.append("".join(str(int(bin(r).count("1") == 1)) for r in range(2**n)))
        for table in tables:
            labels = _depth_zero_labels(boolean.sophie(table))
            assert len(labels) == len(set(labels)), (n, table)

    def test_a_label_is_never_a_bit_value(self) -> None:
        """48 and 49 are what a read leaves behind, so a block cannot own one.

        Nothing else is reserved -- the interpreter parses a label as a
        plain digit run -- so this is the whole constraint, and it binds
        only once the count climbs past 47.
        """
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
