"""Independent finite expression plans and complete workspace recounts."""

import re
from itertools import product

import pytest

from esolangs.languages.parenthesys.interpreter import _Machine, prepare_machine
from esolangs.runtime._state import WorkspaceSnapshot
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import reject_faults
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "parenthesys-v1", "instruction stack frames globals functions locals input_cursor"
)
_NUMBER = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")


def _plan(source):
    """Lower only the owned fixtures, without production syntax or operations."""
    ops, at = [], 0

    def emit(kind, argument=None):
        ops.append((kind, argument))
        return len(ops) - 1

    def expression(closing=""):
        nonlocal at
        count = 0
        while at < len(source) and source[at] not in closing:
            char = source[at]
            at += 1
            if char == "$":
                emit("input")
            elif char in "([{<":
                group(char)
            else:
                text = char
                while at < len(source) and source[at] not in "()[]{}<>|$":
                    text += source[at]
                    at += 1
                emit("lit", (text, bool(_NUMBER.fullmatch(text))))
            count += 1
        if not count:
            emit("lit", ("", False))
        elif count > 1:
            emit("cat", count)

    def group(opener):
        nonlocal at
        closer = {"(": ")", "[": "]", "{": "}", "<": ">"}[opener]
        # A loop's accumulator precedes the first condition operation.
        depth, scan, pipes = 0, at, 0
        while scan < len(source):
            token = source[scan]
            if token in "([{<":
                depth += 1
            elif token in ")]}>" and depth:
                depth -= 1
            elif token == closer and not depth:
                break
            elif token == "|" and not depth:
                pipes += 1
            scan += 1
        if opener == "{" and pipes:
            emit("acc")
        start = len(ops)
        expression("|" + closer)
        parts = 1
        patch = None
        while source[at] == "|":
            at += 1
            parts += 1
            if opener == "{" or parts == 4:
                patch = emit("test" if opener == "{" else "def")
            expression("|" + closer)
        assert source[at] == closer
        at += 1
        if opener == "{" and pipes:
            emit("add")
            emit("jump", start)
            ops[patch] = ("test", len(ops))
            emit("done")
        elif opener == "[" and parts == 4:
            emit("ret")
            ops[patch] = ("def", len(ops))
        else:
            emit(
                {
                    "(": "print",
                    "<": "str",
                    "{": "num",
                    "[": ("get", "set", "call")[parts - 1],
                }[opener]
            )

    expression()
    return ops


def _value(text, *, numeric=False):
    return text, numeric and bool(_NUMBER.fullmatch(text))


def _builtin(name, left, right):
    if name not in ("+", "-", "*"):
        raise ValueError("finite builtin scope")
    a, b = int(left[0]), int(right[0])
    return str({"+": a + b, "-": a - b, "*": a * b}[name]), True


def _scope(frames, locals_, globals_, name):
    if frames and name in locals_[frames[-1][1]]:
        return locals_[frames[-1][1]]
    return globals_


def _model(source, stdin):
    ops = _plan(source)
    pc = cursor = reads = past_end = 0
    stack, frames, globals_, functions, locals_ = [], [], {}, {}, {}
    output, failure, trace = "", None, []

    def row():
        values = tuple(
            ("".join(item[0]), item[1]) if isinstance(item, list) else item
            for item in reversed(stack)
        )
        parts = (
            pc,
            values,
            tuple(reversed(frames)),
            frozenset(globals_.items()),
            frozenset(functions.items()),
            frozenset(
                (key, frozenset(value.items())) for key, value in locals_.items()
            ),
            cursor,
        )
        return (parts, reads, past_end), pc == len(ops), output, cursor, cursor

    trace.append(row())
    for _ in range(256):
        kind, arg = ops[pc]
        nxt = pc + 1
        if kind == "input":
            if cursor == len(stdin):
                past_end += 1
                failure = "input"
            else:
                end = stdin.find("\n", cursor)
                stop = len(stdin) if end < 0 else end + 1
                text = stdin[cursor:stop].removesuffix("\n").removesuffix("\r")
                cursor, reads = stop, reads + 1
                stack.append(_value(text, numeric=True))
        elif kind == "lit":
            stack.append(arg)
        elif kind == "cat":
            items, stack = stack[-arg:], stack[:-arg]
            stack.append(
                _value(
                    "".join(item[0] for item in items),
                    numeric=any(item[1] for item in items),
                )
            )
        elif kind == "print":
            output += stack[-1][0]
        elif kind in ("num", "str"):
            if kind == "num" and not _NUMBER.fullmatch(stack[-1][0]):
                failure = "halt"
            else:
                stack[-1] = (stack[-1][0], kind == "num")
        elif kind == "get":
            name = stack.pop()[0]
            stack.append(_scope(frames, locals_, globals_, name).get(name, ("0", True)))
        elif kind == "set":
            name = stack.pop()[0]
            _scope(frames, locals_, globals_, name)[name] = stack[-1]
        elif kind in ("def", "call"):
            f, x, y = stack[-3:]
            if kind == "def":
                functions[f[0]] = (pc + 1, x[0], y[0])
                stack[-3:] = [f]
                nxt = arg
            elif f[0] in ("+", "-", "*"):
                stack[-3:] = [_builtin(f[0], x, y)]
            elif f[0] in functions:
                start, a, b = functions[f[0]]
                locals_[f[0]] = {a: x, b: y}
                frames.append((nxt, f[0]))
                del stack[-3:]
                nxt = start
            else:
                stack[-3:] = [("", False)]
        elif kind == "ret":
            nxt, _ = frames.pop()
        else:
            nxt = _loop(kind, arg, stack, nxt)
        if not failure:
            pc = nxt
        trace.append(row())
        if failure:
            break
        if pc == len(ops):
            trace.extend([row()] * 3)
            break
    else:
        raise AssertionError("finite corpus exceeded cap256")
    return failure, trace


def _loop(kind, arg, stack, nxt):
    if kind == "acc":
        stack.append([[], False])
    elif kind == "test":
        text, _ = stack.pop()
        if not text or (_NUMBER.fullmatch(text) and int(text) == 0):
            nxt = arg
    elif kind == "add":
        text, numeric = stack.pop()
        stack[-1][0].append(text)
        stack[-1][1] |= numeric
    elif kind == "jump":
        nxt = arg
    else:
        assert kind == "done"
        pieces, numeric = stack.pop()
        stack.append(_value("".join(pieces), numeric=numeric))
    return nxt


def _view(machine):
    snapshot = machine.workspace_snapshot()
    return snapshot.parts, machine.io.reads, machine.io.past_end


def _check(factory, source, stdin=""):
    return workspace.agrees(
        _model(source, stdin),
        (factory, source, stdin),
        (_WORKSPACE, lambda row: row[0][0]),
        _view,
        cap=256,
    )


def _isolation(source, stdin):
    expected = _model(source, stdin)[1]
    build = prepare_machine(source, {})
    siblings = (build(ScriptedIO(stdin)), build(ScriptedIO(stdin)))
    held = []
    for machine in siblings:
        sibling = siblings[1] if machine is siblings[0] else siblings[0]
        idle = sibling.workspace_snapshot()
        checked = workspace.workspace_view(
            expected, _WORKSPACE, lambda row: row[0][0], _view
        )
        for row in expected:
            captured = machine.workspace_snapshot()
            predicted = WorkspaceSnapshot(_WORKSPACE, row[0][0])
            assert captured == predicted
            assert _view(machine) == row[0]
            assert checked(machine) == row[0]
            assert machine.io.progress() == row[4]
            assert (machine.io.getvalue(), machine.io.position()) == (row[2], row[3])
            held.append((captured, predicted))
            assert all(before == reference for before, reference in held)
            machine.step()
            assert sibling.workspace_snapshot() == idle
    assert siblings[0].workspace_snapshot() == held[-1][1]


def check_workspace_parenthesys():
    for count, factor, offset in product(range(6), (-3, 0, 7), (-2, 0, 4)):
        source = f"[{count}|n]({{[n]|([+|[*|[n]|{factor}]|{offset}])[[-|[n]|1]|n]}})"
        _check(_Machine, source)
    for count in (1, 2, 5):
        _check(_Machine, f"[{-count}|n]({{[n]|([n])[[+|[n]|1]|n]}})")
    source = "[5|g][f|a|b|[+|[a]|[g]]]([f|$|3])"
    expected = _check(_Machine, source, "2\n")
    assert expected[1][-1][2] == "7"
    initial = expected[1][0][0][0]
    assert all(
        any(row[0][0][i] != part for row in expected[1])
        for i, part in enumerate(initial)
    )
    for code, stdin in ((source, ""), ("{$}", "bad\n"), ("($)", "hello\r\n")):
        _check(_Machine, code, stdin)
    workspace.check_erasures(_WORKSPACE, _check, _Machine, source, "2\n")
    reject_faults(
        _check, _Machine, workspace.missing_workspace(_Machine, "frames"), source, "2\n"
    )

    class ErasedCounts(_Machine):
        def step(self):
            try:
                super().step()
            finally:
                self.io._reads = self.io._past_end = 0

    for stdin in ("", "2\n"):
        with pytest.raises(AssertionError):
            _check(ErasedCounts, source, stdin)
    _isolation(source, "2\n")
