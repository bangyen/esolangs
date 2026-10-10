r"""Interpreter for SStack (Seven Stacks).

Seven stacks ``a``-``g`` of unbounded unsigned integers; an empty stack
reads 0.  Commands: ``>x/y<`` move a top, ``+x/y+``/``-x/y-`` move it
incremented/decremented (decrementing 0 is a nop), ``;x;`` push an input
byte, ``:x:`` print the top as a byte, ``"N/y"`` push decimal ``N``,
``~x~`` pop, ``[x\y/ ... ]`` loop while the tops of ``x`` and ``y`` are
equal.  The page has no example with a stated output (its brainfuck
interpreter is marked untested and has a ``[d\g`` typo), so every gap
below is a judgment call from the command list alone:

- Whitespace is discarded everywhere before parsing ("new lines ... are
  optional"); any other stray character raises :class:`ValueError`, as do
  unmatched brackets and a stack name outside ``a``-``g``.
- Popping an empty stack (``>``, ``+``, ``-``, ``~``) reads 0 and leaves
  it empty: "accsess empty stack ... would return 0".
- ``:x:`` peeks; a top above 255 has no byte and raises
  :class:`HaltError`.
- ``;x;`` at EOF raises :class:`EOFError` (the page is silent).
- The page's ``!`` input separator belongs to its brainfuck interpreter's
  input, not to SStack source, so it is a stray character here.

Stacks are persistent cons cells, so a push or pop is O(1) and the
snapshot shares structure instead of copying seven stacks per step.
"""

from __future__ import annotations

import re

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.brackets import unmatched
from esolangs.interpreters.io import IO
from esolangs.interpreters.source_hints import syntax_error

#: A stack: ``None`` when empty, else ``(top, rest)``.
type _Stack = tuple[int, _Stack] | None
#: ``(ind, stacks)``: the instruction cursor and the seven stacks, ``a`` first.
type _State = tuple[int, tuple[_Stack, ...]]
#: ``(kind, x, y, jump)``: ``kind`` is the opening glyph; ``x`` a stack index
#: or, for ``"``, the literal; ``y`` a stack index; ``jump`` the op after the
#: partner bracket for ``[``, the partner ``[`` for ``]``.
type _Op = tuple[str, int, int, int]

_NAMES = "abcdefg"
_TOKEN = re.compile(
    r"""(?P<move>([>+-])([a-g])/([a-g])([<+-]))"""
    r"""|(?P<unary>([;:~])([a-g])([;:~]))"""
    r"""|(?P<push>"([0-9]+)/([a-g])")"""
    r"""|(?P<loop>\[([a-g])\\([a-g])/)"""
    r"""|(?P<end>\])"""
)
_CLOSERS = {">": "<", "+": "+", "-": "-"}


def _parse(code: str) -> list[_Op]:
    """Tokenize ``code`` with whitespace removed and resolve the brackets.

    Positions in errors count from the start of the original source.
    """
    where = [i for i, char in enumerate(code) if not char.isspace()]
    text = "".join(code[i] for i in where)
    ops: list[_Op] = []
    opens: list[tuple[int, int]] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        g = match.groups() if match else ()
        if (
            match is None
            or (g[0] and _CLOSERS[g[1]] != g[4])
            or (g[5] and g[6] != g[8])
        ):
            raise syntax_error(
                f"no SStack command at position {where[pos]}",
                'commands are >x/y< +x/y+ -x/y- ;x; :x: "N/y" ~x~ [x\\y/ ]',
            )
        if g[0]:
            ops.append((g[1], _NAMES.index(g[2]), _NAMES.index(g[3]), 0))
        elif g[5]:
            ops.append((g[6], _NAMES.index(g[7]), 0, 0))
        elif g[9]:
            ops.append(('"', int(g[10]), _NAMES.index(g[11]), 0))
        elif g[12]:
            opens.append((len(ops), where[pos]))
            ops.append(("[", _NAMES.index(g[13]), _NAMES.index(g[14]), 0))
        else:
            if not opens:
                raise unmatched("]", where[pos])
            start, _ = opens.pop()
            ops[start] = (*ops[start][:3], len(ops) + 1)
            ops.append(("]", 0, 0, start))
        pos = match.end()
    if opens:
        raise unmatched("[", opens[-1][1])
    return ops


def _top(stack: _Stack) -> int:
    return stack[0] if stack is not None else 0


def _advance(state: _State, ops: list[_Op], byte: int | None = None) -> _State:
    """Return the state after the op at the cursor; ``;``'s byte is ``byte``.

    Pure: the stacks are immutable and only the touched slots are rebuilt.
    """
    ind, stacks = state
    kind, x, y, jump = ops[ind]
    if kind == "[":
        return (ind + 1 if _top(stacks[x]) == _top(stacks[y]) else jump, stacks)
    if kind == "]":
        return (jump, stacks)
    new = list(stacks)
    if kind in "><+-~":
        source = new[x]
        value = source[0] if source is not None else 0
        new[x] = source[1] if source is not None else None
        if kind == "+":
            value += 1
        elif kind == "-":
            value = max(value - 1, 0)
        if kind != "~":
            new[y] = (value, new[y])
    elif kind == ";":
        new[x] = (byte if byte is not None else 0, new[x])
    elif kind == '"':
        new[y] = (x, new[y])
    # ``:`` changes no stack; its write is the shell's.
    return (ind + 1, tuple(new))


class _Machine:
    """An SStack run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.ops = _parse(code)
        self.state: _State = (0, (None,) * len(_NAMES))

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.ops)

    @property
    def stacks(self) -> dict[str, list[int]]:
        """Each stack, bottom first."""
        out = {}
        for name, stack in zip(_NAMES, self.state[1], strict=True):
            items = []
            while stack is not None:
                items.append(stack[0])
                stack = stack[1]
            out[name] = items[::-1]
        return out

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Execute one op; the reads, the writes and the byte check live here."""
        if self.halted:
            return
        kind, x, _, _ = self.ops[self.state[0]]
        byte = None
        if kind == ";":
            byte = self.io.input_char()
        elif kind == ":":
            value = _top(self.state[1][x])
            if value > 255:
                raise HaltError(
                    f"':{_NAMES[x]}:' prints {value}, which is not a byte",
                    hint="keep printed values in 0..255",
                )
            self.io.print_char(chr(value))
        self.state = _advance(self.state, self.ops, byte)


def run(code: str, io: IO) -> None:
    """Run an SStack program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
