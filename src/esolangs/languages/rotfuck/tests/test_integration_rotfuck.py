"""ROTfuck through the shared API, CLI and machinery."""

import pytest

from esolangs import DialectSettings, compat
from esolangs.vm import complete_vm, make_vm


@pytest.mark.parametrize(
    "isolated", [False, pytest.param(True, marks=pytest.mark.medium)]
)
def test_rotfuck_rotation_reaches_every_execution_path(isolated) -> None:
    """The wiki cat ``,[`` echoes backward; forward, ``,,`` does instead.

    The generator follows the choice: it emits a forward program that answers
    the table when run forward.
    """
    forward = DialectSettings(rotation="forward")
    assert compat.run("ROTfuck", ",[", stdin="x", isolated=isolated) == "x"
    assert (
        compat.run("ROTfuck", ",,", stdin="x", settings=forward, isolated=isolated)
        == "x"
    )
    assert (
        complete_vm(make_vm("ROTfuck", ",,", stdin="x", settings=forward), 100) == "x"
    )
    assert complete_vm(make_vm("ROTfuck", ",,", stdin="x"), 100) == ""
    generated = compat.generate("ROTfuck", "01", settings=forward)
    assert (
        compat.run("ROTfuck", generated, stdin="0", settings=forward, isolated=isolated)
        == "0"
    )
    assert (
        compat.run("ROTfuck", generated, stdin="1", settings=forward, isolated=isolated)
        == "1"
    )
