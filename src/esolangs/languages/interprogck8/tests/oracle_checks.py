"""Independent line/call-stack Interprogck8 model, capped at 48 instructions.

https://esolangs.org/wiki/Interprogck8, revision 72769, memory and commands.
Arithmetic, dice, input, function capture/calls, conditional calls, skip and
restart. Random commands stay in raw tests; dialect choices are explicit.
"""

from dataclasses import replace
from itertools import product

import pytest

from esolangs.languages.interprogck8.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread, stalled


class _Port:
    def __init__(self, stdin):
        self.stdin, self.cursor = stdin, 0

    def line(self):
        if self.cursor == len(self.stdin):
            raise EOFError
        end = self.stdin.find("\n", self.cursor)
        stop = len(self.stdin) if end < 0 else end + 1
        text = self.stdin[self.cursor : stop].removesuffix("\n").removesuffix("\r")
        self.cursor = stop
        if not text:
            raise ArithmeticError("empty input")
        return text


def _pips(text):
    if not text or any(c not in ":." for c in text):
        raise ArithmeticError("dice literal")
    return sum(1 if c == "." else 2 for c in text)


def _argument(text, acc, port):
    if not text:
        return acc
    if text == "u":
        return ord(port.line()[0])
    if text == "$py":
        return _pips(port.line())
    return _pips(text)


def _basic(command, acc, port):
    if command in ("@nd", "@nt", "@id", "@dd"):
        magnitude = 1 if command[1] == "n" else 10
        return (
            acc + magnitude * (1 if command[-1] == "d" and command != "@dd" else -1)
        ) % 256, ""
    if command in ("NnNn", "nNnN", "Empty_"):
        return {"NnNn": 0, "nNnN": 65, "Empty_": 32}[command], ""
    if command in ("u", "$py"):
        return _argument(command, acc, port) % 256, ""
    if command == "div":
        return acc, chr(acc)
    if command == "$ay":
        quotient, remainder = divmod(acc, 2)
        return acc, ":" * quotient + "." * remainder
    if command.startswith("{values/=") and command.endswith("}"):
        arguments = command[len("{values/=") : -1].split("/=")
        if len(arguments) != 3:
            raise ArithmeticError("arguments")
        values = [_argument(text, acc, port) for text in arguments]
        return (81 if len(set(values)) == 1 else 84), ""
    if command == "Instruction26":
        return acc, chr(acc).join(map(str, range(1, 27)))
    if command in ("X", "x", "mathroundtofloor", ">"):
        return acc, ""
    assert command != "~", "random command outside model"
    assert not command.startswith("["), "random command outside model"
    raise ArithmeticError("instruction")


def _after(ip, frames):
    if not frames:
        return ip + 1, []
    frames = list(frames)
    body, index = frames[-1]
    frames[-1] = body, index + 1
    while frames and frames[-1][1] == len(frames[-1][0]):
        frames.pop()
    return ip, frames


def _control(command, lines, ip, acc, slot, frames):
    if command == "z":
        if frames or ip == 0:
            raise ArithmeticError("restart")
        return lines[: ip - 1] + lines[ip + 1 :], 0, 0, None, []
    if command == "<":
        if frames:
            raise ArithmeticError("nested capture")
        end = ip + 1
        while end < len(lines) and lines[end] not in ("<", ">"):
            end += 1
        if end == len(lines) or lines[end] != ">":
            raise ArithmeticError("unclosed capture")
        return lines, end + 1, acc, lines[ip + 1 : end], []
    if command == "DownAccLines":
        target = ip + 1 + acc
        if frames or target > len(lines):
            raise ArithmeticError("skip")
        return lines, target, acc, slot, frames
    should_call = (
        command == "EXE"
        or (command == "IFT" and acc == 84)
        or (command == "IFQ" and acc == 81)
    )
    if should_call and slot is None:
        raise ArithmeticError("missing function")
    ip, frames = _after(ip, frames)
    if should_call and slot:
        frames.append((slot, 0))
    return lines, ip, acc, slot, frames


def _model(source, stdin):
    lines, ip, acc, slot, frames = tuple(source), 0, 0, None, []
    port, output, trace = _Port(stdin), "", []

    def row():
        state = lines, ip, acc, slot, tuple(frames)
        return state, not frames and ip >= len(lines), output, port.cursor, port.cursor

    for tick in range(49):
        trace.append(row())
        if not frames and ip >= len(lines):
            return None, trace + [row()] * 3
        if tick == 48:
            break
        command = frames[-1][0][frames[-1][1]] if frames else lines[ip]
        try:
            if command in ("<", "EXE", "IFT", "IFQ", "z", "DownAccLines"):
                lines, ip, acc, slot, frames = _control(
                    command, lines, ip, acc, slot, frames
                )
            else:
                acc, text = _basic(command, acc, port)
                output += text
                ip, frames = _after(ip, frames)
        except EOFError:
            return "input", [*trace, row()]
        except ArithmeticError:
            return "halt", [*trace, row()]
    return None, trace


def _view(machine):
    state = machine.state
    return state.lines, state.ip, state.acc, state.slot, state.frames


def _check(factory, source, stdin="unused"):
    assert observed(factory, list(source), stdin, _view, cap=48) == _model(
        source, stdin
    ), (source, stdin)


def check_raw_interprogck8():
    commands = (
        "@nd",
        "@nt",
        "@id",
        "@dd",
        "NnNn",
        "nNnN",
        "Empty_",
        "X",
        "x",
        "mathroundtofloor",
        ">",
        "div",
        "$ay",
        "Instruction26",
        "unknown",
        "",
    )
    for first, second in product(commands, repeat=2):
        _check(_Machine, (first, second, "div", "$ay"))
    for command, stdin in product(
        ("u", "$py"), ("", "\n", "A\nB", "λ", ":::.", "bad", ":" * 129, ":\r\n.")
    ):
        _check(_Machine, (command, "$ay", "div", command), stdin)
    for value in (255, 256, 258, 337, 340, 955):
        literal = ":" * (value // 2) + "." * (value % 2)
        for command, data in (("u", chr(value)), ("$py", literal)):
            _check(
                _Machine, (f"{{values/={command}/={literal}/={literal}}}", "div"), data
            )
            _check(
                _Machine, (command, "DownAccLines", *["X"] * (value % 256), "div"), data
            )
            call = "IFT" if value % 256 == 84 else "IFQ"
            _check(_Machine, ("<", "div", ">", command, call), data)
    for left, middle, right in product(("", ".", ":", "u", "$py"), repeat=3):
        _check(
            _Machine,
            ("{values/=" + left + "/=" + middle + "/=" + right + "}", "div"),
            ".\nA\n:\n",
        )
    for call, body in product(
        ("EXE", "IFT", "IFQ"),
        ((), ("@nd", "div"), ("EXE",), ("<",), ("z",), ("DownAccLines",)),
    ):
        _check(_Machine, ("<", *body, ">", call, "div"))
    for source in (
        (),
        ("z",),
        ("X", "z"),
        ("@nd", "z", "div"),
        ("@nd", "DownAccLines", "unknown", "div"),
        ("@id", "DownAccLines"),
        ("EXE",),
        ("<",),
        ("<", "<", ">"),
        ("NnNn", "{values/=./=./=}", "<", "@nd", "div", ">", "IFT"),
    ):
        _check(_Machine, source)

    class WrongAccumulator(_Machine):
        def step(self):
            super().step()
            self.state = replace(self.state, acc=(self.state.acc + 1) % 256)

    for factory in (stalled(_Machine), WrongAccumulator, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, ("@nd", "div"))
