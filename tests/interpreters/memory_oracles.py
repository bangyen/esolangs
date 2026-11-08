"""Independent bounded models of self-modifying numeric and grid programs."""

import re
from dataclasses import dataclass
from struct import calcsize

from esolangs.exceptions import ArgumentError, HaltError, InterpreterLimitError
from esolangs.runtime.io import ScriptedIO
from tests.support.model_input import decimal_value
from tests.support.workspace_oracle import WorkspaceWitness


@dataclass(frozen=True)
class MemoryObservation:
    memory: tuple[int, ...] | tuple[str, ...]
    cursor: tuple[int, ...]
    stack: tuple[int, ...]
    string: bool
    output: str
    consumed: int
    draws: int
    halted: bool
    error: str | None


def _load_error():
    return [
        MemoryObservation(
            (),
            (),
            (),
            string=False,
            output="",
            consumed=0,
            draws=0,
            halted=False,
            error="syntax",
        )
    ]


def decimal_fold(word):
    """Fold signed Unicode Nd/underscored decimal text without host digit caps."""
    if re.fullmatch(r"[+-]?\d(?:_?\d)*", word) is None:
        raise ValueError("invalid decimal token")
    return decimal_value(word)


def decleq(code: str, stdin: str, cap: int = 32):
    """Copy-decrement with runtime memory growth, negative writes and I/O."""
    try:
        cells = [
            decimal_fold(word)
            for line in code.splitlines()
            for word in line.partition("#")[0].split()
        ]
    except ValueError:
        return _load_error()
    pc = consumed = 0
    output, error = "", None

    def snapshot():
        return MemoryObservation(
            memory=tuple(cells),
            cursor=(pc,),
            stack=(),
            string=False,
            output=output,
            consumed=consumed,
            draws=0,
            halted=not 0 <= pc < len(cells),
            error=error,
        )

    def read(at):
        return cells[at] if 0 <= at < len(cells) else 0

    trace = [snapshot()]
    for _ in range(cap):
        if not 0 <= pc < len(cells):
            break
        a, b, jump = (read(pc + k) for k in range(3))
        # Stop before allocating a large valid store; still test the hard limit.
        if a != -2 and 4096 <= b < 2**24:
            break
        if a == -2:
            output += chr(read(b) % 256)
            pc += 3
        elif a == -1 and consumed == len(stdin):
            error = "input"
        else:
            value = ord(stdin[consumed]) if a == -1 else read(a) - 1
            if a == -1:
                consumed += 1
            target = b + len(cells) if b < 0 else b
            if target < 0:
                error = "halt"
            elif target >= 2**24:
                error = "limit"
            else:
                if target >= len(cells):
                    cells.extend([0] * (target + 1 - len(cells)))
                cells[target] = value
                pc = jump if a != -1 and value <= 0 else pc + 3
        trace.append(snapshot())
        if error:
            break
    return trace


class _NumberError(Exception):
    pass


class _Befunge:
    def __init__(self, code, stdin, first):
        rows = []
        for line in code:
            if any(char != " " for char in line[80:]):
                raise ValueError
            rows.append(line[:80])
        if not rows or not any(rows) or len(rows) > 25:
            raise ValueError
        if any(ord(char) > 255 for row in rows for char in row):
            raise ValueError
        self.cells = [ord(char) for row in rows for char in row.ljust(80)]
        self.cells.extend([32] * (2000 - len(self.cells)))
        # Snapshots share the unchanged 2000-cell image until a put rewrites it.
        self.image = "".join(map(chr, self.cells))
        self.stack = []
        self.x = self.y = self.consumed = self.draws = 0
        self.dx, self.dy = 1, 0
        self.string = self.done = False
        self.output = ""
        self.stdin, self.first = stdin, first

    def observation(self, error):
        return MemoryObservation(
            (self.image,),
            (self.x, self.y, self.dx, self.dy),
            tuple(self.stack),
            self.string,
            self.output,
            self.consumed,
            self.draws,
            self.done,
            error,
        )

    def pop(self):
        return self.stack.pop() if self.stack else 0

    def number(self):
        while self.consumed < len(self.stdin) and self.stdin[self.consumed].isspace():
            self.consumed += 1
        if self.consumed == len(self.stdin):
            raise EOFError
        start = self.consumed
        while (
            self.consumed < len(self.stdin) and not self.stdin[self.consumed].isspace()
        ):
            self.consumed += 1
        token = self.stdin[start : self.consumed]
        digits = token[1:] if token.startswith(("+", "-")) else token
        if not digits or any(c not in "0123456789" for c in digits):
            raise _NumberError
        value = 0
        for start in range(0, len(digits), 9):
            chunk = digits[start : start + 9]
            value = value * 10 ** len(chunk) + int(chunk)
        return -value if token.startswith("-") else value

    def arithmetic(self, command):
        a = self.pop()
        if command == "!":
            self.stack.append(int(not a))
        elif command == ":":
            self.stack.extend((a, a))
        elif command == "\\":
            self.stack.extend((a, self.pop()))
        elif command != "$":
            self.stack.append(self.binary(command, a, self.pop()))

    def binary(self, command, a, b):
        if command == "+":
            return b + a
        if command == "-":
            return b - a
        if command == "*":
            return b * a
        if command == "`":
            return int(b > a)
        if not a:
            try:
                return self.number()
            except EOFError:
                raise RuntimeError from None
        quotient = abs(b) // abs(a)
        if (a < 0) != (b < 0):
            quotient = -quotient
        return quotient if command == "/" else b - a * quotient

    def direction(self, command):
        if command == "?":
            direction = (self.first + self.draws) % 4
            self.draws += 1
        elif command in ">v<^":
            direction = ">v<^".index(command)
        elif command == "_":
            direction = 2 if self.pop() else 0
        else:
            direction = 3 if self.pop() else 1
        self.dx, self.dy = ((1, 0), (0, 1), (-1, 0), (0, -1))[direction]

    def memory(self, command):
        row, column = self.pop(), self.pop()
        value = self.pop() if command == "p" else None
        if 0 <= row < 25 and 0 <= column < 80:
            if command == "g":
                self.stack.append(self.cells[row * 80 + column])
            else:
                self.cells[row * 80 + column] = value % 256
                self.image = "".join(map(chr, self.cells))
        elif command == "g":
            self.stack.append(0)

    def io(self, command):
        if command == ".":
            self.output += str(self.pop()) + " "
        elif command == ",":
            self.output += chr(self.pop() % 256)
        elif command == "&":
            self.stack.append(self.number())
        else:
            if self.consumed == len(self.stdin):
                raise EOFError
            self.stack.append(ord(self.stdin[self.consumed]))
            self.consumed += 1

    def move(self):
        self.x, self.y = (self.x + self.dx) % 80, (self.y + self.dy) % 25

    def step(self):
        command = chr(self.cells[80 * self.y + self.x])
        if self.string and command != '"':
            self.stack.append(ord(command))
        elif command in "0123456789":
            self.stack.append(ord(command) - 48)
        elif command in "+-*/%!`:\\$":
            self.arithmetic(command)
        elif command in ">v<^?_|":
            self.direction(command)
        elif command == "#":
            self.move()
        elif command == '"':
            self.string = not self.string
        elif command in "gp":
            self.memory(command)
        elif command in ".,&~":
            self.io(command)
        elif command == "@":
            self.done = True
        bits = calcsize("@l") * 8
        if any(not -(2 ** (bits - 1)) <= v < 2 ** (bits - 1) for v in self.stack):
            raise RuntimeError


def befunge(code: list[str], stdin: str, cap: int = 32, *, first: int = 0):
    """Walk a byte torus without production parsing, arithmetic or wiring helpers."""
    try:
        model = _Befunge(code, stdin, first)
    except ValueError:
        return _load_error()
    trace = [model.observation(None)]
    for _ in range(cap):
        if model.done:
            break
        before = model.stack.copy()
        error = None
        try:
            model.step()
        except _NumberError:
            error = "argument"
        except EOFError:
            error = "input"
        except RuntimeError:
            error = "halt"
        if error:
            model.stack = before
        else:
            model.move()
        trace.append(model.observation(error))
        if error:
            break
    return trace


class _Directions:
    def __init__(self, first):
        self.first, self.draws = first, 0

    def randbelow(self, upper):
        assert upper == 4
        value = (self.first + self.draws) % upper
        self.draws += 1
        return value


def observed_memory(
    machine_type, code, stdin, steps, *, grid=False, first=0, workspace=None
):
    io, rng = ScriptedIO(stdin), _Directions(first)
    try:
        machine = machine_type(code, io, rng=rng) if grid else machine_type(code, io)
    except ValueError:
        return _load_error()
    error = None
    prior_grid = flat = None

    def snapshot():
        nonlocal prior_grid, flat
        if workspace is not None:
            workspace(machine)
        if grid:
            state = machine.state
            if state.grid is not prior_grid:
                prior_grid = state.grid
                flat = "".join("".join(row) for row in prior_grid)
            memory, cursor, stack, mode = (
                (flat,),
                state.cursor,
                tuple(machine.stack),
                state.string,
            )
        else:
            memory, cursor, stack, mode = (
                tuple(machine.memory),
                (machine.ip,),
                (),
                False,
            )
        return MemoryObservation(
            memory,
            cursor,
            stack,
            mode,
            io.getvalue(),
            io.position(),
            rng.draws,
            machine.halted,
            error,
        )

    trace = [snapshot()]
    for _ in range(steps):
        if machine.halted:
            break
        try:
            machine.step()
        except InterpreterLimitError:
            error = "limit"
        except ArgumentError:
            error = "argument"
        except HaltError:
            error = "halt"
        except EOFError:
            error = "input"
        except ValueError:
            error = "syntax"
        trace.append(snapshot())
        if error:
            break
    return trace


def checked_run(runner, code, stdin, expected, *, grid=False, first=0):
    """Run only cases whose stepped model already halted or raised within cap."""
    if not expected.halted and expected.error is None:
        return
    io, rng = ScriptedIO(stdin), _Directions(first)
    error = None
    try:
        if grid:
            runner(code, io, rng=rng)
        else:
            runner(code, io)
    except InterpreterLimitError:
        error = "limit"
    except ArgumentError:
        error = "argument"
    except HaltError:
        error = "halt"
    except EOFError:
        error = "input"
    except ValueError:
        error = "syntax"
    assert (io.getvalue(), io.position(), rng.draws, error) == (
        expected.output,
        expected.consumed,
        expected.draws,
        expected.error,
    ), (code, stdin)


def agrees_memory(
    machine_type,
    oracle,
    code,
    stdin="",
    *,
    grid=False,
    first=0,
    runner=None,
    workspace=None,
):
    expected = oracle(code, stdin, first=first) if grid else oracle(code, stdin)
    capture = None
    if workspace is not None:
        model, project = workspace
        witness, predictions = WorkspaceWitness(model), iter(expected)

        def capture(machine):
            predicted = next(predictions)
            assert predicted.cursor
            witness.sample(machine.workspace_snapshot(), project(predicted))

    actual = observed_memory(
        machine_type,
        code,
        stdin,
        len(expected) - 1,
        grid=grid,
        first=first,
        workspace=capture,
    )
    assert actual == expected, (code, stdin, actual, expected)
    if runner is not None:
        checked_run(runner, code, stdin, expected[-1], grid=grid, first=first)
    return expected
