"""Independent constant-language engine (Nope. revision 193999).

The wiki calls Nope. ConstantLanguage("Nope.") and names "Nope." its quine,
so the output is exactly those five characters with no newline.
"""

import itertools

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.nope import _Machine, run
from tests.interpreters.views import view as vm_view


def reference(code, cap):
    del code  # the source is never parsed
    done = cap > 0
    return ("Nope." if done else ""), int(done), [], done


def corpus():
    yield from (
        "".join(chars)
        for length in range(4)
        for chars in itertools.product("N.x\n", repeat=length)
    )
    yield from ["Nope.", "nope", "[", "]]", "Āā😀", "\x00", "+" * 500]


def observe(code, stdin, cap):
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    assert vm_view(machine, "stack") == []
    assert io.position() == 0
    result = (
        io.getvalue(),
        vm_view(machine, "ip"),
        vm_view(machine, "memory"),
        machine.halted,
    )
    if machine.halted:
        snapshot = machine.snapshot()
        machine.step()
        machine.step()
        assert machine.snapshot() == snapshot
        assert io.getvalue() == result[0]
    return result


@pytest.mark.parametrize("stdin", ["", "Nope."])
@pytest.mark.parametrize("cap", [0, 1, 2, 5])
def test_bounded_states_match_independent_engine(stdin, cap):
    for code in corpus():
        assert observe(code, stdin, cap) == reference(code, cap), (code, cap)


def test_run_matches_independent_engine():
    for code in corpus():
        io = ScriptedIO("unused")
        run(code, io)
        assert io.getvalue() == reference(code, 1)[0], code
        assert io.position() == 0


@pytest.mark.parametrize("code", ["Nope.", "", "Hello, world!", ",[.,]"])
def test_reference_positive_controls(code):
    # The wiki's quine: running "Nope." prints "Nope.".
    assert reference(code, 1)[0] == "Nope."
    assert observe(code, "", 1) == ("Nope.", 1, [], True)
