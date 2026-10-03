"""Qoibl source and diagnostic counterexamples."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.qoibl import _Machine, tokenize


@pytest.mark.parametrize("suffix", ["w", "q", "t", "r", "qt"])
def test_incomplete_prefix_cannot_discard_output(suffix: str) -> None:
    with pytest.raises(ValueError, match="malformed Qoibl expression"):
        _Machine(f"tt y tt {suffix}", ScriptedIO())


@pytest.mark.parametrize("prefix", ["w", "q", "t", "r"])
def test_lone_prefix_does_not_invent_an_opcode(prefix: str) -> None:
    assert tokenize(prefix) == [[]]


@pytest.mark.parametrize("bits", ["ey", "eey", "yy"])
def test_trailing_r_borrows_the_preceding_bit(bits: str) -> None:
    assert tokenize(bits + "r") == [[bits[:-1], "yr"]]
    with pytest.raises(ValueError, match="malformed Qoibl comparison operator"):
        _Machine(bits + "r", ScriptedIO())


@pytest.mark.parametrize("operation", ["index", "division"])
def test_large_binary_operand_preserves_halt_diagnostic(operation: str) -> None:
    bits = "y" + "e" * 20000
    value = 1 << 20000
    digits = []
    while value:
        value, digit = divmod(value, 10)
        digits.append(chr(48 + digit))
    decimal = "".join(reversed(digits))
    source = f"qe {bits} qe" if operation == "index" else f"{bits} ry yy ry e"
    expected = (
        f"variable index {decimal} is outside 0..255"
        if operation == "index"
        else f"division by zero: {decimal} divided by 0"
    )
    machine = _Machine(source, ScriptedIO())
    with pytest.raises(HaltError) as raised:
        machine.step()
    assert str(raised.value) == expected
    assert machine.ip == 1
    assert machine.var == {}
