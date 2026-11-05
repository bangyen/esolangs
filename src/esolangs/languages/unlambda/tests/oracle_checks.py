"""Independent recursive Unlambda combinator model, bounded to 128 applications.

https://esolangs.org/wiki/Unlambda, combinators and version-2 IO.
SKIv, printing, exit, input, queries and current-character forwarding;
compare terminal values and IO within 256 VM steps. Delay and call/cc remain
in raw tests. This evaluator uses no production term or continuation objects.
"""

from dataclasses import replace
from itertools import product

import pytest

from esolangs.languages.unlambda.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread, stalled


class _ExitError(Exception):
    def __init__(self, value):
        self.value = value


class _Evaluator:
    def __init__(self, stdin):
        self.stdin, self.cursor, self.current, self.output, self.fuel = (
            stdin,
            0,
            None,
            "",
            128,
        )

    def evaluate(self, term):
        if isinstance(term, tuple) and term[0] == "apply":
            return self.apply(self.evaluate(term[1]), self.evaluate(term[2]))
        return (".", "\n") if term == "r" else term

    def apply(self, function, argument):
        self.fuel -= 1
        assert self.fuel >= 0, "model application bound exceeded"
        if isinstance(function, tuple):
            return self.compound(function, argument)
        if function == "i":
            return argument
        if function == "v":
            return "v"
        if function in ("k", "s"):
            return ("K" if function == "k" else "S", argument)
        if function == "e":
            raise _ExitError(argument)
        if function == "@":
            self.current = (
                self.stdin[self.cursor] if self.cursor < len(self.stdin) else None
            )
            self.cursor += int(self.current is not None)
            return self.apply(argument, "i" if self.current is not None else "v")
        assert function == "|", "delay/callcc outside model"
        value = (".", self.current) if self.current is not None else "v"
        return self.apply(argument, value)

    def compound(self, function, argument):
        kind, *held = function
        if kind == ".":
            self.output += held[0]
            return argument
        if kind == "?":
            return self.apply(argument, "i" if self.current == held[0] else "v")
        if kind == "K":
            return held[0]
        if kind == "S":
            return "SS", held[0], argument
        assert kind == "SS"
        left = self.apply(held[0], argument)
        right = self.apply(held[1], argument)
        return self.apply(left, right)


def _source(term):
    if isinstance(term, str):
        return term
    if term[0] == "apply":
        return "`" + _source(term[1]) + " " + _source(term[2])
    return term[0] + term[1]


def _value(value):
    kind = type(value).__name__
    if kind == "_Cmd":
        return value.name
    if kind == "_Print":
        return ".", value.char
    if kind == "_Query":
        return "?", value.char
    assert kind == "_Partial"
    name = {"k1": "K", "s1": "S", "s2": "SS"}[value.name]
    return name, *(_value(argument) for argument in value.args)


def _view(machine):
    task, continuation, current, _ = machine.state
    value = _value(task.value) if type(task).__name__ == "_Ret" else None
    return value, current, continuation is None


def _check(factory, term, stdin="unused"):
    expected = _Evaluator(stdin)
    try:
        value = expected.evaluate(term)
    except _ExitError as exited:
        value = exited.value
    terminal = (
        (value, expected.current, True),
        True,
        expected.output,
        expected.cursor,
        expected.cursor,
    )
    error, trace = observed(
        factory, "# raw combinators\n" + _source(term), stdin, _view, cap=256
    )
    assert (error, trace[-1]) == (None, terminal), (term, stdin)
    assert trace[0] == ((None, None, True), False, "", 0, 0)
    assert trace[-4:] == [trace[-1]] * 4


def _app(function, *arguments):
    for argument in arguments:
        function = "apply", function, argument
    return function


def check_raw_unlambda():
    atoms = ("i", "k", "s", "v", "e", "@", "|", "r", (".", "A"), ("?", "A"))
    for function, first, second in product(atoms, repeat=3):
        _check(_Machine, _app(function, first, second), "A\n")
    for first, second, third in product(("i", "k", "v", (".", "X")), repeat=3):
        _check(_Machine, _app("s", first, second, third))
    for stdin, char in product(("", "A", "B", "λ\n", "\0"), ("A", "λ", "\n", "#")):
        _check(_Machine, _app("@", _app("k", _app("|", "i"))), stdin)
        _check(
            _Machine,
            _app("@", _app("s", _app("k", ("?", char)), _app("k", "i"))),
            stdin,
        )
        _check(_Machine, _app(_app("@", "i"), _app("|", "i")), stdin)
    for char in ("#", " ", "\n", "λ", "`", "\0"):
        _check(_Machine, _app((".", char), "i"))
    for code in ("", "`i", ".", "?", "ii", "x", "`"):
        assert observed(_Machine, code, "", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class WrongValue(_Machine):
        def step(self):
            super().step()
            if self.halted:
                task, continuation, current, done = self.state
                self.state = (
                    replace(task, value=replace(task.value, name="v")),
                    continuation,
                    current,
                    done,
                )

    for factory in (stalled(_Machine), WrongValue, overread(_Machine)):
        with pytest.raises(AssertionError):
            _check(factory, _app("i", "i"))
