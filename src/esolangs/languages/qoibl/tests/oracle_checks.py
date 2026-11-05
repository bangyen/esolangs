"""Independent expression-tree Qoibl model, 32 statements and finite loops.

https://esolangs.org/wiki/Qoibl, revision 84835, instruction table.
Spaced bicharacter assembler, right-associated arithmetic, stores, IO and
decreasing loops. Fused token ambiguity remains in the raw regression suite.
"""

from itertools import product
from operator import add, eq, floordiv, gt, lt, mul, ne, sub

import pytest

from esolangs.languages.qoibl.interpreter import _Machine
from tests.interpreters.oracle_support import observed

_ARITH = dict(zip("+-*/", (add, sub, mul, floordiv), strict=True))
_COMPARE = dict(zip(("=", ">", "<", "!"), (eq, gt, lt, ne), strict=True))


def _source(tree):
    if type(tree) is int:
        assert tree >= 0
        return bin(tree)[2:].translate(str.maketrans("01", "ey"))
    kind, *args = tree
    if kind == "read":
        return "et"
    if kind in ("emit", "at"):
        marker = "tt" if kind == "emit" else "qe"
        return marker + " " + _source(args[0]) + " " + marker
    if kind in ("store", "loop"):
        marker = "we" if kind == "store" else "rr"
        return (
            marker
            + " "
            + _source(args[0])
            + " "
            + marker
            + " "
            + _source(args[1])
            + " "
            + marker
        )
    marker = "ry" if kind in _ARITH else "yr"
    operator = dict(
        zip(
            _ARITH if marker == "ry" else _COMPARE,
            ("ee", "ey", "ye", "yy"),
            strict=True,
        )
    )[kind]
    return (
        _source(args[0])
        + " "
        + marker
        + " "
        + operator
        + " "
        + marker
        + " "
        + _source(args[1])
    )


class _Port:
    def __init__(self, stdin):
        self.stdin, self.cursor, self.output = stdin, 0, ""

    def read(self):
        if self.cursor == len(self.stdin):
            raise EOFError
        value = ord(self.stdin[self.cursor])
        self.cursor += 1
        return value


def _index(value):
    if not 0 <= value < 256:
        raise ArithmeticError("variable bounds")
    return value


def _eval(tree, variables, port):
    if type(tree) is int:
        return tree
    kind, *args = tree
    if kind == "read":
        return port.read()
    if kind == "loop":
        for _ in range(8):
            if not _eval(args[0], variables, port):
                return 0
            _eval(args[1], variables, port)
        raise AssertionError("model loop bound exceeded")
    left = _eval(args[0], variables, port)
    if kind == "at":
        return variables.get(_index(left), 0)
    if kind == "emit":
        port.output += chr(left)
        return 0
    right = _eval(args[1], variables, port)
    if kind == "store":
        variables[_index(left)] = right
        return 0
    if kind in _COMPARE:
        return int(_COMPARE[kind](left, right))
    return _ARITH[kind](left, right)


def _model(statements, stdin):
    variables, pc, trace, port = {}, 0, [], _Port(stdin)

    def row():
        return (
            (pc, tuple(sorted(variables.items()))),
            pc == len(statements),
            port.output,
            port.cursor,
            port.cursor,
        )

    for statement in statements:
        trace.append(row())
        changed = dict(variables)
        try:
            _eval(statement, changed, port)
        except EOFError:
            return "input", [*trace, row()]
        except ArithmeticError:
            return "halt", [*trace, row()]
        except ValueError:
            return "syntax", [*trace, row()]
        variables, pc = changed, pc + 1
    return None, trace + [row()] * 4


def _view(machine):
    return machine.ind, tuple(sorted(machine.var.items()))


def _check(factory, statements, stdin="unused"):
    assert len(statements) <= 32
    code = "\n".join(_source(statement) for statement in statements)
    assert observed(factory, code, stdin, _view, cap=32) == _model(statements, stdin), (
        code,
        stdin,
    )


def check_raw_qoibl():
    for left, right, op in product((0, 1, 5, 65), (0, 1, 3), (*_ARITH, *_COMPARE)):
        value = (op, left, right)
        _check(_Machine, (("store", 7, value), ("emit", ("at", 7))))
    for index, value in product((0, 1, 255, 256), (0, 65)):
        _check(_Machine, (("store", index, value), ("emit", ("at", index))))
        _check(_Machine, (("emit", ("at", index)),))
    for count in range(4):
        decrement = ("store", 0, ("-", ("at", 0), 1))
        _check(
            _Machine,
            (("store", 0, count), ("loop", ("at", 0), decrement), ("emit", ("at", 0))),
        )
    for stdin in ("", "A", "AB", "λ\n", "\0"):
        for statements in (
            (("emit", ("read",)), ("emit", ("read",))),
            (("store", 0, ("read",)), ("emit", ("at", 0))),
            (("emit", 65), ("read",)),
            (("store", ("emit", 65), ("read",)),),
        ):
            _check(_Machine, statements, stdin)
    for op in _ARITH:
        _check(_Machine, (("store", 0, (op, 8, (op, 4, 2))), ("emit", ("at", 0))))
    _check(_Machine, (("store", ("emit", 65), ("/", 1, 0)),))
    _check(_Machine, (("store", 0, ("-", 0, 1)), ("store", 1, ("/", ("at", 0), 2))))
    _check(_Machine, ())
    for code in ("tt", "we e", "rr e rr", "qe qe"):
        assert observed(_Machine, code, "", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class Skips(_Machine):
        def step(self):
            pass

    class WrongStore(_Machine):
        def step(self):
            super().step()
            self.var = {**self.var, 7: 66}

    class ReadsExtra(_Machine):
        def step(self):
            self.io.input_char()
            super().step()

    for factory in (Skips, WrongStore, ReadsExtra):
        with pytest.raises(AssertionError):
            _check(factory, (("store", 7, 65), ("emit", ("at", 7))))
