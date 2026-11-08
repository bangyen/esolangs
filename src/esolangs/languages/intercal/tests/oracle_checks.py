"""String-bit model of C-INTERCAL operators and bounded scalar programs.

https://www.catb.org/~esr/intercal/ick.htm, operators and numeric I/O.
Mingle/select/unary, widths/overflow, digit-word input and small Roman output.
Arrays, chance and control transfers remain in the existing raw suite.
"""

from dataclasses import replace
from itertools import product

import pytest

from esolangs.languages.intercal.interpreter import _Machine
from tests.interpreters.oracle_support import decorate_io, observed, overread, stalled

_WORDS = [
    "ZERO",
    "ONE",
    "TWO",
    "THREE",
    "FOUR",
    "FIVE",
    "SIX",
    "SEVEN",
    "EIGHT",
    "NINE",
]


def _expression(expr):
    if isinstance(expr, int):
        return "#" + str(expr)
    kind, *args = expr
    if kind in ".:":
        return kind + str(args[0])
    if kind == "logic":
        raw = _expression(args[1])
        if isinstance(args[1], tuple) and args[1][0] in ("$", "~"):
            return '"' + args[0] + raw + '"'
        return raw[0] + args[0] + raw[1:]
    return _expression(args[0]) + kind + _expression(args[1])


def _source(ops):
    assert len(ops) >= 3
    polite = len(ops) // 3
    lines = []
    for i, (kind, *args) in enumerate(ops):
        if kind == "set":
            text = _expression(args[0]) + " <- " + _expression(args[1])
        elif kind == "read":
            text = "WRITE IN " + _expression(args[0])
        elif kind == "print":
            text = "READ OUT " + _expression(args[0])
        else:
            text = "GIVE UP"
        lines.append(("PLEASE " if i < polite else "DO ") + text)
    return "\n".join(lines)


def _unary(operation, number, width):
    bits = format(number, f"0{width}b")
    neighbor = bits[-1] + bits[:-1]
    result = []
    for left, right in zip(bits, neighbor, strict=True):
        a, b = left == "1", right == "1"
        result.append(
            "1"
            if (a and b if operation == "&" else a or b if operation == "V" else a != b)
            else "0"
        )
    return int("".join(result), 2)


def _evaluate(expr, variables):
    if isinstance(expr, int):
        return expr, 16
    kind, *args = expr
    if kind in ".:":
        return variables.get(expr, 0), 16 if kind == "." else 32
    if kind == "logic":
        number, width = _evaluate(args[1], variables)
        return _unary(args[0], number, width), width
    left, _ = _evaluate(args[0], variables)
    right, width = _evaluate(args[1], variables)
    if kind == "$":
        if max(left, right) > 65535:
            raise ValueError("halt")
        bits = "".join(
            a + b for a, b in zip(f"{left:016b}", f"{right:016b}", strict=True)
        )
        return int(bits, 2), 32
    bits = "".join(
        a for a, b in zip(f"{left:032b}", f"{right:032b}", strict=True) if b == "1"
    )
    return int(bits or "0", 2), width


def _roman(number):
    assert 0 <= number < 4000, "large Roman formatting is outside this model"
    if not number:
        return "_\n\n"
    result = ""
    for value, symbol in (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ):
        copies, number = divmod(number, value)
        result += symbol * copies
    return result + "\n"


def _model(ops, stdin):
    variables, output, trace = {}, "", []
    pc = cursor = progress = 0

    def row():
        state = (
            pc,
            frozenset(variables.items()),
            (),
            frozenset(),
            (),
            (0,) * len(ops),
            (),
            0,
            0,
        )
        return state, pc == len(ops), output, cursor, progress

    while True:
        trace.append(row())
        if pc == len(ops):
            return None, trace + [row()] * 3
        kind, *args = ops[pc]
        try:
            if kind == "set":
                value, _ = _evaluate(args[1], variables)
                if value >= 2 ** (16 if args[0][0] == "." else 32):
                    raise ValueError("halt")
                variables[args[0]] = value
            elif kind == "read":
                if cursor == len(stdin):
                    return "input", [*trace, row()]
                stop = stdin.find("\n", cursor)
                stop = len(stdin) if stop < 0 else stop + 1
                words = stdin[cursor:stop].upper().split()
                progress += max(1, stop - cursor)
                cursor = stop
                if not words or any(word not in _WORDS for word in words):
                    raise ValueError("halt")
                value = int("".join(str(_WORDS.index(word)) for word in words))
                if value >= 2 ** (16 if args[0][0] == "." else 32):
                    raise ValueError("halt")
                variables[args[0]] = value
            elif kind == "print":
                output += _roman(_evaluate(args[0], variables)[0])
            else:
                pc = len(ops)
                continue
        except ValueError:
            return "halt", [*trace, row()]
        pc += 1


def _view(machine):
    s = machine.state
    return (
        s.ind,
        frozenset(s.scalars.items()),
        tuple(s.arrays.items()),
        s.ignored,
        tuple(s.stashes.items()),
        s.abstained,
        s.nexts,
        s.last_in,
        s.last_out,
    )


def _check(factory, ops, stdin="unused"):
    assert observed(factory, _source(ops), stdin, _view, cap=16) == _model(
        ops, stdin
    ), (ops, stdin)


def check_raw_intercal():
    for left, right, mask, operation in product(
        (0, 1, 77, 173, 32768, 65535),
        (0, 1, 77, 173, 32768, 65535),
        (0, 1, 0xAAAA, 65535),
        "&V?",
    ):
        _check(
            _Machine,
            (
                ("set", (":", 1), ("$", left, right)),
                ("set", (":", 2), ("~", (":", 1), mask)),
                ("set", (":", 3), ("logic", operation, (":", 2))),
                ("set", (".", 1), ("~", (":", 3), 255)),
                ("print", (".", 1)),
                ("halt",),
            ),
        )
    for number, operation in product((0, 1, 77, 65535), "&V?"):
        _check(
            _Machine,
            (
                ("set", (".", 1), ("logic", operation, number)),
                ("print", ("~", (".", 1), 255)),
                ("halt",),
            ),
        )
    for number, operation, wide in product((0, 1, 77, 65535), "&V?", (False, True)):
        mask = (":", 1) if wide else 65535
        _check(
            _Machine,
            (
                ("set", (":", 1), 65535),
                ("set", (":", 2), ("logic", operation, ("~", number, mask))),
                ("print", ("~", (":", 2), 255)),
                ("halt",),
            ),
        )
    for key, stdin in product(
        ((".", 1), (":", 1)),
        (
            "",
            "ZERO\n",
            "FOUR TWO\nunused",
            "one two\r\n",
            "TEN\n",
            "\n",
            "SIX FIVE FIVE THREE SIX",
            "FOUR TWO NINE FOUR NINE SIX SEVEN TWO NINE SIX",
        ),
    ):
        _check(_Machine, (("read", key), ("print", ("~", key, 255)), ("halt",)), stdin)
    for number in (1, 65535, 65536):
        words = " ".join(_WORDS[int(c)] for c in str(number))
        _check(
            _Machine,
            (
                ("read", (":", 1)),
                ("set", (":", 2), ("$", (":", 1), 1)),
                ("print", ("~", (":", 2), 255)),
                ("halt",),
            ),
            words,
        )
    _check(_Machine, (("set", (".", 1), ("$", 65535, 65535)), ("print", 0), ("halt",)))
    _check(_Machine, (("print", (".", 1)), ("print", 0), ("halt",)))
    for source in ("", "DO .1 <- #1", "PLEASE GIVE UP\nPLEASE GIVE UP\nPLEASE GIVE UP"):
        assert observed(_Machine, source, "unused", _view) == (
            "halt",
            [(None, False, "", 0, 0)],
        )

    wrong_output = decorate_io(
        _Machine, "print_str", lambda write: lambda text: write(text + "!")
    )

    ops = (("set", (".", 1), 1), ("print", (".", 1)), ("halt",))
    for factory in (stalled(_Machine), wrong_output, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, ops)

    class TruncatesWidth(_Machine):
        def step(self):
            super().step()
            value = self.state.scalars.get((":", 2), 0)
            if value > 65535:
                self.state = replace(
                    self.state, scalars=self.state.scalars.set((":", 2), value % 65536)
                )

    with pytest.raises(AssertionError):
        _check(
            TruncatesWidth,
            (
                ("set", (":", 1), 65535),
                ("set", (":", 2), ("logic", "V", ("~", 1, (":", 1)))),
                ("print", 0),
                ("halt",),
            ),
        )
