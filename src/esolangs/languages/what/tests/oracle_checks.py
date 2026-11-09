"""Closed-form checks for arithmetic, counted loops, and dual-slot guards."""

from itertools import product
from operator import add, floordiv, mul, sub

import pytest

from esolangs import run as public_run
from esolangs.exceptions import ArgumentError, HaltError
from esolangs.languages.what import interpreter as native
from esolangs.languages.what.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import observed, overread, stalled
from tests.support import workspace_oracle as workspace

from .full_oracle import _assemble, _Case, _cases, _Guard, _metadata, _model, _parts

_WORKSPACE = workspace.workspace_model(
    "what-v1", "instruction pointer integers strings input_cursor"
)


def _output(factory, source, stdin=""):
    io = ScriptedIO(stdin)
    machine = factory(source, io)
    for _ in range(128):
        if machine.halted:
            break
        machine.step()
    assert machine.halted, source
    assert io.position() == len(stdin)
    return io.getvalue()


def _arithmetic(factory, left, right, token, operation):
    source = f'{left}."tag"{right}{token}!!"!"!!!'
    if token == "/" and not left:
        with pytest.raises(HaltError, match="division by zero"):
            _output(factory, source)
        return
    assert _output(factory, source) == f"{operation(right, left) % 65536}tag!"


def check_raw_what():
    for left, right, (token, operation) in product(
        (0, 1, 11, 65535),
        (0, 2, 10, 65534),
        zip("+-*/", (add, sub, mul, floordiv), strict=True),
    ):
        _arithmetic(_Machine, left, right, token, operation)
    for count, value in product(range(1, 9), ("A", "Ω", "\n")):
        source = f'1.{count}("x"-)!!!.?!!'
        assert _output(_Machine, source, value) == "x" * count + str(ord(value))
    for literal, current, op in product(
        (0, 2, 9), (0, 3, 9), (":", "<", ">", ";", ":;", "<>")
    ):
        tests = {
            ":": literal == current,
            "<": literal < current,
            ">": literal > current,
        }
        comparisons = op.replace(";", "") or ":"
        holds = any(tests[t] for t in comparisons) != (";" in op)
        source = f'{current}[{literal}{op}"yes"]"end"!!!'
        assert _output(_Machine, source) == ("yes" if holds else "") + "end"

    class ReversedSubtraction(_Machine):
        def __init__(self, code, io):
            super().__init__(code.replace("-", "+"), io)

    with pytest.raises(AssertionError):
        _arithmetic(ReversedSubtraction, 2, 7, "-", sub)

    _check_workspace_cases()
    _check_failure_history()
    _check_seed_refusal()


def _view(machine, case):
    assert case.operations is not None
    assert all(type(token) is native._Token for token in machine.tokens)
    assert tuple(
        (t.kind, t.at, t.arg, t.text, t.literal, t.ops) for t in machine.tokens
    ) == _metadata(case)
    pc, pointer, integer_chunks, string_chunks = machine.state
    assert type(pc) is type(pointer) is int
    assert type(integer_chunks) is type(string_chunks) is tuple
    assert all(type(chunk) is tuple for chunk in (*integer_chunks, *string_chunks))
    integers = tuple(value for chunk in integer_chunks for value in chunk)
    strings = tuple(value for chunk in string_chunks for value in chunk)
    assert len(integers) == len(strings) == 256
    assert all(type(value) is int for value in integers)
    assert all(type(value) is str for value in strings)
    port = machine.io
    assert type(port.reads) is type(port.past_end) is type(port._line_reads) is int
    assert type(port._character_reads) is type(port._newline) is bool
    assert port._pending == ""
    return (
        pc,
        pointer,
        integers,
        strings,
        machine.ip,
        port.reads,
        port.past_end,
        port._line_reads,
        port._character_reads,
        port._newline,
    )


def _cycle(machine):
    pc, pointer, integers, strings, cursor = machine.snapshot()
    return (
        pc,
        pointer,
        tuple(v for chunk in integers for v in chunk),
        tuple(v for chunk in strings for v in chunk),
        cursor,
    )


def _check_case(factory, case):
    expected = _model(case)
    pending = iter(expected[1])
    held = []

    def view(machine):
        row = next(pending)
        state = _view(machine, case)
        assert state == row[0]
        assert _cycle(machine) == (*row[0][:4], row[-1])
        snap = machine.snapshot()
        held.append((snap, hash(snap)))
        assert all(hash(saved) == digest for saved, digest in held)
        return state

    checked = workspace.workspace_view(expected[1], _WORKSPACE, _parts, view)
    assert observed(factory, case.source, case.stdin, checked, cap=128) == expected, (
        case.source
    )


def _witness():
    return _assemble((("num", 65), (".", 0), ("str", "x"), ("in", 1), ("out", 2)), "A")


def _extra_cases():
    cases = [
        _witness(),
        _assemble(()),
        _assemble((("num", 65), ("out", 1), ("out", 4))),
        _assemble((("num", 5), ("sub", "abc"), ("out", 2))),
        _assemble((("str", "x" * 256), ("out", 3))),
    ]
    for size in (1, 2, 3):
        prefix = (("str", "a"),) if size == 3 else (("num", 5),)
        cases.append(_assemble((*prefix, ("in", size), ("out", 3 if size == 3 else 2))))
    cases.extend(
        _assemble((("in", 2), ("out", 2)), text)
        for text in ("  +65\nQ", "0" * 5000 + "65\nQ", "-1", "70000", "٦٥", "6_5")
    )
    cases.extend(
        (
            _assemble(
                (
                    ("num", 5),
                    ("in", 1),
                    ("out", 2),
                    ("in", 1),
                    ("out", 2),
                    ("in", 1),
                    ("out", 2),
                )
            ),
            _assemble((("str", "a"), ("in", 3), ("out", 3)), "\r\nQ"),
            _assemble((("in", 3),), "x" * 257),
            _assemble((("in", 1),), "𐀀"),
            _assemble((("num", 55296), ("out", 1))),
            _assemble((("str", "x" * 257),)),
            _assemble(((",", 0),)),
            _assemble((("+", 0),)),
        )
    )
    cases.extend(
        _assemble(
            (
                ("str", "b"),
                ("cond", _Guard("a", operators, 4)),
                ("str", "yes"),
                ("]", 0),
                ("out", 3),
            )
        )
        for operators in ("<", "<;")
    )
    cases.extend(
        _Case(source, "unread", None)
        for source in (
            '"a',
            "'a",
            "(",
            ")",
            "[1:",
            "[:]",
            "[1]",
            "[1::]",
            "65536",
            '"\\t"',
        )
    )
    return cases


def _check_workspace_cases():
    cases = _cases()
    for case in (*cases, *_extra_cases()):
        _check_case(_Machine, case)
    case = _witness()
    error, rows = _model(case)
    assert error is None
    machine = _Machine(case.source, ScriptedIO(case.stdin))
    witness = workspace.WorkspaceWitness(_WORKSPACE)
    for index, row in enumerate(rows):
        witness.sample(machine.workspace_snapshot(), _parts(row))
        if index + 1 < len(rows):
            machine.step()
    witness.finish()
    assert all(witness.expected.written)
    assert witness.measured.bits == witness.expected.bits == 281
    workspace.check_erasures(_WORKSPACE, _check_case, _Machine, case)
    for field in (2, 3):

        class ShortTape(_Machine):
            def workspace_snapshot(self, _field=field):
                saved = super().workspace_snapshot()
                values = list(saved.parts)
                values[_field] = values[_field][:-1]
                return type(saved)(saved.model, tuple(values))

        with pytest.raises(AssertionError):
            _check_case(ShortTape, case)
    for factory in (stalled(_Machine), overread(_Machine)):
        with pytest.raises(AssertionError):
            _check_case(factory, case)


def _check_history(case, rows, failed, error_type, decorate):
    port = ScriptedIO(case.stdin)
    machine = _Machine(case.source, port)
    restore = decorate(port)
    witness = workspace.WorkspaceWitness(_WORKSPACE)
    held = []
    for index, row in enumerate(rows):
        if index == failed:
            with pytest.raises(error_type) as caught:
                machine.step()
            assert type(caught.value) is error_type
            restore()
        elif index:
            machine.step()
        assert (
            _view(machine, case),
            machine.halted,
            port.getvalue(),
            port.position(),
            port.progress(),
        ) == row
        assert _cycle(machine) == (*row[0][:4], row[-1])
        witness.sample(machine.workspace_snapshot(), _parts(row))
        cycle = machine.snapshot()
        capture = machine.workspace_snapshot()
        held.append((cycle, hash(cycle), capture, hash(capture)))
        assert all(hash(c) == ch and hash(w) == wh for c, ch, w, wh in held)
    witness.finish()


def _check_failure_history():
    for start, tail, payload in (
        ((("num", 12), ("out", 2)), (), 12),
        ((("num", 12), ("out", 2)), (("num", 7), ("out", 2)), 12),
        ((("str", "ab"), ("out", 3)), (), "ab"),
        ((("str", "ab"), ("out", 3)), (("str", "c"), ("out", 3)), "ab"),
    ):
        case = _assemble((*start, *tail))
        error, normal = _model(case)
        assert error is None
        text = str(payload)
        for prefix in ("", text[:1]):
            rows = []
            for index, normal_row in enumerate(normal):
                row = normal_row
                if index >= 2:
                    state = (*row[0][:9], False if index < 4 or not tail else row[0][9])
                    row = state, row[1], prefix + row[2][len(text) :], row[3], row[4]
                rows.append(row)
            refused = []

            def decorate(port, _prefix=prefix, _refused=refused, _payload=payload):
                write = port._write

                def fail(value):
                    assert type(value) is type(_payload)
                    assert value == _payload
                    _refused.append(value)
                    if _prefix:
                        write(_prefix)
                    raise ValueError("controlled physical refusal")

                port._write = fail
                return lambda: setattr(port, "_write", write)

            _check_history(case, rows, 2, ValueError, decorate)
            assert refused == [payload]
    case = _assemble((("num", 0), ("in", 1), ("out", 2)), "A")
    error, normal = _model(case)
    assert error is None
    rows = [*normal[:2], normal[1], *normal[2:]]
    refused = []

    def decorate(port):
        read = port.input_char

        def fail():
            refused.append(True)
            raise ValueError("controlled read refusal")

        port.input_char = fail
        return lambda: setattr(port, "input_char", read)

    _check_history(case, rows, 2, ValueError, decorate)
    assert refused == [True]


def _check_seed_refusal():
    class Unread:
        def read(self):
            raise AssertionError("input guard reached")

    with pytest.raises(ArgumentError) as caught:
        public_run("What!?", "1!!", stdin=Unread(), seed=0)
    assert type(caught.value) is ArgumentError

    assert "draws no random values" in str(caught.value)
    with pytest.raises(AssertionError, match="input guard reached"):
        public_run("What!?", "1!!", stdin=Unread())
