"""Finite source-authored stage, value, stack, condition and IO witnesses."""

import re

import pytest

from esolangs.languages.shakespeare.interpreter import _Machine, prepare_machine
from esolangs.runtime._state import WorkspaceSnapshot
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import reject_faults
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "shakespeare-v1", "instruction values stacks stage condition input_cursor"
)
_HEAD = (
    "T.\nRomeo, a man.\nJuliet, a woman.\nHamlet, a prince.\nAct I: A.\nScene I: S.\n"
)
_SOURCE = _HEAD + (
    "[Enter Romeo and Juliet]\nRomeo:\n"
    "You are a big rose. Remember a rose. Remember a big big rose.\n"
    "Am I worse than you? If so, Open your heart! If not, Speak your mind!\n"
    "Recall my past. Open your heart. Recall my sins. Open your heart.\n"
    "Open your mind. Listen to your heart. Open your heart.\n"
    "[Exit Juliet]\n[Enter Hamlet]\nRomeo:\nYou are a rose.\n"
)
# Independently authored semantic boundaries, not parsed production operations.
_PLAN = (
    ("enter", (0, 1), None),
    ("set", 2, None),
    ("push", 1, None),
    ("push", 4, None),
    ("ask", None, None),
    ("out", None, True),
    ("char_out", None, False),
    ("pop", None, None),
    ("out", None, None),
    ("pop", None, None),
    ("out", None, None),
    ("char_in", None, None),
    ("num_in", None, None),
    ("out", None, None),
    ("exit", 1, None),
    ("enter", (2,), None),
    ("set", 1, None),
)


def _number(stdin, cursor):
    while cursor < len(stdin) and stdin[cursor].isspace():
        cursor += 1
    if cursor == len(stdin):
        return None, cursor, "input"
    start = cursor
    while cursor < len(stdin) and not stdin[cursor].isspace():
        cursor += 1
    token = stdin[start:cursor]
    if re.fullmatch(r"[+-]?[0-9]+", token) is None:
        return None, cursor, "argument"
    return int(token), cursor, None


def _model(plan, stdin):
    pc = cursor = reads = past_end = 0
    values, stacks, stage, flag = [0] * 3, [[], [], []], [], False
    output, failure, trace = "", None, []

    def row():
        return (
            (
                pc,
                tuple(values),
                tuple(map(tuple, stacks)),
                tuple(stage),
                flag,
                reads,
                past_end,
            ),
            pc == len(plan),
            output,
            cursor,
            cursor,
        )

    trace.append(row())
    for kind, argument, condition in plan:
        target = next((who for who in stage if who != 0), None)
        if condition is not None and flag != condition:
            pc += 1
        elif kind == "enter":
            if len(stage) + len(argument) > 2:
                failure = "halt"
            else:
                stage.extend(argument)
                pc += 1
        elif kind == "exit":
            stage.remove(argument)
            pc += 1
        elif kind == "ask":
            flag = values[0] < values[target]
            pc += 1
        elif kind in ("char_in", "num_in"):
            if kind == "num_in":
                value, cursor, failure = _number(stdin, cursor)
            elif cursor == len(stdin):
                failure = "input"
            else:
                value = ord(stdin[cursor])
                cursor += 1
            if failure == "input":
                past_end += 1
            else:
                reads += 1
            if not failure:
                values[target] = value
                pc += 1
        elif kind == "set":
            values[target] = argument
            pc += 1
        elif kind == "push":
            stacks[target].append(argument)
            pc += 1
        elif kind == "pop":
            if not stacks[target]:
                failure = "halt"
            else:
                values[target] = stacks[target].pop()
                pc += 1
        else:
            assert kind in ("out", "char_out")
            output += str(values[target]) if kind == "out" else chr(values[target])
            pc += 1
        trace.append(row())
        if failure:
            break
    if not failure:
        trace.extend([row()] * 3)
    return failure, trace


def _view(machine):
    stacks = []
    for stack in machine.state.stacks:
        rest = stack
        items = []
        while rest is not None:
            value, rest = rest
            items.append(value)
        stacks.append(tuple(reversed(items)))
    state = machine.state
    return (
        state.pc,
        state.values,
        tuple(stacks),
        state.stage,
        state.flag,
        machine.io.reads,
        machine.io.past_end,
    )


def _parts(row):
    return (*row[0][:5], row[-1])


def _check(factory, source, plan, stdin):
    return workspace.agrees(
        _model(plan, stdin),
        (factory, source, stdin),
        (_WORKSPACE, _parts),
        _view,
        cap=32,
        context=(plan, stdin),
    )


def _isolation():
    expected = _model(_PLAN, "A -7")[1]
    left = _Machine(_SOURCE, ScriptedIO("A -7"))
    right = _Machine(_SOURCE, ScriptedIO("A -7"))
    held = []
    for machine, count in ((left, 6), (right, 9)):
        for index in range(count + 1):
            captured = machine.workspace_snapshot()
            predicted = WorkspaceSnapshot(_WORKSPACE, _parts(expected[index]))
            assert captured == predicted
            assert _view(machine) == expected[index][0]
            held.append((captured, predicted))
            if index != count:
                machine.step()
            assert all(before == reference for before, reference in held)
    assert left.workspace_snapshot() == WorkspaceSnapshot(
        _WORKSPACE, _parts(expected[6])
    )


def check_workspace_shakespeare():
    expected = _check(_Machine, _SOURCE, _PLAN, "A -7")
    assert expected[1][-1][2] == "241-7"
    initial = _parts(expected[1][0])
    assert all(
        any(_parts(row)[index] != initial[index] for row in expected[1])
        for index in range(len(_WORKSPACE.components))
    )
    for stdin in ("", "A ", "A nope"):
        _check(_Machine, _SOURCE, _PLAN, stdin)
    _check(
        _Machine,
        _SOURCE + "Recall my sins.\n",
        (*_PLAN, ("pop", None, None)),
        "A -7",
    )
    _check(
        _Machine,
        _HEAD + "[Enter Romeo and Juliet]\n[Enter Hamlet]\n",
        (_PLAN[0], ("enter", (2,), None)),
        "",
    )
    workspace.check_erasures(_WORKSPACE, _check, _Machine, _SOURCE, _PLAN, "A -7")
    reject_faults(
        _check,
        _Machine,
        workspace.missing_workspace(_Machine, "stacks"),
        _SOURCE,
        _PLAN,
        "A -7",
    )
    _isolation()

    class ErasedCounts(_Machine):
        def step(self):
            try:
                super().step()
            finally:
                self.io._reads = self.io._past_end = 0

    for stdin in ("", "A ", "A nope", "A -7"):
        with pytest.raises(AssertionError):
            _check(ErasedCounts, _SOURCE, _PLAN, stdin)
    _prepared_counters()


def _prepared_counters():
    expected = _model(_PLAN, "A -7")[1]
    build = prepare_machine(_SOURCE, {})
    siblings = (build(ScriptedIO("A -7")), build(ScriptedIO("A -7")))
    for machine, sibling in (siblings, siblings[::-1]):
        inactive = sibling.workspace_snapshot()
        checked = workspace.workspace_view(expected, _WORKSPACE, _parts, _view)
        for index, reference in enumerate(expected):
            if index:
                machine.step()
            assert (
                checked(machine),
                machine.halted,
                machine.io.getvalue(),
                machine.io.position(),
                machine.io.progress(),
            ) == reference
            assert sibling.workspace_snapshot() == inactive
