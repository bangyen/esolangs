"""Painfuck model from the published substitution table and command meanings.

https://esolangs.org/wiki/Painfuck, revision 189090. Basic tape/loops,
scripted conditional execution and token/character I/O, 32 steps. Repeat
runs c/t and trailing zero-coin y remain outside this bounded model; their
existing regressions and explicit Decisions remain in force.
"""

import re
from itertools import product

import pytest

from esolangs.languages.painfuck.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import stalled
from tests.support import workspace_oracle as workspace
from tests.support.model_input import token_span

_WORKSPACE = workspace.workspace_model(
    "painfuck-v1",
    "tape loops pointer instruction repeat origin input_cursor input_reads draws",
)

_BEFORE = "pysrlijouavbtkzhwqdec"
_AFTER = "euopdhzbclkqsjwariyvt"


def _encode(commands):
    inverse = dict(zip(_AFTER, _BEFORE, strict=True))
    out = []
    for i, target in enumerate(commands):
        command = target
        for _ in range(i):
            command = inverse[command]
        out.append("!?\n" + command)
    return "".join(out)


class _Coin:
    def __init__(self, value):
        self.value = value

    def randbelow(self, upper):
        return self.value % upper


class _Model:
    def __init__(self, commands, coin):
        self.commands, self.coin = commands, coin
        self.tape, self.loops = [0], []
        self.pointer = self.pc = self.origin = 0
        self.repeat = 1
        self.cursor = self.reads = self.draws = 0
        self.output = ""

    @property
    def halted(self):
        return self.pc >= len(self.commands)

    def row(self):
        return (
            (
                tuple(self.tape),
                tuple(self.loops),
                self.pointer,
                self.pc,
                self.repeat,
                self.origin,
                self.reads,
                self.draws,
                self.commands,
            ),
            self.halted,
            self.output,
            self.cursor,
            self.cursor,
        )

    def read(self, command, stdin):
        if command == "j":
            if self.cursor == len(stdin):
                return "input"
            value = ord(stdin[self.cursor])
            self.cursor += 1
        else:
            start, self.cursor = token_span(stdin, self.cursor)
            if self.cursor == start:
                return "input"
            token = stdin[start : self.cursor]
            self.reads += 1
            if re.fullmatch(r"[+-]?[0-9]+", token) is None:
                return "halt"
            value = int(token)
        if command == "j":
            self.reads += 1
        self.tape[self.pointer] = value
        return None

    def loop(self, command):
        if command == "b":
            if not self.loops:
                return "halt"
            entry = self.loops.pop()
            if self.tape[self.pointer]:
                self.pc = entry
        elif self.tape[self.pointer]:
            self.loops.append(self.pc - 1)
        else:
            depth = 1
            while self.pc < len(self.commands) and depth:
                char = self.commands[self.pc]
                depth += (char == "a") - (char == "b")
                self.pc += 1
        return None

    def data(self, command):
        value = self.tape[self.pointer]
        if command == "p":
            self.tape[self.pointer] = value + 2
        elif command == "s":
            self.tape[self.pointer] = value - 1
        elif command == "k":
            self.tape[self.pointer] = value * value
        elif command == "z":
            self.tape[self.pointer] = 0
        elif command == "h":
            self.tape[self.pointer] = value // 2
        elif command == "r":
            self.pointer += 2
            while self.pointer >= len(self.tape):
                self.tape.append(0)
        elif command == "l":
            if self.pointer:
                self.pointer -= 1
            else:
                self.tape.insert(0, 0)
                self.origin += 1
        elif command == "d":
            self.pointer = self.origin
        elif command == "w":
            self.tape[self.pointer] = (
                self.tape[self.pointer + 1] if self.pointer + 1 < len(self.tape) else 0
            )
        elif command == "q":
            self.tape[self.pointer] = self.tape[self.pointer - 1] if self.pointer else 0
        elif command == "o":
            self.output += str(value)
        elif command == "u":
            self.output += chr(value % 256)

    def step(self, stdin):
        command = self.commands[self.pc]
        self.pc += 1
        self.repeat = 0
        while command in "yv":
            if command == "y":
                self.draws += 1
                execute = not self.coin
            else:
                execute = self.tape[self.pointer] == 0
            if self.pc == len(self.commands):
                self.repeat = 1
                return None
            command, self.pc = self.commands[self.pc], self.pc + 1
            if not execute:
                self.repeat = 1
                return None
        if command in "ij":
            error = self.read(command, stdin)
            if error:
                return error
        elif command in "ab":
            error = self.loop(command)
            if error:
                return error
        elif command == "e":
            self.pc = len(self.commands)
            return None
        else:
            self.data(command)
        self.repeat = 1
        return None


def _model(commands, stdin, coin):
    machine = _Model(commands, coin)
    trace = [machine.row()]
    for _ in range(32):
        if machine.halted:
            break
        error = machine.step(stdin)
        trace.append(machine.row())
        if error:
            return error, trace
    if machine.halted:
        trace += [machine.row()] * 3
    return None, trace


def _view(machine):
    return (
        machine.tape,
        machine.loop,
        machine.ptr,
        machine.ind,
        machine.rep,
        machine.origin,
        machine._input_reads,
        machine._random_draws,
        machine.prog,
    )


def _check(factory, commands, stdin="unused", coin=0):
    assert not any(c in commands for c in "ct"), "repeat runs are outside this model"

    def build(source, io):
        return factory(source, io, _Coin(coin))

    workspace.agrees(
        _model(commands, stdin, coin),
        (build, _encode(commands), stdin),
        (_WORKSPACE, lambda row: (*row[0][:6], row[-1], *row[0][6:8])),
        _view,
        cap=32,
        context=(commands, stdin, coin),
    )


def check_raw_painfuck():
    # Constructor control checks the entire published permutation without
    # executing an unbounded repeat family.
    for text in (_BEFORE, _AFTER, _BEFORE * 2):
        assert _Machine(_encode(text), ScriptedIO()).prog == text
    for size in range(4):
        for commands in product("psrlzkhdwqou", repeat=size):
            _check(_Machine, "".join(commands))
    for commands, coin in product(
        (
            "pasbu",
            "pazbo",
            "paipbo",
            "asabe",
            "paabbs",
            "paopb",
            "b",
            "a",
            "vpe",
            "pvpe",
            "ype",
            "yype",
            "vype",
            "yvpe",
            "pv",
            "y",
            "py",
            "yy",
        ),
        (0, 1),
    ):
        _check(_Machine, commands, coin=coin)
    for code, stdin in product(
        ("ioe", "jue", "ijoue", "vie", "yje"),
        ("", "  -12 A", "bad\n", "λ\n", "0", "\n"),
    ):
        _check(_Machine, code, stdin)

    class WrongTranslation(_Machine):
        def __init__(self, code, io, rng):
            super().__init__(code, io, rng)
            self.prog = self.prog[::-1]

    class WrongCoin(_Machine):
        def __init__(self, code, io, _rng):
            super().__init__(code, io, _Coin(1))

    for factory, code in (
        (stalled(_Machine), "pou"),
        (WrongTranslation, "pou"),
        (WrongCoin, "ypo"),
    ):
        with pytest.raises(AssertionError):
            _check(factory, code)

    workspace.check_erasures(
        _WORKSPACE, lambda f: _check(f, "lriypasbue", "2"), _Machine
    )
