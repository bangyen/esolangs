"""Deque model of the Taglate token stream."""

from collections import deque
from itertools import product
from operator import add, floordiv, mul, sub
from string import ascii_letters, digits

import pytest

from esolangs.languages.taglate.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.support import workspace_oracle as workspace
from tests.support.model_input import matching_delimiter

_WORKSPACE = WorkspaceModel("taglate-v1", ("queue", "instruction", "input_cursor"))

_ARITHMETIC = dict(zip("abcd", (add, sub, mul, floordiv), strict=True))


def _partner(tokens, pc):
    opening = tokens[pc]
    direction = 1 if opening == "gy" else -1
    stop = len(tokens) if direction > 0 else -1
    indices = range(pc + direction, stop, direction)
    span = matching_delimiter(
        (tokens[index] for index in indices), opening, "gz" if opening == "gy" else "gy"
    )
    return None if span is None else pc + direction * span


def _model(seed, tokens, stdin):
    queue = deque(ord(c) % 65536 for c in seed)
    pc = cursor = instruction = 0
    output, error, trace = "", None, []
    for step in range(17):
        halted = pc == len(tokens)
        trace.append(((tuple(queue), instruction), halted, output, cursor, cursor))
        if error or halted or step == 16:
            return error, trace + ([trace[-1]] * 3 if halted else [])
        token = tokens[pc]
        destination = pc + 1
        try:
            if token in _ARITHMETIC:
                first, second = queue.popleft(), queue.popleft()
                queue.append(_ARITHMETIC[token](first, second) % 65536)
            elif token == "e":
                queue.append(queue.popleft())
            elif token == "f":
                queue.popleft()
            elif token == "h":
                if cursor == len(stdin):
                    error = "input"
                    continue
                queue.append(ord(stdin[cursor]) % 65536)
                cursor += 1
            elif token == "i":
                output += chr(queue.popleft())
            elif token == "j":
                value = queue.popleft()
                queue.append(value - 1 if value else 1)
            elif token == "t":
                text = "".join(
                    c if c in ascii_letters + digits + "-_.~" else f"%{ord(c):02X}"
                    for c in map(chr, queue)
                )
                url = f"https://translate.google.com/?sl=en&tl=es&text={text}&op=translate"
                queue = deque(map(ord, url))
            elif bool(queue and queue[0]) == (token == "gz"):
                partner = _partner(tokens, pc)
                if partner is None:
                    error = "syntax"
                    continue
                destination = partner + 1
        except (IndexError, ZeroDivisionError) as problem:
            note = "hint: enqueue a value before removing one from the queue"
            message = "the queue is empty, so there is nothing to pop"
            if isinstance(problem, ZeroDivisionError):
                message = f"'d' divides {first} by the queued {second}, which is zero"
                note = "hint: ensure the divisor is nonzero before dividing"
            instruction = workspace.WorkspaceVariant(
                "halt_fault", (pc, (message,), (note,))
            )
            error = "halt"
            continue
        pc = instruction = destination
    return error, trace


def _check(factory, seed, tokens, stdin):
    code = [seed, "g?qq".join(tokens)]
    workspace.agrees(
        _model(seed, tokens, stdin),
        (factory, code, stdin),
        (_WORKSPACE, lambda row: (*row[0], row[-1])),
        lambda m: (m.queue, m._instruction()),
        cap=16,
        context=(seed, tokens, stdin),
    )


def check_raw_taglate():
    commands = (*"abcdefhijt", "gy", "gz")
    for seed, tokens, stdin in product(
        ("", "A", "A\0", "😀 ñ"), product(commands, repeat=2), ("", "Ω")
    ):
        _check(_Machine, seed, tokens, stdin)
    for tokens in (("gy", "gy", "i", "gz", "gz"), ("gy", "j", "gz", "i")):
        for seed in ("", "\x01", "\x02"):
            _check(_Machine, seed, tokens, "")

    class MissingInput(_Machine):
        def step(self):
            super().step()
            if self.ind and self.tokens[self.ind - 1] == "h":
                self.queue = ()

    with pytest.raises(AssertionError):
        _check(MissingInput, "", ("h", "i"), "x")
    workspace.check_erasures(_WORKSPACE, _check, _Machine, "A", ("a", "i"), "")
