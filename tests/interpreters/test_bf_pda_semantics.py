"""Independent scanning bit-stack model; BF-PDA wiki revision 83429."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.bf_pda import _Machine, run


def rejection(code):
    if code == "":
        return "BF-PDA program cannot be empty"
    brackets = [(index, glyph) for index, glyph in enumerate(code) if glyph in "[]"]
    while True:
        paired = set()
        for index in range(len(brackets) - 1):
            if brackets[index][1] + brackets[index + 1][1] == "[]":
                paired.update((index, index + 1))
        if not paired:
            break
        brackets = [
            entry for index, entry in enumerate(brackets) if index not in paired
        ]
    closes = [index for index, glyph in brackets if glyph == "]"]
    if closes:
        return f"unmatched ']' at position {closes[0]}"
    if brackets:
        return f"unmatched '[' at position {brackets[-1][0]}"
    return None


def partner(code, at):
    opening = code[at] == "["
    direction = 1 if opening else -1
    same, opposite = ("[", "]") if opening else ("]", "[")
    nesting = 1
    cursor = at
    while nesting:
        cursor += direction
        if code[cursor] == same:
            nesting += 1
        elif code[cursor] == opposite:
            nesting -= 1
    return cursor


class Reference:
    def __init__(self, code, stack=(), ip=0):
        error = rejection(code)
        if error is not None:
            raise ValueError(error)
        self.code = code
        self.stack = list(stack)
        self.ip = ip
        self.output = ""

    @property
    def halted(self):
        return self.ip >= len(self.code)

    def state(self):
        return self.ip, tuple(self.stack)

    def step(self):
        if self.halted:
            return
        glyph = self.code[self.ip]
        # Empty storage represents the implicit zero without a physical cell.
        bit = self.stack[-1] if self.stack else 0
        cursor = self.ip + 1
        if glyph == "@":
            if self.stack:
                self.stack.pop()
            self.stack.append(1 - bit)
        elif glyph == "<":
            self.stack.append(0)
        elif glyph == ">":
            if self.stack:
                self.stack.pop()
        elif glyph == ".":
            self.output += str(bit)
        elif (glyph == "[" and bit == 0) or (glyph == "]" and bit == 1):
            cursor = partner(self.code, self.ip) + 1
        self.ip = cursor


def inspect(machine):
    assert machine.ip == machine.state[0]
    assert machine.stack == machine.state[1]
    assert machine.memory == []
    assert machine.io.position() == machine.io.past_end == 0
    return machine.state, machine.halted, machine.io.getvalue()


def compare(code, cap, stack=(), ip=0):
    expected = Reference(code, stack, ip)
    actual = _Machine(code, ScriptedIO("unused\x00\u0101"))
    assert actual.state == (0, ())
    actual.state = (ip, tuple(stack))
    assert actual.code == code
    assert actual.size == len(code)
    assert actual.jumps == {
        at: partner(code, at) for at, glyph in enumerate(code) if glyph in "[]"
    }
    assert inspect(actual) == (expected.state(), expected.halted, expected.output)
    states = {expected.state()}
    for _ in range(cap):
        before = actual.snapshot()
        saved_hash = hash(before)
        expected.step()
        actual.step()
        assert inspect(actual) == (
            expected.state(),
            expected.halted,
            expected.output,
        ), (code, stack, ip, cap)
        assert actual.snapshot() == expected.state()
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


def source_images():
    for size in range(6):
        for chars in itertools.product("@.<>[]x", repeat=size):
            yield "".join(chars)
    yield from (
        "<[.<[.",
        "[[]",
        "<@]",
        "abc<@.xyz",
        "<@\n.\t>",
        "<@<@[>[@]]",
        "<@<@[>[>].]",
        "[[.]]",
        "<@<@[<@[>@]>]",
        ".[[]@]",
        ".[[].]",
        "@<@.[>][]",
        "@<@[>.][]",
        "<@." * 60,
        "<" * 110 + ".",
        "<" * 50 + "." * 10 + "<" * 200,
        "\u0101\x00\r\n@.\u2603",
        "@[<@]",
        "@[@@]",
        "@[.]",
        "[ignored[\n\t[]]@]tail",
        "<[<@>[.]]>.",
    )


@pytest.mark.medium
def test_source_validation_matches_independent_cancellation():
    for code in source_images():
        error = rejection(code)
        if error is None:
            actual = _Machine(code, ScriptedIO())
            assert actual.jumps == {
                at: partner(code, at) for at, glyph in enumerate(code) if glyph in "[]"
            }
        else:
            with pytest.raises(
                ValueError, match=r"cannot be empty|unmatched"
            ) as caught:
                _Machine(code, ScriptedIO())
            assert str(caught.value) == error
            with pytest.raises(ValueError, match=r"cannot be empty|unmatched"):
                run(code, ScriptedIO())


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_bounded_commands_and_nested_loops(cap):
    for code in source_images():
        if rejection(code) is None:
            compare(code, cap)


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_every_small_stack_and_instruction_position(cap):
    programs = ("@.<>x", "[.@>]x", "[[]@].", "<@[>[@]]", "@<@.[>][]", "@<@[>.][]")
    for size in range(4):
        for stack in itertools.product((0, 1), repeat=size):
            for code in programs:
                for ip in range(len(code) + 2):
                    compare(code, cap, stack, ip)


def test_public_runner_matches_independent_halt_certificates():
    programs = (
        "<@.",
        "<.",
        "<@@.",
        "<@@@.",
        "<<@.>.",
        "abc<@.xyz",
        "<@\n.\t>",
        "<[.]",
        "<@[>]",
        "<@<@[.>]",
        "<@[@.]",
        "<@[>.]",
        "<@<@[>[@]]",
        "<@<@[>[>].]",
        "[[.]]",
        "<@<@[<@[>@]>]",
        ".[[]@]",
        ".[[].]",
        "@<@.[>][]",
        "@<@[>.][]",
        "<@." * 60,
        "<" * 110 + ".",
        "<" * 50 + "." * 10 + "<" * 200,
        ">",
        ">>",
        "<>>",
        ".",
        "@.",
        "[<@.>]",
        "<@>.",
        "\u0101\x00\r\n@.\u2603",
    )
    for code in programs:
        expected, verdict = compare(code, 1000)
        assert verdict == "halt"
        io = ScriptedIO("unused")
        run(code, io)
        assert (io.getvalue(), io.position(), io.past_end) == (expected.output, 0, 0)
        assert esolangs.run("BF-PDA", code, "unused", max_steps=1000) == expected.output


def test_exact_cycles_and_growth_have_distinct_certificates():
    from esolangs.vm import run_until_halt_or_cycle

    assert run_until_halt_or_cycle(_Machine("<@.", ScriptedIO()), limit=24)
    for code in ("@[]", "@[@@]", "@[.]", "@<@[><@]"):
        expected, verdict = compare(code, 24)
        assert verdict == "cycle"
        assert not expected.halted
        assert not run_until_halt_or_cycle(_Machine(code, ScriptedIO()), limit=24)
    expected, verdict = compare("@[<@]", 24)
    assert verdict == "bounded"
    assert len(expected.stack) > 1
    with pytest.raises(TimeoutError, match="undecided"):
        run_until_halt_or_cycle(_Machine("@[<@]", ScriptedIO()), limit=24)


def test_snapshot_distinguishes_cursor_and_buried_bits():
    states = ((0, ()), (1, ()), (0, (0,)), (0, (1,)), (0, (0, 1)), (0, (1, 1)))
    machine = _Machine("@.<>", ScriptedIO())
    snapshots = []
    for state in states:
        machine.state = state
        snapshots.append(machine.snapshot())
    assert len(set(snapshots)) == len(states)


def generated_result(table, row, n, width=None):
    template = esolangs.generate("BF-PDA", table, width=width)
    code = esolangs.instantiate(
        "BF-PDA", template, [int(bit) for bit in format(row, f"0{n}b")]
    )
    expected = Reference(code)
    actual = _Machine(code, ScriptedIO("unused"))
    for _ in range(4000):
        if expected.halted:
            break
        expected.step()
        actual.step()
        assert inspect(actual) == (expected.state(), expected.halted, expected.output)
    assert expected.halted, (n, row, width)
    assert expected.output == table[row]
    assert esolangs.run("BF-PDA", code, "unused", timeout=3) == table[row]
    return expected.stack


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [None, 1, 4, 9])
def test_every_small_generated_table(n, width):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        for row in range(1 << n):
            assert generated_result(table, row, n, width) == []


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6, 9])
@pytest.mark.parametrize("kind", range(5))
def test_larger_generated_tables(n, kind):
    rng = random.Random(1729 + n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        "".join(rng.choice("01") for _ in range(1 << n)),
        "1" * (1 << (n - 1)) + "0" * (1 << (n - 1)),
    ]
    for row in range(1 << n):
        assert generated_result(tables[kind], row, n) == []
