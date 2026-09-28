"""thisthat deterministic-core semantics."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.thisthat import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.thisthat import thisthat


def test_constant_output_and_halt() -> None:
    io = ScriptedIO("")
    run(["▣─■═◇"], io)
    assert io.getvalue() == "1"


def test_loader_push_pop_and_horizontal_route() -> None:
    io = ScriptedIO("0\n")
    run(thisthat("01").splitlines(), io)
    assert io.getvalue() == "0"


def test_invalid_programs_abort() -> None:
    with pytest.raises(HaltError, match="exactly one"):
        _Machine([], ScriptedIO(""))
    with pytest.raises(HaltError, match="must be a bit"):
        run(["▣─◇"], ScriptedIO("x\n"))
