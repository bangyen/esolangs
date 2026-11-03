"""Two dictionary tapes with explicit bit queues."""

import re
from itertools import product

import pytest

from esolangs.languages.nandypants.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _pack(bits):
    return sum(bit * 2**index for index, bit in enumerate(bits))


def _model(code, stdin):
    tokens = []
    for match in re.finditer(r"\d+|.", code, re.DOTALL):
        token = match[0]
        if token.isdecimal():
            tokens.append(int(token))
        elif token in "{}<>^v/\\":
            tokens.append(token)
    tapes = [{}, {}]
    heads = [0, 0]
    incoming, outgoing = [], []
    pc = cursor = 0
    output = ""
    trace = []
    error = None
    stopped = 0
    for step in range(36):
        halted = pc == len(tokens)
        trace.append(
            (
                (
                    (
                        pc,
                        *heads,
                        _pack(incoming),
                        len(incoming),
                        _pack(outgoing),
                        len(outgoing),
                    ),
                    *(
                        frozenset(key for key, bit in tape.items() if bit)
                        for tape in tapes
                    ),
                ),
                halted,
                output,
                cursor,
                cursor,
            )
        )
        if error or (step == 32 and not halted):
            break
        if halted:
            stopped += 1
            if stopped == 4:
                break
            continue
        token = tokens[pc]
        a, b = (tape.get(head, 0) for tape, head in zip(tapes, heads, strict=True))
        nand = int(not (a and b))
        target = pc + 1
        if isinstance(token, int):
            positions = [i for i, label in enumerate(tokens) if label == token]
            if token % 2 == nand:
                destination = positions[-1] if nand else positions[0]
                if destination != pc:
                    target = destination
        elif token in "{}<>":
            heads[int(token in "<>")] += 1 if token in "}>" else -1
        elif token in "^v":
            index = int(token == "v")
            tapes[index][heads[index]] = nand
        elif token == "/":
            if not incoming:
                if cursor == len(stdin):
                    error = "input"
                    continue
                incoming = [(ord(stdin[cursor]) >> index) & 1 for index in range(8)]
                cursor += 1
            tapes[1][heads[1]] = incoming.pop(0)
        else:
            outgoing.append(a)
        pc = target
        if outgoing and (len(outgoing) == 8 or pc == len(tokens)):
            output += chr(_pack(outgoing))
            outgoing.clear()
    return error, trace


def _check(factory, code, stdin):
    def state(machine):
        return (
            tuple(machine.state),
            frozenset(machine.a_ones),
            frozenset(machine.b_ones),
        )

    assert observed(factory, code, stdin, state, cap=32) == _model(code, stdin), (
        code,
        stdin,
    )


def check_raw_nandypants():
    alphabet = "{}<>^v/\\"
    corpus = ["".join(tokens) for tokens in product(alphabet, repeat=3)]
    corpus += [
        "",
        "ignored",
        "02 ^v 2",
        "03^3v03",
        "1^1v3",
        "1^1v1",
        "0^v0^0",
        "^" + "\\" * 11,
        "/^\\" * 10,
        "{^}^<v>v",
        "٣^3",
    ]
    for code, stdin in product(corpus, ("", "\\0", "āÿ")):
        _check(_Machine, code, stdin)

    class LostOutput(_Machine):
        def step(self):
            super().step()
            if self.halted:
                self.io.print_str("!")

    with pytest.raises(AssertionError):
        _check(LostOutput, "^\\", "")
