"""Independent scalar-counter Packlang model, capped at 48 statements.

https://esolangs.org/wiki/Packlang, variables, IO and datatype bounds.
Plain bytes and named under/overflow values, INIT, XOR/not and IO. Arrays,
package calls and structured control remain in raw tests; see Decisions.
"""

from itertools import product

import pytest

from esolangs.languages.packlang.interpreter import _Machine
from tests.interpreters.oracle_support import after_step, observed, overread, stalled


def _expr(expr):
    if not isinstance(expr, tuple):
        return str(expr)
    kind, *args = expr
    if kind == "not":
        return "!(" + _expr(args[0]) + ")"
    assert kind == "xor"
    return "(" + _expr(args[0]) + " ^ " + _expr(args[1]) + ")"


def _source(kind, statements):
    datatype = (
        kind if isinstance(kind, str) else "Integer(" + ",".join(map(str, kind)) + ")"
    )
    body = []
    for op, value in statements:
        if op in ("INIT", "INCR", "DECR"):
            body.append(op + " " + value)
        elif op in ("read", "write"):
            body.append(
                ("charGet" if op == "read" else "charPut") + "(" + _expr(value) + ")"
            )
        else:
            assert op == "value"
            body.append(_expr(value))
    return (
        "Package : IO { "
        + datatype
        + " cell; Integer main { "
        + ";".join(body)
        + "; } } scope;"
    )


def _eval(expr, values):
    if isinstance(expr, str):
        return values[expr]
    if type(expr) is int:
        return expr
    kind, *args = expr
    if kind == "not":
        return int(_eval(args[0], values) == 0)
    return _eval(args[0], values) ^ _eval(args[1], values)


def _model(kind, statements, stdin):
    low, high, under, over = (0, 255, 255, 0) if isinstance(kind, str) else kind
    values, trace = {"cell": low}, []
    pc = result = cursor = reads = 0
    output, done = "", False

    def row():
        state = None if done else (pc, tuple(sorted(values.items())), result)
        return (state, reads), done, output, cursor, cursor

    for op, arg in statements:
        trace.append(row())
        try:
            if op == "INIT":
                values[arg]
                values[arg] = low
            elif op in ("INCR", "DECR"):
                value = values[arg] + (1 if op == "INCR" else -1)
                values[arg] = under if value < low else over if value > high else value
            elif op == "read":
                if cursor == len(stdin):
                    value = 10
                else:
                    value = ord(stdin[cursor])
                    cursor, reads = cursor + 1, reads + 1
                values[arg]
                values[arg] = value
            elif op == "write":
                output += chr(_eval(arg, values) % 256)
            else:
                result = _eval(arg, values)
        except KeyError:
            return "halt", [*trace, row()]
        pc += 1
    trace.append(row())
    done = True
    return None, trace + [row()] * 4


def _view(machine):
    state = (
        None
        if machine.halted
        else (machine.frame.pc, machine.frame.store, machine.frame.result)
    )
    return state, machine._input_reads


def _check(factory, kind, statements, stdin="unused"):
    assert len(statements) < 48
    assert observed(factory, _source(kind, statements), stdin, _view, cap=48) == _model(
        kind, statements, stdin
    ), (kind, statements, stdin)


def check_raw_packlang():
    kinds = ("Integer", "Char", (0, 1, 1, 0), (2, 4, 3, 2), (0, 3, 2, 1))
    actions = (
        ("INIT", "cell"),
        ("INCR", "cell"),
        ("DECR", "cell"),
        ("write", "cell"),
        ("write", ("xor", "cell", 65)),
        ("value", ("not", "cell")),
    )
    for kind, first, second, third in product(kinds, actions, actions, actions):
        _check(_Machine, kind, (first, second, third))
    for kind, stdin in product(
        kinds, ("", "A", "\nZ", "λ", "ÿ", "Ā", "😀", "\0", "abc")
    ):
        _check(
            _Machine,
            kind,
            (
                ("read", "cell"),
                ("write", "cell"),
                ("INCR", "cell"),
                ("write", "cell"),
                ("read", "cell"),
                ("value", "cell"),
            ),
            stdin,
        )
    for operation in (("INCR", "missing"), ("read", "missing"), ("write", "missing")):
        _check(_Machine, "Integer", (operation,))

    for expr in (
        ("xor", 48, ("not", ("xor", 7, 7))),
        ("xor", 48, ("not", ("xor", 7, 6))),
        ("xor", 48, ("not", ("not", ("xor", 7, 6)))),
    ):
        _check(_Machine, "Integer", (("write", expr),))
    _check(_Machine, "Integer", (("write", 104), ("write", 105), ("value", 0)))

    wrong_output = after_step(_Machine, lambda self: self.io.print_str("!"))

    for factory in (stalled(_Machine), wrong_output, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, "Integer", (("INCR", "cell"), ("write", "cell")))
