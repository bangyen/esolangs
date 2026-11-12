"""Reference expansion of signed stack paths before final aggregation."""

import random
import sys
from collections import Counter
from itertools import product
from typing import NamedTuple
from unittest.mock import patch

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.caballo.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.randomness import Seeded
from tests.interpreters.oracle_support import observed
from tests.support import workspace_oracle as workspace

from .full_oracle import _full_model, _full_parts


def _trim(cells):
    while cells and not cells[-1]:
        cells.pop()
    return tuple(cells)


def _primitive(op, stack):
    cells = list(stack) or [0]
    if op == "p":
        del cells[0]
    elif op == "q":
        cells.insert(0, 0)
    elif op in "id":
        cells[0] += 1 if op == "i" else -1
        if cells[0] < 0:
            return None
    else:
        index = int(op) - 1
        cells.extend([0] * (index + 1 - len(cells)))
        cells[index], cells[0] = cells[0], cells[index]
    return _trim(cells)


def _paths(program, paths):
    for op in program:
        if isinstance(op, tuple):
            paths = [path for branch in op for path in _paths(branch, paths)]
        elif isinstance(op, list):
            layer = paths
            for _ in range(16):
                layer = _paths(op, layer)
                if not layer:
                    break
                paths = paths + layer
            else:
                raise AssertionError("oracle loop bound exceeded")
        elif op == "0":
            return []
        elif op == "-":
            paths = [(stack, -sign) for stack, sign in paths]
        else:
            paths = [
                (moved, sign)
                for stack, sign in paths
                if (moved := _primitive(op, stack)) is not None
            ]
    return paths


def _source(program):
    return "".join(
        "(" + "+".join(map(_source, op)) + ")"
        if isinstance(op, tuple)
        else "[" + _source(op) + "]"
        if isinstance(op, list)
        else op
        for op in program
    )


class _Ticket:
    def __init__(self, ticket):
        self.ticket = ticket
        self.bounds = []

    def randbelow(self, bound):
        self.bounds.append(bound)
        return self.ticket


def _check(factory, program, seed):
    expected = Counter()
    for stack, sign in _paths(program, [(_trim(list(seed)), 1)]):
        expected[stack] += sign
    expected = {stack: weight for stack, weight in expected.items() if weight}
    draws = [stack for stack, weight in sorted(expected.items()) for _ in range(weight)]
    for ticket, chosen in enumerate(draws or [None]):
        io = ScriptedIO(" ".join(map(str, seed)))
        rng = _Ticket(ticket)
        machine = factory(_source(program), io, rng)
        for _ in range(256):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert dict(machine.state.mapping) == expected
        answer = "" if chosen is None else "[" + ",".join(map(str, chosen)) + "]"
        machine.step()
        assert io.getvalue() == answer
        assert rng.bounds == ([len(draws)] if len(set(draws)) > 1 else [])
        _check_full(factory, _source(program), " ".join(map(str, seed)), ticket=ticket)


def check_raw_caballo():
    commands = "pqid1234567890-"
    for pair, seed in product(product(commands, repeat=2), ((), (0, 2), (3, 1, 0))):
        _check(_Machine, pair, seed)
    for program, seed in product(
        ((("i", "q", "i"),), (("i", "i-", "q"),), (["d"],), (list("d2i2"), "p")),
        ((), (2, 1), (3, 0, 2)),
    ):
        _check(_Machine, program, seed)

    class MissingOutput(_Machine):
        def _output(self):
            pass

    with pytest.raises(AssertionError):
        _check(MissingOutput, "i", ())
    _check_full_cases()
    _check_writer_phase()
    _check_resource_literals()
    _check_seeded_routes()
    _check_public_randomness()
    _check_physical_write()
    _check_provider_refusal()
    _check_host_limit()


_FULL_WORKSPACE = workspace.workspace_model(
    "caballo-v1", "frames distribution stopped input_cursor"
)


class _CountedDraw:
    def __init__(self, ticket):
        self.ticket = ticket
        self.bounds, self.used = ([], [])

    def randbelow(self, bound):
        self.bounds.append(bound)
        self.used.append(self.ticket)
        return self.ticket


def _check_full(factory, source, stdin, *, ticket=0, cap=256):
    error, trace, constructor_io, program = _full_model(
        source, stdin, cap=cap, ticket=ticket
    )
    rng = _CountedDraw(ticket)

    def build(code, io):
        try:
            machine = factory(code, io, rng)
        finally:
            _exact_value((io.progress(), io.reads, io.past_end), constructor_io)
        _exact_value(machine.program, program)
        return machine

    expected = iter(trace)

    def state(machine):
        row = next(expected)
        assert machine.snapshot() == (*row[0][:3], row[-1])
        assert machine.stack == [frame[0] for frame in row[0][0]]
        assert machine.memory == list(row[0][1])
        actual = (
            *machine.state,
            machine.done,
            tuple(rng.bounds),
            tuple(rng.used),
            machine.io.reads,
            machine.io.past_end,
        )
        _exact_value(actual, row[0])
        return actual

    checked = workspace.workspace_view(trace, _FULL_WORKSPACE, _full_parts, state)
    assert observed(build, source, stdin, checked, cap=cap) == (error, trace)
    return (error, trace)


def _check_full_cases():
    for source, stdin in (
        ("", ""),
        (" () \n", "2 1 0\n"),
        ("(i|ii)", ""),
        ("(i+i)[d]", "2"),
        ("0([i]+q)", "1"),
        ("[(d+0)]", "3"),
        ("[-]", "1"),
        ("[]", ""),
        ("(", "2"),
        ("([)]", "2"),
        ("+", "2"),
        ("?", "2"),
        ("i", "-1"),
        ("i", "1_0"),
        ("i", "\u0661"),
    ):
        _check_full(_Machine, source, stdin)
    assert not _full_model("[-]", "1")[1][-1][1]
    for source, bits in (("", 27), ("i", 29), ("0", 28)):
        _, rows = _check_full(_Machine, source, "")
        assert workspace.charged_bits(_FULL_WORKSPACE, map(_full_parts, rows)) == bits
    for ticket in (0, 1):
        _check_full(_Machine, "(i+ii)", "", ticket=ticket)

    class SkipCursor(_Machine):
        def step(self):
            super().step()
            if self.state.frames:
                frame = self.state.frames[-1]
                self.state = self.state._replace(
                    frames=(*self.state.frames[:-1], (*frame[:2], frame[2] + 1))
                )

    with pytest.raises(AssertionError):
        _check_full(SkipCursor, "ii", "")
    source, stdin = ("(i+i)[d]", "2")
    error, trace, _, _ = _full_model(source, stdin, ticket=0)
    assert error is None
    assert trace[-1][1]
    initial = _full_parts(trace[0])
    assert [
        any(_full_parts(row)[i] != initial[i] for row in trace) for i in range(4)
    ] == [True, True, True, False]
    for index in range(4):

        class Frozen(_Machine):
            def workspace_snapshot(self, _index=index):
                snapshot = super().workspace_snapshot()
                parts = list(snapshot.parts)
                parts[_index] = None if _index == 3 else initial[_index]
                return type(snapshot)(snapshot.model, tuple(parts))

        with pytest.raises(AssertionError):
            _check_full(Frozen, source, stdin)


def _check_writer_phase():
    from esolangs import ProgramArtifact
    from esolangs.debugger import make_debugger
    from esolangs.vm import _capture_workspace

    error, trace, _, _ = _full_model("i", "2", writer_prefix=2, idle_after_failure=2)
    assert error == "writer"
    failed_at = next((i for i, row in enumerate(trace) if row[1]))
    for route in ("raw", "debug"):
        if route == "raw":
            io = ScriptedIO("2")
            machine = _Machine("i", io, _CountedDraw(0))
        else:
            machine = make_debugger(
                "Caballo", ProgramArtifact("i", "Caballo"), stdin="2", seed=0
            )
            io = machine.vm._io
        write = io.print_str

        def interrupted(text, _write=write):
            _write(text[:2])
            raise HaltError("controlled writer interruption")

        io.print_str = interrupted
        captured = []
        for index, row in enumerate(trace):
            if index:
                try:
                    machine.step()
                except HaltError:
                    assert index == failed_at
                else:
                    assert index != failed_at
            snapshot = (
                machine.workspace_snapshot()
                if route == "raw"
                else _capture_workspace(machine.vm)
            )
            reference = _FULL_WORKSPACE.capture(
                **dict(zip(_FULL_WORKSPACE.components, _full_parts(row), strict=True))
            )
            assert snapshot == reference
            assert (io.getvalue(), io.progress(), io.reads, io.past_end) == (
                row[2],
                1,
                1,
                0,
            )
            assert all((saved == expected for saved, expected in captured))
            captured.append((snapshot, reference))
            if route == "debug":
                assert machine.result.steps == min(index, failed_at - 1)
                assert machine.result.completion is None


class _Capture(NamedTuple):
    row: tuple
    workspace: object
    cycle: tuple
    rng_state: object


def _captured(raw, bounds, draws):
    return _Capture(
        (
            (
                *raw.state,
                raw.done,
                tuple(bounds),
                tuple(draws),
                raw.io.reads,
                raw.io.past_end,
            ),
            raw.halted,
            raw.io.getvalue(),
            raw.io.position(),
            raw.io.progress(),
        ),
        raw.workspace_snapshot(),
        raw.snapshot(),
        None if raw._rng is None else raw._rng._random.getstate(),
    )


def _check_capture(captured, row, witness, held):
    _exact_value(captured.row, row)
    _exact_value(captured.workspace.parts, _full_parts(row))
    assert captured.cycle == (*row[0][:3], row[-1])
    witness.sample(captured.workspace, _full_parts(row))
    held.append(
        (
            captured.workspace,
            hash(captured.workspace),
            captured.cycle,
            hash(captured.cycle),
        )
    )
    assert all(
        hash(saved) == digest and hash(cycle) == cycle_hash
        for saved, digest, cycle, cycle_hash in held
    )


def _audit_draw(provider, bounds, draws):
    original = provider.randbelow

    def audit(upper):
        value = original(upper)
        bounds.append(upper)
        draws.append(value)
        return value

    provider.randbelow = audit


def _check_resource_literals():
    for source, stdin, bits in (
        ("i", "0", 29),
        ("i", "65", 35),
        ("i", "255", 37),
        ("q", "1", 30),
    ):
        _, rows = _check_full(_Machine, source, stdin)
        assert workspace.charged_bits(_FULL_WORKSPACE, map(_full_parts, rows)) == bits
    workspace.check_erasures(_FULL_WORKSPACE, _check_full, _Machine, "(i+i)[d]", "2")

    class WrongUpper(_Machine):
        def __init__(self, source, io, rng):
            super().__init__(source, io, rng)
            original = rng.randbelow
            rng.randbelow = lambda upper: original(upper + 1)

    with pytest.raises(AssertionError):
        _check_full(WrongUpper, "(i+i+ii)", "")

    class IntegerStop(_Machine):
        def step(self):
            super().step()
            if self.done:
                self.done = 1

    with pytest.raises(AssertionError):
        _check_full(IntegerStop, "i", "")


def _seeded_machine(route, source, stdin, seed):
    from esolangs import ProgramArtifact
    from esolangs.debugger import make_debugger
    from esolangs.languages.caballo.interpreter import prepare_machine
    from esolangs.vm import make_vm

    if route in ("raw", "prepared"):
        provider = Seeded(seed)
        io = ScriptedIO(stdin)
        if route == "raw":
            machine = _Machine(source, io, provider)
        else:
            options = {"rng": provider}
            factory = prepare_machine(source, options)
            options["rng"] = Seeded(seed + 1)
            machine = factory(io)
        return machine, machine, provider
    factory = make_debugger if route == "debug" else make_vm
    machine = factory(
        "Caballo", ProgramArtifact(source, "Caballo"), stdin=stdin, seed=seed
    )
    vm = machine.vm if route == "debug" else machine
    return machine, vm._machine, vm._machine._rng


def _check_seeded_routes():
    for source, stdin in (("", ""), ("(i+i+ii)", ""), ("(i-i)", ""), ("[-]", "1")):
        for seed in (0, 1):
            error, rows, _, program = _full_model(source, stdin, seed=seed)
            assert error is None
            for route in ("raw", "prepared", "vm", "debug"):
                machine, raw, provider = _seeded_machine(route, source, stdin, seed)
                assert type(provider) is Seeded
                assert raw._rng is provider
                assert raw.program == program
                bounds, draws, held = [], [], []
                _audit_draw(provider, bounds, draws)
                witness = workspace.WorkspaceWitness(_FULL_WORKSPACE)
                expected_rng = random.Random(seed)
                consumed = 0
                for index, row in enumerate(rows):
                    if index:
                        machine.step()
                    while consumed < len(row[0][3]):
                        value = expected_rng.randrange(row[0][3][consumed])
                        assert value == row[0][4][consumed]
                        consumed += 1
                    capture = _captured(raw, bounds, draws)
                    _check_capture(capture, row, witness, held)
                    assert capture.rng_state == expected_rng.getstate()
                    assert raw._rng is provider
                    assert raw.memory == list(row[0][1])
                    assert raw.stack == [frame[0] for frame in row[0][0]]
                    assert raw.io._newline is bool(row[2])
                witness.finish()


def _active_rows(rows):
    index = next(i for i, row in enumerate(rows) if row[1])
    return rows[: index + 1]


def _public_prediction(source, stdin, options):
    if options == {}:
        # Every ticket alternative is computed before the real secrets call.
        return [
            _active_rows(_full_model(source, stdin, ticket=ticket)[1])
            for ticket in range(3)
        ]
    return [_active_rows(_full_model(source, stdin, seed=options.get("seed", 0))[1])]


def _check_public_randomness():
    from esolangs import ProgramArtifact, run
    from esolangs.languages.caballo import interpreter as native
    from esolangs.runtime import randomness

    source, stdin = "(i+i+ii)", ""
    for options in ({}, {"seed": 1}, {"max_steps": 256}):
        expected = _public_prediction(source, stdin, options)
        created, captures, bounds, draws = [], [], [], []
        original_init, original_step = native._Machine.__init__, native._Machine.step
        original_secret = randomness.secrets.randbelow

        def audit_secret(
            upper, _original=original_secret, _bounds=bounds, _draws=draws
        ):
            value = _original(upper)
            _bounds.append(upper)
            _draws.append(value)
            return value

        def initialize(
            self,
            *args,
            _init=original_init,
            _options=options,
            _bounds=bounds,
            _draws=draws,
            _created=created,
            _captures=captures,
            **kwargs,
        ):
            _init(self, *args, **kwargs)
            if _options:
                assert type(self._rng) is Seeded
                _audit_draw(self._rng, _bounds, _draws)
            else:
                assert self._rng is None
            _created.append(self)
            _captures.append(_captured(self, _bounds, _draws))

        def step(
            self, _step=original_step, _captures=captures, _bounds=bounds, _draws=draws
        ):
            try:
                return _step(self)
            finally:
                _captures.append(_captured(self, _bounds, _draws))

        with (
            patch.object(native._Machine, "__init__", initialize),
            patch.object(native._Machine, "step", step),
            patch.object(randomness.secrets, "randbelow", audit_secret),
        ):
            # No timeout: a timed run executes in a worker, out of these patches.
            result = run(
                "Caballo", ProgramArtifact(source, "Caballo"), stdin=stdin, **options
            )
        assert len(created) == 1
        assert any([capture.row for capture in captures] == rows for rows in expected)
        assert bounds == [3]
        assert len(draws) == 1
        assert 0 <= draws[0] < 3
        selected = next(
            rows for rows in expected if [capture.row for capture in captures] == rows
        )
        witness = workspace.WorkspaceWitness(_FULL_WORKSPACE)
        held = []
        for capture, row in zip(captures, selected, strict=True):
            _check_capture(capture, row, witness, held)
        witness.finish()
        assert result.output == selected[-1][2]
        assert result.completion.kind.value == "halted"
        assert result[1:4] == (0, 1, 0)
        assert result.steps == (len(selected) - 1 if "max_steps" in options else None)
        if options:
            expected_rng = random.Random(options.get("seed", 0))
            for capture, row in zip(captures, selected, strict=True):
                if row[0][3] and capture is captures[-1]:
                    assert expected_rng.randrange(3) == row[0][4][0]
                assert capture.rng_state == expected_rng.getstate()
        else:
            assert all(capture.rng_state is None for capture in captures)


def _check_physical_write():
    from esolangs import ProgramArtifact, ProgramError
    from esolangs.debugger import make_debugger

    for route in ("raw", "debug"):
        for count in (0, 2):
            _, rows, _, _ = _full_model(
                "i", "2", writer_prefix=count, idle_after_failure=2
            )
            failed_at = next(i for i, row in enumerate(rows) if row[1])
            if route == "raw":
                machine = _Machine("i", ScriptedIO("2"), Seeded(0))
                raw = machine
            else:
                machine = make_debugger(
                    "Caballo", ProgramArtifact("i", "Caballo"), stdin="2", seed=0
                )
                raw = machine.vm._machine
            original = raw.io._write
            writes = []

            def fail(value, _writes=writes, _count=count, _original=original):
                assert type(value) is str
                assert value == "[3]"
                _writes.append(value)
                if _count:
                    _original(value[:_count])
                raise ValueError("controlled physical refusal")

            witness = workspace.WorkspaceWitness(_FULL_WORKSPACE)
            held = []
            with patch.object(raw.io, "_write", fail):
                for index, row in enumerate(rows):
                    if index == failed_at:
                        expected_error = ValueError if route == "raw" else ProgramError
                        with pytest.raises(expected_error) as caught:
                            machine.step()
                        assert type(caught.value) is expected_error
                    elif index:
                        machine.step()
                    _check_capture(_captured(raw, [], []), row, witness, held)
                    assert raw.io._newline is False
                    if route == "debug":
                        assert machine.result.steps == min(index, failed_at - 1)
                        assert machine.result.completion is None
                assert writes == ["[3]"]
            witness.finish()


def _exact_value(actual, expected):
    pending = [(actual, expected)]
    while pending:
        actual, expected = pending.pop()
        assert type(actual) is type(expected)
        if isinstance(expected, (tuple, list)):
            assert len(actual) == len(expected)
            pending.extend(zip(actual, expected, strict=True))
        else:
            assert actual == expected


def _draw_failure_rows(source, stdin):
    _, rows, _, _ = _full_model(source, stdin, ticket=0)
    failed_at = next(i for i, row in enumerate(rows) if row[1])
    terminal = rows[failed_at]
    # Finishing commits the model state before asking the provider for a value.
    state = (*terminal[0][:4], (), *terminal[0][5:])
    failed = (state, True, rows[failed_at - 1][2], terminal[3], terminal[4])
    return [*rows[:failed_at], failed, failed, failed], failed_at


def _check_provider_refusal():
    from esolangs import ProgramError

    source, stdin = "(i+ii)", ""
    rows, failed_at = _draw_failure_rows(source, stdin)
    for route in ("raw", "prepared", "vm", "debug"):
        machine, raw, provider = _seeded_machine(route, source, stdin, 0)
        initial = random.Random(0).getstate()
        bounds, held = [], []

        def refuse(upper, _bounds=bounds):
            _bounds.append(upper)
            raise ValueError("controlled provider refusal")

        witness = workspace.WorkspaceWitness(_FULL_WORKSPACE)
        with patch.object(provider, "randbelow", refuse):
            for index, row in enumerate(rows):
                if index == failed_at:
                    expected = (
                        ValueError if route in ("raw", "prepared") else ProgramError
                    )
                    with pytest.raises(expected) as caught:
                        machine.step()
                    assert type(caught.value) is expected
                elif index:
                    machine.step()
                capture = _captured(raw, bounds, [])
                _check_capture(capture, row, witness, held)
                assert capture.rng_state == initial
                assert raw._rng is provider
                assert raw.io._newline is False
                if route == "debug":
                    assert machine.result.steps == min(index, failed_at - 1)
                    assert machine.result.completion is None
            assert bounds == [2]
        witness.finish()


def _check_host_limit():
    limit = sys.get_int_max_str_digits()
    digits = limit or 5000
    error, rows = _check_full(_Machine, "i", "9" * digits)
    assert error == ("syntax" if limit else None)
    assert rows[-1][1] is True
    error, _ = _check_full(_Machine, "i", "0" * (digits + 1) + "65")
    assert error == ("syntax" if limit else None)
    assert sys.get_int_max_str_digits() == limit
