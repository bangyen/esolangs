"""Independent single-row Fish stack evaluator, capped at 48 cells executed.

https://esolangs.org/wiki/Fish, stacks, registers and instruction tables.
Arithmetic, scopes, strings, IO, reads, skips and toroidal wrap; movement,
random turns and code writes remain in the raw grid regression suite.
"""

from itertools import product
from operator import add, eq, gt, lt, mod, mul, sub, truediv

from esolangs.languages.fish.interpreter import _Machine
from tests.interpreters.oracle_support import observed, reject_faults


def _whole(value):
    if int(value) != value:
        raise ValueError("integer operand")
    return int(value)


def _shuffle(command, top):
    if command == ":":
        top.append(top[-1])
    elif command == "~":
        top.pop()
    elif command == "$":
        top[-2], top[-1] = top[-1], top[-2]
    elif command == "@":
        a, b, c = top[-3:]
        top[-3:] = [c, a, b]
    elif command in "{}":
        if command == "}":
            top.insert(0, top.pop())
        else:
            top.append(top.pop(0))
    elif command == "r":
        top.reverse()
    elif command == "l":
        top.append(len(top))


def _scope(command, scopes, slots, top):
    if command == "[":
        count = _whole(top.pop())
        if count < 0 or count > len(top):
            raise ValueError("split bounds")
        split = len(top) - count
        scopes[-1] = tuple(top[:split])
        scopes.append(())
        slots.append(None)
        top = top[split:]
    elif command == "]":
        if len(scopes) == 1:
            top, slots = [], [None]
        else:
            scopes.pop()
            slots.pop()
            top = [*scopes[-1], *top]
    elif command == "&":
        if slots[-1] is None:
            slots[-1] = top.pop()
        else:
            top.append(slots[-1])
            slots[-1] = None
    return scopes, slots, top


def _string(quote, command, top):
    if command == quote:
        return None
    top.append(ord(command))
    return quote


def _calculate(operation, left, right):
    result = operation(left, right)
    return int(result) if type(result) is bool else result


def _format(command, value):
    if command == "o":
        return chr(_whole(value))
    return str(int(value) if int(value) == value else value)


def _model(source, stdin):
    if not source:
        return "syntax", [(None, False, "", 0, 0)]
    operators = dict(
        zip("+-*,%=()", (add, sub, mul, truediv, mod, eq, lt, gt), strict=True)
    )
    pc = cursor = 0
    stacks, registers = [()], [None]
    quote, done, output, trace = None, False, "", []
    cells = tuple(((i, 0), ord(c)) for i, c in enumerate(source))

    def row():
        state = (
            pc,
            0,
            1,
            0,
            cells,
            tuple(stacks),
            tuple(registers),
            quote,
            len(source),
            1,
        )
        return state, done, output, cursor, cursor

    for tick in range(49):
        trace.append(row())
        if done:
            return None, trace + [row()] * 3
        if tick == 48:
            break
        command, top = source[pc], list(stacks[-1])
        scopes, slots = list(stacks), list(registers)
        text, next_quote, distance = "", quote, 1
        try:
            if quote is not None:
                next_quote = _string(quote, command, top)
            elif command in "0123456789abcdef":
                top.append(int(command, 16))
            elif command in operators:
                right, left = top.pop(), top.pop()
                top.append(_calculate(operators[command], left, right))
            elif command in "'\"":
                next_quote = command
            elif command in ":~$@{}rl":
                _shuffle(command, top)
            elif command in "[]&":
                scopes, slots, top = _scope(command, scopes, slots, top)
            elif command == "i":
                top.append(ord(stdin[cursor]) if cursor < len(stdin) else -1)
                cursor = min(cursor + 1, len(stdin))
            elif command in "on":
                text = _format(command, top.pop())
            elif command == "g":
                y, x = _whole(top.pop()), _whole(top.pop())
                top.append(ord(source[x]) if y == 0 and 0 <= x < len(source) else 0)
            elif command == "!":
                distance = 2
            elif command == "?":
                distance = 2 if top.pop() == 0 else 1
            elif command == ";":
                done = True
                continue
            elif command not in " \0":
                assert command not in "><^v/\\|_#x.p", "outside linear model"
                raise ValueError("instruction")
        except (IndexError, ValueError, ZeroDivisionError):
            return "halt", [*trace, row()]
        scopes[-1] = tuple(top)
        stacks, registers, quote = scopes, slots, next_quote
        pc = (pc + distance) % len(source)
        output += text
    return None, trace


def _view(machine):
    return (
        machine.x,
        machine.y,
        machine.dx,
        machine.dy,
        tuple(sorted(machine.cells.items())),
        tuple(tuple(s) for s in machine.stacks),
        tuple(machine.registers),
        machine.quote,
        machine.width,
        machine.height,
    )


def _check(factory, source, stdin="unused"):
    assert observed(factory, [source], stdin, _view, cap=48) == _model(source, stdin), (
        source,
        stdin,
    )


def check_raw_fish():
    for left, right, op in product("014af7b", "012f7b", "+-*,%=()"):
        _check(_Machine, left + right + op + "n;")
    for prefix, op in product(
        ("", "1", "12", "123", "1234"),
        (":", "~", "$", "@", "}", "{", "r", "l", "[", "]", "&", "o", "n", "g"),
    ):
        _check(_Machine, prefix + op + "l;")
    for count, suffix in product("01234", ("r]nnn;", "&l]&nnn;", "0[1&]l]l;")):
        _check(_Machine, "123" + count + "[" + suffix)
    for source in (
        "12345 3[r]rnnnnn;",
        "1&2&nn;",
        "1&0[2&]&&n;",
        "1&]l&;",
        "12,3*n;",
        "13,on;",
        "01-o;",
        "00gno;",
        "01-0gn;",
        "ffgn;",
        "00gn;",
        "0?9n;",
        "1?9n;",
        "!9;",
        "0?",
        "123",
        "'ab'oo;",
        '"λ \'"ooo;',
        "'';",
        "'",
        "\0;",
        "\t;",
        "z",
        "",
        "00[",
        "01-[;",
        "12,[;",
        "12@;",
        "12,o;",
        "1r{n;",
    ):
        _check(_Machine, source)
    for source, stdin in product(
        ("iin;", "ion;", "i!0in;", "'i'niin;"), ("", "A", "λ\n", "\0Z", "abc")
    ):
        _check(_Machine, source, stdin)

    class WrongSum(_Machine):
        def step(self):
            c = self.cells.get((self.x, self.y))
            super().step()
            if c == ord("+"):
                state = list(self.state)
                state[5] = ((*state[5][-1][:-1], state[5][-1][-1] + 1),)
                self.state = tuple(state)

    reject_faults(_check, _Machine, WrongSum, "12+n;")
