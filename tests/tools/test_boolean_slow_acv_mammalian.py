"""Covers :mod:`esolangs.tools.slow_acv_mammalian`."""

import random

import pytest

from esolangs import tools as boolean
from esolangs.tools.slow_acv_mammalian import (
    _greedy_advance,
    _stash_chunk,
    _Sums,
    _trampoline,
    _trampoline_len,
    _w_raise,
    _w_raise_len,
)
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
            # at 0.07s -- so they rejoin the fast run.
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

    def test_routing_is_accounted_for_array_by_array(self) -> None:
        """Every ``SPRINT`` belongs to a named errand, and none is spare.

        ``ACCEPT`` appends to array 0 whatever the pointer holds, so the
        reads never route.  The pointer leaves array 0 to plant each print
        array and each pool (out and back), to raise array 16 to the leaf
        base (out and back), once per arm -- twice for a solved weight,
        three times for a pooled one, whose middle hop is the ride the
        planted cell pays for -- once for the dispatch, and once inside
        whichever leaf the run lands on.  A count off by one would mean a
        read or a merge running on the wrong array.
        """
        for table, n, pools in (("01", 1, 0), ("0110", 2, 1), ("01101001", 3, 2)):
            tokens = boolean.slow_acv_mammalian(table).split()
            arms = 2 * (n - pools) + 3 * pools
            assert tokens.count("SPRINT") == 4 + 2 * pools + 2 + arms + 1 + len(table)
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

    def test_only_the_construction_s_own_opcodes_appear(self) -> None:
        """Eight opcodes, and ``FISSION`` is not one of them.

        Arrays 0 and 16 are never indexed -- ``SPRINT`` reads ``curr[0]``
        with a zeroed accumulator and every ``LEAPFROG``'s firing cell is
        appended by its own code -- which is what lets the build track
        them as a head and a sum (see ``_Sums``).  ``CONSUME`` indexes
        only the small planted arrays, and ``FISSION``, which would
        halve a cell and move every index after it, appears nowhere.
        """
        program = boolean.slow_acv_mammalian("0110")
        used = set(program.split())
        assert used == {
            "SEED",
            "EXCRETE",
            "DIGEST",
            "ACCEPT",
            "PRONOUNCE",
            "LEAPFROG",
            "SPRINT",
            "CONSUME",
        }

    def test_a_pooled_weight_is_blind_to_what_array_16_holds(self) -> None:
        """The pool banks its byte from any starting sum, unchanged.

        This is the property the whole stride rests on.  A solved chunk
        reads array 16's sum, so two runs that reached the arm with
        different sums would append different bytes -- which is why every
        solved weight has to be a multiple of 256.  The pool never reads
        it: ``CONSUME`` lifts a planted byte, ``SPRINT`` rides it over and
        ``EXCRETE`` drops it.  Run here from sums 256 apart *and* from
        sums that are not, which a solved chunk could never survive.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.slow_acv_mammalian")
        banked = set()
        for offset in (0, 1, 17, 255, 256, 4097):
            st = module._Sums()  # noqa: SLF001
            _ = module._build_pool(st, 32, 4)  # noqa: SLF001
            st.nw += offset
            before = st.nw
            module._pool_bank(st, 32, 4)  # noqa: SLF001
            banked.add(st.nw - before)
        assert banked == {32}

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

        The construction's one data-dependent jump is the dispatch: array
        16's non-head sum is the leaf table's own address plus whatever
        the ones banked, so the same fixed ``DIGEST LEAPFROG`` must land
        run ``row`` on its weight sum.  Recovering the slot from the halt
        cursor pins that arithmetic through the machine rather than
        through the builder's own model of it.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.tools.slow_acv_mammalian import _LEAF_UNIT, _weights

        table = "01101001"
        program = boolean.slow_acv_mammalian(table)
        tokens = program.split()
        leaf_base = len(tokens) - _LEAF_UNIT * len(table)
        weights = _weights(3)
        for row in range(8):
            bits = [(row >> (2 - i)) & 1 for i in range(3)]
            machine = _Machine(program, ScriptedIO("".join(f"{b}\n" for b in bits)))
            while not machine.halted:
                machine.step()
            banked = sum(w for w, b in zip(weights, bits, strict=True) if b)
            assert machine.ind - leaf_base - banked in range(_LEAF_UNIT)

    def test_the_emitted_size_is_pinned_and_linear(self) -> None:
        """Exact sizes per arity, and the leaf table is the whole growth.

        The construction is deterministic, so three sizes pin every piece
        -- a node, an arm, a slot or the dispatch drifting shows here
        first.  The differences also carry the linearity: each added input
        costs one more level plus the doubled leaf table, and a slot is
        eight tokens whatever the row, so per-entry cost falls toward that
        floor instead of growing.
        """
        sizes = [
            len(boolean.slow_acv_mammalian(table))
            for table in ("01", "0110", "01101001")
        ]
        assert sizes == [13_276, 23_330, 28_055]

    def test_a_slot_is_the_same_width_for_either_digit(self) -> None:
        """The table's stride is a leaf, and a leaf does not read the sum.

        Both leaves clear the accumulator and SPRINT to a print array, one
        SEED apart, so the two bodies differ by where they land and not by
        how long they are.  That is what puts the stride at eight tokens
        rather than at the 256 a solved print would need: a program's
        length cannot depend on which entries its table holds.
        """
        sizes = {
            len(boolean.slow_acv_mammalian(table))
            for table in ("0000", "1111", "0110", "1001", "0111")
        }
        assert len(sizes) == 1


class TestFastLanding:
    """The O(1) sizing helpers agree with the O(weight) builds they replace.

    ``slow_acv_mammalian``'s per-node retry loop used to re-simulate
    ``_w_raise`` and ``_trampoline`` on every retry just to size and
    length-check a candidate landing.  ``_w_raise_len`` and
    ``_trampoline_len`` answer the same questions in O(1); these tests
    hold them to the slow builds directly; cases marked below force a
    residue cycle, the O(1) path's only real branch.
    """

    @pytest.mark.parametrize(
        ("hw0", "nw0", "amount"),
        [
            (0, 0, 0),  # no raise at all
            (5, 100, 10),  # inside the two exact chunks, no greedy phase
            (5, 100, 1_000),  # a handful of greedy chunks, no cycle
            (200, 50_000, 5_000_000),  # forces a residue cycle
            (1, 1, 10**7),  # forces a residue cycle from a different start
        ],
    )
    def test_w_raise_len_matches_the_real_build(
        self, hw0: int, nw0: int, amount: int
    ) -> None:
        st = _Sums()
        st.hw, st.nw, st.ptr = hw0, nw0, 16
        real_tokens = _w_raise(st, amount)

        fast_len, fast_hw = _w_raise_len(hw0, nw0, amount)
        assert fast_len == len(real_tokens)
        assert fast_hw == st.hw

    def test_greedy_advance_cycle_matches_a_full_walk(self) -> None:
        """A target past 256 chunks must exercise the cycle-jump branch."""
        _, chunks, advance, final_r = _greedy_advance(17, 10**6)
        assert chunks > 256  # otherwise this case is not testing the jump
        assert advance >= 10**6

        # Cross-check against the slow reference the construction ships.
        st = _Sums()
        st.hw, st.nw, st.ptr = 0, 17, 16
        _w_raise(st, 10**6 + 510)
        assert (st.hw + st.nw) % 256 == final_r

    @pytest.mark.parametrize("target", range(1, 4001, 40))
    def test_greedy_advance_matches_a_slow_walk_across_many_targets(
        self, target: int
    ) -> None:
        """Sweep small-to-large targets from one residue.

        Some of these land the cycle jump exactly on its first lap (no
        extra multiple needed) and some skip several laps -- both paths
        through the jump, not just the one big-target picks.
        """
        st = _Sums()
        st.hw, st.nw, st.ptr = 3, 29, 16
        real_tokens = _w_raise(st, target)
        fast_len, fast_hw = _w_raise_len(3, 29, target)
        assert (fast_len, fast_hw) == (len(real_tokens), st.hw)

    @pytest.mark.parametrize(
        "seed",
        range(20),
    )
    def test_w_raise_len_matches_random_states(self, seed: int) -> None:
        rng = random.Random(seed)
        hw0 = rng.randrange(256)
        nw0 = rng.randrange(10**6)
        amount = rng.randrange(2 * 10**6)
        st = _Sums()
        st.hw, st.nw, st.ptr = hw0, nw0, 16
        real_tokens = _w_raise(st, amount)
        fast_len, fast_hw = _w_raise_len(hw0, nw0, amount)
        assert (fast_len, fast_hw) == (len(real_tokens), st.hw)

    @pytest.mark.parametrize(
        ("h0", "n0", "acc", "target"),
        [
            (5, 0, 0, 1),  # zero chunks: the initial gap already fits
            (5, 10, 4, 20),  # one chunk
            (5, 10, 4, 500),  # two chunks
            (5, 10, 4, 100_000),  # past two chunks: the closed-form tail
            (200, 50_000, 999, 300_000),  # a longer closed-form tail
        ],
    )
    def test_trampoline_len_matches_the_real_build(
        self, h0: int, n0: int, acc: int, target: int
    ) -> None:
        array = [h0, n0]
        real_tokens, _, _ = _trampoline(array, acc, target)
        assert _trampoline_len(array, acc, target) == len(real_tokens)

    def test_trampoline_stash_chunk_count_is_one_past_the_second(self) -> None:
        """The closed-form tail's premise, pinned directly.

        ``_trampoline_len`` assumes every chunk past the second spends
        exactly one ``SEED`` -- verified here against ``_stash_chunk``
        itself rather than only through the lengths above.
        """
        array, acc = [11, 23], 7
        counts = []
        for _ in range(6):
            chunk, array, acc = _stash_chunk(array, acc)
            counts.append(len(chunk) - 2)
        assert counts[2:] == [1, 1, 1, 1]
