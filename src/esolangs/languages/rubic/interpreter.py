"""Interpreter for Rubic.

The memory is a Rubik's cube and one integer, The Variable (V), starting
at 0 and solved with white up, green front, orange left (yellow, blue and
red opposite).  Tokens are whitespace-separated and case-insensitive.  A
colour pair ``x`` such as ``wg`` counts the stickers of the second colour on
the face whose centre is the first, the centre not counted.  Colours are
``w g o`` and, primed, their opposites ``w' g' o'`` (yellow, blue, red).
The wiki's Hello World prints ``Hello World!`` and a newline.

Commands:
    ``R U L F B D``: turn that face a clockwise quarter as seen from it.
    ``M E S``: turn the middle slice as ``R``, ``U``, ``F`` do.
    ``'`` suffix: turns anticlockwise; ``2`` suffix: a half turn.
    ``.x``: set V to x.
    ``+x -x *x``: add, subtract, multiply.
    ``/x``: floor-divide (0 when x is 0).
    ``%x``: reduce V mod x (unchanged when x is 0).
    ``!``: print V mod 128 as a character.
    ``( ... )``: run the body V times, V read on entry.  A negative V runs
    it |V| times backwards, each command inverted: a turn turns back, ``.x``
    sets -x, ``+``/``-`` and ``*``/``/`` swap, ``%x`` is skipped, ``!``
    reads one character into V as its code point, and a nested loop runs
    normally, by V's sign on reaching it.

Input/output:
    A backwards ``!`` reads one character; a read past the end of the input
    raises (see Errors).

Errors:
    ProgramError: An unknown token, a colour pair that is not two colours,
    or an unmatched parenthesis.
    InputExhaustedError: A backwards ``!`` at EOF.

Decisions:
    * The cat program ``r b -go ( ! ) !`` never reads: after ``r b`` there is
      no orange on the green face, so ``go`` is 0 and it prints NUL.
      ``og`` is 1 there and is the only pair of those two colours that is,
      so ``r b -og ( ! ) !`` is the repair.  Both are pinned.
    * V is unbounded; ``%x`` with x > 0 leaves 0..x-1 (Python's ``%``,
      matching the floored ``/``).
"""

from __future__ import annotations

import re
from typing import NamedTuple

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO


def _rotate(v: tuple[int, int, int], axis: int, sign: int) -> tuple[int, int, int]:
    """Rotate ``v`` a quarter turn about ``axis``, anticlockwise if ``sign`` is 1."""
    x, y, z = v
    if axis == 0:
        return (x, -sign * z, sign * y)
    if axis == 1:
        return (sign * z, y, -sign * x)
    return (-sign * y, sign * x, z)


#: Centre normals, x right, y up, z front, in colour order w w' g g' o o'.
_CENTRES = ((0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (-1, 0, 0), (1, 0, 0))
_COLOURS = {"w": 0, "w'": 1, "g": 2, "g'": 3, "o": 4, "o'": 5}


def _face(
    n: tuple[int, int, int],
) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
    """Return the nine stickers ``(position, normal)`` of the face with normal ``n``."""
    axis = next(i for i in range(3) if n[i])
    stickers = []
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            free = iter((a, b))
            p = tuple(n[i] if i == axis else next(free) for i in range(3))
            stickers.append(((p[0], p[1], p[2]), n))
    return stickers


#: Every sticker as (position, normal); the cube is the colour on each.
_STICKERS = tuple(sorted(s for n in _CENTRES for s in _face(n)))
_SLOT = {s: k for k, s in enumerate(_STICKERS)}
_SOLVED = tuple(_CENTRES.index(n) for _, n in _STICKERS)
#: Per face normal: its centre slot and its eight other slots.
_FACES = {
    n: (_SLOT[(n, n)], tuple(_SLOT[s] for s in _STICKERS if s[1] == n and s[0] != n))
    for n in _CENTRES
}
#: Layer axis, layer coordinate, and the clockwise quarter's sign.
_LAYERS = {
    "r": (0, 1, -1),
    "l": (0, -1, 1),
    "m": (0, 0, -1),
    "u": (1, 1, -1),
    "d": (1, -1, 1),
    "e": (1, 0, -1),
    "f": (2, 1, -1),
    "b": (2, -1, 1),
    "s": (2, 0, -1),
}


def _permutation(axis: int, layer: int, sign: int) -> tuple[int, ...]:
    """``perm[k]`` is the slot whose sticker moves to slot ``k``."""
    perm = list(range(len(_STICKERS)))
    for k, (p, n) in enumerate(_STICKERS):
        if p[axis] == layer:
            perm[_SLOT[(_rotate(p, axis, sign), _rotate(n, axis, sign))]] = k
    return tuple(perm)


def _turns() -> dict[str, tuple[int, ...]]:
    """Every turn token's permutation."""
    table = {}
    for face, (axis, layer, sign) in _LAYERS.items():
        quarter = _permutation(axis, layer, sign)
        table[face] = quarter
        table[face + "'"] = _permutation(axis, layer, -sign)
        table[face + "2"] = tuple(quarter[k] for k in quarter)
    return table


_TURNS = _turns()


def _inverse_turn(token: str) -> str:
    """Return the turn that undoes ``token``."""
    if token.endswith("2"):
        return token
    return token[:-1] if token.endswith("'") else token + "'"


#: A command, its turn token (else ""), and its colour pair (else 0, 0).
type _Op = tuple[str, str, int, int]


class _Program(NamedTuple):
    """The parsed tokens, their source offsets, and each bracket's partner."""

    ops: tuple[_Op, ...]
    offsets: tuple[int, ...]
    match: tuple[int, ...]


def _colour_pair(text: str) -> tuple[int, int]:
    """Parse ``wg`` or ``w'o'`` into two colour indices."""
    colours, at = [], 0
    while at < len(text):
        primed = text[at + 1 : at + 2] == "'"
        colour = _COLOURS.get(text[at : at + 1 + primed])
        if colour is None:
            break
        colours.append(colour)
        at += 1 + primed
    if at != len(text) or len(colours) != 2:
        raise ValueError(f"{text!r} is not a Rubic colour pair such as wg or w'o'")
    return colours[0], colours[1]


def parse(code: str) -> _Program:
    """Tokenize ``code`` and pair its parentheses."""
    ops: list[_Op] = []
    offsets: list[int] = []
    opens: list[int] = []
    match: list[int] = []
    for found in re.finditer(r"\S+", code):
        token = found.group().lower()
        offsets.append(found.start())
        match.append(-1)
        if token == "(":
            opens.append(len(ops))
            ops.append(("(", "", 0, 0))
        elif token == ")":
            if not opens:
                raise ValueError("Rubic ')' has no matching '('")
            partner = opens.pop()
            match[partner], match[-1] = len(ops), partner
            ops.append((")", "", 0, 0))
        elif token in _TURNS:
            ops.append(("t", token, 0, 0))
        elif token == "!":
            ops.append(("!", "", 0, 0))
        elif token[0] in ".+-*/%":
            ops.append((token[0], "", *_colour_pair(token[1:])))
        else:
            raise ValueError(f"{token!r} is not a Rubic command")
    if opens:
        raise ValueError("Rubic '(' is never closed")
    return _Program(tuple(ops), tuple(offsets), tuple(match))


def _value(cube: tuple[int, ...], centre: int, colour: int) -> int:
    """Stickers of ``colour`` on the face whose centre is ``centre``."""
    for middle, others in _FACES.values():
        if cube[middle] == centre:
            return sum(1 for k in others if cube[k] == colour)
    raise AssertionError("every colour has a centre")


def _arith(op: str, v: int, x: int, *, backwards: bool) -> int:
    """Apply an arithmetic command, inverted when ``backwards``."""
    if backwards:
        if op == ".":
            return -x
        if op == "%":
            return v
        op = {"+": "-", "-": "+", "*": "/", "/": "*"}[op]
    if op == ".":
        return x
    if op == "+":
        return v + x
    if op == "-":
        return v - x
    if op == "*":
        return v * x
    if op == "/":
        return v // x if x else 0
    return v % x if x else v


#: A running loop: its brackets, the passes left, its direction, and where
#: the enclosing code resumes.
class _Frame(NamedTuple):
    start: int
    end: int
    left: int
    backwards: bool
    resume: int


class _State(NamedTuple):
    """One instant: the next token, V, the cube, and the running loops."""

    ind: int
    v: int
    cube: tuple[int, ...]
    frames: tuple[_Frame, ...]


def _advance(
    state: _State, program: _Program, char: int | None
) -> tuple[_State, str | None]:
    """Run the token at ``state.ind``; a reversed ``!`` takes ``char``, a code point.

    Return the next state and the character printed, if any.
    """
    ind, v, cube, frames = state
    backwards = bool(frames) and frames[-1].backwards
    step = -1 if backwards else 1
    op = program.ops[ind]
    kind = op[0]
    if frames and ind == (frames[-1].start if backwards else frames[-1].end):
        top = frames[-1]
        if top.left > 1:
            restart = top.end - 1 if backwards else top.start + 1
            return _State(
                restart, v, cube, (*frames[:-1], top._replace(left=top.left - 1))
            ), None
        return _State(top.resume, v, cube, frames[:-1]), None
    if kind in "()":
        # Forward code meets a loop at '(', backward code at ')'.
        start, end = (
            (program.match[ind], ind) if backwards else (ind, program.match[ind])
        )
        resume = start - 1 if backwards else end + 1
        if v == 0:
            return _State(resume, v, cube, frames), None
        frame = _Frame(start, end, abs(v), v < 0, resume)
        first = end - 1 if v < 0 else start + 1
        return _State(first, v, cube, (*frames, frame)), None
    out = None
    if kind == "t":
        turn = _TURNS[_inverse_turn(op[1]) if backwards else op[1]]
        cube = tuple(cube[k] for k in turn)
    elif kind == "!":
        if backwards:
            v = char if char is not None else v
        else:
            out = chr(v % 128)
    else:
        v = _arith(kind, v, _value(cube, op[2], op[3]), backwards=backwards)
    return _State(ind + step, v, cube, frames), out


class _Machine:
    """The run state over the parsed program."""

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.program = parse(code)
        self.state = _State(0, 0, _SOLVED, ())

    @property
    def halted(self) -> bool:
        return not self.state.frames and self.state.ind >= len(self.program.ops)

    @property
    def ip(self) -> int:
        """The source offset of the next token."""
        if self.halted:
            return len(self.code)
        return self.program.offsets[self.state.ind]

    @property
    def memory(self) -> list[object]:
        """The Variable, then each sticker's colour index (w w' g g' o o')."""
        return [self.state.v, *self.state.cube]

    @property
    def stack(self) -> list[object]:
        """The running loops, outermost first: passes left and direction."""
        return [
            (f.left, "backwards" if f.backwards else "forwards")
            for f in self.state.frames
        ]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Run one token; a backwards ``!`` reads, a forwards one prints."""
        if self.halted:
            return
        ind, _, _, frames = self.state
        char = None
        if self.program.ops[ind][0] == "!" and frames and frames[-1].backwards:
            char = self.io.input_char()
        self.state, out = _advance(self.state, self.program, char)
        if out is not None:
            self.io.print_char(out)


def run(code: str, io: IO) -> None:
    """Run a Rubic program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
