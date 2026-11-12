"""Independent complex-plane Dig walker, bounded to 48 steps.

https://esolangs.org/wiki/Dig, revision 189083, command and priority tables.
Work, steering, mutable cells, input and boundary halts; initial rightward
heading, division and output retain the public contract's choices.
"""

import re
from decimal import Decimal
from itertools import product

import pytest

import esolangs
from esolangs.languages.dig.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import observed, reject_faults
from tests.support import workspace_oracle as workspace
from tests.support.model_input import token_span

_WORKSPACE = workspace.workspace_model(
    "dig-v2", "row column direction mole number grid input_cursor input_reads stopped"
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
    start, cursor = token_span(stdin, cursor)
    if start == cursor:
        return None, cursor, "input"
    text = stdin[start:cursor]
    if re.fullmatch(r"[+-]?\d(?:_?\d)*", text) is None:
        return None, cursor, "syntax"
    value = 0
    for digit in text.lstrip("+-").replace("_", ""):
        value = 10 * value + int(digit)
    return value * (-1 if text.startswith("-") else 1), cursor, None


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
                        output += format(Decimal(mole), "f") if mole < 10 else chr(mole)
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
        except (OverflowError, ValueError) as error:
            kind = "overflow" if isinstance(error, OverflowError) else "syntax"
            return kind, [*trace, row()]
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


def _parts(row):
    grid, point, direction, mole, number, reads = row[0]
    return (
        int(point.imag),
        int(point.real),
        (-1j, 1, 1j, -1).index(direction),
        mole,
        number,
        grid,
        row[-1],
        reads,
        row[1],
    )


def _check(factory, lines, stdin="unused"):
    expected = _model(lines, stdin)
    checked = workspace.workspace_view(expected[1], _WORKSPACE, _parts, _view)
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

    reject_faults(_check, _Machine, WrongValue, [">$2:@", " 2"])
    workspace.check_erasures(_WORKSPACE, lambda f: _check(f, [">$2:@", " 2"]), _Machine)

    latch = _model(["@"], "unused")[1]
    assert _parts(latch[0])[:-1] == _parts(latch[1])[:-1]
    assert [row[1] for row in latch[:2]] == [False, True]
    assert workspace.charged_bits(_WORKSPACE, map(_parts, latch)) == 1
    _check(_Machine, ["@"])

    for token in (
        "1" + "0" * 5000,
        "+" + "_".join("\u0669" * 5000),
        "-00_\u0661_\u0662",
        "1" + "0" * 5000 + "__1",
        "+" + "\u0669" * 5000 + "x",
        "0x10",
        "²",
        "+",
        "1_",
    ):
        _check(_Machine, [">$~0:@", " 3"], token + " Z")
    for token in ("-" + "9" * 5000, "-" + "\uff19" * 5000):
        _check(_Machine, [">$~:=:@", " 4"], token + " Z")
    for stdin in ("", " \t\n"):
        _check(_Machine, [">$~0:@", " 3"], stdin)
    assert _read("~", "-00_\u0661_\u0662 Z", 0) == (-12, 7, None)
    assert (
        _model([">$~:=:@", " 4"], "-" + "\uff19" * 5000 + " Z")[1][-1][2]
        == "-" + "9" * 5000 + " "
    )
    lines = [">$~:@", " 2"]
    for token, value in (("1114112", 1114112), ("1" + "0" * 5000, 10**5000)):
        with pytest.raises((ValueError, OverflowError)) as builtin:
            chr(value)
        raw = type(builtin.value)
        public = (
            esolangs.InterpreterLimitError
            if raw is OverflowError
            else esolangs.ProgramError
        )
        kind = "overflow" if raw is OverflowError else "syntax"
        failure, rows = _model(lines, token)
        assert failure == kind
        io = ScriptedIO(token)
        machine = _Machine(lines, io)
        for _ in range(3):
            machine.step()
        captured = machine.workspace_snapshot()
        assert captured.parts == _parts(rows[-1])
        assert not machine.halted
        for _ in range(2):
            with pytest.raises(raw):
                machine.step()
            assert machine.workspace_snapshot() == captured
        assert io.getvalue() == ""
        usage = io.position(), io.progress(), io.reads, io.past_end
        assert usage == (len(token), len(token), 1, 0)
        with pytest.raises(public) as caught:
            esolangs.run("Dig", "\n".join(lines), stdin=token)
        assert caught.value.observation == esolangs.ExecutionResult(
            "", len(token), 1, 0
        )
