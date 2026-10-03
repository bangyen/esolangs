"""Line rasters checked against an independent segment graph."""

import itertools
from pathlib import Path

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.line import _Machine
from esolangs.raster import Raster
from esolangs.tools.line import _render_node, line_boolean
from esolangs.tools.line.render import chain
from tests.line.reference_pixels import evaluate, program


def prepare(data):
    paths, start = program(data)
    return Raster.from_png(data), paths, start


def check(source, paths, start, values, expected=None):
    output, cells, reads = evaluate(paths, start, values)
    if expected is not None:
        assert output == [expected]
    assert reads == len(values)
    io = ScriptedIO(" \t".join(str(value) for value in values))
    machine = _Machine(source, io)
    for _ in range(10000):
        if machine.halted:
            break
        machine.step()
    else:
        raise AssertionError("raster execution did not halt within cap")
    assert io.getvalue() == "".join(str(value) for value in output)
    assert {cell: value for cell, value in machine.state[3] if value} == {
        cell: value for cell, value in cells.items() if value
    }
    state = machine.snapshot()
    machine.step()
    assert machine.snapshot() == state


@pytest.mark.medium
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("table", [format(i, "04b") for i in range(16)])
def test_all_two_input_pngs(table, reverse):
    data = Raster(_render_node(line_boolean(table, reverse=reverse))).to_png()
    source, paths, start = prepare(data)
    for row, expected in enumerate(table):
        check(source, paths, start, [row // 2, row % 2], int(expected))


@pytest.mark.medium
@pytest.mark.parametrize("heading", [(-1, 0), (0, 1), (1, 0), (0, -1)])
@pytest.mark.parametrize("scale", [1, 2, 3, 4])
def test_rotated_scaled_identity_and_complement(heading, scale):
    for table in ("00", "01", "10", "11"):
        data = (
            Raster(_render_node(line_boolean(table), heading)).upscaled(scale).to_png()
        )
        source, paths, start = prepare(data)
        for row, expected in enumerate(table):
            check(source, paths, start, [row], int(expected))


@pytest.mark.slow
@pytest.mark.parametrize("reverse", [False, True])
def test_every_three_input_table_through_segment_graph(reverse):
    for encoded in range(256):
        table = format(encoded, "08b")
        data = Raster(_render_node(line_boolean(table, reverse=reverse))).to_png()
        source, paths, start = prepare(data)
        for row, expected in enumerate(table):
            check(
                source,
                paths,
                start,
                [int(bit) for bit in format(row, "03b")],
                int(expected),
            )


@pytest.mark.medium
@pytest.mark.parametrize("ops", ["+++", ">++<+", "<---o", "i>i<o>o", "i-o", "i+o"])
def test_straight_counted_arithmetic_and_numeric_io(ops):
    from esolangs.tools.line.render import render

    canvas = render(chain(*ops))
    data = Raster(
        tuple(tuple((v, v, v) for v in row) for row in canvas.pixels)
    ).to_png()
    source, paths, start = prepare(data)
    values = [-257, 10**40][: ops.count("i")]
    check(source, paths, start, values)


@pytest.mark.slow
@pytest.mark.parametrize(
    "fixture",
    [
        "addition.png",
        "addition_2x.png",
        "addition_3x.png",
        "multiplication.png",
        "multiplication_2x.png",
    ],
)
def test_published_arithmetic_loops_and_reconnections(fixture):
    data = (Path(__file__).parents[1] / "fixtures" / "line" / fixture).read_bytes()
    source, paths, start = prepare(data)
    operation = (
        (lambda a, b: a + b) if fixture.startswith("addition") else (lambda a, b: a * b)
    )
    for a, b in itertools.product(range(13), repeat=2):
        check(source, paths, start, [a, b], operation(a, b))


@pytest.mark.slow
@pytest.mark.parametrize("n", range(6))
def test_brainfuck_translation_straight_transfer_and_nested_loops(n):
    from esolangs.tools.line.bf_to_line import bf_to_line
    from esolangs.tools.line.render import render

    cases = [
        ("+" * n + ".", [], n),
        ("+>" + "+" * n + ".", [], n),
        (",.", [10**40], 10**40),
        ("+" * n + "[-].", [], 0),
        ("+" * n + "[>+<-]>.", [], n),
    ]
    for multiplier in (1, 2, 4):
        cases.extend(
            [
                ("+" * n + "[>" + "+" * multiplier + "<-]>.", [], n * multiplier),
                (
                    "+" * n + "[>" + "+" * multiplier + "[>+<-]<-]>>.",
                    [],
                    n * multiplier,
                ),
            ]
        )
    for source, values, expected in cases:
        canvas = render(bf_to_line(source))
        data = Raster(
            tuple(tuple((v, v, v) for v in row) for row in canvas.pixels)
        ).to_png()
        source, paths, start = prepare(data)
        check(source, paths, start, values, expected)
