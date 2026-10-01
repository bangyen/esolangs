"""Jaune wrapping preserves signs, runs, and read markers."""

import pytest

from tests.generator_support import evaluate_generated


@pytest.mark.parametrize("program", ["++4:", "--4?", "-4?", "+12+", "v:", "v$"])
def test_jaune_wrapping_preserves_signed_operands_and_runs(program: str) -> None:
    """A split run must not turn its last arithmetic command into a sign."""
    from esolangs.interpreters.tape_based.jaune import _parse
    from esolangs.tools.wrap import wrap_program

    for width in range(1, 17):
        assert _parse(wrap_program(program, "jaune", width)) == _parse(program)


def test_jaune_wrapping_preserves_the_reordered_retirement_witness() -> None:
    """A line break inside ++ before label4 formerly lost an increment."""
    for width in (1, 16):
        assert evaluate_generated("Jaune", "00100001", width=width) == "00100001"
