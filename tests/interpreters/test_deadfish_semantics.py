"""Independent accumulator arithmetic and bounded execution controls."""

import itertools

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.deadfish import _Machine, run
from tests.interpreters.views import view as vm_view


def reference(code, cap):
    value = cursor = 0
    output = []
    stopped = False
    for command in code[:cap]:
        if command == "h":
            stopped = True
            break
        if command == "i":
            value += 1
        elif command == "d":
            value -= 1
        elif command == "s":
            value = pow(value, 2)
        if value == -1 or value == 256:
            value = 0
        if command == "o":
            output.append(str(value) + "\n")
        cursor += 1
    return "".join(output), cursor, value, stopped or cursor == len(code)


def corpus():
    yield from (
        "".join(commands)
        for length in range(5)
        for commands in itertools.product("idsohx", repeat=length)
    )
    yield from [
        "i" * 255 + "oio",
        "i" * 257 + "o",
        "iissso",
        "diissisdo",
        "iissisd" + "d" * 32 + "o",
        "i i\nxyz!o",
        "i" * 65 + "o",
        "ioio",
        "iiohiiio",
        "iiso",
        "do",
        "sso",
    ]


def observe(code, cap):
    io = ScriptedIO("unused λ")
    machine = _Machine(code, io)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    assert vm_view(machine, "memory") == [machine.value]
    assert vm_view(machine, "stack") == []
    assert machine.ind == vm_view(machine, "ip")
    assert io.position() == 0
    result = io.getvalue(), vm_view(machine, "ip"), machine.value, machine.halted
    if machine.halted:
        snapshot = machine.snapshot()
        machine.step()
        machine.step()
        assert machine.snapshot() == snapshot
        assert io.getvalue() == result[0]
    return result


@pytest.mark.parametrize("cap", [0, 1, 2, 5, 400])
def test_bounded_states_match_independent_arithmetic(cap):
    for code in corpus():
        assert observe(code, cap) == reference(code, cap), (code, cap)


def test_run_matches_independent_engine():
    for code in corpus():
        expected = reference(code, len(code))
        assert expected[3]
        io = ScriptedIO("unused")
        run(code, io)
        assert io.getvalue() == expected[0], code
        assert io.position() == 0


@pytest.mark.parametrize(
    ("code", "output", "value"),
    [
        ("iissso", "0\n", 0),
        ("diissisdo", "288\n", 288),
        ("iissisd" + "d" * 32 + "o", "0\n", 0),
        ("i" * 255 + "oio", "255\n0\n", 0),
        ("i" * 257 + "o", "1\n", 1),
        ("ioio", "1\n2\n", 2),
        ("iiohiiio", "2\n", 2),
        ("i i\nxyz!o", "2\n", 2),
        ("i" * 65 + "o", "65\n", 65),
        ("iiso", "4\n", 4),
        ("do", "0\n", 0),
        ("sso", "0\n", 0),
        ("", "", 0),
    ],
)
def test_reference_positive_controls(code, output, value):
    expected = reference(code, len(code))
    assert expected[0] == output
    assert expected[2] == value
    assert expected[3]
    assert observe(code, len(code)) == expected
