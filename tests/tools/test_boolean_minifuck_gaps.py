"""Minifuck chain paths the generator's own budgets never reach."""

import importlib

import pytest

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


def test_every_ignored_input_drops_from_the_lookup() -> None:
    """Interior inputs 1 and 4, and trailing input 6, leave the table index."""
    from esolangs import generate
    from esolangs._evaluate import _evaluate
    from esolangs.tools.minifuck import _reduce
    from esolangs.tools.minifuck.mux import _mux_lookup

    inner = "0110100110010111"
    bits = ((r >> 6 - i & 1 for i in (0, 2, 3, 5)) for r in range(128))
    table = "".join(inner[int("".join(map(str, b)), 2)] for b in bits)
    assert _reduce(table, 7) == (0, inner, [0, 2, 3, 5], (1, 0, 1), 1)
    assert _evaluate("Minifuck", generate("Minifuck", table), inputs=7) == table
    assert len(_solve(table)) < 0.4 * len(_mux_lookup(table, 7))


@pytest.mark.medium
@pytest.mark.parametrize(("n", "gaps"), [(2, (1,)), (2, (3,)), (3, (3, 0))])
@pytest.mark.parametrize("paired", [False, True])
def test_extended_pads_compute_every_small_table(
    n: int, gaps: tuple[int, ...], *, paired: bool
) -> None:
    from esolangs.tools.minifuck.mux import _mux_lookup
    from tests.tools.minifuck_support import _MinifuckCase

    runner = _MinifuckCase()
    inputs = n + sum(gaps)
    positions = [0]
    for gap in gaps:
        positions.append(positions[-1] + gap + 1)
    for value in range(1 << (1 << n)):
        table = f"{value:0{1 << n}b}"
        template = _mux_lookup(table, n, paired=paired, gaps=gaps)
        for row in range(1 << inputs):
            bits = [row >> shift & 1 for shift in range(inputs - 1, -1, -1)]
            index = int("".join(str(bits[p]) for p in positions), 2)
            assert (
                runner.run_minifuck(runner.instantiate(template, bits)) == table[index]
            )


@pytest.mark.parametrize(
    ("table", "characters", "width"),
    [("1010101001010000", 570, 24), ("01" * 16 + "10" * 16, 474, 22)],
)
def test_balanced_projection_pads_only_after_the_program(
    table: str, characters: int, width: int
) -> None:
    from esolangs import generate
    from esolangs._evaluate import _evaluate
    from esolangs.tools.wrap import balance_score

    template = generate("Minifuck", table, balance=True)
    assert balance_score(template) == (0, characters, width)
    assert _evaluate("Minifuck", template, inputs=len(table).bit_length() - 1) == table


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


def test_narrow_layout_drops_ignored_inputs() -> None:
    """A width-1 layout drops ignored inputs: under half a fully essential one."""
    from esolangs import generate
    from esolangs._evaluate import _evaluate

    table = "0110" * 8
    narrow = generate("Minifuck", table, width=1)
    assert _evaluate("Minifuck", narrow, inputs=5) == table
    assert len(str(narrow)) < 0.5 * len(
        str(generate("Minifuck", "0110100110010110" + "0110100110010111", width=1))
    )
    # One essential input: the paired lookup is built at arity 1.
    single = "".join("01"[r >> 1 & 1] for r in range(16))
    assert (
        _evaluate("Minifuck", generate("Minifuck", single, width=1), inputs=4) == single
    )
