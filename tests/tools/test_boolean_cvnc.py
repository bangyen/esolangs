"""Covers :mod:`esolangs.tools.cvnc`."""

import importlib
import itertools

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_cvnc,
)


class TestCvnc:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # AND4
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.cvnc(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_cvnc(program, bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_a_table_that_folds_nothing_is_a_full_tree(self) -> None:
        """Parity folds nowhere, so it keeps a leaf per row."""
        program = boolean.cvnc("01101001")
        assert program.count("fu") == 8  # one leaf per row
        assert program.count("\u0270\u030ao") == 7  # one branch per interior node

    def test_a_constant_table_folds_to_one_leaf_but_keeps_its_reads(self) -> None:
        """Folding drops the branches, never the reads."""
        for table in ("00000000", "11111111"):
            program = boolean.cvnc(table)
            assert program.count("so") == 3  # still three inputs consumed
            assert program.count("\u0270\u030ao") == 0  # nothing left to branch on
            assert program.count("fu") == 1  # one leaf for the whole table

    def test_a_one_dependency_table_costs_two_leaves(self) -> None:
        """Depending on one input collapses the other two levels.

        This table is where the hoisted build wins, so the three reads are
        the load block's and appear once each rather than once per folded
        path.  Either way only the root branches and only two leaves remain.
        """
        program = boolean.cvnc("11110000")
        assert program.count("fu") == 2
        assert program.count("\u0270\u030ao") == 1  # only the root still branches
        assert program.count("so") == 3  # three inputs, read once each
        for combo in range(8):
            bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
            assert run_cvnc(program, bits) == "11110000"[combo]

    def test_folding_shortens_the_program(self) -> None:
        assert len(boolean.cvnc("00000000")) < len(boolean.cvnc("01101001"))

    def test_the_halting_goto_covers_every_arity_the_generator_emits(self) -> None:
        """The gadget's reach is the generator's arity bound, and is checked.

        The goto lands at a fixed offset, so a program longer than that
        offset would jump back *into itself* instead of halting.  The
        generator raises rather than emit one, and the reach is chosen so
        that no arity it can practically be asked for trips the guard.
        """
        module = importlib.import_module("esolangs.tools.cvnc")
        reach = module._HALT_REACH  # noqa: SLF001

        # parity is the table that folds nothing, so it is the worst case
        for n in range(1, 9):
            table = "01" * (2**n // 2)
            assert len(boolean.cvnc(table)) < reach, f"n={n}"

    def test_a_program_outgrowing_the_goto_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The guard raises rather than emitting a self-re-entering program.

        The reach is far past any table worth generating, so the guard is
        reached by shrinking it rather than by building a vast table.
        """
        # ``esolangs.tools.cvnc`` resolves to the re-exported
        # *function*, so the module has to be fetched by name.
        module = importlib.import_module("esolangs.tools.cvnc")
        monkeypatch.setattr(module, "_HALT_REACH", 10)
        with pytest.raises(ValueError, match="outgrew"):
            module.cvnc("01")

    def test_every_leaf_ends_by_halting(self) -> None:
        """Without the halting goto a then-arm falls into its own loop end."""
        program = boolean.cvnc("0110")
        assert program.count("\u0279i") == program.count("fu")

    def test_a_zero_input_table_is_refused(self) -> None:
        """A one-entry table is a constant, not a function of any input."""
        for bit in ("0", "1"):
            with pytest.raises(ValueError, match="at least one input"):
                boolean.cvnc(bit)

    def test_the_hoisted_build_reorders_a_table_the_stream_order_cannot_fold(
        self,
    ) -> None:
        """A table folding only on its *last* input is what the reorder is for.

        ``10101010`` is ``11110000``'s function with the inputs renamed, so
        the node-read tree cannot fold it at the root while the hoisted one
        tests input 2 first and folds after a single branch.  The win has to
        show up as a shorter program, not merely a different one.
        """
        program = boolean.cvnc("10101010")
        assert program.count("fu") == 2  # two leaves, as the reorder intends
        assert program.count("ɰ̊o") == 1
        # The unreordered node-read tree over the same table folds only at the
        # bottom, so it costs a leaf per row.
        module = importlib.import_module("esolangs.tools.cvnc")
        unreordered = module._tree("10101010", 0)  # noqa: SLF001
        assert unreordered.count("fu") == 8
        assert len(program) < len(unreordered)

    def test_the_hoisted_build_stores_and_fetches_rather_than_rotating(self) -> None:
        """The bridge between read order and test order is the deque's ends."""
        program = boolean.cvnc("10101010")
        # Every input is read once and pushed to an end in the same syllable.
        assert program.count("so") == 3
        assert program.count("som") + program.count("son") == 3
        # The one surviving node fetches rather than reads.
        assert program.count("cuŋ") + program.count("cuɲ") == 1

    # 256 tables at eight rows each, all of it in the interpreter.
    @pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.medium)])
    def test_every_table_computes_its_function(self, n: int) -> None:
        """Exhaustive over the stream and reordered paths."""
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            program = boolean.cvnc(table)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_cvnc(program, bits) == table[combo], f"{table} {bits}"

    def test_choosing_between_the_builds_never_grows_a_program(self) -> None:
        """The hoist has a price, so it is a candidate and not a replacement.

        Parity is the table it loses on: nothing folds, so the load block's
        nasals and the per-node fetch are paid for with no fold to show for
        them, and the node-read tree must still be the one returned.
        """
        module = importlib.import_module("esolangs.tools.cvnc")
        for value in range(2**8):
            table = bin(value)[2:].zfill(8)
            assert len(boolean.cvnc(table)) <= len(module._tree(table, 0))  # noqa: SLF001
        # and parity specifically keeps the node-read build
        assert boolean.cvnc("01101001") == module._tree("01101001", 0)  # noqa: SLF001

    def test_an_unservable_order_is_skipped_rather_than_mispriced(self) -> None:
        """The deque serves the unimodal orders; the rest return no program.

        ``best_input_order`` reads an empty candidate as "this order could
        not be built" and skips it, so returning one is how an unservable
        order declines. Substituting some other program would let it win on
        a length it never paid.
        """
        module = importlib.import_module("esolangs.tools.cvnc")
        # (0, 2, 1, 3) is the smallest non-unimodal permutation.
        assert module._deque_schedule((0, 2, 1, 3)) is None  # noqa: SLF001
        assert module._stored_candidate("0" * 16, (0, 2, 1, 3)) == ""  # noqa: SLF001
        # The identity is always unimodal, so a candidate always exists.
        assert module._deque_schedule((0, 1, 2, 3)) is not None  # noqa: SLF001

    @pytest.mark.parametrize(
        ("n", "servable"),
        [(1, 1), (2, 2), (3, 6), (4, 20), (5, 70), (6, 252)],
    )
    def test_the_servable_orders_are_counted_exactly(
        self, n: int, servable: int
    ) -> None:
        """How many permutations the deque serves, per arity.

        The ends are chosen by *search* over the ``2**n`` push assignments,
        with the pops then forced, and the search returns the first
        assignment that works.  That makes the two ends' bit tests
        surprisingly hard to break visibly: scrambling which bit selects
        which end still finds *a* working assignment for many orders, so
        the generator keeps emitting correct programs and only the size of
        the servable set moves.  Measured at four inputs, the shift and
        mask edits take it from 20 down to 8 or 16 while every program
        that is still built stays right.

        The counts are the documented ones (all six at three inputs, 20 of
        24 at four, 252 of 720 at six) and they are the whole observable,
        so they are asserted rather than sampled.
        """
        module = importlib.import_module("esolangs.tools.cvnc")

        served = sum(
            1
            for perm in itertools.permutations(range(n))
            if module._deque_schedule(perm) is not None  # noqa: SLF001
        )
        assert served == servable

    def test_a_tie_keeps_the_node_read_tree(self) -> None:
        """The hoisted build must be strictly shorter to be taken.

        Sixteen of the 256 three-input tables build a hoisted program of
        exactly the tree's length, so ``<`` and ``<=`` ship different
        programs of *identical size*: invisible to a length bound and to
        every truth-table assertion, since both shapes compute the table.
        All sixteen keep the tree.

        The comparison has to be driven through ``best_input_order``, the
        way the generator does it -- that helper permutes the *table* per
        order, so calling ``_ordered_candidate`` on the unpermuted one and
        taking the best is a different quantity, and gives a different set.
        """
        from esolangs.tools.helpers import best_input_order

        module = importlib.import_module("esolangs.tools.cvnc")

        tied = []
        for value in range(2**8):
            table = bin(value)[2:].zfill(8)
            tree = module._tree(table, 0)  # noqa: SLF001
            hoisted = best_input_order(
                table,
                module._stored_candidate,  # noqa: SLF001
            )
            if hoisted and len(hoisted) == len(tree):
                tied.append(table)
        assert len(tied) == 16
        for table in tied:
            assert boolean.cvnc(table) == module._tree(table, 0)  # noqa: SLF001

    def test_a_served_order_pops_from_the_end_holding_its_input(self) -> None:
        """The schedule is not merely non-empty; it is the right one.

        A count says how many orders are served, not that the pushes and
        pops agree with each other.  Replaying the schedule against a
        model deque is what checks that, and it is the property the
        construction rests on -- a pop from the wrong end reads another
        input's bit and the tree tests the wrong variable.
        """
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
                    if pop == module._FETCH_FRONT:  # noqa: SLF001
                        assert held.pop(0) == wanted, (perm, wanted)
                    else:
                        assert held.pop() == wanted, (perm, wanted)
                assert not held

    def test_a_table_folding_at_its_root_normalizes_the_last_read(self) -> None:
        """The hoisted build's folded root still holds an unpredictable bit.

        No branch has run, so the accumulator is whatever the load block read
        last rather than a bit the tree chose.  Without the ``cə`` the leaf
        climbs from that and prints one too many for a 1 input.
        """
        module = importlib.import_module("esolangs.tools.cvnc")
        program = module._ordered("00", (0,))  # noqa: SLF001
        assert program is not None
        assert "cə" in program
        for bit in ("0", "1"):
            assert run_cvnc(program, [bit]) == "0"
