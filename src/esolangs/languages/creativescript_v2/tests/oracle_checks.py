"""Revision 164501 CreativeScript v2, using named variables and line scanning."""

import itertools
import random
from decimal import Decimal

import pytest

from esolangs.languages.creativescript_v2.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.support.workspace_oracle import agrees as workspace_agrees
from tests.support.workspace_oracle import check_erasures

_WORKSPACE = WorkspaceModel(
    "creativescript-v2-v1", ("variables", "instruction", "input_cursor")
)


def _literal(word):
    digits = word[1:] if word[:1] in "+-" else word
    return bool(digits) and all(c in "0123456789" for c in digits)


def _parse(source):
    program, names, offset = [], [], 0
    counts = {
        "set!": 2,
        "in!": 1,
        "out!": 1,
        **dict.fromkeys(("add!", "sub!", "mul!", "div!", "mod!"), 3),
    }
    for line in source.split("\n"):
        if line.strip():
            text = line.lstrip()
            command, _space, rest = text.partition(" ")
            args, literal = rest.split(), None
            if command == "say!":
                args, literal = [], rest
            else:
                if command not in counts or len(args) != counts[command]:
                    raise ValueError
                if command == "set!" and _literal(args[1]):
                    literal = int(Decimal(args.pop()))
                for arg in args:
                    if _literal(arg):
                        raise ValueError
                    if arg not in names:
                        names.append(arg)
            program.append((command, args, literal, offset + len(line) - len(text)))
        offset += len(line) + 1
    if not program:
        raise ValueError
    return program, names


def _input(stdin, at):
    while at < len(stdin) and stdin[at].isspace():
        at += 1
    start = at
    while at < len(stdin) and not stdin[at].isspace():
        at += 1
    token = stdin[start:at]
    if not token:
        return None, at, "input"
    return (
        (int(Decimal(token)), at, None) if _literal(token) else (None, at, "argument")
    )


def _model(source, stdin):
    try:
        program, names = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    values, pc, consumed, output, error = dict.fromkeys(names), 0, 0, "", None

    def view():
        state = tuple(values[name] for name in names)
        memory = tuple(value for value in state if value is not None)
        ip = program[min(pc, len(program) - 1)][3]
        return ((state, pc, memory, ip), pc == len(program), output, consumed, consumed)

    trace = [view()]
    for _ in range(64):
        if pc == len(program):
            break
        command, args, extra, _ = program[pc]
        write = None
        if command == "say!":
            output += extra
        elif command == "in!":
            value, consumed, error = _input(stdin, consumed)
            write = args[0], value
        elif command == "set!" and extra is not None:
            write = args[0], extra
        elif command == "set!":
            if values[args[1]] is None:
                error = "halt"
            else:
                write = args[0], values[args[1]]
        elif command == "out!":
            if values[args[0]] is None:
                error = "halt"
            else:
                output += str(Decimal(values[args[0]]))
        else:
            a, b, target = args
            x, y = values[a], values[b]
            if x is None or y is None or (command in ("div!", "mod!") and y == 0):
                error = "halt"
            else:
                operations = {
                    "add!": lambda a, b: a + b,
                    "sub!": lambda a, b: a - b,
                    "mul!": lambda a, b: a * b,
                    "div!": lambda a, b: a // b,
                    "mod!": lambda a, b: a % b,
                }
                write = target, operations[command](x, y)
        if not error:
            if write is not None:
                values[write[0]] = write[1]
            pc += 1
        trace.append(view())
        if error:
            break
    if not error and pc == len(program):
        trace.extend([view()] * 3)
    return error, trace


def _agrees(factory, source, stdin):
    return workspace_agrees(
        _model(source, stdin),
        (factory, source, stdin),
        (_WORKSPACE, lambda row: (row[0][0], row[0][1], row[-1])),
        lambda m: (m.state, m.cursor, tuple(m.memory), m.ip),
    )


def check_raw_creativescript_v2():
    operations = ("add!", "sub!", "mul!", "div!", "mod!")
    corpus = [
        f"set! a {a}\nset! b {b}\n{op} a b c\nout! c"
        for a, b in itertools.product((-3, 0, 2), repeat=2)
        for op in operations
    ]
    atoms = (
        "set! a 3",
        "set! a b",
        "in! a",
        "out! a",
        "say! λ  ",
        "add! a b c",
        "sub! a b c",
        "mul! a a a",
        "div! a b a",
        "mod! a b b",
    )
    corpus += ["\n".join(pair) for pair in itertools.product(atoms, repeat=2)]
    rng = random.Random(20261103)
    corpus += [
        "set! a 3\nset! b -2\n" + "\n".join(rng.choices(atoms, k=8)) for _ in range(64)
    ]
    corpus += [
        "say!",
        " \t say!  a\t b\r",
        "set! a 1\nset! A 2\nout! a\nout! A",
        "set! c -0\nset! b c\nout! b",
        "set! 1_0 4\nout! 1_0",
        "set! \u0663 5\nout! \u0663",
        "set! --1 6\nout! --1",
        "in! a\nin! b\nadd! a b c\nout! c",
        "say! x\n" * 80,
    ]
    inputs = ("", " 1 -2\n3", "x", "\u0663", "+4 5 trailing")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    results.extend(
        _agrees(_Machine, code, "unread")
        for code in (
            "",
            " \n",
            "say!\tx",
            "Set! a 1",
            "set! 1 2",
            "out! 1",
            "add! a 1 c",
            "in! a b",
            "set! a",
            "set! a 1 extra",
            "unknown!",
        )
    )
    results.append(_agrees(_Machine, "set! a " + "0" * 5000 + "7\nout! a", ""))
    results.append(_agrees(_Machine, "in! a\nout! a", "9" * 5000))
    assert {error for error, _ in results} == {
        None,
        "syntax",
        "input",
        "argument",
        "halt",
    }
    assert _model("set! a -3\nset! b 2\ndiv! a b c\nout! c", "")[1][-1][2] == "-2"
    controls = {
        "subtract": ("set! a 3\nset! b 2\nsub! a b a", ""),
        "divide": ("set! a -3\nset! b 2\ndiv! a b a", ""),
        "zero": ("set! a 3\nset! b 0\ndiv! a b a", ""),
        "unset": ("out! a", ""),
        "copy": ("set! a 3\nset! b a", ""),
        "input": ("in! a", "5"),
        "syntax": ("out! 1", "unread"),
        "say": ("say!  x", ""),
        "offset": ("  say! x", ""),
        "posthalt": ("say! x", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                super().__init__(
                    code.replace("out! 1", "say! x") if self.mode == "syntax" else code,
                    io,
                )
                if self.mode == "unset":
                    self.state = (0,) * len(self.state)
                elif self.mode == "offset":
                    self.offsets = (0,) * len(self.offsets)

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                name, slots, _ = self.program[self.cursor]
                before, cursor = self.state, self.cursor
                if self.mode == "zero" and name == "div!":
                    changed = list(before)
                    changed[slots[-1]] = 0
                    self.state, self.cursor = tuple(changed), cursor + 1
                    return
                super().step()
                changed = list(self.state)
                if self.mode == "subtract" and name == "sub!":
                    changed[slots[-1]] *= -1
                elif self.mode == "divide" and name == "div!":
                    changed[slots[-1]] = -1
                elif self.mode == "copy" and name == "set!" and len(slots) == 2:
                    changed[slots[0]] = 0
                elif self.mode == "input" and name == "in!":
                    changed[slots[0]] += 1
                elif self.mode == "say" and name == "say!":
                    self.io.print_str("\n")
                self.state = tuple(changed)

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    check_erasures(_WORKSPACE, _agrees, _Machine, "set! a 1\nout! a", "")
    return len(results), len(controls) + 3
