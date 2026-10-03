"""Bounded interpreters sharing no parser, transition, or I/O code with production."""

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    output: str
    memory: tuple[int, ...]
    ip: int
    consumed: int
    halted: bool
    internal: tuple[int, ...] | None = None


@dataclass(frozen=True)
class StackObservation:
    output: str
    stack: tuple[int, ...]
    control: tuple[int, ...]
    memory: tuple[int, ...]
    ip: int
    consumed: int
    halted: bool
    error: str | None


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
        outgoing.clear()
    occupied = [at for at, value in cells.items() if value] + [0, ptr]
    memory = tuple(cells.get(at, 0) for at in range(min(occupied), max(occupied) + 1))
    used_input = bit_at % 8
    buffered = (
        (ord(stdin[(bit_at - 1) // 8]) % 256)
        if bit_at and (bit_at - 1) // 8 < len(stdin)
        else 0
    )
    incoming = buffered >> (used_input or 8)
    remaining = 8 - used_input if used_input else 0
    internal = (
        pc,
        ptr,
        incoming,
        remaining,
        sum(b * 2**i for i, b in enumerate(outgoing)),
        len(outgoing),
    )
    return Observation("".join(output), memory, pc, consumed, halted, internal)


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


def cyclic_tag(code: str, _stdin: str, cap: int) -> Observation:
    parts = code.split(",")
    if len(parts) != 2:
        raise ValueError("expected one queue separator")
    rules = ["".join(rule.split()) for rule in parts[0].split(";")]
    data = "".join(parts[1].split())
    if any(bit not in "01" for word in [*rules, data] for bit in word):
        raise ValueError("nonbinary rule or queue")
    starts = [0] + [at + 1 for at, char in enumerate(parts[0]) if char == ";"]
    offsets = [
        next(at for at in range(start, len(code)) if not code[at].isspace())
        for start in starts
    ]
    queue = deque(data)
    rule = 0
    answer = ""
    for _ in range(cap):
        if not queue:
            break
        answer = queue.popleft()
        if answer == "1":
            queue.extend(rules[rule])
        rule = (rule + 1) % len(rules)
    return Observation(
        answer if not queue else "", tuple(map(int, queue)), offsets[rule], 0, not queue
    )


def bfstack(code: str, stdin: str, cap: int) -> StackObservation:
    data = []
    loops = []
    output = []
    pc = consumed = 0
    error = None
    for _ in range(cap):
        if pc >= len(code):
            break
        command = code[pc]
        if command in "<+-.[" and not data:
            error = "HaltError"
            break
        if command == ">":
            data.append(0)
        elif command == "<":
            data.pop()
        elif command == "+":
            data[-1] = (data[-1] + 1) % 256
        elif command == "-":
            data[-1] = (data[-1] - 1) % 256
        elif command == ".":
            output.append(chr(data[-1]))
        elif command == ",":
            if consumed == len(stdin):
                error = "EOFError"
                break
            data.append(ord(stdin[consumed]))
            consumed += 1
        elif command == "[":
            if data[-1]:
                loops.append(pc)
            else:
                nesting = 1
                while nesting and pc + 1 < len(code):
                    pc += 1
                    if code[pc] == "[":
                        nesting += 1
                    elif code[pc] == "]":
                        nesting -= 1
                if nesting:
                    pc = len(code)
                    error = "ValueError"
                    break
        elif command == "]":
            if not loops:
                error = "HaltError"
                break
            pc = loops.pop()
            continue
        pc += 1
    return StackObservation(
        "".join(output),
        tuple(data),
        tuple(loops),
        (),
        pc,
        consumed,
        pc >= len(code),
        error,
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
