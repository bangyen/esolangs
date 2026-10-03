"""Independent mutable Decleq store; esolangs.org/wiki/Decleq, revision 194503."""

import itertools
import random

import pytest

import esolangs
from esolangs.exceptions import HaltError, InterpreterLimitError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.decleq import _Machine, run


class Reference:
    def __init__(self, memory, stdin="", pc=0, ceiling=1 << 24):
        self.memory = list(memory)
        self.pc = pc
        self.stdin = stdin
        self.cursor = self.past_end = 0
        self.output = ""
        self.ceiling = ceiling

    @property
    def halted(self):
        return not 0 <= self.pc < len(self.memory)

    def read(self, address):
        return self.memory[address] if 0 <= address < len(self.memory) else 0

    def write(self, address, value):
        if address < -len(self.memory):
            raise HaltError(
                f"address {address} is {-address - len(self.memory)} cells past the "
                f"left end of a {len(self.memory)}-cell store"
            )
        if address >= len(self.memory):
            if address >= self.ceiling:
                raise InterpreterLimitError(
                    f"Decleq would have to grow its store to {address + 1} cells, "
                    f"past the {self.ceiling}-cell limit this interpreter allocates"
                )
            self.memory.extend([0] * (address + 1 - len(self.memory)))
        self.memory[address] = value

    def step(self):
        if self.halted:
            return
        words = self.memory[self.pc : self.pc + 3]
        words += [0] * (3 - len(words))
        a, b, c = words
        if a == -2:
            self.output += chr(self.read(b) % 256)
            self.pc += 3
        elif a == -1:
            if self.cursor == len(self.stdin):
                self.past_end += 1
                raise EOFError
            value = ord(self.stdin[self.cursor])
            self.cursor += 1
            self.write(b, value)
            self.pc += 3
        else:
            value = self.read(a) - 1
            self.write(b, value)
            self.pc = c if value <= 0 else self.pc + 3

    def result(self):
        return (
            self.pc,
            tuple(self.memory),
            self.output,
            self.cursor,
            self.past_end,
            self.halted,
        )


def image(memory):
    return " ".join(map(str, memory))


def inspect(machine):
    assert machine.pc == machine.ip
    assert machine.state == (machine.pc, tuple(machine.memory))
    assert machine.stack == []
    return (
        machine.pc,
        tuple(machine.memory),
        machine.io.getvalue(),
        machine.io.position(),
        machine.io.past_end,
        machine.halted,
    )


def compare(memory, stdin, cap, pc=None, code=None, ceiling=1 << 24):
    expected = Reference(memory, stdin, 0 if pc is None else pc, ceiling)
    actual = _Machine(image(memory) if code is None else code, ScriptedIO(stdin))
    if pc is not None:
        actual.pc = pc
    assert inspect(actual) == expected.result()
    error = None
    for _ in range(cap):
        old_state = actual.state
        snapshot = actual.snapshot()
        old_hash = hash(snapshot)
        detail = None
        try:
            expected.step()
        except (EOFError, HaltError) as caught:
            error = EOFError if isinstance(caught, EOFError) else type(caught)
            with pytest.raises(error) as reported:
                actual.step()
            if not isinstance(caught, EOFError):
                detail = (str(reported.value), str(caught))
        else:
            actual.step()
        if detail is not None:
            assert detail[0] == detail[1]
        assert inspect(actual) == expected.result(), (memory, stdin, pc, cap)
        assert old_state == (snapshot[1], snapshot[0])
        assert hash(snapshot) == old_hash
        assert actual.snapshot() == (
            tuple(expected.memory),
            expected.pc,
            expected.cursor,
        )
        if error or expected.halted:
            break
    if expected.halted:
        before = inspect(actual)
        actual.step()
        actual.step()
        assert inspect(actual) == before
    return expected, error


def corpus():
    yield [], "unused", None
    for a, b, c, value in itertools.product(
        (-3, -2, -1, 0, 1, 2, 3, 6, 8, 12),
        (-10, -9, -8, -1, 0, 1, 2, 3, 6, 8, 9, 12),
        (-1, 0, 1, 3, 6, 8, 9, 20),
        (-1, 0, 1, 2, 257),
    ):
        yield [a, b, c, -2, 8, 0, 0, 0, value], "\x00A\n\u0101", None
    for size in (1, 2):
        for words in itertools.product((-3, -2, -1, 0, 1, 3, 6), repeat=size):
            yield list(words), "AB", None
    for stdin in ("", "Q", "\x00", "\n", "\u0101", "AB"):
        for b in (-7, -6, -1, 0, 1, 2, 3, 6, 8):
            yield [-1, b, -1, -2, b, 0], stdin, None
    for value in (-(10**100), 10**100, -257, -256, 255, 256, 257):
        yield [-2, 6, 0, 6, 6, -1, value], "", None
    yield [9, 9, 3, -1, 10, 0, -2, 11, 0, 1, 0, 66, 0, 0, 999], "Z", None
    for pc in (-1, 1, 2, 3, 4, 5, 6, 7):
        yield [5, 5, 6, 0, 0, 0, 7], "AB", pc
    for address in ((1 << 24) + 1, 10**40):
        yield [0, address, -1], "", None
        yield [-1, address, -1], "Q", None
        yield [0, -address, -1], "", None
    rng = random.Random(1720)
    for _ in range(48):
        yield [rng.choice(range(-9, 25)) for _ in range(24)], "0\n1\u0100xyz", None


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_bounded_mutable_states_and_effects(cap):
    for memory, stdin, pc in corpus():
        compare(memory, stdin, cap, pc)


def test_run_matches_independent_halting_or_error_cases():
    for memory, stdin, pc in corpus():
        if pc is not None:
            continue
        expected = Reference(memory, stdin)
        error = None
        for _ in range(16):
            try:
                expected.step()
            except (EOFError, HaltError) as caught:
                error = EOFError if isinstance(caught, EOFError) else type(caught)
            if error or expected.halted:
                break
        if not (expected.halted or error):
            continue
        io = ScriptedIO(stdin)
        if error:
            with pytest.raises(error):
                run(image(memory), io)
        else:
            run(image(memory), io)
        assert (io.getvalue(), io.position(), io.past_end) == (
            expected.output,
            expected.cursor,
            expected.past_end,
        )


@pytest.mark.parametrize(
    ("memory", "stdin", "cap", "state", "output"),
    [
        ([0, 2, 99], "", 1, (99, (0, 2, -1)), ""),
        ([3, 1, -1, 2], "", 1, (3, (3, 1, -1, 2)), ""),
        ([3, 1, -1, 1], "", 1, (-1, (3, 0, -1, 1)), ""),
        ([-2, 0, -1], "", 1, (3, (-2, 0, -1)), "\xfe"),
        ([-1, -1, -1], "\u0101", 1, (3, (-1, -1, 257)), ""),
        ([6, -1, -1, 9, 8, 7, 3], "", 1, (3, (6, -1, -1, 9, 8, 7, 2)), ""),
    ],
)
def test_literal_copy_branch_and_io_controls(memory, stdin, cap, state, output):
    expected, error = compare(memory, stdin, cap)
    assert error is None
    assert (expected.pc, tuple(expected.memory)) == state
    assert expected.output == output


def test_self_decrementing_states_do_not_repeat():
    memory = [10, 10, 0]
    expected = Reference(memory)
    actual = _Machine(image(memory), ScriptedIO())
    seen = set()
    for step in range(500):
        expected.step()
        actual.step()
        assert inspect(actual) == expected.result()
        assert expected.memory[10] == -step - 1
        assert actual.snapshot() not in seen
        seen.add(actual.snapshot())


def test_pure_transition_default_byte_and_empty_negative_write():
    from esolangs.interpreters.register_based.decleq import _advance, _written

    initial = (0, (-1, 3, 0))
    assert _advance(initial) == (3, (-1, 3, 0, 0))
    assert initial == (0, (-1, 3, 0))
    assert _advance(initial, 65) == (3, (-1, 3, 0, 65))
    with pytest.raises(HaltError) as caught:
        _written((), -1, 9)
    assert (
        str(caught.value) == "address -1 is 1 cells past the left end of a 0-cell store"
    )


def test_numeric_source_comments_and_malformed_tokens():
    from esolangs.interpreters.memory import parse_int_memory

    for code, memory in [
        ("# head\n+1_0 -1 # tail\n\n\u0662\n", [10, -1, 2]),
        ("-2\t5\n0 9 6 7", [-2, 5, 0, 9, 6, 7]),
        ("\n\t# only", []),
    ]:
        assert parse_int_memory(code) == memory
        compare(memory, "AB", 16, code=code)
    for token in ("x", "1.0", "1__0", "-", "0x10"):
        with pytest.raises(ValueError, match="malformed memory token") as caught:
            _Machine("1 " + token, ScriptedIO())
        assert str(caught.value) == f"malformed memory token: {token!r}"


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
        code = esolangs.generate("Decleq", table, width=width)
        for row, answer in enumerate(table):
            stdin = format(row, f"0{n}b")
            assert generated_result(code, stdin, 2000) == (answer, n)


@pytest.mark.parametrize("n", [4, 5, 6, 9])
@pytest.mark.medium
def test_larger_generated_folded_and_lookup_tables(n):
    rng = random.Random(1721 + n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "1" * (1 << (n - 1)) + "0" * (1 << (n - 1)),
        "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        "".join(rng.choice("01") for _ in range(1 << n)),
    ]
    if n == 6:
        old_rng = random.Random(6)
        tables.append("".join(old_rng.choice("01") for _ in range(1 << n)))
    for table in tables:
        code = esolangs.generate("Decleq", table)
        rows = range(1 << n) if n <= 6 else (0, 1, 255, 256, 510, 511)
        for row in rows:
            stdin = format(row, f"0{n}b")
            assert generated_result(code, stdin, 4000) == (table[row], n)


def test_exact_allocation_ceiling_with_bounded_proxy(monkeypatch):
    import esolangs._validate as validation

    assert validation.check_address((1 << 24) - 1, "Decleq") == (1 << 24) - 1
    with pytest.raises(InterpreterLimitError) as caught:
        validation.check_address(1 << 24, "Decleq")
    assert str(caught.value) == (
        "Decleq would have to grow its store to 16777217 cells, "
        "past the 16777216-cell limit this interpreter allocates"
    )
    monkeypatch.setattr(validation, "_MAX_CELLS", 8)
    for a, b, stdin in itertools.product((0, -1), (7, 8, 9), ("Q", "")):
        compare([a, b, -1], stdin, 2, ceiling=8)
    for length, a, address in itertools.product((7, 8), (0, -1), (6, 7, 8, 9)):
        memory = [a, address, -1] + [0] * (length - 3)
        compare(memory, "Q", 1, ceiling=8)
    expected, error = compare([-1, 7, -1], "Q", 1, ceiling=8)
    assert error is None
    assert expected.memory == [-1, 7, -1, 0, 0, 0, 0, 81]


def test_unbounded_integer_cells_and_target_messages():
    from esolangs.interpreters.memory import parse_int_memory

    for digits in ("9" * 6000, "1" + "0" * 5998 + "7"):
        value = 0
        for digit in digits:
            value = 10 * value + ord(digit) - ord("0")
        for sign, number in (("", value), ("-", -value)):
            source = "-2 6 0 0 0 -1 " + sign + digits
            expected, error = compare([-2, 6, 0, 0, 0, -1, number], "", 3, code=source)
            assert error is None
            assert expected.halted
            assert expected.output == chr(number % 256)
            io = ScriptedIO()
            run(source, io)
            assert io.getvalue() == chr(number % 256)
        assert parse_int_memory("+0" + digits) == [value]
        assert parse_int_memory("_".join(digits)) == [value]
        assert parse_int_memory("\u0669" * 6000) == [10**6000 - 1]
        for a, stdin in ((0, ""), (-1, "Q")):
            machine = _Machine(f"{a} " + digits + " -1", ScriptedIO(stdin))
            before = machine.state
            with pytest.raises(InterpreterLimitError) as caught:
                machine.step()
            expected_length = (
                "1" + "0" * 6000 if digits[0] == "9" else digits[:-1] + "8"
            )
            assert str(caught.value) == (
                "Decleq would have to grow its store to " + expected_length + " cells, "
                "past the 16777216-cell limit this interpreter allocates"
            )
            assert machine.state == before
            assert machine.io.position() == len(stdin)
        machine = _Machine("0 -" + digits + " -1", ScriptedIO())
        before = machine.snapshot()
        with pytest.raises(HaltError) as caught:
            machine.step()
        past = digits[:-1] + ("6" if digits[0] == "9" else "4")
        assert str(caught.value) == (
            "address -"
            + digits
            + " is "
            + past
            + " cells past the left end of a 3-cell store"
        )
        assert machine.snapshot() == before
    with pytest.raises(ValueError, match="malformed memory token"):
        parse_int_memory("9" * 6000 + "z")


def test_shared_parser_executes_large_subleq_and_sbleq_cells():
    from esolangs.interpreters.tape_based.sbleq import run as run_sbleq
    from esolangs.interpreters.tape_based.subleq import run as run_subleq

    digits = "9" * 6000
    for runner, code in (
        (run_subleq, "6 -1 0 3 3 -1 " + digits),
        (run_sbleq, "-3 6 0 6 6 7 " + digits + " -1"),
    ):
        io = ScriptedIO()
        runner(code, io)
        assert (io.getvalue(), io.position(), io.past_end) == ("\xff", 0, 0)


def test_full_state_cycle_and_input_progress_certificates():
    from esolangs.vm import run_until_halt_or_cycle

    memory = [3, 4, 0, 0, -1]
    expected = Reference(memory)
    expected.step()
    assert expected.result() == Reference(memory).result()
    assert not run_until_halt_or_cycle(_Machine(image(memory), ScriptedIO()), limit=20)
    machine = _Machine("-1 6 0 7 6 0 0 0", ScriptedIO("\x00\x00"))
    expected, error = compare([-1, 6, 0, 7, 6, 0, 0, 0], "\x00\x00", 5)
    assert error is EOFError
    assert (expected.cursor, expected.past_end) == (2, 1)
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(machine, limit=20)
    assert (machine.io.position(), machine.io.past_end) == (2, 1)


def test_io_falls_through_from_a_nonzero_pointer():
    memory = [9, 9, 3, -1, 10, 0, -2, 11, 0, 1, 0, 66, 0, 0, 999]
    expected, error = compare(memory, "Z", 3)
    assert error is None
    assert (expected.pc, expected.output, expected.cursor) == (9, "B", 1)
    assert expected.memory[10] == 90
