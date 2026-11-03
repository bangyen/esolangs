"""Trit-by-trit reference with an independently filled memory image."""

from functools import cache

import pytest

from esolangs.languages.malbolge.interpreter import _Machine
from tests.interpreters.oracle_support import observed

_OPS = {
    4: "jump",
    5: "out",
    23: "in",
    39: "rotate",
    40: "seek",
    62: "mix",
    68: "pass",
    81: "stop",
}
_CIPHER = (
    "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1C"
    "B6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
)
_WORDS = 59049


@cache
def _mix(left, right):
    value = 0
    for place in range(10):
        left, x = divmod(left, 3)
        right, y = divmod(right, 3)
        value += int(("100", "102", "221")[y][x]) * 3**place
    return value


@cache
def _image(code):
    memory = [ord(c) for c in code if not c.isspace()]
    if any(
        not 33 <= word <= 126 or (word + i) % 94 not in _OPS
        for i, word in enumerate(memory)
    ):
        raise ValueError
    previous, last = [0, 0, *memory][-2:]
    for _ in range(len(memory), _WORDS):
        previous, last = last, _mix(last, previous)
        memory.append(last)
    return tuple(memory)


def _projection(a, c, d, halted, memory):
    addresses = sorted({0, 1, 2, c, d, 59048, (c - 1) % _WORDS, (d - 1) % _WORDS})
    return a, c, d, halted, tuple(memory[address] for address in addresses)


def _model(code, stdin):
    try:
        memory = list(_image(code))
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    a = c = d = cursor = 0
    output = ""
    halted = False
    trace = []
    for _ in range(129):
        trace.append(
            (_projection(a, c, d, halted, memory), halted, output, cursor, cursor)
        )
        if halted:
            return None, trace + [trace[-1]] * 3
        word = memory[c]
        operation = _OPS.get((word + c) % 94)
        if not 33 <= word <= 126 or operation == "stop":
            halted = True
            continue
        match operation:
            case "jump":
                c = memory[d]
            case "seek":
                d = memory[d]
            case "rotate":
                low = memory[d] % 3
                a = memory[d] = low * 19683 + memory[d] // 3
            case "mix":
                a = memory[d] = _mix(a, memory[d])
            case "in":
                a = ord(stdin[cursor]) if cursor < len(stdin) else 59048
                cursor += cursor < len(stdin)
            case "out":
                output += chr(a % 256)
        word = memory[c]
        if 33 <= word <= 126:
            memory[c] = ord(_CIPHER[word - 33])
        c, d = (c + 1) % _WORDS, (d + 1) % _WORDS
    return None, trace


def check_raw_malbolge(hello, cat):
    def compare(factory, code, stdin):
        def state(machine):
            return _projection(*machine.state, machine.memory)

        assert observed(factory, code, stdin, state, cap=128) == _model(code, stdin), (
            code
        )

    # Encode each legal first instruction followed by a stop.
    corpus = [chr((op - 33) % 94 + 33) + "P" for op in _OPS]
    for code in [*corpus, hello, cat, " ", "?", "é"]:
        for stdin in ("", "Hi!"):
            compare(_Machine, code, stdin)

    # Output masks the accumulator, but input must retain the full code point.
    compare(_Machine, "ubO", "Ā")

    class WrongCipher(_Machine):
        def step(self):
            if not self.halted:
                address = self.state[1]
                super().step()
                self.memory[address] = 0

    with pytest.raises(AssertionError):
        compare(WrongCipher, "DP", "")
