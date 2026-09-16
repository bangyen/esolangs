"""Covers :mod:`esolangs.tools.slow_acv_mammalian`."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_slow_acv_mammalian,
)


class TestSlowAcvMammalian:
    """The decision tree LEAPFROG makes possible.

    ``ACCEPT`` appends the bit to array 0 whatever the pointer holds, and
    ``LEAPFROG`` jumps exactly when the array's last element is nonzero, so
    the bit just read is the branch condition and nothing has to be routed.
    """

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            # These carried ``slow`` while the generator searched: 3.5s at
            # worst, 1.68s after the landings were first solved.  The whole
            # construction is closed-form now -- a build is 0.3ms and this
            # case is dominated by the eight interpreter runs, measured
            # 2026-09-05 at 0.07s -- so they rejoin the fast run.
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.slow_acv_mammalian(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_slow_acv_mammalian(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_tables_still_read_every_input(self) -> None:
        """A constant table consumes all ``n`` inputs.

        The reads are the language's interface, and leaving a caller's bits
        on the input stream would break whatever runs next.  The chain
        carries exactly one ``ACCEPT`` per input and executes all of them
        unconditionally -- there is no subtree to fold a constant into.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        for table in ("0000", "1111", "0110"):
            program = boolean.slow_acv_mammalian(table)
            assert program.split().count("ACCEPT") == 2  # one per input
            io_obj = ScriptedIO("0\n" * 8)
            run_until_halt_or_cycle(_Machine(program, io_obj))
            assert io_obj.position() == 2

    def test_routing_is_confined_to_the_arms_and_the_dispatch(self) -> None:
        """Exactly ``2n + 1`` ``SPRINT``s: out and back per arm, one out.

        ``ACCEPT`` appends to array 0 whatever the pointer holds, so the
        reads never route; the pointer leaves array 0 only to bank a
        weight on array 16 (each 1-arm goes out and comes back) and once
        at the end, when the dispatch trampoline jumps from array 16 into
        the leaf table.  A count off by one would mean a read or a merge
        running on the wrong array.
        """
        for table, n in (("01", 1), ("0110", 2), ("01101001", 3)):
            tokens = boolean.slow_acv_mammalian(table).split()
            assert tokens.count("SPRINT") == 2 * n + 1
            assert "CONFLAGRATE" not in tokens

    def test_a_node_opens_the_accumulator_on_a_clean_digit(self) -> None:
        """``ACCEPT`` is entered with ``acc % 256 == 48``, whatever the state.

        The whole construction rests on this: a node normalizes the
        accumulator so ``'0'``/``'1'`` XORs down to a bare ``0``/``1``.
        The aim class delivers it by arithmetic -- ``first`` even with bits
        4-5 ``01``, so the fixed ``+16`` run flips exactly those bits --
        and a state whose low byte drifted off 48 would append a junk byte
        and branch on something other than the bit just read.  Recovered
        here from either exit: XORing the exit accumulator against the exit
        sum reproduces what ``ACCEPT`` saw.
        """
        from esolangs.tools.slow_acv_mammalian import _node

        for array, acc in (
            ([0], 0),
            ([3, 255, 255], 0),
            ([200, 17, 9], 128),
            ([254, 1, 77, 30], 99999),
        ):
            _, fell, taken, _ = _node(list(array), acc)
            assert (fell[1] ^ sum(fell[0])) % 256 == 48
            assert (taken[1] ^ sum(taken[0])) % 256 == 48

    def test_the_landing_is_start_minus_15(self) -> None:
        """A 1-bit resumes exactly 15 tokens short of the array sum.

        This is the identity that replaced the 256-candidate sweep: on the
        aim class the ``j1`` seeds cancel out of the jump arithmetic, so
        the landing is a pure function of the sum and aiming is done by
        stashing ballast, never by trying candidates.  Machine-backed
        rather than re-derived, so a drift in either the generator's
        algebra or the interpreter's ``LEAPFROG`` shows up here.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.tools.slow_acv_mammalian import _node, _seeded

        for array, acc in (([3, 255, 255, 255], 7), ([90, 200, 200, 255], 4242)):
            tokens, _, taken, landing = _node(list(array), acc)
            wrap = (256 - array[0]) % 256
            start = sum([*_seeded(array, wrap), acc % 256])
            assert landing == start - 15
            padded = [*tokens, *["SEED"] * (landing + 2 - len(tokens))]
            machine = _Machine(" ".join(padded), ScriptedIO("1\n"))
            machine.lst = (tuple(array), *machine.lst[1:])
            machine.acc = acc
            while not machine.halted and machine.ind < len(tokens):
                machine.step()
            assert machine.ind == landing
            assert list(machine.lst[0]) == taken[0]
            assert machine.acc == taken[1]

    def test_the_trampoline_jump_ignores_the_head(self) -> None:
        """The trampoline lands on its target from any head value.

        ``LEAPFROG``'s target is ``acc - head - 1`` and the final
        ``DIGEST`` folds the head into the accumulator, so the head cancels
        and the landing is the non-head sum plus the appended byte.  That
        cancellation is what makes the jump *solvable* -- no candidate ever
        has to be tried -- and it holds through a ``SEED`` run that wraps
        the head, which drops the array sum by 256 but not the target.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.tools.slow_acv_mammalian import _trampoline

        target = 900
        for head in (0, 130, 255):
            array = [head, 255, 255, 200]
            tokens, out_array, out_acc = _trampoline(list(array), 5000, target)
            padded = [*tokens, *["SEED"] * (target + 2 - len(tokens))]
            machine = _Machine(" ".join(padded), ScriptedIO(""))
            machine.lst = (tuple(array), *machine.lst[1:])
            machine.acc = 5000
            while not machine.halted and machine.ind < len(tokens):
                machine.step()
            assert machine.ind == target, f"head {head}"
            assert list(machine.lst[0]) == out_array
            assert machine.acc == out_acc

    def test_the_shortest_hop_still_fires(self) -> None:
        """A hop of one token appends ``b == 1``, the least firing byte.

        The trampoline's ``LEAPFROG`` fires because the appended byte is
        the array's last element, so ``b == 0`` would fall through into the
        dead pad and execute garbage.  ``_MIN_HOP`` exists to keep the
        emitter's targets off that edge, and this pins the edge itself:
        the shortest representable hop still jumps.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.tools.slow_acv_mammalian import _trampoline

        array = [5, 255, 255, 255]
        target = sum(array) - array[0] + 1
        tokens, out_array, _ = _trampoline(list(array), 0, target)
        assert out_array[-1] == 1
        machine = _Machine(
            " ".join([*tokens, *["SEED"] * (target + 2 - len(tokens))]),
            ScriptedIO(""),
        )
        machine.lst = (tuple(array), *machine.lst[1:])
        while not machine.halted and machine.ind < len(tokens):
            machine.step()
        assert machine.ind == target

    def test_ballast_is_spent_where_it_stands(self) -> None:
        """No ``CONSUME`` or ``FISSION``: no cell is ever indexed.

        The build tracks only heads and non-head sums (see ``_Sums``), and
        that is sound precisely because the emitted program never touches
        a cell by position -- ``SPRINT`` reads ``curr[0]`` with a zeroed
        accumulator and every ``LEAPFROG``'s firing cell is appended by
        its own code.  The program says so: only the seven ops the
        construction needs appear.
        """
        program = boolean.slow_acv_mammalian("0110")
        used = set(program.split())
        assert used <= {
            "SEED",
            "EXCRETE",
            "DIGEST",
            "ACCEPT",
            "PRONOUNCE",
            "LEAPFROG",
            "SPRINT",
        }

    def test_a_stale_slot_bound_is_caught_not_emitted(self) -> None:
        """An arm too wide for its slot raises, loudly.

        The slot is the one place the construction leans on a bound rather
        than an exact solve, so a stale ``_tramp_bound`` must surface as
        an error naming the overflow -- not as a program whose merge
        trampoline spills past its slot and lands the two branch paths at
        different addresses.
        """
        import importlib

        # The package re-exports the generator under its own module's
        # name, so the package attribute is the *function*; only
        # import_module reaches the module.
        module = importlib.import_module("esolangs.tools.slow_acv_mammalian")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_tramp_bound", lambda _distance: 0)
            with pytest.raises(AssertionError, match="slot"):
                module.slow_acv_mammalian("0110")

    @pytest.mark.parametrize("amount", [0, 100, 256, 600, 2000])
    def test_a_weight_raise_is_exact_on_the_machine(self, amount: int) -> None:
        """``_w_raise`` moves array 16's non-head sum by exactly its ask.

        The weights are the construction's dispatch index, so a raise that
        overshot by one would land every affected row on the wrong leaf.
        The amounts cover each closing shape: nothing to do, one exact
        chunk, the two-chunk split, and greedy high bytes first.  Run on
        the machine so the step-17 head arithmetic is the interpreter's,
        not the builder's.
        """
        import importlib

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        module = importlib.import_module("esolangs.tools.slow_acv_mammalian")
        st = module._Sums()  # noqa: SLF001
        st.ptr, st.hw, st.nw = 16, 9, 255
        tokens = module._w_raise(st, amount)  # noqa: SLF001
        machine = _Machine(" ".join(tokens), ScriptedIO(""))
        machine.ptr = 16
        machine.lst = tuple((9, 200, 55) if k == 16 else (0,) for k in range(23))
        while not machine.halted:
            machine.step()
        array = machine.lst[16]
        assert sum(array) - array[0] == 255 + amount
        assert (st.nw, st.hw) == (255 + amount, array[0])

    def test_the_dispatch_lands_every_row_on_its_own_leaf(self) -> None:
        """Each run halts inside the leaf slot its inputs selected.

        The construction's one data-dependent jump is the dispatch: the
        banked weights shift array 16's non-head sum by ``row * 256``, so
        the same fixed trampoline must land run ``row`` at
        ``leaf_base + row * 256``.  Recovering the slot from the halt
        cursor pins that arithmetic through the machine rather than
        through the builder's own model of it.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        table = "01101001"
        program = boolean.slow_acv_mammalian(table)
        tokens = program.split()
        leaf_base = len(tokens) - 256 * len(table)
        for row in range(8):
            bits = [(row >> (2 - i)) & 1 for i in range(3)]
            machine = _Machine(program, ScriptedIO("".join(f"{b}\n" for b in bits)))
            while not machine.halted:
                machine.step()
            assert (machine.ind - leaf_base) // 256 == row

    def test_the_emitted_size_is_pinned_and_linear(self) -> None:
        """Exact sizes per arity, and the leaf table is the whole growth.

        The construction is deterministic, so three sizes pin every piece
        -- a node, an arm, a slot or the dispatch drifting shows here
        first.  The differences also carry the linearity: each added input
        costs one more level (whose arm doubles) plus the doubled leaf
        table, so per-entry cost falls toward the 256-token slot floor
        instead of growing.
        """
        sizes = [
            len(boolean.slow_acv_mammalian(table))
            for table in ("01", "0110", "01101001")
        ]
        assert sizes == [22_531, 40_555, 58_472]
