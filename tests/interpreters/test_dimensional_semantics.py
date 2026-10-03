"""Independent literal and observer checks; Dimensional wiki revision 156292."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.dimensional import _Machine


@pytest.mark.parametrize("value", range(256))
def test_character_literal_consumes_its_payload(value):
    machine = _Machine(":" + chr(value) + ".", ScriptedIO())
    machine.step()
    assert machine.ind == 2
    assert not machine.comment
    assert machine.memory == [value]
    machine.step()
    assert machine.halted
    assert machine.io.getvalue() == chr(value)


@pytest.mark.parametrize("value", range(256))
def test_two_hex_digits_set_the_byte(value):
    for spelling in (f"{value:02x}", f"{value:02X}"):
        machine = _Machine("=" + spelling + ".", ScriptedIO())
        machine.step()
        assert machine.ind == 3
        assert machine.memory == [value]
        machine.step()
        assert machine.io.getvalue() == chr(value)
        assert machine.halted


@pytest.mark.parametrize(
    "literal", [" 1", "1 ", "+1", "-1", "\uff110", "0\u0661", "gg", "[0", "}0", "**"]
)
def test_hex_literal_requires_two_ascii_hex_digits(literal):
    machine = _Machine("=" + literal + ".", ScriptedIO())
    before = machine.tape.top.freeze()
    with pytest.raises(ValueError, match="invalid hex literal") as caught:
        machine.step()
    assert str(caught.value) == f"invalid hex literal {literal!r}"
    assert machine.ind == 1
    assert machine.tape.top.freeze() == before


def test_literal_star_does_not_hide_following_loop():
    machine = _Machine(":*[-].", ScriptedIO())
    for _ in range(150):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert machine.io.getvalue() == "\x00"


@pytest.mark.parametrize("source", ["", "$3>0", "$4>0$2>7", "+$3>1"])
def test_memory_observer_does_not_allocate_slots(source):
    machine = _Machine(source, ScriptedIO())
    while not machine.halted:
        machine.step()
    before = machine.snapshot()
    view = machine.memory
    assert machine.snapshot() == before
    view[0] = 123
    assert machine.snapshot() == before
