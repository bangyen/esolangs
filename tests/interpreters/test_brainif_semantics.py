"""Independent mutable BrainIf model; wiki 164276 plus documented dialect."""

import itertools
import random
import re
import unicodedata

import pytest

import esolangs
from esolangs.exceptions import InputExhaustedError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.persistent import chunked
from esolangs.interpreters.tape_based.brainif import _Machine, run
from tests.interpreters.views import view as vm_view


def number(token):
    if re.fullmatch(r"[+-]?\d(?:_?\d)*", token) is None:
        raise ValueError(f"invalid literal for int() with base 10: {token!r}")
    negative = token.startswith("-")
    token = token.lstrip("+-").replace("_", "")
    value = 0
    for char in token:
        value = 10 * value + unicodedata.decimal(char)
    return -value if negative else value


def parse(source):
    if not source.strip():
        return None
    match = re.fullmatch(r"\s*if\s+(\S+)(?:\s+(.*?))?\s*", source, re.DOTALL)
    if match is None:
        raise ValueError("malformed BrainIf line: " + source.strip())
    value = number(match[1])
    operation = (match[2] or "").split()
    if operation[:1] == ["move"]:
        if len(operation) == 2 and operation[1] in ("left", "right"):
            return value, operation[1], None
    elif operation[:1] == ["goto"]:
        if len(operation) == 1:
            raise ValueError("goto requires a target line")
        if len(operation) == 2:
            target = number(operation[1])
            if target < 1:
                raise ValueError("goto target must be a positive line number")
            return value, "goto", target
    elif len(operation) <= 1:
        command = operation[0] if operation else ""
        if command not in ("inc", "increment", "left", "right", "input", "output"):
            raise ValueError(f"unknown BrainIf command {command!r}")
        return value, command, None
    raise ValueError("malformed BrainIf line: " + source.strip())


class Reference:
    def __init__(self, code, stdin="", cells=(0,), ptr=0, ip=0):
        self.code = list(code)
        self.cells = list(cells)
        self.ptr, self.ip = ptr, ip
        self.stdin = stdin
        self.cursor = self.past_end = 0
        self.output = ""

    @property
    def halted(self):
        return self.ip >= len(self.code)

    def state(self):
        return tuple(self.cells), self.ip, self.ptr, self.cursor

    def result(self):
        return self.state(), self.halted, self.output, self.past_end

    def step(self):
        if self.halted:
            return
        instruction = parse(self.code[self.ip])
        following = self.ip + 1
        if instruction is not None:
            guard, command, target = instruction
            if self.cells[self.ptr] == guard:
                if command in ("inc", "increment"):
                    self.cells[self.ptr] += 1
                elif command == "right":
                    self.ptr += 1
                    if self.ptr == len(self.cells):
                        self.cells.append(0)
                elif command == "left":
                    if self.ptr:
                        self.ptr -= 1
                elif command == "goto":
                    following = target - 1
                elif command == "input":
                    if self.cursor == len(self.stdin):
                        self.past_end += 1
                        raise InputExhaustedError(
                            self.cursor, len(self.stdin), "character"
                        )
                    self.cells[self.ptr] = ord(self.stdin[self.cursor])
                    self.cursor += 1
                elif command == "output":
                    self.output += chr(self.cells[self.ptr])
        self.ip = following


def normalized(snapshot):
    cells, ip, ptr, cursor = snapshot
    return tuple(value for block in cells for value in block), ip, ptr, cursor


def inspect(machine):
    assert vm_view(machine, "ip") == machine.ind == machine.state[0]
    assert machine.ptr == machine.state[1]
    assert vm_view(machine, "memory") == list(machine.cells)
    assert machine.tape == machine.cells
    assert vm_view(machine, "stack") == []
    assert machine.input_position() == machine.io.position()
    assert normalized(machine.snapshot()) == (
        machine.cells,
        machine.ind,
        machine.ptr,
        machine.io.position(),
    )
    return (
        normalized(machine.snapshot()),
        machine.halted,
        machine.io.getvalue(),
        machine.io.past_end,
    )


def compare(code, stdin, cap, cells=(0,), ptr=0, ip=0):
    expected = Reference(code, stdin, cells, ptr, ip)
    actual = _Machine(list(code), ScriptedIO(stdin))
    assert (actual.cells, actual.ind, actual.ptr) == ((0,), 0, 0)
    actual.state = ip, ptr, chunked(cells)
    assert inspect(actual) == expected.result()
    states = {expected.state()}
    error = None
    for _ in range(cap):
        before = actual.snapshot()
        saved_hash = hash(before)
        detail = None
        try:
            expected.step()
        except (ValueError, InputExhaustedError) as caught:
            error = type(caught)
            with pytest.raises(error) as reported:
                actual.step()
            detail = str(reported.value), str(caught)
        else:
            actual.step()
        if detail is not None:
            assert detail[0] == detail[1]
        assert inspect(actual) == expected.result(), (code, stdin, cap, cells, ptr, ip)
        assert hash(before) == saved_hash
        if error:
            return expected, "error", error
        if expected.halted:
            terminal = inspect(actual)
            actual.step()
            actual.step()
            assert inspect(actual) == terminal
            return expected, "halt", None
        if expected.state() in states:
            return expected, "cycle", None
        states.add(expected.state())
    return expected, "bounded", None


def corpus():
    lines = (
        "",
        "if 0 inc",
        "if 1 increment",
        "if 0 right",
        "if 1 left",
        "if 0 move left",
        "if 0 input",
        "if 0 output",
        "if 1 output",
        "if 0 goto 1",
        "if 0 goto 2",
        "if 0 goto 4",
        "if 1 goto 1",
        "if 0",
        "if 0 frobnicate",
    )
    for size in range(4):
        for code in itertools.product(lines, repeat=size):
            for stdin in ("", "\x00A\n\u0101"):
                yield list(code), stdin
    values = ("0", "1", "-1", "+0", "1_0", "\u0660", "x", "0x1", "1__0")
    commands = (
        "",
        "inc",
        "increment",
        "right",
        "left",
        "input",
        "output",
        "move right",
        "move left",
        "move up",
        "move right junk",
        "goto",
        "goto 1",
        "goto 3",
        "goto 0",
        "goto -1",
        "goto x",
        "goto 1 junk",
        "frobnicate",
        "incidental",
        "incrementoutput",
        "XinputY",
        "moveright",
        "output junk",
        "frobnicate output",
    )
    for value, command, space in itertools.product(values, commands, (" ", "\t")):
        yield [space.join(("if", value, command)), "if 0 output"], "\nA\u0101"
    for line in (
        "if",
        "if ",
        "garbage 0 output",
        "IF 0 input",
        "\x00",
        "  ",
        "\n",
        "if\n0\ninc",
    ):
        yield [line, "if 1 output"], ""
    for stdin in ("", "A", "\n", "\x00\x00", "\u0101", "AB"):
        yield ["if 0 input", "if 1 input", "if 0 goto 1"], stdin
    yield ["if 0 goto 3", "garbage", "if 0 output"], ""
    yield (
        ["if 0 right"] * 65
        + ["if 0 increment", "if 1 left", "if 0 inc", "if 1 right", "if 1 output"],
        "",
    )
    yield [f"if {n} increment" for n in range(300)] + ["if 300 output"], ""
    yield (
        ["if 0 right"] * 3
        + [
            "if 0 inc",
            "if 1 left",
            "if 0 inc",
            "if 1 left",
            "if 0 inc",
            "if 1 left",
            "if 0 output",
            "if 0 right",
            "if 1 output",
        ],
        "",
    )
    yield ["if 0 input", "if 257 output"], "\u0101"
    yield ["if 0 input", "if 10 output"], "\n"
    rng = random.Random(1741)
    for _ in range(64):
        code = [
            f"if {rng.choice((-1, 0, 1, 2, 10, 65, 255, 256))} {rng.choice(commands)}"
            for _ in range(12)
        ]
        yield code, "0\n1\u0101AB\x00"


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_bounded_mutable_tape_and_line_effects(cap):
    for code, stdin in corpus():
        compare(code, stdin, cap)


@pytest.mark.medium
def test_seeded_tape_chunk_boundaries_and_live_guards():
    for size in (1, 2, 3, 31, 32, 33, 63, 64, 65):
        cells = [index * 257 for index in range(size)]
        for ptr in {0, size // 2, size - 1}:
            value = cells[ptr]
            for command in ("inc", "increment", "left", "right", "input", "output"):
                for guard in (value, value + 1):
                    compare(
                        [f"if {guard} {command}", "if 0 right"],
                        "\u0101\n",
                        7,
                        cells,
                        ptr,
                    )
    compare(["if 0 increment", "if 1 increment", "if 2 output"], "", 7)


def forward_only(code):
    for index, line in enumerate(code):
        try:
            instruction = parse(line)
        except ValueError:
            continue
        if (
            instruction is not None
            and instruction[1] == "goto"
            and instruction[2] <= index + 1
        ):
            return False
    return True


@pytest.mark.medium
def test_public_acyclic_runner_matches_reference():
    for code, stdin in corpus():
        if not forward_only(code):
            continue
        expected, verdict, error = compare(code, stdin, 400)
        assert verdict in ("halt", "error")
        io = ScriptedIO(stdin)
        if error:
            with pytest.raises(error):
                run(code, io)
        else:
            run(code, io)
        assert (io.getvalue(), io.position(), io.past_end) == (
            expected.output,
            expected.cursor,
            expected.past_end,
        )


def test_public_backward_cache_and_long_climbs():
    codes = (
        ["if 1 increment", "if 0 increment", "if 1 goto 1", "if 2 output"],
        [f"if {n} increment" for n in range(72)]
        + ["if 72 output"]
        + [f"if {n} increment" for n in range(72, 105)]
        + ["if 105 output"],
        ["if 0 input", "if 48 output", "if 48 goto 6", "if 49 output", "if 49 goto 2"],
        ["if 0 inc", "", " ", "if 1 output"],
        [
            "if 0 inc",
            "if 1 right",
            "if 0 inc",
            "if 1 inc",
            "if 2 left",
            "if 1 inc",
            "if 2 right",
            "if 2 output",
        ],
        ["if 0 right"] * 3
        + [
            "if 0 inc",
            "if 1 left",
            "if 0 inc",
            "if 1 left",
            "if 0 inc",
            "if 1 left",
            "if 0 output",
            "if 0 right",
            "if 1 output",
        ],
    )
    for code in codes:
        expected, verdict, error = compare(code, "0", 1000)
        assert verdict == "halt"
        assert error is None
        io = ScriptedIO("0")
        run(code, io)
        assert (io.getvalue(), io.position(), io.past_end) == (
            expected.output,
            expected.cursor,
            0,
        )
        assert (
            esolangs.run("BrainIf", "\n".join(code), "0", max_steps=1000)
            == expected.output
        )


def test_exact_cycles_preserve_input_position_and_growth_is_undecided():
    from esolangs.vm import run_until_halt_or_cycle

    assert run_until_halt_or_cycle(_Machine(["if 0 output"], ScriptedIO()), limit=24)
    for code in (["if 0 goto 1"], ["if 0 output", "if 0 goto 1"]):
        expected, verdict, error = compare(code, "", 24)
        assert verdict == "cycle"
        assert error is None
        assert not expected.halted
        assert not run_until_halt_or_cycle(_Machine(code, ScriptedIO()), limit=24)
    code = ["if 0 input", "if 0 goto 1"]
    expected, verdict, error = compare(code, "\x00\x00A", 24)
    assert verdict == "halt"
    assert error is None
    assert expected.cursor == 3
    machine = _Machine(code, ScriptedIO("\x00\x00A"))
    assert run_until_halt_or_cycle(machine, limit=24)
    assert machine.io.position() == 3
    with pytest.raises(TimeoutError, match="undecided"):
        run_until_halt_or_cycle(
            _Machine(["if 0 right", "if 0 goto 1"], ScriptedIO()), limit=24
        )


def test_integer_operands_beyond_decimal_conversion_cap():
    digits = "9" * 6000
    for token in (digits, "-" + digits):
        expected, verdict, error = compare(["if " + token + " output"], "", 1)
        assert verdict == "halt"
        assert error is None
        assert expected.output == ""
        io = ScriptedIO()
        run(["if " + token + " output"], io)
        assert io.getvalue() == ""
    code = ["if 0 goto " + digits]
    expected, verdict, error = compare(code, "", 1)
    assert verdict == "halt"
    assert error is None
    run(code, ScriptedIO())


def generated_result(table, row, n, width=None, builder=None, program=None, cap=12000):
    if program is None:
        program = (
            esolangs.generate("BrainIf", table, width=width)
            if builder is None
            else builder(table)
        )
    code = program.splitlines()
    stdin = format(row, f"0{n}b")
    expected = Reference(code, stdin)
    actual = _Machine(code, ScriptedIO(stdin))
    for _ in range(cap):
        if expected.halted:
            break
        expected.step()
        actual.step()
    assert expected.halted, (n, row, width)
    assert inspect(actual) == expected.result()
    assert expected.output == table[row]
    assert expected.cursor == n
    assert expected.past_end == 0
    io = ScriptedIO(stdin + "sentinel")
    run(code, io)
    assert (io.getvalue(), io.position(), io.past_end) == (table[row], n, 0)
    assert io.input_str() == "sentinel"
    return "\n".join(code)


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        programs = {
            str(esolangs.generate("BrainIf", table, width=width))
            for width in (None, 1, 11, 12, 13, 40, 80, 1000)
        }
        for program in programs:
            for row in range(1 << n):
                generated_result(table, row, n, program=program)


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6])
@pytest.mark.parametrize("kind", range(6))
def test_larger_generated_dag_tree_and_spatial_routes(n, kind):
    rng = random.Random(1742 + n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        "".join(rng.choice("01") for _ in range(1 << n)),
        "".join(str((row * 73 + row // 3) % 2) for row in range(1 << n)),
        "1" + "0" * ((1 << n) - 1),
    ]
    table = tables[kind]
    programs = {
        str(esolangs.generate("BrainIf", table, width=width))
        for width in (None, 1, 12, 80, 1000)
    }
    for program in programs:
        for row in range(1 << n):
            generated_result(table, row, n, program=program)


@pytest.mark.medium
def test_retained_tree_and_linear_builders():
    from esolangs.tools.brainif import _brainif_linear, _brainif_tree

    for n in (5, 6):
        table = "".join(str(row.bit_count() % 2) for row in range(1 << n))
        assert _brainif_tree(table, 1, prune=False) == _brainif_linear(table)
        assert str(esolangs.generate("BrainIf", table, width=1000)) == _brainif_linear(
            table
        )
    table = "".join(str(row.bit_count() % 2) for row in range(16))
    for builder in (
        _brainif_linear,
        lambda table: _brainif_tree(table, 1, prune=False),
    ):
        for row in range(16):
            generated_result(table, row, 4, builder=builder)
    table = "0110" * 16
    for row in range(64):
        generated_result(table, row, 6, width=1000)


def test_pure_input_default_and_neighbor_preservation():
    from esolangs.interpreters.tape_based.brainif import _advance

    initial = (2, 0, chunked((0, 7)))
    assert _advance(initial, (0, "input", 0)) == (3, 0, initial[2])
    result = _advance(initial, (0, "input", 0), 257)
    assert normalized((result[2], result[0], result[1], 0)) == ((257, 7), 3, 0, 0)
    assert initial == (2, 0, chunked((0, 7)))


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 9, 10, 11, 12])
@pytest.mark.parametrize("case", range(7))
def test_wide_generated_marker_boundaries(n, case):
    size = 1 << n
    table = "".join(str(row.bit_count() % 2) for row in range(size))
    rows = (0, 1, size // 3, size // 2 - 1, size // 2, size - 2, size - 1)
    generated_result(table, rows[case], n, width=1000, cap=4000 + 50 * size)
