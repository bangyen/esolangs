"""Revision 182685 rules; dense tape, explicit bits and independent brackets."""

import itertools
import random

import pytest

from esolangs.languages.monotonic_boolfuck.interpreter import _Machine
from tests.interpreters.oracle_support import observed
from tests.interpreters.semantic_oracles import bracket_pairs
from tests.support import workspace_oracle as resources

_WORKSPACE = resources.workspace_model(
    "monotonic-boolfuck-v1", "control ones input_cursor"
)

_CAP = 64


def _model(code, stdin):
    try:
        pairs = bracket_pairs(code)
    except ValueError:
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
        outgoing = (0, 0) if halted else (packed(pending), len(pending))
        state = pc, ptr, buffered, remaining, *outgoing
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
            next_pc = pairs[pc] + (command == "[")
        pc = next_pc
        trace.append(view())
    if pc == len(code):
        trace.extend([view()] * 3)
    return None, trace


def _observed(machine_type, code, stdin, expected):
    def view(machine):
        state, ones, progress = machine.snapshot()
        assert progress == machine.io.progress()
        return tuple(state), tuple(sorted(ones)), tuple(machine.memory)

    checked = resources.workspace_view(
        expected,
        _WORKSPACE,
        lambda row: (row[0], frozenset(row[1]), row[-1]),
        view,
    )
    error, rows = observed(machine_type, code, stdin, checked, cap=_CAP)
    if rows[0][0] is None:
        assert error == "syntax"
        return error, []
    assert error is None
    return None, [(*row[0], *row[1:]) for row in rows]


def _agrees(machine_type, code, stdin):
    expected = _model(code, stdin)
    assert _observed(machine_type, code, stdin, expected[1]) == expected, (code, stdin)
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
    for component in _WORKSPACE.components:

        class MissingAtHalt(resources.missing_workspace(_Machine, component)):
            def workspace_snapshot(self):
                if not self.halted:
                    return _Machine.workspace_snapshot(self)
                return super().workspace_snapshot()

        with pytest.raises(AssertionError):
            _agrees(MissingAtHalt, "1,;", "A")
    for code, stdin, bits in (("", "", 0), ("1", "", 7), ("1;", "", 8), (",", "A", 15)):
        rows = _agrees(_Machine, code, stdin)[1]
        parts = ((row[0], frozenset(row[1]), row[-1]) for row in rows)
        assert resources.charged_bits(_WORKSPACE, parts) == bits
    return len(results) + 4, len(controls) + len(_WORKSPACE.components)
