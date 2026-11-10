"""Full independent capture/IO boundary checks for the old one-row family."""

from dataclasses import fields, is_dataclass
from io import StringIO
from types import MappingProxyType

from esolangs.exceptions import HaltError, InputExhaustedError
from esolangs.languages.streetcode.interpreter import _Machine
from esolangs.languages.streetcode.interpreter.geometry import _Grid, _Latches, _State
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import ScriptedIO
from tests.support.workspace_oracle import WorkspaceWitness

from .full_oracle import Case, cases, parts, predict, witness

MODEL = WorkspaceModel(
    "streetcode-v1",
    ("steering", "pointer", "cells", "input_cursor", "stopped", "input_reads"),
)


def exact(left, right):
    """Reject bool/int and container substitutions at every declared leaf."""
    todo = [(left, right)]
    while todo:
        actual, expected = todo.pop()
        assert type(actual) is type(expected)
        if is_dataclass(expected):
            todo.extend(
                (getattr(actual, f.name), getattr(expected, f.name))
                for f in fields(expected)
            )
        elif isinstance(expected, (tuple, list)):
            assert len(actual) == len(expected)
            todo.extend(zip(actual, expected, strict=True))
        elif type(expected) is frozenset:
            assert actual == expected
            assert all(
                type(pair) is tuple
                and len(pair) == 2
                and all(type(x) is int for x in pair)
                for pair in actual
            )
        else:
            assert actual == expected


def io_state(port, row, stdin):
    """Check all eleven caller-owned fields, including failed-read phase flags."""
    values = vars(port).copy()
    assert type(values["_buffer"]) is StringIO
    assert values["_buffer"].closed is False
    values["_buffer"] = values["_buffer"].__getstate__()
    expected = {
        "_source": stdin,
        "_supplied": stdin.count("\n") + int(bool(stdin) and not stdin.endswith("\n")),
        "_offset": row.cursor,
        "_line_reads": 0,
        "_character_reads": row.character_reads,
        "_past_end": row.past_end,
        "_pending": "",
        "_reads": row.cursor,
        "_consumed": row.cursor,
        "_newline": row.newline,
        "_buffer": (row.output, "\n", len(row.output), None),
    }
    assert values.keys() == expected.keys()
    for name in expected:
        exact(values[name], expected[name])


def boundary(machine, port, case, row, meter, held):
    """Read full real state/metadata/capture without supplying predictor inputs."""
    pc, heading, pointer, cells, reads = row.state
    assert type(machine._state) is _State
    assert type(machine._state.latches) is _Latches
    expected_state = _State(0, pc, heading, _Latches(None, None, 0))
    exact(machine._state, expected_state)
    exact(machine.cp, pointer)
    assert type(machine.cells) in (dict, MappingProxyType)
    assert all(type(k) is int and type(v) is int for k, v in machine.cells.items())
    exact(tuple(sorted(machine.cells.items())), cells)
    exact(machine._done, row.halted)
    exact(machine._input_reads, reads)
    exact(machine.ip, (0, pc, "NESW".index(heading)))
    exact(
        machine.memory,
        []
        if not cells
        else [dict(cells).get(i, 0) for i in range(max(dict(cells)) + 1)],
    )
    assert type(machine.grid) is _Grid
    exact(tuple(machine.grid), (case.source,))
    exact(machine.grid.height, 1)
    exact(machine.grid.width, len(case.source))
    assert type(machine.grid._rows) is list
    exact(machine.grid._rows, [case.source])
    assert type(machine.grid._geometry) is dict
    assert machine._graph is None
    io_state(port, row, case.stdin)
    cycle = machine.snapshot()
    exact(
        cycle,
        (expected_state, pointer, cells, row.cursor, row.halted, reads, (case.source,)),
    )
    captured = machine.workspace_snapshot()
    expected = WorkspaceSnapshot(MODEL, parts(row))
    exact(captured, expected)
    meter.sample(captured, expected.parts)
    for saved, reference, old_cycle, old_hash in held:
        exact(saved, reference)
        assert hash(old_cycle) == old_hash
    held.append((captured, expected, cycle, hash(cycle)))


def check_case(case, factory=_Machine):
    """Compare all cap48 boundaries and exactly three post-halt idles."""
    error, rows = predict(case)
    port = ScriptedIO(case.stdin)
    machine = factory([case.source], port)
    meter, held = WorkspaceWitness(MODEL), []
    for index, row in enumerate(rows):
        caught = None
        if index:
            try:
                machine.step()
            except (HaltError, InputExhaustedError) as failure:
                caught = failure
        if index == len(rows) - 1 and error:
            assert type(caught) is (
                InputExhaustedError if error == "input" else HaltError
            )
            if error == "input":
                exact(
                    (caught.reads, caught.supplied, caught.unit),
                    (row.cursor, len(case.stdin), "character"),
                )
        else:
            assert caught is None
        boundary(machine, port, case, row, meter, held)
    meter.finish()
    return meter.measured.bits, len(rows)


def check_accounting_streetcode():
    """Retain all511 old cases, add six populated omissions and visited zero."""
    boundaries = 0
    for case in cases():
        _, count = check_case(case)
        boundaries += count
    case, _ = witness()
    bits, _ = check_case(case)
    assert bits == 35
    for field in range(6):
        touched = []

        class Missing(_Machine):
            def workspace_snapshot(self, field=field, touched=touched):
                touched.append(field)
                captured = super().workspace_snapshot()
                values = list(captured.parts)
                values[field] = None
                return WorkspaceSnapshot(captured.model, tuple(values))

        try:
            check_case(case, Missing)
        except AssertionError:
            assert touched == [field]
        else:
            raise AssertionError("populated omission accepted")
    # A visited zero remains an allocated semantic cell.
    zero = Case("C~^;", "")
    _, rows = predict(zero)
    assert rows[-1].state[3] == ((0, 0),)
    check_case(zero)
    return {
        "cases": 511,
        "boundaries": boundaries,
        "omissions": 6,
        "anchor_bits": 35,
        "visited_zero": 1,
    }


def check_complete_streetcode():
    """Keep every old case plus the declared populated junction phases."""
    from .junction_checks import controls

    check_accounting_streetcode()
    controls()
