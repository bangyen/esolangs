"""Revision 103718 Sonata, using explicit shortest-first substring matching."""

import itertools
import random
import re
from dataclasses import replace

import pytest

from esolangs.languages.sonata.interpreter import _Machine
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model("sonata-v1", "text stopped rendered")


def _parse(source):
    rules = []
    for line in source.split("\n"):
        if not line.strip():
            continue
        tokens = re.findall(r"[\^_][\s\S]|[\s\S]", line)
        if any(token in ("^", "_") for token in tokens):
            raise ValueError
        arrow = next(
            (i for i in range(len(tokens) - 1) if tokens[i : i + 2] == ["-", ">"]), None
        )
        if arrow is None:
            raise ValueError
        lhs, rhs = tokens[:arrow], tokens[arrow + 2 :]
        names = [token[1] for token in lhs if len(token) == 2]
        if len(set(names)) != len(names) or any(
            token[1] not in names for token in rhs if len(token) == 2
        ):
            raise ValueError
        rules.append((lhs, rhs))
    return rules


def _match(pattern, text, bindings):
    if not pattern:
        return bindings if not text else None
    token, rest = pattern[0], pattern[1:]
    if len(token) == 1:
        return _match(rest, text[1:], bindings) if text.startswith(token) else None
    lengths = range(len(text) + 1) if token[0] == "_" else (1,) if text else ()
    for count in lengths:
        found = _match(rest, text[count:], {**bindings, token[1]: text[:count]})
        if found is not None:
            return found
    return None


def _model(source, stdin, cap=16):
    try:
        rules = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    text = stdin.removesuffix("\n")
    halted, rendered, output = False, False, ""

    def view():
        return ((text, rendered, (len(text),)), halted, output, len(stdin), len(stdin))

    trace = [view()]
    for _ in range(cap):
        if halted:
            break
        for lhs, rhs in rules:
            bindings = _match(lhs, text, {})
            if bindings is not None:
                text = "".join(
                    token if len(token) == 1 else bindings[token[1]] for token in rhs
                )
                break
        else:
            halted, rendered, output = True, True, text
        trace.append(view())
    if halted:
        trace.extend([view()] * 3)
    return None, trace


def _agrees(factory, source, stdin, cap=16):
    expected = _model(source, stdin, cap)
    return workspace.agrees(
        expected,
        (factory, source, stdin),
        (_WORKSPACE, lambda row: (row[0][0], row[1], row[0][1])),
        lambda m: (m.text, m.rendered, m.ip),
        cap=cap,
    )


def check_raw_sonata():
    atoms = (
        "a->b",
        "b->",
        "->a",
        "^A_B->^A^A_B",
        "_Aa_Bb->_A,_B",
        "_A->_A",
        "_A_B->_B_A",
        "^A->x",
        "_A^B->^B_A",
    )
    corpus = [
        "\n".join(p) for n in range(3) for p in itertools.product(atoms, repeat=n)
    ]
    rng = random.Random(20261103)
    corpus += ["\n".join(rng.choices(atoms, k=3)) for _ in range(64)]
    corpus += [
        "apple->orange",
        "^-->x",
        "_A->^A",
        "^A->_A",
        "a->b->c",
        " ->x",
        "^A_B->^A",
        "a^X_Y->_Ybc\nb^X_Y->_Ya\nc^X_Y->_Yaaa",
        "\n \n",
        "^λ->x",
    ]
    inputs = ("", "a", "ab", "aabb", "λ\n", "a\nb\n", "x\r\n", "a\n\n")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    results.extend(
        _agrees(_Machine, code, "unread\n")
        for code in (
            "x",
            "^",
            "_",
            "^A->^B",
            "_A_A->",
            "^A_A->",
            "a->^",
            "a->_",
            "_-->x",
            "a->^A",
            "_->x",
        )
    )
    results.append(_agrees(_Machine, "_A->_A_A", "ab", cap=8))
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model("_Aa_Bb->_A,_B", "aabb")[1][1][0][0] == ",ab"
    assert _model("apple->orange", "1apple2")[1][-1][2] == "1apple2"
    controls = {
        "greedy": ("_Aa_Bb->_A,_B", "aabb"),
        "whole": ("a->b", "xa"),
        "order": ("a->b\na->c", "a"),
        "single": ("^A->x", "λ\n\n"),
        "syntax": ("x", "unread"),
        "initial": ("", "a\n\n"),
        "read": ("", "abc"),
        "early": ("a->b", "a"),
        "repeat": ("", "a"),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "read":
                    io.input_all = lambda: "abc"
                super().__init__("" if self.mode == "syntax" else code, io)
                if self.mode == "greedy":
                    self.rules = tuple(
                        replace(
                            rule,
                            pattern=re.compile(
                                rule.pattern.pattern.replace("(.*?)", "(.*)"), re.DOTALL
                            ),
                        )
                        for rule in self.rules
                    )
                elif self.mode == "order":
                    self.rules = tuple(reversed(self.rules))
                elif self.mode == "initial":
                    self.text = self.text.rstrip("\n")
                elif self.mode == "single":
                    self.rules = tuple(
                        replace(
                            rule,
                            pattern=re.compile(
                                rule.pattern.pattern.replace("(.)", "(.*)"), re.DOTALL
                            ),
                        )
                        for rule in self.rules
                    )

            def step(self):
                if self.mode == "repeat" and self.halted:
                    self.io.print_str(self.text)
                if self.mode == "whole" and self.text == "xa":
                    self.text = "xb"
                    return
                super().step()
                if self.mode == "early" and not self.halted:
                    self.io.print_str(self.text)

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    workspace.check_erasures(_WORKSPACE, _agrees, _Machine, "a->b", "a")
    return len(results), len(controls)
