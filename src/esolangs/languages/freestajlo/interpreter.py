r"""Interpreter for Freestajlo.

LEOMOK's 2024 FALSE-inspired stack language.  Single-character commands run
left to right over an array of stacks indexed by every integer (one of them
current, stack 0 at the start) and one unnumbered transfer stack.  Values are
unbounded signed integers; popping an empty stack gives 0, and 0 is the only
false value.  The program halts after its last command.

Commands:
    ``0``-``9`` push a decimal number, as many digits as follow; ``'c``
    pushes ``c``'s code point; ``"s"`` pushes 0, then ``s`` reversed, so
    its first character ends on top.
    ``+ - * /`` pop ``a`` then ``b`` and push ``b op a``; ``%`` is ``b``
    mod ``a`` with ``a``'s sign; ``^`` is ``b**a``, 0 for ``a < 0``;
    ``_`` negates.
    ``=`` pushes -1 if ``a == b``; ``<`` -1 if ``b > a``; ``>`` -1 if
    ``b < a``; else 0.  `````` pushes the NOR of the two.
    ``$`` dup, ``#`` drop, ``\`` swap; ``&`` pops ``a`` and copies the item
    ``a`` deep (0 is the top); ``~`` pops ``a`` and ``b`` and inserts ``b``
    ``a`` deep; ``|`` pushes the stack's length.
    ``:`` prints the top in decimal, ``.`` as the character of its value
    mod 0x10FFFF; both pop.
    ``?{then}`` pops and runs ``then`` on a nonzero value; ``?{then}{else}``
    runs ``else`` otherwise.  ``@{body}`` runs ``body`` while the top is
    nonzero, without popping.
    ``!`` pops ``a`` and makes stack ``a`` current; ``(`` moves the transfer
    stack's top onto the current stack, ``)`` the reverse.
    A letter followed by a block defines that function; a letter alone runs
    it.  ``[...]`` is a comment; whitespace is a no-op.

Input/output:
    ``,`` pushes the next character's code point, or -1 at EOF.  ``;`` reads
    characters until a decimal integer, an optional ``-`` before its digits,
    and pushes it, consuming the character that ends it; 0 at EOF.

Errors:
    ProgramError: an unterminated string, comment or block, ``'`` at the end
    of the source, ``?`` or ``@`` without a block, a block with neither
    before it, an unmatched ``}``, and any other character.
    HaltError: dividing or taking ``%`` by zero, ``&`` or ``~`` at a depth
    the stack does not reach or below zero, running an undefined function,
    and printing a surrogate code point.

Decisions:
    * A string ends at the next ``"``: the Hello, World! example closes it
      there, and the page gives no escape.
    * ``<`` and ``>`` follow the page literally: ``<`` is true when the
      deeper value is the greater, the reverse of ``-``'s operand order.
    * An else block may follow its then block after whitespace or a
      comment: the FizzBuzz example puts both between them.
    * ``&`` and ``~`` past the bottom raise rather than read 0: the page
      gives 0 only to a pop.
    * A function is defined when its definition runs, as FALSE's lambda
      assignment is; a block may define one inside a call.
    * The FizzBuzz example is not pinned: the page states no output and its
      counter runs on the input value's stack, so it does not count up to it.
"""

from __future__ import annotations

from string import ascii_lowercase, ascii_uppercase
from typing import NamedTuple

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.memory import trunc_div
from esolangs.runtime.source_hints import syntax_error

#: Stack cells, top first: ``(top, rest)``, or ``None`` when empty.
type _Cells = tuple[int, _Cells] | None
#: A stack: its length and its cells; persistent, so a push, pop or length is
#: O(1) and a snapshot shares every untouched cell.  One length a stack, not
#: one a cell: per-cell lengths made the written state grow as T log T.
type _Stack = tuple[int, _Cells]
_EMPTY: _Stack = (0, None)
#: The return addresses of the running calls, innermost first.
type _Calls = tuple[int, _Calls] | None
#: One compiled command: its kind, operand and source offset.
type _Op = tuple[str, object, int]

_LETTERS = ascii_uppercase + ascii_lowercase
_DIGITS = "0123456789"
_BINARY = set("+-*/%^=<>`")
_PLAIN = set("_$#\\&~|:.!()")
#: ``.`` prints the value modulo this, as the page writes it.
_CHAR_MOD = 0x10FFFF


class _State(NamedTuple):
    """Everything a command can change but the inactive stacks."""

    ip: int
    stack: _Stack
    transfer: _Stack
    calls: _Calls
    #: Each letter's entry address, or -1 while undefined.
    funcs: tuple[int, ...]


def _push(stack: _Stack, value: int) -> _Stack:
    return stack[0] + 1, (value, stack[1])


def _pop(stack: _Stack) -> tuple[int, _Stack]:
    """Return the top and the rest; an empty stack gives 0."""
    length, cells = stack
    if cells is None:
        return 0, stack
    return cells[0], (length - 1, cells[1])


def _depth(stack: _Stack, depth: int, command: str) -> tuple[list[int], _Stack]:
    """Return the ``depth`` values above the rest, top first."""
    length, cells = stack
    if not 0 <= depth <= length:
        raise HaltError(
            f"Freestajlo {command!r} reaches depth {depth} of a {length}-item stack"
        )
    above = []
    for _ in range(depth):
        assert cells is not None
        above.append(cells[0])
        cells = cells[1]
    return above, (length - depth, cells)


class _Parser:
    """Compile source to a flat list of ops with resolved jumps."""

    def __init__(self, code: str) -> None:
        self.code = code
        self.pos = 0
        self.ops: list[_Op] = []

    def _emit(self, kind: str, arg: object, at: int) -> int:
        self.ops.append((kind, arg, at))
        return len(self.ops) - 1

    def _patch(self, index: int, target: int) -> None:
        kind, _, at = self.ops[index]
        self.ops[index] = (kind, target, at)

    def _skip(self) -> None:
        """Skip whitespace and comments."""
        code = self.code
        while self.pos < len(code):
            if code[self.pos].isspace():
                self.pos += 1
            elif code[self.pos] == "[":
                end = code.find("]", self.pos)
                if end < 0:
                    raise syntax_error(
                        "a Freestajlo '[' comment is never closed", "end it with ']'"
                    )
                self.pos = end + 1
            else:
                return

    def _block(self, command: str) -> None:
        """Compile the ``{...}`` that must come next."""
        if not self._next_is_block():
            raise syntax_error(
                f"Freestajlo {command!r} needs a {{block}}", f"write {command}{{...}}"
            )
        self.pos += 1
        self.body(closing=True)

    def _next_is_block(self) -> bool:
        self._skip()
        return self.code[self.pos : self.pos + 1] == "{"

    def body(self, *, closing: bool) -> None:
        """Compile commands up to the matching ``}``, or the end."""
        code = self.code
        while True:
            self._skip()
            if self.pos == len(code):
                if closing:
                    raise syntax_error(
                        "a Freestajlo '{' block is never closed", "end it with '}'"
                    )
                return
            at, char = self.pos, code[self.pos]
            self.pos += 1
            if char == "}":
                if not closing:
                    raise syntax_error(
                        "a Freestajlo '}' has no matching '{'", "balance the braces"
                    )
                return
            self._command(char, at)

    def _command(self, char: str, at: int) -> None:
        code = self.code
        if char in _DIGITS:
            end = at
            while end < len(code) and code[end] in _DIGITS:
                end += 1
            self._emit("push", int(code[at:end]), at)
            self.pos = end
        elif char == "'":
            if self.pos == len(code):
                raise syntax_error(
                    "a Freestajlo ''' needs a character after it", "write 'c"
                )
            self._emit("push", ord(code[self.pos]), at)
            self.pos += 1
        elif char == '"':
            end = code.find('"', self.pos)
            if end < 0:
                raise syntax_error(
                    "a Freestajlo '\"' string is never closed", "end it with '\"'"
                )
            text = code[self.pos : end]
            self._emit("string", tuple(ord(c) for c in reversed(text)), at)
            self.pos = end + 1
        elif char == "?":
            test = self._emit("if", 0, at)
            self._block("?")
            if self._next_is_block():
                skip = self._emit("jump", 0, self.pos)
                self._patch(test, len(self.ops))
                self.pos += 1
                self.body(closing=True)
                self._patch(skip, len(self.ops))
            else:
                self._patch(test, len(self.ops))
        elif char == "@":
            test = self._emit("while", 0, at)
            self._block("@")
            self._emit("jump", test, self.pos - 1)
            self._patch(test, len(self.ops))
        elif char in _LETTERS:
            slot = _LETTERS.index(char)
            if self._next_is_block():
                define = self._emit("define", (slot, 0), at)
                self.pos += 1
                self.body(closing=True)
                self._emit("return", None, self.pos - 1)
                self.ops[define] = ("define", (slot, len(self.ops)), at)
            else:
                self._emit("call", slot, at)
        elif char in _BINARY or char in _PLAIN or char in ",;":
            self._emit(char, None, at)
        elif char == "{":
            raise syntax_error(
                "a Freestajlo block needs '?', '@' or a letter before it",
                "write ?{...}, @{...} or f{...}",
            )
        else:
            raise syntax_error(
                f"{char!r} is not a Freestajlo command",
                "use the commands the spec lists, whitespace, or a [comment]",
            )


def _parse(code: str) -> tuple[_Op, ...]:
    """Return the compiled ops of ``code``."""
    parser = _Parser(code)
    parser.body(closing=False)
    return tuple(parser.ops)


def _binary(char: str, a: int, b: int) -> int:
    """Return ``b char a``."""
    if char in "/%" and a == 0:
        raise HaltError(f"Freestajlo {char!r} by zero")
    match char:
        case "+":
            return b + a
        case "-":
            return b - a
        case "*":
            return b * a
        case "/":
            return trunc_div(b, a)
        case "%":
            return b % a
        case "^":
            return 0 if a < 0 else b**a
        case "=":
            return -(a == b)
        case "<":
            return -(b > a)
        case ">":
            return -(b < a)
    return ~(a | b)


def _stack_op(char: str, stack: _Stack) -> _Stack:
    """Return the current stack after a stack-shuffling command."""
    if char == "|":
        return _push(stack, stack[0])
    a, stack = _pop(stack)
    if char == "_":
        return _push(stack, -a)
    if char == "$":
        return _push(_push(stack, a), a)
    if char == "#":
        return stack
    if char == "\\":
        b, stack = _pop(stack)
        return _push(_push(stack, a), b)
    if char == "&":
        # Depth ``a`` is the ``a + 1``-th item; ``-1`` would pass as zero.
        above, _ = _depth(stack, a + 1 if a >= 0 else -1, "&")
        return _push(stack, above[a])
    b, stack = _pop(stack)
    above, rest = _depth(stack, a, "~")
    rest = _push(rest, b)
    for value in reversed(above):
        rest = _push(rest, value)
    return rest


def _advance(
    state: _State, ops: tuple[_Op, ...], read: int | None
) -> tuple[_State, tuple[str, int] | None]:
    """Return the state after one op, and its effect on the outside.

    Pure: a read arrives as ``read``; the effect is ``(":", value)`` or
    ``(".", value)`` to print, or ``("!", index)`` to switch stacks.
    """
    ip, stack, transfer, calls, funcs = state
    kind, arg, _ = ops[ip]
    ip += 1
    effect = None
    if kind == "push":
        assert isinstance(arg, int)
        stack = _push(stack, arg)
    elif kind == "string":
        assert isinstance(arg, tuple)
        stack = _push(stack, 0)
        for value in arg:
            stack = _push(stack, value)
    elif kind in _BINARY:
        a, stack = _pop(stack)
        b, stack = _pop(stack)
        stack = _push(stack, _binary(kind, a, b))
    elif kind in ",;":
        assert read is not None
        stack = _push(stack, read)
    elif kind in ":.!":
        value, stack = _pop(stack)
        effect = (kind, value)
    elif kind == "(":
        value, transfer = _pop(transfer)
        stack = _push(stack, value)
    elif kind == ")":
        value, stack = _pop(stack)
        transfer = _push(transfer, value)
    elif kind in _PLAIN:
        stack = _stack_op(kind, stack)
    elif kind in ("if", "while"):
        assert isinstance(arg, int)
        value, rest = _pop(stack)
        if kind == "if":
            stack = rest
        if not value:
            ip = arg
    elif kind == "jump":
        assert isinstance(arg, int)
        ip = arg
    elif kind == "define":
        assert isinstance(arg, tuple)
        slot, after = arg
        funcs = (*funcs[:slot], ip, *funcs[slot + 1 :])
        ip = after
    elif kind == "call":
        assert isinstance(arg, int)
        if funcs[arg] < 0:
            raise HaltError(f"Freestajlo function {_LETTERS[arg]} is not defined")
        calls, ip = (ip, calls), funcs[arg]
    else:  # return
        assert calls is not None
        ip, calls = calls
    return _State(ip, stack, transfer, calls, funcs), effect


class _Machine:
    """The compiled program, the current stack's state and the others."""

    #: ``,`` and ``;`` push the spec's EOF values instead of raising.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.ops = _parse(code)
        self.end = len(code)
        self.state = _State(0, _EMPTY, _EMPTY, None, (-1,) * len(_LETTERS))
        self.index = 0
        #: The inactive stacks by index; the current one lives in ``state``.
        self.others: dict[int, _Stack] = {}

    @property
    def halted(self) -> bool:
        return self.state.ip >= len(self.ops)

    @property
    def ind(self) -> int:
        """The source offset of the next command."""
        return self.ops[self.state.ip][2] if not self.halted else self.end

    @property
    def stack(self) -> list[int]:
        """The current stack, bottom first."""
        values, cells = [], self.state.stack[1]
        while cells is not None:
            values.append(cells[0])
            cells = cells[1]
        return values[::-1]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        others = frozenset((k, v) for k, v in self.others.items() if v[0])
        return (*self.state, self.index, others, self.io.progress())

    def _read(self, kind: str) -> int:
        if kind == ",":
            try:
                return self.io.input_char()
            except EOFError:
                return -1
        return self._read_number()

    def _read_number(self) -> int:
        """Scan to the next decimal integer; 0 at EOF."""
        negative, digits = False, ""
        while True:
            try:
                char = chr(self.io.input_char())
            except EOFError:
                break
            if char in _DIGITS:
                digits += char
            elif digits:
                break
            else:
                negative = char == "-"
        if not digits:
            return 0
        return -int(digits) if negative else int(digits)

    def step(self) -> None:
        if self.halted:
            return
        kind = self.ops[self.state.ip][0]
        read = self._read(kind) if kind in ",;" else None
        self.state, effect = _advance(self.state, self.ops, read)
        if effect is None:
            return
        command, value = effect
        if command == ":":
            self.io.print_num(value)
        elif command == ".":
            point = value % _CHAR_MOD
            if 0xD800 <= point <= 0xDFFF:
                raise HaltError(f"Freestajlo '.' cannot print surrogate {point:#x}")
            self.io.print_char(chr(point))
        elif value != self.index:
            self.others[self.index] = self.state.stack
            self.state = self.state._replace(stack=self.others.pop(value, _EMPTY))
            self.index = value


def run(code: str, io: IO) -> None:
    """Run a Freestajlo program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
