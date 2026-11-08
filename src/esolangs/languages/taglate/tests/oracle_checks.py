"""Deque model of the Taglate token stream."""

from collections import deque
from itertools import product
from operator import add, floordiv, mul, sub
from string import ascii_letters, digits

import pytest

from esolangs.languages.taglate.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.support.workspace_oracle import agrees as workspace_agrees
from tests.support.workspace_oracle import missing_workspace

_WORKSPACE = WorkspaceModel("taglate-v1", ("queue", "instruction", "input_cursor"))

_ARITHMETIC = dict(zip("abcd", (add, sub, mul, floordiv), strict=True))


def _partner(tokens, pc):
    opening = tokens[pc]
    direction = 1 if opening == "gy" else -1
    depth = 1
    stop = len(tokens) if direction > 0 else -1
    for index in range(pc + direction, stop, direction):
        if tokens[index] in ("gy", "gz"):
            depth += 1 if tokens[index] == opening else -1
            if not depth:
                return index
    return None


def _model(seed, tokens, stdin):
    queue = deque(ord(c) % 65536 for c in seed)
    pc = cursor = 0
    output = ""
    error = None
    trace = []
    for step in range(17):
        halted = pc == len(tokens)
        trace.append(((tuple(queue), pc), halted, output, cursor, cursor))
        if error:
            break
        if halted:
            trace.extend([trace[-1]] * 3)
            break
        if step == 16:
            break
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
        except (IndexError, ZeroDivisionError):
            error = "halt"
            continue
        pc = destination
    return error, trace


def _check(factory, seed, tokens, stdin):
    expected = _model(seed, tokens, stdin)
    code = [seed, "g?qq".join(tokens)]
    workspace_agrees(
        expected,
        (factory, code, stdin),
        (_WORKSPACE, lambda row: (*row[0], row[-1])),
        lambda m: (m.queue, m.ind),
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
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _check(missing_workspace(_Machine, component), "A", ("a", "i"), "")
