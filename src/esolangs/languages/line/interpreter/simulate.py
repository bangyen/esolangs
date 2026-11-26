"""Execute a Line program's walked path tree against a Brainfuck-style tape.

:mod:`extract` traces a drawing once; a loop (``?`` turning back on
itself) revisits the same fork many times, so this walks the same tree
repeatedly.  The wiki (https://esolangs.org/wiki/Line, "Unimplemented")
leaves much unspecified; the choices here:

* Tape: unbounded both ways, arbitrary-precision ints (no wrap or width
  is documented), a sparse tape whose pointer may go negative.
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
unlinked dead end; :func:`_compile` recovers the link.  ``find_merge``
checks a leaf's final vertex against every other stroke's final vertex
and every straight leg (exact integer collinearity, since every segment
is one of 8 compass directions); an exact-vertex match alone would miss
a merge into the middle of a leg.  Any *other* vertex is never a match:
sibling arms share the fork's corner.  A match resumes from that point,
running only the ops not yet run (:func:`extract.OpCall`'s ``index``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from esolangs.runtime.source_hints import syntax_error

from .extract import OpCall, classify_ops
from .lattice import Stroke, Vertex

if TYPE_CHECKING:
    from esolangs.languages.line.generator.layout import Node


@dataclass
class IO:
    """Pluggable input/output for :func:`run`, mirroring `i`/`o`'s wiki wording.

    The default is the terminal; tests swap in ``read``/``write``.
    """

    read: Callable[[], int] = field(default=lambda: int(input("Input: ")))
    write: Callable[[int], None] = field(default=print)


@dataclass
class _Compiled:
    """One stroke's classified ops plus its two possible next strokes.

    Built once per :class:`lattice.Stroke` so a looping run never
    re-classifies.  ``goto`` is set only for a leaf whose path reconnects,
    with an instruction offset into the target stroke.
    """

    ops: list[OpCall]
    end: tuple[int, int]
    zero: _Compiled | None
    nonzero: _Compiled | None
    goto: _Compiled | _Resume | None = None
    positions: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class _Resume:
    """A stroke suffix retains the continuation bound when its merge was linked."""

    target: _Compiled
    offset: int
    goto: _Compiled | _Resume | None


class _TreeCompiler:
    """State for one :func:`_compile` pass over a stroke tree.

    ``strokes`` registers every real stroke's geometry for
    :meth:`find_merge`; ``leaves`` collects the strokes with no branch
    children, whose loop-back links are resolved once the whole tree is
    built.
    """

    def __init__(self, unit: int) -> None:
        self.unit = unit
        self.strokes: list[tuple[_Compiled, list[Vertex], list[OpCall]]] = []
        self.leaves: list[_Compiled] = []

    def compile(self, stroke: Stroke) -> _Compiled:
        """Build the tree, then link each leaf's loop-back, if it has one."""
        root = self.build(stroke)
        resumes: dict[tuple[int, int], _Resume] = {}
        for leaf in self.leaves:
            match = self.find_merge(leaf.end, exclude=leaf)
            if match is None:
                continue
            target, offset = match
            if offset:
                key = id(target), offset
                if key not in resumes:
                    resumes[key] = _Resume(target, offset, target.goto)
                leaf.goto = resumes[key]
            else:
                leaf.goto = target
        return root

    def build(self, node: Stroke) -> _Compiled:
        """Classify one stroke and, recursively, its branch children."""
        ops = classify_ops(node.vertices, self.unit)
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
            compiled.zero = self.build(node.zero)
        if node.nonzero is not None:
            compiled.nonzero = self.build(node.nonzero)
        if compiled.zero is None and compiled.nonzero is None:
            self.leaves.append(compiled)
        self.strokes.append((compiled, node.vertices, ops))
        return compiled

    def find_merge(
        self, point: tuple[int, int], exclude: _Compiled
    ) -> tuple[_Compiled, int] | None:
        """Find where a leaf ending at ``point`` reconnects, if anywhere.

        Tests every other stroke's final vertex, then every straight leg
        (exact integer cross/dot product; no tolerance needed).
        """
        py, px = point
        for target, vertices, ops in self.strokes:
            if target is exclude:
                # A leaf trivially matches its own final vertex; skip it.
                continue
            last = vertices[-1]
            if (last.y, last.x) == point:
                # Its own final vertex is a fork or dead end, never a shared
                # corner: the common case, a loop-back right at a `?`.
                return target, len(ops)
            for i in range(len(vertices) - 1):
                v0, v1 = vertices[i], vertices[i + 1]
                # Strictly interior: sibling arms share the fork's corner,
                # and a merge lands inside a leg.
                dy, dx = v1.y - v0.y, v1.x - v0.x
                oy, ox = py - v0.y, px - v0.x
                if dy * ox - dx * oy != 0:
                    continue
                t_num = oy * dy + ox * dx
                t_den = dy * dy + dx * dx
                if 0 < t_num < t_den:
                    return target, next(
                        (at for at, call in enumerate(ops) if call.index > i), len(ops)
                    )
        return None


def _compile(stroke: Stroke, unit: int) -> _Compiled:
    """Classify every stroke in ``stroke``'s tree exactly once, recursively.

    Also recovers the loop-back link: every leaf's final vertex is tested by
    ``find_merge`` against every other stroke's final vertex and straight
    legs (exact integer cross/dot product; no tolerance needed).  A match on
    another stroke resumes at the first operation beyond the merge.  A target
    can be defined after the leaf that jumps to it.
    """
    return _TreeCompiler(unit).compile(stroke)


def compile_program(stroke: Stroke, unit: int | None = None) -> _Compiled:
    """Compile ``stroke`` once for repeated :func:`run_compiled` calls."""
    return _compile(stroke, stroke.unit if unit is None else unit)


type _Cursor = tuple[int | None, int, int]


@dataclass(frozen=True)
class _Frame:
    ops: tuple[tuple[str, int], ...]
    positions: tuple[tuple[int, int], ...]
    end: tuple[int, int]
    zero: int | None
    nonzero: int | None
    goto: int | None
    offset: int = 0


def _index_graph[T](
    root: T, children: Callable[[T], tuple[T | None, ...]]
) -> tuple[list[T], dict[int, int]]:
    """Return the nodes reachable from ``root``, breadth first, and index by id."""
    nodes = [root]
    indices = {id(root): 0}
    for node in nodes:
        for child in children(node):
            if child is not None and id(child) not in indices:
                indices[id(child)] = len(nodes)
                nodes.append(child)
    return nodes, indices


def _freeze_program(root: _Compiled) -> tuple[_Frame, ...]:
    """Return immutable instructions and indexed control links."""

    def successors(
        entry: _Compiled | _Resume,
    ) -> tuple[_Compiled | _Resume | None, ...]:
        node = entry.target if isinstance(entry, _Resume) else entry
        return node.zero, node.nonzero, entry.goto

    first: _Compiled | _Resume = root
    entries, indices = _index_graph(first, successors)
    instructions: dict[int, tuple[tuple[str, int], ...]] = {}
    frames = []
    for entry in entries:
        node = entry.target if isinstance(entry, _Resume) else entry
        offset = entry.offset if isinstance(entry, _Resume) else 0
        if id(node) not in instructions:
            instructions[id(node)] = tuple((call.op, call.count) for call in node.ops)
        frames.append(
            _Frame(
                instructions[id(node)],
                node.positions,
                node.end,
                indices.get(id(node.zero)),
                indices.get(id(node.nonzero)),
                indices.get(id(entry.goto)),
                offset,
            )
        )
    return tuple(frames)


def _advance(
    cursor: _Cursor, program: tuple[_Frame, ...], cell: int, value: int | None = None
) -> tuple[_Cursor, int | None, int | None]:
    """Return the next cursor, an optional current-cell write, and output."""
    node, at, pointer = cursor
    if node is None:
        return cursor, None, None
    frame = program[node]
    if frame.offset + at == len(frame.ops):
        if frame.zero is None and frame.nonzero is None:
            return (frame.goto, 0, pointer), None, None
        node = frame.zero if cell == 0 else frame.nonzero
        return (node, 0, pointer), cell, None
    op, count = frame.ops[frame.offset + at]
    write = output = None
    if op == "+":
        write = cell + count
    elif op == "-":
        write = cell - count
    elif op == ">":
        pointer += 1
    elif op == "<":
        pointer -= 1
    elif op == "i":
        if value is None:
            raise syntax_error(
                "input transition requires a value",
                "supply the input value before applying the input transition",
            )
        write = value
    elif op == "o":
        write = cell
        output = cell
    else:  # pragma: no cover - classification emits only these opcodes
        raise syntax_error(
            f"unknown opcode {op!r}", "use an opcode from the extracted Line program"
        )
    return (node, at + 1, pointer), write, output


def _needs_input(program: tuple[_Frame, ...], state: _Cursor) -> bool:
    """Whether the next step reads a number, so the shell must feed one.

    Pure: reading the opcode is not evaluating it.  Naming the question
    separately keeps ``_advance`` free of any caller it would have to ask.
    """
    node, at = state[0], state[1]
    if node is None:
        return False
    frame = program[node]
    return frame.offset + at < len(frame.ops) and frame.ops[frame.offset + at][0] == "i"


def _drive(program: tuple[_Frame, ...], io: IO) -> dict[int, int]:
    """Drive the frames with a private sparse tape."""
    tape: dict[int, int] = {}
    cursor: _Cursor = (0, 0, 0)
    while cursor[0] is not None:
        pointer = cursor[2]
        value = io.read() if _needs_input(program, cursor) else None
        cursor, write, output = _advance(cursor, program, tape.get(pointer, 0), value)
        if output is not None:
            io.write(output)
        if write is not None:
            tape[pointer] = write
    return tape


def run_compiled(program: _Compiled, io: IO | None = None) -> dict[int, int]:
    """Run compiled code, returning its final tape."""
    return _drive(_freeze_program(program), IO() if io is None else io)


def _freeze_node(root: Node) -> tuple[_Frame, ...]:
    """Index generated graph instructions without extracting the raster."""
    nodes, indices = _index_graph(
        root, lambda node: (node.zero, node.nonzero, node.next, node.goto)
    )
    return tuple(
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


def run_node(root: Node, io: IO) -> None:
    """Execute generated graph code through the same pure transition core."""
    _drive(_freeze_node(root), io)


def run(
    stroke: Stroke,
    io: IO | None = None,
    unit: int | None = None,
) -> dict[int, int]:
    """Execute ``stroke``'s full walked tree, returning the final tape.

    Each stroke's ops run in order; a leaf halts unless its ``goto`` jumps
    back; a stroke with children is a ``?`` choosing by the current cell.
    A zero cell takes ``zero``, per the wiki -- correct only because
    :func:`lattice._classify` names arms relative to the *heading* (right
    in the cursor's frame).  No termination guard: the wiki documents
    none, and no other interpreter's plain ``run`` imposes one.
    """
    return run_compiled(compile_program(stroke, unit), io)


if __name__ == "__main__":
    import sys

    from .extract import extract

    result = extract(sys.argv[1])
    final_tape = run(result)
    nonzero_cells = {k: v for k, v in sorted(final_tape.items()) if v != 0}
    print(f"final tape (nonzero cells): {nonzero_cells}")
