"""Minifuck chain paths the generator's own budgets never reach."""

import importlib

import pytest


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
        module = importlib.import_module("esolangs.tools.minifuck")
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
        module = importlib.import_module("esolangs.tools.minifuck_mux")
        base, accs = _scout_setup(module, 2)
        assert module._mux_scout(base, "0110", 2, accs)[1]  # noqa: SLF001

        with monkeypatch.context() as patch:
            patch.setattr(module, "_sculpt_columns", lambda *_a: None)
            assert module._mux_scout(base, "0110", 2, accs) == (  # noqa: SLF001
                None,
                False,
            )


class TestMuxUsesOneRule:
    """The production mux uses one direct preloaded-strip rule."""

    def test_the_rule_matches_the_named_lookup(self) -> None:
        """The named strip construction is the production spelling."""
        module = importlib.import_module("esolangs.tools.minifuck")
        for n, table in ((2, "0110"), (2, "0001"), (3, "01101001")):
            built = module._mux(table, n)  # noqa: SLF001
            assert built == module._mux_lookup(table, n)  # noqa: SLF001

    def test_the_scout_and_sweep_are_not_on_the_build_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Retired candidate contests cannot affect the fixed construction."""
        module = importlib.import_module("esolangs.tools.minifuck_mux")
        expected = module._mux("0110", 2)  # noqa: SLF001
        assert expected is not None

        def forbidden(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("the fixed construction enumerated candidates")

        with monkeypatch.context() as patch:
            patch.setattr(module, "_mux_scout", forbidden)
            patch.setattr(module, "_mux_sweep", forbidden)
            assert module._mux("0110", 2) == expected  # noqa: SLF001

    def test_the_start_displacement_sets_the_baseline_phase(self) -> None:
        """Crossing an odd extra prefix flips the zero-control column."""
        module = importlib.import_module("esolangs.tools.minifuck")
        phases = [
            (n ^ (module._mux_start(n) - module._MUX_BASE) ^ 1)  # noqa: SLF001
            & 1
            for n in range(2, 9)
        ]
        assert phases == [1, 0, 1, 1, 0, 1, 0]


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
        module = importlib.import_module("esolangs.tools.minifuck")
        assert module._probe_frame(".[[...[<", 242) is None  # noqa: SLF001

    def test_the_columns_decline_an_accumulator_inside_the_pool(self) -> None:
        """Below the region there is no window to take a parity over."""
        module = importlib.import_module("esolangs.tools.minifuck")
        base = module._mux_separate(2)  # noqa: SLF001
        assert module._sculpt_columns(base, module._POOL_WIDTH) is None  # noqa: SLF001

    def test_a_byte_with_no_frame_declines_both_summaries(self) -> None:
        """242 and 243 are the two bytes the sculpt code cannot be framed from.

        Both the column law and the scout consult that frame first, so the
        byte refuses each -- the column by falling back to simulation, the
        scout by distrusting itself.
        """
        module = importlib.import_module("esolangs.tools.minifuck")
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
        module = importlib.import_module("esolangs.tools.minifuck")
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
        module = importlib.import_module("esolangs.tools.minifuck_mux")
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
