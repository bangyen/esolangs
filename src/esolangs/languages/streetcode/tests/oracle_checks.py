"""Independent one-row Streetcode walker and sparse tape, capped at 48 cells.

The author's command table: https://esolangs.org/wiki/Streetcode (78016).
Wall-free row, byte-independent integer cells, IO, stop and dead-end reversal;
lane geometry and junctions remain in raw tests. Movement follows Decisions.
"""

from itertools import product

from esolangs.languages.streetcode.interpreter import _Machine
from tests.interpreters.oracle_support import observed, reject_faults


def _model(source, stdin):
    pc, direction, pointer, cursor, reads = 0, (1 if len(source) > 1 else 0), 0, 0, 0
    cells, done, output, trace = {}, False, "", []

    def row():
        heading = "E" if direction == 1 else "W" if direction == -1 else "S"
        state = pc, heading, pointer, tuple(sorted(cells.items())), reads
        return state, done, output, cursor, cursor

    for tick in range(49):
        trace.append(row())
        if done:
            return None, trace + [row()] * 3
        if tick == 48:
            break
        command = source[pc]
        if command == ";":
            done = True
            continue
        if command == "U" or (command == "_" and pointer == 0):
            return "halt", [*trace, row()]
        value = cells.get(pointer, 0)
        if command == "O" and not 0 <= value <= 0x10FFFF:
            return "halt", [*trace, row()]
        if command == "I":
            if cursor == len(stdin):
                return "input", [*trace, row()]
            cells[pointer] = ord(stdin[cursor])
            reads, cursor = reads + 1, cursor + 1
        elif command in "^~":
            cells[pointer] = value + (1 if command == "^" else -1)
        elif command == "=":
            pointer += 1
        elif command == "_":
            pointer -= 1
        elif command == "O":
            output += chr(value)
        if len(source) == 1:
            done = True
        else:
            if not 0 <= pc + direction < len(source):
                direction = -direction
            pc += direction
    return None, trace


def _view(machine):
    return (
        machine.col,
        machine.heading,
        machine.cp,
        tuple(sorted(machine.cells.items())),
        machine._input_reads,
    )


def _check(factory, body, stdin="unused"):
    source = "C" + body
    assert observed(factory, [source], stdin, _view, cap=48) == _model(source, stdin), (
        source,
        stdin,
    )


def check_raw_streetcode():
    for first, second in product("^~=_IOU; abc?><", repeat=2):
        _check(_Machine, first + second + ";", "Aλ")
    for first, second, third in product(("^", "~", "=", "_", "O", "a"), repeat=3):
        _check(_Machine, first + second + third)
    for source in (
        "",
        ";",
        "^=^_O;",
        "^^^^O;",
        "~^O;",
        "=~O;",
        "===___;",
        "U;",
        "I=I_OO;",
        "IOIOIO;",
        "I~O;",
        "I^O;",
        "IO",
        "I^O^;",
    ):
        for stdin in ("", "AB", "λ\n", "\0", chr(0x10FFFF)):
            _check(_Machine, source, stdin)
    for code in ([], [""], ["abc"], ["CC"]):
        assert observed(_Machine, code, "", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class WrongCell(_Machine):
        def step(self):
            super().step()
            self.cells = {**self.cells, self.cp: self.cells.get(self.cp, 0) + 1}

    reject_faults(_check, _Machine, WrongCell, "^O;")
