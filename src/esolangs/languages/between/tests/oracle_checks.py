"""Between's operations and examples as a bounded variable-machine model.

https://esolangs.org/wiki/Between. Nested arithmetic, declarations/reset,
line input, conditions, goto and exit; sixteen instructions per trace.
Mixed-type equality follows the explicitly open choice in Decisions.
"""

from itertools import product

import pytest

from esolangs.languages.between.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _argument(value):
    if type(value) is bool:
        return "(True)" if value else "(False)"
    if isinstance(value, int):
        return f"|{value}|"
    if isinstance(value, str):
        return f"'{value}'"
    operation, *args = value
    if operation == "var":
        return "[" + args[0] + "]"
    left, right = map(_argument, args)
    symbol = {"add": "+", "mul": "*", "equal": "="}[operation]
    start, end = ("(", ")") if operation == "equal" else ("|", "|")
    return start + left + symbol + right + end


def _source(program):
    lines = []
    for operation, *args in program:
        if operation == "declare":
            line = _argument(args[0]) + "v."
        elif operation == "assign":
            line = "[" + args[0] + "]s" + _argument(args[1])
        elif operation == "read":
            line = "[" + args[0] + "]i."
        elif operation == "print":
            line = _argument(args[0]) + "p."
        elif operation == "jump":
            line = _argument(args[0]) + "f" + _argument(args[1])
        else:
            line = ".x."
        lines.append(line)
    return "# ignored\n\n" + "\n\n".join(lines)


def _value(value, variables):
    if not isinstance(value, tuple):
        return value
    operation, *args = value
    if operation == "var":
        return variables[args[0]]
    left, right = (_value(a, variables) for a in args)
    if type(left) is not type(right):
        raise ValueError("mixed types")
    if operation == "add":
        return left + right
    if operation == "mul":
        return left * right
    return left == right


def _model(program, stdin):
    variables, trace, output = {}, [], ""
    pc = cursor = progress = 0
    exited = False
    for tick in range(17):
        row = (
            (tuple(sorted(variables.items())), pc, exited),
            exited or pc == len(program),
            output,
            cursor,
            progress,
        )
        trace.append(row)
        if row[1]:
            return None, trace + [row] * 3
        if tick == 16:
            break
        operation, *args = program[pc]
        next_pc = pc + 1
        try:
            if operation == "declare":
                variables[args[0]] = 0
            elif operation == "assign":
                if args[0] not in variables:
                    raise KeyError(args[0])
                variables[args[0]] = _value(args[1], variables)
            elif operation == "print":
                output += str(_value(args[0], variables))
            elif operation == "read":
                if cursor == len(stdin):
                    return "input", [*trace, row]
                end = stdin.find("\n", cursor)
                end = len(stdin) if end < 0 else end + 1
                value = stdin[cursor:end].removesuffix("\n").removesuffix("\r")
                progress += max(1, end - cursor)
                cursor = end
                variables[args[0]] = value
            elif operation == "jump":
                if _value(args[1], variables):
                    next_pc = args[0]
                    if not 0 <= next_pc <= len(program):
                        raise ValueError(next_pc)
            else:
                exited, next_pc = True, pc
        except (KeyError, ValueError):
            return "halt", [*trace, row]
        pc = next_pc
    return None, trace


def _check(factory, program, stdin="unused"):
    def state(machine):
        return tuple(sorted(machine.variables.items())), machine.ind, machine.exited

    assert observed(factory, _source(program), stdin, state, cap=16) == _model(
        program, stdin
    ), (program, stdin)


def check_raw_between():
    x = ("var", "x")
    for left, right, last in product((0, 1, 3, 9), repeat=3):
        for expression in (("add", x, right), ("mul", ("add", x, right), last)):
            _check(
                _Machine,
                (
                    ("declare", "x"),
                    ("assign", "x", left),
                    ("assign", "x", expression),
                    ("print", x),
                ),
            )
        _check(
            _Machine,
            (("declare", "x"), ("assign", "x", left), ("declare", "x"), ("print", x)),
        )
    truth = (
        ("declare", "x"),
        ("read", "x"),
        ("jump", 5, ("equal", x, "1")),
        ("print", 0),
        ("exit",),
        ("print", 1),
        ("jump", 5, True),
    )
    for stdin in ("", "0", "1\n", "1\r\nunused", "λ\nrest", "\n", "11"):
        _check(_Machine, truth, stdin)
    for program in (
        (),
        (("print", x),),
        (("jump", 2, True),),
        (("jump", 1, False),),
        (("jump", 1, ("equal", "1", 1)),),
    ):
        _check(_Machine, program)
    for source in ("'x'p", "|1|s|1|", ".x|1|", "|1|p|1|", "'unterminated"):
        assert observed(_Machine, source, "unused", lambda m: m.ind) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class Skips(_Machine):
        def step(self):
            if not self.halted:
                self.ind += 1

    class ReadsExtra(_Machine):
        def step(self):
            if self.ind == 1:
                self.io.input_char()
            super().step()

    class Repeats(_Machine):
        def __init__(self, code, io):
            write = io.print_str
            io.print_str = lambda text: write(text + "!")
            super().__init__(code, io)

    for factory, program in (
        (Skips, (("declare", "x"),)),
        (ReadsExtra, truth),
        (Repeats, (("print", 1),)),
    ):
        with pytest.raises(AssertionError):
            _check(factory, program, "1\n0\n")
