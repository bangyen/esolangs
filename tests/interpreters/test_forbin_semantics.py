"""Independent Forbin parsing, transitions, complete snapshots and I/O."""

import itertools

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import _Frame, _Machine
from esolangs.tools.forbin import forbin
from esolangs.vm import run_until_halt_or_ancestor
from tests.interpreters.forbin_cases import finite_cases, global_cases
from tests.interpreters.forbin_observer import check


@pytest.mark.parametrize(
    "family",
    [
        "parallel_assignment",
        "anonymous_parameters",
        "wildcard_short",
        "wildcard_group",
        "inclusive_range",
        "msb_byte_reads",
        "bare_literal_call",
    ],
)
def test_primary_rule_corpus(family):
    cases = finite_cases()
    for case in cases:
        if case["family"] == family:
            result = check(
                case["source"],
                case["input"],
                _Machine,
                "".join(map(chr, case["expected_bytes"])),
            )
            assert result["halted"]


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "shard"), [(1, 0), (2, 0), *((3, index) for index in range(8))]
)
@pytest.mark.parametrize("width", [None, 1, 13, 100])
def test_all_generated_tables(n, shard, width):
    for value in range(shard, 1 << (1 << n), 8 if n == 3 else 1):
        table = format(value, f"0{1 << n}b")
        source = forbin(table, width)
        for row, answer in enumerate(table):
            result = check(source, format(row, f"0{n}b"), _Machine, answer)
            assert result["halted"]
            assert result["reads"] == n
            assert result["bit_reads"] == 8 * n


@pytest.mark.parametrize(
    ("code", "stdin"),
    [
        ("main{x=(in 0);for _:1..x{main 0;}}", chr(254)),
        ("main{x=0;loop 0;}loop{x=!x;for _:1..x{loop 0;}}", ""),
        ("main{f={g={};g 0;};f 0;}", ""),
        ("main{{{} 0;} 0;}", ""),
    ],
)
def test_finite_calls_are_not_ancestor_cycles(code, stdin):
    assert check(code, stdin, _Machine)["halted"]
    assert run_until_halt_or_ancestor(_Machine(code, ScriptedIO(stdin)), 500)


def test_actual_recursive_cycle_is_detected():
    assert (
        run_until_halt_or_ancestor(
            _Machine("main{loop 0;}loop{loop 0;}", ScriptedIO()), 500
        )
        is False
    )


def test_pending_rows_are_in_the_snapshot():
    source = "main{for i:((in 0),(in 0)){out 0,0,0,0,0,0,0,i;}}"
    first = _Machine(source, ScriptedIO(chr(0)))
    second = _Machine(source, ScriptedIO(chr(64)))
    second.globals = first.globals
    second.global_frame = first.global_frame
    second.state.frames = [_Frame(first.globals["main"], first.global_frame)]
    first.step()
    second.step()
    assert first.snapshot() != second.snapshot()
    assert check(source, chr(0), _Machine, "\0\0")["halted"]
    assert check(source, chr(64), _Machine, "\0\1")["halted"]


@pytest.mark.parametrize(
    ("code", "stdin"),
    [
        ("main{x=(in 0);}", ""),
        ("main{out 0;}", ""),
        ("main{x=!out;}", ""),
        ("main{missing 0;}", ""),
        ("main{x=0;x 0;}", ""),
        ("main{for i:out..1{}}", ""),
    ],
)
def test_errors_match_independent_execution(code, stdin):
    assert "error" in check(code, stdin, _Machine)


def test_global_initializers_and_visibility():
    cases = global_cases()
    for case in cases:
        stdin = chr(case["input_byte"]) if "input_byte" in case else ""
        result = check(case["code"], stdin, _Machine, chr(case["expected_byte"]))
        assert result["halted"]


@pytest.mark.parametrize(
    ("source", "stdin"),
    [
        ("g{out 0,0,0,0,0,0,0,1;return 0;}main{(g 0);}", ""),
        ("main{(in 0);}", chr(0)),
        ("g{out 0,0,0,0,0,0,0,1;return 0;}main{for _:0..0{(g 0);}}", ""),
    ],
)
def test_call_target_is_evaluated_once(source, stdin):
    assert check(source, stdin, _Machine)["error"] == "invalid"


def test_definitions_in_loops_belong_to_the_enclosing_function():
    for bit, depth, bounds in itertools.product(
        [0, 1], range(1, 6), ["0..0", "0..1", "1..0"]
    ):
        body = "f{return " + str(bit) + ";}"
        for _ in range(depth):
            body = "for _:" + bounds + "{" + body + "}"
        source = "main{" + body + "out 0,0,0,0,0,0,0,(f 0);}"
        assert check(source, "", _Machine, chr(bit))["halted"]
