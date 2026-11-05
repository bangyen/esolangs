"""Independent big-step algebra and persistent input-binding model.

https://esolangs.org/wiki/Algebraic_Programming_Language, revision 141098.
Fully parenthesized expressions, short circuits and return; compare terminal
state, IO, errors and post-halt stability within 128 VM steps. Functions and
custom operators remain in the raw suite; framing follows public Decisions.
"""

from itertools import product
from operator import add, mod, mul, sub, truediv

import pytest

from esolangs.languages.algebraic_programming_language.interpreter import _Machine
from tests.interpreters.oracle_support import observed

_OPERATORS = {"+": add, "-": sub, "*": mul, "/": truediv, "%": mod, "**": pow}


class _ReturnedError(Exception):
    def __init__(self, value):
        self.value = value


def _source(tree):
    if not isinstance(tree, tuple):
        return str(tree) if isinstance(tree, str) or tree >= 0 else f"({tree})"
    kind, *args = tree
    if kind in ("negate", "exit_value"):
        sign = "-" if kind == "negate" else "$"
        return "(" + sign + _source(args[0]) + ")"
    return "(" + _source(args[0]) + kind + _source(args[1]) + ")"


def _variables(tree):
    if isinstance(tree, str):
        yield tree
    elif isinstance(tree, tuple):
        for child in tree[1:]:
            yield from _variables(child)


def _eval(tree, bindings):
    if isinstance(tree, str):
        return bindings[tree]
    if not isinstance(tree, tuple):
        return tree
    kind, *args = tree
    left = _eval(args[0], bindings)
    if kind == "negate":
        return -left
    if kind == "exit_value":
        raise _ReturnedError(left)
    if kind == "&":
        return _eval(args[1], bindings) if left else 0
    if kind == "|":
        return left if left else _eval(args[1], bindings)
    return _OPERATORS[kind](left, _eval(args[1], bindings))


def _read(stdin, cursor):
    while cursor < len(stdin) and stdin[cursor].isspace():
        cursor += 1
    start = cursor
    while cursor < len(stdin) and not stdin[cursor].isspace():
        cursor += 1
    if start == cursor:
        return None, cursor, "input"
    text = stdin[start:cursor]
    try:
        value = float(text) if "." in text else int(text)
        return value, cursor, None
    except ValueError:
        return None, cursor, "halt"


def _model(lines, stdin):
    bindings, cursor, output, line, active = {}, 0, "", 0, False

    def terminal(error):
        state = (line, tuple(sorted(bindings.items())), active)
        return error, (state, line == len(lines) and not active, output, cursor, cursor)

    for expression in lines:
        pending = dict(bindings)
        for name in _variables(expression):
            if name not in pending:
                value, cursor, error = _read(stdin, cursor)
                if error:
                    return terminal(error)
                pending[name] = value
        bindings, line, active = pending, line + 1, True
        try:
            value = _eval(expression, bindings)
        except _ReturnedError as returned:
            value = returned.value
        except ArithmeticError:
            return terminal("halt")
        output += str(int(value) if int(value) == value else value) + "\n"
        active = False
    return terminal(None)


def _view(machine):
    return machine.line, tuple(sorted(machine.globals.items())), bool(machine.frames)


def _check(factory, lines, stdin="unused"):
    code = "\n".join(_source(expression) for expression in lines)
    error, trace = observed(factory, code, stdin, _view, cap=128)
    assert (error, trace[-1]) == _model(lines, stdin), (code, stdin)
    assert trace[0] == ((0, (), False), not lines, "", 0, 0)
    if trace[-1][1]:
        assert trace[-4:] == [trace[-1]] * 4


def check_raw_algebraic_programming_language():
    for left, right, op in product((-3, 0, 1, 5), (0, 1, 2), (*_OPERATORS, "&", "|")):
        _check(_Machine, ((op, left, right),))
    for op, outer in product((*_OPERATORS, "&", "|"), ("+", "*", "&", "|")):
        _check(_Machine, ((outer, (op, 2, 3), ("-", 7, 4)),))
    for condition, op in product((0, 1), ("&", "|")):
        _check(_Machine, ((op, condition, ("/", 1, 0)),))
        _check(_Machine, (("+", 9, (op, condition, ("exit_value", 7))),))
    for stdin in ("", "1", "1 2", "1 2 3 4 5", "0 7 2 8", "bad", " 2.5 -3\n7 9 2"):
        _check(
            _Machine, (("+", ("+", "a", "b"), "d"), ("+", ("+", "c", "e"), "b")), stdin
        )
        _check(_Machine, (("&", 0, ("+", "a", "b")),), stdin)
        _check(_Machine, (65, ("/", "a", "b")), stdin)
    for line in (
        ("negate", 2.5),
        ("+", 1.5, 2.5),
        ("**", 2, -2),
        ("**", 0, -1),
        ("+", 2**80, 1),
        ("exit_value", 9),
    ):
        _check(_Machine, (line,))
    _check(_Machine, ())
    for code in ("1(2)", "1 +", "(", "UNKNOWN()"):
        error, trace = observed(_Machine, code, "", _view)
        assert error == "syntax"
        assert trace[-1][2:] == ("", 0, 0)

    class Skips(_Machine):
        def step(self):
            pass

    class WrongOutput(_Machine):
        def step(self):
            super().step()
            self.io.print_str("!")

    class ReadsExtra(_Machine):
        def step(self):
            self.io.input_char()
            super().step()

    for factory in (Skips, WrongOutput, ReadsExtra):
        with pytest.raises(AssertionError):
            _check(factory, (("+", 2, 3),))
