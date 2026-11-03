"""Closed-form oracle for compiled loops, aliases and overflow modes."""

from itertools import product

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.basicfuck.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO


def _execute(machine):
    for _ in range(40):
        if machine.halted:
            break
        machine.step()


def _check(factory, mode, char, increment, count):
    source = f"""#basicfuck t=unbounded r=0~255 o={mode}
#allocate arr->2, counter
read -> arr;
counter += {count};
while (counter) {{
    arr->1 += arr;
    arr->1 += {increment};
    counter -= 1;
}}
if !(counter) {{ write <- arr->1; }}
if (counter) {{ read -> arr; }}
"""
    io = ScriptedIO(char + "sentinel")
    machine = factory(source, io)
    byte = ord(char)
    total = count * (byte + increment)
    if mode == "halt" and (byte > 255 or total > 255):
        with pytest.raises(HaltError, match="overflow"):
            _execute(machine)
        assert io.position() == 1
        assert io.getvalue() == ""
        return
    if mode == "wrap":
        initial, result = byte % 256, total % 256
    else:
        initial = min(byte, 255)
        result = min(count * (initial + increment), 255)
    _execute(machine)
    assert machine.halted
    assert machine.memory == [initial, result, 0]
    assert io.position() == 1
    assert io.getvalue() == chr(result)
    machine.step()
    assert io.getvalue() == chr(result)


def check_raw_basicfuck():
    for mode, char, increment, count in product(
        ("wrap", "nearest", "halt"), ("\0", "A", "ÿ", "Ω"), (0, 1, 300), (0, 1, 4)
    ):
        _check(_Machine, mode, char, increment, count)

    class WrongOverflow(_Machine):
        def __init__(self, code, io):
            super().__init__(code.replace("o=wrap", "o=nearest"), io)

    with pytest.raises(AssertionError):
        _check(WrongOverflow, "wrap", "ÿ", 1, 1)
