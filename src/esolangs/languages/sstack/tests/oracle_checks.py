"""Revision 163676 SStack, using a manual scanner and seven mutable lists."""

import itertools
import random
from decimal import Decimal

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.sstack.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _parse(source):
    text, ops, at = "".join(source.split()), [], 0
    while at < len(text):
        kind = text[at]
        if kind == "]":
            ops.append((kind, "", ""))
            at += 1
            continue
        if kind == '"':
            end = text.find('"', at + 1)
            number, slash, name = text[at + 1 : end].partition("/")
            if (
                end < 0
                or not slash
                or not number
                or any(c not in "0123456789" for c in number)
                or name not in tuple("abcdefg")
            ):
                raise ValueError
            ops.append((kind, int(Decimal(number)), name))
            at = end + 1
            continue
        size = 3 if kind in ";:~" else 5
        token = text[at : at + size]
        if (
            kind in ";:~"
            and len(token) == 3
            and token[-1] == kind
            and token[1] in "abcdefg"
        ):
            ops.append((kind, token[1], ""))
        elif (
            kind in ">+-["
            and len(token) == 5
            and token[1] in "abcdefg"
            and token[3] in "abcdefg"
            and token[2] == ("\\" if kind == "[" else "/")
            and token[4] == {">": "<", "+": "+", "-": "-", "[": "/"}[kind]
        ):
            ops.append((kind, token[1], token[3]))
        else:
            raise ValueError
        at += size
    levels = list(itertools.accumulate((op[0] == "[") - (op[0] == "]") for op in ops))
    if min([0, *levels]) < 0 or (levels and levels[-1]):
        raise ValueError
    return ops


def _partner(ops, at, step):
    depth, opening, closing = 1, "[" if step > 0 else "]", "]" if step > 0 else "["
    while depth:
        at += step
        depth += (ops[at][0] == opening) - (ops[at][0] == closing)
    return at


def _model(source, stdin):
    try:
        ops = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    stacks, pc, consumed, output, error = (
        {name: [] for name in "abcdefg"},
        0,
        0,
        "",
        None,
    )

    def view():
        state = tuple((name, tuple(stack)) for name, stack in stacks.items())
        return ((pc, state), pc == len(ops), output, consumed, consumed)

    trace = [view()]
    for _ in range(64):
        if pc == len(ops):
            break
        kind, x, y = ops[pc]
        next_pc = pc + 1
        if kind == "[":
            if (stacks[x][-1] if stacks[x] else 0) != (
                stacks[y][-1] if stacks[y] else 0
            ):
                next_pc = _partner(ops, pc, 1) + 1
        elif kind == "]":
            next_pc = _partner(ops, pc, -1)
        elif kind in ">+-~":
            value = stacks[x].pop() if stacks[x] else 0
            if kind != "~":
                # The repo clamps the arithmetic decrement, then transfers zero.
                value = (
                    value + 1
                    if kind == "+"
                    else max(value - 1, 0)
                    if kind == "-"
                    else value
                )
                stacks[y].append(value)
        elif kind == '"':
            stacks[y].append(x)
        elif kind == ";":
            if consumed == len(stdin):
                error = "input"
            else:
                stacks[x].append(ord(stdin[consumed]))
                consumed += 1
        elif kind == ":":
            value = stacks[x][-1] if stacks[x] else 0
            if value > 255:
                error = "halt"
            else:
                output += chr(value)
        if not error:
            pc = next_pc
        trace.append(view())
        if error:
            break
    if not error and pc == len(ops):
        trace.extend([view()] * 3)
    return error, trace


def _agrees(factory, source, stdin):
    expected = _model(source, stdin)
    assert (
        observed(
            factory,
            source,
            stdin,
            lambda m: (m.ind, tuple((k, tuple(v)) for k, v in m.stacks.items())),
        )
        == expected
    ), (source, stdin)
    return expected


def check_raw_sstack():
    atoms = [
        f"{kind}{a}/{b}{close}"
        for a, b in itertools.product("ag", repeat=2)
        for kind, close in ((">", "<"), ("+", "+"), ("-", "-"))
    ]
    atoms += [f"{kind}{name}{kind}" for kind in ";:~" for name in "ag"] + [
        '"0/a"',
        '"255/g"',
        '"256/a"',
    ]
    corpus = [a + b for a, b in itertools.product(atoms, repeat=2)]
    rng = random.Random(20261103)
    corpus += [" \n".join(rng.choices(atoms, k=8)) for _ in range(64)]
    corpus += [
        "",
        r"[a\b/+a/a+]",
        r'"1/a"[a\b/:a:]',
        r"[a\a/]",
        r"[a\a/[b\c/+b/b+]]",
        "-a/g->g/a<",
        '"1 2/a":a:',
        '"' + "0" * 5000 + '1/a"',
    ]
    results = [
        _agrees(_Machine, code, stdin)
        for code in corpus
        for stdin in ("", "A\n", "λ", "\xff")
    ]
    for code in (
        "!",
        ">a/h<",
        ">a/b+",
        ";a:",
        '"-1/a"',
        '"٣/a"',
        "[a\\b",
        "]",
        "[a\\b/]",
        '"1/a',
    ):
        results.append(_agrees(_Machine, code, "unread"))
    results.append(_agrees(_Machine, '"' + "9" * 5000 + '/a":a:', ""))
    assert {error for error, _ in results} == {None, "syntax", "input", "halt"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    controls = {
        "move": ('"1/a">a/g<', ""),
        "loop": (r'"1/a"[a\b/+a/a+]', ""),
        "byte": ('"256/a":a:', ""),
        "eof": (";a;", ""),
        "posthalt": ("", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eof":
                    io.input_char = lambda: 0
                super().__init__(code, io)

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                pc, stacks = self.state
                kind = self.ops[pc][0]
                try:
                    super().step()
                except HaltError:
                    if self.mode != "byte":
                        raise
                    self.state = pc + 1, stacks
                if (self.mode == "move" and kind == ">") or (
                    self.mode == "loop" and kind == "["
                ):
                    self.state = pc + 1, stacks

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    return len(results), len(controls)
