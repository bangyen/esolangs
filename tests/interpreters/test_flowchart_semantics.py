"""Independent Flowchart transitions and generated execution."""

import itertools
from collections import deque

import pytest

from esolangs.interpreters.grid_based.flowchart import _Machine, _Pointer
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.flowchart import flowchart
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.flowchart_observer import Factory, check, compare, step
from tests.interpreters.flowchart_reference import (
    SPELLINGS,
    Pointer,
    Reference,
    coordinate,
)
from tests.interpreters.test_flowchart import CAT, KOLAKOSKI, TRUTH_MACHINE


@pytest.mark.parametrize("node", SPELLINGS)
def test_node_rules_from_every_incident_rail(node):
    for value, tape, contents, heading in itertools.product(
        [None, 0, 1], [-3, 0, 2], [(), (0,), (1,), (0, 1), (1, 0, 1)], [1, -1j, -1, 1j]
    ):
        center = 4 + len(node) // 2
        lines = [" " * center + "│", "( )─" + node + "─(( ))", " " * center + "│"]
        ref = Reference(lines, " \n1")
        io = ScriptedIO(" \n1")
        machine = _Machine(lines, io)
        point = (4 if heading == 1 else 3 + len(node) if heading == -1 else center) - 1j
        ref.pointers = [Pointer(point, heading, value, tape, previous=point - heading)]
        ref.tapes = {tape: deque(contents)}
        machine.pointers = [
            _Pointer(
                *coordinate(point),
                coordinate(heading),
                value,
                tape,
                prev=coordinate(point - heading),
            )
        ]
        machine.deques.update({tape: list(contents)})
        compare(machine, ref, io)
        assert step(machine, ref, io) is None


@pytest.mark.parametrize(
    "text", ["", "0", "1", "101", "1101", "000", "111", " \n1\t0 1"]
)
def test_published_cat(text):
    check(CAT, text, _Machine, "".join(c for c in text if c in "01"))


def test_published_truth_machine_and_exact_cycle():
    assert check(TRUTH_MACHINE, "0", _Machine, "0")["halted"]
    result = check(TRUTH_MACHINE, "1", _Machine)
    assert not result["halted"]
    assert result["cycle_start"] == 20


def test_published_parallel_diagram_rounds():
    io = ScriptedIO()
    machine = _Machine(KOLAKOSKI, io)
    ref = Reference(KOLAKOSKI)
    for _ in range(400):
        assert step(machine, ref, io) is None
    # Compare the diagram's declared profile, not its advertised sequence.
    assert not machine.halted


@pytest.mark.parametrize("text", ["", " \n", "0", "1", "A", "λ"])
def test_character_reads_and_eof(text):
    check(["( )─/ /─\\ \\─(( ))"], text, _Machine)


def test_cursorless_input_cannot_fake_a_cycle():
    class Cursorless(ScriptedIO):
        def position(self):
            return 0

    lines = [
        "( )──┐",
        "  ┌─/ /─┐",
        "  │  │  │",
        "  │ ( ) │",
        "  │  │  │",
        "  └─< >─┘",
        "     │",
        "   (( ))",
    ]
    io = Cursorless("1" * 21)
    machine = _Machine(lines, io)
    assert run_until_halt_or_cycle(machine, 10000)
    assert io.reads == 21
    assert io.past_end == 1
    assert (
        run_until_halt_or_cycle(_Machine(TRUTH_MACHINE, ScriptedIO("1")), 1000) is False
    )


@pytest.mark.medium
@pytest.mark.parametrize(("n", "shard"), [(1, 0), (2, 0), *((3, i) for i in range(8))])
@pytest.mark.parametrize("width", [None, 1, 13, 100])
def test_all_small_generated_tables(n, shard, width):
    stride = 8 if n == 3 else 1
    for value in range(shard, 1 << (1 << n), stride):
        table = format(value, f"0{1 << n}b")
        factory = Factory(flowchart(table, width).splitlines(), _Machine)
        for row, answer in enumerate(table):
            result = factory.check(format(row, f"0{n}b"), answer)
            assert result["halted"]
            assert result["reads"] == n


@pytest.mark.parametrize("builder", ["flat", "stacked", "deque"])
def test_private_drawing_paths(builder):
    from esolangs.tools.flowchart import (
        _flowchart_cells,
        _flowchart_deque,
        _flowchart_render,
        _flowchart_stacked,
    )

    for n in range(1, 5):
        length = 1 << n
        tables = (
            [format(value, f"0{length}b") for value in range(1 << length)]
            if n < 3
            else [
                "0" * length,
                "1" * length,
                "".join(str(row.bit_count() % 2) for row in range(length)),
                "1" + "0" * (length - 1),
                "0" + "1" * (length - 1),
                "0011" * (length // 4),
            ]
        )
        for table in dict.fromkeys(tables):
            program = (
                _flowchart_deque(table)
                if builder == "deque"
                else _flowchart_render(
                    (_flowchart_cells if builder == "flat" else _flowchart_stacked)(
                        table
                    )
                )
            )
            factory = Factory(program.splitlines(), _Machine)
            for row, answer in enumerate(table):
                result = factory.check(format(row, f"0{n}b"), answer)
                assert result["halted"]
                assert result["reads"] == n


@pytest.mark.parametrize(
    ("lines", "reference_message", "native_message"),
    [
        ([], "start", "start node"),
        (["(( ))"], "start", "start node"),
        (["( )─?─(( ))"], "unknown glyph", "unknown character"),
        (["( )[ }"], "touching nodes", "nodes touch without a path"),
        ([" ( )", " [ }"], "touching nodes", "nodes touch without a path"),
        (["( )", "  [ }"], "touching nodes", "nodes touch without a path"),
        ([" ( )", " │  ", "(( ))"], "vertical alignment", "vertical path"),
        (["( )"], "exit", "start node has no exit path"),
    ],
)
def test_independent_parser_rejections(lines, reference_message, native_message):
    with pytest.raises(ValueError, match=reference_message):
        Reference(lines)
    with pytest.raises(ValueError, match=native_message):
        _Machine(lines, ScriptedIO())


@pytest.mark.parametrize(
    "lines",
    [
        ["( )─[ }─\\ \\─(( ))"],
        [" ( )", "  │", " [ }", "  │", " \\ \\", "  │", "(( ))"],
        [
            "( )─[ }─[ }─( )─\\ \\─(( ))",
            "             │",
            "            \\ \\",
            "             │",
            "           (( ))",
        ],
    ],
)
def test_node_entries_and_register_fork(lines):
    result = check(lines, "", _Machine)
    assert result["halted"]


@pytest.mark.medium
@pytest.mark.parametrize(
    "table",
    [
        "0110100110010110",
        "1000000000000000",
        "0011" * 8,
        "".join(str((row.bit_count() ^ (row >> 2)) & 1) for row in range(64)),
    ],
)
@pytest.mark.parametrize("width", [None, 1, 12, 20, 100])
@pytest.mark.parametrize("shard", range(8))
def test_retired_generator_examples_independently(table, width, shard):
    n = len(table).bit_length() - 1
    factory = Factory(flowchart(table, width).splitlines(), _Machine)
    for row in range(shard, len(table), 8):
        result = factory.check(format(row, f"0{n}b"), table[row])
        assert result["halted"]
        assert result["reads"] == n
