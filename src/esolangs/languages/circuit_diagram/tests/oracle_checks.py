"""Independent single-gate event model, including multi-wire inputs.

https://esolangs.org/wiki/Circuit_Diagram, logic gates and wiring values.
All seven Boolean gates, widths 1..3, EOF-zero input and quiescence. Latching
and event lifetime follow Decisions; arbitrary topology stays in raw tests.
"""

from itertools import product

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.circuit_diagram import interpreter as native
from esolangs.languages.circuit_diagram.interpreter import _Machine, prepare_machine
from esolangs.runtime._state import WorkspaceSnapshot
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import observed, reject_faults
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "circuit-diagram-v1", "signals latches stopped clock_cursor"
)


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


def _input_counts(count, width, stdin):
    cursor = past_end = 0
    for _ in range(count * width):
        while cursor < len(stdin) and stdin[cursor].isspace():
            cursor += 1
        if cursor == len(stdin):
            past_end += 1
        else:
            value = stdin[cursor]
            cursor += 1
            if value not in "01":
                break
    return cursor, past_end


def _parts(machine, row, ports, kind, clock_cursor=0):
    # Bind only the static index permutation; predictions never read native values.
    indices = tuple(
        machine.index[id(machine.topology.by_cell[point])] for point in ports
    )
    assert sorted(indices) == list(range(len(ports)))
    assert len(machine.values) == len(ports)
    assert len(machine.gates) == 2
    gate = next(i for i, gate in enumerate(machine.gates) if gate.kind == kind)
    outlet = next(i for i, gate in enumerate(machine.gates) if gate.kind == ":")
    values, remembered = row[0]
    signals = [None] * len(ports)
    for index, value in zip(indices, values, strict=True):
        signals[index] = value
    latches = [None, None]
    latches[gate], latches[outlet] = remembered, (None,)
    return tuple(signals), tuple(latches), row[1], clock_cursor


def _check(factory, kind, width, stdin="01 unused"):
    code, ports = _source(kind, width)
    expected = _model(kind, width, stdin)
    predictions = iter(expected[1])
    witness = workspace.WorkspaceWitness(_WORKSPACE)
    count = 1 if kind == "~" else 2
    reads, past_end = _input_counts(count, width, stdin)
    inputs = []

    def build(code, io):
        inputs.append(io)
        return factory(code, io)

    def view(machine):
        predicted = next(predictions)
        parts = _parts(machine, predicted, ports, kind)
        witness.sample(machine.workspace_snapshot(), parts)
        assert machine.snapshot() == parts
        assert (machine.io.reads, machine.io.past_end) == (reads, past_end)
        values = tuple(
            machine.values[machine.index[id(machine.topology.by_cell[point])]]
            for point in ports
        )
        gate = next(i for i, gate in enumerate(machine.gates) if gate.kind == kind)
        return values, machine.latches[gate]

    assert observed(build, code, stdin, view, cap=8) == expected, (code, stdin)
    assert (inputs[0].reads, inputs[0].past_end) == (reads, past_end)
    witness.finish()


_CLOCK_CODE = ["{stamp", "-.~.-:", "t-32-:", "}", "-stamp-:"]
_CLOCK_PORTS = ((0, 0), (0, 6))


def _clock_model():
    bits = (*(int(bit) for bit in f"{5:032b}"), 0)
    output = "".join(map(str, bits))
    trace = [
        ((((1,), None), (None,)), False, "", 1, 1),
        (((None, bits), ((1,),)), False, "", 1, 1),
        (((None, None), ((1,),)), False, output, 1, 1),
        (((None, None), ((1,),)), True, output, 1, 1),
    ]
    return trace + [trace[-1]] * 3


def _clock_histories(factory):
    expected = _clock_model()
    prepared = prepare_machine(_CLOCK_CODE, {})
    machines = (
        factory(_CLOCK_CODE, ScriptedIO("1")),
        prepared(ScriptedIO("1")),
        prepared(ScriptedIO("1")),
    )
    witnesses = [workspace.WorkspaceWitness(_WORKSPACE) for _ in machines]
    held = []
    for tick, row in enumerate(expected):
        for machine, witness in zip(machines, witnesses, strict=True):
            if tick:
                machine.step()
            parts = _parts(machine, row, _CLOCK_PORTS, "stamp", int(tick > 0))
            captured = machine.workspace_snapshot()
            witness.sample(captured, parts)
            assert machine.snapshot() == parts
            assert (
                machine.halted,
                machine.io.getvalue(),
                machine.io.position(),
                machine.io.progress(),
            ) == row[1:]
            assert (machine.io.reads, machine.io.past_end) == (1, 0)
            held.append((captured, WorkspaceSnapshot(_WORKSPACE, parts)))
            assert all(capture == reference for capture, reference in held)
    assert all(
        any(reference.parts[index] != held[0][1].parts[index] for _, reference in held)
        for index in range(len(_WORKSPACE.components))
    )
    for witness in witnesses:
        witness.finish()
    assert machines[0].clock is not machines[1].clock
    assert machines[1].clock is not machines[2].clock


def _output_failure():
    class BrokenIO(ScriptedIO):
        def print_str(self, text):
            super().print_str(text[:2])
            raise HaltError("witness output failure")

    io = BrokenIO("1")
    machine = _Machine(_CLOCK_CODE, io)
    expected = _clock_model()
    witness = workspace.WorkspaceWitness(_WORKSPACE)
    for tick in (0, 1):
        if tick:
            machine.step()
        witness.sample(
            machine.workspace_snapshot(),
            _parts(machine, expected[tick], _CLOCK_PORTS, "stamp", tick),
        )
    before = machine.snapshot()
    with pytest.raises(HaltError) as caught:
        machine.step()
    assert type(caught.value) is HaltError
    assert caught.value.args == ("witness output failure",)
    assert machine.snapshot() == before
    witness.sample(
        machine.workspace_snapshot(),
        _parts(machine, expected[1], _CLOCK_PORTS, "stamp", 1),
    )
    assert (io.getvalue(), io.position(), io.progress(), io.reads, io.past_end) == (
        "00",
        1,
        1,
        1,
        0,
    )
    witness.finish()


def _check_clock_workspace():
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(native, "_seconds_since_2000", lambda: 5)
        _clock_histories(_Machine)
        workspace.check_erasures(_WORKSPACE, _clock_histories, _Machine)
        _output_failure()


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
    _check_clock_workspace()
