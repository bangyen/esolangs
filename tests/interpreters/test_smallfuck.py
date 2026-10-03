"""Smallfuck fixed-tape semantics."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.smallfuck import run


def _run(source: str) -> str:
    io = ScriptedIO("")
    run(source, io)
    return io.getvalue()


@pytest.mark.parametrize("source", ["[", "]"])
def test_unbalanced_loops_are_rejected(source: str) -> None:
    with pytest.raises(ValueError, match="unmatched"):
        _run(source)
