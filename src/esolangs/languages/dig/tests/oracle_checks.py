"""Independent complex-plane Dig walker, bounded to 48 steps.

https://esolangs.org/wiki/Dig, revision 189083, command and priority tables.
Work, steering, mutable cells, input and boundary halts; initial rightward
heading, division and output retain the public contract's choices.
"""

from itertools import product

import pytest

from esolangs.languages.dig.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed, overread, stalled
from tests.support.workspace_oracle import missing_workspace, workspace_view

_WORKSPACE = WorkspaceModel(
    "dig-v1",
    (
        "row",
        "column",
        "direction",
        "mole",
        "number",
        "grid",
        "input_cursor",
        "input_reads",
    ),
)


def _adjacent(cells, point):
    for delta in (-1j, 1, 1j, -1):
        value = cells.get(point + delta, " ")
        if type(value) is int:
            return value
        if value in "0123456789":
            return int(value)
    raise ArithmeticError("missing operand")


def _read(command, stdin, cursor):
    if command == "=":
        if cursor == len(stdin):
            return None, cursor, "input"
        return ord(stdin[cursor]), cursor + 1, None
    while cursor < len(stdin) and stdin[cursor].isspace():
        cursor += 1
    start = cursor
    while cursor < len(stdin) and not stdin[cursor].isspace():
        cursor += 1
    if start == cursor:
        return None, cursor, "input"
    text = stdin[start:cursor]
    try:
        value = int(text)
    except ValueError:
        return None, cursor, "syntax"
    return value, cursor, None


def _work(command, value, cells, point):
    if type(command) is int:
        return command
    if command in "%+-*/":
        operand = _adjacent(cells, point)
        if command == "%":
            return {0: 32, 1: 10}.get(operand, value)
        return {
            "+": lambda: value + operand,
            "-": lambda: value - operand,
            "*": lambda: value * operand,
            "/": lambda: value // operand,
        }[command]()
    if command == ";":
        cells[point] = value
    elif command == ":":
        return 0
    elif command in "0123456789":
        return int(command)
    elif command.isalpha() or command in ".,!?":
        return ord(command)
    return value


def _model(lines, stdin):
    if not lines or not any(line.strip() for line in lines):
        return "syntax", [(None, False, "", 0, 0)]
    width = max(map(len, lines))
    cells = {
        x + y * 1j: c
        for y, line in enumerate(lines)
        for x, c in enumerate(line.ljust(width))
    }
    point, direction, mole, underground = 0j, 1, 0, 0
    done, cursor, reads, output, trace = False, 0, 0, "", []

    def row():
        grid = tuple(
            tuple(cells[x + y * 1j] for x in range(width)) for y in range(len(lines))
        )
        return (
            (grid, point, direction, mole, underground, reads),
            done,
            output,
            cursor,
            cursor,
        )

    for tick in range(49):
        trace.append(row())
        if done:
            return None, trace + [row()] * 3
        if tick == 48:
            break
        command = cells[point]
        try:
            if underground:
                if command in ("=", "~"):
                    value, cursor, error = _read(command, stdin, cursor)
                    reads += error != "input"
                    if error:
                        return error, [*trace, row()]
                    mole = value
                else:
                    if command == ":":
                        output += str(mole) if mole < 10 else chr(mole)
                    mole = _work(command, mole, cells, point)
                underground -= 1
            elif command in ("^", ">", "'", "<"):
                direction = {"^": -1j, ">": 1, "'": 1j, "<": -1}[command]
            elif command == "#":
                direction *= {0: -1j, 1: 1j}.get(_adjacent(cells, point), 1)
            elif command == "$":
                underground = _adjacent(cells, point)
                if underground < 0:
                    raise ArithmeticError("negative depth")
            elif command == "@":
                done = True
                continue
        except ArithmeticError:
            return "halt", [*trace, row()]
        point += direction
        done = not (0 <= point.real < width and 0 <= point.imag < len(lines))
    return None, trace


def _view(machine):
    return (
        machine.code,
        machine.col + 1j * machine.row,
        (-1j, 1, 1j, -1)[machine.move],
        machine.mole,
        machine.num,
        machine._input_reads,
    )


def _check(factory, lines, stdin="unused"):
    expected = _model(lines, stdin)
    checked = workspace_view(
        expected[1],
        _WORKSPACE,
        lambda row: (
            int(row[0][1].imag),
            int(row[0][1].real),
            (-1j, 1, 1j, -1).index(row[0][2]),
            row[0][3],
            row[0][4],
            row[0][0],
            row[-1],
            row[0][5],
        ),
        _view,
    )
    assert observed(factory, lines, stdin, checked, cap=48) == expected, (lines, stdin)


def check_raw_dig():
    for value, operand, command in product("0129A", "01239", "+-*/%"):
        _check(_Machine, [">$" + value + command + ":@", " 3 " + operand])
    for first, second in product("01A.,!?;: #$@^>'<", repeat=2):
        _check(_Machine, [">$" + first + second + ":@", " 3"])
    for control, operand in product("#$", "0129"):
        for lines in (
            [">" + control + "@", " " + operand],
            [">" + control + operand + "@", " 9"],
            [">" + control + "@", "  "],
            [">" + control + "@", " " + operand, " <"],
        ):
            _check(_Machine, lines)
    for command, stdin in product("=~", ("", " \n", "-12 Z", "9 λ", "λ\n", "1_0", "٣")):
        _check(_Machine, [">$" + command + ":@", " 2"], stdin)
    for stdin in ("-3", "-7", "bad"):
        _check(_Machine, [">$~/:@", " 3 2"], stdin)
    for lines in (
        [">$H:e:l:l:$o:%:W:o:$r:l:d:!:@", " 8        8  0     8"],
        [">$=:'", "^2  <"],
        [">$5;@", " 2"],
        ["@$1;", " 2"],
        ["^"],
        ["<"],
        ["'", "@"],
        [">$+@", " 1"],
        [],
        [""],
        ["  "],
    ):
        _check(_Machine, lines, "Hi")

    class WrongValue(_Machine):
        def step(self):
            super().step()
            self.mole += 1

    for factory in (stalled(_Machine), WrongValue, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, [">$2:@", " 2"])
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _check(missing_workspace(_Machine, component), [">$2:@", " 2"])
