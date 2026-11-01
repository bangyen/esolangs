"""REFRACTRAN's multiply/divide directions and fraction cursor."""

import pytest

from esolangs.languages.refractran.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO


def test_fraction_search() -> None:
    """Forward multiplication, reverse division and invalid sources."""
    cases = [
        ("2 3/2", "11"),
        ("8 2/3", "1000"),
        ("2 3/5 3/2", "101"),
        ("2 6/4", "11"),
        ("2^3*3 # initial\n 5/7", "11000"),
        ("1", "1"),
    ]
    for source, expected in cases:
        io = ScriptedIO()
        run(source, io)
        assert io.getvalue() == expected
    for source in ["", "0", "-1", "2^-1", "2 0/3", "2 3/0", "2 abc"]:
        with pytest.raises(ValueError, match=r"initial|fraction"):
            run(source, ScriptedIO())

    machine = _Machine("2 3/5 3/2", ScriptedIO())
    machine.step()
    assert tuple(machine.state) == (1, 2, 1)
    machine.step()
    assert tuple(machine.state) == (0, 3, -1)
    machine.step()
    assert tuple(machine.state) == (1, 5, 1)
    machine.step()
    assert tuple(machine.state) == (2, 5, 1)
