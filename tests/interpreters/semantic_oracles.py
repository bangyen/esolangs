"""Bounded interpreters sharing no parser, transition, or I/O code with production."""

from dataclasses import dataclass

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO


@dataclass(frozen=True)
class Observation:
    output: str
    memory: tuple[int, ...]
    ip: int
    consumed: int
    halted: bool


def boolfuck(code: str, stdin: str, cap: int) -> Observation:
    pairs = {}
    opens = []
    for at, command in enumerate(code):
        if command == "[":
            opens.append(at)
        elif command == "]":
            if not opens:
                raise ValueError("unmatched close")
            start = opens.pop()
            pairs[start], pairs[at] = at, start
    if opens:
        raise ValueError("unmatched open")
    cells = {}
    pc = ptr = consumed = bit_at = 0
    outgoing = []
    output = []
    for _ in range(cap):
        if pc == len(code):
            break
        command = code[pc]
        bit = cells.get(ptr, 0)
        if command == "+":
            cells[ptr] = 1 - bit
        elif command == "<":
            ptr -= 1
        elif command == ">":
            ptr += 1
        elif command == ",":
            byte_at = bit_at // 8
            byte = ord(stdin[byte_at]) % 256 if byte_at < len(stdin) else 0
            cells[ptr] = (byte >> (bit_at % 8)) & 1
            bit_at += 1
            consumed = min(len(stdin), (bit_at + 7) // 8)
        elif command == ";":
            outgoing.append(bit)
            if len(outgoing) == 8:
                output.append(chr(sum(b * 2**i for i, b in enumerate(outgoing))))
                outgoing.clear()
        elif command == "[" and not bit:
            pc = pairs[pc]
        elif command == "]":
            pc = pairs[pc]
            continue
        pc += 1
    halted = pc == len(code)
    if halted and outgoing:
        output.append(chr(sum(b * 2**i for i, b in enumerate(outgoing))))
    occupied = [at for at, value in cells.items() if value] + [0, ptr]
    memory = tuple(cells.get(at, 0) for at in range(min(occupied), max(occupied) + 1))
    return Observation("".join(output), memory, pc, consumed, halted)


def subleq(code: str, stdin: str, cap: int) -> Observation:
    cells = [int(token) for token in code.split()]
    pc = consumed = 0
    output = []
    for _ in range(cap):
        if pc < 0 or pc >= len(cells):
            break
        if pc + 2 >= len(cells):
            raise RuntimeError("incomplete instruction")
        a, b, target = cells[pc : pc + 3]
        if a == -1:
            if b < 0:
                raise ValueError("negative input destination")
            if consumed == len(stdin):
                raise EOFError
            value = ord(stdin[consumed]) % 256
            consumed += 1
        else:
            if a < 0 or b < -1:
                raise ValueError("negative data address")
            left = cells[a] if a < len(cells) else 0
            if b == -1:
                output.append(chr(left % 256))
                pc += 3
                continue
            value = (cells[b] if b < len(cells) else 0) - left
        if b >= len(cells):
            cells.extend([0] * (b + 1 - len(cells)))
        cells[b] = value
        pc = target if a != -1 and value <= 0 else pc + 3
    return Observation(
        "".join(output), tuple(cells), pc, consumed, pc < 0 or pc >= len(cells)
    )


def smallfuck(code: str, _stdin: str, cap: int) -> Observation:
    """Model source-sized tape, boundary halts and the repo's final-cell answer."""
    depth = 0
    for command in code:
        depth += (command == "[") - (command == "]")
        if depth < 0:
            raise ValueError("unmatched close")
    if depth:
        raise ValueError("unmatched open")
    tape = [0] * len(code)
    pc = pointer = 0
    for _ in range(cap):
        if pc >= len(code):
            break
        command = code[pc]
        if command == "*":
            tape[pointer] ^= 1
        elif command in "<>":
            pointer += 1 if command == ">" else -1
            if not 0 <= pointer < len(tape):
                pc = len(code)
                break
        elif command in "[]" and tape[pointer] == (command == "]"):
            direction = 1 if command == "[" else -1
            nesting = 1
            while nesting:
                pc += direction
                if code[pc] == command:
                    nesting += 1
                elif code[pc] == ("]" if command == "[" else "["):
                    nesting -= 1
        pc += 1
    halted = pc >= len(code)
    output = str(tape[2] if len(tape) > 2 else 0) if halted else ""
    return Observation(output, tuple(tape), pc, 0, halted)


#: Empty, two raw bytes, and a long multibyte stream.
STDINS = ["", "\x81\x02", "λ\n\xff" * 30]


def observed(machine_type, code, stdin, cap=200, *, dump=False):
    """Step the production machine; ``dump`` takes its one post-halt step."""
    io = ScriptedIO(stdin)
    machine = machine_type(code, io)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    if dump and machine.halted:
        machine.step()
    return Observation(
        io.getvalue(), tuple(machine.memory), machine.ip, io.position(), machine.halted
    )


def agrees(machine_type, oracle, code, stdin, *, dump=False):
    """Production matches the oracle, or fails the way the oracle does."""
    try:
        expected = oracle(code, stdin, 200)
    except (EOFError, ValueError, RuntimeError) as error:
        raised = HaltError if isinstance(error, RuntimeError) else type(error)
        with pytest.raises(raised):
            observed(machine_type, code, stdin, dump=dump)
        return error
    assert observed(machine_type, code, stdin, dump=dump) == expected, (code, stdin)
    return expected
