"""Finite independent INTERCAL workspace, tape and control-flow witnesses."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.intercal.interpreter import _Machine, prepare_machine
from esolangs.runtime._state import WorkspaceSnapshot
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import observed
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "intercal-v1",
    "instruction scalars arrays ignored stashes abstentions returns last_input "
    "last_output input_cursor",
)
_KEY = (".", 1)
_ARRAY = (",", 1)
_LINES = (
    ".1 <- #1",
    "STASH .1",
    "IGNORE .1",
    ".1 <- #2",
    "REMEMBER .1",
    "RETRIEVE .1",
    ",1 <- #2",
    "WRITE IN ,1",
    "READ OUT ,1",
    "ABSTAIN FROM (10)",
    "REINSTATE (10)",
    "(10) .1 <- #3",
    "(20) NEXT",
    "READ OUT .1",
    "GIVE UP",
    "(20) .1 <- #4",
    "RESUME #1",
)


def _source(*, failed=False):
    lines = []
    for index, line in enumerate(_LINES):
        text = line
        prefix = "PLEASE " if index < len(_LINES) // 3 else "DO "
        if index in (11, 15):
            label, text = text.split(" ", 1)
            prefix = label + " " + prefix
        if failed and index == 14:
            text = "RETRIEVE .2"
        lines.append(prefix + text)
    return "\n".join(lines)


def _parts(row):
    return (*row[0][:9], row[-1])


def _view(machine):
    state = machine.state

    def array(value):
        if isinstance(value, int):
            return value
        dimensions, cells = value
        return dimensions, frozenset(cells.items())

    return (
        state.ind,
        frozenset(state.scalars.items()),
        frozenset(
            (key, dims, frozenset(data.items()))
            for key, (dims, data) in state.arrays.items()
        ),
        state.ignored,
        frozenset(
            (key, tuple(map(array, stash))) for key, stash in state.stashes.items()
        ),
        state.abstained,
        state.nexts,
        state.last_in,
        state.last_out,
        machine.io.reads,
        machine.io.past_end,
    )


def observe_scalar(factory, source, stdin, view, expected):
    predictions = iter(enumerate(expected[1]))
    witness = workspace.WorkspaceWitness(_WORKSPACE)

    def capture(machine):
        index, row = next(predictions)
        state = row[0]
        parts = (
            state[0],
            state[1],
            frozenset(state[2]),
            state[3],
            frozenset(state[4]),
            *state[5:],
            row[-1],
        )
        witness.sample(machine.workspace_snapshot(), parts)
        consumed = stdin[: row[3]]
        reads = consumed.count("\n") + int(
            bool(consumed) and not consumed.endswith("\n")
        )
        past_end = int(expected[0] == "input" and index == len(expected[1]) - 1)
        assert (machine.io.reads, machine.io.past_end) == (reads, past_end)
        return view(machine)

    result = observed(factory, source, stdin, capture, cap=16)
    witness.finish()
    return result


def _tape(stdin):
    cells, previous, cursor, past_end = {}, 0, 0, 0
    for index in range(2):
        if cursor == len(stdin):
            value, previous = 256, -1
            past_end += 1
        else:
            character = ord(stdin[cursor])
            value, previous = (character - previous) % 256, character
            cursor += 1
        cells[index] = value
    return frozenset(cells.items()), previous, cursor, past_end


def _rich_model(stdin, *, failed=False):
    scalars, arrays, ignored, stashes = {}, frozenset(), set(), {}
    abstentions, returns = [0] * len(_LINES), ()
    pc = last_in = last_out = cursor = reads = past_end = 0
    output, trace = "", []

    def row():
        state = (
            pc,
            frozenset(scalars.items()),
            arrays,
            frozenset(ignored),
            frozenset(stashes.items()),
            tuple(abstentions),
            returns,
            last_in,
            last_out,
            reads,
            past_end,
        )
        return state, pc == len(_LINES), output, cursor, cursor

    trace.append(row())
    # This named program visits each statement once, including its NEXT body.
    for instruction in (*range(13), 15, 16, 13, 14):
        assert pc == instruction
        if instruction == 0:
            scalars[_KEY] = 1
        elif instruction == 1:
            stashes[_KEY] = (scalars[_KEY],)
        elif instruction == 2:
            ignored.add(_KEY)
        elif instruction == 3:
            assert _KEY in ignored  # ignored writes retain the old value
        elif instruction == 4:
            ignored.remove(_KEY)
        elif instruction == 5:
            scalars[_KEY], stashes[_KEY] = stashes[_KEY][-1], stashes[_KEY][:-1]
        elif instruction == 6:
            arrays = frozenset({(_ARRAY, (2,), frozenset())})
        elif instruction == 7:
            cells, last_in, cursor, past_end = _tape(stdin)
            reads = cursor
            arrays = frozenset({(_ARRAY, (2,), cells)})
        elif instruction == 8:
            for _, _, cells in arrays:
                for _, value in sorted(cells):
                    last_out = (last_out - value) % 256
                    output += chr(int(f"{last_out:08b}"[::-1], 2))
        elif instruction in (9, 10):
            abstentions[11] = int(instruction == 9)
        elif instruction in (11, 15):
            scalars[_KEY] = 3 if instruction == 11 else 4
        elif instruction == 12:
            returns, pc = ((13, 12),), 15
            trace.append(row())
            continue
        elif instruction == 16:
            returns, pc = (), 13
            trace.append(row())
            continue
        elif instruction == 13:
            output += "IV\n"
        elif failed:
            return "halt", [*trace, row()]
        else:
            pc = len(_LINES)
            trace.append(row())
            return None, trace + [row()] * 3
        pc += 1
        trace.append(row())
    raise AssertionError("named plan did not finish")


def _check_rich(factory, stdin="AB", *, failed=False):
    return workspace.agrees(
        _rich_model(stdin, failed=failed),
        (factory, _source(failed=failed), stdin),
        (_WORKSPACE, _parts),
        _view,
        cap=32,
    )


def _histories():
    source, expected = _source(), _rich_model("AB")[1]
    factory = prepare_machine(source, {})
    machines = (
        _Machine(source, ScriptedIO("AB")),
        factory(ScriptedIO("AB")),
        factory(ScriptedIO("AB")),
    )
    witnesses = [workspace.WorkspaceWitness(_WORKSPACE) for _ in machines]
    held = []
    for index, row in enumerate(expected):
        for machine, witness in zip(machines, witnesses, strict=True):
            if index:
                machine.step()
            capture = machine.workspace_snapshot()
            witness.sample(capture, _parts(row))
            assert (
                _view(machine),
                machine.halted,
                machine.io.getvalue(),
                machine.io.position(),
                machine.io.progress(),
            ) == row
            held.append((capture, WorkspaceSnapshot(_WORKSPACE, _parts(row))))
            assert all(capture == reference for capture, reference in held)
    for witness in witnesses:
        witness.finish()


def _output_failure():
    class BrokenIO(ScriptedIO):
        def print_str(self, text):
            super().print_str(text[:1])
            raise HaltError("witness output failure")

    machine = _Machine(_source(), BrokenIO("AB"))
    expected = _rich_model("AB")[1]
    witness = workspace.WorkspaceWitness(_WORKSPACE)
    for index in range(9):
        if index:
            machine.step()
        witness.sample(machine.workspace_snapshot(), _parts(expected[index]))
    with pytest.raises(HaltError) as caught:
        machine.step()
    assert type(caught.value) is HaltError
    assert caught.value.args == ("witness output failure",)
    # The shell commits the transition before flushing its output effect.
    witness.sample(machine.workspace_snapshot(), _parts(expected[9]))
    assert _view(machine) == expected[9][0]
    assert (machine.io.getvalue(), machine.io.position(), machine.io.progress()) == (
        expected[9][2][:1],
        2,
        2,
    )
    witness.finish()


def check_workspace_intercal():
    expected = _check_rich(_Machine)
    initial = _parts(expected[1][0])
    assert all(
        any(_parts(row)[index] != initial[index] for row in expected[1])
        for index in range(len(_WORKSPACE.components))
    )
    for stdin in ("", "A"):
        _check_rich(_Machine, stdin)
    _check_rich(_Machine, "AB", failed=True)
    workspace.check_erasures(_WORKSPACE, _check_rich, _Machine)
    _histories()
    _output_failure()
