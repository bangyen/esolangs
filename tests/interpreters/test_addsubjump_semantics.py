"""Independent dense ASJ machine; esolangs.org/wiki/AddSubJump, revision 188172."""

import itertools
import random

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.addsubjump import _Machine, _program, run
from tests.interpreters.views import view as vm_view


class Reference:
    def __init__(self, memory, stdin=""):
        self.memory = list(memory)
        self.ip = 0
        self.flags = [0] * 5
        self.stdin = stdin
        self.cursor = self.past_end = 0
        self.output = ""

    @property
    def halted(self):
        return not 0 <= self.ip < len(self.memory)

    def read(self, address):
        if address == -1:
            if self.cursor == len(self.stdin):
                self.past_end += 1
                raise EOFError
            value = ord(self.stdin[self.cursor])
            self.cursor += 1
            return value
        if -5 <= address <= -2:
            return self.flags[-address - 2]
        if address in (-6, -7, -8):
            return {-6: 1, -7: 0, -8: -1}[address]
        if address == -9:
            return self.flags[4]
        return self.memory[address] if 0 <= address < len(self.memory) else 0

    def step(self):
        if self.halted:
            return
        words = self.memory[self.ip : self.ip + 4]
        words += [0] * (4 - len(words))
        a, b, c, d = words
        if a < -9:
            raise ValueError("unassigned negative address")
        if a >= 1 << 24 and a >= len(self.memory):
            raise HaltError(f"memory address {a} is too large")
        selector = self.read(d)
        operand = self.read(b)
        if a == -1:
            value = operand
        else:
            current = self.read(a)
            value = current - operand if selector > 0 else current + operand
        if a == -1:
            self.output += chr(value % 256)
        elif a == -9:
            self.flags[4] = value
        elif a >= 0:
            self.memory += [0] * max(0, a + 1 - len(self.memory))
            self.memory[a] = value
        if self.flags[4] != 0:
            self.flags[:4] = [0, int(value == 0), int(value < 0), 0]
        self.ip = c

    def result(self):
        return (
            self.ip,
            tuple(self.memory),
            tuple(self.flags),
            self.output,
            self.cursor,
            self.past_end,
            self.halted,
        )


def image(memory):
    return " ".join(map(str, memory))


def inspect(machine):
    assert vm_view(machine, "stack") == []
    flags = (machine.cf, machine.zf, machine.nf, machine.vf, machine.fum)
    cells, length = machine.state[0]
    assert length == len(vm_view(machine, "memory"))
    assert all(value != 0 for value in cells.values())
    assert all(0 <= address < length for address in cells)
    assert tuple(machine.state[1:]) == (vm_view(machine, "ip"), *flags)
    return (
        vm_view(machine, "ip"),
        tuple(vm_view(machine, "memory")),
        flags,
        machine.io.getvalue(),
        machine.io.position(),
        machine.io.past_end,
        machine.halted,
    )


def compare(memory, stdin, cap, code=None, flags=None):
    expected = Reference(memory, stdin)
    actual = _Machine(image(memory) if code is None else code, ScriptedIO(stdin))
    if flags is not None:
        expected.flags = list(flags)
        actual.state = (*actual.state[:2], *flags)
    assert inspect(actual) == expected.result()
    error = None
    for _ in range(cap):
        before = actual.snapshot()
        old_hash = hash(before)
        old_state = actual.state
        old_cells = dict(old_state[0][0])
        try:
            expected.step()
        except ValueError:
            # The specification assigns only -9 through -1 below zero.
            return expected, "undefined address"
        except (EOFError, HaltError) as caught:
            error = EOFError if isinstance(caught, EOFError) else HaltError
        if error:
            with pytest.raises(error):
                actual.step()
        else:
            actual.step()
        assert inspect(actual) == expected.result(), (memory, stdin, cap)
        assert old_state[0][0] == old_cells
        assert hash(before) == old_hash
        cells, length = actual.state[0]
        assert actual.snapshot() == (
            tuple(sorted(cells.items())),
            length,
            vm_view(actual, "ip"),
            *expected.flags,
            expected.cursor,
        )
        if error or expected.halted:
            break
    if expected.halted:
        frozen = actual.snapshot()
        output = actual.io.getvalue()
        actual.step()
        actual.step()
        assert actual.snapshot() == frozen
        assert actual.io.getvalue() == output
    return expected, error


def corpus():
    yield [], "unused"
    addresses = (-9, -8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 8, 12)
    for a, b, c, d in itertools.product(
        addresses, addresses, (-10, -9, -1, 0, 1, 4, 8, 20), (-9, -8, -7, -6, -1, 0)
    ):
        yield [a, b, c, d, -1, -7, -1, -7, 3, 0, -2], "\x00\nA\u0101z"
    for size in (1, 2, 3):
        for words in itertools.product((-1, -6, -7, 0, 4), repeat=size):
            yield list(words), "AB"
    for stdin in ("", "Q", "\n", "AB", "ABC", "\u0101\n\xff"):
        for a, b, d in itertools.product((-1, 12), (-1, -6), (-1, -7)):
            yield [a, b, -1, d], stdin
    huge = 10**100 + 17
    for value in (-huge, huge, -257, -256, 255, 256, 257):
        yield [8, 9, 4, 10, -1, 8, -1, -7, value, -value, 1], ""
    for a in (0, 1, 2, 3, 4, 8, 11):
        yield [a, -6, 4, -7, -1, a, -1, -7], ""
    rng = random.Random(1718)
    pool = list(range(-9, 33))
    for _ in range(48):
        yield [rng.choice(pool) for _ in range(32)], "0\n1\u0100xyz"
    for destination in (8, 1 << 24, (1 << 24) + 1, 10**40):
        yield [destination, -1, -1, -1], "AB"


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_bounded_dense_states_and_effects(cap):
    for memory, stdin in corpus():
        compare(memory, stdin, cap)


def test_run_matches_independent_halting_or_error_cases():
    # A smaller projection avoids re-running every finite-prefix case publicly.
    cases = [
        ([-1, 4, -1, -7, 65], ""),
        ([12, -1, 4, -7, -1, 12, -1, -7], "X"),
        ([12, -1, 4, -7, -1, 12, -1, -7], ""),
        ([-1, -1, -1, -1], "AB"),
        ([8, -1, 4, -1, -1, 8, -1, -7], "ABC"),
        ([-9, -6, 4, -7, 12, -6, 8, -6, -1, -4, -1, -7], ""),
        ([1 << 24, -1, -1, -1], "AB"),
        ([], "unused"),
    ]
    for memory, stdin in cases:
        reference, error = compare(memory, stdin, 100)
        io = ScriptedIO(stdin)
        if error:
            with pytest.raises(error):
                run(image(memory), io)
        else:
            assert reference.halted
            run(image(memory), io)
        assert (io.getvalue(), io.position(), io.past_end) == (
            reference.output,
            reference.cursor,
            reference.past_end,
        )


@pytest.mark.parametrize(
    ("memory", "stdin", "result"),
    [
        ([-1, -1, -1, -1], "AB", (-1, "B", 2)),
        ([8, -1, 4, -1, -1, 8, -1, -7], "ABC", (-1, "\xbe", 2)),
        ([-1, -8, -1, -6], "", (-1, "\xff", 0)),
        ([-1], "", (0, "\xff\xff", 0)),
        ([2, -6, -1, -7], "", (-1, "", 0)),
    ],
)
def test_literal_read_order_output_and_captured_jump(memory, stdin, result):
    expected, error = compare(memory, stdin, 2)
    assert error is None
    assert (expected.ip, expected.output, expected.cursor) == result


def assembly_cases():
    specials = {
        "IO": -1,
        "CF": -2,
        "ZF": -3,
        "NF": -4,
        "VF": -5,
        "@1": -6,
        "@0": -7,
        "@n1": -8,
        "FUM": -9,
    }
    for name, address in specials.items():
        yield f".data {name}", [address]
    for b, d in itertools.product(("@1", "@0", "@n1"), ("@1", "@0", "@n1")):
        yield (
            f"ASJ value {b} ? {d}\nIO value IO\nvalue:.data 65",
            [8, specials[b], 4, specials[d], -1, 8, -1, -7, 65],
        )
    for size in range(7):
        numbers = list(range(size))
        source = ".data " + " ".join(f"V{i}:{value}" for i, value in enumerate(numbers))
        source += " end: ?"
        yield source, [*numbers, size + 1]
    for a, b in itertools.product(range(-3, 4), repeat=2):
        yield (
            f"IO A{a:+}\nIO A{b:+} IO\nA:.data 65",
            [-1, 8 + a, 4, -7, -1, 8 + b, -1, -7, 65],
        )
    for count in range(5):
        prefix = "def emit X {\nIO X\n}\n"
        source = prefix + "\n".join("emit H" for _ in range(count))
        source += "\n@0 @0 IO\nH:.data 72"
        words = [
            word
            for i in range(count)
            for word in (-1, 4 * (count + 1), 4 * (i + 1), -7)
        ]
        yield source, [*words, -7, -7, -1, -7, 72]
    yield "def one X {\n.data X\n}\ndef two X {\none X\none X\n}\ntwo 7", [7, 7]
    yield (
        "def skip X {\nlocal: @0 @0 local+4\nIO X IO\n}\nskip H\nskip H\nH:.data 72",
        [-7, -7, 4, -7, -1, 16, -1, -7, -7, -7, 12, -7, -1, 16, -1, -7, 72],
    )
    yield "def nop {\n}\nstart: nop\n.data start", [0]
    yield "def one X {\n.data X\n}\nstart: one 7\n.data start", [7, 0]
    yield ".data A: 1 ? A", [1, 3, 0]


def test_assembly_matches_independently_constructed_images():
    for code, memory in assembly_cases():
        assert _program(code) == memory, code
        compare(memory, "ABC\n", 16, code)
        commented = "/* header\ncontinued */\n" + "\n".join(
            line + (" // tail" if i % 2 else " # tail")
            for i, line in enumerate(code.splitlines())
        )
        assert _program(commented) == memory
        compare(memory, "ABC\n", 16, commented)


def test_canonical_snapshot_after_different_write_orders_and_input_reads():
    from esolangs.interpreters.register_based.addsubjump import _store

    one = _Machine("0 0 0 0", ScriptedIO("one\n"))
    other = _Machine("0 0 0 0", ScriptedIO("one\n"))
    one.state = _store(_store(one.state, 1, 4), 2, 9)
    other.state = _store(_store(other.state, 2, 9), 1, 4)
    assert one.snapshot() == other.snapshot()
    frozen = one.snapshot()
    one.io.input_char()
    assert one.snapshot() != frozen
    assert other.snapshot() == frozen


def generated_result(code, stdin, cap):
    expected = Reference([int(word) for word in code.split()], stdin)
    actual = _Machine(code, ScriptedIO(stdin))
    for _ in range(cap):
        if expected.halted:
            break
        expected.step()
        actual.step()
    assert expected.halted, (len(stdin), stdin, cap)
    assert inspect(actual) == expected.result()
    io = ScriptedIO(stdin)
    run(code, io)
    assert (io.getvalue(), io.position(), io.past_end) == (
        expected.output,
        expected.cursor,
        0,
    )
    return expected.output, expected.cursor


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [None, 1, 4, 9])
def test_every_small_generated_table(n, width):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        code = esolangs.generate("AddSubJump", table, width=width)
        for row, answer in enumerate(table):
            stdin = format(row, f"0{n}b")
            assert generated_result(code, stdin, 2000) == (answer, n)


@pytest.mark.parametrize(
    "n",
    [
        pytest.param(4, marks=pytest.mark.medium),
        pytest.param(5, marks=pytest.mark.medium),
        pytest.param(6, marks=pytest.mark.slow),
        pytest.param(7, marks=pytest.mark.slow),
        pytest.param(11, marks=pytest.mark.slow),
    ],
)
def test_larger_generated_packed_and_shared_tables(n):
    rng = random.Random(1719 + n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        "".join(rng.choice("01") for _ in range(1 << n)),
    ]
    for table in tables:
        code = esolangs.generate("AddSubJump", table)
        rows = (
            range(1 << n)
            if n <= 7
            else sorted(
                {0, 1, (1 << n) // 2 - 1, (1 << n) // 2, (1 << n) - 2, (1 << n) - 1}
            )
        )
        for row in rows:
            stdin = format(row, f"0{n}b")
            assert generated_result(code, stdin, 100000) == (table[row], n)


def test_unbounded_decimal_operands_and_allocation_error():
    for digits in ("9" * 6000, "1" + "0" * 5998 + "7"):
        value = 0
        for digit in digits:
            value = 10 * value + ord(digit) - ord("0")
        for signed, number in ((digits, value), ("-" + digits, -value)):
            memory = [-1, 4, -1, -7, number]
            for code in ("-1 4 -1 -7 " + signed, "IO X IO\nX:.data " + signed):
                reference, error = compare(memory, "", 2, code)
                assert error is None
                assert reference.halted
                io = ScriptedIO()
                run(code, io)
                assert io.getvalue() == chr(number % 256)
        code = digits + " -1 -1 -1"
        machine = _Machine(code, ScriptedIO("AB"))
        before = machine.snapshot()
        with pytest.raises(HaltError) as caught:
            machine.step()
        assert str(caught.value) == "memory address " + digits + " is too large"
        assert machine.snapshot() == before
        assert machine.io.position() == 0
        offset_code = ".data X: 0 X+" + digits
        assert _program(offset_code) == [0, value]


@pytest.mark.parametrize("fum", [0, 1, -1])
def test_seeded_flags_are_preserved_or_replaced_by_result(fum):
    for a, b, d in itertools.product((-9, -5, 8), (-8, -7, -6), (-7, -6)):
        compare([a, b, -1, d], "", 1, flags=(3, 4, 5, 6, fum))


def test_allocation_boundary_without_dense_materialization():
    last = (1 << 24) - 1
    memory = [last, -6, -1, -7]
    machine = _Machine(image(memory), ScriptedIO("AB"))
    machine.step()
    assert machine.state == (
        ({0: last, 1: -6, 2: -1, 3: -7, last: 1}, last + 1),
        -1,
        0,
        0,
        0,
        0,
        0,
    )
    assert machine.halted
    assert (machine.io.getvalue(), machine.io.position()) == ("", 0)
    io = ScriptedIO("AB")
    run(image(memory), io)
    assert (io.getvalue(), io.position()) == ("", 0)
    machine = _Machine(image([last + 1, -1, -1, -1]), ScriptedIO("AB"))
    before = machine.snapshot()
    with pytest.raises(HaltError) as caught:
        machine.step()
    assert str(caught.value) == f"memory address {last + 1} is too large"
    assert machine.snapshot() == before
    assert machine.io.position() == 0


def test_consuming_zero_bytes_does_not_certify_a_false_cycle():
    from esolangs.vm import run_until_halt_or_cycle

    code = "12 -1 0 -7"
    expected, error = compare([12, -1, 0, -7], "\x00\x00", 3)
    assert error is EOFError
    assert (expected.cursor, expected.past_end) == (2, 1)
    machine = _Machine(code, ScriptedIO("\x00\x00"))
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(machine, limit=10)
    assert (machine.io.position(), machine.io.past_end) == (2, 1)


def test_raw_numeric_compatibility_and_assembly_errors():
    for code, memory in [
        ("+1_0 -6 -1 -7 # tail", [10, -6, -1, -7]),
        ("\u0661\u0660 -6 -1 -7", [10, -6, -1, -7]),
        ("IO Missing IO", None),
        (".data 1__0", None),
        (".data +", None),
    ]:
        if memory is None:
            with pytest.raises(
                ValueError, match=r"(?:undefined label|invalid AddSubJump operand)"
            ):
                _program(code)
        else:
            assert _program(code) == memory
            compare(memory, "", 2, code)
