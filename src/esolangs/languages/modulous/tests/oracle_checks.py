"""Independent Modulous module assembler and bounded stack evaluator.

https://esolangs.org/wiki/Modulous, revision 143648, commands and rules.
Stack, four variables, jumps, reset, strings and token/line input, 48 steps.
Random draws remain in raw tests; backward wrap and bare PRT follow Decisions.
"""

from itertools import product

from esolangs.languages.modulous.interpreter import _Machine
from tests.interpreters.oracle_support import observed, reject_faults
from tests.support.model_input import token_span


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
    assert observed(factory, _source(modules, curly), stdin, _view, cap=48) == _model(
        modules, stdin
    ), (modules, stdin)


def check_raw_modulous():
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
