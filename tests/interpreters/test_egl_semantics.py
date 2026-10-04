"""Independent EGL contracts and generated execution."""

# ruff: noqa: SLF001, PT011 -- Compare private state and error types independently.

import pytest

from esolangs.interpreters.grid_based import egl as native
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.tools.egl import egl
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.egl_observer import Factory, check, compare, step
from tests.interpreters.egl_reference import Reference, display


@pytest.mark.parametrize("shape", [(1, 1), (2, 3), (3, 2)])
def test_every_command_at_every_position(shape):
    width, height = shape
    for y in range(height):
        for x in range(width):
            for value in [-10, 0, 1, 65, 128]:
                for op in "><^v_|%+-x=#?\n":
                    source = f"{width},{height}:" + op
                    ref = Reference(source, "λ\n")
                    io = ScriptedIO("λ\n")
                    m = native._Machine(source, io)
                    ref.cells = {p: value + index for index, p in enumerate(ref.cells)}
                    ref.point = x, y
                    m.state = (0, y, x, ref.values, ())
                    compare(m, ref, io)
                    step(m, ref, io)


@pytest.mark.parametrize(
    ("source", "answer"),
    [
        ("10,10:v>>_++=", "2"),
        ("10,1:++(>+++++<-)>=", "10"),
        ("2,2:+>++v+++#", "|1|2|\n|0|3|\n"),
        ("2,1:+(->)=", "0"),
        ("2,1:+(->+)=", "1"),
        ("2,1:++(>+<-)>=", "2"),
        ("1,1:(x)", ""),
        ("2,1:+(-(+(-)))=", "0"),
    ],
)
def test_published_examples_and_loop_anchors(source, answer):
    check(source, "", native._Machine, answer)


@pytest.mark.parametrize("stdin", ["", "\0", "\n", "λ", "😀"])
def test_input_and_eof(stdin):
    check("1,1:x=", stdin, native._Machine)


@pytest.mark.parametrize(
    "source", ["", "0,1:", "1,0:", "-1,2:", "1,1:(", "1,1:)", "1,1:)( "]
)
def test_malformed_source(source):
    with pytest.raises(ValueError):
        Reference(source)
    with pytest.raises(ValueError):
        native._Machine(source, ScriptedIO())


def test_cursorless_reads_do_not_fake_a_cycle():
    class Cursorless(IO):
        def __init__(self):
            super().__init__()
            self.source = iter("\1" * 10 + "\0")
            self.count = 0

        def input_char(self, prompt=""):
            del prompt
            self.count += 1
            return ord(next(self.source))

    io = Cursorless()
    machine = native._Machine("1,1:+(x)", io)
    assert run_until_halt_or_cycle(machine, 100)
    assert io.count == 11
    assert (
        run_until_halt_or_cycle(native._Machine("1,1:+()", ScriptedIO()), 100) is False
    )


def test_unbounded_dimensions_and_decimal_output():
    check("0" * 5000 + "1,1:+=", "", native._Machine, "1")
    for value in [10**5000, -(10**5000)]:
        for op in ["=", "#"]:
            ref = Reference("1,1:" + op)
            io = ScriptedIO()
            m = native._Machine("1,1:" + op, io)
            ref.cells[0, 0] = value
            m.state = (0, 0, 0, (value,), ())
            compare(m, ref, io)
            step(m, ref, io)
            assert io.getvalue() == (
                display(value) if op == "=" else "|" + display(value) + "|\n"
            )


@pytest.mark.medium
@pytest.mark.parametrize(("n", "shard"), [(1, 0), (2, 0), *((3, i) for i in range(8))])
@pytest.mark.parametrize("width", [None, 1, 5, 20, 80])
def test_all_small_generated_tables(n, shard, width):
    stride = 8 if n == 3 else 1
    for value in range(shard, 1 << (1 << n), stride):
        table = format(value, f"0{1 << n}b")
        factory = Factory(egl(table, width), native._Machine)
        for row, answer in enumerate(table):
            result = factory.check(format(row, f"0{n}b"), answer)
            assert result["halted"]
            assert result["reads"] == n
