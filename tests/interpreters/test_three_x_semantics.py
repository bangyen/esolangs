"""Independent mutable rational stacks; esolangs.org/wiki/3x."""

import itertools
import random
from fractions import Fraction

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.three_x import _Machine, run
from tests.interpreters.views import view as vm_view


def number(token):
    parts = token.split("/")
    if len(parts) not in (1, 2):
        raise ValueError
    if len(parts) == 2 and parts[1].startswith(("+", "-")):
        raise ValueError
    for part in parts:
        digits = part[1:] if part.startswith(("+", "-")) else part
        if not digits or not all(char.isdecimal() for char in digits):
            raise ValueError
    denominator = int(parts[1]) if len(parts) == 2 else 1
    if denominator == 0:
        raise ValueError
    return Fraction(int(parts[0]), denominator)


def reference(code, stdin, cap):
    pc = position = 0
    stack = []
    loops = []
    variables = {}
    output = ""
    error = None
    for _ in range(cap):
        if pc >= len(code):
            break
        char = code[pc]
        needed = 3 if char == "x" else 2 if char in "v#" else 1 if char in "!^()" else 0
        if len(stack) < needed:
            error = ("HaltError", "empty stack")
            break
        following = pc + 1
        if char == "3":
            stack.append(Fraction(3))
        elif char == "x":
            if stack[-3] == 0:
                error = ("HaltError", "division by zero")
                break
            top, middle, bottom = stack.pop(), stack.pop(), stack.pop()
            stack.append((top - middle) / bottom)
        elif char == "?":
            while position < len(stdin) and stdin[position].isspace():
                position += 1
            start = position
            while position < len(stdin) and not stdin[position].isspace():
                position += 1
            if start == position:
                error = ("EOFError", "")
                break
            try:
                value = number(stdin[start:position])
            except ValueError:
                error = ("ValueError", "input must be an integer or a fraction")
                break
            stack.append(value)
        elif char == "!":
            output += str(stack.pop())
        elif char == "v":
            value, key = stack.pop(), stack.pop()
            variables[key] = value
        elif char == "^":
            key = stack.pop()
            stack.append(variables.get(key, Fraction(3)))
        elif char == "#":
            right, left = stack.pop(), stack.pop()
            stack.extend((right, left))
        elif char == "(":
            # Matchedness is settled on entry, whichever way the top goes.
            depth = 0
            matching = None
            for index in range(pc, len(code)):
                if code[index] == "(":
                    depth += 1
                elif code[index] == ")":
                    depth -= 1
                    if depth == 0:
                        matching = index
                        break
            if matching is None:
                pc = len(code)
                error = ("HaltError", "unmatched (")
                break
            if stack[-1]:
                loops.append(pc)
            else:
                following = matching + 1
        elif char == ")":
            if stack[-1]:
                if not loops:
                    error = ("HaltError", "unmatched )")
                    break
                following = loops[-1] + 1
            elif loops:
                loops.pop()
        elif char == "[":
            for index in range(pc + 1, len(code)):
                if code[index] == "]":
                    output += code[pc + 1 : index]
                    following = index + 1
                    break
        pc = following
    return (
        output,
        tuple(stack),
        tuple(loops),
        tuple(sorted(variables.items())),
        pc,
        position,
        pc >= len(code),
        error,
    )


def observe(code, stdin, cap):
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    error = None
    for _ in range(cap):
        if machine.halted:
            break
        try:
            machine.step()
        except (HaltError, ValueError, EOFError) as exc:
            error = (
                ("EOFError", "")
                if isinstance(exc, EOFError)
                else (type(exc).__name__, str(exc))
            )
            break
    assert vm_view(machine, "ip") == machine.ind
    assert vm_view(machine, "memory") == []
    if machine.halted:
        before = machine.snapshot(), io.getvalue(), io.position()
        machine.step()
        machine.step()
        assert (machine.snapshot(), io.getvalue(), io.position()) == before
    return (
        io.getvalue(),
        tuple(vm_view(machine, "stack")),
        tuple(machine.jumps),
        tuple(sorted(machine.variables.items())),
        vm_view(machine, "ip"),
        io.position(),
        machine.halted,
        error,
    )


def corpus():
    for size in range(4):
        for chars in itertools.product("3x?v^#!()[]a", repeat=size):
            yield "".join(chars), "1/2 -3 0 7 3 1"
    for code in (
        "[Hi]",
        "[Hello, World!]",
        "[A]333x!",
        "3333x3x!",
        "3333333x3xx!",
        "333x3#!",
        "???!!!",
        "????!!!",
        "33?x!",
        "?3^!",
        "3333xv3^!",
        "3333xv3333x3v3^!",
        "3333x3x(33x)!",
        "333x(3)!",
        "3(33x)!",
        "333x33x!",
        "333x(",
        "3)",
        "333(33x#)!",
        "333x(3()3)3!",
        "333x(())3!",
        "[abc",
        "[a]b[c]",
        "[hi][yo]",
        "[][a]",
        "3()",
        "3([1])",
        "?(!?)!",
        "333x([)])!",
        "333x([()])3!",
        "??v??v?^!?^!",
    ):
        yield code, "1 2 3 4 1 3"
    for stdin in (
        "",
        " \n\t",
        "abc",
        "1/0",
        "1.5",
        "1_2",
        "+1/-2",
        "1/+2",
        "-4/-2",
        "²",
        "\u0661/\u0662",
        "1/2/3",
        "+",
        "  4/2\t-3/7\n",
        "9" * 120,
    ):
        yield "?!", stdin
        yield "???", stdin
    rng = random.Random(1714)
    for _ in range(32):
        yield "".join(rng.choices("3x?v^#!()[]a", k=20)), "0 1 2 3 4 5"


@pytest.mark.parametrize("cap", [0, 1, 2, 9, 120])
def test_bounded_states_and_errors_match_independent_stacks(cap):
    for code, stdin in corpus():
        assert observe(code, stdin, cap) == reference(code, stdin, cap), (
            code,
            stdin,
            cap,
        )


def test_run_matches_proven_terminal_reference():
    for code, stdin in corpus():
        result = reference(code, stdin, 120)
        if not result[-2] and result[-1] is None:
            continue
        io = ScriptedIO(stdin)
        error = None
        try:
            run(code, io)
        except (HaltError, ValueError, EOFError) as exc:
            error = (
                ("EOFError", "")
                if isinstance(exc, EOFError)
                else (type(exc).__name__, str(exc))
            )
        assert (io.getvalue(), io.position(), error) == (
            result[0],
            result[5],
            result[-1],
        ), (code, stdin)


@pytest.mark.parametrize(
    ("code", "stdin", "output"),
    [
        ("[Hello, world!]", "", "Hello, world!"),
        ("3!", "", "3"),
        ("333x!", "", "0"),
        ("3333x3x!", "", "1"),
        ("3333333x3xx!", "", "-2/3"),
        ("???!!!", "1 2 3", "321"),
        ("????!!!", "1 2 3 4", "432"),
        ("333(33x#)!", "", "0"),
        ("333x(3()3)3!", "", "3"),
        ("3^!", "", "3"),
        ("3333xv3^!", "", "0"),
        ("?!", "1/2", "1/2"),
        ("?!", "4/2", "2"),
        ("?[1]?!", "0 2", "12"),
        ("?([1])[0]", "0", "0"),
    ],
)
def test_reference_positive_controls(code, stdin, output):
    result = reference(code, stdin, 120)
    assert result[0] == output
    assert result[-2:] == (True, None)
    assert observe(code, stdin, 120) == result
    io = ScriptedIO(stdin)
    run(code, io)
    assert io.getvalue() == output


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        code = esolangs.generate("3x", table)
        for row, answer in enumerate(table):
            stdin = " ".join(format(row, f"0{n}b"))
            result = reference(code, stdin, 10_000)
            assert result[-2:] == (True, None), (table, row)
            assert result[0] == answer, (table, row)
            assert observe(code, stdin, 10_000) == result, (table, row)
            io = ScriptedIO(stdin)
            run(code, io)
            assert (io.getvalue(), io.position()) == (result[0], result[5])


def test_input_progress_prevents_false_cycle():
    from esolangs.vm import run_until_halt_or_cycle

    machine = _Machine("?(!?)!", ScriptedIO("1 1 0"))
    assert run_until_halt_or_cycle(machine, limit=100) is True
    assert machine.io.getvalue() == "110"
    assert machine.io.position() == 5
    machine = _Machine("3(3v3)", ScriptedIO())
    machine.step()
    machine.step()
    before = machine.snapshot()
    for _ in range(4):
        machine.step()
    assert (vm_view(machine, "ip"), vm_view(machine, "stack"), machine.jumps) == (
        2,
        (3,),
        (1,),
    )
    assert machine.variables == {3: 3}
    assert machine.snapshot() != before
