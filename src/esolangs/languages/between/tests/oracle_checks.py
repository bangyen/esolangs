"""Between's operations and examples as a bounded variable-machine model.

https://esolangs.org/wiki/Between. Nested arithmetic, declarations/reset,
line input, conditions, goto and exit; sixteen instructions per trace.
Mixed-type equality follows the explicitly open choice in Decisions.
"""

from itertools import product
from sys import get_int_max_str_digits

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.between.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import observed
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model(
    "between-v1", "instruction variables exited input_cursor"
)


_SYMBOL = {
    "add": "+",
    "mul": "*",
    "equal": "=",
    "greater": ">",
    "or": "r",
    "not": "n",
    "convert": "c",
}
_CONDITION = {"equal", "greater", "or", "not"}


def _expression(value):
    operation, *args = value
    return (
        _argument(args[0])
        + _SYMBOL[operation]
        + _argument(args[1] if len(args) == 2 else None)
    )


def _argument(value):
    if value is None:
        return "."
    if type(value) is bool:
        return "(True)" if value else "(False)"
    if isinstance(value, int):
        return f"|{value}|"
    if isinstance(value, str):
        return f"'{value}'"
    if value[0] == "var":
        return "[" + value[1] + "]"
    kind, expr = (
        (value[1], value[2])
        if value[0] == "group"
        else ("cond" if value[0] in _CONDITION else "int", value)
    )
    start, end = ("(", ")") if kind == "cond" else ("|", "|")
    return start + _expression(expr) + end


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
        elif operation == "pure":
            line = _expression(args[0])
        else:
            line = ".x."
        lines.append(line)
    return "# ignored\n\n" + "\n\n".join(lines)


class _HostLimitError(ValueError):
    pass


def _text(value):
    if (
        type(value) is int
        and (limit := get_int_max_str_digits())
        and abs(value) >= 10**limit
    ):
        raise _HostLimitError
    return str(value)


def _pure(value, variables):
    operation, *args = value
    left, right = [_value(a, variables) for a in (*args, None)[:2]]
    if operation in ("add", "equal"):
        if type(left) not in (int, str) or type(left) is not type(right):
            raise ValueError
        return left + right if operation == "add" else left == right
    if operation in ("mul", "greater"):
        if type(left) is not int or type(right) is not int:
            raise ValueError
        return left * right if operation == "mul" else left > right
    if operation == "convert":
        if type(left) is int:
            return _text(left)
        if type(left) is str and left and all(c in "0123456789" for c in left):
            if (limit := get_int_max_str_digits()) and len(left) > limit:
                raise _HostLimitError
            return int(left)
        raise ValueError
    if type(left) is not bool or (operation == "or" and type(right) is not bool):
        raise ValueError
    return not left if operation == "not" else left or right


def _value(value, variables):
    if not isinstance(value, tuple):
        return value
    if value[0] == "var":
        return variables[value[1]]
    kind, expr = (
        (value[1], value[2])
        if value[0] == "group"
        else ("cond" if value[0] in _CONDITION else "int", value)
    )
    result = _pure(expr, variables)
    if type(result) is not (bool if kind == "cond" else int):
        raise ValueError
    return result


def _model(program, stdin, cap=16):
    if any(
        (op == "pure" and args[0][0] not in ("convert", "not") and args[0][-1] is None)
        or (op == "assign" and args[1] is None)
        for op, *args in program
    ):
        return "syntax", [(None, False, "", 0, 0)]
    variables, trace, output = {}, [], ""
    pc = cursor = progress = 0
    exited = False
    for tick in range(cap + 1):
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
        if tick == cap:
            break
        operation, *args = program[pc]
        next_pc = pc + 1
        try:
            if operation == "declare":
                name = _value(args[0], variables)
                if type(name) is not str:
                    raise ValueError
                variables[name] = 0
            elif operation == "assign":
                value = _value(args[1], variables)
                if type(value) not in (str, int) or args[0] not in variables:
                    raise ValueError
                variables[args[0]] = value
            elif operation == "print":
                value = _value(args[0], variables)
                if type(value) not in (str, int):
                    raise ValueError
                output += _text(value)
            elif operation == "read":
                if cursor == len(stdin):
                    raise EOFError
                end = stdin.find("\n", cursor)
                end = len(stdin) if end < 0 else end + 1
                value = stdin[cursor:end].removesuffix("\n").removesuffix("\r")
                progress += max(1, end - cursor)
                cursor = end
                if args[0] not in variables:
                    raise KeyError
                variables[args[0]] = value
            elif operation == "jump":
                target = _value(args[0], variables)
                if type(target) is not int:
                    raise ValueError
                if args[1] is None or _value(args[1], variables) is True:
                    next_pc = target
                    if not 0 <= next_pc <= len(program):
                        raise ValueError(next_pc)
            elif operation == "pure":
                _pure(args[0], variables)
            else:
                exited, next_pc = True, pc
        except (KeyError, ValueError, EOFError) as error:
            failed = (
                (tuple(sorted(variables.items())), pc, exited),
                False,
                output,
                cursor,
                progress,
            )
            return "syntax" if isinstance(
                error, _HostLimitError
            ) else "input" if isinstance(error, EOFError) else "halt", [*trace, failed]
        pc = next_pc
    return None, trace


def _parts(row):
    return row[0][1], frozenset(row[0][0]), row[0][2], row[-1]


def _check(factory, program, stdin="unused", cap=16):
    expected = _model(program, stdin, cap)

    def state(machine):
        return tuple(sorted(machine.variables.items())), machine.ind, machine.exited

    checked = workspace.workspace_view(
        expected[1],
        _WORKSPACE,
        _parts,
        state,
    )
    assert observed(factory, _source(program), stdin, checked, cap=cap) == expected, (
        program,
        stdin,
    )
    return expected


def corpus():
    x = ("var", "x")
    for left, right, last in product((0, 1, 3, 9), repeat=3):
        for expression in (("add", x, right), ("mul", ("add", x, right), last)):
            yield (
                (
                    ("declare", "x"),
                    ("assign", "x", left),
                    ("assign", "x", expression),
                    ("print", x),
                ),
                "unused",
                16,
            )
        yield (
            (("declare", "x"), ("assign", "x", left), ("declare", "x"), ("print", x)),
            "unused",
            16,
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
        yield truth, stdin, 16
    for program in (
        (),
        (("print", x),),
        (("jump", 2, True),),
        (("jump", 1, False),),
        (("jump", 1, ("equal", "1", 1)),),
    ):
        yield program, "unused", 16
    for left, right in product((0, 1, "0", "", True, False, None), repeat=2):
        for operation in _SYMBOL:
            expr = (
                (operation, left)
                if operation in ("not", "convert")
                else (operation, left, right)
            )
            yield (("pure", expr),), "unused", 16
            yield (("print", expr),), "unused", 16
    for target, cond in product(
        (0, 1, 9, "0", True, None, ("var", "missing")), (True, False, 1, "1", None)
    ):
        yield (("jump", target, cond),), "unused", 16
    for name, stdin in product(
        ("x", "long_name", "λ"), ("", "A\nB", "A\r\nB", "A\rB", "A\u2028B", "\n", "\r")
    ):
        yield (
            (
                ("declare", name),
                ("read", name),
                ("print", ("var", name)),
                ("read", name),
                ("read", name),
            ),
            stdin,
            16,
        )
        yield (("read", name),), stdin, 16
    for name in (0, True, None, ("var", "missing")):
        yield (("declare", name),), "", 16
    for value in (0, 1, "text", True, None):
        yield (
            (
                ("declare", "x"),
                ("assign", "x", value),
                ("assign", "x", value),
                ("declare", "x"),
            ),
            "",
            16,
        )
    for program in (
        (),
        (("exit",),),
        (("pure", ("add", 1, 2)),),
        (("print", ("group", "int", ("equal", 1, 1))),),
        (("print", ("group", "cond", ("add", 1, 1))),),
    ):
        yield program, "", 16

    if limit := get_int_max_str_digits():
        for digits in ("9" * (limit + 1), "0" * (limit + 1), "0" * (limit - 1) + "1"):
            yield (("print", "prefix"), ("pure", ("convert", digits))), "", 16

        x = ("var", "x")
        prefix = (("declare", "x"), ("assign", "x", 10 ** (limit // 4))) + (
            ("assign", "x", ("mul", x, x)),
        ) * 3
        for final in (("print", x), ("pure", ("convert", x))):
            yield (*prefix, final), "", 16


def syntax_cases():
    return ("'x'p", "|1|s|1|", ".x|1|", "|1|p|1|", "'unterminated")


def check_raw_between():
    for case in corpus():
        _check(_Machine, *case)
    truth = (
        ("declare", "x"),
        ("read", "x"),
        ("jump", 5, ("equal", ("var", "x"), "1")),
        ("print", 0),
        ("exit",),
        ("print", 1),
        ("jump", 5, True),
    )
    for source in syntax_cases():
        assert observed(_Machine, source, "unused", lambda m: m.ind) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    for program, stdin, bits in (
        ((), "", 0),
        ((("exit",),), "", 1),
        ((("declare", "x"),), "", 10),
        ((("declare", "long_name"),), "", 74),
        (
            (
                ("declare", "x"),
                ("assign", "x", 1),
                ("assign", "x", 1),
                ("declare", "x"),
            ),
            "",
            12,
        ),
        ((("declare", "x"), ("read", "x")), "A\r\n", 20),
    ):
        rows = _check(_Machine, program, stdin)[1]
        assert workspace.charged_bits(_WORKSPACE, map(_parts, rows)) == bits

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

    class WrongText(_Machine):
        def __init__(self, code, io):
            write = io.print_str
            io.print_str = lambda text: write(text.translate(str.maketrans("01", "10")))
            super().__init__(code, io)

    for factory, program in (
        (Skips, (("declare", "x"),)),
        (ReadsExtra, truth),
        (Repeats, (("print", 1),)),
        (WrongText, (("print", 1),)),
    ):
        with pytest.raises(AssertionError):
            _check(factory, program, "1\n0\n")
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _check(
                workspace.missing_workspace(_Machine, component),
                (("declare", "x"), ("assign", "x", 3)),
            )

    class BeforeRead(_Machine):
        def step(self):
            if (
                not self.halted
                and self.code[self.ind][0] == "i"
                and "missing" not in self.variables
            ):
                raise HaltError
            super().step()

    class TruthyJump(_Machine):
        def step(self):
            before = self.ind
            super().step()
            if before == 0:
                self.ind = 2

    for factory, program in (
        (BeforeRead, (("read", "missing"),)),
        (TruthyJump, (("jump", 2, 1), ("print", 1), ("exit",))),
    ):
        with pytest.raises(AssertionError):
            _check(factory, program, "line\n")
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _check(
                workspace.missing_workspace(_Machine, component),
                (("declare", "x"), ("read", "x"), ("exit",)),
                "line\n",
            )
    machine = _Machine(_source((("declare", "x"), ("read", "x"))), ScriptedIO(""))
    witness = workspace.WorkspaceWitness(_WORKSPACE)
    witness.sample(machine.workspace_snapshot(), (0, frozenset(), False, 0))
    machine.step()
    for attempt in range(1, 4):
        with pytest.raises(EOFError):
            machine.step()
        witness.sample(
            machine.workspace_snapshot(), (1, frozenset({("x", 0)}), False, 0)
        )
        assert machine.ind == 1
        assert not machine.exited
        assert machine.io.position() == machine.io.progress() == 0
        assert machine.io.reads == 0
        assert machine.io.past_end == attempt
