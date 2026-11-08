"""List-stack model with tuple blocks and independently generated source."""

from collections import deque
from itertools import product
from operator import add, floordiv, mul, neg

import pytest

from esolangs.languages.fackward.interpreter import Block, _Machine
from tests.interpreters.oracle_support import observed, stalled
from tests.support import workspace_oracle
from tests.support.workspace_oracle import workspace_view

_WORKSPACE = workspace_oracle.workspace_model(
    "fackward-v1", "forward backward active swapped stopped input_cursor"
)

_MATH = {"+": add, "-": neg, "*": mul, "/": floordiv, "%": lambda n: int(not n)}
_ARITY = dict(
    zip("+-*/%:~!$(<)H", (2, 1, 2, 2, 1, 1, 2, 1, 2, 1, 2, 1, 0), strict=True)
)


def _source(items):
    return " ".join(
        f"[{_source(x)}]" if isinstance(x, tuple) else str(x) for x in items
    )


def _results(op, args):
    if op in _MATH:
        return [_MATH[op](*args)]
    if op == ":":
        return args * 2
    if op == "~":
        return args[::-1]
    if op == "$":
        if args[0] < 0:
            raise ValueError
        return [args[1]] * args[0]
    if op == "(":
        return [tuple(args)]
    if op == "<":
        return [(*args[0], args[1])]
    if op == ")":
        return args[0]
    return []


def _ready(op, args):
    if op in _MATH:
        return all(isinstance(x, int) for x in args)
    if op == "$":
        return isinstance(args[0], int)
    if op in "<)":
        return isinstance(args[0], tuple)
    return True


def _model(program, stdin):
    front, rear = deque(program), []
    active = swapped = halted = False
    cursor = 0
    output = ""
    trace = []
    for step in range(25):
        state = tuple(front), tuple(reversed(rear)), active, swapped
        row = state, halted, output, cursor, cursor
        trace.append(row)
        if halted:
            return None, trace + [row] * 3
        if step == 24:
            break
        if not front:
            if swapped and not active and cursor == len(stdin):
                halted = True
                continue
            front, rear = deque(reversed(rear)), []
            if swapped and not active:
                rear.append(ord(stdin[cursor]))
                cursor += 1
            active, swapped = False, True
            continue
        token = front.popleft()
        if isinstance(token, int):
            if not 0 <= token <= 0x10FFFF or 0xD800 <= token <= 0xDFFF:
                return "halt", [*trace, row]
            output += chr(token)
            active = True
        elif (
            isinstance(token, str)
            and len(front) >= _ARITY[token]
            and _ready(token, args := list(front)[: _ARITY[token]])
        ):
            try:
                rear.extend(_results(token, args))
            except (ValueError, ZeroDivisionError):
                return "halt", [*trace, row]
            for _ in args:
                front.popleft()
            active, halted = True, token == "H"
        else:
            rear.append(token)
    return None, trace


def _value(item):
    return tuple(map(_value, item.items())) if isinstance(item, Block) else item


def _check(factory, program, stdin):
    expected = _model(program, stdin)

    def state(machine):
        front, rear, active, swapped, *_ = machine.snapshot()
        return tuple(map(_value, front)), tuple(map(_value, rear)), active, swapped

    checked = workspace_view(
        expected[1], _WORKSPACE, lambda row: (*row[0], row[1], row[-1]), state
    )
    assert observed(factory, _source(program), stdin, checked, cap=24) == expected, (
        program,
        stdin,
    )


def check_raw_fackward():
    for op, a, b, stdin in product(
        _ARITY, (0, 1, 65, "!", (66,)), (0, 2, ()), ("", "xyZ")
    ):
        _check(_Machine, (op, a, b, "H"), stdin)
    for program in ((), (":", ":"), ("-", 1, "$", "H"), (0xD800,), (256,)):
        _check(_Machine, program, "abc")

    with pytest.raises(AssertionError):
        _check(stalled(_Machine), ("H",), "")
    workspace_oracle.check_erasures(_WORKSPACE, _check, _Machine, (1, 2, "+"), "")
