"""Revision 95947 BASICER, using labeled instruction maps and line input."""

import itertools
import random
import re

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.basicer.interpreter import _Machine
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model("basicer-v1", "instruction input_cursor")


def _instruction(body):
    match = re.fullmatch(r"(CLEAR|PAUSE|PRINT|PLOT|GOTO)(?: (.*))?", body)
    if match is None:
        raise ValueError
    command, operand = match.groups()
    operand = operand or ""
    if command in ("CLEAR", "PAUSE"):
        if operand:
            raise ValueError
    elif command == "GOTO":
        if not operand or any(not word.isdigit() for word in operand.split()):
            raise ValueError
        operand = tuple(map(int, operand.split()))
    elif command == "PLOT":
        fields = operand.split(" ")
        if len(fields) != 3:
            raise ValueError
        x, y, color = fields
        if (
            not all(1 <= len(v) <= 2 and v.isdecimal() for v in (x, y))
            or len(color) != 7
            or color[0] != "#"
            or any(c not in "0123456789abcdefABCDEF" for c in color[1:])
        ):
            raise ValueError
    return command, operand


def _parse(source):
    rows = [row.strip() for row in source.split("\n") if row.strip()]
    flags = [row.partition(" ")[0].isdigit() for row in rows]
    if flags and any(flags) != all(flags):
        raise ValueError
    instructions = {}
    for ordinal, row in enumerate(rows, 1):
        if flags and flags[0]:
            number, _, body = row.partition(" ")
            number = int(number)
        else:
            number, body = ordinal, row
        if number in instructions:
            raise ValueError
        instructions[number] = _instruction(body)
    return instructions


def _line(stdin, at):
    if at == len(stdin):
        return None, at, 0
    end = stdin.find("\n", at)
    stop = len(stdin) if end < 0 else end + 1
    line = stdin[at : len(stdin) if end < 0 else end].removesuffix("\r")
    return line, stop, max(1, len(line), stop - at)


def _model(source, stdin):
    try:
        instructions = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    labels = sorted(instructions)
    pc, at, progress, output, error = 0, 0, 0, "", None

    def view():
        return (pc, pc == len(labels), output, at, progress)

    trace = [view()]
    for _ in range(64):
        if pc == len(labels):
            break
        command, operand = instructions[labels[pc]]
        next_pc = pc + 1
        if command == "PRINT":
            output += operand + "\n"
        elif command == "GOTO":
            choice = 1
            if len(operand) > 1:
                raw, at, consumed = _line(stdin, at)
                progress += consumed
                if raw is None:
                    error = "input"
                else:
                    token = raw.strip()
                    if not token.lstrip("-").isdigit():
                        error = "argument"
                    else:
                        try:
                            choice = int(token)
                        except ValueError:
                            error = "syntax"
                        else:
                            if not 1 <= choice <= len(operand):
                                error = "halt"
            if not error:
                label = operand[choice - 1]
                next_pc = labels.index(label) if label in instructions else len(labels)
        if not error:
            pc = next_pc
        trace.append(view())
        if error:
            break
    if pc == len(labels) and not error:
        trace.extend([view()] * 3)
    return error, trace


def _agrees(factory, source, stdin):
    return workspace.agrees(
        _model(source, stdin),
        (factory, source, stdin),
        (_WORKSPACE, lambda row: (row[0], row[-1])),
        lambda m: m.ind,
    )


def check_raw_basicer():
    atoms = (
        "PRINT x",
        "PRINT",
        "PRINT  y",
        "CLEAR",
        "PAUSE",
        "PLOT 99 0 #Ab001f",
        "GOTO 1",
        "GOTO 2 4",
        "GOTO 99",
    )
    corpus = [
        "\n".join(p) for n in range(3) for p in itertools.product(atoms, repeat=n)
    ]
    rng = random.Random(20261103)
    for _ in range(128):
        rows = [(i * 10, rng.choice(atoms)) for i in range(1, 5)]
        rng.shuffle(rows)
        corpus.append("\n\n".join(f"{label} {text}" for label, text in rows))
    corpus += [
        "20 PRINT b\n10 PRINT a",
        "0 GOTO 0",
        "10 GOTO 30 20\n20 PRINT no\n30 PRINT yes",
        "PRINT λ",
        "GOTO 2 99\nPRINT x\nGOTO 1",
        "PRINT x\n" * 80,
        "PLOT \u0661 \uff12 #aBc123",
        "\u0661 PRINT x",
    ]
    inputs = ("", "1\n2\n", " 2\r\n1\n", "0\n", "x\n", "+1\n", "--1\n", "²\n")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    results.append(_agrees(_Machine, "GOTO 2 3 4\nPRINT a\nPRINT b\nPRINT c", "3\n"))
    invalid = (
        "PRINT\tx",
        "clear",
        "PLOT 100 0 #000000",
        "PLOT 1  2 #000000",
        "PLOT -1 0 #000000",
        "PLOT 1 0 #GGGGGG",
        "CLEAR x",
        "PAUSE x",
        "GOTO",
        "GOTO -1",
        "GOTO ²",
        "1 PRINT x\nPRINT y",
        "1 PRINT x\n1 PAUSE",
        "1  PRINT x",
        "² PRINT x",
    )
    results += [_agrees(_Machine, code, "1\n") for code in invalid]
    assert {error for error, _ in results} == {
        None,
        "syntax",
        "input",
        "argument",
        "halt",
    }
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("20 PRINT b\n10 PRINT a", "")[1][-1][2] == "a\nb\n"
    controls = {
        "order": ("20 PRINT b\n10 PRINT a", ""),
        "missing": ("GOTO 99", ""),
        "choice": ("GOTO 2 3\nPRINT a\nPRINT b", "2\n"),
        "range": ("GOTO 2 3", "0\n"),
        "pause": ("PAUSE", "unused"),
        "clear": ("PRINT a\nCLEAR", ""),
        "print": ("PRINT a", ""),
        "plot": ("PLOT 100 0 #000000", ""),
        "syntax": ("clear", ""),
        "cursor": ("GOTO 2 3", "1\nextra"),
        "posthalt": ("", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "range":
                    io.input_str = lambda: "1"
                elif self.mode == "choice":
                    read = io.input_str
                    io.input_str = lambda: str(3 - int(read()))
                elif self.mode == "cursor":
                    read = io.input_str

                    def consume_extra():
                        text = read()
                        io.input_char()
                        return text

                    io.input_str = consume_extra
                if self.mode == "plot":
                    code = code.replace("100", "99")
                super().__init__(code.upper() if self.mode == "syntax" else code, io)
                if self.mode == "order":
                    self.lines = tuple(reversed(self.lines))

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                command = self.lines[self.ind].op
                if self.mode == "pause" and command == "PAUSE":
                    self.io.input_char()
                if self.mode == "missing" and command == "GOTO":
                    raise HaltError("missing line treated as an error")
                super().step()
                if self.mode == "print" and command == "PRINT":
                    self.io.print_str("extra")
                elif self.mode == "clear" and command == "CLEAR":
                    self.io.print_str("erase")

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    workspace.check_erasures(_WORKSPACE, _agrees, _Machine, "PRINT x", "")
    return len(results), len(controls) + 2
