"""Independent stack/frame model of Grapheme's modes and command table.

https://esolangs.org/wiki/Grapheme. Both public integer dialects, strings,
variables, arithmetic, calls and literal flushes, bounded to 64 commands.
Tracks deferred X skips and clamps negative V counts to zero.
"""

from decimal import Decimal
from itertools import product

import pytest

from esolangs.languages.grapheme.interpreter import _Machine
from esolangs.runtime._state import WorkspaceSnapshot
from tests.interpreters.oracle_support import overread, stalled
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "grapheme-v1", "stack variables frames input_cursor input_reads"
)


def _integer(text, dialect):
    value = 0
    for c in text:
        if c == "F":
            break
        value = value * 10 + (0 if c == "Z" else ord(c) - ord("A") + 1)
    return value * (10 if dialect == "after_each_letter" else 1)


def _truth(value):
    return bool(value[1]) if isinstance(value, tuple) else bool(value)


def _number(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return ord(value[0]) if value else 0
    raise ValueError("halt")


def _to_int(value, dialect):
    if isinstance(value, int):
        return value
    if isinstance(value, tuple):
        return len(value[1])
    return _integer(value, dialect)


def _literal(mode, text, dialect):
    if mode == "int":
        return _integer(text, dialect)
    if mode == "func":
        return ("func", text)
    return text


def _data(command, stack, variables, dialect):
    if command in "ABRS":
        a, b = _number(stack.pop()), _number(stack.pop())
        if command == "A":
            value = a + b
        elif command == "B":
            value = a - b
        elif command == "R":
            value = a // b
        else:
            value = a * b
        stack.append(value)
    elif command == "C":
        name, value = stack.pop(), stack.pop()
        variables[name] = value
    elif command == "D":
        name = stack.pop()
        stack.append(variables.get(name, name))
    elif command == "J":
        stack.append(_to_int(stack.pop(), dialect))
    elif command == "K":
        value = stack.pop()
        stack.extend((value, value))
    elif command == "L":
        a, b = stack.pop(), stack.pop()
        stack.extend((a, b))
    elif command == "M":
        stack.pop()
    elif command == "N":
        value = stack.pop()
        if isinstance(value, tuple):
            value = value[1]
        elif isinstance(value, int):
            if value < 0:
                raise ValueError("halt")
            digits = format(Decimal(value), "f")
            value = "".join(chr(ord("A") + (int(c) - 1) % 10) for c in digits)
        stack.append(value)
    elif command == "O":
        value = stack.pop()
        stack.append(len(value) if isinstance(value, str) else value)
    elif command == "P":
        stack.reverse()
    elif command == "T":
        stack.append(int(not _truth(stack.pop())))
    else:
        value = stack.pop()
        if isinstance(value, tuple):
            raise ValueError("halt")
        return value
    return None


def _control(command, stack, dialect, pc, pending):
    skip, body, repeat = 0, None, False
    if command == "G":
        value = stack.pop()
        body = value[1] if isinstance(value, tuple) else value
        if not isinstance(body, str):
            raise ValueError("halt")
    elif command == "I":
        value = stack.pop()
        if isinstance(value, tuple):
            body = value[1]
        else:
            stack.append(value)
    elif command == "Q":
        value, condition = stack.pop(), stack.pop()
        if isinstance(value, tuple) and _truth(condition):
            body = value[1]
    elif command == "Z":
        value = stack.pop()
        if isinstance(value, tuple) and stack:
            body, repeat = value[1], True
    elif command == "U":
        skip = int(not _truth(stack.pop()))
    elif command == "V":
        a, b = stack.pop(), stack.pop()
        if not _truth(a):
            skip = max(0, _to_int(b, dialect))
    elif command == "X":
        skip = 0 if _truth(stack.pop()) else 1
        if not skip:
            pending = pc
    else:
        raise ValueError("syntax")
    return skip, body, repeat, pending


def _finish(frames, stack, dialect):
    while frames and frames[-1][1] >= len(frames[-1][0]):
        code, _, mode, buf, _, repeat = frames.pop()
        if mode:
            stack.append(_literal(mode, "".join(buf), dialect))
        if repeat and stack:
            frames.append((code, 0, "", (), -1, repeat))
            break


def _model(source, stdin, dialect):
    frames, stack, variables = [(source, 0, "", (), -1, False)], [], {}
    output, trace = "", []
    cursor = progress = reads = 0

    def row():
        state = tuple(stack), frozenset(variables.items()), tuple(frames), reads
        return state, not frames, output, cursor, progress

    for tick in range(65):
        trace.append(row())
        if not frames:
            return None, trace + [row()] * 3
        if tick == 64:
            break
        code, pc, mode, buf, pending, repeat = frames[-1]
        if pc >= len(code):
            _finish(frames, stack, dialect)
            continue
        command = code[pc]
        if mode:
            if command == {"string": "E", "int": "F", "func": "H"}[mode]:
                stack.append(_literal(mode, "".join(buf), dialect))
                mode, buf = "", ()
            else:
                buf = (*buf, command)
            frames[-1] = code, pc + 1, mode, buf, pending, repeat
            continue
        line = None
        if command == "W":
            if cursor == len(stdin):
                return "input", [*trace, row()]
            stop = stdin.find("\n", cursor)
            stop = len(stdin) if stop < 0 else stop + 1
            line = stdin[cursor:stop].removesuffix("\n").removesuffix("\r")
            progress += max(1, stop - cursor)
            cursor, reads = stop, reads + 1
        changed, memory, calls = stack.copy(), variables.copy(), frames.copy()
        body, call_repeat, skip, text = None, False, 0, None
        try:
            if command in "EFH":
                mode, buf = {"E": "string", "F": "int", "H": "func"}[command], ()
            elif command == "W":
                changed.append(line)
            elif command in "ABCDJKLMNOPRSTY":
                text = _data(command, changed, memory, dialect)
            else:
                skip, body, call_repeat, pending = _control(
                    command, changed, dialect, pc, pending
                )
        except (IndexError, ZeroDivisionError):
            return "halt", [*trace, row()]
        except ValueError as error:
            return str(error), [*trace, row()]
        destination = pc + 1 + skip
        if pending >= 0 and destination == pending + 2:
            destination, pending = destination + 1, -1
        calls[-1] = code, destination, mode, buf, pending, repeat
        if body is not None:
            calls.append((body, 0, "", (), -1, call_repeat))
        _finish(calls, changed, dialect)
        stack, variables, frames = changed, memory, calls
        if text is not None:
            try:
                output += str(text)
            except ValueError:
                return "syntax", [*trace, row()]
    return None, trace


def _check(factory, code, stdin="unused", dialect="between_letters"):
    normalized = code.replace("\n", "")

    def build(source, io):
        return factory(source, io, integer_conversion=dialect)

    def state(machine):
        return (
            tuple(machine.stack),
            frozenset(machine.vars.items()),
            machine.frames,
            machine._input_reads,
        )

    workspace.agrees(
        _model(normalized, stdin, dialect)
        if all("A" <= c <= "Z" for c in normalized)
        else ("syntax", [(None, False, "", 0, 0)]),
        (build, code, stdin),
        (_WORKSPACE, lambda row: (row[0][0], row[0][1], row[0][2], row[-1], row[0][3])),
        state,
        cap=64,
        context=(code, stdin, dialect),
    )


def check_raw_grapheme():
    for dialect, left, right, operation in product(
        ("between_letters", "after_each_letter"),
        ("", "A", "Z", "J", "AZ"),
        ("", "A", "B", "Z"),
        "ABRS",
    ):
        _check(
            _Machine,
            "F" + left + "FF" + right + "F" + operation + "KY",
            dialect=dialect,
        )
    for prefix, command in product(
        ("", "FAF", "FAFFBF", "EABE", "HH"), "CDEIJKLMNOPQRTUVYZ"
    ):
        _check(_Machine, prefix + command)
    for dialect, code in product(
        ("between_letters", "after_each_letter"),
        (
            "EAZEJY",
            "FAFNJY",
            "FAFEKEYCFAFEKEYDY",
            "HFAFYHI",
            "FAFHFAFYHQ",
            "HFAFYHIG",
            "EFAFYE G".replace(" ", ""),
            "HHM",
            "FAFHHZ",
            "EAB",
            "FZ",
            "HFAFY",
        ),
    ):
        _check(_Machine, code, dialect=dialect)
    for code, stdin in product(
        ("WY", "WWLYY", "EWEY", "WGY"), ("", "λ\r\nmore", "ABC\n", "FAFY", "\n")
    ):
        _check(_Machine, code, stdin)
    for code in ("", "FA\nFY", "a", " ", "\r", "EbadE"):
        _check(_Machine, code)

    class WrongOutput(_Machine):
        def __init__(self, code, io, **kwargs):
            write = io.print_value
            io.print_value = lambda n: write(n + 1)
            super().__init__(code, io, **kwargs)

    for factory, code in (
        (stalled(_Machine), "FAFY"),
        (WrongOutput, "FAFY"),
        (overread(_Machine), "WY"),
    ):
        with pytest.raises(AssertionError):
            _check(factory, code, "ab")
    workspace.check_erasures(_WORKSPACE, _check, _Machine, "I")

    for dialect, code in product(
        ("between_letters", "after_each_letter"),
        (
            "FAFFFXKY",
            "FAFFBFFCFXYKY",
            "FAFFBFHXYKHI",
            "FAFFZFBFZFVFAFY",
            "FAFXEABEY",
            "FAFKKXXKMY",
            "FZFFAFXXKFAFY",
        ),
    ):
        _check(_Machine, code, dialect=dialect)
    _check(_Machine, "WEKECEKEDY", "A\nremaining")
    _check(_Machine, "WJY", "A" * 5000)
    _check(_Machine, "WJNY", "A" * 5000)
    workspace.check_erasures(_WORKSPACE, _check, _Machine, "WEKECEKEDY", "A\nremaining")

    class NoPending(_Machine):
        def workspace_snapshot(self):
            saved = super().workspace_snapshot()
            parts = list(saved.parts)
            parts[2] = tuple((*frame[:4], -1, frame[5]) for frame in parts[2])
            return WorkspaceSnapshot(saved.model, tuple(parts))

    with pytest.raises(AssertionError):
        _check(NoPending, "FAFXKMY")
