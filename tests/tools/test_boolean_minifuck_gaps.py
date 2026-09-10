"""Minifuck chain paths the generator's own budgets never reach."""

import importlib

import pytest

from esolangs.tools.boolean.minifuck import _BASE, _CHAIN_CAP, _Chain


class TestChainExtent:
    """``extent`` inverts the staircase, clamped to the chain's ceiling."""

    def test_a_budget_past_the_chain_is_clamped_to_the_ceiling(self) -> None:
        """No budget buys more cells than the chain holds."""
        chain = _Chain([0] * _CHAIN_CAP)
        assert chain.extent(10**6) == (_CHAIN_CAP - 3, False)

    def test_the_clamp_is_the_same_for_a_chain_of_ones(self) -> None:
        # Crossing costs two instructions per cell here rather than one,
        # so the ceiling is reached by a different route to the same cap.
        chain = _Chain([1] * _CHAIN_CAP)
        extent, _ = chain.extent(10**6)
        assert extent == _CHAIN_CAP - 3

    def test_a_budget_inside_the_chain_is_not_clamped(self) -> None:
        chain = _Chain([0] * _CHAIN_CAP)
        extent, _ = chain.extent(_BASE + 2)
        assert extent < _CHAIN_CAP - 3


class TestStagingIndexBudget:
    """The index stops mid-pass when its accumulator budget runs out.

    ``_budget`` returns None at every shipped arity, so the exit is dead
    as configured; a budget landing inside the insert pass is what shows
    it stops rather than running the enumeration out.
    """

    def test_a_smaller_budget_indexes_strictly_fewer_columns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each exit truncates the enumeration where the budget ran out.

        Three budgets, three prefixes of the same order: 200 stops in the
        bracket pass, 7600 inside the insert pass, 20000 later still.  The
        counts must grow with the budget, and each smaller index must be a
        sub-map of the larger -- a prefix, not a different walk.
        """
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        indexes = []
        for budget in (200, 7600, 20_000):
            module._staging_index.cache_clear()  # noqa: SLF001
            with monkeypatch.context() as patch:
                patch.setattr(module, "_budget", lambda _n, b=budget: b)
                indexes.append(module._staging_index(4))  # noqa: SLF001
        module._staging_index.cache_clear()  # noqa: SLF001

        small, middle, large = indexes
        assert len(small) < len(middle) < len(large)
        assert all(middle[key] == value for key, value in small.items())
        assert all(large[key] == value for key, value in middle.items())


def _scout_setup(module: object, n: int) -> tuple[object, range]:
    """The separation ``_mux`` scouts at ``n``, with the accumulators it tries."""
    base = module._mux_separate(n)  # noqa: SLF001
    positions = base.ptrs()
    lowest, highest = min(positions), max(positions)
    accs = range(highest - lowest + module._POOL_WIDTH + 1, lowest - 1)  # noqa: SLF001
    return base, accs


class TestScoutPricesNothing:
    """The scout's two empty-handed exits, which a real table never takes."""

    def test_a_column_no_read_prints_is_priced_away(self) -> None:
        """A summarisable byte no pool code answers leaves nothing priced.

        ``_pool_slice`` answers 36 of 512 keys, so most bytes have no
        endgame at either ``cell7`` -- the sculpt would run its rounds and
        ``_try_print`` would refuse, which the scout skips instead of
        pricing.  Every combination skipping is how ``best`` stays None,
        and that must come back *trusted*: nothing was mispriced, there was
        simply nothing to price.  The separation's own byte is 254, which
        every code answers, so the byte is forged -- identically in every
        row, since rows disagreeing inside the pool is a different refusal.
        """
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        base, accs = _scout_setup(module, 2)

        forged = base.fork()
        for row in forged.ms:
            row.tape = (row.tape & ~module._POOL_MASK) | 1  # noqa: SLF001

        codes = tuple(module._POOL_CODES)  # noqa: SLF001
        slice0 = module._pool_slice(codes, 0, skip=False)  # noqa: SLF001
        assert slice0.get((1, 0)) is None
        assert slice0.get((1, 1)) is None
        assert module._probe_frame(module._SCULPT_POOL_CODE, 1) is not None  # noqa: SLF001

        assert module._mux_scout(forged, "0110", 2, accs) == (None, True)  # noqa: SLF001

    def test_a_contradicted_probe_distrusts_the_whole_scout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The law and the simulation disagreeing refuses rather than ships.

        The first priced combination checks its column both ways, once per
        build.  No state reaches this -- the pair agree wherever the
        separation puts them -- so the disagreement is injected: the scout
        must come back untrusted, sending ``_mux`` to the sweep.
        """
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        base, accs = _scout_setup(module, 2)
        assert module._mux_scout(base, "0110", 2, accs)[1]  # noqa: SLF001

        with monkeypatch.context() as patch:
            patch.setattr(module, "_sculpt_columns", lambda *_a: None)
            assert module._mux_scout(base, "0110", 2, accs) == (  # noqa: SLF001
                None,
                False,
            )


class TestMuxFallsBackToTheSweep:
    """Both routes from the priced winner back to sculpting for real.

    The sweep is the spelling the scout is held to, so each fallback must
    answer with exactly the program the trusted path answers with -- a
    fallback that returned something *else* would be a second construction,
    not a safety net.
    """

    def test_the_sweep_answers_what_the_scout_priced(self) -> None:
        """Sculpting every combination picks the build the scout predicts."""
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        for n, table in ((2, "0110"), (2, "0001"), (3, "01101001")):
            base, accs = _scout_setup(module, n)
            expected = module._mux(table, n)  # noqa: SLF001
            assert expected is not None, f"n={n} must build for this to pin anything"
            assert module._mux_sweep(base, table, n, accs) == expected  # noqa: SLF001

    def test_an_untrusted_scout_sends_mux_to_the_sweep(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A scout that refuses to summarise still yields the same program."""
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        expected = module._mux("0110", 2)  # noqa: SLF001
        assert expected is not None

        with monkeypatch.context() as patch:
            patch.setattr(module, "_mux_scout", lambda *_a: (None, False))
            assert module._mux("0110", 2) == expected  # noqa: SLF001

    def test_a_replay_that_misses_its_predicted_length_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The winner's replay disagreeing answers from the sweep instead.

        Only the *replay* is broken -- the first sculpt ``_mux`` asks for --
        since the sweep that follows sculpts through the same function and
        needs it working to answer at all.
        """
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        expected = module._mux("0110", 2)  # noqa: SLF001
        assert expected is not None

        real = module._mux_sculpt  # noqa: SLF001
        calls = []

        def once_broken(*args: object, **kwargs: object) -> str | None:
            calls.append(1)
            if len(calls) == 1:
                return None
            return real(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(module, "_mux_sculpt", once_broken)
            assert module._mux("0110", 2) == expected  # noqa: SLF001
        assert len(calls) > 1, "the sweep must have sculpted after the bad replay"

    def test_a_scout_that_priced_nothing_returns_empty_handed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Priced nothing *and* trusted is a refusal, not a fallback.

        The two None returns are read differently: untrusted goes to the
        sweep, trusted means every combination was skipped on its merits
        and there is nothing for the sweep to find either.
        """
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_mux_scout", lambda *_a: (None, True))
            assert module._mux("0110", 2) is None  # noqa: SLF001


class TestProbeFrameAndColumns:
    """The summaries' own refusals, reached by constructed keys.

    Each is a guard on the frame being a function of the pool byte alone.
    The construction never offers these states, so every one is built here
    rather than waited for.
    """

    def test_a_code_that_writes_above_the_pool_has_no_frame(self) -> None:
        """The frame summarises the low byte, so a carry out of it refuses.

        Found by enumerating the ``<[.x`` alphabet: ``.[[...[<`` from byte
        242 leaves the region's cells alone but changes what sits above it,
        which the frame cannot describe.
        """
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        assert module._probe_frame(".[[...[<", 242) is None  # noqa: SLF001

    def test_the_columns_decline_an_accumulator_inside_the_pool(self) -> None:
        """Below the region there is no window to take a parity over."""
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        base = module._mux_separate(2)  # noqa: SLF001
        assert module._sculpt_columns(base, module._POOL_WIDTH) is None  # noqa: SLF001

    def test_a_byte_with_no_frame_declines_both_summaries(self) -> None:
        """242 and 243 are the two bytes the sculpt code cannot be framed from.

        Both the column law and the scout consult that frame first, so the
        byte refuses each -- the column by falling back to simulation, the
        scout by distrusting itself.
        """
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        base, accs = _scout_setup(module, 2)
        assert module._probe_frame(module._SCULPT_POOL_CODE, 242) is None  # noqa: SLF001

        forged = base.fork()
        for row in forged.ms:
            row.tape = (row.tape & ~module._POOL_MASK) | 242  # noqa: SLF001

        acc = module._POOL_WIDTH + 4  # noqa: SLF001
        assert module._sculpt_columns(forged, acc) is None  # noqa: SLF001
        assert module._mux_scout(forged, "0110", 2, accs) == (None, False)  # noqa: SLF001

    def test_the_simulated_probe_declines_an_orientation_with_no_code(
        self,
    ) -> None:
        """``cell7 == 1`` is spelled by no pool code, so the probe has none."""
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        base = module._mux_separate(2)  # noqa: SLF001
        assert module._sculpt_pool_code(1) is None  # noqa: SLF001
        assert module._mux_probe_sim(base, module._POOL_WIDTH + 4, 1) is None  # noqa: SLF001

    def test_an_endgame_code_it_cannot_frame_distrusts_the_scout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The endgame's own frame must agree with the slice that named it.

        The scout frames two codes: the sculpt's, then the endgame's.  Only
        the second is broken here, since the first refusing is the separate
        guard above.
        """
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        base, accs = _scout_setup(module, 2)
        real = module._probe_frame  # noqa: SLF001
        seen: list[str] = []

        def second_call_unframed(code: str, byte: int) -> object:
            seen.append(code)
            return None if len(seen) > 1 else real(code, byte)

        with monkeypatch.context() as patch:
            patch.setattr(module, "_probe_frame", second_call_unframed)
            assert module._mux_scout(base, "0110", 2, accs) == (  # noqa: SLF001
                None,
                False,
            )
        assert len(seen) > 1, "the endgame frame must have been reached"
