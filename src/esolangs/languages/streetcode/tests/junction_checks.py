"""Real validated construction; independent local latch phases and readonly caches."""

from copy import deepcopy

from esolangs.languages.streetcode.interpreter import _Machine
from esolangs.languages.streetcode.interpreter.geometry import (
    _Car,
    _Grid,
    _Latches,
    _Merge,
    _Mouth,
    _State,
)
from esolangs.runtime._state import WorkspaceSnapshot
from esolangs.runtime.io import ScriptedIO
from tests.support.workspace_oracle import WorkspaceWitness

from .junction_oracle import CODE, parts, prefix
from .workspace_checks import MODEL, exact


def typed_state(state):
    """Admit only complete native immutable steering records."""
    assert type(state) is _State
    assert type(state.row) is int
    assert type(state.col) is int
    assert type(state.heading) is str
    assert state.heading in ("N", "E", "S", "W")
    latch = state.latches
    assert type(latch) is _Latches
    assert type(latch.skip_hug) is int
    assert latch.skip_hug >= 0
    assert latch.merging_heading is None or (
        type(latch.merging_heading) is str
        and latch.merging_heading in ("N", "E", "S", "W")
    )
    if latch.merge is not None:
        merge = latch.merge
        assert type(merge) is _Merge
        assert type(merge.target_row) is int
        assert type(merge.target_col) is int
        assert type(merge.turn) is str
        assert merge.turn in ("left", "right")
        assert type(merge.latched_heading) is str
        assert merge.latched_heading in ("N", "E", "S", "W")
        assert type(merge.crossing) is bool


def metadata_schema(machine):
    """Check complete cache/graph types, not independent expected geometry values."""
    assert type(machine._graph) is dict
    for state, edges in machine._graph.items():
        typed_state(state)
        assert type(edges) is dict
        assert len(edges) == 4
        assert set(edges) == {(0, 0), (0, 1), (1, 0), (1, 1)}
        for key, successor in edges.items():
            assert type(key) is tuple
            assert all(type(bit) is int for bit in key)
            typed_state(successor)  # This no-op drawing has no ';' halt edge.
    assert type(machine.grid._geometry) is dict
    for key, value in machine.grid._geometry.items():
        assert type(key) is tuple
        assert len(key) == 2
        name, arguments = key
        assert type(name) is str
        assert type(arguments) is tuple
        car = arguments[0]
        assert type(car) is _Car
        assert type(car.row) is int
        assert type(car.col) is int
        assert type(car.heading) is str
        assert car.heading in ("N", "E", "S", "W")
        if name in ("_open_toward", "_road_mouth", "_plus_dist"):
            assert len(arguments) == 2
            assert type(arguments[1]) is str
            assert arguments[1] in ("N", "E", "S", "W")
        else:
            assert len(arguments) == 1
        if name in ("_open_toward", "_crossing_mouth"):
            assert type(value) is bool
        elif name == "_road_mouth":
            assert value is None or (
                type(value) is _Mouth and all(type(part) is int for part in value)
            )
        elif name == "_plus_dist":
            assert value is None or type(value) is int
        elif name in ("_junction_shape", "_junction_kind"):
            assert type(value) is int
            assert value in (0, 3, 4)
        else:
            assert name == "_junction_choices"
            assert type(value) is list
            assert all(type(h) is str and h in ("N", "E", "S", "W") for h in value)


def trace(factory=_Machine):
    """Compare17 actual bounded steps, without pretending this loop halts."""
    predicted = prefix()
    port = ScriptedIO("")
    machine = factory(list(CODE), port)
    assert type(machine.grid) is _Grid
    assert type(machine._graph) is dict
    # These are full readonly metadata sidecars, NOT independent expected
    # graph/cache values. Every semantic steering prediction stays pure.
    graph, memo = deepcopy(machine._graph), deepcopy(machine.grid._geometry)
    witness, held = WorkspaceWitness(MODEL), []
    for index, row in enumerate(predicted):
        if index:
            machine.step()
        merge = None if row.merge is None else _Merge(*row.merge)
        expected_state = _State(
            row.row,
            row.col,
            row.heading,
            _Latches(merge, row.merging_heading, row.skip_hug),
        )
        exact(machine._state, expected_state)
        exact(
            (
                machine.cp,
                tuple(sorted(machine.cells.items())),
                machine._input_reads,
                machine.halted,
            ),
            (0, (), 0, False),
        )
        exact(tuple(machine.grid), CODE)
        exact((machine.grid.height, machine.grid.width), (8, 9))
        assert machine._graph == graph
        assert machine.grid._geometry == memo
        metadata_schema(machine)
        assert expected_state in graph
        exact(machine.snapshot(), (expected_state, 0, (), 0, False, 0, CODE))
        expected_io = {
            "_source": "",
            "_supplied": 0,
            "_offset": 0,
            "_line_reads": 0,
            "_character_reads": False,
            "_past_end": 0,
            "_pending": "",
            "_reads": 0,
            "_consumed": 0,
            "_newline": False,
            "_buffer": ("", "\n", 0, None),
        }
        actual_io = vars(port).copy()
        actual_io["_buffer"] = actual_io["_buffer"].__getstate__()
        assert actual_io.keys() == expected_io.keys()
        for name in expected_io:
            exact(actual_io[name], expected_io[name])
        actual = machine.workspace_snapshot()
        wanted = WorkspaceSnapshot(MODEL, parts(row))
        exact(actual, wanted)
        witness.sample(actual, wanted.parts)
        for saved, reference in held:
            exact(saved, reference)
        held.append((actual, wanted))
    witness.finish()
    assert witness.expected.peaks == [57, 1, 0, 1, 1, 1]
    assert witness.expected.written == [True, False, False, False, False, False]
    assert witness.measured.bits == 57
    return machine


def controls():
    """Three actual latent-field erasures, and two real readonly geometry futures."""
    trace()
    for field in range(3):
        touched = []

        class Missing(_Machine):
            def workspace_snapshot(self, field=field, touched=touched):
                saved = super().workspace_snapshot()
                values = list(saved.parts)
                steering = list(values[0])
                latches = list(steering[3])
                if latches[field] not in (None, 0):
                    touched.append(field)
                latches[field] = None if field < 2 else 0
                steering[3] = tuple(latches)
                values[0] = tuple(steering)
                return WorkspaceSnapshot(saved.model, tuple(values))

        try:
            trace(Missing)
        except AssertionError:
            assert touched == [field]
        else:
            raise AssertionError("active latch omission accepted")
    for kind in ("drawing", "compiled-edge"):
        machine = _Machine(list(CODE), ScriptedIO(""))
        capture = machine.workspace_snapshot()
        before = deepcopy(machine._graph)
        if kind == "drawing":
            machine.grid[2] = machine.grid[2].replace("C", ";")
            assert tuple(machine.grid) != CODE
        else:
            machine._graph[machine._state][(0, 0)] = "halt"
            assert machine._graph != before
        exact(machine.workspace_snapshot(), capture)
        machine.step()
        assert machine.halted is True
        assert (machine.row, machine.col) == (2, 1)
    return {
        "natural_prefixes": 1,
        "boundaries": 18,
        "active_latch_omissions": 3,
        "readonly_geometry_futures": 2,
        "steering_bits": 57,
    }
