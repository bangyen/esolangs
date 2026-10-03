"""Independent scanner and mutable instruction store; esolangs.org/wiki/Crement."""

import itertools
import random
import string
from decimal import Decimal

import pytest

import esolangs
from esolangs.exceptions import HaltError, ProgramError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.crement import _Machine, run
from tests.raises import raises_message

_LETTERS = string.ascii_letters + "_"
_DIGITS = string.digits


def name_valid(name):
    return (
        bool(name)
        and name[0] in _LETTERS
        and all(char in _LETTERS + _DIGITS for char in name)
    )


def number(source, labels, here):
    position = total = 0
    if not source:
        raise ProgramError("a number must contain at least one term")
    while position < len(source):
        sign = 1
        if source[position] in "+-":
            sign = -1 if source[position] == "-" else 1
            position += 1
        elif position:
            raise ProgramError(f"invalid number: {source}")
        if position == len(source):
            raise ProgramError(f"invalid number: {source}")
        start = position
        char = source[position]
        if char == "@":
            value = here
            position += 1
        elif char in _DIGITS:
            while position < len(source) and source[position] in _DIGITS:
                position += 1
            value = 0
            for digit in source[start:position]:
                value = 10 * value + ord(digit) - ord("0")
        elif char in _LETTERS:
            while position < len(source) and source[position] in _LETTERS + _DIGITS:
                position += 1
            name = source[start:position]
            if name not in labels:
                raise ProgramError(f"undefined label: {name}")
            value = labels[name]
        else:
            raise ProgramError(f"invalid number: {source}")
        total += sign * value
    return total


def parse(code):
    text = []
    comment = False
    for char in code:
        if char == "\n":
            comment = False
            text.append(char)
        elif not comment:
            if char == "*":
                text.append(" ")
                comment = True
            else:
                text.append(char)
    tokens = iter("".join(text).split())
    records = []
    for first in tokens:
        count = 3 if first.startswith(":") else 2
        record = [first]
        for _ in range(count):
            following = next(tokens, None)
            if following is None:
                break
            record.append(following)
        records.append(record)
    labels = {}
    for here, record in enumerate(records):
        if record[0].startswith(":"):
            name = record[0][1:]
            if not name_valid(name):
                raise ProgramError(f"invalid label: {name}")
            if name in labels:
                raise ProgramError(f"duplicate label: {name}")
            labels[name] = here
    program = []
    for here, record in enumerate(records):
        fields = record[1:] if record[0].startswith(":") else record
        if len(fields) != 3:
            raise ProgramError(f"instruction {here} must have three fields")
        opcode, address, data = fields
        if len(opcode) != 2 or opcode[0] not in "+-" or opcode[1] not in "ADJ":
            raise ProgramError(f"invalid opcode: {opcode}")
        program.append(
            [
                opcode[1],
                1 if opcode[0] == "+" else -1,
                number(address, labels, here),
                number(data, labels, here),
            ]
        )
    return program


def frozen(program):
    return tuple(tuple(row) for row in program)


def apply(program, pc):
    if pc >= len(program):
        return pc
    if pc < 0:
        raise HaltError(f"Crement executed negative address {Decimal(pc)}")
    opcode, polarity, address, data = program[pc]
    if opcode == "J":
        taken = data > 0 if polarity == 1 else data < 0
        if taken:
            if address < 0:
                raise HaltError(
                    f"Crement jumped to negative address {Decimal(address)}"
                )
            return address
    else:
        if address < 0:
            raise HaltError(f"Crement wrote to negative address {Decimal(address)}")
        if address < len(program):
            field = 2 if opcode == "A" else 3
            program[address][field] = data + polarity
    return pc + 1


def reference(code, cap):
    program = parse(code)
    pc = 0
    error = None
    for _ in range(cap):
        if pc >= len(program):
            break
        try:
            pc = apply(program, pc)
        except HaltError as exc:
            error = str(exc)
            break
    return pc, frozen(program), pc >= len(program), error


def machine_store(program):
    return tuple((row.opcode, row.polarity, row.address, row.data) for row in program)


def observe(code, cap):
    io = ScriptedIO("unused")
    machine = _Machine(code, io)
    error = None
    for _ in range(cap):
        if machine.halted:
            break
        before = machine.state
        saved = before.ip, machine_store(before.program)
        snapshot = machine.snapshot()
        assert (snapshot.ip, machine_store(snapshot.program)) == saved
        old_hash = hash(snapshot)
        try:
            machine.step()
        except HaltError as exc:
            error = str(exc)
        assert (before.ip, machine_store(before.program)) == saved
        assert (snapshot.ip, machine_store(snapshot.program)) == saved
        assert hash(snapshot) == old_hash
        if error is not None:
            break
    assert io.getvalue() == ""
    assert io.position() == 0
    assert machine.stack == []
    assert machine_store(machine.memory) == machine_store(machine.state.program)
    if machine.halted:
        before = machine.snapshot()
        machine.step()
        machine.step()
        assert machine.snapshot() == before
    return machine.ip, machine_store(machine.memory), machine.halted, error


def corpus():
    instructions = [
        f"{op} {address} {data}"
        for op in ["+A", "-A", "+D", "-D", "+J", "-J"]
        for address in [-1, 0, 1, 2]
        for data in [-1, 0, 1]
    ]
    yield ""
    yield from instructions
    for pair in itertools.product(instructions, repeat=2):
        yield "\n".join(pair)
    yield from [
        "+D 1 4\n+J 2 0",
        "+A 1 0\n+J 2 1",
        "-D 1 4\n+D 9 7",
        ":start +J end-start 0 * forward\n:end -D @-1 start+2",
        ":start\n+J\nend-start * comment\n0\n:end\n-D\n@-1\nstart+2",
        "+J\n0\n0",
        "+J\n0\n1",
        "* ignored\r still ignored\n+J 0 0",
        "+D 0 4",
        "+A 0 1\n+D 0 8",
        "+A 2 1\n-D 2 1\n+J 0 0",
        ":_x9 +J +end-_x9+@ 0 :end -D @-1 _x9+2-1",
        ":x +J @-x+0 0",
        "+J 0-0 0",
        "+J 000 0",
        "+J -0 +0",
        ":1bad +J 0 0",
        ":x +J 0 0\n:x +J 0 0",
        "+J nowhere 0",
        "J 0 0",
        "+J 0",
        "+J 1x 0",
        "+J @+ 0",
        "+J 0++1 0",
        "+J \u0661 0",
        ": +J 0 0",
        ":Å +J 0 0",
        "+j 0 0",
        "+J 1.0 0",
        ":a +J a! 0",
        "+J missing! 0",
        "+J @-2+1 0",
        "+J 0 0 trailing",
        "+A 0 " + "9" * 100,
        "+J " + "9" * 100 + " 1",
    ]
    rng = random.Random(1717)
    for _ in range(32):
        yield "\n".join(rng.choices(instructions, k=8))


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 9, 48])
def test_bounded_states_and_parse_errors_match_independent_store(cap):
    for code in corpus():
        try:
            expected = reference(code, cap)
        except ProgramError as exc:
            with raises_message(ProgramError, str(exc)):
                _Machine(code, ScriptedIO())
        else:
            assert observe(code, cap) == expected, (code, cap)


def test_run_matches_proven_halting_reference():
    for code in corpus():
        try:
            result = reference(code, 48)
        except ProgramError:
            continue
        if result[-2] and result[-1] is None:
            io = ScriptedIO("unused")
            run(code, io)
            assert (io.getvalue(), io.position()) == ("", 0), code


@pytest.mark.parametrize(
    ("code", "cap", "pc", "program"),
    [
        ("+D 1 4\n+J 2 0", 1, 1, (("D", 1, 1, 4), ("J", 1, 2, 5))),
        ("+A 1 0\n+J 2 1", 1, 1, (("A", 1, 1, 0), ("J", 1, 1, 1))),
        ("-D 1 4\n+D 9 7", 2, 2, (("D", -1, 1, 4), ("D", 1, 9, 3))),
        ("+D 0 4", 1, 1, (("D", 1, 0, 5),)),
        ("+J 0 1", 9, 0, (("J", 1, 0, 1),)),
        ("+J -1 0", 1, 1, (("J", 1, -1, 0),)),
    ],
)
def test_reference_positive_controls(code, cap, pc, program):
    result = reference(code, cap)
    assert result[:2] == (pc, program)
    assert result[-1] is None
    assert observe(code, cap) == result


def certificate(code, cap):
    program = parse(code)
    pc = 0
    seen = {}
    for steps in range(cap + 1):
        state = pc, frozen(program)
        if pc >= len(program):
            return "halt", state, steps, None
        if state in seen:
            return "cycle", state, steps, seen[state]
        seen[state] = steps
        if steps < cap:
            pc = apply(program, pc)
    raise AssertionError("independent classification exceeded its step bound")


def test_self_modification_is_part_of_cycle_certificate():
    code = "+D 1 0\n+J 0 0"
    assert certificate(code, 20)[0] == "cycle"
    machine = _Machine(code, ScriptedIO())
    before = machine.snapshot()
    machine.step()
    machine.step()
    assert machine.ip == 0
    assert machine.snapshot() != before
    assert observe(code, 2) == reference(code, 2)


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [None, 1, 5, 6, 9, 13])
def test_every_small_generated_table_with_full_state_certificate(n, width):
    from esolangs.vm import run_until_halt_or_cycle

    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        template = esolangs.generate("Crement", table, width=width)
        sizes = set()
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            code = esolangs.instantiate("Crement", template, bits)
            sizes.add(len(code))
            kind, state, steps, entry = certificate(code, 200)
            assert kind == ("halt" if answer == "0" else "cycle"), (table, row, width)
            actual = _Machine(code, ScriptedIO("unused"))
            first = actual.snapshot() if entry == 0 else None
            for position in range(steps):
                actual.step()
                if position + 1 == entry:
                    first = actual.snapshot()
            assert (actual.ip, machine_store(actual.memory)) == state
            assert actual.halted is (kind == "halt")
            if kind == "cycle":
                assert actual.snapshot() == first
                assert entry is not None
                assert entry < steps
            else:
                io = ScriptedIO("unused")
                run(code, io)
                assert (io.getvalue(), io.position()) == ("", 0)
            driven = _Machine(code, ScriptedIO("unused"))
            assert run_until_halt_or_cycle(driven, limit=200) is (kind == "halt")
            assert (driven.io.getvalue(), driven.io.position()) == ("", 0)
        assert len(sizes) == 1, (table, width, sizes)


def test_unbounded_decimal_operands_and_negative_target_messages():
    huge = "9" * 6000
    value = 10**6000 - 1
    for code in [
        "+D 0 " + huge,
        "+A 0 " + huge,
        "+J " + huge + " 1",
        "+J -" + huge + " 1",
        "-D -" + huge + " 0",
    ]:
        assert observe(code, 1) == reference(code, 1)
    assert reference("+D 0 " + huge, 1)[1][0][3] == value + 1
    assert (
        reference("+J -" + huge + " 1", 1)[-1]
        == "Crement jumped to negative address -" + huge
    )

    sparse = "1" + "0" * 5998 + "7"
    for digits in (sparse, "000" + sparse):
        assert observe("+D 0 " + digits, 1) == reference("+D 0 " + digits, 1)
        assert observe("+J -" + digits + " 1", 1)[-1] == (
            "Crement jumped to negative address -" + sparse
        )
