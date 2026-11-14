"""Small-step call witnesses from overload, suspension and block-entry rules."""

from concurrent.futures import ThreadPoolExecutor
from functools import partial

import pytest

import esolangs
from esolangs.debugger import Debugger
from esolangs.languages.dinac.interpreter import _Machine
from esolangs.results import Completion, CompletionReport
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_observation, _capture_workspace, make_vm
from tests.interpreters.oracle_support import after_step, overread, stalled
from tests.support.certification_barrier import guarded_worker
from tests.support.workspace_oracle import WorkspaceWitness


def _frame(fn, scope, body):
    return {
        "fn": fn,
        "scope": scope,
        "blocks": ((body, 0),),
        "pending": None,
        "returned": None,
        "null_types": (),
    }


class _Trace:
    def __init__(self, body, scope=()):
        self.frames = [_frame(0, scope, body)]
        self.output = ""
        self.cursor = self.reads = self.past_end = 0
        self.rows = []
        self.save()

    def save(self):
        names = "fn", "scope", "blocks", "pending", "returned", "null_types"
        frames = tuple(tuple(f[key] for key in names) for f in self.frames)
        self.rows.append((frames, self.output, self.cursor, self.reads, self.past_end))

    def push(self, fn, scope, body, expression):
        self.frames[0].update(pending=expression, returned=None)
        self.frames.insert(0, _frame(fn, scope, body))
        self.save()

    def leave(self, value):
        self.frames.pop(0)
        self.frames[0]["returned"] = value
        self.save()

    def resume(self, blocks, output="", scope=None):
        self.frames[0].update(blocks=blocks, pending=None, returned=None)
        if scope is not None:
            self.frames[0]["scope"] = scope
        self.output += output
        self.save()

    def end(self):
        self.frames.clear()
        self.save()
        for _ in range(3):
            self.save()


def _call(name, *args):
    return "call", name, args


def _literal(kind, value):
    return "lit", (kind, value)


_INC = "DEF/00 inc n:00\n    GIVE n+\nDEF/\\0 inc n:\\0\n    GIVE n+\n"


def _nested(kind, value, equal):
    modulus, fn = (256, 1) if kind == "wubyte" else (128, 2)
    first, second = (value + 1) % modulus, (value + 2) % modulus
    right = first if equal else value

    def leaf(n):
        return _literal(kind, n)

    rhs = _call("inc", leaf(right))
    original = "cmp", "=", _call("inc", _call("inc", leaf(value))), rhs
    middle = "cmp", "=", _call("inc", leaf(first)), rhs
    final = "cmp", "=", leaf(second), rhs
    # Definitions allocate bodies before the root, in source order.
    t = _Trace(2)
    for argument, result, expression in (
        (value, first, original),
        (first, second, middle),
        (right, (right + 1) % modulus, final),
    ):
        t.push(fn, ((kind, argument),), fn - 1, expression)
        t.leave((kind, result))
    t.resume(((2, 1),), "01" if equal else "00")
    t.end()

    def spell(n):
        return f"{n:02X}" if kind == "wubyte" else r"\0" if not n else "'" + chr(n)

    return (
        _INC + f"OUT inc(inc({spell(value)})) = inc({spell(right)})",
        "unused",
        t.rows,
        False,
    )


def _recursive(depth):
    code = "DEF/00 d n:00\n    IF n\n        GIVE d(n-)\n    ELSE\n        GIVE 07\n"
    # IF children precede their enclosing body; the root is allocated last.
    t = _Trace(3)
    t.push(1, (("wubyte", depth),), 2, _call("d", _literal("wubyte", depth)))
    for n in range(depth, -1, -1):
        t.frames[0]["blocks"] = ((2, 1), (0 if n else 1, 0))
        t.save()
        if n:
            t.push(1, (("wubyte", n - 1),), 2, _call("d", ("step", "-", ("name", 0))))
        else:
            t.leave(("wubyte", 7))
    for _ in range(depth):
        t.leave(("wubyte", 7))
    t.resume(((3, 1),), "07")
    t.end()
    return code + f"OUT d({depth:02X})", "unused", t.rows, False


def _loop(count):
    code = "DEF/00 test n:00\n    GIVE n\nDEF/00 dec n:00\n    GIVE n-\n"
    code += f"SET n:{count:02X}\nWHILE test(n)\n    n . dec(n)\nOUT n"
    t = _Trace(3, (None,))
    t.resume(((3, 1),), scope=(("wubyte", count),))
    for n in range(count, -1, -1):
        t.push(1, (("wubyte", n),), 0, _call("test", ("name", 0)))
        t.leave(("wubyte", n))
        t.resume(((3, 1), (2, 0)) if n else ((3, 2),))
        if n:
            t.push(2, (("wubyte", n),), 1, _call("dec", ("name", 0)))
            t.leave(("wubyte", n - 1))
            t.resume(((3, 1), (2, 1)), scope=(("wubyte", n - 1),))
            t.frames[0]["blocks"] = ((3, 1),)
            t.save()
    t.resume(((3, 3),), "00")
    t.end()
    return code, "unused", t.rows, False


def _void():
    t = _Trace(1)
    t.push(1, (), 0, _call("shout"))
    t.resume(((0, 1),), "h")
    t.resume(((0, 2),), "i")
    t.leave(("snuval", 0))
    t.resume(((1, 1),))
    t.end()
    return "DEF/$ shout\n    OUT 'h\n    OUT 'i\nshout()", "unused", t.rows, False


def _failures():
    t = _Trace(1)
    t.resume(((1, 1),), "p")
    t.push(1, (("wubyte", 1),), 0, _call("bad", _literal("wubyte", 1)))
    t.save()  # A rejected return preserves the callee and its suspended caller.
    yield "DEF/00 bad n:00\n    GIVE 'x\nOUT 'p\nOUT bad(01)", "unused", t.rows, True
    t = _Trace(2)
    t.resume(((2, 1),), "p")
    t.save()  # Failed overload selection never commits a pending expression.
    yield _INC + "OUT 'p\nOUT inc(01,02)", "unused", t.rows, True
    t = _Trace(3)
    t.resume(((3, 1),), "p")
    t.push(1, (("wubyte", 0),), 2, _call("maybe", _literal("wubyte", 0)))
    t.resume(((2, 1), (1, 0)))
    t.resume(((2, 1), (1, 1)), "x")
    t.frames[0]["blocks"] = ((2, 1),)
    t.save()
    t.save()
    code = (
        "DEF/00 maybe n:00\n    IF n\n        GIVE n\n"
        "    ELSE\n        OUT 'x\nOUT 'p\nOUT maybe(00)"
    )
    yield code, "unused", t.rows, True


def _input(stdin, *, null=False):
    t = _Trace(1)
    t.push(1, (None,), 0, _call("read"))
    t.resume(((0, 1),), scope=(("wubyte", 0),))
    if null:
        t.frames[0]["null_types"] = ((0, "wubyte"),)
        t.resume(((0, 2),), scope=(("snuval", 0),))
    text = stdin.partition("\n")[0].strip()
    value = int(text) if text.isascii() and text.isdigit() and len(text) <= 3 else 0
    value = value if value <= 255 else 0
    t.cursor = stdin.index("\n") + 1 if "\n" in stdin else len(stdin)
    t.reads, t.past_end = int(bool(stdin)), int(not stdin)
    t.frames[0]["null_types"] = ()
    t.resume(((0, 2 + null),), scope=(("wubyte", value),))
    t.leave(("wubyte", value))
    t.resume(((1, 1),), f"{value:02X}")
    t.end()
    return (
        "DEF/00 read\n    SET n:00\n"
        + ("    n . $\n" if null else "")
        + "    IN n\n    GIVE n\nOUT read()",
        stdin,
        t.rows,
        False,
    )


def _cases():
    cases = [
        _nested(kind, value, equal)
        for kind, values in (
            ("wubyte", (0, 1, 126, 127, 254, 255)),
            ("aschar", (0, 1, 126, 127)),
        )
        for value in values
        for equal in (False, True)
    ]
    cases += [_recursive(n) for n in (0, 1, 2, 5, 10)]
    cases += [_loop(n) for n in (0, 1, 2, 5)]
    cases += [_void(), *_failures()]
    cases += [_input(text) for text in ("", "12\nunused", "256\n", "λ\n", "7")]
    cases += [_input(text, null=True) for text in ("", "7")]
    assert len(cases) == 40
    assert all(
        (
            len(rows) - 1
            if failure
            else next(i for i, row in enumerate(rows) if not row[0])
        )
        <= 48
        for _, _, rows, failure in cases
    )
    return cases


def _check_trace(case, machine, capture, output, counters):
    _code, _stdin, rows, failure = case
    witness = WorkspaceWitness(WorkspaceModel("dinac-v1", ("frames", "input_cursor")))
    for index, (frames, text, cursor, reads, past_end) in enumerate(rows):
        if index:
            if failure and index == len(rows) - 1:
                with pytest.raises(esolangs.HaltError):
                    machine.step()
            else:
                machine.step()
        witness.sample(capture(), (frames, cursor))
        assert machine.halted == (not frames)
        assert output() == text
        assert counters() == (cursor, reads, past_end)
    return witness


def _raw(case, factory=_Machine):
    code, stdin, _rows, _failure = case
    io = ScriptedIO(stdin)
    machine = factory(code, io)
    return _check_trace(
        case,
        machine,
        machine.workspace_snapshot,
        io.getvalue,
        lambda: (io.position(), io.reads, io.past_end),
    )


def _stepped(case, debug):
    code, stdin, rows, failure = case
    vm = make_vm("DINAC", code, stdin=stdin)
    machine = Debugger(vm) if debug else vm

    def capture():
        return _capture_workspace(vm)

    def observation():
        return machine.observation if debug else _capture_observation(vm)

    _check_trace(
        case,
        machine,
        capture,
        lambda: machine.output,
        lambda: (
            observation().input_position,
            observation().input_reads,
            observation().input_past_end,
        ),
    )
    if debug:
        commands = (
            len(rows) - 2
            if failure
            else next(i for i, row in enumerate(rows) if not row[0])
        )
        assert machine.observation.steps == commands


def _execution(case, *, isolated):
    code, stdin, rows, failure = case
    _frames, text, cursor, reads, past_end = rows[-1]
    expected = esolangs.ExecutionResult(
        text,
        cursor,
        reads,
        past_end,
        completion=None if failure else CompletionReport(Completion.HALTED),
    )
    if failure:
        with pytest.raises(esolangs.HaltError) as caught:
            esolangs.run("DINAC", code, stdin=stdin, isolated=isolated)
        assert caught.value.observation == expected
        assert caught.value.partial_output == text
    else:
        assert esolangs.run("DINAC", code, stdin=stdin, isolated=isolated) == expected


def check_call_frames():
    cases = _cases()
    with guarded_worker(expected=len(cases)):
        for case in cases:
            _raw(case)
            for debug in (False, True):
                _stepped(case, debug)
            _execution(case, isolated=False)
        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(partial(_execution, isolated=True), cases))
    controls = ("caller", "pending", "returned", "blocks", "function", "scope", "order")
    controls += ("null_types",)
    for fault in controls:

        class Fault(_Machine):
            mode = fault

            def workspace_snapshot(self):
                saved = super().workspace_snapshot()
                frames, cursor = saved.parts
                if self.mode == "caller" and len(frames) > 1:
                    frames = frames[:-1]
                elif self.mode == "order" and len(frames) > 1:
                    frames = tuple(reversed(frames))
                else:
                    changed = []
                    for frame in frames:
                        row = list(frame)
                        if self.mode == "pending":
                            row[3] = None
                        elif self.mode == "returned":
                            row[4] = None
                        elif self.mode == "blocks":
                            row[2] = row[2][-1:]
                        elif self.mode == "function":
                            row[0] = 0
                        elif self.mode == "scope":
                            row[1] = ()
                        elif self.mode == "null_types":
                            row[5] = ()
                        changed.append(tuple(row))
                    frames = tuple(changed)
                return WorkspaceSnapshot(saved.model, (frames, cursor))

        case = _input("7", null=True) if fault == "null_types" else _recursive(2)
        with pytest.raises(AssertionError):
            _raw(case, Fault)

    wrong_output = after_step(_Machine, lambda self: self.io.print_str("!"))

    for factory in (stalled(_Machine), overread(_Machine), wrong_output):
        with pytest.raises(AssertionError):
            _raw(cases[0], factory)
    return len(cases), sum(len(case[2]) for case in cases), len(controls) + 3
