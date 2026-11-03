"""Mutable array model for both byte moduli and both jump readings."""

from itertools import product

from esolangs.languages.slow_acv_mammalian.interpreter import _Machine
from tests.interpreters.oracle_support import observed

_COMMANDS = (
    "SEED",
    "CONFLAGRATE",
    "EXCRETE",
    "CONSUME",
    "FISSION",
    "DIGEST",
    "SPRINT",
    "LEAPFROG",
    "ACCEPT",
    "PRONOUNCE",
)


def _mix(arrays, modulus):
    positions = [(a, b) for a, row in enumerate(arrays) for b in range(len(row))]
    for (a, b), (c, d) in zip(
        positions[: len(positions) // 2], reversed(positions), strict=False
    ):
        x, y = arrays[a][b], arrays[c][d]
        if x > y > 0:
            transfer = x // y
            arrays[a][b], arrays[c][d] = x - transfer, (y + transfer) % modulus
        elif y > x > 0:
            transfer = y % x
            arrays[a][b], arrays[c][d] = x + transfer, y - transfer


def _model(code, stdin, modulus, io_modulus, resume):
    arrays = [[0] for _ in range(23)]
    pc = pointer = acc = cursor = 0
    output = ""
    stopped = False
    trace = []
    for step in range(25):
        halted = stopped or pc >= len(code)
        row = (
            (tuple(map(tuple, arrays)), pointer, acc, pc),
            halted,
            output,
            cursor,
            cursor,
        )
        trace.append(row)
        if halted:
            return None, trace + [row] * 3
        if step == 24:
            break
        current = arrays[pointer]
        following = pc + 1
        match code[pc]:
            case "SEED":
                for number, array in enumerate(arrays, 1):
                    if array:
                        array[0] = (array[0] + number) % modulus
            case "CONFLAGRATE":
                _mix(arrays, modulus)
            case "EXCRETE":
                current.append(acc % io_modulus)
                acc = 0
            case "CONSUME" if current:
                acc = current.pop((len(current) - 1) // 2)
            case "FISSION" if current:
                half = current.pop((len(current) - 1) // 2) // 2
                current.insert(0, half)
                current.append(half)
            case "DIGEST":
                acc ^= sum(current)
            case "SPRINT" if acc < len(current):
                pointer = (pointer + current[acc]) % len(arrays)
            case "LEAPFROG" if current and current[-1]:
                target = acc - current[0]
                if target < 1:
                    stopped = True
                    continue
                following = target - (resume == "at")
            case "ACCEPT":
                if cursor == len(stdin):
                    return "input", [*trace, row]
                arrays[0].append((ord(stdin[cursor]) ^ acc) % modulus)
                cursor += 1
            case "PRONOUNCE":
                output += chr(acc % io_modulus)
        pc = following
    return None, trace


def check_raw_slow_acv_mammalian():
    for tail, stdin, cell, port, resume in product(
        product(_COMMANDS, repeat=2),
        ("", "ÿΩ"),
        (255, 256),
        (255, 256),
        ("at", "after"),
    ):
        code = ("SEED", "ACCEPT", "FISSION", "DIGEST", *tail)
        if not stdin:
            code = code[2:]

        def build(source, io, cell=cell, port=port, resume=resume):
            return _Machine(
                source, io, cell_modulus=cell, io_modulus=port, leapfrog_resume=resume
            )

        actual = observed(
            build, " ".join(code), stdin, lambda m: (m.lst, m.ptr, m.acc, m.ind), cap=24
        )
        assert actual == _model(code, stdin, cell, port, resume), (code, stdin)
