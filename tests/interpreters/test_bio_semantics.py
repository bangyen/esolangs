"""Independent mutable BIO model; wiki revision 138700 and byte-output dialect."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.bio import _Machine, parse, run


def tokenize(source):
    text = "\n".join(line.partition("//")[0] for line in source.split("\n"))
    commands = []
    cursor = 0
    while cursor < len(text):
        if text[cursor].isspace():
            cursor += 1
            continue
        if text[cursor : cursor + 2] == "};":
            commands.append(("end", None))
            cursor += 2
            continue
        token = text[cursor : cursor + 4].lower()
        if (
            len(token) != 4
            or token[0] not in "01"
            or token[1] not in "oi"
            or token[2] not in "xyz"
            or token[3] != ("{" if token[:2] == "0i" else ";")
        ):
            raise ValueError("BIO: not a command")
        commands.append((token[:2], "xyz".index(token[2])))
        cursor += 4
    depth = 0
    for operation, _register in commands:
        if operation == "0i":
            depth += 1
        elif operation == "end":
            if depth == 0:
                raise ValueError("BIO: '}' closes no loop")
            depth -= 1
    if depth:
        raise ValueError("BIO: unmatched '{'")
    return commands


def spelling(command):
    operation, register = command
    if operation == "end":
        return "};"
    return operation + "xyz"[register] + ("{" if operation == "0i" else ";")


class Reference:
    def __init__(self, code, registers=(0, 0, 0)):
        self.commands = tokenize(code)
        self.registers = list(registers)
        self.stack = []
        self.ip = 0
        self.output = ""

    @property
    def halted(self):
        return self.ip >= len(self.commands)

    def state(self):
        return tuple(self.registers), tuple(self.stack), self.ip, 0

    def step(self):
        if self.halted:
            return
        operation, register = self.commands[self.ip]
        following = self.ip + 1
        if operation == "0o":
            self.registers[register] += 1
        elif operation == "1o":
            self.registers[register] -= 1
        elif operation == "1i":
            self.output += chr(self.registers[register] % 256)
        elif operation == "end":
            following = self.stack.pop()
        elif self.registers[register] != 0:
            self.stack.append(self.ip)
        else:
            depth = 1
            while depth:
                nested, _index = self.commands[following]
                depth += (nested == "0i") - (nested == "end")
                following += 1
        self.ip = following


def inspect(actual):
    assert actual.ip == actual.ind
    assert actual.memory == list(actual.reg)
    assert actual.stack == list(actual.stk)
    assert actual.io.position() == actual.io.past_end == 0
    assert actual.snapshot() == (actual.reg, actual.stk, actual.ind, 0)
    return actual.snapshot(), actual.halted, actual.io.getvalue()


def compare(code, cap, registers=(0, 0, 0)):
    expected = Reference(code, registers)
    actual = _Machine(code, ScriptedIO("unused\x00\u0101"))
    assert actual.state == (0, (0, 0, 0), ())
    assert actual.commands == [spelling(command) for command in expected.commands]
    assert actual.size == len(expected.commands)
    actual.state = (0, tuple(registers), ())
    assert inspect(actual) == (expected.state(), expected.halted, expected.output)
    states = {expected.state()}
    for _ in range(cap):
        before = actual.snapshot()
        saved_hash = hash(before)
        expected.step()
        actual.step()
        assert inspect(actual) == (expected.state(), expected.halted, expected.output)
        assert hash(before) == saved_hash
        if expected.halted:
            terminal = inspect(actual)
            actual.step()
            actual.step()
            assert inspect(actual) == terminal
            return expected, "halt"
        if expected.state() in states:
            return expected, "cycle"
        states.add(expected.state())
    return expected, "bounded"


def multiplication_print(message):
    pieces = []
    for char in message:
        quotient, remainder = divmod(ord(char), 8)
        pieces.append(
            "0ox;" * 8
            + "0ix{"
            + "0oy;" * quotient
            + "1ox;};"
            + "0oy;" * remainder
            + "1iy;0iy{1oy;};"
        )
    return "".join(pieces)


def corpus():
    tokens = [
        mode + register + ("{" if mode == "0i" else ";")
        for mode in ("0o", "1o", "1i", "0i")
        for register in "xyz"
    ] + ["};"]
    for length in range(4):
        for commands in itertools.product(tokens, repeat=length):
            yield "".join(commands)
    for length in range(4):
        for characters in itertools.product("01oix;{}/ \n", repeat=length):
            yield "".join(characters)
    yield from (
        "0OX;1IX;",
        "0oY;1Iy;",
        "\u20030oz;\u00a01iz;",
        "//};\n0ox; // invalid {\n1ix; // text",
        "0o//x;\nx;",
        "0ix;",
        "0Iy;",
        "0ox;0iz;",
        "0ox{};",
        "1ix{};",
        "0ox;invalid;1ix;",
        "0ox;};1ix;",
        "0iy{0ox;",
        "};garbage",
        "0ox;0ix{0oy;0iy{0oz;1oy;};1ox;};1iz;",
        "0ox;0ix{0ix{};};",
        "0ox;0ix{0ox;};",
        "1ox;0ix{1ox;};",
        "0ix{0iy{0iz{0ox;};};};1iy;",
        "0ox;0ix{1ox;};0oy;0iy{1oy;};",
        "0ox;" * 300 + "1ix;",
        "1oz;" * 257 + "1iz;",
        multiplication_print("Hello World!"),
        multiplication_print("\x00\xffA\n"),
        "0ox;0oy;0ix{1ox;0oy;};1iy;",
        "0ox;0ox;0oy;0iy{0ox;1oy;};1ix;",
        "0ox;" * 5 + "0ix{1ox;" + "0oy;" * 5 + "};1iy;",
    )


@pytest.mark.medium
def test_manual_tokenization_and_exact_load_errors():
    for code in corpus():
        error_message = None
        try:
            expected = tokenize(code)
        except ValueError as error:
            error_message = str(error)
        if error_message is not None:
            for factory in (
                parse,
                lambda code: _Machine(code, ScriptedIO()),
                lambda code: run(code, ScriptedIO()),
            ):
                with pytest.raises(ValueError, match="BIO:") as caught:
                    factory(code)
                assert str(caught.value) == error_message, code
        else:
            assert parse(code) == [spelling(command) for command in expected], code
            compare(code, 0)


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_bounded_nested_loops_and_register_operations(cap):
    for code in corpus():
        try:
            tokenize(code)
        except ValueError:
            continue
        compare(code, cap)


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_signed_register_boundaries_and_independence(cap):
    programs = [
        mode + register + ";" for mode in ("0o", "1o", "1i") for register in "xyz"
    ]
    programs += ["0i" + register + "{1o" + register + ";};" for register in "xyz"]
    programs += ["0ix{0iy{0iz{1oz;};1oy;};1ox;};1iz;", "0ix{0iy{};};"]
    for values in itertools.product((-257, -1, 0, 1, 257), repeat=3):
        for code in programs:
            compare(code, cap, values)
    for index in range(3):
        for value in (-(10**80), 10**80, -256, 255, 256):
            values = [17, 31, 47]
            values[index] = value
            for code in programs:
                compare(code, cap, values)


def test_snapshots_distinguish_register_stack_cursor_and_input():
    machine = _Machine("0ox;0ix{0iy{};};", ScriptedIO("x"))
    snapshots = {machine.snapshot()}
    for state in (
        (1, (0, 0, 0), ()),
        (0, (1, 0, 0), ()),
        (0, (0, 1, 0), ()),
        (0, (0, 0, 1), ()),
        (0, (0, 0, 0), (1,)),
        (0, (0, 0, 0), (1, 2)),
    ):
        machine.state = state
        snapshots.add(machine.snapshot())
    machine.io.input_char()
    snapshots.add(machine.snapshot())
    assert len(snapshots) == 8


def test_cycles_growth_and_halt_have_independent_certificates():
    from esolangs.vm import run_until_halt_or_cycle

    for code in ("0ox;0ix{};", "0ox;0ix{0ix{};};", "1oz;0iz{0iy{};};"):
        _expected, verdict = compare(code, 24)
        assert verdict == "cycle"
        assert run_until_halt_or_cycle(_Machine(code, ScriptedIO()), limit=24) is False
    for code in ("0ox;0ix{0ox;};", "1ox;0ix{1ox;};"):
        expected, verdict = compare(code, 24)
        assert verdict == "bounded"
        assert abs(expected.registers[0]) > 1
        with pytest.raises(TimeoutError, match="undecided"):
            run_until_halt_or_cycle(_Machine(code, ScriptedIO()), limit=24)
    assert run_until_halt_or_cycle(_Machine("0ox;1ix;", ScriptedIO()), limit=24)


def test_public_runner_and_named_arithmetic_examples():
    programs = {
        "": "",
        "0ox;1ix;": "\x01",
        "1ox;1ix;": "\xff",
        "0ox;0oy;0ix{1ox;0oy;};1iy;": "\x02",
        # The wiki's subtraction body increments x; its actual result is 2 + 1.
        "0ox;0ox;0oy;0iy{0ox;1oy;};1ix;": "\x03",
        "0ox;" * 5 + "0ix{1ox;" + "0oy;" * 5 + "};1iy;": "\x19",
        multiplication_print("Hello World!"): "Hello World!",
        multiplication_print("\x00\xffA\n"): "\x00\xffA\n",
    }
    for code, output in programs.items():
        expected, verdict = compare(code, 10000)
        assert verdict == "halt"
        assert expected.output == output
        io = ScriptedIO("unused")
        run(code, io)
        assert io.getvalue() == output
        assert io.position() == 0
        assert esolangs.run("BIO", code, "unused", max_steps=10000) == output


def generated_result(table, row, n, template):
    bits = [(row >> (n - 1 - index)) & 1 for index in range(n)]
    code = esolangs.instantiate("BIO", template, bits)
    expected = Reference(code)
    actual = _Machine(code, ScriptedIO("unused"))
    for _ in range(2000 + 80 * (1 << n)):
        if expected.halted:
            break
        expected.step()
        actual.step()
    assert expected.halted, (n, row)
    assert expected.output == table[row]
    assert inspect(actual) == (expected.state(), True, expected.output)
    io = ScriptedIO("unused")
    run(code, io)
    assert io.getvalue() == expected.output
    assert io.position() == 0


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [None, 1, 4, 9])
def test_every_small_generated_table(n, width):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        template = esolangs.generate("BIO", table, width=width)
        for row in range(1 << n):
            generated_result(table, row, n, template)


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6])
@pytest.mark.parametrize("kind", range(5))
def test_larger_generated_tables(n, kind):
    rng = random.Random(1743 + n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        "".join(rng.choice("01") for _ in range(1 << n)),
        "1" * (1 << (n - 1)) + "0" * (1 << (n - 1)),
    ]
    table = tables[kind]
    template = esolangs.generate("BIO", table)
    for row in range(1 << n):
        generated_result(table, row, n, template)


@pytest.mark.medium
@pytest.mark.parametrize("n", [9, 12])
@pytest.mark.parametrize("case", range(7))
def test_wide_generated_index_boundaries(n, case):
    size = 1 << n
    table = "".join(str(row.bit_count() % 2) for row in range(size))
    rows = (0, 1, size // 3, size // 2 - 1, size // 2, size - 2, size - 1)
    generated_result(table, rows[case], n, esolangs.generate("BIO", table))
