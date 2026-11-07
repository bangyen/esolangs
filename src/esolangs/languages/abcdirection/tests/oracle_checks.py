"""Complex-coordinate grid walk and exact silent-cycle witness."""

from collections import deque
from random import Random

import pytest

from esolangs.languages.abcdirection.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import stalled
from tests.support.workspace_oracle import (
    WorkspaceWitness,
    missing_workspace,
    workspace_model,
)

_WORKSPACE = workspace_model(
    "abcdirection-v1",
    "control tape queue incoming outgoing input_cursor "
    "cycle_anchor cycle_power cycle_length stopped",
)

_HEADINGS = (1, 1j, -1, -1j)


def _data(tape, queue, incoming, cursor, outgoing, output):
    return (
        frozenset(tape),
        tuple(queue),
        tuple(incoming),
        cursor,
        tuple(outgoing),
        len(output),
    )


def _control(key):
    pos, direction, cell = key
    return int(pos.real), int(pos.imag), _HEADINGS.index(direction), cell


def _buffer(bits):
    return sum(bit << i for i, bit in enumerate(bits)), len(bits)


def _cycle(phase, key, before, after):
    anchor, valid, power, length, _ = phase
    valid &= before[2:4] == after[2:4]
    if before[:2] + before[4:] != after[:2] + after[4:]:
        return key, True, 1, 1, False
    if key == anchor and valid:
        return anchor, valid, power, length, True
    if length == power:
        return key, True, 2 * power, 1, False
    return anchor, valid, power, length + 1, False


def _check(factory, grid, stdin):
    io = ScriptedIO(stdin)
    machine = factory("\n".join([*grid, "ignored"]), io)
    position, heading = 0j, 1j
    address = cursor = 0
    tape = set()
    queue, incoming, outgoing = deque(), deque(), []
    output = ""
    seen = set()
    repeat = False
    phase = ((position, heading, address), True, 1, 1, False)
    witness = WorkspaceWitness(_WORKSPACE)

    def sample():
        anchor, valid, *progress = phase
        low, high = min(tape, default=0), max(tape, default=-1)
        witness.sample(
            machine.workspace_snapshot(),
            (
                _control((position, heading, address)),
                (low, tuple(int(i in tape) for i in range(low, high + 1))),
                tuple(queue),
                _buffer(incoming),
                _buffer(outgoing),
                cursor,
                (_control(anchor), valid),
                *progress,
            ),
        )

    def pop():
        return queue.popleft() if queue else 0

    sample()
    for _ in range(96):
        assert machine.halted == phase[-1]
        assert machine.ip == (
            int(position.imag),
            int(position.real),
            _HEADINGS.index(heading),
        )
        assert machine.state.cell == address
        assert machine.ones == tape
        assert tuple(machine.queue) == tuple(queue)
        assert io.getvalue() == output
        assert io.position() == cursor
        if machine.halted:
            assert (position, heading, address) in seen
            machine.step()
            sample()
            assert io.getvalue() == output
            return
        key = position, heading, address
        repeat = key in seen
        seen.add(key)
        command = grid[int(position.imag)][int(position.real)]
        before = _data(tape, queue, incoming, cursor, outgoing, output)
        if command == "A":
            heading *= 1j
        elif command == "C":
            if heading == 1:
                address -= 1
            elif heading == -1:
                address += 1
                tape.symmetric_difference_update({address})
            elif heading == -1j:
                if address in tape:
                    heading = -1
            else:
                outgoing.append(int(address in tape))
                if len(outgoing) == 8:
                    output += chr(sum(bit << i for i, bit in enumerate(outgoing)))
                    outgoing.clear()
        elif command == "D":
            if heading == 1:
                queue.append(int(address in tape))
            elif heading == 1j:
                if address not in tape:
                    heading = -1j if pop() else 1 if pop() else -1
            else:
                if heading == -1:
                    bit = pop()
                else:
                    if not incoming and cursor < len(stdin):
                        incoming.extend((ord(stdin[cursor]) >> i) & 1 for i in range(8))
                        cursor += 1
                    bit = incoming.popleft() if incoming else 0
                if bit:
                    tape.add(address)
                else:
                    tape.discard(address)
        after = _data(tape, queue, incoming, cursor, outgoing, output)
        if before != after:
            seen.clear()
            repeat = False
        position += heading
        position = complex(position.real % len(grid[0]), position.imag % len(grid))
        key = position, heading, address
        phase = _cycle(phase, key, before, after)
        machine.step()
        sample()
    assert not repeat or machine.halted


def check_raw_abcdirection():
    rng = Random(420)
    grids = [["DDDDDD"], ["CCCCCC", "DDDDDD"], ["BBBBBB", "DDDDDD"]]
    grids += [
        ["".join(rng.choices("ABCD", k=6)) for _ in range(4)] + ["DDDDDD"]
        for _ in range(64)
    ]
    for grid in grids:
        for stdin in ("", "Āÿ"):
            _check(_Machine, grid, stdin)

    _check(_Machine, grids[3], "\x01")

    with pytest.raises(AssertionError):
        _check(stalled(_Machine), ["DDDDDD"], "")
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _check(missing_workspace(_Machine, component), grids[3], "\x01")
