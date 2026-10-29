"""Interpreter for CreativeScript v2.

Unname4798's total language: one command a line, run once, top to bottom,
over unboundedly many named integer variables.  No jump exists, so every run
ends after at most one step a line.

Commands:
    ``say! text``: print the rest of the line.
    ``set! a b``: ``a`` = the integer literal or variable ``b``.
    ``add! a b c``, ``sub! a b c``, ``mul! a b c``, ``div! a b c``,
    ``mod! a b c``: ``c`` = ``a`` op ``b``; ``sub!`` is ``a - b``, ``div!``
    and ``mod!`` floor.
    ``out! a``: print variable ``a`` in decimal.
    ``in! a``: ``a`` = the next input integer.

Input/output:
    Whitespace-separated decimal integers; a read at EOF raises.  Output is
    raw text: ``say!`` and ``out!`` add no newline.

Errors:
    ProgramError: an unknown command, a wrong operand count, an operand that
    is an integer literal where a variable is required, or a variable named
    like an integer.
    InputExhaustedError: ``in!`` at EOF.
    ArgumentError: an input token that is not an integer.
    HaltError: a variable read before it is set, and ``div!``/``mod!`` by 0.

Decisions:
    * Division floors: the page's equality program feeds ``2sq / (sq + 1)``
      to ``sub! one neq eq`` and needs 0 for ``sq = 0`` and 1 for ``sq >= 1``
      ("if we assume the divide function is floor divide").  ``mod!`` floors
      to match, and ``sub!`` is ``a - b`` by the same program (``sub! one neq
      eq`` is 1 - neq).
    * Only ``set!`` takes a literal: every example builds constants with
      ``set! one 1``; a literal elsewhere raises, as the page never shows one.
    * Division by 0, a variable read before it is set, and ``in!`` text that
      is not an integer are errors; the page defines none.
    * Output has no separator or newline: the page's ``say!`` examples print
      one string and ``out!`` "prints variable a".
    * ``say!`` prints everything after ``say! ``, spaces kept; a bare
      ``say!`` prints nothing.
"""

import re

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.memory import format_integer, parse_integer
from esolangs.runtime.source_hints import keyword_hint, syntax_error

#: Operand counts; ``say!`` takes the raw rest of its line.
_ARITY = {
    "set!": 2,
    "add!": 3,
    "sub!": 3,
    "mul!": 3,
    "div!": 3,
    "mod!": 3,
    "out!": 1,
    "in!": 1,
}
_INTEGER = re.compile(r"[+-]?[0-9]+")
#: A command: its name, the slots it names, and a ``say!`` text or ``set!``
#: literal (``None`` when ``set!`` copies a variable).
type _Command = tuple[str, tuple[int, ...], str | int | None]
#: Each variable's value by slot, ``None`` until set.
type _State = tuple[int | None, ...]


def _parse(code: str) -> tuple[tuple[_Command, ...], tuple[int, ...], int]:
    """Return the commands, each one's source offset, and the variable count."""
    program: list[_Command] = []
    offsets: list[int] = []
    slots: dict[str, int] = {}
    for found in re.finditer(r"[^\n]+", code):
        line = found.group()
        if not line.strip():
            continue
        name, _, rest = line.lstrip().partition(" ")
        if name == "say!":
            program.append((name, (), rest))
        elif name in _ARITY:
            args = rest.split()
            if len(args) != _ARITY[name]:
                raise syntax_error(
                    f"{name} takes {_ARITY[name]} operands, got {len(args)}",
                    f"write {name} with {_ARITY[name]} operands",
                )
            literal = None
            if name == "set!" and _INTEGER.fullmatch(args[1]):
                literal = parse_integer(args.pop())
            for operand in args:
                if _INTEGER.fullmatch(operand):
                    raise syntax_error(
                        f"{operand} is an integer where {name} needs a variable",
                        "name a variable; only the second operand of set! "
                        "takes a literal",
                    )
            program.append(
                (name, tuple(slots.setdefault(op, len(slots)) for op in args), literal)
            )
        else:
            raise syntax_error(
                f"{name!r} is not a CreativeScript v2 command",
                keyword_hint(name, ["say!", *_ARITY], "write say! set! add! ..."),
            )
        offsets.append(found.start() + len(line) - len(line.lstrip()))
    if not program:
        raise syntax_error(
            "a CreativeScript v2 program needs at least one command",
            "write at least one command, for example say! Hello",
        )
    return tuple(program), tuple(offsets), len(slots)


def _get(state: _State, slot: int) -> int:
    value = state[slot]
    if value is None:
        raise HaltError("a variable is read before it is set")
    return value


def _advance(
    state: _State, command: _Command, byte: int | None = None
) -> tuple[_State, str | None]:
    """Return the state after one command, and the text to print.

    Pure: an ``in!`` arrives as ``byte``, a print leaves as the return value.
    """
    name, slots, extra = command
    value: int | None
    if name == "say!":
        return state, str(extra)
    if name == "out!":
        return state, format_integer(_get(state, slots[0]))
    if name == "in!":
        value = byte
    elif name == "set!":
        value = extra if isinstance(extra, int) else _get(state, slots[1])
    else:
        x, y = _get(state, slots[0]), _get(state, slots[1])
        if name == "add!":
            value = x + y
        elif name == "sub!":
            value = x - y
        elif name == "mul!":
            value = x * y
        elif y == 0:
            raise HaltError(f"{name} by zero")
        else:
            value = x // y if name == "div!" else x % y
    target = slots[0] if name in ("in!", "set!") else slots[-1]
    return (*state[:target], value, *state[target + 1 :]), None


class _Machine:
    """The variables and the next command."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.program, self.offsets, count = _parse(code)
        self.state: _State = (None,) * count
        self.cursor = 0

    @property
    def halted(self) -> bool:
        return self.cursor >= len(self.program)

    @property
    def memory(self) -> list[int]:
        """The variables set so far, in first-mention order."""
        return [value for value in self.state if value is not None]

    @property
    def ip(self) -> int:
        """The source offset of the next command."""
        return self.offsets[min(self.cursor, len(self.offsets) - 1)]

    def snapshot(self) -> tuple[object, ...]:
        # The names are fixed by the program, so slots carry the run state.
        return (self.state, self.cursor, self.io.progress())

    def step(self) -> None:
        if self.halted:
            return
        command = self.program[self.cursor]
        byte = self.io.input_num() if command[0] == "in!" else None
        self.state, out = _advance(self.state, command, byte)
        if out is not None:
            self.io.print_str(out)
        self.cursor += 1


def run(code: str, io: IO) -> None:
    """Run a CreativeScript v2 program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
