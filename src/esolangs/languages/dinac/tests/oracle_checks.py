"""Independent typed-value model for DINAC's straight-line fragment.

https://esolangs.org/wiki/DINAC, datatypes, variables, IO and operators.
Byte/ASCII wrapping, comparison, null and input; 48 statements. Functions
and indentation control remain in raw tests. Dialect choices follow Decisions.
"""

import re
from itertools import product

import pytest

from esolangs.languages.dinac.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread, stalled


def _source(expr):
    if isinstance(expr, str):
        return expr
    kind, *args = expr
    if kind == "wubyte":
        return f"{args[0]:02X}"
    if kind == "aschar":
        text = {0: r"\0", 9: r"\t", 10: r"\n", 13: r"\r", 92: r"\\"}.get(args[0])
        return text if text is not None else "'" + chr(args[0])
    if kind == "snuval":
        return "$"
    if kind in ("+", "-"):
        return "(" + _source(args[0]) + ")" + kind
    if kind == "~":
        return "~(" + _source(args[0]) + ")"
    return "(" + _source(args[0]) + ") " + kind + " (" + _source(args[1]) + ")"


def _line(statement):
    kind, *args = statement
    if kind == "declare":
        return "SET " + args[0] + ":" + _source(args[1])
    if kind == "assign":
        return args[0] + " . " + _source(args[1])
    if kind == "out":
        return "OUT " + _source(args[0])
    assert kind == "in"
    return "IN " + args[0]


def _eval(expr, bindings):
    if isinstance(expr, str):
        return bindings[expr]
    kind, *args = expr
    if kind in ("wubyte", "aschar", "snuval"):
        return kind, args[0]
    value = _eval(args[0], bindings)
    if kind == "~":
        return "wubyte", int(value[0] == "snuval" or value[1] == 0)
    if kind in ("=", "!"):
        equal = value == _eval(args[1], bindings)
        return "wubyte", int(equal if kind == "=" else not equal)
    if value[0] == "snuval":
        raise ArithmeticError("null arithmetic")
    modulus = 256 if value[0] == "wubyte" else 128
    return value[0], (value[1] + (1 if kind == "+" else -1)) % modulus


def _read(kind, stdin, cursor):
    if cursor == len(stdin):
        return (kind, 0), cursor
    if kind == "aschar":
        value = ord(stdin[cursor])
        return (kind, value if value < 128 else 0), cursor + 1
    end = stdin.find("\n", cursor)
    stop = len(stdin) if end < 0 else end + 1
    text = stdin[cursor:stop].strip()
    value = int(text) if re.fullmatch(r"[0-9]{1,3}", text) else 0
    return (kind, value if value <= 255 else 0), stop


def _statement(statement, bindings, types, stdin, cursor):
    kind, *args = statement
    if kind == "out":
        tag, value = _eval(args[0], bindings)
        text = (
            f"{value:02X}"
            if tag == "wubyte"
            else chr(value)
            if tag == "aschar"
            else "$"
        )
        return cursor, text
    name = args[0]
    if kind == "in":
        tag = types[name]
        bindings[name], cursor = _read(tag, stdin, cursor)
    else:
        value = _eval(args[1], bindings)
        if kind == "declare":
            if name in bindings or value[0] == "snuval":
                raise ArithmeticError("declaration")
            types[name] = value[0]
        elif value[0] != "snuval" and value[0] != types[name]:
            raise ArithmeticError("assignment type")
        bindings[name] = value
    return cursor, ""


def _model(statements, stdin):
    bindings, types, pc, cursor, output, trace, done = {}, {}, 0, 0, "", [], False

    def row():
        state = (
            None
            if done
            else (pc, tuple(sorted(bindings.items())), tuple(sorted(types.items())))
        )
        return state, done, output, cursor, cursor

    for statement in statements:
        trace.append(row())
        pending, pending_types = dict(bindings), dict(types)
        try:
            cursor, text = _statement(statement, pending, pending_types, stdin, cursor)
        except (ArithmeticError, KeyError):
            return "halt", [*trace, row()]
        bindings, types, pc, output = pending, pending_types, pc + 1, output + text
    trace.append(row())
    done = True
    return None, trace + [row()] * 4


def _view(machine):
    if machine.state is None:
        return None
    frame = machine.state[0]
    names = machine.prog.fns[frame.fn].names
    values = (
        (name, (value.kind, value.code))
        for name, value in zip(names, frame.scope, strict=True)
        if value is not None
    )
    types = (
        (name, frame.declared(slot))
        for slot, name in enumerate(names)
        if frame.scope[slot] is not None
    )
    return frame.blocks[-1][1], tuple(sorted(values)), tuple(sorted(types))


def _check(factory, statements, stdin="unused"):
    assert len(statements) < 48
    code = "\n".join(_line(statement) for statement in statements)
    assert observed(factory, code, stdin, _view, cap=48) == _model(statements, stdin), (
        code,
        stdin,
    )


def check_raw_dinac():
    literals = (
        tuple(("wubyte", value) for value in (0, 1, 65, 127, 255))
        + tuple(("aschar", value) for value in (0, 9, 65, 127))
        + (("snuval", 0),)
    )
    for value, operator in product(literals, ("+", "-", "~")):
        _check(_Machine, (("out", (operator, value)),))
    for left, right, operator in product(literals, literals, ("=", "!")):
        _check(_Machine, (("out", (operator, left, right)),))
    for initial, assigned in product(literals, repeat=2):
        _check(
            _Machine,
            (
                ("declare", "value", initial),
                ("assign", "value", assigned),
                ("out", "value"),
            ),
        )
    for tag, stdin in product(
        ("wubyte", "aschar"),
        (
            "",
            "\n",
            "Aλ",
            "12\nZ",
            "256\n",
            "-1\n",
            "1 2\n",
            "٣\n",
            "1_0\n",
            "127\r\n",
            "255\n",
            "7",
            "é",
        ),
    ):
        _check(
            _Machine,
            (
                ("declare", "value", (tag, 0)),
                ("in", "value"),
                ("out", "value"),
                ("in", "value"),
                ("out", "value"),
            ),
            stdin,
        )
    for tag, value in product(("wubyte", "aschar"), literals):
        _check(
            _Machine,
            (
                ("declare", "value", (tag, 0)),
                ("assign", "value", ("snuval", 0)),
                ("assign", "value", value),
                ("out", "value"),
            ),
        )
    for tag, stdin in product(("wubyte", "aschar"), ("", "65\nZ", "λ")):
        prefix = (("declare", "value", (tag, 0)), ("assign", "value", ("snuval", 0)))
        _check(_Machine, (*prefix, ("in", "value"), ("out", "value")), stdin)
        for expr in ("value", ("+", "value"), ("=", "value", ("snuval", 0))):
            _check(_Machine, (*prefix, ("out", expr)))
    _check(_Machine, (("out", "unknown"),))
    _check(_Machine, ())

    class WrongOutput(_Machine):
        def step(self):
            super().step()
            self.io.print_str("!")

    for factory in (stalled(_Machine), WrongOutput, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, (("out", ("wubyte", 1)),))
