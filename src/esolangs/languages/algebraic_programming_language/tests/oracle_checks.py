"""Independent big-step algebra and persistent input-binding model.

https://esolangs.org/wiki/Algebraic_Programming_Language, revision 141098.
Fully parenthesized expressions, short circuits and return; compare terminal
state, IO, errors and post-halt stability within 128 VM steps. Functions and
custom operators remain in the raw suite; framing follows public Decisions.
"""

from itertools import product
from operator import add, mod, mul, sub

import pytest

from esolangs.languages.algebraic_programming_language.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread, stable_halt, stalled


def _divide(left, right):
    if isinstance(left, int) and isinstance(right, int):
        quotient, remainder = divmod(left, right)
        if not remainder:
            return quotient
    quotient = left / right
    return int(quotient) if quotient.is_integer() else quotient


_OPERATORS = {"+": add, "-": sub, "*": mul, "/": _divide, "%": mod, "**": pow}


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
    error, trace = observed(factory, code, stdin, stable_halt(_view), cap=128)
    assert (error, trace[-1]) == _model(lines, stdin), (code, stdin)
    assert trace[0] == ((0, (), False), not lines, "", 0, 0)


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
        ("/", ("+", 2**80, 1), 1),
        ("+", ("/", ("**", 10, 30), 1.0), 1),
        ("+", 1, 1.0),
    ):
        _check(_Machine, (line,))
    _check(_Machine, ())
    for code in ("1(2)", "1 +", "(", "UNKNOWN()"):
        error, trace = observed(_Machine, code, "", _view)
        assert error == "syntax"
        assert trace[-1][2:] == ("", 0, 0)

    class WrongOutput(_Machine):
        def step(self):
            super().step()
            self.io.print_str("!")

    for factory in (stalled(_Machine), WrongOutput, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, (("+", 2, 3),))
    check_continuation_accounting()


def check_continuation_accounting():
    from struct import pack

    from esolangs.runtime import _state as ws
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState
    from tests.support.workspace_oracle import missing_workspace

    variant = ws.WorkspaceVariant
    zero = variant("integer", (0,))
    model = ws.WorkspaceModel(
        "algebraic-programming-language-v1",
        ("line", "globals", "frames", "input_cursor"),
    )

    def frame(site, value=zero, work=(), assign=None, locals_=()):
        work = tuple((variant("instruction", (node,)), done) for node, done in work)
        function = variant("function", (site,))
        locals_ = frozenset(locals_)
        return variant(
            "frame", (function, 0, work, value, False, False, assign, locals_)
        )

    def activation(factory, stdin, value, width, *, operator=False):
        header, call = ("a@", "n@") if operator else ("F(a)", "F(n)")
        current = factory(
            f"n\n{header}={{\na&$0\na+1\n}}\nx={call}\nx", ScriptedIO(stdin)
        )
        measured = WrittenState(current.workspace_snapshot())
        for _ in range(8):
            current.step()
            measured.sample(current.workspace_snapshot())
        # Postorder a=0, 0=1, $0=2, a&$0=3; caller waits for the callee.
        expected = model.capture(
            line=3,
            globals=frozenset({("n", value)}),
            frames=(
                frame(2, value, assign="x"),
                frame(1, work=((3, ()),), locals_=(("a", value),)),
            ),
            input_cursor=len(stdin),
        )
        assert current.workspace_snapshot() == expected
        # Frames 2w+28, globals w+8, line 2; all four components are written.
        assert measured.bits == 3 * width + 38 + len(stdin).bit_length()

    for number, stdin in ((2, "2"), (2.0, "2.0")):
        floating = isinstance(number, float)
        value = variant(
            "floating" if floating else "integer",
            (pack("!d", number) if floating else number,),
        )
        for operator in (False, True):
            activation(_Machine, stdin, value, 64 if floating else 2, operator=operator)
    for component in model.components:
        with pytest.raises(AssertionError):
            activation(
                missing_workspace(_Machine, component),
                "2",
                variant("integer", (2,)),
                2,
            )
