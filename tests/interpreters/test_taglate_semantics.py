"""Independent deque execution and inline loop scans; esolangs.org/wiki/Taglate."""

import itertools
import random
import re
from collections import deque

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.queue_based.taglate import _Machine, run
from tests.interpreters.views import view as vm_view


def reference(code, stdin, cap):
    queue = deque(ord(char) & 65535 for char in code[0]) if code else deque()
    tokens = re.findall(r"gy|gz|[abcdefhijt]", "".join(code[1:]))
    pc = offset = 0
    output = ""
    error = None
    for _ in range(cap):
        if pc == len(tokens):
            break
        command = tokens[pc]
        next_pc = pc + 1
        try:
            if command in "abcd":
                x, y = queue.popleft(), queue.popleft()
                if command == "a":
                    value = x + y
                elif command == "b":
                    value = x - y
                elif command == "c":
                    value = x * y
                else:
                    if y == 0:
                        error = "halt"
                        break
                    value = x // y
                queue.append(value & 65535)
            elif command == "e":
                queue.append(queue.popleft())
            elif command == "f":
                queue.popleft()
            elif command == "i":
                output += chr(queue.popleft())
            elif command == "h":
                if offset == len(stdin):
                    error = "eof"
                    break
                queue.append(ord(stdin[offset]) & 65535)
                offset += 1
            elif command == "j":
                value = queue.popleft()
                queue.append(value - 1 if value else 1)
            elif command in {"gy", "gz"}:
                nonzero = bool(queue and queue[0])
                if (command == "gy" and not nonzero) or (command == "gz" and nonzero):
                    direction = 1 if command == "gy" else -1
                    depth = 1
                    at = pc
                    while depth:
                        at += direction
                        if not 0 <= at < len(tokens):
                            error = "syntax"
                            break
                        if tokens[at] == command:
                            depth += 1
                        elif tokens[at] in {"gy", "gz"}:
                            depth -= 1
                    if error:
                        break
                    next_pc = at + 1
            elif command == "t":
                text = ""
                for value in queue:
                    char = chr(value)
                    safe = (
                        ("A" <= char <= "Z")
                        or ("a" <= char <= "z")
                        or ("0" <= char <= "9")
                        or char in "-_.~"
                    )
                    text += char if safe else "%" + hex(value)[2:].upper().zfill(2)
                url = (
                    "https://translate.google.com/?sl=en&tl=es&text="
                    + text
                    + "&op=translate"
                )
                queue = deque(map(ord, url))
        except IndexError:
            error = "halt"
            break
        pc = next_pc
    return output, tuple(queue), pc, offset, pc == len(tokens), error


def observe(code, stdin, cap):
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    error = None
    for _ in range(cap):
        if machine.halted:
            break
        try:
            machine.step()
        except HaltError:
            error = "halt"
            break
        except EOFError:
            error = "eof"
            break
        except ValueError:
            error = "syntax"
            break
    assert vm_view(machine, "memory") == list(machine.queue)
    assert vm_view(machine, "stack") == []
    assert machine.ind == vm_view(machine, "ip")
    result = (
        io.getvalue(),
        tuple(vm_view(machine, "memory")),
        vm_view(machine, "ip"),
        io.position(),
        machine.halted,
        error,
    )
    if machine.halted:
        before = machine.snapshot()
        machine.step()
        machine.step()
        assert machine.snapshot() == before
        assert io.getvalue() == result[0]
    return result


def corpus():
    seeds = ["", "\0", "\x01", "\x02\0", "12", "\uffff\x01", "\U00010001", "a !\u0100"]
    commands = ["a", "b", "c", "d", "e", "f", "gy", "gz", "h", "i", "j", "t", "g", "x"]
    for seed in seeds:
        for count in range(3):
            for program in itertools.product(commands, repeat=count):
                yield [seed, "".join(program)]
    yield from [
        [],
        [""],
        ["Hi", "ii"],
        ["11", "gyigz"],
        ["\0" + "1", "gyigz"],
        ["\x03", "gyjgzi"],
        ["\0", "gygyigzgzi"],
        ["\x02\0", "gyjgyegzegz"],
        ["11", "g", "yigz"],
        ["1", "gi"],
        ["1", "ig"],
        ["1", "gXi"],
        ["1", "ix"],
        ["1", "gygz"],
        ["", "hhhiii"],
        ["", "hi"],
        ["0", "fhi"],
        ["\uffff\uffff", "ci"],
        ["Hi", "t" + "i" * 59],
        ["a b", "t" + "i" * 62],
    ]
    rng = random.Random(1710)
    for _ in range(32):
        yield [rng.choice(seeds), "".join(rng.choices(commands, k=12))]


@pytest.mark.parametrize("cap", [0, 1, 2, 9, 80])
def test_bounded_states_match_independent_deque(cap):
    for code in corpus():
        for stdin in ("", "x\n\U00010001"):
            assert observe(code, stdin, cap) == reference(code, stdin, cap), (
                code,
                stdin,
                cap,
            )


def test_run_matches_proven_halting_reference():
    for code in corpus():
        expected = reference(code, "x\n\U00010001", 80)
        if expected[4] and expected[5] is None:
            io = ScriptedIO("x\n\U00010001")
            run(code, io)
            assert (io.getvalue(), io.position()) == (expected[0], expected[3]), code


@pytest.mark.parametrize(
    ("seed", "commands", "output"),
    [
        ("Hi", "ii", "Hi"),
        ("12", "ai", "c"),
        ("12", "bi", "\uffff"),
        ("11", "ci", chr(49 * 49)),
        ("93", "di", "\x01"),
        ("12", "ei", "2"),
        ("12", "fi", "2"),
        ("1", "ji", "0"),
        ("11", "bji", "\x01"),
        ("\uffff\x01", "ai", "\0"),
        ("\uffff\uffff", "ci", "\x01"),
        ("\U00010001", "i", "\x01"),
        ("\x03", "gyjgzi", "\0"),
        ("1", "gi", "1"),
        ("1", "ig", "1"),
        ("1", "gXi", "1"),
        ("1", "ix", "1"),
    ],
)
def test_reference_positive_controls(seed, commands, output):
    code = [seed, commands]
    expected = reference(code, "", 80)
    assert expected[0] == output
    assert expected[4]
    assert expected[5] is None
    assert observe(code, "", 80) == expected


def test_url_control_and_error_side_effects():
    url = "https://translate.google.com/?sl=en&tl=es&text=a%20%21%100&op=translate"
    assert reference(["a !\u0100", "t"], "", 1)[1] == tuple(map(ord, url))
    for code in (
        ["1", "a"],
        ["1\0", "d"],
        ["", "i"],
        ["", "h"],
        ["\0", "gy"],
        ["1", "gz"],
    ):
        assert observe(code, "", 1) == reference(code, "", 1)
    assert reference(["1", "a"], "", 1)[1:] == ((), 0, 0, False, "halt")
    assert reference(["1\0", "d"], "", 1)[1:] == ((), 0, 0, False, "halt")
    assert observe(["", "hi"], "\U00010001", 2)[0] == "\x01"
    assert reference(["1", "gygz"], "", 80)[4:] == (False, None)


def test_snapshot_distinguishes_queue_changes_at_equal_cursor():
    machine = _Machine(["\x02", "gyjgz"], ScriptedIO())
    machine.step()
    before = machine.snapshot()
    cursor = vm_view(machine, "ip")
    machine.step()
    machine.step()
    assert vm_view(machine, "ip") == cursor
    assert machine.queue == (1,)
    assert machine.snapshot() != before


def test_snapshot_distinguishes_consumed_input_at_equal_queue_and_cursor():
    machine = _Machine(["1", "gyhfgz"], ScriptedIO("11"))
    machine.step()
    before = machine.snapshot()
    state = machine.queue, vm_view(machine, "ip")
    for _ in range(3):
        machine.step()
    assert (machine.queue, vm_view(machine, "ip")) == state
    assert machine.io.position() == 1
    assert machine.snapshot() != before


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        program = esolangs.generate("Taglate", table)
        code = program.split("\n")
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            stdin = esolangs.encode_inputs("Taglate", bits, table)
            result = reference(code, stdin, 20_000)
            assert result[4:] == (True, None), (table, row)
            assert result[0] == answer, (table, row)
            assert observe(code, stdin, 20_000) == result, (table, row)
            io = ScriptedIO(stdin)
            run(code, io)
            assert (io.getvalue(), io.position()) == (answer, len(stdin))
