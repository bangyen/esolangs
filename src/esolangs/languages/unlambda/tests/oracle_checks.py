"""Independent recursive Unlambda combinator model, bounded to 128 applications.

https://esolangs.org/wiki/Unlambda, combinators and version-2 IO.
SKIv, printing, exit, input, queries and current-character forwarding;
compare terminal values and IO within 256 VM steps. Delay and call/cc remain
in raw tests. This evaluator uses no production term or continuation objects.
"""

from dataclasses import replace
from itertools import product

import pytest

from esolangs.languages.unlambda.interpreter import _Machine, prepare_machine
from esolangs.runtime._state import WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import observed, reject_faults, stable_halt
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "unlambda-v1", "task continuation character stopped input_cursor"
)


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


def _node(kind, *parts):
    return kind, parts


def _term(term):
    """Translate authored tuples into the independent logical constructor grammar."""
    if isinstance(term, str):
        return _node("Print", "\n") if term == "r" else _node("Cmd", term)
    if term[0] == "apply":
        return _node("App", _term(term[1]), _term(term[2]))
    return _node("Print" if term[0] == "." else "Query", term[1])


def _frozen(node):
    if node is None or isinstance(node, (str, bool)):
        return node
    kind, parts = node
    return WorkspaceVariant(kind, tuple(_frozen(part) for part in parts))


class _Steps:
    """Call-by-value evaluation with explicit argument and function obligations."""

    def __init__(self, term, stdin):
        self.task = _node("Evaluate", _term(term))
        self.kont, self.current, self.stopped = [], None, False
        self.stdin, self.cursor, self.reads, self.past_end, self.output = (
            stdin,
            0,
            0,
            0,
            "",
        )

    def continuation(self):
        return _node("Kont", *self.kont) if self.kont else None

    def row(self):
        parts = (
            _frozen(self.task),
            _frozen(self.continuation()),
            self.current,
            self.stopped,
            self.cursor,
        )
        return (
            (parts, self.reads, self.past_end),
            self.stopped,
            self.output,
            self.cursor,
            self.cursor,
        )

    def evaluate(self, term):
        kind, parts = term
        if kind == "App":
            self.kont.append(_node("Arg", parts[1]))
            self.task = _node("Evaluate", parts[0])
        else:
            self.task = _node("Ret", parts[0] if kind == "Val" else term)

    def resume(self, value):
        if not self.kont:
            self.stopped = True
            return
        kind, parts = self.kont.pop()
        if kind == "Fun":
            self.task = _node("Apply", parts[0], value)
        elif value == _node("Cmd", "d"):
            self.task = _node("Ret", _node("Promise", parts[0]))
        else:
            self.kont.append(_node("Fun", value))
            self.task = _node("Evaluate", parts[0])

    def combinator(self, function, argument):
        kind, parts = function
        name = parts[0]
        held = parts[1][1] if kind == "Partial" else ()
        if name == "i":
            value = argument
        elif name == "v":
            value = _node("Cmd", "v")
        elif name in ("k", "s", "s1"):
            tag = "s2" if name == "s1" else name + "1"
            value = _node("Partial", tag, _node("tuple", *held, argument))
        elif name == "k1":
            value = held[0]
        elif name == "d":
            value = _node("Promise", _node("Val", argument))
        elif name == "e":
            value = argument
            self.kont.clear()
            self.stopped = True
        else:
            self.effectful(name, held, argument)
            return
        self.task = _node("Ret", value)

    def effectful(self, name, held, argument):
        if name == "s2":
            left = _node("App", _node("Val", held[0]), _node("Val", argument))
            right = _node("App", _node("Val", held[1]), _node("Val", argument))
            self.task = _node("Evaluate", _node("App", left, right))
        elif name == "c":
            self.task = _node("Apply", argument, _node("Cont", self.continuation()))
        elif name == "@":
            if self.cursor < len(self.stdin):
                self.current = self.stdin[self.cursor]
                self.cursor += 1
                self.reads += 1
                answer = "i"
            else:
                self.current = None
                self.past_end += 1
                answer = "v"
            self.task = _node("Apply", argument, _node("Cmd", answer))
        else:
            assert name == "|"
            value = (
                _node("Print", self.current)
                if self.current is not None
                else _node("Cmd", "v")
            )
            self.task = _node("Apply", argument, value)

    def apply(self, function, argument):
        kind, parts = function
        if kind == "Print":
            self.output += parts[0]
            self.task = _node("Ret", argument)
        elif kind == "Query":
            answer = "i" if self.current == parts[0] else "v"
            self.task = _node("Apply", argument, _node("Cmd", answer))
        elif kind == "Promise":
            self.task = _node(
                "Evaluate", _node("App", parts[0], _node("Val", argument))
            )
        elif kind == "Cont":
            self.kont = list(parts[0][1]) if parts[0] is not None else []
            self.task = _node("Ret", argument)
        else:
            self.combinator(function, argument)

    def step(self):
        kind, parts = self.task
        if kind == "Evaluate":
            self.evaluate(parts[0])
        elif kind == "Ret":
            self.resume(parts[0])
        else:
            assert kind == "Apply"
            self.apply(*parts)


def _workspace_trace(term, stdin):
    model, trace = _Steps(term, stdin), []
    for tick in range(257):
        trace.append(model.row())
        if model.stopped:
            return None, trace + [model.row()] * 3
        if tick == 256:
            break
        model.step()
    return None, trace


def _workspace_view(machine):
    return machine.workspace_snapshot().parts, machine.io.reads, machine.io.past_end


def _check_workspace(factory, term, stdin="unused"):
    return workspace.agrees(
        _workspace_trace(term, stdin),
        (factory, "# raw combinators\n" + _source(term), stdin),
        (_WORKSPACE, lambda row: row[0][0]),
        _workspace_view,
        cap=256,
        context=(term, stdin),
    )


def _check_prepared(term, stdin):
    trace = _workspace_trace(term, stdin)[1]
    build = prepare_machine("# raw combinators\n" + _source(term), {})
    left, right = build(ScriptedIO(stdin)), build(ScriptedIO(stdin))
    held = []
    for machine, sibling in ((left, right), (right, left)):
        idle = sibling.workspace_snapshot()
        checked = workspace.workspace_view(
            trace, _WORKSPACE, lambda row: row[0][0], _workspace_view
        )
        for index, row in enumerate(trace):
            if index:
                machine.step()
            captured = machine.workspace_snapshot()
            predicted = WorkspaceSnapshot(_WORKSPACE, row[0][0])
            held.append((captured, predicted))
            assert (
                checked(machine),
                machine.halted,
                machine.io.getvalue(),
                machine.io.position(),
                machine.io.progress(),
            ) == row
            assert all(before == expected for before, expected in held)
            assert sibling.workspace_snapshot() == idle
    assert left.io is not right.io


def _check_constructor(source):
    def prepared(code, io):
        return prepare_machine(code, {})(io)

    for factory in (_Machine, prepared):
        io = ScriptedIO("")
        with pytest.raises(ValueError, match="Unlambda"):
            factory(source, io)
        assert io.getvalue() == ""
        assert (io.position(), io.progress(), io.reads, io.past_end) == (0, 0, 0, 0)


def _check_populated_workspace():
    term = _app("@", (".", "Q"))
    expected = _check_workspace(_Machine, term, "A")
    initial = expected[1][0][0][0]
    for index, part in enumerate(initial):
        assert any(row[0][0][index] != part for row in expected[1])
    for candidate, stdin in (
        (_app("d", _app((".", "A"), "i")), ""),
        (_app(_app("d", _app((".", "A"), "i")), "i"), ""),
        (_app("c", _app("s", "i", _app("k", "v")), (".", "A")), ""),
        (_app(_app("@", "@"), "i"), "A"),
        (term, ""),
    ):
        _check_workspace(_Machine, candidate, stdin)
    workspace.check_erasures(_WORKSPACE, _check_workspace, _Machine, term, "A")

    class ErasedCounts(_Machine):
        def step(self):
            try:
                super().step()
            finally:
                self.io._reads = self.io._past_end = 0

    for stdin in ("", "A"):
        with pytest.raises(AssertionError):
            _check_workspace(ErasedCounts, term, stdin)
    _check_prepared(term, "A")
    _check_prepared(_app(_app("@", "@"), "i"), "A")


def _checked_terminal_view(term, stdin):
    """Check full resources and IO during the original terminal observation."""
    trace = _workspace_trace(term, stdin)[1]
    checked = workspace.workspace_view(
        trace,
        _WORKSPACE,
        lambda row: row[0][0],
        lambda machine: (machine.io.reads, machine.io.past_end),
    )
    terminal = stable_halt(_view)
    index = 0

    def sample(machine):
        nonlocal index
        reference = trace[index]
        assert checked(machine) == reference[0][1:]
        assert (
            machine.halted,
            machine.io.getvalue(),
            machine.io.position(),
            machine.io.progress(),
        ) == reference[1:]
        index += 1
        return terminal(machine)

    return sample


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
        factory,
        "# raw combinators\n" + _source(term),
        stdin,
        _checked_terminal_view(term, stdin),
        cap=256,
    )
    assert (error, trace[-1]) == (None, terminal), (term, stdin)
    assert trace[0] == ((None, None, True), False, "", 0, 0)


def _app(function, *arguments):
    for argument in arguments:
        function = "apply", function, argument
    return function


def check_raw_unlambda():
    _check_populated_workspace()
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
        _check_constructor(code)
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

    reject_faults(_check, _Machine, WrongValue, _app("i", "i"))
