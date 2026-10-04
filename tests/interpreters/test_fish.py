"""Fish instruction semantics."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.fish import _Machine, run
from esolangs.interpreters.io import ScriptedIO


def _run(source: str, stdin: str = "", rng: object = None) -> str:
    io = ScriptedIO(stdin)
    run(source.splitlines(), io, rng=rng)
    return io.getvalue()


def test_errors_are_fishy() -> None:
    for source in ("~;", "10,;", "10%;", "};", "{;", "2[;", "z;"):
        with pytest.raises(HaltError, match="fishy"):
            _run(source)
    fractional = _Machine(["p"], ScriptedIO(""))
    fractional.stacks[-1].extend((2.5, 0, 0))
    with pytest.raises(HaltError, match="fishy"):
        fractional.step()


def test_empty_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run([], ScriptedIO(""))
