"""B-tapemark loading and pure-transition diagnostics."""

import pytest

from esolangs.interpreters.grid_based.b_tapemark import (
    _advance,
    _Grid,
    _load,
    run,
)
from esolangs.interpreters.io import ScriptedIO


def execute(source: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(source, io)
    return io.getvalue()


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("!", "exactly one start"),
        ("> <!", "exactly one start"),
        ('>"', "unmatched quote"),
        (">a!", "invalid.*'a'"),
        (">²!", "invalid.*'²'"),
    ],
)
def test_malformed_program(source: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        execute(source)


def test_grid_comparison_with_another_memory_value() -> None:
    """Comparing against a non-grid answers False rather than raising."""
    assert _Grid({}) != frozenset()


def test_input_command_without_a_symbol_is_refused() -> None:
    """Step past the blank start marker before testing the missing input."""
    state = _advance(_load(">-!"))[0]
    with pytest.raises(ValueError, match="input symbol required"):
        _advance(state)
