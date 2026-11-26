"""Tests for the Bleh interpreter."""

import pickle
import sys
from dataclasses import fields, replace
from itertools import product

import pytest

from esolangs import Catalog, ExecutionLimits, ExecutionResult, Language
from esolangs.exceptions import InterpreterLimitError, ProgramError
from esolangs.languages.bleh.interpreter import _Lazy, _Machine, run
from esolangs.runtime._vm_adapter import _capture_workspace
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import check_terminal
from tests.interpreters.runner import native_runner
from tests.support.vm_support import assert_rejected_output_retry

#: The page's pattern table: pattern, arguments, ``1`` if they match.
TABLE = [
    ("1", "1", "1"),
    ("0", "1", "0"),
    ('"a"', "01100001", "1"),
    ('"a"', "1100001", "0"),
    ("x", "1", "1"),
    ("[a, b]", "11", "1"),
    ("[_, b]", "10", "1"),
    ("[a, b]", "101", "0"),
    ("[a, b..]", "101", "1"),
    ("x[_, ..]", "1011", "1"),
    ("x[_, ..]", "[]", "0"),
    ("x[a, b..]", "1011", "1"),
    ("[x, x]", "00", "1"),
    ("[x, x]", "11", "1"),
    ("[x, x]", "10", "0"),
    ("x, 1", "1, 1", "1"),
    ("x, 1", "1, 0", "0"),
    ("x..", "1, 0, 10, 1", "1"),
]


_out = native_runner(run)


@pytest.mark.parametrize(("pattern", "args", "expected"), TABLE)
def test_the_page_pattern_table(pattern: str, args: str, expected: str) -> None:
    code = (
        f"^:std::io; main := f({args}); f : {pattern} = io::debug 1 : .. = io::debug 0;"
    )
    assert _out(code) == expected


def test_a_forced_argument_is_read_once(monkeypatch) -> None:
    """Call by need: ``x`` is forced by the literal and reused, not reread."""
    code = '^:std::io; main := f(io::next()); f : "a" = 1 : x = io::print(x, x);'

    # Retry does not rerun a committed write prefix or reclassify sink faults.
    source = '^:std::io; main := io::print("ab");'
    assert_rejected_output_retry(
        "Bleh",
        source,
        "ab",
        "ab",
        prefix=4,
        monkeypatch=monkeypatch,
        unchanged_if_unwritten=True,
        following_writes=(),
    )
    debugger = Language("Bleh").make_debugger(source)
    fault = ProgramError("writer refused")

    def fail(_io, _text):
        raise fault

    with monkeypatch.context() as port:
        port.setattr(ScriptedIO, "_write", fail)
        with pytest.raises(ProgramError) as rejected:
            debugger.run(limits=ExecutionLimits(max_steps=16))
    assert rejected.value is fault
    assert fault.observation == ExecutionResult("", 0, 0, 0, steps=4)
    assert debugger.run(limits=ExecutionLimits(max_steps=16)) == "halted"
    assert debugger.observation.output == "ab"

    def check(program, expected, stdin="", consumed=0):
        check_terminal(
            _Machine,
            program,
            stdin,
            lambda m: (
                (m.state.control.value, m.state.kont, m.ahead) if m.halted else None
            ),
            (("", None, None), True, expected, consumed, consumed),
            cap=256,
        )

    # The first and last bits must agree. Reprinting the bound middle
    # checks that the rest pattern consumes precisely the intervening bits.
    for length in range(6):
        for parts in product("01", repeat=length):
            bits = "".join(parts)
            program = (
                f"^:std::io; main := f({bits or '[]'}); "
                "f : [x, middle.., x] = io::debug(middle, middle) "
                ": _ = io::debug 0;"
            )
            expected = "0"
            if length >= 2 and bits[0] == bits[-1]:
                expected = bits[1:-1] * 2 or "[]"
            check(program, expected)
            assert _out(program) == expected, bits

    for bits in ("001", "010", "01101", "01110"):
        program = (
            f"^:std::io; main := f({bits}); "
            "f : [x, middle.., x, 1] = io::debug(middle) "
            ": _ = io::debug 0;"
        )
        expected = (
            (bits[1:-2] or "[]") if bits[0] == bits[-2] and bits[-1] == "1" else "0"
        )
        check(program, expected)
        assert _out(program) == expected, bits

    for char, sentinel in product(("b", "é", "😀"), ("z", "!")):
        assert _out(code, char + sentinel) == char * 2
        check(code, char * 2, char + sentinel, 1)

    api = Language("Bleh")
    limits = ExecutionLimits(max_steps=30)
    next_character = "io::print(io::next())"
    for expression, steps in (
        (next_character, 3),
        (f"{{io::hasNext(); {next_character}}}", 7),
    ):
        source = f"^:std::io; main := {expression};"
        debugger = api.make_debugger(source, stdin="\ud800A")
        with pytest.raises(ProgramError, match="surrogates not allowed") as first:
            debugger.run(limits=limits)
        expected = ExecutionResult("", 1, 1, 0, steps=steps)
        assert first.value.observation == debugger.observation == expected
        snapshot = debugger.snapshot()
        assert snapshot[-2] == "\ud800"
        with pytest.raises(ProgramError, match="surrogates not allowed") as second:
            debugger.run(limits=limits)
        assert second.value is not first.value
        assert second.value.observation == debugger.observation == expected
        assert debugger.snapshot() == snapshot
        valid = api.run(source, stdin="éA", limits=limits)
        assert (valid.output, valid.input_position, valid.input_reads) == ("é", 1, 1)
        eof = api.run(source, limits=limits)
        assert (eof.output, eof.input_reads, eof.input_past_end) == ("", 0, 1)

    from esolangs.languages.bleh import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Bleh",
        code,
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("bz", "bb"), ("cz", "cc"), ("dz", "dd")),
    )


@pytest.mark.medium
def test_nested_source_respects_the_parent_recursion_limit() -> None:
    language = Language("Bleh")
    original = sys.getrecursionlimit()

    def source(depth: int) -> str:
        operand = "{" * depth + '"A"' + "}" * depth
        return f"^:std::io; main := io::print({operand});"

    def split(depth: int) -> str:
        pattern = "[" * depth + "_" + "]" * depth
        return f'^:std::io; f: {pattern} = "A"; main := io::print(f(1));'

    def check_routes(program: str, steps: int) -> None:
        local = language.run(program, limits=ExecutionLimits(max_steps=600))
        assert (local.output, local.steps) == ("A", steps)
        for deadline in ({"total_timeout": 3}, {"execution_timeout": 3}):
            assert (
                language.run(program, limits=ExecutionLimits(max_steps=600, **deadline))
                == local
            )
        debugger = language.make_debugger(program)
        debugger.step()
        hash(debugger.snapshot())
        assert _capture_workspace(debugger.vm).model.name == "bleh-v1"
        assert debugger.run(limits=ExecutionLimits(max_steps=600)) == "halted"
        assert debugger.observation == local

    try:
        sys.setrecursionlimit(160)
        check_routes(source(79), 84)
        check_routes(split(80), 7)
        forwards = "".join(f"f{i}: x.. = f{i + 1}(x);" for i in range(100))
        check_routes(
            f'^:std::io; {forwards} f100: 1 = "A"; main := io::print(f0(1));', 207
        )
        message = None
        for options in (
            {},
            {"limits": ExecutionLimits(max_steps=500)},
            {"isolated": True},
            {"limits": ExecutionLimits(execution_timeout=3)},
        ):
            assert language.execute(source(1), **options).unwrap().output == "A"
            for program in (source(80), source(85), split(81)):
                limited = language.execute(program, **options)
                assert limited.status == "limit"
                assert isinstance(limited.error, InterpreterLimitError)
                assert limited.observation == ExecutionResult("", 0, 0, 0)
                message = message or str(limited.error)
                assert "recursed deeper" in message
                assert str(limited.error) == message
        sys.setrecursionlimit(400)
        assert language.run(source(85), isolated=True).output == "A"
        sys.setrecursionlimit(1000)
        check_routes(source(499), 504)
        _check_recursive_snapshot_formatting(language)
        _check_shared_lazy_comparison()
    finally:
        sys.setrecursionlimit(original)


def _check_recursive_snapshot_formatting(language: Language) -> None:
    shallow = language.make_debugger('^:std::io; main := io::print(["A", {"B"}]);')
    shallow.step()
    assert repr(shallow.snapshot()) == (
        "(_Eval(expr=_Call(func='io.print', args=(_Join(parts=("
        "_Bits(value='01000001'), _Seq(parts=(_Bits(value='01000010'),)))),)), "
        "env=()), None, 0, frozenset(), None, 0)"
    )

    depth = 12
    forwards = "".join(f"f{i}: x.. = f{i + 1}(x,x);" for i in range(depth))
    shared = language.make_debugger(
        f'^:std::io; {forwards} f{depth}: .. = io::print("A"); main := f0(1);'
    )
    for _ in range(2 * depth + 2):
        shared.step()
    snapshot = shared.snapshot()
    first, second = snapshot[0].args
    assert first is second
    for value in (snapshot, _capture_workspace(shared.vm)):
        rendered = repr(value)
        assert "_Lazy(...)" in rendered
        assert len(rendered) < 8000
    assert shared.snapshot() == snapshot
    assert shared.run(limits=ExecutionLimits(max_steps=10)) == "halted"
    assert shared.output == "A"

    declaration = language.catalog.languages[language.name]
    contract = replace(
        declaration.contract,
        answer_mode="termination",
        answer_values=("halts", "diverges"),
    )
    scoped = Catalog([replace(declaration, contract=contract)]).bind(language.name)
    operand = "{" * 499 + '"A"' + "}" * 499
    source = f"loop: x = loop(x); main := loop({operand});"
    artifact = scoped.from_source(source)
    local = scoped.evaluate(artifact, [1], limits=ExecutionLimits(max_steps=12))
    worker = scoped.evaluate(
        artifact, [1], limits=ExecutionLimits(max_steps=12, total_timeout=3)
    )
    assert local == worker
    assert local.answer == "1"
    assert local.termination is not None
    assert local.termination.commands == 5

    debugger = language.make_debugger(source)
    for _ in range(3):
        debugger.step()
    snapshot = debugger.snapshot()
    for value in (snapshot, _capture_workspace(debugger.vm), local, worker):
        rendered = repr(value)
        assert "_Seq(...)" in rendered
        assert len(rendered) < 8000
    assert debugger.snapshot() == snapshot
    assert hash(debugger.snapshot()) == hash(snapshot)

    source = f"{forwards} f{depth}: x, _ = loop(x); loop: x = loop(x); main := f0(1);"
    artifact = scoped.from_source(source)
    local = scoped.evaluate(artifact, [1], limits=ExecutionLimits(max_steps=64))
    worker = scoped.evaluate(
        artifact, [1], limits=ExecutionLimits(max_steps=64, total_timeout=3)
    )
    assert local == worker
    assert local.answer == "1"
    assert local.termination is not None
    assert local.termination.cycle is not None
    assert "_Lazy(" in repr(local.termination.cycle.state)


def _check_shared_lazy_comparison() -> None:
    comparisons = hashes = 0

    class Probe(str):
        def __eq__(self, other: object) -> bool:
            nonlocal comparisons
            comparisons += 1
            return str.__eq__(self, other)

        def __hash__(self) -> int:
            nonlocal hashes
            hashes += 1
            return str.__hash__(self)

    left, right = _Lazy((Probe("1"),)), _Lazy((Probe("1"),))
    for _ in range(12):
        left, right = _Lazy((left, left)), _Lazy((right, right))
    assert left == right
    assert comparisons == 1
    fingerprint = hash(left)
    for _ in range(3):
        assert hash(left) == fingerprint
    assert hashes == 1
    assert hash((left.parts,)) == fingerprint

    leaf = _Lazy(("1",))
    shared = _Lazy((leaf, leaf))
    expanded = _Lazy((_Lazy(("1",)), _Lazy(("1",))))
    assert shared == expanded
    assert hash(shared) == hash(expanded) == hash((shared.parts,))
    assert shared != _Lazy((leaf, _Lazy(("0",))))
    assert shared != _Lazy((leaf,))
    assert [field.name for field in fields(shared)] == ["parts"]

    cold = _Lazy((_Lazy(("1",)), _Lazy(("1",))))
    stored = pickle.dumps(cold)
    assert hash(cold) == hash(expanded)
    assert pickle.dumps(cold) == stored
    restored = pickle.loads(stored)
    assert restored == expanded
    assert hash(restored) == hash(expanded)
