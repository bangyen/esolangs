"""Revision 198382 Qrain, using list FIFOs and scanned bracket targets."""

import itertools
import random

import pytest

from esolangs.languages.qrain.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _model(source, stdin):
    level = 0
    for char in source:
        level += (char == "[") - (char == "]")
        if level < 0:
            return "syntax", [(None, False, "", 0, 0)]
    if level:
        return "syntax", [(None, False, "", 0, 0)]
    pc, pointer, queues, outgoing, consumed, output, error = 0, 0, {}, [], 0, "", None

    def view():
        occupied = {*queues, 0, pointer}
        memory = tuple(
            (queues.get(i) or [0])[0] for i in range(min(occupied), max(occupied) + 1)
        )
        live = tuple(sorted((i, tuple(q)) for i, q in queues.items() if q))
        return (
            (pc, pointer, live, tuple(outgoing), memory, pc),
            pc == len(source),
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if pc == len(source):
            break
        command, next_pc = source[pc], pc + 1
        queue = queues.setdefault(pointer, [])
        front = queue[0] if queue else 0
        if command == ">":
            pointer += 1
        elif command == "<":
            pointer -= 1
        elif command == "+":
            queue.append(int(front == (outgoing[0] if outgoing else 0)))
        elif command == "-":
            if queue:
                del queue[0]
            else:
                error = "halt"
        elif command == ",":
            byte = ord(stdin[consumed]) % 256 if consumed < len(stdin) else 0
            consumed = min(consumed + 1, len(stdin))
            queue.extend(map(int, f"{byte:08b}"[::-1]))
        elif command == ".":
            outgoing.extend(queue[:8])
            del queue[:8]
            if len(outgoing) >= 8:
                output += chr(int("".join(map(str, outgoing[:8][::-1])), 2))
                del outgoing[:8]
        elif (command == "[" and front == 0) or (command == "]" and front == 1):
            at, depth, step = pc, 1, 1 if command == "[" else -1
            opposite = "]" if command == "[" else "["
            while depth:
                at += step
                depth += (source[at] == command) - (source[at] == opposite)
            next_pc = at + 1
        if not error:
            pc = next_pc
        trace.append(view())
        if error:
            break
    if not error and pc == len(source):
        trace.extend([view()] * 3)
    return error, trace


def _agrees(factory, source, stdin):
    expected = _model(source, stdin)
    assert (
        observed(
            factory,
            source,
            stdin,
            lambda m: (
                *m.state,
                tuple(sorted((i, tuple(q)) for i, q in m.queues.items() if q)),
                tuple(m.out),
                tuple(m.memory),
                m.ip,
            ),
        )
        == expected
    ), (source, stdin)
    return expected


def check_raw_qrain():
    atoms = "><+-.,[]x"
    corpus = ["".join(p) for n in range(4) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += ["".join(rng.choices(atoms, k=16)) for _ in range(128)]
    corpus += [
        ",.",
        ",,....",
        "+.+++++++.",
        "+.+.",
        "+.[+.-]",
        "[[-]]",
        "+[+]",
        ",[-].",
        ",.>+.<,.",
        "<>+",
        "++-",
        ".",
        "λ\n",
        " ",
        "x" * 80,
        "] [",
        ",+.......",
    ]
    inputs = ("", "\x81\x02", "λ\n", "\xff\x00", "\U0010ffff")
    results = [
        _agrees(_Machine, source, stdin) for source in corpus for stdin in inputs
    ]
    assert {error for error, _ in results} == {None, "syntax", "halt"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model(",.", "λ")[1][-1][2] == chr(ord("λ") % 256)
    assert _model("+.+++++++.", "")[1][-1][2] == "\x01"
    controls = {
        "equal": ("+", ""),
        "outfront": ("+.+", ""),
        "dequeue": ("++-", ""),
        "underflow": ("-", ""),
        "input": (",", "\x02"),
        "eof": (",", ""),
        "output": (",.", "\x81"),
        "partial": ("+.", ""),
        "left": ("<+", ""),
        "jump": ("[+]", ""),
        "syntax": ("[", ""),
        "posthalt": ("", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eof":
                    io.input_char = lambda: 255
                super().__init__(
                    code.replace("[", "x") if self.mode == "syntax" else code, io
                )

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                pc, ptr = self.state
                command = self.code[pc]
                if self.mode == "underflow":
                    self.state = type(self.state)(pc + 1, ptr)
                    return
                if self.mode == "outfront" and command == "+":
                    self.out.clear()
                super().step()
                if self.mode == "equal" and command == "+":
                    self.queues[ptr][-1] ^= 1
                elif self.mode == "dequeue" and command == "-":
                    self.queues[ptr].appendleft(1)
                elif self.mode == "input" and command == ",":
                    self.queues[ptr].reverse()
                elif self.mode == "output" and command == ".":
                    self.io.print_str("extra")
                elif self.mode == "partial" and command == ".":
                    self.io.print_char("\x01")
                    self.out.clear()
                elif self.mode == "left" and command == "<":
                    self.state = type(self.state)(pc + 1, 0)
                elif self.mode == "jump" and command == "[":
                    self.state = type(self.state)(pc + 1, ptr)

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    return len(results), len(controls)
