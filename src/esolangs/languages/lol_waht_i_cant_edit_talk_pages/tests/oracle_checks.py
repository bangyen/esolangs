"""Revision 145166, using word-shaped statements and mutable named variables."""

import itertools
import random
from decimal import Decimal

import pytest

from esolangs.languages.lol_waht_i_cant_edit_talk_pages.interpreter import _Machine
from tests.support.workspace_oracle import (
    charged_bits,
    check_erasures,
    workspace_model,
)
from tests.support.workspace_oracle import checker as workspace_checker

_WORKSPACE = workspace_model(
    "lol-waht-i-cant-edit-talk-pages-v1", "instruction variables input_cursor"
)


def _keyword(text):
    return text.translate(str.maketrans("İıſK", "iisk")).casefold()


def _name(text):
    return bool(text) and not any(c.isspace() for c in text)


def _statement(text):
    words = text.split(" ")
    lower = [_keyword(w) for w in words]
    if _keyword(text[:5]) == "user:" and _name(text[5:]):
        return "def", (text[5:].casefold(),)
    if (
        len(words) == 7
        and lower[:2] == ["edit", "user"]
        and _keyword(words[2][:5]) == "talk:"
        and _name(words[2][5:])
        and lower[3] == "to"
        and lower[4] in ("change", "remove")
        and _name(words[5])
        and lower[6] in ("message", "messages")
    ):
        return "add", (words[2][5:].casefold(), lower[4], words[5].casefold())
    if (
        len(words) == 9
        and lower[:4] == ["just", "let", "me", "change"]
        and lower[5] in ("message", "messages")
        and lower[6] == "on"
        and lower[8] == "{"
        and _name(words[4])
        and _name(words[7])
    ):
        return "loop", (words[4].casefold(), words[7].casefold())
    for kind, prefix in (
        ("read", ["im", "awesome", "tottaly", "but", "no"]),
        ("chr", ["grr", "why", "u", "do", "this"]),
        ("num", ["i", "hate", "u"]),
        ("num", ["i", "hate", "you"]),
    ):
        if lower[:-1] == prefix and _name(words[-1]):
            return kind, (words[-1].casefold(),)
    if lower == ["waht", "i", "got", "banned"]:
        return "halt", ()
    if text == "}":
        return "end", ()
    marker, at = " --tommyaweosme", 0
    while (at := text.find(marker, at)) >= 0:
        end = at + len(marker)
        if end == len(text) or not (text[end].isalnum() or text[end] == "_"):
            return "say", (text[:at],)
        at += 1
    raise ValueError


def _parse(source):
    ops = [_statement(line.strip()) for line in source.split("\n") if line.strip()]
    levels = list(itertools.accumulate((k == "loop") - (k == "end") for k, _ in ops))
    if min([0, *levels]) < 0 or (levels and levels[-1]):
        raise ValueError
    return ops


def _value(env, name):
    digits = name[1:] if name[:1] in "+-" else name
    if digits and all(c in "0123456789" for c in digits):
        return int(Decimal(name))
    return 0 if name == "no" else env[name]


def _input(stdin, at):
    while at < len(stdin) and stdin[at].isspace():
        at += 1
    start = at
    while at < len(stdin) and not stdin[at].isspace():
        at += 1
    token = stdin[start:at]
    if not token:
        return None, at, "input"
    digits = token[1:] if token[:1] in "+-" else token
    if not digits or any(c not in "0123456789" for c in digits):
        return None, at, "argument"
    return int(Decimal(token)), at, None


def _partner(ops, pc, step):
    opening, closing = ("loop", "end") if step > 0 else ("end", "loop")
    depth = 1
    while depth:
        pc += step
        depth += (ops[pc][0] == opening) - (ops[pc][0] == closing)
    return pc


def _model(source, stdin):
    try:
        ops = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    env, pc, consumed, output, error = {}, 0, 0, "", None

    def view():
        state = pc, tuple(sorted(env.items())), pc
        return state, pc == len(ops), output, consumed, consumed

    trace = [view()]
    for _ in range(64):
        if pc == len(ops):
            break
        kind, args = ops[pc]
        next_pc = pc + 1
        try:
            if kind == "def":
                env[args[0]] = 0
            elif kind == "add":
                amount = _value(env, args[2])
                env[args[0]] = _value(env, args[0]) + (
                    amount if args[1] == "change" else -amount
                )
            elif kind == "loop":
                if _value(env, args[1]) != _value(env, args[0]):
                    next_pc = _partner(ops, pc, 1) + 1
            elif kind == "end":
                next_pc = _partner(ops, pc, -1)
            elif kind == "read":
                number, consumed, error = _input(stdin, consumed)
                if not error:
                    _value(env, args[0])
                    env[args[0]] = number
            elif kind in ("chr", "num"):
                value = _value(env, args[0])
                if kind == "chr" and not 0 <= value <= 0x10FFFF:
                    error = "halt"
                else:
                    output += chr(value) if kind == "chr" else str(Decimal(value))
            elif kind == "say":
                output += args[0]
            elif kind == "halt":
                next_pc = len(ops)
        except KeyError:
            error = "halt"
        if not error:
            pc = next_pc
        trace.append(view())
        if error:
            break
    if not error and pc == len(ops):
        trace.extend([view()] * 3)
    return error, trace


_agrees = workspace_checker(
    _model,
    (_WORKSPACE, lambda row: (row[0][0], frozenset(row[0][1]), row[-1])),
    lambda machine: (*machine.state, machine.ip),
)


def check_raw_lol_waht_i_cant_edit_talk_pages():
    atoms = (
        "user:a",
        "user:b",
        "edit user talk:a to change 1 message",
        "edit user talk:a to remove b messages",
        "im awesome tottaly but no a",
        "i hate you A",
        "grr why u do this a",
        "waht i got banned",
        "Hi --tommyaweosme timestamp",
    )
    corpus = ["\n".join(pair) for pair in itertools.product(atoms, repeat=2)]
    rng = random.Random(20261103)
    corpus += [
        "user:a\nuser:b\n" + "\n".join(rng.choices(atoms, k=8)) for _ in range(64)
    ]
    corpus += [
        "",
        "user:a\nJUST LET ME CHANGE no MESSAGES ON A {\n"
        "edit user talk:a to change 1 message\n}\ni hate u a",
        "user:a\nJUST LET ME CHANGE a MESSAGES ON A {\ni hate u a\n}",
        "USER:a\nuser:A\ni hate u a",
        "user:用户1\nim awesome tottaly but no 用户1\ni hate u 用户1",
        "user:a\nedit user talk:a to remove 1 message\ngrr why u do this a",
        "user:a\nedit user talk:a to change -1 messages\ngrr why u do this a",
        "im awesome tottaly but no missing",
        "im awesome tottaly but no no\ni hate u no",
        "İ hate u no",
        "hello --tommyaweosmex",
        "hello --tommyaweosme!",
        "user:a\n" * 80,
    ]
    inputs = ("", "1 -2\n", "x", "٣", "-1")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    results.extend(
        _agrees(_Machine, code, "unread")
        for code in (
            "}",
            "user:a\nJUST LET ME CHANGE no MESSAGES ON a {",
            "user:",
            "user:a b",
            "i  hate u a",
            "bad",
        )
    )
    read = "user:a\nim awesome tottaly but no a"
    cases = (
        (read + "\ni hate u a", "9" * 5000),
        (
            "user:a\nedit user talk:a to change "
            + "0" * 5000
            + "1 messages\ni hate u a",
            "",
        ),
        (read + "\ngrr why u do this a", "9" * 5000),
        (read, "no"),
    )
    results.extend(_agrees(_Machine, code, stdin) for code, stdin in cases)
    errors = {error for error, _ in results}
    assert errors == {None, "syntax", "halt", "argument", "input"}
    controls = {
        "arithmetic": ("user:a\nedit user talk:a to change 1 messages", ""),
        "loop": ("user:a\nJUST LET ME CHANGE 1 MESSAGE ON a {\ni hate u a\n}", ""),
        "read": ("im awesome tottaly but no a", "5"),
        "case": ("user:A\ni hate u a", ""),
        "posthalt": ("", ""),
        "output": ("Hi --tommyaweosme", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "output":
                    write = io.print_str
                    io.print_str = lambda text: write("X" * len(text))
                super().__init__(code, io)
                if self.mode == "case":
                    self.ops[0] = ("def", ("A",), -1)

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                pc, env = self.state
                kind = self.ops[pc][0]
                if self.mode == "read":
                    self.state = type(self.state)(pc + 1, env)
                    return
                super().step()
                at, changed = self.state
                if self.mode == "arithmetic" and kind == "add":
                    self.state = type(self.state)(at, env)
                elif self.mode == "loop" and kind == "loop":
                    self.state = type(self.state)(pc + 1, changed)

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    for source, stdin, bits in (
        ("", "", 0),
        ("user:a", "", 10),
        (read, "5", 14),
        (read, "-8", 17),
    ):
        rows = _agrees(_Machine, source, stdin)[1]
        parts = ((row[0][0], frozenset(row[0][1]), row[-1]) for row in rows)
        assert charged_bits(_WORKSPACE, parts) == bits
    check_erasures(_WORKSPACE, _agrees, _Machine, read, "5")
    return len(results) + 4, len(controls) + len(_WORKSPACE.components)
