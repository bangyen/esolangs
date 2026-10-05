"""Independent mutable Suffolk model; wiki 189093 and scripted EOF dialect."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.suffolk import _Machine, run
from tests.interpreters.views import view as vm_view
from tests.raises import raises_message


class Reference:
    def __init__(self, code, stdin="", state=(0, 0, 0, (0,))):
        if not code:
            raise ValueError("Suffolk program cannot be empty")
        self.code = code
        self.stdin = stdin
        self.ip, self.pointer, self.accumulator, cells = state
        self.cells = list(cells)
        self.position = 0
        self.past_end = 0
        self.halted = False
        self.output = ""

    def snapshot(self):
        return (
            self.ip,
            self.pointer,
            self.accumulator,
            tuple(self.cells),
            self.position,
            self.halted,
        )

    def step(self):
        if self.halted:
            return
        operation = self.code[self.ip]
        if operation == ">":
            self.pointer += 1
            if self.pointer >= len(self.cells):
                self.cells.append(0)
        elif operation == "<":
            self.accumulator += self.cells[self.pointer]
            self.pointer = 0
        elif operation == "!":
            difference = self.cells[self.pointer] + 1 - self.accumulator
            self.cells[self.pointer] = difference if difference > 0 else 0
            self.pointer = self.accumulator = 0
        elif operation == ",":
            if self.position < len(self.stdin):
                self.accumulator += ord(self.stdin[self.position])
                self.position += 1
            else:
                self.accumulator = 0
                self.halted = True
                self.past_end += 1
        elif operation == "." and self.accumulator != 0:
            character = chr(self.accumulator - 1)
            self.output += character
        self.ip = (self.ip + 1) % len(self.code)


def inspect(machine):
    assert vm_view(machine, "ip") == machine.ind
    assert vm_view(machine, "memory") == list(machine.tape)
    assert vm_view(machine, "stack") == []
    assert machine.key == (machine.ind, machine.ptr, len(machine.tape))
    assert machine.values == (machine.acc, *machine.tape)
    assert machine.input_position() == machine.io.position()
    slack = (
        machine.tape[machine.ptr] + 1 - machine.acc
        if machine.code[machine.ind] == "!"
        else None
    )
    assert machine.clamp_slack == slack
    assert machine.snapshot() == (*machine.state, machine.io.position(), machine.halted)
    return machine.snapshot(), machine.io.past_end, machine.io.getvalue()


def compare(code, stdin="", cap=24, state=(0, 0, 0, (0,))):
    expected = Reference(code, stdin, state)
    actual = _Machine(code, ScriptedIO(stdin))
    actual.state = state
    assert inspect(actual) == (expected.snapshot(), expected.past_end, expected.output)
    states = {expected.snapshot()}
    for _ in range(cap):
        previous = actual.snapshot()
        previous_hash = hash(previous)
        error = None
        try:
            expected.step()
        except (ValueError, OverflowError) as caught:
            error = caught
        if error is not None:
            with pytest.raises(type(error)) as caught:
                actual.step()
            assert str(caught.value) == str(error)
        else:
            actual.step()
        assert inspect(actual) == (
            expected.snapshot(),
            expected.past_end,
            expected.output,
        ), (code, stdin, state)
        assert hash(previous) == previous_hash
        if error is not None:
            return expected, "error"
        if expected.halted:
            terminal = inspect(actual)
            actual.step()
            actual.step()
            assert inspect(actual) == terminal
            return expected, "halt"
        if expected.snapshot() in states:
            return expected, "cycle"
        states.add(expected.snapshot())
    return expected, "bounded"


def corpus():
    for length in range(1, 5):
        for operations in itertools.product("><!,.x", repeat=length):
            yield "".join(operations)
    yield from (
        " ",
        "\n",
        "\u2003",
        "a! b< c.",
        "!!!<>!",
        "!!<!",
        ">>>!",
        "!<.<<!",
        "!.<<!",
        "!!!!<<!",
        "!" * 66 + "<.",
        "!" * 70 + "<.",
        "!!!!!!!!>!><<<<<<<<<.!",
        ",,.",
        ",!",
        ",. ",
        ">>!>>!>>!>>!>>!>>!>>!>>!>>>!>>!>>!>><!>>",
    )


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_exhaustive_command_transitions_input_and_noise(cap):
    for code in corpus():
        for stdin in ("", "\x00\x00", "A\n", "\u0101", "01"):
            compare(code, stdin, cap)


@pytest.mark.medium
@pytest.mark.parametrize("pointer", [0, 1, 3])
def test_seeded_clamps_unbounded_values_and_character_errors(pointer):
    for values in itertools.product((0, 1, 2, 255, 256, 0x110000, 10**80), repeat=2):
        cell, accumulator = values
        cells = [17, 31, 47, 61]
        cells[pointer] = cell
        for operation in "><!,.x":
            for stdin in ("", "\x00", "\n", "\u0101"):
                compare(operation, stdin, 1, (0, pointer, accumulator, tuple(cells)))
    for operation in "<!.":
        compare(operation, cap=1, state=(0, pointer, 1 << 20000, (1 << 20000,) * 4))


def test_empty_source_exact_error_and_eof_snapshot_distinction():
    for factory in (
        Reference,
        lambda code: _Machine(code, ScriptedIO()),
        lambda code: run(code, ScriptedIO()),
    ):
        with raises_message(ValueError, "Suffolk program cannot be empty"):
            factory("")
    machine = _Machine(",", ScriptedIO())
    before = machine.snapshot()
    machine.step()
    assert machine.halted
    assert machine.snapshot() != before
    assert machine.io.position() == 0
    assert machine.io.past_end == 1


def test_snapshots_cover_cursor_pointer_accumulator_tape_input_and_eof():
    machine = _Machine(",!.", ScriptedIO("\x00"))
    snapshots = {machine.snapshot()}
    for state in (
        (1, 0, 0, (0,)),
        (0, 1, 0, (0, 0)),
        (0, 0, 1, (0,)),
        (0, 0, 0, (1,)),
        (0, 0, 0, (0, 0)),
    ):
        machine.state = state
        snapshots.add(machine.snapshot())
    machine.state = (0, 0, 0, (0,))
    machine.step()
    machine.state = (0, 0, 0, (0,))
    snapshots.add(machine.snapshot())
    machine.step()
    machine.state = (0, 0, 0, (0,))
    snapshots.add(machine.snapshot())
    assert len(snapshots) == 8


@pytest.mark.medium
def test_public_run_stops_only_on_certified_cycles_or_scripted_eof():
    from esolangs.vm import run_until_halt_or_cycle

    for code in corpus():
        expected, verdict = compare(code, cap=80)
        if verdict not in ("cycle", "halt"):
            continue
        io = ScriptedIO()
        run(code, io)
        assert io.getvalue() == expected.output
        assert io.position() == expected.position
        assert io.past_end == expected.past_end
        assert esolangs.run("Suffolk", code + " ", "") == expected.output
        actual = _Machine(code, ScriptedIO())
        assert run_until_halt_or_cycle(actual, limit=240) == (verdict == "halt")
    for code in ("!", ">", ">!", "!!"):
        expected, verdict = compare(code, cap=80)
        assert verdict == "bounded"
        assert (
            expected.accumulator > 0
            or max(expected.cells) > 1
            or len(expected.cells) > 1
        )
        with pytest.raises(TimeoutError, match="undecided"):
            run_until_halt_or_cycle(_Machine(code, ScriptedIO()), limit=80)


def generated_result(table, n, row, code):
    stdin = format(row, f"0{n}b")
    expected, verdict = compare(code, stdin, cap=2 * len(code) + 1)
    assert verdict == "halt"
    assert expected.output == table[row]
    assert expected.position == n
    assert expected.past_end == 1
    io = ScriptedIO(stdin)
    run(code, io)
    assert io.getvalue() == expected.output
    assert io.position() == n


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "batch"), [(1, 0), (2, 0), *((3, batch) for batch in range(16))]
)
@pytest.mark.parametrize("width", [None, 1, 4, 17])
def test_every_small_generated_table(n, batch, width):
    for value in range(16 * batch, min(16 * (batch + 1), 1 << (1 << n))):
        table = format(value, f"0{1 << n}b")
        code = esolangs.generate("Suffolk", table, width=width)
        for row in range(1 << n):
            generated_result(table, n, row, code)


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6, 8, 9, 10])
@pytest.mark.parametrize("kind", range(5))
def test_larger_generated_tables_and_ignored_inputs(n, kind):
    rng = random.Random(1135 + n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() & 1) for row in range(1 << n)),
        "".join(rng.choice("01") for _ in range(1 << n)),
        "1" * (1 << (n - 1)) + "0" * (1 << (n - 1)),
    ]
    table = tables[kind]
    code = esolangs.generate("Suffolk", table)
    rows = (
        range(1 << n)
        if n <= 5
        else (0, 1, (1 << n) // 2 - 1, (1 << n) // 2, (1 << n) - 2, (1 << n) - 1)
    )
    for row in rows:
        generated_result(table, n, row, code)


WIKI_HELLO = (
    "!!!!!!!!>!><<<<<<<<<<.!!!!!!>>!>><><<<<<<<<<<<<<<<<<<<<<.!!!"
    "!!!!!!!><<<<<<<<<<<<<.!!!!!!!!!!><<<<<<<<<<<<<.!!!!!!!!!!!>>"
    "<><<<<<<<<<<<<.!!!!!!<<<<<<<<<.!!!!<<<<<<<<<<<.!!!!!!!!!!!<<"
    "<<<<<<<<<<.!!!!!!!!!<<<<<<<<<<<<<<.!!!!!!<<<<<<<<<<<<<<<<<<<"
    "<<<<.!!!!!!!!!!><<<<<<<<<<<<<.!!!!!!!!!!!><<<<<<<<<<<.!!!!><"
    "<<<<<<<<<<<.!!!!<<<<<<<<<<<.!>>>!>>>!>>><>>!>>><>!"
)


def test_wiki_hello_has_bounded_output_and_observed_unreset_cell():
    reference, verdict = compare(WIKI_HELLO, cap=3 * len(WIKI_HELLO))
    assert verdict == "bounded"
    assert reference.output == "Hello, world! " * 3
    # The published cleanup leaves cell 3 growing by two each pass.
    assert reference.cells == [0, 0, 0, 6]


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 9, 10])
def test_historical_generated_size_controls_execute(n):
    table = "".join(str((row * 73 + row.bit_count()) & 1) for row in range(1 << n))
    code = esolangs.generate("Suffolk", table)
    assert len(code) == {8: 2211, 9: 3224, 10: 5087}[n]
    for row in (0, 1, (1 << n) // 2 - 1, (1 << n) // 2, (1 << n) - 2, (1 << n) - 1):
        generated_result(table, n, row, code)


@pytest.mark.medium
@pytest.mark.parametrize(
    "table",
    [
        "1000000000000000",
        "11111110",
        "1111111111111110",
        "0111111111111111",
        "11111100",
    ],
)
def test_historical_generated_complements_and_single_one(table):
    n = len(table).bit_length() - 1
    code = esolangs.generate("Suffolk", table)
    for row in range(1 << n):
        generated_result(table, n, row, code)


def test_affine_growth_certificates_have_repeating_positive_controls():
    from esolangs.vm import run_until_halt_or_value_growth

    for code in ("!", "!!", ">!"):
        expected, verdict = compare(code, cap=80)
        assert verdict == "bounded"
        assert max(expected.cells) >= 40
        assert (
            run_until_halt_or_value_growth(_Machine(code, ScriptedIO()), limit=240)
            is False
        )
    for code in (".", "<", "!<.<<!"):
        _expected, verdict = compare(code, cap=80)
        assert verdict == "cycle"
        with pytest.raises(TimeoutError, match="undecided"):
            run_until_halt_or_value_growth(_Machine(code, ScriptedIO()), limit=240)
