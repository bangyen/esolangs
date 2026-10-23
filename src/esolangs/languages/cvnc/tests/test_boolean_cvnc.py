"""Covers :mod:`esolangs.languages.cvnc.generator`."""

import importlib
import random
from functools import partial

import pytest

from esolangs.generation.helpers import in_input_order
from esolangs.languages import generators as boolean
from esolangs.languages.cvnc.generator import (
    _HALT_SQUARINGS,
    _direct,
    _halt,
)
from tests.generators.boolean_runners import _runner
from tests.generators.sample_tables import five_input_sample
from tests.support.witness_tables import witnesses

run_cvnc = _runner("cvnc", newline=True)


def _leaves(program: str) -> int:
    """Count the leaves: every one of them ends with the ``j`` that halts."""
    return program.count("j")


def _branches(program: str) -> int:
    """Count the interior nodes: a plain ``ɰ``, not the prologue's ``ɰ̊``."""
    return program.count("\u0270") - program.count("\u0270\u030a")


class TestCvnc:
    def test_a_table_that_folds_nothing_is_a_full_tree(self) -> None:
        """Parity folds nowhere, so its plain tree keeps a leaf per row."""
        module = importlib.import_module("esolangs.languages.cvnc.generator")
        tree = module._render(module._tree("01101001"))  # noqa: SLF001
        assert _leaves(tree) == 8  # one leaf per row
        assert _branches(tree) == 7  # one branch per interior node
        program = boolean.cvnc("01101001")
        assert (_leaves(program), _branches(program)) == (7, 6)

    def test_a_constant_table_folds_to_one_leaf_but_keeps_its_reads(self) -> None:
        """Folding drops the branches, never the reads."""
        for table in ("00000000", "11111111"):
            program = boolean.cvnc(table)
            assert program.count("s") == 3  # still three inputs consumed
            assert _branches(program) == 0  # nothing left to branch on
            assert _leaves(program) == 1  # one leaf for the whole table

    def test_a_one_dependency_table_costs_two_leaves(self) -> None:
        """Depending on one input collapses the other two levels."""
        program = boolean.cvnc("11110000")
        assert _leaves(program) == 2
        assert _branches(program) == 1  # only the root still branches
        assert program.count("s") == 5  # the root's, then two owed on each arm
        for combo in range(8):
            bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
            assert run_cvnc(program, bits) == "11110000"[combo]

    def test_folding_shortens_the_program(self) -> None:
        assert len(boolean.cvnc("00000000")) < len(boolean.cvnc("01101001"))

    def test_the_halting_goto_clears_every_program_without_escalating(self) -> None:
        """The starting gadget's reach covers every arity worth asking for."""
        module = importlib.import_module("esolangs.languages.cvnc.generator")
        reach = module._reach(_HALT_SQUARINGS)  # noqa: SLF001

        # parity is the table that folds nothing, so it is the worst case
        for n in range(1, 9):
            table = "01" * (2**n // 2)
            program = boolean.cvnc(table)
            assert len(program) < reach, f"n={n}"
            assert _halt(_HALT_SQUARINGS + 1) not in program

    def test_a_program_outgrowing_the_goto_gets_another_squaring(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Past the reach every gadget squares once more, until it fits."""
        # ``esolangs.languages.cvnc.generator`` resolves to the re-exported
        # *function*, so the module has to be fetched by name.
        module = importlib.import_module("esolangs.languages.cvnc.generator")
        monkeypatch.setattr(module, "_HALT_SQUARINGS", 0)
        rng = random.Random(7)
        dense = "".join(rng.choice("01") for _ in range(128))
        for table, squarings in (("01", 3), ("0110", 3), (dense, 4)):
            program = module.cvnc(table)
            assert _halt(squarings) in program
            assert _halt(squarings + 1) not in program
            assert len(program) < module._reach(squarings)  # noqa: SLF001
            n = len(table).bit_length() - 1
            for combo in range(len(table)):
                bits = bin(combo)[2:].zfill(n)
                assert run_cvnc(program, bits) == table[combo], (table, bits)

    def test_squarings_match_the_retry_search_it_replaced(self) -> None:
        """The closed form never undershoots the old one-more-squaring loop.

        It equals the search wherever the unshared body and the shared one
        fall on one side of a reach; between them (n=14 at 20% ones: 61,808
        chars against 57,660) it squares once more.
        """
        module = importlib.import_module("esolangs.languages.cvnc.generator")
        rng = random.Random(11)
        for n, density in ((6, 0.5), (10, 0.5), (12, 0.1), (13, 0.5), (14, 0.2)):
            table = "".join(
                "1" if rng.random() < density else "0" for _ in range(1 << n)
            )
            squarings = _HALT_SQUARINGS
            while True:  # the search, kept as the oracle
                offset = module._prologue_syllables(squarings)  # noqa: SLF001
                body = in_input_order(table, partial(_direct, offset=offset))
                if len(_halt(squarings)) + len(body) < module._reach(squarings):  # noqa: SLF001
                    break
                squarings += 1
            program = module.cvnc(table)
            assert program.startswith(_halt(squarings)) or (n, density) == (14, 0.2)
            assert program.startswith(_halt(squarings + 1)) == (
                (n, density) == (14, 0.2)
            )

    def test_an_extra_squaring_rebases_shared_jumps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Shared jumps still land after a larger halt prologue."""
        module = importlib.import_module("esolangs.languages.cvnc.generator")
        monkeypatch.setattr(module, "_HALT_SQUARINGS", 5)
        table = "11101000"
        program = boolean.cvnc(table)
        for combo in range(8):
            bits = bin(combo)[2:].zfill(3)
            assert run_cvnc(program, bits) == table[combo], bits

    def test_every_leaf_ends_by_halting(self) -> None:
        """Without the halting jump a then-arm falls into its own loop end."""
        program = boolean.cvnc("0110")
        assert _leaves(program) == 4
        assert program.count("\u0279") == 1

    def test_a_table_folding_at_its_root_normalizes_the_last_read(self) -> None:
        """A folded root still holds an unpredictable bit."""
        program = boolean.cvnc("00")
        assert "sə" in program  # the floor rides the read's own vowel slot
        for bit in ("0", "1"):
            assert run_cvnc(program, [bit]) == "0"


class TestCvncSharing:
    """A subtree already emitted at its depth is jumped into, not repeated."""

    @staticmethod
    def _totals(tables: list[str]) -> tuple[int, int]:
        """Return plain and shipped character totals."""
        before = after = 0
        for table in tables:
            body = in_input_order(table, _direct)
            plain = len(_halt(_HALT_SQUARINGS)) + len(body)
            shipped = len(boolean.cvnc(table))
            before, after = before + plain, after + shipped
        return before, after

    def test_three_input_total(self) -> None:
        """Three-input retirement stays within five percent of the original."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._totals(tables) == (15_834, 14_893)
        assert 14_893 * 100 < 14_621 * 105

    def test_five_input_sample_total(self) -> None:
        """Five-input sharing totals; the retired hoist cost 4.87% at n=8."""
        assert self._totals(five_input_sample()) == (42_786, 40_121)

    def test_the_climb_is_a_closed_form(self) -> None:
        """A target is its nearer square's root climbed to, squared, stepped."""
        module = importlib.import_module("esolangs.languages.cvnc.generator")
        climb = module._climb  # noqa: SLF001
        assert climb(1, 9) == [("i", 2), ("æ", 1), ("i", 0)]
        # 0, 2, 4, 16, 15: four squared is nearer fifteen than three squared.
        assert climb(0, 15) == [("i", 2), ("æ", 1), ("i", 0), ("æ", 1), ("ə", 1)]
        for start in (0, 1):
            for target in range(2, 400):
                value = start
                for step, count in climb(start, target):
                    for _ in range(count):
                        value = {"i": value + 1, "æ": value * value}.get(
                            step, max(value - 1, 0)
                        )
                assert value == target

    @pytest.mark.parametrize("n", [4, 5, 6])
    def test_a_shared_copy_runs_from_every_arm(self, n: int) -> None:
        """Seeded tables that share run every row, entered from each arm."""
        rng = random.Random(n)
        for _ in range(3):
            table = format(rng.getrandbits(2**n), f"0{2**n}b")
            program = boolean.cvnc(table)
            plain = in_input_order(table, _direct)
            assert not program.endswith(plain), table
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_cvnc(program, bits) == table[combo], f"{table} {bits}"


@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [1, 3, 11])
@pytest.mark.medium
def test_lf_wrapped_generators_execute_every_small_table(n: int, width: int) -> None:
    for table in witnesses(n):
        raw = boolean.cvnc(table)
        wrapped = "\n".join(raw[at : at + width] for at in range(0, len(raw), width))
        for row, expected in enumerate(table):
            inputs = list(format(row, f"0{n}b"))
            assert run_cvnc(wrapped, inputs) == expected


#: A pair spelled alone, by its two bits: constants fold to a read and a leaf.
_PAIR_CHARS = {"00": 5, "01": 11, "10": 12, "11": 7}


def _closed(table: str) -> int:
    """Spell each node as a whole chunk: 5 a node over its halves, 12 a pair."""
    k = len(table).bit_length() - 1
    if len(set(table)) == 1:
        return 2 * k + 5  # k reads at 2, then the leaf
    if k == 1:
        return _PAIR_CHARS[table]
    half = len(table) // 2
    return 5 + _closed(table[:half]) + _closed(table[half:])


class TestCvncScalingBound:
    """Sharing's segment breaks and jumps never beat the chunk spelling."""

    def test_pair_chars_are_what_the_generator_spells(self) -> None:
        module = importlib.import_module("esolangs.languages.cvnc.generator")
        for table, chars in _PAIR_CHARS.items():
            assert len(module._render(module._tree(table))) == chars  # noqa: SLF001

    def test_a_program_is_at_most_its_prologue_and_chunks(self) -> None:
        """The 17T/2 + 13 bound: pairs 12, nodes above 5, prologue <= 18."""
        rng = random.Random(7)
        tables = [format(v, "08b") for v in range(256)]
        tables += [
            "".join("1" if rng.random() < 0.1 + k / 70 else "0" for _ in range(64))
            for k in range(60)
        ]
        for table in tables:
            n = len(table).bit_length() - 1
            assert len(boolean.cvnc(table)) <= 18 + _closed(table), table
            assert _closed(table) <= 17 * 2 ** (n - 1) - 5
