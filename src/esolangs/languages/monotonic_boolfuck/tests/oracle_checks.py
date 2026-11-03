"""Revision 182685 rules; dense tape, explicit bit streams and scanned loops."""

import itertools
import random

import pytest

from esolangs.languages.monotonic_boolfuck.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO

_CAP = 64


def _balanced(code):
    depth = 0
    for command in code:
        depth += (command == "[") - (command == "]")
        if depth < 0:
            return False
    return depth == 0


def _model(code, stdin):
    if not _balanced(code):
        return "syntax", []
    incoming = [int(b) for c in stdin for b in f"{ord(c) % 256:08b}"[::-1]]
    tape, origin, pc, ptr, reads, bits = [0], 0, 0, 0, 0, []

    def packed(chunk):
        return sum(bit * 2**i for i, bit in enumerate(chunk))

    def view():
        halted = pc == len(code)
        ones = tuple(origin + i for i, bit in enumerate(tape) if bit)
        low, high = min((0, ptr, *ones)), max((0, ptr, *ones))
        memory = tuple(tape[i - origin] for i in range(low, high + 1))
        buffered, remaining, consumed = 0, 0, 0
        if reads:
            byte, used = divmod(reads - 1, 8)
            remaining = 7 - used
            buffered = packed(incoming[8 * byte + used + 1 : 8 * byte + 8])
            consumed = min(len(stdin), byte + 1)
        complete = len(bits) // 8 * 8
        output = "".join(chr(packed(bits[i : i + 8])) for i in range(0, complete, 8))
        pending = bits[complete:]
        if halted and pending:
            output += chr(packed(pending))
        state = (
            pc,
            ptr,
            buffered,
            remaining,
            0 if halted else packed(pending),
            0 if halted else len(pending),
        )
        return state, ones, memory, halted, output, consumed, consumed

    trace = [view()]
    for _ in range(_CAP):
        if pc == len(code):
            break
        command = code[pc]
        index, next_pc = ptr - origin, pc + 1
        if command == "1":
            tape[index] = 1
        elif command == ",":
            tape[index] |= incoming[reads] if reads < len(incoming) else 0
            reads += 1
        elif command == ";":
            bits.append(tape[index])
        elif command in "<>":
            ptr += 1 if command == ">" else -1
            if ptr < origin:
                tape.insert(0, 0)
                origin -= 1
            elif ptr == origin + len(tape):
                tape.append(0)
        elif (command == "[" and not tape[index]) or command == "]":
            direction = 1 if command == "[" else -1
            depth, at = 1, pc
            while depth:
                at += direction
                if code[at] == command:
                    depth += 1
                elif code[at] in "[]":
                    depth -= 1
            next_pc = at + (command == "[")
        pc = next_pc
        trace.append(view())
    if pc == len(code):
        trace.extend([view()] * 3)
    return None, trace


def _observed(machine_type, code, stdin):
    io = ScriptedIO(stdin)
    try:
        machine = machine_type(code, io)
    except ValueError:
        return "syntax", []

    def view():
        state, ones, progress = machine.snapshot()
        return (
            tuple(state),
            tuple(sorted(ones)),
            tuple(machine.memory),
            machine.halted,
            io.getvalue(),
            io.position(),
            progress,
        )

    trace = [view()]
    for _ in range(_CAP):
        if machine.halted:
            break
        machine.step()
        trace.append(view())
    if machine.halted:
        for _ in range(3):
            machine.step()
            trace.append(view())
    return None, trace


def _agrees(machine_type, code, stdin):
    expected = _model(code, stdin)
    assert _observed(machine_type, code, stdin) == expected, (code, stdin)
    return expected


def check_raw_monotonic():
    atoms = "1,;<>[]x"
    corpus = ["".join(p) for n in range(4) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += [
        "".join(rng.choices(("1", ",", ";", "<", ">", "[]", "[>]", "[<]", "x"), k=12))
        for _ in range(256)
    ]
    corpus += [
        ",;>" * 17,
        "1" + ",;>" * 17,
        "1" + ",;" * 17,
        "1[>]",
        "1[>1]",
        "1;[]",
        ";1[]",
        "1[;]",
        "<[>1]<;",
        "λ<1>;",
        "[1[;]]1;",
        "1;;x",
    ]
    stdins = ("", "\x81\x02", "λ\n\xff")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in stdins]
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][3] for error, trace in results if not error)
    assert _model("1;", "")[1][-1][4] == "\x01"
    assert _model(",;>" * 8, "\x81")[1][-1][4] == "\x81"
    assert _model("1;[]", "")[1][-1][4] == ""  # a cap must not flush
    controls = {
        "clear": ("1,;", "\x00"),
        "consume": ("1,", "X"),
        "close": ("1[>]", ""),
        "left": ("<1;", ""),
        "flush": ("1;", ""),
        "syntax": ("[", ""),
    }
    for fault, (code, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "flush":

                    def discard(_char):
                        pass

                    io.print_char = discard
                super().__init__(
                    code.replace("[", "") if self.mode == "syntax" else code, io
                )

            def step(self):
                if self.halted:
                    super().step()
                    return
                at, pointer = self.state.pc, self.state.ptr
                command = self.code[at]
                if (
                    self.mode == "consume" and command == "," and pointer in self.ones
                ) or (
                    self.mode == "close" and command == "]" and pointer not in self.ones
                ):
                    self.state = self.state._replace(pc=at + 1)
                else:
                    super().step()
                    if self.mode == "clear" and command == ",":
                        self.ones.discard(pointer)
                    elif self.mode == "left" and command == "<":
                        self.state = self.state._replace(ptr=0)

        with pytest.raises(AssertionError):
            _agrees(Fault, code, stdin)
    return len(results), len(controls)
