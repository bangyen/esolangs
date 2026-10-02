"""Execute a Line program's walked path tree against a Brainfuck-style tape.

:mod:`extract` traces a drawing once; a loop (``?`` turning back on
itself) revisits the same fork many times, so this walks the same tree
repeatedly.  The wiki (https://esolangs.org/wiki/Line, "Unimplemented")
leaves much unspecified; the choices here:

* Tape: unbounded both ways, arbitrary-precision ints (no wrap or width
  is documented), an immutable sparse tape whose pointer may go negative.
* Initial state: all zeros, pointer at 0.
* ``+``/``-``: by 1, run ``count`` times for a merged run of repeats.
* ``<``/``>``, ``i``/``o``: per the wiki's wording.
* ``?``: "turn right if the current cell is 0, otherwise turn left",
  taken literally -- a zero cell walks ``zero``.  Correct only because
  ``lattice._classify`` names arms in the cursor's frame (see :func:`run`).
* Termination: execution ends where the drawn path ends (a stroke-tree
  leaf).  A program with no reachable leaf never halts, and :func:`run`
  imposes no step limit, like every other interpreter's plain ``run``.

Loops are drawn, not encoded: a stroke reconnects to a pixel it passed
earlier.  :mod:`lattice`'s walker stops at an already-visited vertex as an
unlinked dead end; :func:`_compile` recovers the link.  ``addition.png``'s
loop-body arm merges into the *middle* of its stem's straight run
(``(42, 159)`` between ``(62, 159)`` and ``(22, 159)``), which an
exact-vertex match missed and reported loop-free; ``find_merge`` now
checks a leaf's final vertex against every other stroke's final vertex
and every straight leg (exact integer collinearity, since every segment
is one of 8 compass directions).  Any *other* vertex is never a match:
sibling arms share the fork's corner.  A match resumes from that point,
running only the ops not yet run (:func:`extract.OpCall`'s ``index``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .extract import DEFAULT_UNIT, OpCall, Stroke, Vertex, classify_ops

if TYPE_CHECKING:
    from .render import Node


@dataclass
class IO:
    """Pluggable input/output for :func:`run`, mirroring `i`/`o`'s wiki wording.

    The default is the terminal; tests swap in ``read``/``write``.
    """

    read: Callable[[], int] = field(default=lambda: int(input("Input: ")))
    write: Callable[[int], None] = field(default=lambda value: print(value))


@dataclass
class _Compiled:
    """One stroke's classified ops plus its two possible next strokes.

    Built once per :class:`extract.Stroke` so a looping run never
    re-classifies.  ``goto`` is set only for a leaf whose path reconnects,
    and may be a synthetic resume point (the tail of another stroke's ops,
    sharing its children) rather than a real stroke.
    """

    ops: list[OpCall]
    end: tuple[int, int]
    zero: _Compiled | None
    nonzero: _Compiled | None
    # A leaf's loop-back (see _compile): another node, or a resume point
    # holding only the ops not yet run at the merge.
    goto: _Compiled | None = None
    positions: tuple[tuple[int, int], ...] = ()


def _compile(stroke: Stroke, unit: int) -> _Compiled:
    """Classify every stroke in ``stroke``'s tree exactly once, recursively.

    Also recovers the loop-back link: every leaf's final vertex is tested by
    ``find_merge`` against every other stroke's final vertex and straight
    legs (exact integer cross/dot product; no tolerance needed).  A match on
    a stroke's own final vertex resumes at that node; a mid-leg match builds
    a synthetic node holding the remaining ops.  A stroke never matches its
    own final vertex.  The whole tree is built before linking, since a target
    can be defined after the leaf that jumps to it.
    """
    # Every real stroke's geometry, for find_merge below.
    strokes: list[tuple[_Compiled, list[Vertex], list[OpCall]]] = []
    leaves: list[_Compiled] = []
    resume_cache: dict[tuple[int, int], _Compiled] = {}

    def build(node: Stroke) -> _Compiled:
        ops = classify_ops(node.vertices, unit)
        last = node.vertices[-1]
        compiled = _Compiled(
            ops=ops,
            end=(last.y, last.x),
            zero=None,
            nonzero=None,
            positions=tuple(
                (node.vertices[call.index].y, node.vertices[call.index].x)
                for call in ops
            ),
        )
        if node.zero is not None:
            compiled.zero = build(node.zero)
        if node.nonzero is not None:
            compiled.nonzero = build(node.nonzero)
        if compiled.zero is None and compiled.nonzero is None:
            leaves.append(compiled)
        strokes.append((compiled, node.vertices, ops))
        return compiled

    def resume(target: _Compiled, remaining: list[OpCall]) -> _Compiled:
        if remaining == target.ops:
            return target
        key = id(target), len(remaining)
        if key not in resume_cache:
            resume_cache[key] = _Compiled(
                ops=remaining,
                end=target.end,
                zero=target.zero,
                nonzero=target.nonzero,
                goto=target.goto,
                positions=tuple(
                    target.positions[target.ops.index(call)] for call in remaining
                ),
            )
        return resume_cache[key]

    def find_merge(
        point: tuple[int, int], exclude: _Compiled
    ) -> tuple[_Compiled, list[OpCall]] | None:
        py, px = point
        for target, vertices, ops in strokes:
            if target is exclude:
                # A leaf trivially matches its own final vertex; skip it.
                continue
            last = vertices[-1]
            if (last.y, last.x) == point:
                # Its own final vertex is a fork or dead end, never a shared
                # corner: the common case, a loop-back right at a `?`.
                return target, []
            for i in range(len(vertices) - 1):
                v0, v1 = vertices[i], vertices[i + 1]
                # Strictly interior, interior vertices excluded: sibling
                # arms share the fork's corner (a synthetic test matched an
                # unrelated arm), and a real merge lands inside a leg
                # (addition.png's does).
                dy, dx = v1.y - v0.y, v1.x - v0.x
                oy, ox = py - v0.y, px - v0.x
                if dy * ox - dx * oy != 0:
                    continue
                t_num = oy * dy + ox * dx
                t_den = dy * dy + dx * dx
                if 0 < t_num < t_den:
                    return target, [c for c in ops if c.index >= i + 1]
        return None

    root = build(stroke)
    for leaf in leaves:
        match = find_merge(leaf.end, exclude=leaf)
        if match is None:
            continue
        target, remaining = match
        leaf.goto = resume(target, remaining)
    return root


def compile_program(stroke: Stroke, unit: int = DEFAULT_UNIT) -> _Compiled:
    """Compile ``stroke`` once for repeated :func:`run_compiled` calls."""
    return _compile(stroke, unit)


type _Tape = tuple[tuple[int, int], ...]
type _State = tuple[int | None, int, int, _Tape]


@dataclass(frozen=True)
class _Frame:
    ops: tuple[tuple[str, int], ...]
    positions: tuple[tuple[int, int], ...]
    end: tuple[int, int]
    zero: int | None
    nonzero: int | None
    goto: int | None


def _freeze_program(root: _Compiled) -> tuple[_Frame, ...]:
    """Return immutable instructions and indexed control links."""
    nodes = [root]
    indices = {id(root): 0}
    for node in nodes:
        for child in (node.zero, node.nonzero, node.goto):
            if child is not None and id(child) not in indices:
                indices[id(child)] = len(nodes)
                nodes.append(child)
    return tuple(
        _Frame(
            tuple((call.op, call.count) for call in node.ops),
            node.positions,
            node.end,
            indices.get(id(node.zero)),
            indices.get(id(node.nonzero)),
            indices.get(id(node.goto)),
        )
        for node in nodes
    )


def _written(tape: _Tape, pointer: int, value: int) -> _Tape:
    cells = dict(tape)
    cells[pointer] = value
    return tuple(sorted(cells.items()))


def _advance(
    state: _State, program: tuple[_Frame, ...], value: int | None = None
) -> tuple[_State, int | None]:
    """Return a pure Line transition and optional numeric output."""
    node, at, pointer, tape = state
    if node is None:
        return state, None
    frame = program[node]
    cell = dict(tape).get(pointer, 0)
    if at == len(frame.ops):
        if frame.zero is None and frame.nonzero is None:
            node = frame.goto
        else:
            tape = _written(tape, pointer, cell)
            node = frame.zero if cell == 0 else frame.nonzero
        return (node, 0, pointer, tape), None
    op, count = frame.ops[at]
    output = None
    if op == "+":
        tape = _written(tape, pointer, cell + count)
    elif op == "-":
        tape = _written(tape, pointer, cell - count)
    elif op == ">":
        pointer += 1
    elif op == "<":
        pointer -= 1
    elif op == "i":
        if value is None:
            raise ValueError("input transition requires a value")
        tape = _written(tape, pointer, value)
    elif op == "o":
        tape = _written(tape, pointer, cell)
        output = cell
    else:  # pragma: no cover - classification emits only these opcodes
        raise ValueError(f"unknown opcode {op!r}")
    return (node, at + 1, pointer, tape), output


def _drive(program: tuple[_Frame, ...], io: IO) -> _Tape:
    state: _State = (0, 0, 0, ())
    node = state[0]
    while node is not None:
        at = state[1]
        frame = program[node]
        value = io.read() if at < len(frame.ops) and frame.ops[at][0] == "i" else None
        state, output = _advance(state, program, value)
        if output is not None:
            io.write(output)
        node = state[0]
    return state[3]


def run_compiled(program: _Compiled, io: IO | None = None) -> dict[int, int]:
    """Run compiled code with immutable state, returning its final tape."""
    return dict(_drive(_freeze_program(program), IO() if io is None else io))


def run_node(root: Node, io: IO) -> None:
    """Execute generated graph code through the same pure transition core."""
    nodes = [root]
    indices = {id(root): 0}
    for node in nodes:
        for child in (node.zero, node.nonzero, node.next, node.goto):
            if child is not None and id(child) not in indices:
                indices[id(child)] = len(nodes)
                nodes.append(child)
    frames = tuple(
        _Frame(
            ((node.op, 1),) if node.op in {"+", "-", ">", "<", "i", "o"} else (),
            ((0, 0),),
            (0, 0),
            indices.get(id(node.zero)) if node.op == "?" else None,
            indices.get(id(node.nonzero)) if node.op == "?" else None,
            None if node.op == "?" else indices.get(id(node.next or node.goto)),
        )
        for node in nodes
    )
    _drive(frames, io)


def run(
    stroke: Stroke,
    io: IO | None = None,
    unit: int = DEFAULT_UNIT,
) -> dict[int, int]:
    """Execute ``stroke``'s full walked tree, returning the final tape.

    Each stroke's ops run in order; a leaf halts unless its ``goto`` jumps
    back; a stroke with children is a ``?`` choosing by the current cell.
    A zero cell takes ``zero``, per the wiki -- correct only because
    :func:`lattice._classify` names arms relative to the *heading*; an
    earlier version rotated off ``back`` (180 degrees out) and this function
    swapped the children to compensate.  No termination guard: the wiki
    documents none, and no other interpreter's plain ``run`` imposes one.
    """
    return run_compiled(compile_program(stroke, unit), io)


if __name__ == "__main__":
    import sys

    from .extract import extract

    result = extract(sys.argv[1])
    final_tape = run(result)
    nonzero_cells = {k: v for k, v in sorted(final_tape.items()) if v != 0}
    print(f"final tape (nonzero cells): {nonzero_cells}")
