"""Linear stack model of Freestajlo's instruction table, revision 184252.

https://esolangs.org/wiki/Freestajlo. Arithmetic, stack selection/transfer,
character and numeric I/O; blocks, functions and strings remain in raw tests.
Undefined depths and surrogate output follow the public Decisions.
"""

import re
from itertools import product

import pytest

from esolangs.languages.freestajlo.interpreter import _Machine
from tests.interpreters.oracle_support import decorate_io, observed, overread, stalled
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "freestajlo-v1",
    "instruction stack transfer calls functions index other_stacks input_cursor",
)


def _cells(cells):
    values = []
    while cells is not None:
        value, cells = cells
        values.append(value)
    return tuple(reversed(values))


def _view(machine):
    return (
        machine.ind,
        tuple(machine.stack),
        machine.index,
        tuple(sorted((i, _cells(s[1])) for i, s in machine.others.items() if s[0])),
        _cells(machine.state.transfer[1]),
        machine.state.ip,
    )


def _pop(stack):
    return stack.pop() if stack else 0


def _arithmetic(operation, left, right):
    if operation == "+":
        return left + right
    if operation == "-":
        return left - right
    if operation == "*":
        return left * right
    if operation == "/":
        return abs(left) // abs(right) * (-1 if (left < 0) != (right < 0) else 1)
    if operation == "%":
        return left % right
    if operation == "^":
        return 0 if right < 0 else left**right
    if operation == "=":
        return -int(left == right)
    if operation == "<":
        return -int(left > right)
    if operation == ">":
        return -int(left < right)
    return ~(left | right)


def _local(token, stack):
    if token in "+-*/%^=<>`":
        right, left = _pop(stack), _pop(stack)
        stack.append(_arithmetic(token, left, right))
    elif token == "_":
        stack.append(-_pop(stack))
    elif token == "$":
        value = _pop(stack)
        stack.extend((value, value))
    elif token == "#":
        _pop(stack)
    elif token == "\\":
        first, second = _pop(stack), _pop(stack)
        stack.extend((first, second))
    elif token == "|":
        stack.append(len(stack))
    elif token in "&~":
        depth = _pop(stack)
        value = _pop(stack) if token == "~" else None
        if depth < 0 or depth > len(stack) - (token == "&"):
            raise IndexError(depth)
        if token == "&":
            stack.append(stack[-depth - 1])
        else:
            stack.insert(len(stack) - depth, value)
    elif token in ":.)!":
        return token, _pop(stack)
    else:
        raise AssertionError(token)
    return None


def _model(source, stdin):
    tokens = [
        (m.group(), m.start()) for m in re.finditer(r"[0-9]+|'[\s\S]|[^\s]", source)
    ]
    at = cursor = index = 0
    stacks, transfer, output, trace = {0: []}, [], "", []

    def row():
        return (
            (
                tokens[at][1] if at < len(tokens) else len(source),
                tuple(stacks[index]),
                index,
                tuple(
                    sorted((i, tuple(s)) for i, s in stacks.items() if i != index and s)
                ),
                tuple(transfer),
                at,
            ),
            at == len(tokens),
            output,
            cursor,
            cursor,
        )

    while True:
        trace.append(row())
        if at == len(tokens):
            return None, trace + [row()] * 3
        token = tokens[at][0]
        stack = stacks[index].copy()
        effect = None
        if token.isdecimal():
            stack.append(int(token))
        elif token.startswith("'"):
            stack.append(ord(token[1]))
        elif token == ",":
            stack.append(ord(stdin[cursor]) if cursor < len(stdin) else -1)
            cursor += cursor < len(stdin)
        elif token == ";":
            match = re.search(r"-?[0-9]+", stdin[cursor:])
            stack.append(int(match.group()) if match else 0)
            cursor = min(len(stdin), cursor + match.end() + 1) if match else len(stdin)
        elif token == "(":
            stack.append(transfer.pop() if transfer else 0)
        else:
            try:
                effect = _local(token, stack)
            except (ZeroDivisionError, IndexError):
                return "halt", [*trace, trace[-1]]
        stacks[index] = stack
        at += 1
        if effect is not None:
            operation, value = effect
            if operation == ")":
                transfer.append(value)
            elif operation == "!":
                index = value
                stacks.setdefault(index, [])
            elif operation == ":":
                output += str(value)
            else:
                point = value % 0x10FFFF
                if 0xD800 <= point <= 0xDFFF:
                    return "halt", [*trace, row()]
                output += chr(point)


def _workspace_parts(row):
    _offset, values, index, others, transfer, instruction = row[0]

    def stack(items):
        return len(items), tuple(reversed(items))

    return (
        instruction,
        stack(values),
        stack(transfer),
        (),
        (-1,) * 52,
        index,
        frozenset((key, stack(items)) for key, items in others),
        row[-1],
    )


def _check(factory, source, stdin="unused"):
    expected = _model(source, stdin)
    checked = workspace.workspace_view(expected[1], _WORKSPACE, _workspace_parts, _view)
    assert observed(factory, source, stdin, checked, cap=64) == expected, (
        source,
        stdin,
    )


def _check_calls(factory):
    # Literal compiled boundaries for two definitions and a nested call.
    source = "A{66 .}B{A}B"
    empty = (-1,) * 52
    defined_a = (1, *empty[1:])
    defined_ab = (1, 5, *empty[2:])
    boundaries = (
        (0, 0, (), (), empty, ""),
        (7, 4, (), (), defined_a, ""),
        (11, 7, (), (), defined_ab, ""),
        (9, 5, (), (8,), defined_ab, ""),
        (2, 1, (), (6, 8), defined_ab, ""),
        (5, 2, (66,), (6, 8), defined_ab, ""),
        (6, 3, (), (6, 8), defined_ab, "B"),
        (10, 6, (), (8,), defined_ab, "B"),
        (12, 8, (), (), defined_ab, "B"),
    )
    trace = [
        ((offset, values, 0, (), (), ip, calls, functions), ip == 8, output, 0, 0)
        for offset, ip, values, calls, functions, output in boundaries
    ]
    trace.extend([trace[-1]] * 3)

    def view(machine):
        calls = []
        rest = machine.state.calls
        while rest is not None:
            value, rest = rest
            calls.append(value)
        return (*_view(machine), tuple(calls), tuple(machine.state.funcs))

    def parts(row):
        _offset, values, index, others, transfer, ip, calls, functions = row[0]
        return (
            ip,
            (len(values), tuple(reversed(values))),
            (len(transfer), tuple(reversed(transfer))),
            calls,
            functions,
            index,
            frozenset(
                (key, (len(items), tuple(reversed(items)))) for key, items in others
            ),
            row[-1],
        )

    checked = workspace.workspace_view(trace, _WORKSPACE, parts, view)
    assert observed(factory, source, "", checked, cap=64) == (None, trace)


def check_raw_freestajlo():
    def literal(value):
        return str(abs(value)) + (" _" if value < 0 else "")

    for left, right, operation in product(range(-2, 4), range(-2, 4), "+-*/%^=<>`"):
        _check(_Machine, f"{literal(left)} {literal(right)} {operation} $ : .")
    for size in range(4):
        for operations in product(
            ("$", "#", "\\", "|", "(", ")", "0 !", "1 !", "0 &", "1 ~"), repeat=size
        ):
            _check(_Machine, "1 2 " + " ".join(operations) + " : : :")
    for source in ("$ : :", "# :", "\\ : :", "| :", "( :", "0 &", "0 ~"):
        _check(_Machine, source)
    for source, stdin in product(
        (", , : :", "; ; : :", "'λ .", "55296 ."), ("", "a\nλ", "junk -12x+3!", "--7-2")
    ):
        _check(_Machine, source, stdin)
    for source in ("?", "@", "{", "}", "[", '"', "'"):
        assert observed(_Machine, source, "", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    wrong_output = decorate_io(
        _Machine, "print_num", lambda write: lambda n: write(n + 1)
    )

    for factory, code in (
        (stalled(_Machine), "1 2 +"),
        (wrong_output, "1 :"),
        (overread(_Machine), ", :"),
    ):
        with pytest.raises(AssertionError):
            _check(factory, code, "ab")
    workspace.check_erasures(_WORKSPACE, _check, _Machine, "1 2 + :")
    _check_calls(_Machine)
    workspace.check_erasures(_WORKSPACE, _check_calls, _Machine)
