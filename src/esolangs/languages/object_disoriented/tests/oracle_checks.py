"""Independent bit-stream model of Object disoriented's bounded IO fragment.

https://esolangs.org/wiki/Object_disoriented, statements and input objects.
Literal objects, bit reads, output, discards and input-controlled calls;
compare buffers, output, cursor, errors and halt within 512 VM steps.
Aliasing and general object functions remain in the raw regression suite.
"""

from itertools import product

import pytest

from esolangs.languages.object_disoriented.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread, stalled


def _expression(value, zero):
    if value == "input":
        return "i"
    if value == "self_copy":
        return "nrsss"
    return "nrpzz" if value else zero


def _source(operations, zero):
    text = []
    for kind, value in operations:
        expression = _expression(value, zero)
        if kind == "write":
            text.append("o" + expression)
        elif kind == "discard":
            text.append(expression)
        else:
            assert kind == "conditional"
            text.append("fi n o" + expression + " rz zz")
    return "dmain." + " ".join(text) + " rzzz"


def _model(operations, stdin):
    unread, pending, output, cursor = [], [], "", 0

    def read():
        nonlocal cursor, unread
        if not unread:
            if cursor == len(stdin):
                raise EOFError
            unread = [int(bit) for bit in f"{ord(stdin[cursor]) % 256:08b}"]
            cursor += 1
        return unread.pop(0)

    def terminal(error):
        return error, (
            (tuple(unread), tuple(pending)),
            error is None,
            output,
            cursor,
            cursor,
        )

    for kind, operand in operations:
        try:
            if kind == "conditional" and read() == 0:
                continue
            value = read() if operand == "input" else int(bool(operand))
        except EOFError:
            return terminal("input")
        if kind != "discard":
            pending.append(value)
            if len(pending) == 8:
                output += chr(int("".join(map(str, pending)), 2))
                pending.clear()
    return terminal(None)


def _view(machine):
    return machine.state.in_bits, machine.state.out_bits


def _check(factory, operations, stdin="unused", *, zero="z"):
    assert len(operations) <= 32
    code = _source(operations, zero)
    error, trace = observed(factory, code, stdin, _view, cap=512)
    assert (error, trace[-1]) == _model(operations, stdin), (code, stdin)
    assert trace[0] == (((), ()), False, "", 0, 0)
    if trace[-1][1]:
        assert trace[-4:] == [trace[-1]] * 4


def check_raw_object_disoriented():
    for value in range(256):
        operations = tuple(("write", int(bit)) for bit in f"{value:08b}")
        _check(_Machine, operations)
    for count, zero in product(range(10), ("z", "nrzzz")):
        _check(_Machine, tuple(("write", i % 2) for i in range(count)), zero=zero)
    _check(_Machine, (("write", "self_copy"),) * 8)
    for count, operation, stdin in product(
        (0, 1, 7, 8, 9, 16),
        ("write", "discard", "conditional"),
        ("", "\0", "\xff", "\x0f\xf0", "λ\n"),
    ):
        operand = 1 if operation == "conditional" else "input"
        _check(_Machine, ((operation, operand),) * count, stdin)
    for first, second in product(("write", "discard", "conditional"), repeat=2):
        _check(_Machine, ((first, "input"), (second, "input")) * 8, "\xa5\x5a\xff\0")
    for code in ("", "dmain.", "dmain.orzzz", "dmain.oqrzzz", "dmain.rzzz dmain.rzzz"):
        assert observed(_Machine, code, "", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class WrongBit(_Machine):
        def step(self):
            super().step()
            self.state = self.state._replace(out_bits=(*self.state.out_bits, 1))

    for factory in (stalled(_Machine), WrongBit, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, (("write", 0),) * 8)
