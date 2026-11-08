"""Revision 166743 rewriting: iterator fields and character lists."""

import itertools
import random

import pytest

from esolangs.languages.slashes.interpreter import _Machine
from tests.support.workspace_oracle import (
    check_erasures,
    source_checker,
    workspace_model,
)

_WORKSPACE = workspace_model("slashes-v1", "source pattern replacement input_cursor")


def _rule(characters):
    stream = iter(characters)

    def field():
        text = []
        while True:
            char = next(stream)
            if char == "/":
                return "".join(text)
            text.append(next(stream) if char == "\\" else char)

    try:
        pattern, replacement = field(), field()
    except StopIteration:
        return [], None
    return list(stream), (pattern, replacement)


def _model(code):
    unread, active, output = list(code), None, ""

    def view():
        return (
            ("".join(unread), active, tuple(map(ord, unread)), None),
            not unread and active is None,
            output,
            0,
            0,
        )

    trace = [view()]
    for _ in range(64):
        if not unread and active is None:
            break
        if active is not None:
            pattern, replacement = active
            text = "".join(unread)
            if pattern and pattern not in text:
                active = None
            elif pattern:
                unread = list(text.replace(pattern, replacement, 1))
        else:
            char = unread.pop(0)
            if char == "/":
                unread, active = _rule(unread)
            else:
                if char == "\\":
                    char = unread.pop(0) if unread else ""
                output += char
        trace.append(view())
    if not unread and active is None:
        trace.extend([view()] * 3)
    return None, trace


_agrees = source_checker(
    _model,
    (_WORKSPACE, lambda row: (row[0][0], *(row[0][1] or (None, "")), row[-1])),
    lambda m: (*m.state, tuple(m.memory), m.ip),
    "λ\nunused",
)


def check_raw_slashes():
    atoms = "/\\abx"
    corpus = ["".join(p) for n in range(5) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += ["".join(rng.choices(atoms, k=16)) for _ in range(128)]
    corpus += [
        "/a/b/aaa",
        "/a/a/a",
        "/a/aa/a",
        "///",
        "/a/",
        "/a",
        "\\",
        "/a/\\",
        r"/x/\/a\/b\//xaa",
        r"/\//X///",
        r"a\/b\\",
        "/./x/a.b",
        "/a*/x/aaa",
        "λ\n",
        "hello/incomplete",
    ]
    results = [_agrees(_Machine, source) for source in corpus]
    assert any(not trace[-1][1] for _, trace in results)
    assert _model("/a/b/aaa")[1][-1][2] == "bbb"
    assert _model("/./x/a.b")[1][-1][2] == "axb"
    assert not _model("///")[1][-1][1]
    controls = {
        "global": "/a/b/aa",
        "empty": "///",
        "incomplete": "/",
        "escape": r"\x",
        "input": "a",
        "posthalt": "",
    }
    for fault, source in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "incomplete":
                    raise ValueError("incomplete rule rejected")
                super().__init__(code, io)

            def step(self):
                text, rule = self.state
                if self.mode == "posthalt" and self.halted:
                    self.io.print_str("extra")
                if self.mode == "empty" and rule is not None and not rule[0]:
                    self.state = "", None
                elif self.mode == "global" and rule is not None and rule[0] in text:
                    self.state = text.replace(*rule), rule
                else:
                    if self.mode == "input" and not self.halted:
                        self.io.input_char()
                    super().step()
                    if self.mode == "escape" and text.startswith("\\"):
                        self.io.print_str("\\")

        with pytest.raises(AssertionError):
            _agrees(Fault, source)
    check_erasures(_WORKSPACE, _agrees, _Machine, "/a/b/aaa")
    return len(corpus), len(controls) + 4
