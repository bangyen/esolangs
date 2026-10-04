"""Independent tile budgets, mutable numeric cells and executed Dig programs."""

# ruff: noqa: SLF001 -- Seed and compare complete language states.
import itertools

import pytest

from esolangs.interpreters.grid_based import dig as native
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.tools.dig import dig
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.dig_observer import Factory, check, compare, step
from tests.interpreters.dig_reference import Reference


@pytest.mark.parametrize("char", list("^>'<#$@%=~:+-*/;09Az.,!? &"))
def test_local_cell_rules_and_operand_priority(char):
    patterns = [(None,) * 4]
    for direction, digit in itertools.product(range(4), range(10)):
        values = [None] * 4
        values[direction] = str(digit)
        patterns.append(tuple(values))
    patterns.extend(itertools.permutations("0123"))
    for heading, depth, value, pattern in itertools.product(
        range(4), (0, 1, 9), (-10, 0, 1, 9, 10, 65, 128), patterns
    ):
        code = [list("   ") for _ in range(3)]
        code[1][1] = char
        for (row, col), digit in zip(
            ((0, 1), (1, 2), (2, 1), (1, 0)), pattern, strict=True
        ):
            if digit is not None:
                code[row][col] = digit
        if all(not "".join(row).strip() for row in code):
            code[0][0] = "&"
        code = ["".join(row) for row in code]
        ref = Reference(code, "12 A")
        ref.point, ref.heading, ref.depth, ref.value = (
            1 - 1j,
            ref.headings[heading],
            depth,
            value,
        )
        io = ScriptedIO("12 A")
        machine = native._Machine(code, io)
        machine.row = machine.col = 1
        machine.move, machine.num, machine.mole = heading, depth, value
        compare(machine, ref, io)
        step(machine, ref, io)


@pytest.mark.parametrize("value", [-123, -2, -1, 0, 1, 2, 10, 65, 10**100])
def test_stored_integers_are_full_adjacent_operands(value):
    for char, direction, depth in itertools.product("$#%+-*/", range(4), (0, 1, 9)):
        code = ["   ", " " + char + " ", "   "]
        ref = Reference(code)
        ref.point, ref.depth, ref.value = 1 - 1j, depth, 7
        row, col = ((0, 1), (1, 2), (2, 1), (1, 0))[direction]
        ref.rows[row][col] = value
        io = ScriptedIO()
        machine = native._Machine(code, io)
        cells = [list(row) for row in machine.code]
        cells[row][col] = value
        machine.code = tuple(tuple(row) for row in cells)
        machine.row = machine.col = 1
        machine.num, machine.mole = depth, 7
        compare(machine, ref, io)
        step(machine, ref, io)


@pytest.mark.parametrize("value", [-123, -1, 0, 1, 10, 65, 10**100])
def test_store_keeps_geometry_and_survives_revisit(value):
    code = [">$~;:@", " 3"]
    io = ScriptedIO(str(value))
    machine = native._Machine(code, io)
    ref = Reference(code, str(value))
    for _ in range(4):
        step(machine, ref, io)
    assert machine.code[0][3] == value
    assert machine.code[0][4] == ":"
    machine.col, machine.num, machine.mole = 3, 1, 0
    ref.point, ref.depth, ref.value = 3 + 0j, 1, 0
    step(machine, ref, io)
    assert machine.mole == value


@pytest.mark.parametrize("stdin", ["", "A", "\0", "\n", "λ", "😀"])
def test_character_input_and_exhaustion(stdin):
    check([">$=:@", " 2"], stdin, native._Machine)


@pytest.mark.parametrize(
    "stdin", ["", " \t", "7", "-123", "+12", "1_2", " 12 A", "invalid", "_1"]
)
def test_integer_input_consumption_and_failures(stdin):
    check([">$~:@", " 2"], stdin, native._Machine)


def test_unbounded_integer_read_and_negative_print():
    check([">$~:@", " 2"], "0" * 5000 + "1", native._Machine, "1")
    value = "-" + "1" * 5000
    check([">$~:@", " 2"], value, native._Machine, value)


def test_cursorless_input_cannot_fake_a_cat_cycle():
    class Cursorless(IO):
        def __init__(self):
            super().__init__()
            self.characters = iter("A" * 20 + "B")
            self.output = ""

        def _read_char(self, _prompt):
            try:
                return next(self.characters)
            except StopIteration:
                raise EOFError from None

        def _write(self, value):
            self.output += str(value)

    io = Cursorless()
    machine = native._Machine([">$=:'", "^2  <"], io)
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(machine, limit=1000)
    assert io.output == "A" * 20 + "B"


@pytest.mark.parametrize(
    ("code", "start", "period"), [([">'", "^<"], 1, 4), ([">$;'", "^1 <"], 3, 8)]
)
def test_exact_cycles_and_halt_noop(code, start, period):
    result = Factory(code, native._Machine).check("")
    assert result["cycle_start"] == start
    assert result["generations"] == start + period
    machine = native._Machine(["@"], ScriptedIO())
    machine.step()
    state = machine.snapshot()
    machine.step()
    assert machine.halted
    assert machine.snapshot() == state


def test_published_hello_and_nand():
    hello = [">$H:e:l:l:$o:%:W:o:$r:l:d:!:@", " 8        8  0     8"]
    check(hello, "", native._Machine, "Hello World!")
    nand = ["'2  > $~ >$ 1:@", ">$~;#@2   3", "    > $~;#@2", "         > $0:@"]
    for bits in map("".join, itertools.product("01", repeat=2)):
        check(nand, " ".join(bits), native._Machine, str(int(bits != "11")))


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "shard"), [(1, 0), (2, 0), *((3, shard) for shard in range(4))]
)
@pytest.mark.parametrize("width", [None, 1, 13, 100])
def test_all_small_generated_tables(n, shard, width):
    stride = 4 if n == 3 else 1
    for value in range(shard, 1 << (1 << n), stride):
        table = format(value, f"0{1 << n}b")
        factory = Factory(dig(table, width).splitlines(), native._Machine)
        for row, answer in enumerate(table):
            result = factory.check(" ".join(format(row, f"0{n}b")), answer)
            assert result["halted"]
            assert result["reads"] == n


@pytest.mark.medium
@pytest.mark.parametrize("variant", ["flat", "banded", "rotated"])
@pytest.mark.parametrize("shard", range(4))
def test_direct_generated_layouts(variant, shard):
    from esolangs.tools.dig import _dig_grid, _dig_quarter_turn

    for n in (1, 2, 3):
        if n < 3 and shard:
            continue
        stride = 4 if n == 3 else 1
        for value in range(shard, 1 << (1 << n), stride):
            table = format(value, f"0{1 << n}b")
            split = -(-(n + 2) // 2) if variant == "banded" else None
            program = _dig_grid(table, n, split)
            if variant == "rotated":
                program = _dig_quarter_turn(program)
            factory = Factory(program.splitlines(), native._Machine)
            for row, answer in enumerate(table):
                result = factory.check(" ".join(format(row, f"0{n}b")), answer)
                assert result["halted"]
                assert result["reads"] == n


@pytest.mark.medium
@pytest.mark.parametrize("n", [5, 6])
def test_wide_alternating_layouts(n):
    from esolangs.tools.dig import _dig_alternating

    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(i.bit_count() % 2) for i in range(1 << n)),
    ]
    for table in tables:
        factory = Factory(_dig_alternating(table, n).splitlines(), native._Machine)
        for row, answer in enumerate(table):
            result = factory.check(" ".join(format(row, f"0{n}b")), answer)
            assert result["halted"]
            assert result["reads"] == n
