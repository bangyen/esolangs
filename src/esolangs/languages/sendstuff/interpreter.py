"""Interpreter for SendStuff.

A program is a graph of nodes, each a command and a constant parameter.
A node that receives a number runs its command and sends every result, in
order, to every target, in order; a send runs to completion before the
next (Zzo38 on the talk page: ``>start(>(Add 1 >start) >(Add 2 >start))``
never reaches ``Add 2``).  The root sends 0 to the top level's ``>``
items.  ``>`` makes a child the parent's target, ``<`` the parent the
child's, ``|`` neither; ``>name``/``<name`` add the same edge to a node
already named.  A node's ``<`` targets come before its ``>`` ones, each
in source order.  The only branch is a command sending nothing: Subtract
below 0, a zero divisor, Input at EOF.

Input/output:
    Input reads a character and InputNumber a whitespace-separated decimal;
    at EOF either sends nothing and never raises.  Output prints the
    character with that code; OutputNumber prints decimal with no separator.

Errors:
    ProgramError: A malformed program: an unknown command (names are exact:
        the talk page's ``Sub`` is refused, as Zzo38 said), a bad or
        duplicate node or macro, a macro with no closing ``)``, a reference
        to a node not yet opened.
    ArgumentError: An InputNumber token that is not an integer.
    HaltError: Output of a code above 1114111; a negative InputNumber.

Decisions:
    * Interleave puts the parameter's bits in the odd places and the
      received number's in the even ones; LeftHalf returns the odd-place
      bits and RightHalf the even, so they undo Interleave.
    * A command and its parameter are separated by whitespace (the Extended
      section exempts only ``/`` commands); a command takes a parameter even
      where it ignores it.
    * A reference names a node already opened, so a node may target itself.
    * A macro parameter is ``:...;`` or a run of characters other than
      whitespace, parentheses and ``!``; it may be empty.  The wiki's rule
      that a macro node named without ``$`` uses no ``$`` or ``%`` inside it
      is enforced.  Definitions are hoisted, so a macro may be invoked
      before it is defined.  ``$`` becomes ``$k`` for the invocation's
      number ``k``, so it cannot meet a user name.  The wiki treats a
      parameter as one word, so generated calls space each ``!`` (a
      clean-room reading took ``o1!z`` as one parameter, 2026-10-30).
    * A finished node's frame is dropped before its last send, so a loop
      through one chain of single sends revisits a state and is a cycle.
    * The extended language (``/`` commands, ``{}`` node sets, fragments,
      strings) is a separate version and is not implemented.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

_MAX_CHAR = 0x10FFFF
_COMMANDS = frozenset(
    [
        "Input",
        "Output",
        "InputNumber",
        "OutputNumber",
        "Constant",
        "Add",
        "Subtract",
        "Multiply",
        "Divide",
        "DivideBy",
        "Modulo",
        "ModuloBy",
        "CountUp",
        "CountDown",
        "Interleave",
        "LeftHalf",
        "RightHalf",
    ]
)
_READS = frozenset({"Input", "InputNumber"})
_NAME = re.compile(r"[A-Za-z0-9_.$]*")
_WORD = re.compile(r"[A-Za-z0-9_]+")
#: Whitespace separates the parameter; ``Add72`` is no command.
_PARAM = re.compile(r"\s+([0-9]+)")
_MACRO_NAME = re.compile(r"[A-Za-z0-9_.$%]+")
_DEFINITION = re.compile(r"[A-Za-z0-9_.]*")
#: A named node in a macro body; without ``$`` it is the same node each time.
_FIXED = re.compile(r"[|<>]([A-Za-z0-9_.$%]+)\s*\(")
_ARG = re.compile(r"[^\s()!]*")


def _strip_comments(code: str) -> str:
    return re.sub(r"#[^\n]*", "", code)


def _balanced(text: str, start: int, what: str) -> int:
    """Return the index just past the ``)`` matching the ``(`` at ``start``."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    raise ValueError(f"SendStuff {what} has no closing ')'")


def _hoist_macros(code: str) -> tuple[str, dict[str, str]]:
    """Return the code without its ``@name(...)`` definitions, and the bodies."""
    macros: dict[str, str] = {}
    kept: list[str] = []
    pos = 0
    while (at := code.find("@", pos)) >= 0:
        kept.append(code[pos:at])
        name = _DEFINITION.match(code, at + 1)
        assert name is not None
        open_at = _skip_space(code, name.end())
        if not name.group() or open_at >= len(code) or code[open_at] != "(":
            raise ValueError(f"SendStuff macro definition at {at} needs @name(...)")
        end = _balanced(code, open_at, f"macro {name.group()!r}")
        body = code[open_at + 1 : end - 1]
        if "@" in body:
            raise ValueError(
                f"SendStuff macro {name.group()!r} contains a macro definition"
            )
        for fixed in _FIXED.finditer(body):
            if "$" in fixed.group(1):
                continue
            try:
                inside = body[fixed.end() : _balanced(body, fixed.end() - 1, "node")]
            except ValueError:
                inside = body[fixed.end() :]
            if "$" in inside or "%" in inside:
                raise ValueError(
                    f"SendStuff macro {name.group()!r} node {fixed.group(1)!r} has "
                    "no '$' in its name, so nothing inside it may use $ or %"
                )
        if name.group() in macros:
            raise ValueError(f"SendStuff macro {name.group()!r} is defined twice")
        macros[name.group()] = body
        kept.append(" ")
        pos = end
    kept.append(code[pos:])
    return "".join(kept), macros


class _Expander:
    """Replace each ``!name param`` by the macro's body, ``$`` and ``%`` filled."""

    def __init__(self, macros: dict[str, str]) -> None:
        self.macros = macros
        self.count = 0

    def expand(self, text: str, active: tuple[str, ...] = ()) -> str:
        out: list[str] = []
        pos = 0
        while (bang := text.find("!", pos)) >= 0:
            out.append(text[pos:bang])
            name = _MACRO_NAME.match(text, bang + 1)
            if name is None:
                raise ValueError(f"SendStuff macro call at {bang} has no name")
            arg_at = _skip_space(text, name.end())
            if text.startswith(":", arg_at):
                end = text.find(";", arg_at)
                if end < 0:
                    raise ValueError(
                        f"SendStuff macro parameter at {arg_at} has no ';'"
                    )
                arg, pos = text[arg_at + 1 : end], end + 1
            else:
                match = _ARG.match(text, arg_at)
                assert match is not None
                arg, pos = match.group(), match.end()
            macro = name.group()
            if macro not in self.macros:
                raise ValueError(f"SendStuff macro {macro!r} is not defined")
            if macro in active:
                raise ValueError(f"SendStuff macro {macro!r} invokes itself")
            self.count += 1
            body = self.macros[macro]
            body = body.replace("$", f"\0{self.count}").replace("%", arg)
            out.append(self.expand(body.replace("\0", "$"), (*active, macro)))
        out.append(text[pos:])
        return "".join(out)


class _Program(NamedTuple):
    """Each node's command, parameter and targets; node 0 is the root."""

    commands: tuple[str, ...]
    params: tuple[int, ...]
    targets: tuple[tuple[int, ...], ...]


def _skip_space(code: str, pos: int) -> int:
    while pos < len(code) and code[pos].isspace():
        pos += 1
    return pos


def _command(code: str, pos: int) -> tuple[str, int, int]:
    """Read a node's command and parameter after its ``(``; return the end too."""
    pos = _skip_space(code, pos)
    word = _WORD.match(code, pos)
    if word is None or word.group() not in _COMMANDS:
        got = word.group() if word else code[pos : pos + 1]
        raise ValueError(f"SendStuff has no command {got!r}")
    param = _PARAM.match(code, word.end())
    if param is None:
        return word.group(), 0, word.end()
    return word.group(), int(param.group(1)), param.end()


def _parse(code: str) -> _Program:
    code, macros = _hoist_macros(_strip_comments(code))
    for sigil in "$%":
        if sigil in code:
            raise ValueError(f"SendStuff {sigil!r} appears outside a macro")
    code = _Expander(macros).expand(code)
    commands, params = ["root"], [0]
    sends_up: list[list[int]] = [[]]
    sends_down: list[list[int]] = [[]]
    names: dict[str, int] = {}
    open_nodes = [0]
    pos = 0
    while True:
        pos = _skip_space(code, pos)
        if pos >= len(code):
            break  # closing parentheses at the end may be left off
        kind = code[pos]
        if kind == ")":
            if len(open_nodes) == 1:
                raise ValueError(f"SendStuff ')' at {pos} closes no node")
            open_nodes.pop()
            pos += 1
            continue
        if kind not in "|<>":
            raise ValueError(f"SendStuff expects a node type '|', '<' or '>' at {pos}")
        parent = open_nodes[-1]
        if parent == 0 and kind == "<":
            raise ValueError(f"SendStuff '<' at {pos} sends to the root")
        match = _NAME.match(code, pos + 1)
        assert match is not None
        name, pos = match.group(), _skip_space(code, match.end())
        if pos < len(code) and code[pos] == "(":
            if name in names:
                raise ValueError(f"SendStuff node {name!r} is defined twice")
            node = len(commands)
            if name:
                names[name] = node
            command, param, pos = _command(code, pos + 1)
            commands.append(command)
            params.append(param)
            sends_up.append([])
            sends_down.append([])
            open_nodes.append(node)
        elif not name:
            raise ValueError(f"SendStuff node at {pos} has neither name nor '('")
        elif name not in names:
            raise ValueError(f"SendStuff node {name!r} is not defined yet")
        else:
            node = names[name]
        if kind == ">":
            sends_down[parent].append(node)
        elif kind == "<":
            sends_up[node].append(parent)
    targets = tuple(tuple(u + d) for u, d in zip(sends_up, sends_down, strict=True))
    return _Program(tuple(commands), tuple(params), targets)


def _interleave(high: int, low: int) -> int:
    out = bit = 0
    while high or low:
        out |= (low & 1) << bit | (high & 1) << (bit + 1)
        high, low, bit = high >> 1, low >> 1, bit + 2
    return out


def _half(value: int, shift: int) -> int:
    value >>= shift
    out = bit = 0
    while value:
        out |= (value & 1) << bit
        value, bit = value >> 2, bit + 1
    return out


#: The results a node is sending, as ``first + step * k`` for ``k < count``.
type _Results = tuple[int, int, int]
#: ``(node, results, k, j)``: the node is sending result ``k`` to target ``j``.
type _Frame = tuple[int, _Results, int, int]
#: The sending nodes, innermost first, as a linked list.
type _State = tuple[_Frame, _State] | None


def _receive(command: str, param: int, value: int, got: int | None) -> _Results:
    """Return what a node sends on receiving ``value``; ``got`` is its read."""
    if command in _READS:
        return (0, 0, 0) if got is None else (got, 0, 1)
    if command == "CountUp":
        return (0, 1, value + 1)
    if command == "CountDown":
        return (value, -1, value + 1)
    result: int | None
    if command == "Constant":
        result = param
    elif command == "Add":
        result = value + param
    elif command == "Subtract":
        result = value - param if value >= param else None
    elif command == "Multiply":
        result = value * param
    elif command == "Divide":
        result = param // value if value else None
    elif command == "DivideBy":
        result = value // param if param else None
    elif command == "Modulo":
        result = param % value if value else None
    elif command == "ModuloBy":
        result = value % param if param else None
    elif command == "Interleave":
        result = _interleave(param, value)
    elif command == "LeftHalf":
        result = _half(value, 1)
    elif command == "RightHalf":
        result = _half(value, 0)
    else:  # Output and OutputNumber send nothing
        result = None
    return (0, 0, 0) if result is None else (result, 0, 1)


def _advance(
    state: _State, program: _Program, got: int | None = None
) -> tuple[_State, str | None]:
    """Deliver one send; return the state and anything printed.

    Pure: a read the receiving node needs arrives as ``got``, ``None`` at EOF.
    """
    assert state is not None
    (node, results, k, j), rest = state
    first, step, count = results
    value = first + step * k
    targets = program.targets[node]
    target = targets[j]
    j += 1
    if j == len(targets):
        k, j = k + 1, 0
    if k < count:
        rest = ((node, results, k, j), rest)
    command = program.commands[target]
    out = None
    if command == "Output":
        if value > _MAX_CHAR:
            raise HaltError(
                f"SendStuff Output received {value}, outside 0..{_MAX_CHAR}",
                hint="send Output a character code between 0 and 1114111",
            )
        out = chr(value)
    elif command == "OutputNumber":
        out = str(value)
    sent = _receive(command, program.params[target], value, got)
    if sent[2] and program.targets[target]:
        rest = ((target, sent, 0, 0), rest)
    return rest, out


class _Machine:
    """The shell around :func:`_advance`: it reads input and prints."""

    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.program = _parse(code)
        root: _State = ((0, (0, 0, 1), 0, 0), None)
        self.state = root if self.program.targets[0] else None

    @property
    def halted(self) -> bool:
        return self.state is None

    @property
    def ip(self) -> tuple[int, int, int] | None:
        """The sending node, its result index and its target index."""
        if self.state is None:
            return None
        node, _, k, j = self.state[0]
        return node, k, j

    @property
    def stack(self) -> list[object]:
        """The sending nodes, innermost last."""
        nodes: list[object] = []
        state = self.state
        while state is not None:
            nodes.append(state[0][0])
            state = state[1]
        return nodes[::-1]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.state, self.io.progress())

    def step(self) -> None:
        """Deliver one send, reading first if the receiver is an input node."""
        if self.state is None:
            return
        node, _, _, j = self.state[0]
        command = self.program.commands[self.program.targets[node][j]]
        got = None
        try:
            if command == "Input":
                got = self.io.input_char()
            elif command == "InputNumber":
                got = self.io.input_num()
                if got < 0:
                    raise HaltError(
                        f"SendStuff InputNumber read {got}; numbers are non-negative",
                        hint="supply a non-negative decimal integer",
                    )
        except EOFError:
            got = None
        self.state, out = _advance(self.state, self.program, got)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a SendStuff program: the root sends 0 to its ``>`` nodes."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
