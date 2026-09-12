r"""Minifuck chain paths the generator's own budgets never reach."""

import importlib

import pytest

from esolangs.tools.boolean.minifuck import _BASE, _CHAIN_CAP, _Chain


class TestChainExtent:
    r"""``extent`` inverts the staircase, clamped to the chain's ceiling."""

    def test_a_budget_past_the_chain_is_clamped_to_the_ceiling(self) -> None:
        r"""No budget buys more cells than the chain holds."""
        chain = _Chain([0] * _CHAIN_CAP)
        assert chain.extent(10**6) == (_CHAIN_CAP - 3, False)

    def test_the_clamp_is_the_same_for_a_chain_of_ones(self) -> None:
        # Crossing costs two.
        # so the ceiling is reached by.
        chain = _Chain([1] * _CHAIN_CAP)
        extent, _ = chain.extent(10**6)
        assert extent == _CHAIN_CAP - 3

    def test_a_budget_inside_the_chain_is_not_clamped(self) -> None:
        chain = _Chain([0] * _CHAIN_CAP)
        extent, _ = chain.extent(_BASE + 2)
        assert extent < _CHAIN_CAP - 3


class TestStagingIndexBudget:
    r"""The index stops mid-pass when its accumulator budget runs out."""

    def test_a_smaller_budget_indexes_strictly_fewer_columns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""Each exit truncates the enumeration where the budget ran out."""
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
    r"""The separation ``_mux`` scouts at ``n``, with the accumulators it."""
    base = module._mux_separate(n)  # noqa: SLF001
    positions = base.ptrs()
    lowest, highest = min(positions), max(positions)
    accs = range(highest - lowest + module._POOL_WIDTH + 1, lowest - 1)  # noqa: SLF001
    return base, accs


class TestScoutPricesNothing:
    r"""The scout's two empty-handed exits, which a real table never takes."""

    def test_a_column_no_read_prints_is_priced_away(self) -> None:
        r"""A summarisable byte no pool code answers leaves nothing priced."""
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
        r"""The law and the simulation disagreeing refuses rather than ships."""
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
    r"""Both routes from the priced winner back to sculpting for real."""

    def test_the_sweep_answers_what_the_scout_priced(self) -> None:
        r"""Sculpting every combination picks the build the scout predicts."""
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        for n, table in ((2, "0110"), (2, "0001"), (3, "01101001")):
            base, accs = _scout_setup(module, n)
            expected = module._mux(table, n)  # noqa: SLF001
            assert expected is not None, f"n={n} must build for this to pin anything"
            assert module._mux_sweep(base, table, n, accs) == expected  # noqa: SLF001

    def test_an_untrusted_scout_sends_mux_to_the_sweep(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""A scout that refuses to summarise still yields the same program."""
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        expected = module._mux("0110", 2)  # noqa: SLF001
        assert expected is not None

        with monkeypatch.context() as patch:
            patch.setattr(module, "_mux_scout", lambda *_a: (None, False))
            assert module._mux("0110", 2) == expected  # noqa: SLF001

    def test_a_replay_that_misses_its_predicted_length_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""The winner's replay disagreeing answers from the sweep instead."""
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
        r"""Priced nothing *and* trusted is a refusal, not a fallback."""
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_mux_scout", lambda *_a: (None, True))
            assert module._mux("0110", 2) is None  # noqa: SLF001


class TestProbeFrameAndColumns:
    r"""The summaries' own refusals, reached by constructed keys."""

    def test_a_code_that_writes_above_the_pool_has_no_frame(self) -> None:
        r"""The frame summarises the low byte, so a carry out of it refuses."""
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        assert module._probe_frame(".[[...[<", 242) is None  # noqa: SLF001

    def test_the_columns_decline_an_accumulator_inside_the_pool(self) -> None:
        r"""Below the region there is no window to take a parity over."""
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        base = module._mux_separate(2)  # noqa: SLF001
        assert module._sculpt_columns(base, module._POOL_WIDTH) is None  # noqa: SLF001

    def test_a_byte_with_no_frame_declines_both_summaries(self) -> None:
        r"""242 and 243 are the two bytes the sculpt code cannot be framed from."""
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
        r"""``cell7 == 1`` is spelled by no pool code, so the probe has none."""
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        base = module._mux_separate(2)  # noqa: SLF001
        assert module._sculpt_pool_code(1) is None  # noqa: SLF001
        assert module._mux_probe_sim(base, module._POOL_WIDTH + 4, 1) is None  # noqa: SLF001

    def test_an_endgame_code_it_cannot_frame_distrusts_the_scout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""The endgame's own frame must agree with the slice that named it."""
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
