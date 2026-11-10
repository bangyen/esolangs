"""Independent Modulous module assembler and bounded stack evaluator.

https://esolangs.org/wiki/Modulous, revision 143648, commands and rules.
Stack, four variables, jumps, reset, strings and token/line input, 48 steps.
A separate bounded-draw witness populates the random counter; backward wrap
and bare PRT follow Decisions.
"""

from itertools import product

import pytest

from esolangs.languages.modulous.interpreter import _Machine
from tests.interpreters.oracle_support import observed, reject_faults
from tests.support import workspace_oracle as workspace
from tests.support.model_input import token_span

_WORKSPACE = workspace.workspace_model(
    "modulous-v1", "instruction stack variables input_cursor stopped input_reads draws"
)


def _source(modules, curly):
    tokens = []
    for module in modules:
        if module[:2] == ("PSH", "STR"):
            left, right = ("“", "”") if curly else ('"', '"')
            tokens.append("PSH STR " + left + module[2] + right)
        else:
            tokens.append(" ".join(module))
    return "\n".join("[" + token + "]" for token in tokens)


def _read(mode, stdin, cursor):
    if mode == "INT":
        start, cursor = token_span(stdin, cursor)
        return stdin[start:cursor], cursor, start == cursor
    if cursor == len(stdin):
        return "", cursor, True
    end = stdin.find("\n", cursor)
    stop = len(stdin) if end < 0 else end + 1
    return stdin[cursor:stop].removesuffix("\n").removesuffix("\r"), stop, False


def _push(args, stack, variables):
    if args[0] == "INT":
        stack.append(int(args[1]))
    elif args[0] == "STR":
        stack.extend(ord(c) for c in args[1][::-1])
    else:
        variables[args[0]]  # Refuse stores to a fifth variable.
        variables[args[0]] = stack[-1]


def _primitive(command, args, stack, variables):
    if command == "PSH":
        _push(args, stack, variables)
    elif command == "POP":
        stack.pop()
    elif command == "SWP":
        stack[-1], stack[-2] = stack[-2], stack[-1]
    elif command == "DUP":
        stack.append(stack[-1])
    elif command in ("ADD", "SUB"):
        stack[-1] += int(args[0]) * (1 if command == "ADD" else -1)
    elif command.startswith("VAR"):
        name, delta = command.split("+", 1) if "+" in command else command.split("-", 1)
        variables[name] += int(delta) * (1 if "+" in command else -1)
    elif command:
        raise ValueError("command")


def _jump(args, stack, pc):
    condition = True
    if len(args) > 2:
        equal = (stack[-1] if stack else 0) == int(args[-1])
        condition = equal if args[2] == "IF" else not equal
    if condition:
        return pc + int(args[1]) * (1 if args[0] == "F" else -1)
    return pc + 1


def _print(args, stack, variables):
    value = variables[args[0]] if args and args[0].startswith("VAR") else stack[-1]
    text = str(value) if "INT" in args else chr(value)
    if not args or not args[0].startswith("VAR"):
        stack.pop()
    return text


def _model(modules, stdin):
    pc = cursor = reads = 0
    stack, variables, done, output, trace = (
        [],
        dict.fromkeys(("VAR1", "VAR2", "VAR3", "VAR4"), 0),
        False,
        "",
        [],
    )

    def row():
        state = (pc, tuple(stack), tuple(sorted(variables.items())), done, reads, 0)
        return state, done or pc >= len(modules), output, cursor, cursor

    for tick in range(49):
        trace.append(row())
        if done or pc >= len(modules):
            return None, trace + [row()] * 3
        if tick == 48:
            break
        index = pc % len(modules) if pc < 0 else pc
        module = modules[index]
        command, args = (module[0], module[1:]) if module else ("", ())
        changed, assigned, next_pc, text = list(stack), dict(variables), index + 1, ""
        try:
            if command == "INP":
                value, cursor, exhausted = _read(args[0], stdin, cursor)
                if exhausted:
                    return "input", [*trace, row()]
                reads += 1
                changed.extend(
                    [int(value)] if args[0] == "INT" else map(ord, value[::-1])
                )
            elif command == "PRT":
                text = _print(args, changed, assigned)
            elif command == "JMP":
                next_pc = _jump(args, changed, index)
            elif command == "RST":
                next_pc = 0
            elif command == "END":
                done = True
            else:
                _primitive(command, args, changed, assigned)
        except (IndexError, KeyError):
            return "halt", [*trace, row()]
        except ValueError:
            return "syntax", [*trace, row()]
        stack, variables, pc = changed, assigned, next_pc
        output += text
    return None, trace


def _view(machine):
    return (
        machine.ind,
        machine.stk,
        tuple(sorted(machine.var.items())),
        machine._halted,
        machine._input_reads,
        machine._draws,
    )


def _check(factory, modules, stdin="unused", *, curly=False):
    workspace.agrees(
        _model(modules, stdin),
        (factory, _source(modules, curly), stdin),
        (
            _WORKSPACE,
            lambda row: (*row[0][:2], frozenset(row[0][2]), row[-1], *row[0][3:]),
        ),
        _view,
        cap=48,
        context=(modules, stdin),
    )


def _draw_model(modules, choice):
    """Model bounded draws and integer prints without the production dispatcher."""
    pc = draws = 0
    stack, output, stopped, trace = [], "", False, []

    def row():
        state = (
            pc,
            tuple(stack),
            tuple((f"VAR{i}", 0) for i in range(1, 5)),
            stopped,
            0,
            draws,
        )
        return state, stopped or pc >= len(modules), output, 0, 0

    for tick in range(49):
        trace.append(row())
        if stopped or pc >= len(modules):
            return None, trace + [row()] * 3
        if tick == 48:
            break
        command, *args = modules[pc]
        if command == "RND":
            bound = int(args[0])
            assert bound > 0
            stack.append(choice % bound)
            draws += 1
        elif command == "PRT":
            assert args == ["INT"]
            output += str(stack.pop())
        else:
            assert command == "END"
            stopped = True
        pc += 1
    return None, trace


def _check_draws(factory, choice):
    modules = (("RND", "3"), ("RND", "5"), ("PRT", "INT"), ("END",))

    class Draw:
        def randbelow(self, upper):
            return choice % upper

    def build(code, io):
        return factory(code, io, Draw())

    expected = _draw_model(modules, choice)
    assert expected[1][-1][0][-1] == 2
    assert expected[1][-1][2] == str(choice % 5)
    workspace.agrees(
        expected,
        (build, _source(modules, curly=False), ""),
        (
            _WORKSPACE,
            lambda row: (*row[0][:2], frozenset(row[0][2]), row[-1], *row[0][3:]),
        ),
        _view,
        cap=48,
        context=(modules, choice),
    )


def _check_populated_draws():
    for choice in (0, 4):
        _check_draws(_Machine, choice)
    for factory in (
        workspace.missing_workspace(_Machine, "draws"),
        workspace.missing_workspace(_Machine, "stack"),
    ):
        with pytest.raises(AssertionError):
            _check_draws(factory, 4)


def check_raw_modulous():
    _check_populated_draws()
    for value, delta, command in product(
        (-3, 0, 1, 65, 256), (-2, 0, 5), ("ADD", "SUB")
    ):
        _check(
            _Machine,
            (
                ("PSH", "INT", str(value)),
                (command, str(delta)),
                ("DUP",),
                ("PRT", "INT"),
                ("PRT", "STR"),
            ),
        )
    primitives = (
        ("POP",),
        ("SWP",),
        ("DUP",),
        ("PSH", "VAR1"),
        ("PSH", "VAR5"),
        ("PRT", "INT"),
        ("PRT",),
        ("VAR1+5",),
        ("VAR4-2",),
        ("VAR5+1",),
        (),
        ("WHAT",),
    )
    for count, operation in product(range(3), primitives):
        _check(
            _Machine,
            (*(("PSH", "INT", str(i + 1)) for i in range(count)), operation, ("END",)),
        )
    for direction, distance, condition in product(
        ("F", "B"), (0, 1, 2, 20), ((), ("IF", "0"), ("IF", "1"), ("NIF", "0"))
    ):
        _check(
            _Machine,
            (
                ("JMP", direction, str(distance), *condition),
                ("PSH", "INT", "1"),
                ("PRT", "INT"),
                ("END",),
            ),
        )
    for text, curly in product(("", "Hello", "λ\n", "][END]["), (False, True)):
        _check(
            _Machine,
            (("PSH", "STR", text), ("PRT", "STR"), ("JMP", "B", "1", "NIF", "0")),
            curly=curly,
        )
    for mode, stdin in product(
        ("INT", "STR"), ("", "\n", "1 2\nZ", "-3\r\nA", "λ", "1_0", "٣", "invalid")
    ):
        _check(
            _Machine,
            (("INP", mode), ("PRT", "INT"), ("INP", "STR"), ("PRT", "STR")),
            stdin,
        )
    for modules in (
        (),
        (("RST",),),
        (("PSH", "INT", "1"), ("RST",)),
        (
            ("PSH", "INT", "7"),
            ("PSH", "VAR4"),
            ("POP",),
            ("VAR4+9",),
            ("PRT", "VAR4", "INT"),
        ),
        (("PSH", "INT", "bad"),),
    ):
        _check(_Machine, modules)
    for source in (
        "[",
        "[END",
        "text[END]",
        '[PSH STR "unterminated]',
        "[PSH INT 1[END]",
    ):
        assert observed(_Machine, source, "", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class WrongSum(_Machine):
        def step(self):
            super().step()
            if self.stk:
                self.stk = (*self.stk[:-1], self.stk[-1] + 1)

    reject_faults(
        _check, _Machine, WrongSum, (("PSH", "INT", "2"), ("ADD", "3"), ("PRT", "INT"))
    )

    workspace.check_erasures(
        _WORKSPACE,
        lambda f: _check(f, (("INP", "INT"), ("PSH", "VAR1"), ("END",)), "2"),
        _Machine,
    )
