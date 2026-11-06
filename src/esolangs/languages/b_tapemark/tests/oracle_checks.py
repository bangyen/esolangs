"""Complex-coordinate walker for both marker conventions."""

from itertools import product

import pytest

from esolangs.languages.b_tapemark.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import missing_workspace, workspace_view

_HEADINGS = (1, 1j, -1, -1j)
_SYMBOLS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _load(source):
    marks = [{}, {}]
    quoted = False
    starts = []
    for row, line in enumerate(
        source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ):
        for col, char in enumerate(line):
            point = complex(col, row)
            if char == '"':
                quoted = not quoted
            elif not quoted:
                if char in ">v<^":
                    starts.append((point, _HEADINGS[">v<^".index(char)]))
                elif char in _SYMBOLS + "!+-*|?%/\\":
                    marks[0][point] = char
                elif char != " ":
                    raise ValueError
    if quoted or len(starts) != 1:
        raise ValueError
    return marks, starts[0]


def _model(source, stdin, dialect):
    try:
        marks, (start, heading) = _load(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    heads = [start, start]
    active = cursor = 0
    halted = False
    output = ""
    trace = []
    for step in range(25):
        state = active, tuple(heads), heading, tuple(dict(grid) for grid in marks)
        row = state, halted, output, cursor, cursor
        trace.append(row)
        if halted:
            return None, trace + [row] * 3
        if step == 24:
            break
        previous = active
        data = 1 - active
        cmd = marks[active].get(heads[active], " ")
        symbol = marks[data].get(heads[data], " ")
        match cmd:
            case "!":
                halted = True
                continue
            case "/" | "\\":
                heading = heading.conjugate() * (1j if cmd == "\\" else -1j)
            case "+":
                output += symbol
            case "-" if symbol == " ":
                if cursor == len(stdin):
                    return "input", [*trace, row]
                char = stdin[cursor]
                if char != " ":
                    marks[data][heads[data]] = char
                cursor += 1
            case "*":
                heads[active] += heading
                copied = marks[active].get(heads[active])
                if symbol == " " and copied is not None:
                    marks[data][heads[data]] = copied
            case "|":
                heads[data] += heading
            case "?" if symbol == " ":
                active = data
            case "%" if symbol != " ":
                active = data
            case _ if cmd in _SYMBOLS:
                if heading.real:
                    output += cmd
                elif symbol == cmd:
                    active = data
        heads[active if dialect == "new" else previous] += heading
    return None, trace


def _workspace_parts(row):
    active, heads, heading, marks = row[0]
    points = tuple((int(point.real), int(point.imag)) for point in heads)
    grids = tuple(
        frozenset(
            ((int(point.real), int(point.imag)), char) for point, char in grid.items()
        )
        for grid in marks
    )
    return (active, points, _HEADINGS.index(heading), grids, row[1]), row[-1]


def _check(factory, source, stdin, dialect):
    expected = _model(source, stdin, dialect)

    def build(code, io):
        return factory(code, io, swap_marker=dialect)

    def state(machine):
        s = machine.state
        grids = tuple(
            {complex(*point): char for point, char in grid._cells.items()}
            for grid in s.grids
        )
        return (
            s.program,
            tuple(complex(*p) for p in s.positions),
            _HEADINGS[s.direction],
            grids,
        )

    assert (
        observed(
            build,
            source,
            stdin,
            workspace_view(
                expected[1],
                WorkspaceModel("b-tapemark-v1", ("configuration", "input_cursor")),
                _workspace_parts,
                state,
            ),
            cap=24,
        )
        == expected
    ), (source, stdin, dialect)


def check_raw_b_tapemark():
    corpus = [
        ">" + "".join(chars) + "!" for chars in product(" !+-*|?%/\\A0", repeat=2)
    ]
    corpus += [
        "",
        ">^",
        ">a",
        '>"unclosed',
        '> "quoted\r\n>!" !',
        "v\n-\nA\n!",
        ">\\\n /!",
        ">-?+!",
        ">-%+!",
    ]
    for source, stdin, dialect in product(corpus, ("", "A -"), ("new", "old")):
        _check(_Machine, source, stdin, dialect)

    _check(_Machine, ">-!", "Ω", "new")

    class WrongMarker(_Machine):
        def __init__(self, source, io, *, swap_marker):
            super().__init__(
                source, io, swap_marker="old" if swap_marker == "new" else "new"
            )

    with pytest.raises(AssertionError):
        _check(WrongMarker, ">?!", "", "new")
    for component in ("configuration", "input_cursor"):
        with pytest.raises(AssertionError):
            _check(missing_workspace(_Machine, component), ">-!", "x", "new")
