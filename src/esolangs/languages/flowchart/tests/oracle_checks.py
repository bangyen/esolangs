"""Full-state checks against the independent declared Flowchart layouts."""

from dataclasses import replace
from types import MappingProxyType
from typing import NamedTuple

import pytest

from esolangs import run as public_run
from esolangs.exceptions import ArgumentError
from esolangs.languages.flowchart import interpreter as native
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import observed, overread, stalled
from tests.support import workspace_oracle as workspace

from .full_oracle import (
    _SPELL,
    _cases,
    _extra_cases,
    _fork_case,
    _memory_case,
    _Model,
    _model,
    _parallel_case,
    _reentry_case,
    _RefusalError,
    _shared_case,
    _straight,
    _switch_case,
)

_WORKSPACE = workspace.workspace_model(
    "flowchart-v1",
    "pointers deques input_cursor input_reads incoming remaining outgoing used",
)


class _Held(NamedTuple):
    cycle: object
    cycle_hash: int
    capture: object
    capture_hash: int


def _actual(machine, case):
    assert type(machine.state) is native._Run
    assert machine.grid == case.rows
    assert machine.width == len(case.rows[0])
    nodes = {
        (box.row, box.column + offset): (_SPELL[box.kind], box.column)
        for box in case.boxes
        for offset in range(len(_SPELL[box.kind]))
    }
    assert machine.nodes == nodes
    pointers = []
    for pointer in machine.pointers:
        assert type(pointer) is native._Pointer
        assert type(pointer.row) is type(pointer.col) is type(pointer.deque) is int
        assert type(pointer.done) is bool
        assert pointer.reg is None or type(pointer.reg) is int
        assert pointer.reg in (None, 0, 1)
        assert type(pointer.d) is tuple
        assert all(type(v) is int for v in pointer.d)
        assert len(pointer.d) == 2
        assert pointer.prev is None or (
            type(pointer.prev) is tuple
            and len(pointer.prev) == 2
            and all(type(v) is int for v in pointer.prev)
        )
        assert type(pointer.memory) is native._Memory
        assert type(pointer.memory._exits) is dict
        pointers.append(
            (
                pointer.row,
                pointer.col,
                pointer.d,
                pointer.reg,
                pointer.deque,
                pointer.done,
                pointer.prev,
                frozenset(pointer.memory._exits.items()),
            )
        )
    assert type(machine.deques) is MappingProxyType
    assert all(
        type(key) is int
        and type(values) is tuple
        and all(v is None or type(v) is int for v in values)
        for key, values in machine.deques.items()
    )
    port = machine.io
    assert type(port.position()) is type(port.progress()) is int
    assert (
        type(machine._input_reads)
        is type(machine._incoming)
        is type(machine._remaining)
        is int
    )
    assert type(machine.state.outgoing) is type(machine.state.used) is int
    assert type(port.reads) is type(port.past_end) is type(port._line_reads) is int
    assert type(port._character_reads) is type(port._newline) is bool
    assert port._line_reads == 0
    assert port._pending == ""
    return (
        tuple(pointers),
        frozenset((k, v) for k, v in machine.deques.items() if v),
        port.progress(),
        machine._input_reads,
        machine._incoming,
        machine._remaining,
        machine.state.outgoing,
        machine.state.used,
    )


def _cycle(parts):
    pointers = tuple((*p[:7], tuple(sorted(p[7]))) for p in parts[0])
    return pointers, tuple(sorted(parts[1])), *parts[2:]


def _views(machine, parts):
    position = next(((p[0], p[1], *p[2]) for p in parts[0] if not p[5]), None)
    memory = [
        value
        for _key, values in sorted(parts[1])
        for value in values
        if value is not None
    ]
    assert machine.ip == position
    exposed = machine.memory
    assert exposed == memory
    exposed.append(2)
    assert machine.memory == memory


def _hold(machine, held):
    cycle, capture = machine.snapshot(), machine.workspace_snapshot()
    held.append(_Held(cycle, hash(cycle), capture, hash(capture)))
    assert all(hash(c) == ch and hash(w) == wh for c, ch, w, wh in held)


def _check(factory, case, cap=64):
    rows, ios = _model(case, cap)
    pending = iter(zip(rows, ios, strict=True))
    held = []

    def view(machine):
        row, io = next(pending)
        parts = _actual(machine, case)
        assert parts == row[0]
        _views(machine, row[0])
        assert machine.snapshot() == _cycle(row[0])
        assert (
            machine.io.reads,
            machine.io.past_end,
            machine.io._character_reads,
            machine.io._newline,
        ) == io
        _hold(machine, held)
        return parts

    checked = workspace.workspace_view(rows, _WORKSPACE, lambda row: row[0], view)
    assert observed(factory, list(case.rows), case.stdin, checked, cap=cap) == (
        None,
        rows,
    )


def _literal():
    case = _straight(("read", "push_top", "write"), "A")
    assert case.rows == ("( )─/ /─\\[ ]/─\\ \\─(( ))",)
    rows, _ios = _model(case)
    machine = native._Machine(list(case.rows), ScriptedIO("A"))
    witness = workspace.WorkspaceWitness(_WORKSPACE)
    held = []
    for index, row in enumerate(rows):
        assert _actual(machine, case) == row[0]
        _views(machine, row[0])
        assert machine.snapshot() == _cycle(row[0])
        witness.sample(machine.workspace_snapshot(), row[0])
        _hold(machine, held)
        if index + 1 < len(rows):
            machine.step()
    witness.finish()
    assert all(witness.expected.written)
    assert witness.expected.peaks == [63, 2, 1, 1, 6, 3, 1, 1]
    assert witness.measured.bits == witness.expected.bits == 78
    workspace.check_erasures(_WORKSPACE, _check, native._Machine, case)
    for factory in (stalled(native._Machine), overread(native._Machine)):
        with pytest.raises(AssertionError):
            _check(factory, case)
    return case


def _failure_history(case, kind, at, prefix=0):
    model, port = _Model(case), ScriptedIO(case.stdin)
    machine = native._Machine(list(case.rows), port)
    held, events = [], []
    counts = {"read": 0, "write": 0}
    original_read, original_write = port.input_char, port._write
    setattr(model.port, "refuse_" + kind, at)
    model.port.prefix = prefix

    def read():
        counts["read"] += 1
        if kind == "read" and counts["read"] == at:
            events.append(("refuse_read", counts["read"]))
            raise ValueError("controlled physical refusal")
        try:
            value = original_read()
        except EOFError:
            events.append(("eof",))
            raise
        events.append(("read", value))
        return value

    def write(value):
        assert type(value) is str
        assert len(value) == 1
        counts["write"] += 1
        if kind == "write" and counts["write"] == at:
            if prefix:
                original_write(value[:prefix])
            events.append(("refuse_write", ord(value), prefix))
            raise ValueError("controlled physical refusal")
        original_write(value)
        events.append(("write", ord(value)))

    port.input_char, port._write = read, write
    witness = workspace.WorkspaceWitness(_WORKSPACE)
    rejected, idles = 0, 0
    for _tick in range(64):
        row = model.row()
        assert (
            _actual(machine, case),
            machine.halted,
            port.getvalue(),
            port.position(),
            port.progress(),
        ) == row
        _views(machine, row[0])
        assert machine.snapshot() == _cycle(row[0])
        assert (
            port.reads,
            port.past_end,
            port._character_reads,
            port._newline,
        ) == model.io()
        assert events == model.port.events
        witness.sample(machine.workspace_snapshot(), row[0])
        _hold(machine, held)
        if model.halted:
            idles += 1
            if idles == 4:
                break
        try:
            model.step()
        except _RefusalError:
            rejected += 1
            with pytest.raises(
                ValueError, match="controlled physical refusal"
            ) as caught:
                machine.step()
            assert type(caught.value) is ValueError
        else:
            machine.step()
    assert idles == 4
    assert rejected == 1
    witness.finish()
    assert counts[kind] == (
        model.port.read_attempts if kind == "read" else model.port.write_attempts
    )


def _failures():
    for case in (
        _straight(("one",) + ("write",) * 8 + ("zero", "write")),
        _straight(("one", "write")),
        _parallel_case(),
    ):
        for prefix in (0, 1):
            _failure_history(case, "write", 1, prefix)
    for at in (1, 2):
        _failure_history(_parallel_case(), "read", at)


def _masks(case):
    rows, ios = _model(case)
    original = rows[0][0]
    complete = workspace.WorkspaceOracle(
        workspace.WorkspaceSnapshot(_WORKSPACE, original)
    )
    for row in rows:
        complete.sample(workspace.WorkspaceSnapshot(_WORKSPACE, row[0]))
    assert complete.bits == 78
    for field in range(8):
        changed = next(
            i for i, row in enumerate(rows) if row[0][field] != original[field]
        )
        reduced = workspace.workspace_model(
            "flowchart-without-" + _WORKSPACE.components[field],
            " ".join(
                name for i, name in enumerate(_WORKSPACE.components) if i != field
            ),
        )
        for mode in ("initial", "none", "schema", "constructor_none"):

            class Masked(native._Machine):
                _mask_index = 0

                def __init__(self, source, port, _field=field):
                    super().__init__(source, port)
                    self._mask_initial = super().workspace_snapshot().parts[_field]

                def workspace_snapshot(
                    self, _mode=mode, _field=field, _changed=changed, _reduced=reduced
                ):
                    saved = super().workspace_snapshot()
                    values = list(saved.parts)
                    if _mode == "constructor_none":
                        values[_field] = None
                    elif self._mask_index >= _changed:
                        if _mode == "schema":
                            del values[_field]
                            return workspace.WorkspaceSnapshot(_reduced, tuple(values))
                        values[_field] = (
                            self._mask_initial if _mode == "initial" else None
                        )
                    return workspace.WorkspaceSnapshot(saved.model, tuple(values))

            machine = Masked(list(case.rows), ScriptedIO(case.stdin))
            witness = workspace.WorkspaceWitness(_WORKSPACE)
            held = []
            for index, (row, io) in enumerate(zip(rows, ios, strict=True)):
                machine._mask_index = index
                assert _actual(machine, case) == row[0]
                _views(machine, row[0])
                assert machine.snapshot() == _cycle(row[0])
                assert (
                    machine.io.getvalue(),
                    machine.io.position(),
                    machine.io.progress(),
                ) == row[2:]
                assert (
                    machine.io.reads,
                    machine.io.past_end,
                    machine.io._character_reads,
                    machine.io._newline,
                ) == io
                capture = machine.workspace_snapshot()
                expected_parts = tuple(
                    None
                    if i == field and mode == "constructor_none"
                    else original[i]
                    if i == field and index >= changed and mode == "initial"
                    else None
                    if i == field and index >= changed and mode == "none"
                    else value
                    for i, value in enumerate(row[0])
                    if not (mode == "schema" and index >= changed and i == field)
                )
                expected_model = (
                    reduced if mode == "schema" and index >= changed else _WORKSPACE
                )
                assert capture == workspace.WorkspaceSnapshot(
                    expected_model, expected_parts
                )
                if mode == "schema":
                    if index < changed:
                        witness.sample(capture, expected_parts)
                    else:
                        with pytest.raises(ValueError, match="model changed"):
                            witness.measured.sample(capture)
                        with pytest.raises(AssertionError):
                            witness.expected.sample(capture)
                else:
                    witness.sample(capture, expected_parts)
                _hold(machine, held)
                if index + 1 < len(rows):
                    machine.step()
            if mode != "schema":
                witness.finish()
                loss = complete.bits - witness.measured.bits
                if mode in ("initial", "constructor_none"):
                    assert loss == complete.peaks[field]
                else:
                    assert loss == complete.peaks[field] - complete.width(
                        original[field]
                    )

        class Reduced(native._Machine):
            def workspace_snapshot(self, _field=field, _model=reduced):
                saved = super().workspace_snapshot()
                values = list(saved.parts)
                del values[_field]
                return workspace.WorkspaceSnapshot(_model, tuple(values))

        machine = Reduced(list(case.rows), ScriptedIO(case.stdin))
        consistent, held = workspace.WorkspaceWitness(reduced), []
        for index, (row, io) in enumerate(zip(rows, ios, strict=True)):
            assert _actual(machine, case) == row[0]
            _views(machine, row[0])
            assert machine.snapshot() == _cycle(row[0])
            assert (
                machine.io.getvalue(),
                machine.io.position(),
                machine.io.progress(),
            ) == row[2:]
            assert (
                machine.io.reads,
                machine.io.past_end,
                machine.io._character_reads,
                machine.io._newline,
            ) == io
            consistent.sample(
                machine.workspace_snapshot(),
                tuple(v for i, v in enumerate(row[0]) if i != field),
            )
            _hold(machine, held)
            if index + 1 < len(rows):
                machine.step()
        consistent.finish()
        assert complete.bits - consistent.measured.bits == complete.peaks[field]


def _fork_controls():
    for mode in ("newborn_records_fork", "parent_forgets_fork"):

        class WrongFork(native._Machine):
            def step(self, _mode=mode):
                original = native._Tick.fork

                def incorrect(tick, index):
                    before = tick.pointers[index]
                    size = len(tick.pointers)
                    key = before.row, tick.nodes[before.row, before.col][1]
                    original(tick, index)
                    if _mode == "newborn_records_fork":
                        for at in range(size, len(tick.pointers)):
                            child = tick.pointers[at]
                            tick.pointers[at] = replace(
                                child, memory=child.memory.leaving(key, child.d)
                            )
                    else:
                        parent = tick.pointers[index]
                        memory = dict(parent.memory._exits)
                        memory.pop(key, None)
                        tick.pointers[index] = replace(
                            parent, memory=native._Memory(memory)
                        )

                with pytest.MonkeyPatch.context() as patch:
                    patch.setattr(native._Tick, "fork", incorrect)
                    super().step()

        for case, cap in ((_fork_case(), 64), (_reentry_case(), 8)):
            with pytest.raises(AssertionError):
                _check(WrongFork, case, cap)
    case = _straight(("one", "write"))

    class ChangedNode(native._Machine):
        def __init__(self, source, port):
            super().__init__(source, port)
            for key, (kind, column) in tuple(self.nodes.items()):
                if kind == "[ }":
                    self.nodes[key] = ("{ ]", column)

    with pytest.raises(AssertionError):
        _check(ChangedNode, case)
    machine = ChangedNode(list(case.rows), ScriptedIO(""))
    for _ in range(8):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert machine.io.getvalue() == "\0"

    for setter, output in (("one", "\1"), ("zero", "\0"), ("empty", "\0")):
        case = _switch_case(setter)
        rows, _ios = _model(case)
        assert rows[-1][1]
        assert rows[-1][2] == output

    class ForgottenExit(native._Machine):
        def step(self):
            original = native._Memory.exit_from

            def forgotten(memory, cell):
                return None if cell == (4, 4) else original(memory, cell)

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(native._Memory, "exit_from", forgotten)
                super().step()

    case = _memory_case()
    with pytest.raises(AssertionError):
        _check(ForgottenExit, case, 8)
    machine = ForgottenExit(list(case.rows), ScriptedIO(""))
    for _ in range(3):
        machine.step()
    with pytest.raises(ValueError, match="no exit path"):
        machine.step()


def _sharing_control():
    case = _shared_case()
    rows, _ios = _model(case)
    assert rows[-1][1]
    assert rows[-1][2] == "\3"

    class IsolatedPush(native._Machine):
        def step(self):
            original = native._Tick.operate

            def private_queue(tick, spelling, pointer):
                if spelling != "\\[ ]/":
                    return original(tick, spelling, pointer)
                shared = tick.deques
                tick.deques = dict(shared)
                try:
                    return original(tick, spelling, pointer)
                finally:
                    tick.deques = shared

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(native._Tick, "operate", private_queue)
                super().step()

    with pytest.raises(AssertionError):
        _check(IsolatedPush, case)
    machine = IsolatedPush(list(case.rows), ScriptedIO(""))
    for _ in range(10):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert machine.io.getvalue() == "\1"


def _prepared(source, port):
    return native.prepare_machine(source, {})(port)


def _seed_refusal():
    class Unread:
        def read(self):
            raise AssertionError("input guard reached")

    source = "\n".join(_straight(("read", "write")).rows)
    with pytest.raises(ArgumentError) as caught:
        public_run("Flowchart", source, stdin=Unread(), seed=0)
    assert type(caught.value) is ArgumentError
    assert "draws no random values" in str(caught.value)
    with pytest.raises(AssertionError, match="input guard reached"):
        public_run("Flowchart", source, stdin=Unread())


def check_raw_flowchart():
    for case in _cases():
        for factory in (native._Machine, _prepared):
            _check(factory, case)
    for case, cap in _extra_cases():
        _check(native._Machine, case, cap)
    witness = _literal()
    _masks(witness)
    _failures()
    _fork_controls()
    _sharing_control()
    _seed_refusal()
