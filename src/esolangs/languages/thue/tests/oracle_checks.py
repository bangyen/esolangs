"""Brute substring model: https://esolangs.org/wiki/Thue, description and I/O.

Single rules and conflicting/overlapping pairs, twelve rewrites, scripted
choice indices. Undefined EOF and empty-output handling retain the public
contract's explicit decisions; whitespace-only left sides remain outside scope.
"""

from itertools import product

import pytest

from esolangs.languages.thue.interpreter import _Machine
from tests.interpreters.oracle_support import observed, stalled
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model("thue-v1", "text input_cursor")


class _Choices:
    def __init__(self, choices):
        self.choices = iter(choices * 16)

    def randbelow(self, upper):
        return next(self.choices) % upper


def _matches(text, rules):
    return [
        (i, j)
        for i, (left, _) in enumerate(rules)
        for j in range(len(text))
        if text.startswith(left, j)
    ]


def _model(rules, text, stdin, choices):
    cursor = progress = 0
    output, trace = "", []
    selected = iter(choices * 16)
    for tick in range(13):
        matches = _matches(text, rules)
        row = (
            (text, matches[0] if matches else ()),
            not matches,
            output,
            cursor,
            progress,
        )
        trace.append(row)
        if not matches:
            return None, trace + [row] * 3
        if tick == 12:
            break
        rule, at = matches[next(selected) % len(matches)]
        left, right = rules[rule]
        if right == ":::":
            if cursor == len(stdin):
                return "input", [*trace, row]
            end = stdin.find("\n", cursor)
            end = len(stdin) if end < 0 else end + 1
            replacement = stdin[cursor:end].removesuffix("\n").removesuffix("\r")
            progress += max(1, end - cursor)
            cursor = end
        elif right.startswith("~"):
            output += right[1:] or "\n"
            replacement = ""
        else:
            replacement = right
        text = text[:at] + replacement + text[at + len(left) :]
    return None, trace


def _check(factory, rules, text, stdin, choices=(0,)):
    source = "\n".join([*(left + "::=" + right for left, right in rules), "::=", text])

    def build(code, io):
        return factory(code, io, _Choices(choices))

    workspace.agrees(
        _model(rules, text, stdin, choices),
        (build, source, stdin),
        (_WORKSPACE, lambda row: (row[0][0], row[-1])),
        lambda machine: (machine.state, machine.ip),
        context=(rules, text, stdin, choices),
        cap=12,
    )


def check_raw_thue():
    for left, right, text, stdin, choices in product(
        ("a", "b", "aa", "ab"),
        ("", "a", "b", "~0", "~", ":::"),
        ("", "a", "aba", "aaa", "baba"),
        ("", "x\na\n"),
        ((0,), (1, 0)),
    ):
        _check(_Machine, ((left, right),), text, stdin, choices)
    for rules, text, choices in product(
        (
            (("a", "b"), ("a", "~1")),
            (("aa", "a"), ("a", "~")),
            (("a", ":::"), ("b", "a")),
        ),
        ("aa", "aba", "aab"),
        ((0,), (1,), (0, 2, 1)),
    ):
        _check(_Machine, rules, text, "x\ny\n", choices)
    for source in ("", "a::=b", "bad\n::=\na", "::=x\n::=\na"):
        assert observed(_Machine, source, "", lambda m: m.state) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class DropsOutput(_Machine):
        def __init__(self, code, io, rng):
            io.print_str = lambda _: None
            super().__init__(code, io, rng)

    class WrongChoice(_Machine):
        def __init__(self, code, io, _rng):
            super().__init__(code, io, _Choices((1,)))

    for factory, rules, text in (
        (stalled(_Machine), (("a", "b"),), "a"),
        (DropsOutput, (("a", "~1"),), "a"),
        (WrongChoice, (("a", "b"), ("a", "~1")), "a"),
    ):
        with pytest.raises(AssertionError):
            _check(factory, rules, text, "")

    workspace.check_erasures(
        _WORKSPACE, _check, _Machine, (("a", ":::"), ("x", "~!")), "a", "x\n"
    )
