"""REFRACTRAN's multiply/divide directions and fraction cursor."""

import sys

import pytest

import esolangs
from esolangs.languages.refractran import interpreter as native
from esolangs.languages.refractran.interpreter import _Machine, run
from esolangs.languages.refractran.tests.test_integration_refractran import (
    check_serialized_narrow_template_and_vm,
)
from esolangs.runtime.io import ScriptedIO
from tests.support.prepared_support import check_image_reuse


def test_fraction_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """Directions, malformed sources and serialized templates."""
    from esolangs.languages.refractran.tests.oracle_checks import check_raw_refractran

    check_raw_refractran()
    check_serialized_narrow_template_and_vm()
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
    _check_large_operands()

    machine = _Machine("2 3/5 3/2", ScriptedIO())
    machine.step()
    assert tuple(machine.state) == (1, 2, 1)
    machine.step()
    assert tuple(machine.state) == (0, 3, -1)
    machine.step()
    assert tuple(machine.state) == (1, 5, 1)
    machine.step()
    assert tuple(machine.state) == (2, 5, 1)
    check_image_reuse(
        "REFRACTRAN",
        "2 3/5 3/2",
        native,
        "_parse",
        monkeypatch,
        cases=(("", "101"),) * 3,
    )


def _check_large_operands() -> None:
    huge = "9" * 641
    api = esolangs.Language("REFRACTRAN")
    limits = esolangs.ExecutionLimits(max_steps=4)
    original = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        code = f"1^{huge} 2/1"
        assert api.run(code).output == "10"
        assert api.run(code, limits=limits).output == "10"
        assert api.run(code, isolated=True, limits=limits).output == "10"
        code = f"{huge} {huge}/{huge}"
        assert api.run(code, limits=limits).output == format(10**641 - 1, "b")
    finally:
        sys.set_int_max_str_digits(original)
