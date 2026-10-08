"""Minifuck chain paths the generator's own budgets never reach."""

import importlib

from esolangs.tools.minifuck import _solve
from esolangs.tools.minifuck.mux import (
    _probe_frame,
)
from esolangs.tools.minifuck.pool import _POOL_WIDTH


class TestProbeFrameAndColumns:
    """The summaries' own refusals, reached by constructed keys."""

    def test_a_code_that_writes_above_the_pool_has_no_frame(self) -> None:
        """The frame summarises the low byte, so a carry out of it refuses."""
        assert _probe_frame(".[[...[<", 242) is None


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


def test_failed_gap_mux_aborts_without_projecting() -> None:
    """An input ignored between essential ones takes the mux; a failure aborts."""
    from unittest.mock import patch

    import pytest

    module = importlib.import_module("esolangs.tools.minifuck")
    _solve.cache_clear()
    try:
        with (
            patch.object(
                module, "_mux", side_effect=ValueError("broken mux invariant")
            ),
            pytest.raises(ValueError, match="broken mux invariant"),
        ):
            module.minifuck("01011010")
    finally:
        _solve.cache_clear()


def test_failed_unary_column_rule_aborts_without_a_program() -> None:
    """A broken unary rule must abort before entering the two-input mux."""
    from unittest.mock import patch

    import pytest

    module = importlib.import_module("esolangs.tools.minifuck")
    _solve.cache_clear()
    try:
        with (
            patch.object(module, "_degenerate", return_value=None),
            pytest.raises(ValueError, match="could not build '01'"),
        ):
            module.minifuck("01")
    finally:
        _solve.cache_clear()


def test_canonical_endgame_rejects_an_accumulator_inside_the_pool() -> None:
    """The pool is reserved; invalid accumulator placement fails before emitting."""
    import pytest

    from esolangs.tools.minifuck.mux import _canonical_endgame
    from esolangs.tools.minifuck.sim import _Joint

    joint = _Joint(1)
    before = joint.template()
    with pytest.raises(ValueError, match="accumulator must sit past the pool"):
        _canonical_endgame(joint, _POOL_WIDTH - 1, direct=True)
    assert joint.template() == before


def test_probe_frame_refuses_a_pointer_outside_its_low_byte() -> None:
    """A low-byte summary cannot describe a cursor that has left that byte."""
    from esolangs.tools.minifuck.mux import _probe_frame

    assert _probe_frame("[" * (_POOL_WIDTH - 1), 0) == (_POOL_WIDTH - 1, 0)
    assert _probe_frame("[" * _POOL_WIDTH, 0) is None
