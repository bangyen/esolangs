"""Sparse-memory model of the subtract-and-branch instruction."""

from itertools import product

import pytest

from esolangs.languages.s_bleq.interpreter import _Machine
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "s-bleq-v1", "memory instruction input_cursor stopped"
)


def _model(words, stdin, store, *, indirect):
    cells = dict(enumerate(words))
    size = len(words)
    ip = cursor = 0
    stopped = False
    output = ""
    error = delivered = None
    trace = []
    for step in range(13):
        halted = stopped or not 0 <= ip <= size - 3
        view = ip, tuple(cells.get(i, 0) for i in range(size)), stopped, delivered
        trace.append((view, halted, output, cursor, cursor))
        if error:
            break
        if halted:
            trace.extend([trace[-1]] * 3)
            break
        if step == 12:
            break
        a, b, c = (cells.get(i, 0) for i in range(ip, ip + 3))
        if indirect:
            if min(a, b) < 0:
                error = "syntax"
                continue
            a, b = cells.get(a, 0), cells.get(b, 0)
        incoming = 0
        if -2 in (a, b) and cursor < len(stdin):
            incoming = ord(stdin[cursor])
            cursor += 1
        ports = {-1: ip, -2: incoming}

        def read(address, ports=ports):
            if address >= 0:
                return cells.get(address, 0)
            return ports[address]

        try:
            if -3 in (a, b):
                other = b if a == -3 else a
                output += chr(read(other) % 256)
                delivered = ({-2: incoming}.get(other), 0, True)
            if c < 0:
                raise KeyError(c)
            if -3 in (a, b):
                delivered = None
                ip += 3
                continue
            difference = read(a) - read(b)
        except KeyError:
            delivered = incoming if -2 in (a, b) and -3 not in (a, b) else delivered
            error = "syntax"
            continue
        for key, address in zip("ab", (a, b), strict=True):
            if key not in store:
                continue
            if address == -1:
                ip = difference
            if address >= 0:
                cells[address] = difference
                size = max(size, address + 1)
        if difference > 0:
            ip += 3
        elif (target := cells.get(c, 0)) < 0:
            stopped = True
        else:
            ip = target
    return error, trace


def _check(factory, words, stdin, store, *, indirect):
    def machine(code, io):
        return factory(code, io, store, indirect=indirect)

    def parts(row):
        ind, mem, stopped, delivered = row[0]
        cursor = row[-1]
        if isinstance(delivered, int):
            cursor = workspace.WorkspaceVariant("pending_input", (cursor, delivered))
        elif delivered is not None:
            ind = workspace.WorkspaceVariant("pending_output", (ind, delivered))
        return mem, ind, cursor, stopped

    code = " ".join(map(str, words))
    workspace.agrees(
        _model(words, stdin, store, indirect=indirect),
        (machine, code, stdin),
        (_WORKSPACE, parts),
        lambda m: (
            m.ip,
            tuple(m.memory),
            m._halted,
            m._pending_output() if m._input_byte is None else m._input_byte,
        ),
        cap=12,
        context=(words, stdin, store, indirect),
    )


def check_raw_s_bleq():
    addresses = (-4, -3, -2, -1, 0, 3, 4, 8)
    for a, b, store, stdin in product(
        addresses, addresses, ("a", "b", "ab"), ("", "Āz")
    ):
        _check(_Machine, [a, b, 4, 5, -1], stdin, store, indirect=False)
        _check(_Machine, [3, 4, 5, a, b, -1], stdin, store, indirect=True)
    for words in ([-3, 0, -1], [-2, 0, -1], [-1, 3, 0, -2], [], [0, 0]):
        _check(_Machine, words, "x", "a", indirect=False)

    class SuppressedOutput(_Machine):
        def output(self, value):
            pass

    with pytest.raises(AssertionError):
        _check(SuppressedOutput, [-3, -2, 0], "q", "a", indirect=False)

    workspace.check_erasures(
        _WORKSPACE,
        lambda f: _check(f, [-2, 6, 0, 7, 6, 8, 0, 0, -1], "\x02", "b", indirect=False),
        _Machine,
    )
