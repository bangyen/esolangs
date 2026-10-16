"""Interpreter for Caballo.

The data is a mapping from stacks of naturals to integer weights, starting
with the input stack at weight 1.  ``p`` pops, ``q`` pushes 0, ``i`` and
``d`` step the top (a ``d`` below zero drops that stack), ``1`` does
nothing, ``2``-``9`` swap the top with that element; each sums the weights
of every stack it maps to one result.  ``(x+y+...)`` runs each branch on a
copy and adds the results; ``[x]`` is ``(1+x[x])``, so it adds ``x``
applied 0, 1, 2, ... times until the mapping empties; ``0`` empties it and
``-`` negates it.  Stacks have endless zeros below, so bottom zeros vanish.
At the end, negative weights are dropped and one stack is drawn by weight
and printed; an empty mapping prints nothing.  The wiki's Addition
``[d2i2](1+di-)p`` maps ``[2,1]`` to ``[3]``.

The draw uses the randomness hook, so ``esolangs.run(..., seed=s)`` is
reproducible.

Input/output:
    Input is whitespace-delimited naturals, the first on top (the wiki
    writes stacks top first); empty input is the empty stack.  Output is
    the drawn stack in the wiki's notation, top first: ``[0,3]``.

Errors:
    ProgramError: A malformed program: a character that is not a command,
    an unclosed ``(`` or ``[``, or a ``)`` or ``]`` with no opener.
    HaltError: An input token that is not a natural.

Decisions:
    * ``|`` separates branches as ``+`` does: the wiki's lookup-table
      example uses it.  Whitespace is ignored: the examples contain spaces.
    * A command or group reached with an empty mapping is skipped whole, as
      the wiki allows ("all of these commands are no-ops, and thus can be
      skipped").
    * The wiki's pairing example ends ``pp``; its parts leave
      ``[0,(2x+1)2^y]``, so ``pp`` pops the result.  Both versions are
      pinned.
"""

from __future__ import annotations

from typing import NamedTuple, cast

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.randomness import Randomness, draw

type _Stack = tuple[int, ...]
type _Mapping = tuple[tuple[_Stack, int], ...]
#: A command character, a sum over branch sequences, or a loop over one;
#: sequences are named by their index in the program table.
type _Node = str | tuple[str, tuple[int, ...]]
type _Program = tuple[tuple[_Node, ...], ...]
#: ``("seq", id, next)``, ``("sum", branches, next, base, acc)``,
#: ``("loop", id, acc)``: integers name code, so the frames hold no program.
type _Frame = tuple[object, ...]

_PRIMITIVES = frozenset("pqid123456789")


class _State(NamedTuple):
    """One instant: the pending frames, innermost last, and the mapping."""

    frames: tuple[_Frame, ...]
    mapping: _Mapping


def parse(code: str) -> _Program:
    """Return the program's sequences, the whole program first."""
    src = "".join(code.split())
    pos = 0
    table: list[tuple[_Node, ...]] = []

    def seq(stops: str) -> int:
        nonlocal pos
        at = len(table)
        table.append(())
        items: list[_Node] = []
        while pos < len(src) and src[pos] not in stops:
            c = src[pos]
            pos += 1
            if c == "(":
                branches = [seq("+|)")]
                while pos < len(src) and src[pos] in "+|":
                    pos += 1
                    branches.append(seq("+|)"))
                if pos >= len(src):
                    raise ValueError("Caballo '(' is never closed")
                pos += 1
                items.append(("sum", tuple(branches)))
            elif c == "[":
                body = seq("]")
                if pos >= len(src):
                    raise ValueError("Caballo '[' is never closed")
                pos += 1
                items.append(("loop", (body,)))
            elif c in _PRIMITIVES or c in "0-":
                items.append(c)
            else:
                raise ValueError(
                    f"{c!r} is not a Caballo command; the commands are "
                    "p q i d 0-9 - ( + | ) [ ]"
                )
        table[at] = tuple(items)
        return at

    seq(")]+|")
    if pos != len(src):
        raise ValueError(f"Caballo {src[pos]!r} has no opening bracket")
    return tuple(table)


def _strip(stack: _Stack) -> _Stack:
    """Drop the zeros at the bottom, which the endless zeros absorb."""
    end = len(stack)
    while end and stack[end - 1] == 0:
        end -= 1
    return stack[:end]


def _apply(command: str, stack: _Stack) -> _Stack | None:
    """Map one stack; ``None`` when ``d`` would go below zero."""
    if command == "p":
        return stack[1:]
    if command == "q":
        return _strip((0, *stack))
    if command == "i":
        return ((stack[0] if stack else 0) + 1, *stack[1:])
    if command == "d":
        if not stack or stack[0] == 0:
            return None
        return _strip((stack[0] - 1, *stack[1:]))
    if command == "1":
        return stack
    depth = int(command)
    cells = [*stack, *[0] * (depth - len(stack))]
    cells[0], cells[depth - 1] = cells[depth - 1], cells[0]
    return _strip(tuple(cells))


def _add(*mappings: _Mapping) -> _Mapping:
    """Sum mappings, dropping zero weights, in a canonical order."""
    total: dict[_Stack, int] = {}
    for mapping in mappings:
        for stack, weight in mapping:
            total[stack] = total.get(stack, 0) + weight
    return tuple(sorted((s, w) for s, w in total.items() if w))


def _command(command: str, mapping: _Mapping) -> _Mapping:
    """Apply a command that rewrites the mapping stack by stack."""
    if command == "0":
        return ()
    if command == "-":
        return tuple((s, -w) for s, w in mapping)
    moved = []
    for stack, weight in mapping:
        result = _apply(command, stack)
        if result is not None:
            moved.append(((result, weight),))
    return _add(*moved)


def _advance(state: _State, program: _Program) -> _State:
    """Take one step: run a command, enter a group, or finish a frame."""
    frames, mapping = state
    _, seq, at = frames[-1]
    body = program[cast(int, seq)]
    if at == len(body):
        return _finish(frames[:-1], mapping)
    node = body[cast(int, at)]
    frames = (*frames[:-1], ("seq", seq, cast(int, at) + 1))
    if not mapping:
        return _State(frames, mapping)  # every command is a no-op
    if isinstance(node, str):
        return _State(frames, _command(node, mapping))
    kind, parts = node
    group: _Frame = (
        ("sum", parts, 1, mapping, ()) if kind == "sum" else ("loop", parts[0], mapping)
    )
    return _State((*frames, group, ("seq", parts[0], 0)), mapping)


def _finish(frames: tuple[_Frame, ...], mapping: _Mapping) -> _State:
    """Hand a finished sequence's mapping to the group that ran it."""
    if not frames:
        return _State((), mapping)
    frame, rest = frames[-1], frames[:-1]
    if frame[0] == "sum":
        _, branches, k, base, acc = frame
        parts, k = cast(tuple[int, ...], branches), cast(int, k)
        total = _add(cast(_Mapping, acc), mapping)
        if k == len(parts):
            return _State(rest, total)
        return _State(
            (*rest, ("sum", parts, k + 1, base, total), ("seq", parts[k], 0)),
            cast(_Mapping, base),
        )
    _, body, acc = frame
    total = _add(cast(_Mapping, acc), mapping)
    if not mapping:
        return _State(rest, total)
    return _State((*rest, ("loop", body, total), ("seq", body, 0)), mapping)


def _read_stack(text: str) -> _Stack:
    """Parse the input naturals, first on top."""
    values = []
    for token in text.split():
        if not token.isdecimal() or not token.isascii():
            raise HaltError(
                f"Caballo input {token!r} is not a natural number",
                hint="give whitespace-separated naturals, the top first",
            )
        values.append(int(token))
    return _strip(tuple(values))


def _render(stack: _Stack) -> str:
    """Write a stack in the wiki's notation, top first."""
    return "[" + ",".join(map(str, stack)) + "]"


class _Machine:
    """The run state: the pending frames, the mapping, and the halt."""

    reproducible_seed = 0
    #: Missing inputs are the endless zeros below the stack: an underfed
    #: run answers the row with those inputs 0.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO, rng: Randomness | None = None) -> None:
        self.io = io
        self._rng = rng
        self.program = parse(code)
        self.done = False
        # The input is the initial state, not a command's read, so it is
        # taken here and every step after is a pure transition.
        stack = _read_stack(io.input_all())
        self.state = _State((("seq", 0, 0),), ((stack, 1),))

    @property
    def halted(self) -> bool:
        return self.done

    @property
    def memory(self) -> list[object]:
        """The mapping, one ``(stack, weight)`` pair per entry."""
        return list(self.state.mapping)

    @property
    def stack(self) -> list[object]:
        """The pending frames' kinds, innermost last."""
        return [frame[0] for frame in self.state.frames]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.done, self.io.progress())

    def branching_snapshot(self) -> tuple[object, ...]:
        """Return the immutable state the branching search walks."""
        return self.snapshot()

    def branching_halted(self, state: object) -> bool:
        """Report whether ``state`` has finished and printed."""
        return bool(cast(tuple[object, ...], state)[2])

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[tuple[object, ...], ...] | None:
        """Return the one successor.

        The draw picks only what is printed, never the next state, so a
        step has a single successor however the draw falls.
        """
        frames, mapping, done, progress = cast(tuple[object, ...], state)
        if done:
            return (cast(tuple[object, ...], state),)
        moved = _advance(
            _State(cast(tuple[_Frame, ...], frames), cast(_Mapping, mapping)),
            self.program,
        )
        return ((*moved, not moved.frames, progress),)

    def step(self) -> None:
        """Advance one step; draw and print once the frames run out."""
        if self.done:
            return
        self.state = _advance(self.state, self.program)
        if not self.state.frames:
            self.done = True
            self._output()

    def _output(self) -> None:
        """Drop negative weights, then print one stack drawn by weight."""
        kept = [(s, w) for s, w in self.state.mapping if w > 0]
        if not kept:
            return
        if len(kept) == 1:
            self.io.print_str(_render(kept[0][0]))
            return
        ticket = draw(self._rng, sum(w for _, w in kept))
        for stack, weight in kept:
            if ticket < weight:
                self.io.print_str(_render(stack))
                return
            ticket -= weight


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    """Run a Caballo program on the input stack and print one result."""
    machine = _Machine(code, io, rng)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
