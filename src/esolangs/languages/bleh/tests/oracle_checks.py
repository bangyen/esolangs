"""Bounded generated ASTs; independent lazy heap and continuation machine."""

import sys
from itertools import product

import pytest

from esolangs.languages.bleh import interpreter as native
from esolangs.runtime._state import WorkspaceModel
from scripts.benchmark import WrittenState
from tests.interpreters.oracle_support import observed, overread, stalled
from tests.support.workspace_oracle import (
    WorkspaceOracle,
    charged_bits,
    missing_workspace,
    workspace_view,
)

_WORKSPACE = WorkspaceModel(
    "bleh-v1", ("control", "continuation", "fresh", "heap", "lookahead", "input_cursor")
)


def bits(text):
    return "".join(f"{byte:08b}" for byte in text.encode("utf-8"))


def b(value):
    return ("Bits", value) if value else ("Join", ())


def call(name, *args):
    return "Call", name, args


def debug(*args):
    return call("io.debug", *args)


def program(body, *branches):
    return (("main", (((), body),)), *branches)


def _source(functions):
    def emit(node):
        tag, *args = node
        if tag == "Bits":
            return args[0] or "[]"
        if tag == "Ref":
            return args[0]
        if tag == "Join":
            return "[" + ",".join(map(emit, args[0])) + "]"
        if tag == "Seq":
            return "{" + ";".join(map(emit, args[0])) + "}"
        if tag == "Call":
            return (
                args[0].replace("io.", "io::")
                + "("
                + ",".join(map(emit, args[1]))
                + ")"
            )
        if tag == "PText":
            return '"' + args[0] + '"'
        if tag == "PLit":
            return args[0] or "[]"
        if tag == "PAny":
            return "_"
        if tag == "PVar":
            return args[0]
        if tag == "PRest":
            return (args[0] or "") + ".."
        if tag == "PSplit":
            return (args[0] or "") + "[" + ",".join(map(emit, args[1])) + "]"
        raise AssertionError(tag)

    return "^:std::io;" + "".join(
        name
        + "".join(
            ":" + ",".join(map(emit, patterns)) + "=" + emit(body)
            for patterns, body in branches
        )
        + ";"
        for name, branches in functions
    )


def _record(node):
    """Construct declared immutable payload records; never call native semantics."""
    tag, *args = node
    if tag in ("Join", "Seq", "Lazy"):
        args = [tuple(_value(item) for item in args[0])]
    elif tag == "Call":
        args[1] = tuple(map(_record, args[1]))
    elif tag == "Slot":
        args[0] = _value(args[0])
    elif tag == "Evaluate":
        args = [_record(args[0]), _environment(args[1])]
    elif tag == "Try":
        args[1] = tuple(map(_value, args[1]))
    elif tag == "Part":
        args[0], args[2] = _record(args[0]), _environment(args[2])
    elif tag == "Arg":
        args[1], args[3] = tuple(map(_record, args[1])), _environment(args[3])
    constructor = native._Eval if tag == "Evaluate" else getattr(native, "_" + tag)
    return constructor(*args)


def _value(value):
    return _record(value) if isinstance(value, tuple) else value


def _environment(bindings):
    return tuple((name, _value(value)) for name, value in bindings)


class _Need(Exception):  # noqa: N818
    pass


class _Reference:
    def __init__(self, functions, stdin):
        self.stdin = stdin
        self.error = None
        self.funcs = dict(functions)
        self.control, self.frames, self.fresh, self.heap, self.ahead = (
            ("Try", "main", (), 0),
            [],
            0,
            {},
            None,
        )
        self.consumed, self.reads, self.past_end, self.output = (0, 0, 0, "")

    def force_value(self, value):
        if isinstance(value, str):
            return value
        if isinstance(value, tuple):
            return "".join(map(self.force_value, value[1]))
        if isinstance(self.heap[value], str):
            return self.heap[value]
        raise _Need(value)

    def match(self, patterns, values):
        bindings = {}

        def bind(name, value):
            if name not in bindings:
                bindings[name] = value
                return True
            return self.force_value(bindings[name]) == self.force_value(value)

        def level(pats, vals, aggregate):
            rest = [i for i, pat in enumerate(pats) if pat[0] == "PRest"]
            if not rest:
                return len(pats) == len(vals) and all(
                    (one(p, v) for p, v in zip(pats, vals, strict=True))
                )
            index = rest[0]
            suffix = len(pats) - index - 1
            if len(vals) < index + suffix:
                return False
            stop = len(vals) - suffix
            return (
                all(
                    (one(p, v) for p, v in zip(pats[:index], vals[:index], strict=True))
                )
                and (
                    not pats[index][1]
                    or bind(pats[index][1], aggregate(vals[index:stop]))
                )
                and all(
                    (
                        one(p, v)
                        for p, v in zip(pats[index + 1 :], vals[stop:], strict=True)
                    )
                )
            )

        def one(pattern, value):
            tag, *args = pattern
            if tag == "PAny":
                return True
            if tag == "PVar":
                return bind(args[0], value)
            value = self.force_value(value)
            if tag in ("PLit", "PText"):
                return value == (bits(args[0]) if tag == "PText" else args[0])
            return (not args[0] or bind(args[0], value)) and level(
                args[1], tuple(value), "".join
            )

        return (
            tuple(bindings.items())
            if level(patterns, values, lambda vals: ("Lazy", vals))
            else None
        )

    def capture(self):
        kont = None
        for frame in reversed(self.frames):
            kont = (_record(frame), kont)
        cells = frozenset(
            (
                (
                    address,
                    cell
                    if isinstance(cell, str)
                    else (_record(cell[0]), _environment(cell[1])),
                )
                for address, cell in self.heap.items()
            )
        )
        parts = (
            _record(self.control),
            tuple(map(_record, self.frames)),
            self.fresh,
            cells,
            self.ahead,
            self.consumed,
        )
        snapshot = (
            _record(self.control),
            kont,
            self.fresh,
            cells,
            self.ahead,
            self.consumed,
        )
        return (
            (
                snapshot,
                self.control[0] == "Ret" and (not self.frames),
                self.output,
                self.consumed,
                self.consumed,
            ),
            parts,
            self.reads,
            self.past_end,
        )

    def start_part(self, expr, index, env, acc):
        if expr[0] != "Seq" or index != len(expr[1]) - 1:
            self.frames.insert(0, ("Part", expr, index, env, acc))
        self.control = ("Evaluate", expr[1][index], env)

    def start_force(self, address):
        cell = self.heap[address]
        if isinstance(cell, str):
            self.control = ("Ret", cell)
        else:
            self.frames.insert(0, ("Update", address))
            self.control = ("Evaluate", cell[0], cell[1])

    def char(self):
        if self.ahead is not None:
            value = self.ahead
            self.ahead = None if value else ""
            return value
        if self.consumed == len(self.stdin):
            self.past_end += 1
            self.ahead = ""
            return ""
        value = self.stdin[self.consumed]
        self.consumed += 1
        self.reads += 1
        return value

    def try_control(self, args):
        name, values, branch = args
        if not self.funcs[name]:
            self.error = "index"
        else:
            patterns, body = self.funcs[name][branch]
            try:
                env = self.match(patterns, values)
            except _Need as need:
                self.frames.insert(0, self.control)
                self.start_force(need.args[0])
            else:
                if env is not None:
                    self.control = ("Evaluate", body, env)
                elif branch + 1 < len(self.funcs[name]):
                    self.control = ("Try", name, values, branch + 1)
                else:
                    self.error = "halt"

    def evaluate(self, args):
        expr, env = args
        kind, *values = expr
        if kind == "Ref":
            kind, values = ("Slot", [dict(env)[values[0]]])
        if kind == "Slot":
            value = values[0]
            if isinstance(value, int):
                self.start_force(value)
                return
            if isinstance(value, str):
                kind, values = ("Bits", [value])
            else:
                kind, values = ("Join", [tuple(("Slot", part) for part in value[1])])
                expr = (kind, values[0])
        if kind == "Bits":
            self.control = ("Ret", values[0])
        elif kind in ("Join", "Seq"):
            if values[0]:
                self.start_part(expr, 0, env, "")
            else:
                self.control = ("Ret", "")
        else:
            name, operands = values
            if name.startswith("io."):
                if operands:
                    self.frames.insert(0, ("Arg", name[3:], operands, 0, env, ()))
                    self.control = ("Evaluate", operands[0], env)
                else:
                    self.control = ("Do", name[3:], ())
            else:
                actual = []
                for operand in operands:
                    if operand[0] == "Bits":
                        actual.append(operand[1])
                    elif operand[0] in ("Ref", "Slot"):
                        actual.append(
                            dict(env)[operand[1]] if operand[0] == "Ref" else operand[1]
                        )
                    else:
                        actual.append(self.fresh)
                        self.heap[self.fresh] = (operand, env)
                        self.fresh += 1
                self.control = ("Try", name, tuple(actual), 0)

    def return_value(self, args):
        frame = self.frames.pop(0)
        kind, *values = frame
        if kind == "Update":
            self.heap[values[0]] = args[0]
        elif kind == "Try":
            self.control = frame
        elif kind == "Part":
            expr, index, env, acc = values
            acc = acc + args[0] if expr[0] == "Join" else ""
            if index + 1 == len(expr[1]):
                self.control = ("Ret", acc)
            else:
                self.start_part(expr, index + 1, env, acc)
        else:
            name, operands, index, env, prior = values
            prior = (*prior, args[0])
            if index + 1 == len(operands):
                self.control = ("Do", name, prior)
            else:
                self.frames.insert(0, ("Arg", name, operands, index + 1, env, prior))
                self.control = ("Evaluate", operands[index + 1], env)

    def builtin(self, args):
        name, values = args
        text = "".join(values)
        result = ""
        if name in ("next", "hasNext") and values:
            self.error = "halt"
        elif name == "next":
            result = bits(self.char())
        elif name == "hasNext":
            if self.ahead is None:
                self.ahead = self.char()
            result = "1" if self.ahead else "0"
        elif name == "debug":
            self.output += text or "[]"
        else:
            try:
                if len(text) % 8:
                    raise ValueError(text)
                decoded = bytes(
                    int(text[i : i + 8], 2) for i in range(0, len(text), 8)
                ).decode("utf-8")
            except ValueError:
                self.error = "halt"
            else:
                self.output += decoded
        if not self.error:
            self.control = ("Ret", result)

    def step(self):
        tag, *args = self.control
        methods = {
            "Try": self.try_control,
            "Evaluate": self.evaluate,
            "Ret": self.return_value,
            "Do": self.builtin,
        }
        methods[tag](args)


def _model(functions, stdin, cap):
    reference = _Reference(functions, stdin)
    trace = [reference.capture()]
    for _ in range(cap):
        if trace[-1][0][1]:
            break
        reference.step()
        trace.append(reference.capture())
        if reference.error:
            break
    if not reference.error and trace[-1][0][1]:
        trace.extend([reference.capture()] * 3)
    return (reference.error, trace)


def _agrees(factory, functions, stdin, cap):
    error, trace = _model(functions, stdin, cap)
    rows = [row[0] for row in trace]
    expected = iter(trace)

    def view(machine):
        row = next(expected)
        assert (machine.io.reads, machine.io.past_end) == row[2:]
        return machine.snapshot()

    checked = workspace_view(
        rows,
        _WORKSPACE,
        lambda row: (row[0][0], tuple(_frames(row[0][1])), *row[0][2:]),
        view,
    )
    assert observed(factory, _source(functions), stdin, checked, cap=cap) == (
        error,
        rows,
    )
    return error, trace


def _frames(kont):
    while kont is not None:
        yield kont[0]
        kont = kont[1]


def corpus():
    any_pattern = ("PAny",)

    def var(name):
        return "PVar", name

    def rest(name=None):
        return "PRest", name

    def split(*parts, name=None):
        return "PSplit", name, parts

    def literal(text):
        return "PLit", text

    def ref(name):
        return "Ref", name

    table = (
        ((literal("1"),), ("1",)),
        ((literal("0"),), ("1",)),
        ((("PText", "a"),), ("01100001",)),
        ((("PText", "a"),), ("1100001",)),
        ((var("x"),), ("1",)),
        ((split(var("a"), var("b")),), ("11",)),
        ((split(any_pattern, var("b")),), ("10",)),
        ((split(var("a"), var("b")),), ("101",)),
        ((split(var("a"), rest("b")),), ("101",)),
        ((split(any_pattern, rest(), name="x"),), ("1011",)),
        ((split(any_pattern, rest(), name="x"),), ("",)),
        ((split(var("a"), rest("b"), name="x"),), ("1011",)),
        *((((split(var("x"), var("x")),), (value,))) for value in ("00", "11", "10")),
        ((var("x"), literal("1")), ("1", "1")),
        ((var("x"), literal("1")), ("1", "0")),
        ((rest("x"),), ("1", "0", "10", "1")),
    )

    def with_f(body, branches):
        return program(body, ("f", branches))

    for patterns, args in table:
        branches = ((patterns, debug(b("1"))), ((rest(),), debug(b("0"))))
        yield with_f(call("f", *map(b, args)), branches), "", 256
    for length in range(6):
        for values in product("01", repeat=length):
            patterns = (split(var("x"), rest("middle"), var("x")),)
            branches = (
                (patterns, debug(ref("middle"), ref("middle"))),
                ((any_pattern,), debug(b("0"))),
            )
            yield with_f(call("f", b("".join(values))), branches), "", 256
    for value in ("001", "010", "01101", "01110"):
        patterns = (split(var("x"), rest("middle"), var("x"), literal("1")),)
        branches = ((patterns, debug(ref("middle"))), ((any_pattern,), debug(b("0"))))
        yield with_f(call("f", b(value)), branches), "", 256
    branches = (
        ((("PText", "a"),), b("1")),
        ((var("x"),), call("io.print", ref("x"), ref("x"))),
    )
    forced = with_f(call("f", call("io.next")), branches)
    for char, sentinel in product(("b", "é", "😀"), ("z", "!")):
        yield forced, char + sentinel, 256
    yield forced, "az", 256
    for stdin in ("", "a", "é\r\n", "😀z"):
        sequence = (
            "Seq",
            (
                debug(call("io.hasNext")),
                debug(call("io.hasNext")),
                debug(call("io.next")),
                debug(call("io.next")),
                debug(call("io.hasNext")),
            ),
        )
        for expr in (call("io.next"), call("io.hasNext"), sequence):
            yield program(expr), stdin, 128
    for expr in (
        b(""),
        b("1"),
        ("Join", (b("01"), b("10"))),
        ("Seq", (debug(b("1")), call("io.print", b("1")))),
        call("io.print", b("11111111")),
        call("io.next", call("io.next")),
        call("io.hasNext", call("io.next")),
    ):
        yield program(expr), "é", 128
    yield with_f(call("f", b("0")), (((literal("1"),), b("1")),)), "", 128
    for count in (1, 81):
        body = ("Seq", tuple(call("f", call("io.next")) for _ in range(count)))
        yield with_f(body, (((any_pattern,), b("")),)), "a" * count, 768
        yield with_f(body, (((var("x"),), ref("x")),)), "a" * count, 768
    yield with_f(call("f"), (((), call("f")),)), "", 128
    branches = (((var("x"),), call("f", ref("x"))),)
    yield with_f(call("f", call("io.next")), branches), "a", 128


def check_raw_bleh():
    results = [_agrees(native._Machine, *case) for case in corpus()]
    assert {error for error, _ in results} == {None, "halt"}
    assert any(not trace[-1][0][1] for error, trace in results if not error)
    body = (
        "Seq",
        (debug(call("io.hasNext")), debug(call("io.next")), call("f", call("io.next"))),
    )
    branches = (((("PVar", "x"),), ("Join", (("Ref", "x"), ("Ref", "x")))),)
    witness = program(body, ("f", branches))
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(missing_workspace(native._Machine, component), witness, "ab", 128)
    for factory in (stalled(native._Machine), _wrong_output()):
        with pytest.raises(AssertionError):
            _agrees(factory, program(debug(b("1"))), "", 32)
    for functions, expected in ((program(b("1")), 33), (program(b("")), 33)):
        trace = _model(functions, "", 32)[1]
        assert charged_bits(_WORKSPACE, (row[1] for row in trace)) == expected
    return len(results), len(_WORKSPACE.components) + 2


def _wrong_output():
    class Fault(native._Machine):
        def __init__(self, code, io):
            write = io.print_str
            io.print_str = lambda text: write("0" * len(text))
            super().__init__(code, io)

    return Fault


_FOCUS_COUNTS = {}


def _focus_check(value, context):
    assert value, context


def _focus_rejected(action):
    try:
        action()
    except AssertionError:
        return
    raise AssertionError("fault was accepted")


def _focus_literals():
    """Independent permanent table and terminal fixtures, in preserved corpus order."""
    yield from (
        (out, 0)
        for out in (
            "1",
            "0",
            "1",
            "0",
            "1",
            "1",
            "1",
            "0",
            "1",
            "1",
            "0",
            "1",
            "1",
            "1",
            "0",
            "1",
            "0",
            "1",
        )
    )
    for length in range(6):
        for value in range(2**length):
            text = format(value, f"0{length}b") if length else ""
            answer = "0"
            if length >= 2 and text[0] == text[-1]:
                answer = text[1:-1] * 2 or "[]"
            yield (answer, 0)
    for text in ("001", "010", "01101", "01110"):
        answer = text[1:-2] or "[]" if text[0] == text[-2] and text[-1] == "1" else "0"
        yield (answer, 0)
    for char in ("b", "é", "😀"):
        for _ in ("z", "!"):
            yield (char * 2, 1)


def _focus_prepare(engine):
    cases = tuple(engine.corpus())
    _focus_check(len(cases) == 118 <= 200, "preserved case count")
    _focus_check(
        [sum((cap == bound for _, _, cap in cases)) for bound in (128, 256, 768)]
        == [22, 92, 4],
        "preserved explicit caps",
    )
    predicted = tuple(engine._model(*case) for case in cases)
    boundaries = sum((len(trace) for _, trace in predicted))
    _focus_check(boundaries <= 29912 <= 40000, "modeled boundary envelope")
    expected = tuple(_focus_literals())
    _focus_check(len(expected) == 91, "old family literals")
    for index, ((output, reads), (error, trace)) in enumerate(
        zip(expected, predicted[:91], strict=True)
    ):
        row = trace[-1]
        _focus_check(error is None and row[0][1], ("old terminal completion", index))
        _focus_check(
            row[0][2:] == (output, reads, reads), ("old terminal literal", index)
        )
        _focus_check(row[2:] == (reads, 0), ("old exact read counters", index))
    _focus_check(
        {error for error, _ in predicted} == {None, "halt"}, "old error assertion"
    )
    _focus_check(
        any((not trace[-1][0][1] for error, trace in predicted if error is None)),
        "unfinished cases",
    )
    for error, trace in predicted:
        if error == "halt":
            _focus_check(
                trace[-1] == trace[-2], "failed builtin/match boundary is unchanged"
            )
    for index, output in ((92, ""), (93, ""), (94, "00[][]0")):
        error, trace = predicted[index]
        _focus_check(error is None and trace[-1][0][1], "empty EOF completes")
        _focus_check(trace[-1][0][2:] == (output, 0, 0), "EOF literal output/cursor")
        _focus_check(trace[-1][2:] == (0, 1), "cached EOF reads past end exactly once")
    for index, reads in ((112, 0), (113, 1), (114, 0), (115, 81)):
        error, trace = predicted[index]
        _focus_check(
            error is None and trace[-1][0][1], "growth/drain completes within cap"
        )
        _focus_check(
            trace[-1][0][2:] == ("", reads, reads), "lazy/forced literal consumption"
        )
        _focus_check(trace[-1][2:] == (reads, 0), "lazy/forced counters")
    _FOCUS_COUNTS.update(cases=118, old_families=91, modeled_boundaries=boundaries)
    return (cases, predicted)


def _focus_sweep(engine, case, prediction, factory=None, projection=None):
    """Check every native boundary, retained history, and both resource accountants."""
    from esolangs.exceptions import HaltError
    from esolangs.runtime.io import ScriptedIO

    functions, stdin, cap = case
    error, trace = prediction
    machine = (factory or engine.native._Machine)(
        engine._source(functions), ScriptedIO(stdin)
    )
    held = []
    measured = recount = None
    failure = None
    mismatches = 0
    for index, row in enumerate(trace):
        if index:
            try:
                machine.step()
            except HaltError:
                failure = "halt"
        state, parts, reads, past_end = row
        observed = (
            machine.snapshot(),
            machine.halted,
            machine.io.getvalue(),
            machine.io.position(),
            machine.io.progress(),
        )
        _focus_check(
            observed == state, ("native state/IO", index, engine._source(functions))
        )
        _focus_check(
            (machine.io.reads, machine.io.past_end) == (reads, past_end),
            ("read counters", index),
        )
        canonical = engine._WORKSPACE.capture(
            **dict(zip(engine._WORKSPACE.components, parts, strict=True))
        )
        expected = canonical if projection is None else projection(index, canonical)
        actual = machine.workspace_snapshot()
        _focus_check(actual == expected, ("capture", index))
        mismatches += actual != canonical
        if measured is None:
            measured, recount = (WrittenState(actual), WorkspaceOracle(expected))
        else:
            measured.sample(actual)
            recount.sample(expected)
        _focus_check(measured.bits == recount.bits, ("written charge", index))
        held.append(
            (
                machine.snapshot(),
                state[0],
                hash(machine.snapshot()),
                actual,
                expected,
                hash(actual),
            )
        )
    _focus_check(failure == error, "failure classification")
    _focus_check(
        all(
            (
                raw == saved
                and hash(raw) == digest
                and (capture == saved_capture)
                and (hash(capture) == capture_digest)
                for raw, saved, digest, capture, saved_capture, capture_digest in held
            )
        ),
        "held histories",
    )
    _focus_check(len(trace) <= cap + 4, "case cap")
    _FOCUS_COUNTS["native_boundaries"] = _FOCUS_COUNTS.get(
        "native_boundaries", 0
    ) + len(trace)
    return (measured.bits, recount, mismatches)


def _focus_witness(engine):
    body = (
        "Seq",
        (
            engine.debug(engine.call("io.hasNext")),
            engine.debug(engine.call("io.next")),
            engine.call("f", engine.call("io.next")),
        ),
    )
    branches = (((("PVar", "x"),), ("Join", (("Ref", "x"), ("Ref", "x")))),)
    return (engine.program(body, ("f", branches)), "ab", 128)


def _focus_masks(engine):
    """Six genuine changing fields; actual overrides preserve canonical execution."""
    from esolangs.runtime._state import WorkspaceSnapshot

    case = _focus_witness(engine)
    prediction = engine._model(*case)
    canonical = [
        engine._WORKSPACE.capture(
            **dict(zip(engine._WORKSPACE.components, row[1], strict=True))
        )
        for row in prediction[1]
    ]
    baseline = WorkspaceOracle(canonical[0])
    for capture in canonical[1:]:
        baseline.sample(capture)
    _focus_check(all(baseline.written), "all six genuinely populated/changing")
    _focus_sweep(engine, case, prediction)
    for component in range(6):
        for mode in ("late_initial", "none"):

            def project(_index, captured, component=component, mode=mode):
                parts = list(captured.parts)
                parts[component] = (
                    canonical[0].parts[component] if mode == "late_initial" else None
                )
                return WorkspaceSnapshot(captured.model, tuple(parts))

            class Fault(engine.native._Machine):
                def workspace_snapshot(self):
                    return project(0, super().workspace_snapshot())

            charge, reduced, mismatches = _focus_sweep(
                engine, case, prediction, Fault, project
            )
            _focus_check(mismatches > 0, ("nonvacuous mask", component, mode))
            _focus_check(
                not reduced.written[component],
                ("erased field not written", component, mode),
            )
            _focus_check(
                baseline.bits - charge == baseline.peaks[component],
                ("exact component charge loss", component, mode),
            )
            _focus_rejected(lambda: engine._agrees(Fault, *case))
    _FOCUS_COUNTS["populated_masks"] = 12


def _focus_constructors(engine):
    """Literal syntax errors occur before any IO, separate from modeled AST rows."""
    from esolangs.runtime.io import ScriptedIO

    for source in ("", "f := 1;", "main := ;"):
        port = ScriptedIO("λ")
        try:
            engine.native._Machine(source, port)
        except ValueError as error:
            _focus_check(type(error) is ValueError, "exact parser error type")
        else:
            raise AssertionError(("constructor refusal", source))
        _focus_check(
            (
                port.getvalue(),
                port.reads,
                port.past_end,
                port.position(),
                port.progress(),
            )
            == ("", 0, 0, 0, 0),
            "constructor IO untouched",
        )
    _FOCUS_COUNTS["constructors"] = 3


def _focus_faults(engine):
    case = (engine.program(engine.debug(engine.b("1"))), "ab", 32)
    for factory in (
        stalled(engine.native._Machine),
        engine._wrong_output(),
        overread(engine.native._Machine),
    ):
        _focus_rejected(lambda factory=factory: engine._agrees(factory, *case))
    for functions in (engine.program(engine.b("1")), engine.program(engine.b(""))):
        prediction = engine._model(functions, "", 32)
        _focus_check(
            engine.charged_bits(engine._WORKSPACE, (row[1] for row in prediction[1]))
            == 33,
            "literal33",
        )
        measured, _, _ = _focus_sweep(engine, (functions, "", 32), prediction)
        _focus_check(measured == 33, "actual literal33")
    _FOCUS_COUNTS["same_state_faults"] = 3
    _FOCUS_COUNTS["literal_anchors"] = 2


def _focus_writer(engine):
    """Refusal precedes control commit; retry duplicates only a physical prefix."""
    case = (
        engine.program(engine.call("io.print", engine.b(engine.bits("ab")))),
        "",
        64,
    )
    prediction = engine._model(*case)
    trace = prediction[1]
    boundary = next(
        (
            i
            for i, row in enumerate(trace)
            if isinstance(row[0][0][0], engine.native._Do)
        )
    )
    for partial in (False, True):
        _focus__writer_profile(engine, case, trace, boundary, partial)
    _FOCUS_COUNTS["writer_profiles"] = 2


def _focus__writer_profile(engine, case, trace, boundary, partial):
    from esolangs.runtime.io import ScriptedIO

    io = ScriptedIO("")
    machine = engine.native._Machine(engine._source(case[0]), io)
    held = []
    meter = oracle = None

    def capture(row, output):
        nonlocal meter, oracle
        expected = engine._WORKSPACE.capture(
            **dict(zip(engine._WORKSPACE.components, row[1], strict=True))
        )
        actual = machine.workspace_snapshot()
        _focus_check(
            actual == expected and machine.snapshot() == row[0][0],
            "writer native state",
        )
        _focus_check(
            io.getvalue() == output and (io.reads, io.past_end) == (0, 0), "writer IO"
        )
        _focus_check(
            io._newline is bool(output), "writer physical-prefix newline policy"
        )
        if meter is None:
            meter, oracle = (WrittenState(actual), WorkspaceOracle(expected))
        else:
            meter.sample(actual)
            oracle.sample(expected)
        _focus_check(meter.bits == oracle.bits, "writer charge")
        held.append((actual, expected, hash(actual)))

    for index in range(boundary + 1):
        if index:
            machine.step()
        capture(trace[index], "")
    original = io.print_str
    calls = 0

    def refuse(text):
        nonlocal calls
        calls += 1
        _focus_check(text == "ab", "actual print argument")
        if partial:
            original("a")
        raise OSError("writer refused")

    io.print_str = refuse
    try:
        machine.step()
    except OSError as error:
        _focus_check(str(error) == "writer refused", "writer failure identity")
    else:
        raise AssertionError("writer refusal swallowed")
    prefix = "a" if partial else ""
    capture(trace[boundary], prefix)
    _focus_check(calls == 1, "one refused attempt")
    io.print_str = original
    for index in range(boundary + 1, len(trace)):
        machine.step()
        capture(trace[index], prefix + "ab")
    _focus_check(machine.halted and calls == 1, "retry and idle")
    _focus_check(
        all(
            (
                actual == expected and hash(actual) == digest
                for actual, expected, digest in held
            )
        ),
        "writer retained captures",
    )


def check_accounting_bleh():
    """Preserve the full bounded engine, literals, histories and positive faults."""
    engine = sys.modules[__name__]
    _FOCUS_COUNTS.clear()
    cases, predicted = _focus_prepare(engine)
    for case, prediction in zip(cases, predicted, strict=True):
        _focus_sweep(engine, case, prediction)
    assert check_raw_bleh() == (118, 8)
    _focus_masks(engine)
    _focus_constructors(engine)
    _focus_faults(engine)
    _focus_writer(engine)
