"""Model the Bifunge command table at https://esolangs.org/wiki/Bifunge (198926).

Use the repository's conventions for unwritten cells, empty pops and EOF.
"""

from collections import deque

from esolangs.languages.bifunge.interpreter import _Machine, _parse
from tests.interpreters.oracle_support import checker

_OPS = (
    "nop",
    "and",
    "or",
    "south",
    "xor",
    "east",
    "horizontal",
    "read",
    "not",
    "vertical",
    "west",
    "write",
    "north",
    "halt",
    "zero",
    "one",
)
_DIRECTIONS = {"east": 1, "south": 1j, "west": -1, "north": -1j}
_LOGIC = {"and": "0001", "or": "0111", "xor": "0110"}
_STEPS = 64


def _decode(source):
    field = {}
    for row, (top, bottom) in enumerate(zip(source[::2], source[1::2], strict=True)):
        for offset in range(0, len(top), 2):
            tile = top[offset : offset + 2] + bottom[offset : offset + 2]
            bits = "".join(str(ord(char) % 2) for char in tile)
            field[complex(offset // 2, row)] = _OPS[int(bits, 2)]
    return field


def _predict(source, stdin):
    field = _decode(source)
    position, heading = 0j, 1
    cursor = 0
    stack, outgoing, output = [], [], []
    incoming = deque()

    def pop():
        return stack.pop() if stack else 0

    def frame(*, halted=False):
        ip = (
            None
            if halted
            else (
                int(position.imag),
                int(position.real),
                int(heading.real),
                int(heading.imag),
            )
        )
        return (ip, tuple(stack)), halted, "".join(output), cursor, cursor

    trace = [frame()]
    for _ in range(_STEPS):
        op = field.get(position, "nop")
        if op == "halt":
            trace.extend([frame(halted=True)] * 4)
            break
        if op in _DIRECTIONS:
            heading = _DIRECTIONS[op]
        elif op in ("horizontal", "vertical"):
            heading = (1 if op == "horizontal" else 1j) * (1, -1)[pop()]
        elif op in _LOGIC:
            stack.append(int(_LOGIC[op][2 * pop() + pop()]))
        elif op == "not":
            stack.append(int(not pop()))
        elif op in ("zero", "one"):
            stack.append(int(op == "one"))
        elif op == "read":
            if not incoming:
                if cursor == len(stdin):
                    return "input", [*trace, frame()]
                byte = ord(stdin[cursor])
                cursor += 1
                if byte > 255:
                    return "argument", [*trace, frame()]
                incoming.extend(f"{byte:08b}")
            stack.append(int(incoming.popleft()))
        elif op == "write":
            outgoing.append(str(pop()))
            if len(outgoing) == 8:
                output.append(chr(int("".join(outgoing), 2)))
                outgoing.clear()
        position += heading
        trace.append(frame())
    return None, trace


def _source(rows):
    source = []
    for row in rows:
        tiles = [
            f"{int(op, 16):04b}".translate(str.maketrans("01", "()")) for op in row
        ]
        source.extend(
            ["".join(tile[:2] for tile in tiles), "".join(tile[2:] for tile in tiles)]
        )
    return source


def _machine(source, io):
    return _Machine(_parse(source), io)


_check = checker(
    _predict, lambda machine: (machine.ip, tuple(machine.stack)), cap=_STEPS
)


def check_raw_bifunge():
    for rows, stdin, failure, output, halted in (
        (("7B" * 16 + "FB" * 3 + "D",), "\x81é", None, "\x81é", True),
        (("B" * 8 + "D",), "", None, "\x00", True),
        (("81B82B84BF1BEF2BFF4BFF1B08BD",), "", None, "k", True),
        (("003", "C0A"), "", None, "", False),
        (("7D",), "", "input", "", False),
        (("7D",), "λ", "argument", "", False),
    ):
        error, trace = _check(_machine, _source(rows), stdin)
        assert (error, trace[-1][1], trace[-1][2]) == (failure, halted, output)

    for rows, stdin, destination in (
        (("00300", "00700", "0D6D0"), "\x7f", (2, 3, 1, 0)),
        (("00300", "00700", "0D6D0"), "\x80", (2, 1, -1, 0)),
        (("00300", "00000", "0D6D0"), "", (2, 3, 1, 0)),
        (("30D", "579", "00D"), "\x7f", (2, 2, 0, 1)),
        (("30D", "579", "00D"), "\x80", (0, 2, 0, -1)),
        (("30D", "509", "00D"), "", (2, 2, 0, 1)),
    ):
        error, trace = _check(_machine, _source(rows), stdin)
        assert error is None
        assert trace[-1][1]
        last_ip = next(state[0] for state, halted, *_ in reversed(trace) if not halted)
        assert last_ip == destination
