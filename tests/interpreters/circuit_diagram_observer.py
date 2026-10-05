"""Complete event observations with immutable topology reused per source."""

# ruff: noqa: SLF001 -- Observe complete native state and compiled topology.

import copy

from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.circuit_diagram_reference import ClockTape, NamedReference
from tests.interpreters.views import view as vm_view


class Factory:
    def __init__(self, code, machine_type, clock_seconds=0, symbols=None):
        self.code = code
        self.machine_type = machine_type
        self.topologies = {}
        self.template = NamedReference(
            code, "", clock_seconds=clock_seconds, symbols=symbols
        )
        main = self.template.main
        self.ports = []
        for y, row in enumerate(main):
            stripped = row.lstrip()
            if stripped.startswith("-"):
                point = len(row) - len(stripped), -y
                self.ports.append(self.template.owner[point])
        self.constants = [
            gate for gate in self.template.gates if gate.kind in {"(", ")", "t"}
        ]

    def reference(self, stdin):
        ref = copy.copy(self.template)
        ref.clock = ClockTape(self.template.clock.seconds)
        ref.stdin = stdin
        ref.offset = 0
        ref.past_end = 0
        ref.stdout = ""
        ref.halted = False
        ref.latches = {gate: (None,) * len(gate.inputs) for gate in ref.gates}
        arrivals = {group: [] for group in ref.components}
        for group in self.ports:
            arrivals[group].append(tuple(ref.input() for _ in range(ref.widths[group])))
        seconds = (
            ref.clock.read() if any(gate.kind == "t" for gate in self.constants) else 0
        )
        for gate in self.constants:
            group = gate.outputs[0]
            arrivals[group].append(
                tuple((seconds >> index) & 1 for index in range(31, -1, -1))
                if gate.kind == "t"
                else (int(gate.kind == ")"),) * ref.widths[group]
            )
        ref.values = {group: ref.merge(signals) for group, signals in arrivals.items()}
        return ref

    def check(self, stdin, answer=None, limit=4096):
        ref = self.reference(stdin)
        io = ScriptedIO(stdin)
        native = self.machine_type._for_run(self.code, io)
        identity = (
            id(native.grid),
            id(native.wirings),
            id(native.gates),
            id(native.index),
            id(native._by_cell),
        )
        if identity not in self.topologies:
            groups = tuple(
                frozenset((col, -row) for row, col in wiring.cells)
                for wiring in native.wirings
            )
            assert set(groups) == set(ref.components)
            canonical = {group: group for group in ref.components}
            groups = tuple(canonical[group] for group in groups)
            by_wire = {
                id(wire): group
                for wire, group in zip(native.wirings, groups, strict=True)
            }
            assert [wire.width for wire in native.wirings] == [
                ref.widths[group] for group in groups
            ]
            by_gate = {
                (gate.kind, (gate.col, -gate.row)): gate for gate in native.gates
            }
            assert set(by_gate) == {(gate.kind, gate.point) for gate in ref.gates}
            for gate in ref.gates:
                actual = by_gate[gate.kind, gate.point]
                assert tuple(by_wire[id(wire)] for wire in actual.inputs) == gate.inputs
                assert (
                    tuple(by_wire[id(wire)] for wire in actual.outputs) == gate.outputs
                )
            reference_gates = {(gate.kind, gate.point): gate for gate in ref.gates}
            ordered = tuple(
                reference_gates[gate.kind, (gate.col, -gate.row)]
                for gate in native.gates
            )
            fingerprint = self.fingerprint(native)
            self.topologies[identity] = (
                groups,
                ordered,
                fingerprint,
                dict(native.index),
                dict(native._by_cell),
            )
        groups, ordered, fingerprint, index, by_cell = self.topologies[identity]
        assert native.index == index
        assert native._by_cell == by_cell
        assert self.fingerprint(native) == fingerprint
        saved = []
        seen = {}
        for step in range(limit):
            values = tuple(ref.values[group] for group in groups)
            latches = tuple(ref.latches[gate] for gate in ordered)
            assert native.values == values
            assert native.latches == latches
            assert native.halted is ref.halted
            assert (native.halted, io.getvalue(), io.position(), io.past_end) == (
                ref.halted,
                ref.stdout,
                ref.offset,
                ref.past_end,
            )
            assert vm_view(native, "ip") is None
            assert vm_view(native, "stack") == []
            assert vm_view(native, "memory") == [
                bit for bundle in values if bundle is not None for bit in bundle
            ]
            state = (values, latches, ref.halted, ref.clock.position)
            snapshot = native.snapshot()
            hash(snapshot)
            assert snapshot == state
            if ref.halted:
                if answer is not None:
                    assert ref.stdout == answer, (stdin, ref.stdout, answer)
                native.step()
                assert native.snapshot() == snapshot
                assert io.getvalue() == ref.stdout
                assert all(old == expected for old, expected in saved)
                assert self.fingerprint(native) == fingerprint
                assert native.index == index
                assert native._by_cell == by_cell
                return {"output": ref.stdout, "generations": step, "halted": True}
            if state in seen:
                assert snapshot == saved[seen[state]][0]
                assert self.fingerprint(native) == fingerprint
                assert native.index == index
                assert native._by_cell == by_cell
                return {
                    "output": ref.stdout,
                    "generations": step,
                    "halted": False,
                    "cycle_start": seen[state],
                    "period": step - seen[state],
                }
            seen[state] = len(saved)
            saved.append((snapshot, state))
            ref.step()
            native.step()
        raise TimeoutError("observation bound reached; termination or cycle unverified")

    @staticmethod
    def fingerprint(native):
        return (
            tuple(native.grid.rows),
            tuple((wire.cells, wire.width, wire.labelled) for wire in native.wirings),
            tuple(
                (
                    gate.kind,
                    gate.row,
                    gate.col,
                    tuple(map(id, gate.inputs)),
                    tuple(map(id, gate.outputs)),
                    None if gate.body is None else tuple(gate.body),
                )
                for gate in native.gates
            ),
        )
