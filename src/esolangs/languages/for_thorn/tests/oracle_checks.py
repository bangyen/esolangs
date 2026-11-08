"""Imperative frame/stack model of Forþ, wiki revision 189084.

https://esolangs.org/wiki/For%C3%BE. Arithmetic, all three bracket forms,
mutable scopes, line input and Unicode output, bounded to 96 steps. The
public contract supplies unspecified error, EOF and framing choices.
"""

from itertools import product

import pytest

from esolangs.languages.for_thorn.interpreter import _Machine
from tests.interpreters.oracle_support import decorate_io, overread, stalled
from tests.interpreters.semantic_oracles import signed32 as _wrap
from tests.support import workspace_oracle as workspace
from tests.support.model_input import matching_delimiter

_WORKSPACE = workspace.workspace_model(
    "for-thorn-v1", "stack scopes frames input_cursor input_reads"
)


def _number(value):
    digits = format(abs(value), "X")
    code = digits[0] + "".join("F1+*" + c + "+" for c in digits[1:])
    return "0" + code + "-" if value < 0 else code


def _math(command, left, right):
    if command == "+":
        return _wrap(left + right)
    if command == "-":
        return _wrap(left - right)
    if command == "*":
        return _wrap(left * right)
    quotient = abs(left) // abs(right) * (-1 if (left < 0) != (right < 0) else 1)
    return _wrap(quotient if command == "/" else left - right * quotient)


def _finish(frames, stack):
    frames = list(frames)
    while frames and frames[-1][1] == len(frames[-1][0]):
        code, _, loop = frames[-1]
        if loop and stack[-1]:
            frames[-1] = (code, 0, loop)
            break
        frames.pop()
    return frames


def _body(code, start):
    opener = code[start]
    closer = {"(": ")", "[": "]", "{": "}"}[opener]
    span = matching_delimiter(code[start + 1 :], opener, closer)
    return None if span is None else (code[start + 1 : start + span], start + span + 1)


def _operator(command, stack):
    if command in "+-*/%v":
        if len(stack) < 2:
            return False
        right, left = stack.pop(), stack.pop()
        if command == "v":
            stack.extend((right, left))
        else:
            if command in "/%" and right == 0:
                return False
            stack.append(_math(command, left, right))
    elif command == ":":
        stack.append(stack[-1])
    elif command == "~":
        stack[-1] = ~stack[-1]
    elif command == ".":
        stack.pop()
    elif command == "o":
        stack.reverse()
    elif command == "c":
        if len(stack) < 3:
            return False
        a, b, c = stack[-3:]
        stack[-3:] = b, c, a
    return True


def _bracket(command, found, stack, table, frames):
    if found is None:
        return True
    if command == "{":
        table[stack[-1]] = found[0]
    elif stack[-1]:
        frames.append((found[0], 0, command == "["))
    return False


def _model(source, stdin):
    stack, table, frames, trace = [], {}, [(source, 0, False)], []
    cursor = progress = reads = 0
    output, error = "", False

    def row():
        state = (
            tuple(stack),
            tuple(sorted(table.items())),
            tuple(frames),
            error,
            reads,
        )
        return state, not frames, output, cursor, progress

    for tick in range(97):
        trace.append(row())
        if not frames:
            return None, trace + [row()] * 3
        if tick == 96:
            break
        try:
            finalized = _finish(frames, stack)
        except IndexError:
            return "halt", [*trace, row()]
        frames = finalized
        if not frames:
            continue
        code, pc, loop = frames[-1]
        if pc == len(code):
            continue
        command = code[pc]
        found = _body(code, pc) if command in "([{" else None
        end = found[1] if found else len(code) if command in "([{" else pc + 1
        frames[-1] = code, end, loop
        abort = False
        try:
            if command in "0123456789ABCDEF":
                stack.append(int(command, 16))
            elif command == ",":
                if cursor == len(stdin):
                    return "input", [*trace, row()]
                stop = stdin.find("\n", cursor)
                stop = len(stdin) if stop < 0 else stop + 1
                text = stdin[cursor:stop].removesuffix("\n").removesuffix("\r")
                progress += max(1, stop - cursor)
                cursor, reads = stop, reads + 1
                stack.extend(map(ord, text))
            elif command == ".":
                value = stack[-1]
                point = (
                    value
                    if 0 <= value <= 0x10FFFF and not 0xD800 <= value <= 0xDFFF
                    else value % 256
                )
                output += chr(point)
                stack.pop()
            elif command in "([{":
                abort = _bracket(command, found, stack, table, frames)
            elif command == ";":
                frames.append((table.get(stack.pop(), ""), 0, False))
            else:
                abort = not _operator(command, stack)
        except IndexError:
            return "halt", [*trace, row()]
        if abort:
            top = len(frames) == 1
            code, _, loop = frames[-1]
            frames[-1] = code, len(code), loop
            try:
                frames = _finish(frames, stack)
            except IndexError:
                return "halt", [*trace, row()]
            error = error or top
            if error:
                return "halt", [*trace, row()]
    return None, trace


def _parts(row):
    stack, scopes, frames, _error, reads = row[0]
    return stack, frozenset(scopes), frames, row[-1], reads


def _check(factory, code, stdin="unused"):
    workspace.agrees(
        _model(code, stdin),
        (factory, code, stdin),
        (_WORKSPACE, _parts),
        lambda m: (
            m.stack,
            tuple(sorted(m.table.items())),
            tuple((f.code, f.pc, f.loop) for f in m.frames),
            m.error,
            m._input_reads,
        ),
        cap=96,
    )


def check_raw_for_thorn():
    for left, right, command in product(
        (-7, 0, 3, 15, 65536, 2**31 - 1), (-2, 0, 5), "+-*/%v"
    ):
        _check(_Machine, _number(left) + _number(right) + command + ":.")
    for prefix, command in product(
        ("", "1", "12", "123"),
        (":", "~", ".", "o", "c", "v", "+", "/", "%", "(", "[", "{", ";"),
    ):
        _check(_Machine, prefix + command)
    for code in (
        "0(12+.)",
        "1(12+.)",
        "0[]",
        "1[]",
        "3[.0]",
        "1{23+.}1;",
        "1{23+.}1{4.}1;",
        "1{0/}1;2.",
        "1{1;}1;",
        "0;",
        "0(1[2.])",
    ):
        _check(_Machine, code)
    for code, stdin in product(
        (",", "0,.[.]", "0,o[.]", ",,"), ("", "abc\n", "λ\r\nmore", "\n", "Ā")
    ):
        _check(_Machine, code, stdin)
    for value in (0xD7FF, 0xD800, 0xDFFF, 0xE000, 0x10FFFF, 0x110000, -1):
        _check(_Machine, _number(value) + ".")
    for code in (
        "09/~.",
        "65v..",
        "0F7*0+F4*C+[.]",
        "0[F.]5.",
        "123o...",
        "0G.",
        "X5.",
        "1;",
        "1(5:).",
        "1((5.))",
        "1{3[:1-]A.}1;",
        "1{/}1;",
        "23+.",
        "95-.",
        "28*.",
        "1{**.}FFF1;",
        "1(F4*5+.)",
        "0(F4*5+.)",
        "123ccc...",
        "12c",
        "1{65.}1;",
        "1{F4*5+.}1;",
        "a5.",
        "65a.",
        "(5",
        "[",
        "1{.};",
    ):
        _check(_Machine, code)
    for a, b, op in product((0, 1, 7, 15), (0, 2, 11, 15), "+-*"):
        _check(_Machine, f"1{{{op}.}}{a:X}{b:X}1;{b:X}{a:X}1;")
    for code, stdin in ((",..", "hi"), (",68*-.", "0"), (",.", "Ā"), ("F1+:*.", "")):
        _check(_Machine, code, stdin)
    _check(_Machine, "")

    wrong_output = decorate_io(
        _Machine, "print_char", lambda write: lambda c: write(c + "!")
    )

    for factory, code in (
        (stalled(_Machine), "12+"),
        (wrong_output, "1."),
        (overread(_Machine), ","),
    ):
        with pytest.raises(AssertionError):
            _check(factory, code, "ab")

    workspace.check_erasures(_WORKSPACE, _check, _Machine, "1{2},", "A")
