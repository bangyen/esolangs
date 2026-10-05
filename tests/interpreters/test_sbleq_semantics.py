"""Independent mutable S*bleq engine; esolangs.org/wiki/S*bleq, revision 188944."""

import itertools
import random

import pytest

import esolangs
from esolangs.exceptions import InterpreterLimitError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.sbleq import _Machine, run
from tests.interpreters.views import view as vm_view


class Reference:
    def __init__(self, memory, stdin="", store="a", ip=0, ceiling=1 << 24):
        self.memory = list(memory)
        self.ip = ip
        self.stopped = False
        self.stdin = stdin
        self.cursor = self.past_end = 0
        self.output = ""
        self.store = store
        self.ceiling = ceiling

    @property
    def halted(self):
        return self.stopped or not 0 <= self.ip <= len(self.memory) - 3

    def input(self):
        if self.cursor == len(self.stdin):
            self.past_end += 1
            return 0
        value = ord(self.stdin[self.cursor])
        self.cursor += 1
        return value

    def read(self, address, byte=0):
        if address == -1:
            return self.ip
        if address == -2:
            return byte
        if address < 0:
            raise ValueError(f"invalid address {address}")
        return self.memory[address] if address < len(self.memory) else 0

    def step(self):
        if self.halted:
            return
        a, b, c = self.memory[self.ip : self.ip + 3]
        if a == -3 or b == -3:
            other = b if a == -3 else a
            byte = self.input() if other == -2 else 0
            self.output += chr(self.read(other, byte) % 256)
            if c < 0:
                raise ValueError(f"invalid S*bleq branch address {c}")
            self.ip += 3
            return
        byte = self.input() if -2 in (a, b) else 0
        if c < 0:
            raise ValueError(f"invalid S*bleq branch address {c}")
        difference = self.read(a, byte) - self.read(b, byte)
        destinations = {"a": (a,), "ab": (a, b), "b": (b,)}[self.store]
        # Arithmetic writes commit together; an invalid second growth commits neither.
        for address in destinations:
            if address >= len(self.memory) and address >= self.ceiling:
                raise InterpreterLimitError(
                    f"S*bleq would have to grow its store to {address + 1} cells, "
                    f"past the {self.ceiling}-cell limit this interpreter allocates"
                )
        for address in destinations:
            if address == -1:
                self.ip = difference
            elif address >= 0:
                self.memory.extend([0] * max(0, address + 1 - len(self.memory)))
                self.memory[address] = difference
        if difference > 0:
            self.ip += 3
        else:
            target = self.read(c)
            if target < 0:
                self.stopped = True
            else:
                self.ip = target

    def result(self):
        return (
            tuple(self.memory),
            self.ip,
            self.stopped,
            self.output,
            self.cursor,
            self.past_end,
            self.halted,
        )


def image(memory):
    return " ".join(map(str, memory))


def inspect(machine):
    assert vm_view(machine, "memory") == list(machine.mem)
    assert vm_view(machine, "stack") == []
    assert machine.eof_is_a_value is True
    assert machine._state == (  # noqa: SLF001
        tuple(vm_view(machine, "memory")),
        vm_view(machine, "ip"),
        machine._halted,  # noqa: SLF001
    )
    return (
        tuple(vm_view(machine, "memory")),
        vm_view(machine, "ip"),
        machine._halted,  # noqa: SLF001
        machine.io.getvalue(),
        machine.io.position(),
        machine.io.past_end,
        machine.halted,
    )


def compare(memory, stdin, cap, store="a", ip=None, ceiling=1 << 24, code=None):
    expected = Reference(memory, stdin, store, 0 if ip is None else ip, ceiling)
    actual = _Machine(image(memory) if code is None else code, ScriptedIO(stdin), store)
    assert actual.store == store
    if ip is not None:
        actual.ip = ip
    assert inspect(actual) == expected.result()
    error = None
    for _ in range(cap):
        old = actual._state  # noqa: SLF001
        snapshot = actual.snapshot()
        old_hash = hash(snapshot)
        detail = None
        try:
            expected.step()
        except (ValueError, InterpreterLimitError) as caught:
            error = type(caught)
            with pytest.raises(error) as reported:
                actual.step()
            detail = (str(reported.value), str(caught))
        else:
            actual.step()
        if detail is not None:
            assert detail[0] == detail[1]
        assert inspect(actual) == expected.result(), (memory, stdin, cap, store, ip)
        assert old == (snapshot[0], snapshot[1], snapshot[3])
        assert hash(snapshot) == old_hash
        assert actual.snapshot() == (
            tuple(expected.memory),
            expected.ip,
            expected.cursor,
            expected.stopped,
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
    addresses = (-4, -3, -2, -1, 0, 1, 2, 3, 6, 8, 9, 12)
    for a, b, c, value in itertools.product(
        addresses,
        addresses,
        (-3, -2, -1, 0, 1, 2, 3, 6, 8, 9, 12),
        (-1, 0, 1, 2, 5, 257),
    ):
        yield [a, b, c, 0, 0, 9, 0, 1, 2, value, -1, 20], "\x00A\n\u0101", None
    for size in (0, 1, 2):
        for values in itertools.product((-3, -2, -1, 0, 1, 3), repeat=size):
            yield list(values), "AB", None
    for stdin in ("", "Q", "\x00", "\n", "\u0101", "AB"):
        for a, b in itertools.product((-3, -2, -1, 0, 6), repeat=2):
            yield [a, b, 3, -3, 6, 0, -1], stdin, None
    for value in (-(10**100), 10**100, -257, -256, 255, 256, 257):
        yield [-3, 6, 0, 0, 0, 7, value, -1], "", None
        yield [6, 7, 8, -3, 6, 0, value, -value, -1], "", None
    for ip in (-1, 1, 2, 3, 4, 5, 6, 7, 8):
        yield [6, -1, 0, -3, -1, 0, 5, -1, 0], "AB", ip
    for a, b in ((12, 1 << 24), (1 << 24, 0), (0, 10**40)):
        yield [a, b, 0], "", None
    yield [9, 10, 3, -3, 9, 0, 0, 0, 11, 5, 3, -1], "", None
    yield [6, -1, 0, 0, 0, 0, 5], "", None
    rng = random.Random(1722)
    for _ in range(48):
        yield [rng.choice(range(-9, 25)) for _ in range(24)], "0\n1\u0100xyz", None


@pytest.mark.medium
@pytest.mark.parametrize("store", ["a", "ab", "b"])
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_bounded_store_variants_and_effects(store, cap):
    for memory, stdin, ip in corpus():
        compare(memory, stdin, cap, store, ip)


def test_run_matches_independent_halting_or_error_cases():
    cases = [
        ([9, 10, 3, -3, 9, 0, 0, 0, 11, 5, 3, -1], ""),
        ([-3, -2, 0], "\u0101"),
        ([-3, -2, 0], ""),
        ([-2, -2, 3, -1], "AB"),
        ([0, -2, 3, -3, 0, 6, -1], "Q"),
        ([0, -2, -1], "Q"),
        ([-3, 0, -1], ""),
        ([12, 1 << 24, 0], ""),
        ([], "unused"),
        ([0, 0], "unused"),
    ]
    for store in ("a", "ab", "b"):
        for memory, stdin in cases:
            expected, error = compare(memory, stdin, 100, store)
            if not (expected.halted or error):
                continue
            io = ScriptedIO(stdin)
            if error:
                with pytest.raises(error):
                    run(image(memory), io, store)
            else:
                run(image(memory), io, store)
            assert (io.getvalue(), io.position(), io.past_end) == (
                expected.output,
                expected.cursor,
                expected.past_end,
            )


@pytest.mark.parametrize(
    ("store", "cells", "output"),
    [("a", (2, 3), "\x02"), ("ab", (2, 2), "\x02"), ("b", (5, 2), "\x05")],
)
def test_literal_variant_destinations_reach_public_output(store, cells, output):
    memory = [9, 10, 3, -3, 9, 0, 0, 0, 11, 5, 3, -1]
    expected, error = compare(memory, "", 1, store)
    assert error is None
    assert tuple(expected.memory[9:11]) == cells
    io = ScriptedIO()
    run(image(memory), io, store)
    assert io.getvalue() == output
    if store == "a":
        machine = _Machine(image(memory), ScriptedIO())
        machine.step()
        assert tuple(machine.mem[9:11]) == cells
        io = ScriptedIO()
        run(image(memory), io)
        assert io.getvalue() == output


@pytest.mark.parametrize("store", ["a", "ab", "b"])
def test_pointer_destination_and_output_read_current_pointer(store):
    memory = [6, -1, 0, 0, 0, 0, 5]
    expected, error = compare(memory, "", 1, store)
    assert error is None
    assert expected.ip == (3 if store == "a" else 8)
    assert expected.stopped is False
    compare([0, 0, 9, -3, -1, 0, 0, 0, 0, 3], "", 2, store)


def test_shared_input_and_eof_are_observable():
    for stdin, cursor, past_end in (("AB", 1, 0), ("", 0, 1)):
        expected, error = compare([-2, -2, 3, -1], stdin, 1)
        assert error is None
        assert (expected.cursor, expected.past_end) == (cursor, past_end)
        assert expected.stopped
    io = ScriptedIO("\u0101\n")
    run("-3 -2 0 -2 -3 0", io)
    assert (io.getvalue(), io.position(), io.past_end) == ("\x01\n", 2, 0)


@pytest.mark.parametrize("store", ["A", "AB", "B", "c", "", "bb", "abc"])
def test_invalid_store_and_source_are_rejected(store):
    with pytest.raises(ValueError, match="unknown store target") as caught:
        _Machine("0 0 0", ScriptedIO(), store)
    assert str(caught.value) == f"unknown store target: {store!r}"
    with pytest.raises(ValueError, match="unknown store target"):
        run("", ScriptedIO(), store)


def test_source_comments_whitespace_and_malformed_tokens():
    for source, memory in (
        ("# head\n-3 6 0 # output\n0 0 7 65 9", [-3, 6, 0, 0, 0, 7, 65, 9]),
        ("\t# empty\n", []),
        ("+1_0\t-1\n\u0662", [10, -1, 2]),
    ):
        compare(memory, "", 8, code=source)
    for token in ("x", "1.0", "1__0", "-", "0x10"):
        with pytest.raises(ValueError, match="malformed memory token") as caught:
            _Machine("1 " + token, ScriptedIO())
        assert str(caught.value) == f"malformed memory token: {token!r}"


def test_direct_transition_defaults_and_legacy_exhaustion():
    from esolangs.interpreters.tape_based.sbleq import _advance, _write

    initial = ((0, -2, 3, -1), 0, False)
    assert _advance(initial, "a") == (initial[0], 0, True)
    assert initial == ((0, -2, 3, -1), 0, False)
    assert _write(initial, -2, 99) == initial
    assert _write(initial, -3, 99) == initial

    class LegacyIO(ScriptedIO):
        def input_char(self, _prompt="Input: "):
            raise IndexError

    machine = _Machine("0 0 0", LegacyIO())
    assert machine.input_byte() == 0


def test_full_state_cycle_certificate_keeps_input_progress():
    from esolangs.vm import run_until_halt_or_cycle

    memory = [0, -2, 3, 0, 0, 6, -1]
    expected = Reference(memory, "\x00\x00")
    snapshots = []
    for _ in range(3):
        expected.step()
        snapshots.append(
            (tuple(expected.memory), expected.ip, expected.cursor, expected.stopped)
        )
    assert snapshots[0] != snapshots[1]
    assert snapshots[1] == snapshots[2]
    machine = _Machine(image(memory), ScriptedIO("\x00\x00"))
    assert not run_until_halt_or_cycle(machine, limit=10)
    assert (machine.io.position(), machine.io.past_end) == (2, 2)
    assert run_until_halt_or_cycle(_Machine("", ScriptedIO()), limit=10)


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
        code = esolangs.generate("S*bleq", table, width=width)
        for row, answer in enumerate(table):
            stdin = format(row, f"0{n}b")
            assert generated_result(code, stdin, 2000) == (answer, n)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "kind"), [(n, k) for n in (4, 5, 6, 7) for k in range(5 if n == 7 else 4)]
)
def test_larger_shared_and_packed_generators(n, kind):
    from esolangs.tools.sbleq import _sbleq_packed

    rng = random.Random(1723 + n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        "".join(rng.choice("01") for _ in range(1 << n)),
    ]
    if n == 7:
        tables.append(format(random.Random(7).getrandbits(1 << n), f"0{1 << n}b"))
    table = tables[kind]
    shipped, packed = esolangs.generate("S*bleq", table), _sbleq_packed(table)
    if n == 7 and kind == 4:
        assert len(shipped) < len(packed)
    for code in (shipped, packed):
        for row, answer in enumerate(table):
            stdin = format(row, f"0{n}b")
            assert generated_result(code, stdin, 20000) == (answer, n)


def test_large_operands_and_diagnostics():
    digits = "9" * 6000
    huge = int(digits[:3000]) * 10**3000 + int(digits[3000:])
    for source, message in (
        ("-" + digits + " 0 0", "invalid address -" + digits),
        ("0 0 -" + digits, "invalid S*bleq branch address -" + digits),
    ):
        machine = _Machine(source, ScriptedIO())
        with pytest.raises(ValueError, match="invalid") as caught:
            machine.step()
        assert str(caught.value) == message
    io = ScriptedIO()
    run("-3 3 0 " + digits, io)
    assert io.getvalue() == chr(huge % 256)


@pytest.mark.parametrize("store", ["a", "ab", "b"])
def test_allocation_boundary_and_atomic_variant_writes(monkeypatch, store):
    import esolangs._validate as validation

    monkeypatch.setattr(validation, "_MAX_CELLS", 8)
    for memory in (
        [7, 6, 3, -1, 0, 0, 1],
        [8, 6, 3, -1, 0, 0, 1],
        [6, 8, 3, -1, 0, 0, 1],
        [8, 6, 3, -1, 0, 0, 1, 0],
    ):
        compare(memory, "", 2, store, ceiling=8)


def test_branch_target_is_read_after_arithmetic_write():
    expected, error = compare([0, 1, 0], "", 1)
    assert error is None
    assert expected.memory == [-1, 1, 0]
    assert expected.stopped
