"""Byte ring evaluator with explicit bracket walks and mutable cells."""

from itertools import product

import pytest

from esolangs.languages.circlefuck.interpreter import _Machine
from tests.interpreters.oracle_support import observed, stalled


def _branch(ring, pc, token):
    stride = 1 if token == "[" else -1
    depth = 1
    for distance in range(1, len(ring)):
        index = (pc + stride * distance) % len(ring)
        char = chr(ring[index])
        depth += (char == token) - (char in "[]" and char != token)
        if not depth:
            return index + 1
    return pc


def _model(initial, stdin):
    ring = bytearray(initial)
    pc = head = cursor = 0
    halted = False
    output = ""
    trace = []
    for step in range(25):
        row = (pc, head, tuple(ring), halted), halted, output, cursor, cursor
        trace.append(row)
        if halted:
            return None, trace + [row] * 3
        if step == 24:
            break
        token = chr(ring[pc])
        following = pc + 1
        match token:
            case "@":
                halted = True
                continue
            case "#":
                following += 1
            case ">" | "<":
                head += 1 if token == ">" else -1
            case "+" | "-":
                ring[head] = (ring[head] + (1 if token == "+" else -1)) % 256
            case "," if cursor < len(stdin):
                ring[head] = ord(stdin[cursor]) % 256
                cursor += 1
            case ".":
                output += chr(ring[head])
            case "[" | "]":
                if bool(ring[head]) == (token == "]"):
                    following = _branch(ring, pc, token)
            case "{":
                ring.insert(head, 0)
                following += head <= pc
            case "}":
                if len(ring) == 1:
                    return "halt", [*trace, row]
                del ring[head]
                following -= head < pc
        pc, head = following % len(ring), head % len(ring)
    return None, trace


def _check(factory, initial, stdin):
    source = "".join(f"\\x{byte:02x}" for byte in initial)
    assert observed(factory, source, stdin, lambda vm: vm.state, cap=24) == _model(
        initial, stdin
    ), (initial, stdin)


def check_raw_circlefuck():
    commands = b"+-<>.,[]@#{}\0"
    for initial, stdin in product(product(commands, repeat=2), ("", "Ł@")):
        _check(_Machine, initial, stdin)
    for initial in (b"}", b">{.<}@", b">[\0]@", b"@]<", b">[[\0]]", b"],[", b",\xff.@"):
        _check(_Machine, initial, "\0")

    _check(_Machine, b",+.@", "ÿ")

    with pytest.raises(AssertionError):
        _check(stalled(_Machine), b"@", "")
