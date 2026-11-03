"""Complex-coordinate grid walk and exact silent-cycle witness."""

from collections import deque
from random import Random

import pytest

from esolangs.languages.abcdirection.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO

_HEADINGS = (1, 1j, -1, -1j)


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

    def pop():
        return queue.popleft() if queue else 0

    for _ in range(96):
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
            assert io.getvalue() == output
            return
        key = position, heading, address
        repeat = key in seen
        seen.add(key)
        command = grid[int(position.imag)][int(position.real)]
        before = (
            frozenset(tape),
            tuple(queue),
            tuple(incoming),
            cursor,
            tuple(outgoing),
            len(output),
        )
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
        if before != (
            frozenset(tape),
            tuple(queue),
            tuple(incoming),
            cursor,
            tuple(outgoing),
            len(output),
        ):
            seen.clear()
            repeat = False
        position += heading
        position = complex(position.real % len(grid[0]), position.imag % len(grid))
        machine.step()
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

    class SkippedMovement(_Machine):
        def step(self):
            pass

    with pytest.raises(AssertionError):
        _check(SkippedMovement, ["DDDDDD"], "")
