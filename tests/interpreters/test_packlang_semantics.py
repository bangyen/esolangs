"""Independent Packlang transitions, parsing, frames and generated execution."""

import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.packlang import _Machine
from esolangs.tools.packlang import packlang
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.packlang_cases import (
    PORT_PROGRAMS,
    array_control_cases,
    evaluate,
    expression,
    expression_cases,
    render,
    scalar_cases,
)
from tests.interpreters.packlang_observer import check


def test_scalar_rules():
    assert scalar_cases() == 144


def test_array_and_guard_rules():
    assert array_control_cases() == 180


def test_expression_scanner_and_precedence():
    assert expression_cases() == 467


@pytest.mark.parametrize("shard", range(20))
def test_nested_call_frames(shard):
    for seed in range(shard, 200, 20):
        node = expression(random.Random(71377 + seed), 4)
        output = []
        answer = evaluate(node, output)
        output.append(chr(answer % 256))
        source = (
            (
                "Dependency : IO { Integer flip : Integer x { charPut(x); x ^"
                " 1; } Integer zero : Integer x { charPut(x); !x; } } helpers"
                "; Package : IO, helpers { Integer main { charPut("
            )
            + render(node)
            + "); } } p;"
        )
        result = check(source)
        assert result["output"] == "".join(output)


@pytest.mark.parametrize(
    ("n", "shard"),
    [
        (1, 0),
        (2, 0),
        *[pytest.param(3, shard, marks=pytest.mark.medium) for shard in range(16)],
    ],
)
@pytest.mark.parametrize("width", [None, 1, 7, 11, 13, 40, 80, 100])
def test_every_small_table(n, shard, width):
    stride = 16 if n == 3 else 1
    for value in range(shard, 1 << (1 << n), stride):
        table = format(value, f"0{1 << n}b")
        source = packlang(table, width)
        if width is not None:
            assert max(map(len, source.splitlines())) <= max(width, 7)
        for row, answer in enumerate(table):
            result = check(source, format(row, f"0{n}b"))
            assert result["output"] == answer
            assert result["reads"] == n


@pytest.mark.parametrize("source", PORT_PROGRAMS)
@pytest.mark.parametrize("stdin", ["", "A", "\n", "λ🙂"])
def test_ports_arrays_recursion_and_package_scope(source, stdin):
    check(source, stdin)


def test_cursorless_reads_reach_eof_before_cycling():
    class Cursorless(ScriptedIO):
        def position(self):
            return None

    source = (
        "Package : IO { Char x; Integer main { While 1 Do { charGet(x"
        "); INIT x; } } } p;"
    )
    port = Cursorless("ABCD")
    machine = _Machine(source, port)
    assert run_until_halt_or_cycle(machine, 100) is False
    assert port.reads == 4
    assert port.past_end > 0


def test_snapshot_distinguishes_static_programs():
    first = "Package : IO { Char x; Integer main { charPut(65); } } p;"
    second = first.replace("65", "66")
    assert (
        _Machine(first, ScriptedIO()).snapshot()
        != _Machine(second, ScriptedIO()).snapshot()
    )


def test_foreign_variables_are_inaccessible():
    source = (
        "Package { Integer secret; Integer helper { 0; } } hidden; Pa"
        "ckage : IO { Integer main { INCR secret; charPut(secret); } "
        "} visible;"
    )
    machine = _Machine(source, ScriptedIO())
    with pytest.raises(HaltError, match="undefined variable 'secret'"):
        machine.step()


@pytest.mark.parametrize(
    "source",
    [
        "Package { Integer 123; Integer main { 0; } } p;",
        "Package { Integer 123 { 0; } Integer main { 0; } } p;",
        "Package { Integer main { 0; } } 123;",
        "Package { Integer f : Integer 123 { 0; } Integer main { 0; } } p;",
    ],
)
def test_declarations_require_identifiers(source):
    with pytest.raises(ValueError, match="expected an identifier"):
        _Machine(source, ScriptedIO())


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "Package { Integer(7,3,3,7) x; Integer main { 0; } } p;",
            "minimum exceeds maximum",
        ),
        ("Package { Integer(0 255 255 0) x; Integer main { 0; } } p;", "expected"),
        (
            "Package { Array(Char,2) a; Integer main { charGet(a(0,1)); } } p;",
            "exactly one index",
        ),
    ],
)
def test_invalid_type_and_input_target_shapes(source, message):
    with pytest.raises(ValueError, match=message):
        _Machine(source, ScriptedIO())


@pytest.mark.parametrize(
    "table", ["00", "11", "0110", "11111110", "01101001", "10000000"]
)
def test_balanced_layout_executes_every_row(table):
    from esolangs.tools.packlang import balance_packlang

    source = balance_packlang(table, packlang(table))
    n = len(table).bit_length() - 1
    for row, answer in enumerate(table):
        result = check(source, format(row, f"0{n}b"))
        assert result["output"] == answer
        assert result["reads"] == n


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "Package { Integer main { 0; } Integer main { 1; } } p;",
            "duplicate function",
        ),
        (
            "Package { Integer main { 0; } } p; Package { Integer main { 0; } } q;",
            "multiple parameterless",
        ),
    ],
)
def test_ambiguous_program_declarations_are_rejected(source, message):
    with pytest.raises(ValueError, match=message):
        _Machine(source, ScriptedIO())


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("charPut(cell(length));", "not an array"),
        ("charPut(row(0,1));", "exactly one index"),
    ],
)
def test_invalid_array_expressions_halt(body, message):
    source = (
        "Package : IO { Char cell; Array(Char,2) row; Integer main { "
        + body
        + " } } p;"
    )
    machine = _Machine(source, ScriptedIO())
    with pytest.raises(HaltError, match=message):
        run_until_halt_or_cycle(machine, 100)


def test_ambiguous_dependency_calls_halt():
    source = (
        "Dependency { Integer f { 0; } } a; "
        "Dependency { Integer f { 1; } } b; "
        "Package : a,b { Integer main { f(); } } p;"
    )
    machine = _Machine(source, ScriptedIO())
    with pytest.raises(HaltError, match="ambiguous function"):
        run_until_halt_or_cycle(machine, 100)


@pytest.mark.parametrize(
    ("node", "message"),
    [
        (("not", 5), "malformed expression node"),
        (("lit", True), "expected a number"),
        (("lit", "x"), "expected a number"),
        (("bogus", 0), "cannot evaluate"),
        (("apply", "missing", (("lit", 0),)), "unresolved call"),
    ],
)
def test_malformed_internal_expressions_are_rejected(node, message):
    from esolangs.interpreters.other.packlang import _evaluate, _Program

    store = (("cell", 7),)
    with pytest.raises(HaltError, match=message):
        _evaluate(node, store, _Program(), "p")


def test_unknown_internal_nodes_preserve_call_state():
    from esolangs.interpreters.other.packlang import (
        _pending_call,
        _Program,
        _substitute,
    )

    node = ("bogus", 0)
    assert _pending_call(node, (), _Program(), "p") is None
    assert _substitute(node, ("lit", 1), 2) is node


def test_malformed_declaration_probe_restores_parser_position():
    from esolangs.interpreters.other.packlang import _Parser

    parser = _Parser(["Integer", "(", ")"])
    assert not parser.is_declaration()
    assert parser.pos == 0


@pytest.mark.parametrize("seed", range(16))
def test_dependency_visibility_matches_graph_reachability(seed):
    from esolangs.interpreters.other.packlang import _Function, _Program, _visible

    rng = random.Random(71377 + seed)
    names = ("a", "b", "c", "d")
    program = _Program()
    program.dependencies = {
        name: frozenset(other for other in names if rng.randrange(2)) for name in names
    }
    for caller in names:
        reachable = {caller}
        for _ in names:
            reachable |= {
                dependency
                for package in tuple(reachable)
                for dependency in program.dependencies[package]
            }
        for target in (*names, "missing"):
            function = _Function("f", (), (), target, {})
            assert _visible(function, caller, program) == (target in reachable)
