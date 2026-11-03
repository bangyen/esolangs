"""Sparse-memory model of the subtract-and-branch instruction."""

from itertools import product

import pytest

from esolangs.languages.s_bleq.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _model(words, stdin, store, *, indirect):
    cells = dict(enumerate(words))
    size = len(words)
    ip = cursor = 0
    stopped = False
    output = ""
    error = None
    trace = []
    for step in range(13):
        halted = stopped or not 0 <= ip <= size - 3
        view = ip, tuple(cells.get(i, 0) for i in range(size))
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
                output += chr(read(b if a == -3 else a) % 256)
            if c < 0:
                raise KeyError(c)
            if -3 in (a, b):
                ip += 3
                continue
            difference = read(a) - read(b)
        except KeyError:
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

    def state(vm):
        return vm.ip, tuple(vm.memory)

    code = " ".join(map(str, words))
    assert observed(machine, code, stdin, state, cap=12) == _model(
        words, stdin, store, indirect=indirect
    ), (words, stdin, store, indirect)


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
