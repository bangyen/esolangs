"""Independent pending-command deque; esolangs.org/wiki/Underload."""

import itertools
import random
from collections import deque

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.underload import _Machine, run
from tests.interpreters.views import view as vm_view


def reference(code, cap, initial=()):
    pending = deque(code)
    executed = []
    stack = list(initial)
    output = ""
    error = None
    for _ in range(cap):
        if not pending:
            break
        command = pending[0]
        closing = None
        if command == "(":
            depth = 0
            for index, char in enumerate(pending):
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        closing = index
                        break
            if closing is None:
                error = "unmatched Underload '('"
                break
        elif not command.isspace():
            count = 2 if command in "~*" else 1
            if command not in "~:!*a^S":
                error = (
                    "unmatched Underload ')'"
                    if command == ")"
                    else f"unknown Underload command {command!r}"
                )
                break
            if len(stack) < count:
                error = "Underload stack underflow"
                break
        executed.append(pending.popleft())
        if command == "(":
            literal = [pending.popleft() for _ in range(closing)]
            executed.extend(literal)
            stack.append("".join(literal[:-1]))
        elif command.isspace():
            pass
        elif command == "~":
            right, left = stack.pop(), stack.pop()
            stack.extend((right, left))
        elif command == ":":
            stack.extend([stack[-1]])
        elif command == "!":
            stack.pop()
        elif command == "*":
            right, left = stack.pop(), stack.pop()
            stack.append("".join((left, right)))
        elif command == "a":
            value = stack.pop()
            stack.append("(" + value + ")")
        elif command == "^":
            pending.extendleft(reversed(stack.pop()))
        elif command == "S":
            output += stack.pop()
    return (
        output,
        "".join(executed) + "".join(pending),
        len(executed),
        tuple(stack),
        not pending,
        error,
    )


def observe(code, cap, initial=()):
    io = ScriptedIO("unused")
    machine = _Machine(code, io)
    machine.state = (code, 0, tuple(initial))
    error = None
    for _ in range(cap):
        if machine.halted:
            break
        try:
            machine.step()
        except HaltError as exc:
            error = str(exc)
            break
    assert vm_view(machine, "memory") == []
    assert machine.code == code
    assert io.position() == 0
    if machine.halted:
        before = machine.snapshot(), io.getvalue()
        machine.step()
        machine.step()
        assert (machine.snapshot(), io.getvalue()) == before
    return (
        io.getvalue(),
        machine.state[0],
        vm_view(machine, "ip"),
        tuple(vm_view(machine, "stack")),
        machine.halted,
        error,
    )


def corpus():
    atoms = [
        "()",
        "(a)",
        "(b)",
        "((x))",
        "~",
        ":",
        "!",
        "*",
        "a",
        "^",
        "S",
        "x",
        ")",
        "(",
        " ",
    ]
    for size in range(4):
        for tokens in itertools.product(atoms, repeat=size):
            yield "".join(tokens)
    yield from [
        "(Hello, world!)S",
        "((x))S",
        "(a)(b)~SS",
        "(a):SS",
        "(a)(b)*S",
        "(a)aS",
        "(discard)!()S",
        "((yes)S)^((no)S)^",
        "(:^):^",
        "(::^):^",
        " \n\t\r",
        "( \n\t )S",
        "(λ[])S",
        "(a(:^)*S):^",
        "(:aSS):aSS",
        "((a)(b)~SS)^",
        "()^((x)S)^",
        "(((x)S)^)^",
        "(ok)Sx",
        "((a)(b)*S)^",
        "(a)(b)(c)~SSS",
        "(a)(b)(c)!SS",
        "(a)(b)(c)*SS",
        "(a)(b)(c):SSSS",
        "((a)S)(x)~^S",
        "(x)a^S",
        "((unmatched)^",
        "(())(())~*aS",
    ]
    rng = random.Random(1715)
    for _ in range(32):
        yield "".join(rng.choices(atoms, k=12))


@pytest.mark.parametrize("cap", [0, 1, 2, 9, 48])
def test_bounded_states_and_errors_match_independent_deque(cap):
    for code in corpus():
        assert observe(code, cap) == reference(code, cap), (code, cap)


def test_run_matches_proven_terminal_reference():
    for code in corpus():
        result = reference(code, 48)
        if not result[-2] and result[-1] is None:
            continue
        io = ScriptedIO("unused")
        error = None
        try:
            run(code, io)
        except HaltError as exc:
            error = str(exc)
        assert (io.getvalue(), error) == (result[0], result[-1]), code
        assert io.position() == 0


@pytest.mark.parametrize(
    ("code", "output"),
    [
        ("(Hello, world!)S", "Hello, world!"),
        ("((x))S", "(x)"),
        ("(a)(b)~SS", "ab"),
        ("(a):SS", "aa"),
        ("(a)(b)*S", "ab"),
        ("(a)aS", "(a)"),
        ("(discard)!()S", ""),
        ("((yes)S)^((no)S)^", "yesno"),
        ("(a)(b)(c)~SSS", "bca"),
        ("(a)(b)(c)!SS", "ba"),
        ("(a)(b)(c)*SS", "bca"),
        ("(a)(b)(c):SSSS", "ccba"),
        ("(a(:^)*S):^", "(a(:^)*S):^"),
        ("(:aSS):aSS", "(:aSS):aSS"),
        ("( \n\t )S", " \n\t "),
        ("(λ[])S", "λ[]"),
        ("()^((x)S)^", "x"),
    ],
)
def test_reference_positive_controls(code, output):
    result = reference(code, 48)
    assert result[0] == output
    assert result[-2:] == (True, None)
    assert observe(code, 48) == result
    io = ScriptedIO("unused")
    run(code, io)
    assert io.getvalue() == output
    assert io.position() == 0


def test_growth_control_and_snapshot_distinguish_stack_and_future_program():
    result = reference("(:^):^", 48)
    assert result[-2:] == (False, None)
    assert len(result[1]) > len("(:^):^")
    assert observe("(:^):^", 48) == result
    for left, right in [("(x)", "(y)"), ("(x)(a)", "(x)(b)")]:
        one = _Machine(left, ScriptedIO())
        other = _Machine(right, ScriptedIO())
        one.step()
        other.step()
        assert one.ip == other.ip == 3
        assert one.snapshot() != other.snapshot()


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [None, 1, 3, 7, 8, 13, 40, 80])
def test_every_small_generated_table_in_independent_engine(n, width):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        template = esolangs.generate("Underload", table, width=width)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            code = esolangs.instantiate("Underload", template, bits)
            result = reference(code, 10_000)
            assert result[-2:] == (True, None), (table, row, width)
            assert result[0] == answer, (table, row, width)
            assert observe(code, 10_000) == result, (table, row, width)
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == result[0]
            assert io.position() == 0


def test_valid_seeded_stacks_have_distinct_snapshots_and_execution():
    one = _Machine("S", ScriptedIO())
    other = _Machine("S", ScriptedIO())
    one.state = ("S", 0, ("x",))
    other.state = ("S", 0, ("y",))
    assert one.snapshot() != other.snapshot()
    one.step()
    other.step()
    assert (one.io.getvalue(), other.io.getvalue()) == ("x", "y")
    for stack in [(), ("x",), ("x", "y"), ("x", "y", "z"), ("(a)S",)]:
        for code in ["", "~", ":", "!", "*", "a", "^", "S", "(x)~SS"]:
            for cap in [0, 1, 2, 9]:
                assert observe(code, cap, stack) == reference(code, cap, stack), (
                    code,
                    cap,
                    stack,
                )
