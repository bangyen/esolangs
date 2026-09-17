"""Execute a Line program's walked path tree against a Brainfuck-style tape.

:mod:`extract` traces a drawing once; a loop (``?`` turning back on
itself) revisits the same fork many times, so this walks the same tree
repeatedly.  The wiki (https://esolangs.org/wiki/Line, "Unimplemented")
leaves much unspecified; the choices here:

* Tape: unbounded both ways, arbitrary-precision ints (no wrap or width
  is documented), a ``defaultdict(int)`` on a pointer that may go negative.
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

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from .extract import DEFAULT_UNIT, OpCall, Stroke, Vertex, classify_ops


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
        compiled = _Compiled(ops=ops, end=(last.y, last.x), zero=None, nonzero=None)
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


def run_compiled(program: _Compiled, io: IO | None = None) -> dict[int, int]:
    """Run a program returned by :func:`compile_program`."""
    if io is None:
        io = IO()
    tape: dict[int, int] = defaultdict(int)
    pointer = 0

    node: _Compiled | None = program
    while node is not None:
        for call in node.ops:
            if call.op == "+":
                tape[pointer] += call.count
            elif call.op == "-":
                tape[pointer] -= call.count
            elif call.op == ">":
                pointer += 1
            elif call.op == "<":
                pointer -= 1
            elif call.op == "i":
                tape[pointer] = io.read()
            elif call.op == "o":
                io.write(tape[pointer])
            else:  # pragma: no cover - defensive, classify_ops emits no others
                raise ValueError(f"unknown opcode {call.op!r}")

        if node.zero is None and node.nonzero is None:
            node = node.goto
            if node is None:
                return dict(tape)
            continue
        node = node.zero if tape[pointer] == 0 else node.nonzero

    return dict(tape)


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
