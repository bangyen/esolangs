"""Mutable two-stack model with suspended source readers."""

from itertools import product

import pytest

from esolangs.languages.eval.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _model(source):
    stacks = [[], []]
    active = 0
    readers = [[source, 0]] if source else []
    output = ""
    trace = []
    for step in range(25):
        state = active, tuple(map(tuple, stacks)), tuple(map(tuple, readers))
        row = state, not readers, output, 0, 0
        trace.append(row)
        if not readers:
            return None, trace + [row] * 3
        if step == 24:
            break
        code, index = readers[-1]
        if index >= len(code):
            readers.pop()
            continue
        token = code[index]
        stack = stacks[active]
        destination = index + 1
        call = None
        try:
            match token:
                case "0" | "`":
                    stack.append(0 if token == "0" else 1 - active)
                case "^":
                    stack.append(stack[-1])
                case "+" | "-":
                    stack[-1] += 1 if token == "+" else -1
                case ".":
                    output += str(stack.pop())
                case "=":
                    stacks[1 - active].append(stack.pop())
                case ";":
                    stack.pop()
                case "~":
                    active = 1 - active
                case "*":
                    stack.reverse()
                case "?":
                    destination += not stack.pop()
                case "!":
                    call = stack.pop()
                    if not isinstance(call, str):
                        raise TypeError
                case '"' | "'":
                    end = code.find('"', destination)
                    end = len(code) if end < 0 else end
                    literal = code[destination:end].replace("`", '"')
                    stack.append(f'"{literal}"' if token == "'" else literal)
                    destination = end + 1
        except (IndexError, TypeError):
            return "halt", [*trace, row]
        readers[-1][1] = destination
        if call is not None:
            readers.append([call, 0])
    return None, trace


def _check(factory, source):
    def state(machine):
        return machine.ptr, machine.stk, machine.frames

    assert observed(factory, source, "unused", state, cap=24) == _model(source), source


def check_raw_eval():
    tokens = ("0", "`", "^", "+", "-", ".", "=", ";", "~", "*", "?", "!", '"x"', '""')
    for parts in product(tokens, repeat=3):
        _check(_Machine, "".join(parts))
    for source in ("", '"0+."!', '"`0+.`!"!', "'x\"!.", '0?"x".', '"unclosed', '""!'):
        _check(_Machine, source)

    class DiscardsCaller(_Machine):
        def step(self):
            super().step()
            if len(self.frames) > 1:
                self.frames = self.frames[-1:]

    with pytest.raises(AssertionError):
        _check(DiscardsCaller, '"0"!.')
