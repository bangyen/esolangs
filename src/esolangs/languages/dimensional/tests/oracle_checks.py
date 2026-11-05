"""Flat path model of Dimensional v3, axes 2..5 and 64 commands.

https://esolangs.org/wiki/Dimensional, structure and syntax (revision 156292).
Pointer positions and bytes use separate path maps, without lazy node objects.
Default operands, independent bracket pairs and token input follow Decisions.
"""

import re
from itertools import product

import pytest

from esolangs.languages.dimensional.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread, stalled


def _assemble(code):
    pairs, stacks, operands = {}, {"[": [], "{": []}, {}
    comment, i = False, 0
    while i < len(code):
        start, c = i, code[i]
        i += 1
        if c == "*":
            comment = not comment
        elif not comment:
            if c in ":=":
                size = 1 if c == ":" else 2
                text = code[i : i + size]
                if len(text) != size or (
                    c == "=" and not re.fullmatch(r"[0-9a-fA-F]{2}", text)
                ):
                    raise ValueError("literal")
                operands[start] = (ord(text) if c == ":" else int(text, 16), i + size)
                i += size
            elif c in "><${?!":
                match = re.match(r"(~?)([0-9]*)", code[i:])
                sign, digits = match.groups()
                value = int(digits) * (-1 if sign else 1) if digits else None
                if c == "$":
                    value = max(2, 2 if value is None else value)
                    assert value <= 5, "model axis bound"
                elif c not in "><" and value is None:
                    value = 0
                operands[start] = (value, i + len(match.group()))
                i += len(match.group())
            if c in stacks:
                stacks[c].append(start)
            elif c in "]}":
                previous = stacks["[" if c == "]" else "{"].pop()
                pairs[start], pairs[previous] = previous, start
    if any(stacks.values()):
        raise ValueError("unmatched")
    return operands, pairs


def _read(command, stdin, cursor):
    if command == ",":
        if cursor == len(stdin):
            return None, cursor, "input"
        return ord(stdin[cursor]), cursor + 1, None
    while cursor < len(stdin) and stdin[cursor].isspace():
        cursor += 1
    begin = cursor
    while cursor < len(stdin) and not stdin[cursor].isspace():
        cursor += 1
    text = stdin[begin:cursor]
    if not text:
        return None, cursor, "input"
    try:
        if command == "d" and not re.fullmatch(r"[+-]?[0-9]+", text):
            raise ValueError("decimal")
        return int(text, 10 if command == "d" else 16), cursor, None
    except ValueError:
        return None, cursor, "argument" if command == "d" else "syntax"


def _pointer(command, positions, route, dim):
    coords = dict(positions.get(route, ()))
    previous = coords.get(dim, 0)
    if command in "><!":
        coords[dim] = 0 if command == "!" else previous + (1 if command == ">" else -1)
        key = tuple(sorted((d, v) for d, v in coords.items() if v))
        if key:
            positions[route] = key
        else:
            positions.pop(route, None)
    return previous


def _path(positions, level):
    route = ()
    for _ in range(5, level, -1):
        route += (positions.get(route, ()),)
    return route


def _write(cells, key, value):
    if value is not None:
        value %= 256
        if value:
            cells[key] = value
        else:
            cells.pop(key, None)


def _value(command, byte, literal):
    return {"+": byte + 1, "-": byte - 1, ":": literal, "=": literal}[command]


def _model(code, stdin):
    try:
        operands, pairs = _assemble(code)
    except (ValueError, IndexError):
        return "syntax", [(None, False, "", 0, 0)]
    positions, cells = {}, {}
    pc = cursor = 0
    axis, comment, output, trace = 2, False, "", []

    def location():
        route = _path(positions, 2)
        return (*route, positions.get(route, ()))

    def byte():
        return cells.get(location(), 0)

    def row():
        state = (
            pc,
            comment,
            axis,
            tuple(sorted(positions.items())),
            tuple(sorted(cells.items())),
        )
        return state, pc >= len(code), output, cursor, cursor

    for tick in range(65):
        trace.append(row())
        if pc >= len(code):
            return None, trace + [row()] * 3
        if tick == 64:
            break
        start, c = pc, code[pc]
        pc += 1
        if c == "*":
            comment = not comment
            continue
        if comment:
            continue
        arg, end = operands.get(start, (None, pc))
        pc = end
        value = None
        if c in ",dx":
            value, cursor, error = _read(c, stdin, cursor)
            if error:
                return error, [*trace, row()]
        elif c in "+-:=":
            value = _value(c, byte(), arg)
        elif c == ".":
            output += chr(byte())
        elif c == "$":
            axis = arg
        elif c in "><!?{":
            dim = byte() if arg is None else arg
            coordinate = _pointer(c, positions, _path(positions, axis), dim)
            if c == "?":
                value = coordinate
            elif c == "{" and not coordinate:
                pc = pairs[start] + 1
        elif c == "[" and byte() == 0:
            pc = pairs[start] + 1
        elif c in "]}":
            pc = pairs[start]
        _write(cells, location(), value)
    return None, trace


def _view(machine):
    positions, cells = {}, {}

    def visit(node, route):
        key = tuple(sorted((d, v) for d, v in node.pos.items() if v))
        if key:
            positions[route] = key
        for selected, child in node.slots.items():
            if node.level == 2:
                if child:
                    cells[(*route, selected)] = child
            else:
                visit(child, (*route, selected))

    visit(machine.tape.top, ((),) * (5 - machine.tape.top.level))
    return (
        machine.ind,
        machine.comment,
        machine.tape.axis,
        tuple(sorted(positions.items())),
        tuple(sorted(cells.items())),
    )


def _check(factory, code, stdin="unused"):
    assert observed(factory, code, stdin, _view, cap=64) == _model(code, stdin), (
        code,
        stdin,
    )


def check_raw_dimensional():
    pieces = (
        "+",
        "-",
        ">0",
        "<~1",
        ">",
        "<",
        "?0",
        "!~1",
        "$3",
        "$2",
        "=ff",
        ":λ",
        ".",
        "*[]{}*",
        "ignored",
    )
    for first, second in product(pieces, repeat=2):
        _check(_Machine, first + second + ".")
    for axis, dim, value in product(range(2, 6), ("0", "~1", "12"), ("00", "01", "fe")):
        _check(
            _Machine,
            f"={value}${axis}>{dim}+?{dim}.${axis - 1}>{dim}+"
            f"${axis}<{dim}.${axis - 1}.",
        )
        _check(_Machine, f"={value}${axis}>{dim}+<{dim}.>{dim}.!{dim}.")
    for program in (
        "[+]",
        "=03[-].",
        "=01[>0+<0-]>0.",
        ">0>0{0<0}?0.",
        "<~1{~1>~1}?~1.",
        "[{]}",
        ":].",
        ":*.",
        "=5b.",
        "[=ff:[]",
        "$~3>~?~.",
        "*unterminated[",
        "[$5>0+]",
        "+[]",
    ):
        _check(_Machine, program)
    for command, stdin in product(
        (",.,.", "d.,.", "x.,.", "dx.,."),
        ("", " \n", "Aλ", "-257 Z", "+256\n", "ff A", "1_0 A", "٣ A", "0x10 Z"),
    ):
        _check(_Machine, command, stdin)
    for code in (":", "=", "=f", "=xy", "[", "}", "*:*:", "[=zz]"):
        _check(_Machine, code)

    class WrongByte(_Machine):
        def step(self):
            super().step()
            self.tape.set_value(self.tape.peek_value() + 1)

    for factory in (stalled(_Machine), WrongByte, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, "+$3>0+<0.")
