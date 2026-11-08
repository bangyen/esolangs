"""Independent single-gate event model, including multi-wire inputs.

https://esolangs.org/wiki/Circuit_Diagram, logic gates and wiring values.
All seven Boolean gates, widths 1..3, EOF-zero input and quiescence. Latching
and event lifetime follow Decisions; arbitrary topology stays in raw tests.
"""

from itertools import product

from esolangs.languages.circuit_diagram.interpreter import _Machine
from tests.interpreters.oracle_support import observed, reject_faults


def _source(kind, width):
    wire = f"-{width}-."
    if kind == "~":
        return [wire + "~.-:"], ((0, len(wire) - 1), (0, len(wire) + 1))
    return [wire, " " * len(wire) + kind + ".-:", wire], (
        (0, len(wire) - 1),
        (2, len(wire) - 1),
        (1, len(wire) + 1),
    )


def _inputs(count, width, stdin):
    cursor, inputs = 0, []
    for _ in range(count):
        bits = []
        for _ in range(width):
            while cursor < len(stdin) and stdin[cursor].isspace():
                cursor += 1
            if cursor == len(stdin):
                bits.append(0)
            else:
                bit = stdin[cursor]
                cursor += 1
                if bit not in "01":
                    return None, cursor
                bits.append(int(bit))
        inputs.append(tuple(bits))
    return tuple(inputs), cursor


def _result(kind, inputs):
    if kind == "~":
        return tuple(1 - bit for bit in inputs[0])
    bits = [bit for wire in inputs for bit in wire]
    if kind in "aA":
        value = all(bits)
    elif kind in "oO":
        value = any(bits)
    else:
        value = sum(bits) == 1
    return (int(not value if kind.isupper() else value),)


def _model(kind, width, stdin):
    count = 1 if kind == "~" else 2
    inputs, cursor = _inputs(count, width, stdin)
    if inputs is None:
        return "syntax", [(None, False, "", cursor, cursor)]
    values = (*inputs, None)
    latches, done, output, trace = (None,) * count, False, "", []

    def row():
        return (values, latches), done, output, cursor, cursor

    for _ in range(8):
        trace.append(row())
        if done:
            return None, trace + [row()] * 3
        if values[-1] is not None:
            output += "".join(map(str, values[-1]))
        latches = tuple(
            new if new is not None else old
            for old, new in zip(latches, values[:-1], strict=True)
        )
        ready = any(value is not None for value in values[:-1]) and all(
            value is not None for value in latches
        )
        done = not ready and all(value is None for value in values)
        values = (None,) * count + (_result(kind, latches) if ready else None,)
    raise AssertionError("single gate did not settle")


def _check(factory, kind, width, stdin="01 unused"):
    code, ports = _source(kind, width)

    def view(machine):
        values = tuple(
            machine.values[machine.index[id(machine.topology.by_cell[point])]]
            for point in ports
        )
        gate = next(i for i, gate in enumerate(machine.gates) if gate.kind == kind)
        return values, machine.latches[gate]

    assert observed(factory, code, stdin, view, cap=8) == _model(kind, width, stdin), (
        code,
        stdin,
    )


def check_raw_circuit_diagram():
    for kind, width in product("aAoOxX~", range(1, 4)):
        count = width if kind == "~" else 2 * width
        for value in range(1 << count):
            _check(_Machine, kind, width, " \n".join(f"{value:0{count}b}") + " unused")
        for stdin in ("", " \n", "0", "1 ", "01", "bad", "0 x", "10\n1"):
            _check(_Machine, kind, width, stdin)

    class WrongBit(_Machine):
        def step(self):
            super().step()
            self.values = tuple(
                None if value is None else tuple(1 - bit for bit in value)
                for value in self.values
            )

    reject_faults(_check, _Machine, WrongBit, "a", 1)
