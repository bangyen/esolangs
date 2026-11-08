"""List/heap model of https://esolangs.org/wiki/Whitespace command tables.

Arithmetic, stack/heap, branches/calls and mixed numeric/character I/O,
48 steps. Canonical VM.hs backs signed floor arithmetic, first-label wins
and taken-only label resolution; I/O/storage choices remain in Decisions.
Raw-source offsets are derived from this assembler, not production parsing.
"""

import re
from itertools import product

import pytest

from esolangs.languages.whitespace.interpreter import _Machine
from tests.interpreters.oracle_support import decorate_io, observed, overread, stalled

# S/T/N spell the specification's space/tab/line-feed command table.
_CODES = {
    "push": "SS",
    "dup": "SNS",
    "swap": "SNT",
    "discard": "SNN",
    "copy": "STS",
    "slide": "STN",
    "add": "TSSS",
    "sub": "TSST",
    "mul": "TSSN",
    "div": "TSTS",
    "mod": "TSTT",
    "store": "TTS",
    "retrieve": "TTT",
    "out_char": "TNSS",
    "out_num": "TNST",
    "read_char": "TNTS",
    "read_num": "TNTT",
    "mark": "NSS",
    "call": "NST",
    "jump": "NSN",
    "jz": "NTS",
    "jn": "NTT",
    "return": "NTN",
    "end": "NNN",
}


def _assemble(program):
    source, offsets = "ignored", []
    for kind, *args in program:
        token = _CODES[kind]
        if kind in {"push", "copy", "slide"}:
            value = args[0]
            token += (
                ("T" if value < 0 else "S")
                + format(abs(value), "b").translate(str.maketrans("01", "ST"))
                + "N"
            )
        elif args:
            token += args[0].translate(str.maketrans("01", "ST")) + "N"
        offsets.append(len(source))
        source += token.translate(str.maketrans("STN", " \t\n")) + "ignored"
    return source, offsets


def _rearrange(kind, args, stack):
    if kind == "dup":
        stack.append(stack[-1])
    elif kind == "swap":
        stack[-2], stack[-1] = stack[-1], stack[-2]
    elif kind == "discard":
        stack.pop()
    elif kind == "copy":
        depth = args[0]
        if not 0 <= depth < len(stack):
            raise IndexError(depth)
        stack.append(stack[-depth - 1])
    else:
        depth = args[0]
        top = stack.pop()
        for _ in range(max(0, depth)):
            if not stack:
                break
            stack.pop()
        stack.append(top)


def _math(kind, left, right):
    if kind == "add":
        return left + right
    if kind == "sub":
        return left - right
    if kind == "mul":
        return left * right
    quotient, remainder = divmod(abs(left), abs(right))
    if (left < 0) != (right < 0):
        quotient = -quotient - bool(remainder)
    return quotient if kind == "div" else left - quotient * right


def _flow(kind, args, stack, calls, labels, pc):
    if kind == "return":
        return calls.pop()
    if kind == "call":
        calls.append(pc + 1)
        return labels[args[0]]
    if kind == "jump":
        return labels[args[0]]
    value = stack.pop()
    return labels[args[0]] if (value == 0 if kind == "jz" else value < 0) else pc + 1


def _read(kind, stdin, cursor):
    if kind == "read_char":
        if cursor == len(stdin):
            return None, cursor, "input"
        return ord(stdin[cursor]), cursor + 1, None
    if cursor == len(stdin):
        return None, cursor, "input"
    end = stdin.find("\n", cursor)
    stop = len(stdin) if end < 0 else end + 1
    token = stdin[cursor : len(stdin) if end < 0 else end].strip()
    if re.fullmatch(r"[+-]?[0-9]+", token) is None:
        return None, stop, "argument"
    return int(token), stop, None


def _model(program, offsets, stdin):
    pc = cursor = 0
    stack, heap, calls, output, trace = [], {}, [], "", []
    done = False
    labels = {
        args[0]: i
        for i, (kind, *args) in reversed(tuple(enumerate(program)))
        if kind == "mark"
    }

    def row():
        halted = done or pc >= len(program)
        state = (
            pc,
            tuple(stack),
            tuple(sorted((a, n) for a, n in heap.items() if n)),
            tuple(calls),
            done,
            None if halted else offsets[pc],
        )
        return state, halted, output, cursor, cursor

    for tick in range(49):
        trace.append(row())
        if row()[1]:
            return None, trace + [row()] * 3
        if tick == 48:
            break
        kind, *args = program[pc]
        supplied = None
        if kind in {"read_char", "read_num"}:
            supplied, cursor, error = _read(kind, stdin, cursor)
            if error:
                return error, [*trace, row()]
        changed, memory, frames = stack.copy(), heap.copy(), calls.copy()
        next_pc, text = pc + 1, ""
        try:
            if kind == "push":
                changed.append(args[0])
            elif kind in {"dup", "swap", "discard", "copy", "slide"}:
                _rearrange(kind, args, changed)
            elif kind in {"add", "sub", "mul", "div", "mod"}:
                right, left = changed.pop(), changed.pop()
                changed.append(_math(kind, left, right))
            elif kind == "store":
                value, address = changed.pop(), changed.pop()
                memory[address] = value
            elif kind == "retrieve":
                changed.append(memory.get(changed.pop(), 0))
            elif kind in {"read_char", "read_num"}:
                memory[changed.pop()] = supplied
            elif kind in {"out_char", "out_num"}:
                value = changed.pop()
                text = str(value) if kind == "out_num" else chr(value)
            elif kind in {"call", "jump", "jz", "jn", "return"}:
                next_pc = _flow(kind, args, changed, frames, labels, pc)
            elif kind == "end":
                done = True
        except (IndexError, KeyError, ZeroDivisionError, ValueError, OverflowError):
            return "halt", [*trace, row()]
        stack, heap, calls, pc = changed, memory, frames, next_pc
        output += text
    return None, trace


def _check(factory, program, stdin="unused"):
    source, offsets = _assemble(program)

    def state(machine):
        pc, stack, heap, calls, done = machine.state
        return pc, stack, heap, calls, done, machine.ip

    assert observed(factory, source, stdin, state, cap=48) == _model(
        program, offsets, stdin
    ), (program, stdin)


def check_raw_whitespace():
    for address in (-(2**80), -1, 0, 17, 2**80):
        read = (("push", address), ("retrieve",), ("out_num",))
        _check(_Machine, (*read, ("end",)))
        for value in (0, 9):
            store = (("push", address), ("push", value), ("store",))
            gap = (("push", address - 1), ("retrieve",), ("out_num",))
            _check(_Machine, (*store, *gap, *read, ("end",)))
        clear = (("push", address), ("push", 0), ("store",))
        _check(_Machine, (*store, *clear, *read, ("end",)))
    for value in (-1, 0, 255, 256, 0xD800, 0xDFFF, 0x10000, 0x10FFFF, 0x110000, 2**80):
        _check(_Machine, (("push", value), ("out_char",), ("end",)))
    for address, left, right, operation in product(
        (-17, 0, 2**32 + 1),
        (-(2**80) - 1, -7, 0, 3, 256),
        (-2, 0, 5),
        ("add", "sub", "mul", "div", "mod"),
    ):
        _check(
            _Machine,
            (
                ("push", address),
                ("call", "0"),
                ("push", address),
                ("retrieve",),
                ("dup",),
                ("out_num",),
                ("out_char",),
                ("end",),
                ("mark", "0"),
                ("push", left),
                ("push", right),
                (operation,),
                ("store",),
                ("return",),
            ),
        )
    for prefix, operation in product(
        ((), (("push", 7),), (("push", 7), ("push", 9))),
        (
            ("dup",),
            ("swap",),
            ("discard",),
            ("copy", -1),
            ("copy", 0),
            ("copy", 1),
            ("slide", -1),
            ("slide", 0),
            ("slide", 1),
            ("slide", 2),
            ("slide", 100),
            ("retrieve",),
            ("return",),
            ("jump", "1"),
            ("jz", "1"),
            ("jn", "1"),
        ),
    ):
        _check(_Machine, (*prefix, operation, ("end",)))
    for value, kind in product((-1, 0, 1), ("jz", "jn")):
        _check(
            _Machine,
            (
                ("push", value),
                (kind, "0"),
                ("push", 7),
                ("mark", "0"),
                ("push", 2),
                ("out_num",),
                ("end",),
            ),
        )
    for value, kind in product((-1, 0, 1), ("jz", "jn")):
        _check(_Machine, (("push", value), (kind, "1"), ("end",)))
    _check(
        _Machine,
        (
            ("jump", "0"),
            ("mark", "0"),
            ("push", 1),
            ("mark", "0"),
            ("push", 2),
            ("out_num",),
            ("end",),
        ),
    )
    _check(_Machine, (("mark", "0"), ("jump", "0")))
    for kind, stdin in product(
        ("read_num", "read_char"),
        ("", "  -12 x", "λ\n", "2 3", "\n", "12\nQ", "-7", " \n9\n"),
    ):
        _check(
            _Machine,
            (
                ("push", 3),
                (kind,),
                ("push", 3),
                ("retrieve",),
                ("out_num",),
                ("push", 4),
                ("read_char",),
                ("push", 4),
                ("retrieve",),
                ("out_char",),
                ("end",),
            ),
            stdin,
        )
        _check(_Machine, ((kind,),), stdin)
    for source in ("", "ignored", " ", "\t", "\n\n ", "\t\t\n"):
        assert observed(_Machine, source, "", lambda m: m.state) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    for address, a, b, op in product(
        (-17, 2**32 + 17),
        (-257, -7, 0, 3, 256),
        (-11, -2, 1, 5),
        ("add", "sub", "mul", "div", "mod"),
    ):
        _check(
            _Machine,
            (
                ("push", address),
                ("call", "01"),
                ("push", address),
                ("retrieve",),
                ("dup",),
                ("out_num",),
                ("out_char",),
                ("end",),
                ("mark", "01"),
                ("push", a),
                ("push", b),
                (op,),
                ("store",),
                ("return",),
            ),
        )

    wrong_print = decorate_io(
        _Machine, "print_num", lambda write: lambda n: write(n + 1)
    )

    for factory in (stalled(_Machine), overread(_Machine), wrong_print):
        with pytest.raises(AssertionError):
            _check(factory, (("push", 1), ("out_num",), ("end",)))
