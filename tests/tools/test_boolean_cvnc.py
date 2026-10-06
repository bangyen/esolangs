"""Covers :mod:`esolangs.tools.cvnc`."""

import importlib
import itertools
import random
from functools import partial

import pytest

from esolangs import tools as boolean
from esolangs.tools.cvnc import (
    _HALT_SQUARINGS,
    _halt,
    _ordered_candidate,
    _prologue_syllables,
    _render,
    _stored,
)
from esolangs.tools.helpers import best_input_order
from tests.tools.boolean_runners import (
    five_input_sample,
    run_cvnc,
)
from tests.witness_tables import witnesses


def _leaves(program: str) -> int:
    """Count the leaves: every one of them ends with the ``j`` that halts."""
    return program.count("j")


def _branches(program: str) -> int:
    """Count the interior nodes: a plain ``ɰ``, not the prologue's ``ɰ̊``."""
    return program.count("\u0270") - program.count("\u0270\u030a")


def _stored_candidate(truth_table: str, perm: tuple[int, ...]) -> str:
    """Adapt :func:`_stored` to :func:`best_input_order`'s contract."""
    tokens = _stored(truth_table, perm)
    return _render(tokens) if tokens is not None else ""


class TestCvnc:
    def test_a_table_that_folds_nothing_is_a_full_tree(self) -> None:
        """Parity folds nowhere, so its plain tree keeps a leaf per row."""
        module = importlib.import_module("esolangs.tools.cvnc")
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
        assert program.count("s") == 5  # one at the root, two per folded arm
        for combo in range(8):
            bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
            assert run_cvnc(program, bits) == "11110000"[combo]

    def test_folding_shortens_the_program(self) -> None:
        assert len(boolean.cvnc("00000000")) < len(boolean.cvnc("01101001"))

    def test_the_halting_goto_clears_every_program_without_escalating(self) -> None:
        """The starting gadget's reach covers every arity worth asking for."""
        module = importlib.import_module("esolangs.tools.cvnc")
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
        # ``esolangs.tools.cvnc`` resolves to the re-exported
        # *function*, so the module has to be fetched by name.
        module = importlib.import_module("esolangs.tools.cvnc")
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

    def test_an_extra_squaring_rebases_shared_jumps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Shared jumps still land after a larger halt prologue."""
        module = importlib.import_module("esolangs.tools.cvnc")
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

    def test_a_zero_input_table_is_refused(self) -> None:
        """A one-entry table is a constant, not a function of any input."""
        for bit in ("0", "1"):
            with pytest.raises(ValueError, match="at least one input"):
                boolean.cvnc(bit)

    def test_the_hoisted_build_reorders_a_table_the_stream_order_cannot_fold(
        self,
    ) -> None:
        """A table folding only on its *last* input is what the reorder is for."""
        squarings = _HALT_SQUARINGS
        program = _halt(squarings) + best_input_order(
            "10101010",
            partial(_ordered_candidate, offset=_prologue_syllables(squarings)),
        )
        assert _leaves(program) == 2  # two leaves, as the reorder intends
        assert _branches(program) == 1
        # The unreordered node-read tree over the same table folds only at the
        # bottom, so it costs a leaf per row.
        module = importlib.import_module("esolangs.tools.cvnc")
        unreordered = module._render(module._tree("10101010"))  # noqa: SLF001
        assert _leaves(unreordered) == 8
        assert len(program) < len(unreordered)

    def test_the_hoisted_build_stores_and_fetches_rather_than_rotating(self) -> None:
        """The bridge between read order and test order is the deque's ends."""
        squarings = _HALT_SQUARINGS
        program = _halt(squarings) + best_input_order(
            "10101010",
            partial(_ordered_candidate, offset=_prologue_syllables(squarings)),
        )
        # Every input is read once and pushed to an end in the same syllable.
        assert program.count("s") == 3
        assert program.count("sum") + program.count("sun") == 3
        # The one surviving node fetches rather than reads.
        assert program.count("cuŋ") + program.count("cuɲ") == 1

    def test_choosing_between_the_builds_never_grows_a_program(self) -> None:
        """The hoist has a price, so it is a candidate and not a replacement."""
        module = importlib.import_module("esolangs.tools.cvnc")
        for value in range(2**8):
            table = bin(value)[2:].zfill(8)
            stream = module._Stream(table, _prologue_syllables(4))  # noqa: SLF001
            module._tree(table, stream)  # noqa: SLF001
            tree = stream.text()
            assert len(boolean.cvnc(table)) <= len(_halt(4)) + len(tree)
        # and parity specifically keeps the node-read build, pushing nothing
        assert not {"m", "n"} & set(boolean.cvnc("01101001"))

    def test_an_unservable_order_is_skipped_rather_than_mispriced(self) -> None:
        """The deque serves the unimodal orders; the rest return no program."""
        module = importlib.import_module("esolangs.tools.cvnc")
        # (0, 2, 1, 3) is the smallest non-unimodal permutation.
        assert module._deque_schedule((0, 2, 1, 3)) is None  # noqa: SLF001
        assert _stored_candidate("0" * 16, (0, 2, 1, 3)) == ""
        # The identity is always unimodal, so a candidate always exists.
        assert module._deque_schedule((0, 1, 2, 3)) is not None  # noqa: SLF001

    @pytest.mark.parametrize(
        ("n", "servable"),
        [(1, 1), (2, 2), (3, 6), (4, 20), (5, 70), (6, 252)],
    )
    def test_the_servable_orders_are_counted_exactly(
        self, n: int, servable: int
    ) -> None:
        """How many permutations the deque serves, per arity."""
        module = importlib.import_module("esolangs.tools.cvnc")

        served = sum(
            1
            for perm in itertools.permutations(range(n))
            if module._deque_schedule(perm) is not None  # noqa: SLF001
        )
        assert served == servable

    def test_a_tie_keeps_the_node_read_tree(self) -> None:
        """The hoisted build must be strictly shorter to be taken."""
        from esolangs.tools.helpers import best_input_order

        module = importlib.import_module("esolangs.tools.cvnc")

        def stored(table: str, perm: tuple[int, ...]) -> str:
            stream = module._Stream(table, _prologue_syllables(4))  # noqa: SLF001
            if module._stored(table, perm, stream) is None:  # noqa: SLF001
                return ""
            return stream.text()

        tied = []
        for value in range(2**8):
            table = bin(value)[2:].zfill(8)
            stream = module._Stream(table, _prologue_syllables(4))  # noqa: SLF001
            module._tree(table, stream)  # noqa: SLF001
            tree = stream.text()
            hoisted = best_input_order(
                table,
                stored,
            )
            if hoisted and len(hoisted) == len(tree):
                tied.append(table)
        assert len(tied) == 4
        for table in tied:
            stream = module._Stream(table, _prologue_syllables(4))  # noqa: SLF001
            module._tree(table, stream)  # noqa: SLF001
            tree = stream.text()
            assert boolean.cvnc(table).endswith(tree)

    def test_a_served_order_pops_from_the_end_holding_its_input(self) -> None:
        """The schedule is not merely non-empty; it is the right one."""
        module = importlib.import_module("esolangs.tools.cvnc")

        for n in (2, 3, 4):
            for perm in itertools.permutations(range(n)):
                schedule = module._deque_schedule(perm)  # noqa: SLF001
                if schedule is None:
                    continue
                pushes, pops = schedule
                assert len(pushes) == n
                assert len(pops) == n
                held: list[int] = []
                for i, push in enumerate(pushes):
                    if push == module._PUSH_FRONT:  # noqa: SLF001
                        held.insert(0, i)
                    else:
                        held.append(i)
                for wanted, pop in zip(perm, pops, strict=True):
                    if pop == module._POP_FRONT:  # noqa: SLF001
                        assert held.pop(0) == wanted, (perm, wanted)
                    else:
                        assert held.pop() == wanted, (perm, wanted)
                assert not held

    def test_a_table_folding_at_its_root_normalizes_the_last_read(self) -> None:
        """The hoisted build's folded root still holds an unpredictable bit."""
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
            body = best_input_order(table, _ordered_candidate)
            plain = len(_halt(_HALT_SQUARINGS)) + len(body)
            shipped = len(boolean.cvnc(table))
            before, after = before + plain, after + shipped
        return before, after

    def test_three_input_total(self) -> None:
        """Three-input retirement stays within five percent of the original."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._totals(tables) == (14_849, 15_192)
        assert 15_192 * 100 < 14_621 * 105

    def test_five_input_sample_total(self) -> None:
        """Five-input retirement stays within five percent of the original."""
        assert self._totals(five_input_sample()) == (39_373, 38_468)
        assert 38_468 * 100 < 37_048 * 105

    def test_the_climb_is_a_closed_form(self) -> None:
        """A target is its nearer square's root climbed to, squared, stepped."""
        module = importlib.import_module("esolangs.tools.cvnc")
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
            plain = best_input_order(table, _ordered_candidate)
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
