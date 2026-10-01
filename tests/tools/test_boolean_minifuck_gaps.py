"""Minifuck chain paths the generator's own budgets never reach."""

import importlib

from tests.tools.minifuck_support import _mux_separate


def _scout_setup(module: object, n: int) -> tuple[object, range]:
    """The separation ``_mux`` scouts at ``n``, with the accumulators it tries."""
    base = _mux_separate(n)
    positions = base.ptrs()
    lowest, highest = min(positions), max(positions)
    accs = range(highest - lowest + module._POOL_WIDTH + 1, lowest - 1)  # noqa: SLF001
    return base, accs


class TestMuxUsesOneRule:
    """The production mux uses one direct preloaded-strip rule."""

    def test_the_rule_matches_the_named_lookup(self) -> None:
        """The named strip construction is the production spelling."""
        module = importlib.import_module("esolangs.tools.minifuck")
        for n, table in ((2, "0110"), (2, "0001"), (3, "01101001")):
            built = module._mux(table, n)  # noqa: SLF001
            assert built == module._mux_lookup(table, n)  # noqa: SLF001

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


def test_degenerate_column_rules_execute_or_decline() -> None:
    """Standing columns cover both first inputs; later inputs use the mux."""
    from tests.tools.minifuck_support import _MinifuckCase

    module = importlib.import_module("esolangs.tools.minifuck")
    runner = _MinifuckCase()
    for table in ("0101", "1010"):
        template = module._degenerate(table, 2)  # noqa: SLF001
        assert template is not None
        for row, expected in enumerate(table):
            bits = [row >> 1, row & 1]
            assert runner.run_minifuck(runner.instantiate(template, bits)) == expected
    for table, n in (("0110", 2), ("01010101", 3)):
        assert module._degenerate(table, n) is None  # noqa: SLF001
        template = module.minifuck(table)
        for row, expected in enumerate(table):
            bits = [row >> shift & 1 for shift in range(n - 1, -1, -1)]
            assert runner.run_minifuck(runner.instantiate(template, bits)) == expected


def test_failed_projection_mux_aborts_without_lifting() -> None:
    """A failed construction cannot return a lifted template in the wrong order."""
    from unittest.mock import patch

    import pytest

    module = importlib.import_module("esolangs.tools.minifuck")
    module.minifuck.cache_clear()
    try:
        with (
            patch.object(
                module, "_mux", side_effect=ValueError("broken mux invariant")
            ),
            pytest.raises(ValueError, match="broken mux invariant"),
        ):
            module.minifuck("0101")
    finally:
        module.minifuck.cache_clear()


def test_failed_unary_column_rule_aborts_without_a_program() -> None:
    """A broken unary rule must abort before entering the two-input mux."""
    from unittest.mock import patch

    import pytest

    module = importlib.import_module("esolangs.tools.minifuck")
    module.minifuck.cache_clear()
    try:
        with (
            patch.object(module, "_degenerate", return_value=None),
            pytest.raises(ValueError, match="could not build '01'"),
        ):
            module.minifuck("01")
    finally:
        module.minifuck.cache_clear()


def test_canonical_endgame_rejects_an_accumulator_inside_the_pool() -> None:
    """The pool is reserved; invalid accumulator placement fails before emitting."""
    import pytest

    from esolangs.tools.minifuck_mux import _canonical_endgame
    from esolangs.tools.minifuck_pool import _POOL_WIDTH
    from esolangs.tools.minifuck_sim import _Joint

    joint = _Joint(1)
    before = joint.template()
    with pytest.raises(ValueError, match="accumulator must sit past the pool"):
        _canonical_endgame(joint, _POOL_WIDTH - 1, direct=True)
    assert joint.template() == before


def test_probe_frame_refuses_a_pointer_outside_its_low_byte() -> None:
    """A low-byte summary cannot describe a cursor that has left that byte."""
    from esolangs.tools.minifuck_mux import _probe_frame
    from esolangs.tools.minifuck_pool import _POOL_WIDTH

    assert _probe_frame("[" * (_POOL_WIDTH - 1), 0) == (_POOL_WIDTH - 1, 0)
    assert _probe_frame("[" * _POOL_WIDTH, 0) is None
