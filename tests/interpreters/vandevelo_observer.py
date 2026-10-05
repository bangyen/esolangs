"""Compare termination, bindings, reads, and errors with the statement model."""

import re

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.vandevelo import _Machine
from tests.interpreters.vandevelo_reference import reference


def check(source, values):
    expected, reads, error = reference(source, values)
    io = ScriptedIO("".join(value + "\n" for value in values))
    machine = _Machine(source, io)
    actual_error = None
    seen = set()
    for _ in range(2000):
        if machine.halted:
            break
        snapshot = machine.snapshot()
        if snapshot in seen:
            actual_error = "cycle"
            break
        seen.add(snapshot)
        try:
            machine.step()
        except (ValueError, EOFError) as exc:
            actual_error = "undefined" if isinstance(exc, ValueError) else "eof"
            break
    else:
        raise AssertionError("finite bound exceeded")
    assert actual_error == error, (source, values, error, actual_error)
    assert io.reads == reads, (source, values, reads, io.reads)
    actual = dict(machine.state.store)
    assert set(actual) == set(expected), (source, expected, actual)
    for name, value in expected.items():
        if isinstance(value, bool):
            assert actual[name] is value, (source, values, name, value, actual[name])
        else:
            text, negate = value
            pieces = re.split(r"(==|!=)", text.strip())
            expected_names = tuple(token.strip()[:-1] for token in pieces[::2])
            expected_parity = (sum(op == "==" for op in pieces[1::2]) + negate) % 2

            def flatten(node):
                if node.kind == "var":
                    return (node.name,), 0
                if node.kind == "not":
                    names, parity = flatten(node.left)
                    return names, parity ^ 1
                left_names, left_parity = flatten(node.left)
                right_names, right_parity = flatten(node.right)
                return left_names + right_names, left_parity ^ right_parity ^ (
                    node.kind == "eq"
                )

            assert flatten(actual[name]) == (expected_names, expected_parity)
    assert io.getvalue() == ""
