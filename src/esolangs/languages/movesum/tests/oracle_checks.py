"""Revision 189501 Movesum, using mutable cells and an independent token reader."""

import itertools
import random

import pytest

from esolangs.languages.movesum.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _parse(source):
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError
    seeds = []
    for word in lines[0].split():
        key, equals, value = word.partition("=")
        if not equals or not key.isdecimal() or not value.isdecimal():
            raise ValueError
        seeds.append((key, value))
    commands = []
    for line in lines[1:]:
        if line == "sum":
            commands.append("sum")
            continue
        fields = line.split()
        if (
            len(fields) != 3
            or fields[0] != "move"
            or any(
                not (v[1:] if v.startswith("-") else v).isdecimal() for v in fields[1:]
            )
        ):
            raise ValueError
        commands.append(tuple(map(int, fields[1:])))
    return seeds, commands


def _number(stdin, at):
    while at < len(stdin) and stdin[at].isspace():
        at += 1
    start = at
    while at < len(stdin) and not stdin[at].isspace():
        at += 1
    token = stdin[start:at]
    if not token:
        return 0, at, None
    digits = token[1:] if token[:1] in "+-" else token
    if not digits or any(c not in "0123456789" for c in digits):
        return None, at, "argument"
    number = int(token)
    return number, at, "halt" if number < 0 else None


def _seed(seeds, stdin, consumed):
    staging = {}
    for raw_key, raw_value in seeds:
        if raw_key == "42":
            key, consumed, error = _number(stdin, consumed)
            if error:
                return None, consumed, error
        else:
            key = int(raw_key)
        if raw_value == "42":
            value, consumed, error = _number(stdin, consumed)
            if error:
                return None, consumed, error
        else:
            value = int(raw_value)
        staging[key] = value
    return staging, consumed, None


def _model(source, stdin):
    try:
        seeds, commands = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    pc, cells, quiet, printed, consumed, output, error = 0, None, 0, False, 0, "", None

    def view():
        memory = tuple(sorted(cells.items())) if cells is not None else ()
        state = (pc, memory, quiet, printed) if cells is not None else None
        return (
            (state, pc, memory),
            cells is not None and quiet >= 2,
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if cells is not None and quiet >= 2:
            break
        if cells is None:
            cells, consumed, error = _seed(seeds, stdin, consumed)
        else:
            command, write, outgoing = commands[pc], None, None
            if command == "sum":
                write = (0, sum(cells.get(i, 0) for i in (1, 2, 3, 4)))
            else:
                a, b = command
                if a < 0 <= b:
                    value, consumed, error = _number(stdin, consumed)
                    write = (b, value)
                elif a >= 0 > b:
                    outgoing = cells.get(a, 0)
                elif a >= 0 and b >= 0:
                    write = (b, cells.get(a, 0))
            if not error:
                if write is not None and cells.get(write[0], 0) != write[1]:
                    cells[write[0]], quiet = write[1], 0
                else:
                    quiet += 1
                if outgoing is not None:
                    output += (" " if printed else "") + str(outgoing)
                    printed = True
                pc = (pc + 1) % len(commands)
        trace.append(view())
        if error:
            break
    if not error and cells is not None and quiet >= 2:
        trace.extend([view()] * 3)
    return error, trace


def _view(machine):
    state = machine.state
    if state is not None:
        state = (state[0], tuple(sorted(state[1].items())), *state[2:])
    return state, machine.ip, tuple(sorted(machine.memory.items()))


def _agrees(factory, source, stdin):
    expected = _model(source, stdin)
    assert observed(factory, source, stdin, _view) == expected, (source, stdin)
    return expected


def check_raw_movesum():
    seeds = ("0=0", "1=2 2=3 3=4 4=5", "42=42", "0=42", "0=1 0=2", "042=42")
    commands = (
        "sum",
        "move 0 0",
        "move 1 0",
        "move 0 1",
        "move 5 6",
        "move -7 0",
        "move 0 -9",
        "move -1 -2",
    )
    corpus = [
        seed + "\n" + "\n".join(pair)
        for seed in seeds
        for pair in itertools.product(commands, repeat=2)
    ]
    rng = random.Random(20261103)
    corpus += [
        rng.choice(seeds) + "\n" + "\n".join(rng.choices(commands, k=8))
        for _ in range(64)
    ]
    corpus += [
        "1=42 2=42\nsum\nmove 0 -1\nmove 0 0",
        "0=42\nmove 0 -1\nmove 0 1\nmove 2 1",
        "0=042\nmove 0 -1",
        "42=1 42=2\nmove 0 -1",
        "0=0\nmove -1 -1",
        "\u0661=\u0662\nsum",
        "0=0\u2028sum",
        "0=0\nmove\t-0\t1",
    ]
    inputs = ("", "1 2 3 4", " 0 +2\n", "-1 3", "x")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    for code in (
        "",
        "0=0",
        "sum",
        "=0\nsum",
        "0=\nsum",
        "0=-1\nsum",
        "0=0\nSum",
        "0=0\nmove +1 0",
        "0=0\nmove --1 0",
        "0=0\nmove 1 2 3",
        "0_0=0\nsum",
    ):
        results.append(_agrees(_Machine, code, "unread"))
    for stdin in ("1 x", "1 -1", "  ", "٣", "1_0", "2 3 trailing"):
        results.append(_agrees(_Machine, "42=42\nsum", stdin))
    assert {error for error, _ in results} == {None, "syntax", "argument", "halt"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("1=42 2=42\nsum\nmove 0 -1\nmove 0 0", "2 3")[1][-1][2] == "5"
    controls = {
        "sum": ("1=2 4=3\nsum", ""),
        "copy": ("0=1\nmove 0 1", ""),
        "quiet": ("0=0\nmove 5 6", ""),
        "threshold": ("0=0\nsum", ""),
        "seed": ("42=42\nsum", "1 2"),
        "eof": ("0=42\nsum", ""),
        "negative": ("0=42\nsum", "-1"),
        "both": ("0=0\nmove -1 -2", "1"),
        "format": ("0=1\nmove 0 -1", ""),
        "syntax": ("0=0\nSum", ""),
        "posthalt": ("0=0\nsum", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eof" or self.mode == "negative":
                    io.input_num = lambda: 1
                super().__init__(
                    code.replace("Sum", "sum") if self.mode == "syntax" else code, io
                )
                if self.mode == "seed":
                    read = self._number
                    values = [read(), read()]
                    self._number = values.pop

            @property
            def halted(self):
                if self.mode == "threshold":
                    return self.state is not None and self.state[2] >= 1
                return super().halted

            def step(self):
                if self.halted:
                    super().step()
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                before = self.state
                if self.mode == "both" and before is not None:
                    self.io.input_num()
                super().step()
                if before is None or self.state is None:
                    return
                pc, cells, quiet, printed = self.state
                if self.mode in ("sum", "copy"):
                    cells = {**cells, 0 if self.mode == "sum" else 1: 0}
                elif self.mode == "quiet":
                    quiet = 0
                elif self.mode == "format" and printed:
                    self.io.print_str("\n")
                self.state = pc, cells, quiet, printed

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    return len(results), len(controls)
