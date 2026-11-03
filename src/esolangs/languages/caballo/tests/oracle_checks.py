"""Reference expansion of signed stack paths before final aggregation."""

from collections import Counter
from itertools import product

import pytest

from esolangs.languages.caballo.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO


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
