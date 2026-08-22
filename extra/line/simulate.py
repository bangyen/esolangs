"""Execute a Line program's walked path tree against a Brainfuck-style tape.

Counterpart to :mod:`extract`, which only traces a drawing's structure once
(see its module docstring and ``WIP.md``'s "deliberately out of scope"
section): a real run needs to walk the *same* tree repeatedly, since a loop
(built from ``?`` turning back on itself) revisits the same branch pixel many
times, taking a different arm each time depending on current tape state.
This module adds that repeated walk on top of :mod:`extract`'s one-time
structural trace, without changing it.

Line's own wiki page (https://esolangs.org/wiki/Line, tagged
"Unimplemented", no reference implementation) documents each opcode only
loosely and leaves several details unspecified entirely -- this module's
choices, and why, where the wiki is silent:

* **Tape**: "its own memory tape (like in Brainfuck)", unbounded in both
  directions, of cells holding arbitrary-precision integers -- no wraparound
  or bit width is documented anywhere on the page, so cells are plain Python
  ints rather than being masked to a byte the way most Brainfuck derivatives
  are.  Implemented as a ``defaultdict(int)`` keyed by an integer pointer
  that can go negative, matching a tape with no documented left bound either.
* **Initial state**: every cell starts at 0, pointer starts at cell 0 --
  the universal Brainfuck-family default the wiki gives no reason to depart
  from.
* **`+`/`-`**: increment/decrement the current cell by 1 each, per the
  wiki's own wording ("going through this diagonal line will increment the
  selected cell" / "...decrement it") -- run ``count`` times for a merged
  run of repeats (see :mod:`render`'s module docstring for why those merge
  into one stroke; :func:`extract.classify_ops` already recovers the count
  from the merged run's length).
* **`<`/`>`**: move the pointer left/right by one cell, per the wiki's own
  wording ("move the pointer to the left"/"...right").
* **`i`/`o`**: read a number into the current cell / print the current
  cell as a number, per the wiki's own wording -- hence the letters (input/
  output), matching :mod:`render`'s and :mod:`extract`'s existing opcode
  names for these two curves.
* **`?`**: "turn right if the current cell is 0, otherwise...turn left",
  quoted directly from the wiki.  Naively, that would mean taking the
  walked ``Stroke.zero`` child on a zero cell -- but :mod:`lattice`'s
  ``zero``/``nonzero`` field names turn out not to mean that; see
  :func:`run`'s own docstring for the concrete mismatch this module
  corrects for.
* **Termination**: the wiki does not describe a halt condition at all.  The
  natural reading of "cursor follows a drawn curve" is that execution ends
  wherever the drawn path itself ends -- a stroke tree leaf (no ``zero``/
  ``nonzero`` children) in :mod:`lattice`'s terms -- rather than some
  separate halt opcode the wiki never mentions.  A program whose only path
  is a cycle with no reachable leaf then genuinely never halts, and
  :func:`run` does not impose any step limit to paper over that --
  matching every other interpreter's plain ``run(code, io)`` in this repo
  (e.g. ``brainfuck.py``'s own ``run`` is a bare
  ``while not machine.halted: machine.step()``, with no cap; cycle
  detection exists only in ``src/esolangs/vm.py``, an opt-in debugger
  wrapper no language's main run path uses).  A non-halting Line program
  hangs, same as an infinite Brainfuck ``[]`` loop would.

Real loops (``?`` turning back on itself so the same fork is reached again
later, the only way Line can express repetition at all -- there is no other
control-flow opcode) are drawn, not encoded structurally: a stroke's path
physically reconnects to a pixel it already passed through earlier in the
same drawing.  :mod:`lattice`'s walker (see its own module docstring)
already stops a stroke the moment it walks onto any vertex already visited
elsewhere in the tree -- but only as an unlinked dead end, recording just
that vertex's coordinates and nothing pointing back to the earlier node they
match, since :func:`extract.extract_tree` only ever needed a one-time
structural trace (see above).  :func:`_compile` recovers that missing link
itself, entirely within this module and without changing ``lattice.py`` or
``extract.py``.

Confirmed on a real wiki fixture, not just reasoned about: ``addition.png``'s
loop-body arm (the walked stroke ending at ``(42, 159)``) merges back into
the *middle* of the incoming stem's own path -- ``(42, 159)`` sits exactly on
the straight run between two of that stem's own vertices, ``(62, 159)`` and
``(22, 159)``, rather than landing on any recorded vertex at all.  A first
version of this module only matched a fork's own *final* vertex exactly, so
it missed this case entirely and reported ``addition.png`` as loop-free --
wrong, caught by inspecting the actual image rather than trusting the
coordinate check's silence.  :func:`_compile`'s ``find_merge`` now checks a
leaf's final vertex two ways against every other stroke: an exact match on
that stroke's own *final* vertex (a real fork or dead end -- the original,
still-correct case), or a point landing *strictly inside* one of its
straight legs (exact integer collinearity + betweenness, since every Line
segment runs along one of 8 compass directions -- no tolerance needed).
Landing on any *other* vertex is deliberately never treated as a match: a
fork's two children always start exactly at the fork's own end coordinate
by construction, so testing bare vertex equality matches every sibling arm
sharing that corner, not just a real continuation (confirmed to misfire
this way on a synthetic test).  Either matching case resumes execution from
exactly that point, running only the ops that had not yet run there (via
:func:`extract.OpCall`'s own ``index``) rather than replaying the whole
stroke, then continuing normally into that stroke's own fork or further
``goto``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from extract import DEFAULT_UNIT, OpCall, Stroke, Vertex, classify_ops


@dataclass
class IO:
    """Pluggable input/output for :func:`run`, mirroring `i`/`o`'s wiki wording.

    The default reads from and writes to the real terminal; tests and other
    callers can swap in their own ``read``/``write`` to drive a program from
    a fixed input list and capture its output, without monkeypatching
    ``input``/``print``.
    """

    read: Callable[[], int] = field(default=lambda: int(input("Input: ")))
    write: Callable[[int], None] = field(default=lambda value: print(value))


@dataclass
class _Compiled:
    """One stroke's classified ops plus its two possible next strokes.

    :func:`_compile` builds one of these per :class:`extract.Stroke` up
    front so :func:`run`'s hot loop never re-classifies the same stroke's
    ops on a later visit -- load-bearing for a looping program, which by
    construction revisits the same stroke many times (see module
    docstring).  ``goto`` is set only for a leaf (``zero``/``nonzero`` both
    ``None``) whose drawn path reconnects to an earlier point -- see
    :func:`_compile`'s own docstring for how that is recovered.  A ``goto``
    target may itself be a synthetic *resume point* built by
    :func:`_compile` (only the tail of some other stroke's ``ops``, sharing
    that stroke's ``zero``/``nonzero``/``goto``) rather than a node that
    corresponds 1:1 to a real :class:`extract.Stroke` -- see
    :func:`_compile`'s ``by_vertex`` index for why.
    """

    ops: list[OpCall]
    end: tuple[int, int]
    zero: _Compiled | None
    nonzero: _Compiled | None
    # Set only on a leaf whose drawn path reconnects to an earlier point
    # (see _compile).  Points directly at whatever should run next --
    # either another stroke's own node, or a resume point covering just its
    # remaining ops -- deliberately bypassing any ops that already ran the
    # first time that point was reached, since a real loop-back must not
    # replay them every iteration.
    goto: _Compiled | None = None


def _compile(stroke: Stroke, unit: int) -> _Compiled:
    """Classify every stroke in ``stroke``'s tree exactly once, recursively.

    Also recovers the loop-back link :mod:`lattice`'s walker discards (see
    module docstring): every leaf's *final* vertex is tested, via
    :func:`find_merge`, against every other stroke's own vertex/segment
    geometry -- either an exact match on that *other* stroke's own final
    vertex (always a real fork or dead end), or a point landing strictly
    inside one of its straight legs (collinear with, and strictly between,
    two consecutive vertices; every Line segment runs along one of 8 compass
    directions -- see ``render.py``'s module docstring -- so an exact
    integer cross-product/dot-product check is enough, no tolerance needed).
    A match means the drawing's ink physically reconnects there, and the
    leaf's ``goto`` is wired to a jump that skips whatever ops (by
    :class:`extract.OpCall`'s own ``index``, the run a kink starts at)
    already ran up to that point.

    Checking mid-segment points, not just exact vertex matches, matters: a
    real wiki fixture (``addition.png``, confirmed by inspecting the image
    directly after an exact-vertex-only version of this function reported it
    as loop-free, which was wrong) merges its loop-body arm back into the
    *middle* of the incoming stem's path -- a point between two of that
    stem's own vertices, not on any recorded vertex at all.  When the match
    falls exactly on a stroke's *own* final vertex, the resume point *is*
    that stroke's node (no ops to skip -- the whole stroke already ran).
    Otherwise a synthetic resume node is built, holding only that stroke's
    ops from the merge point onward and sharing its
    ``zero``/``nonzero``/``goto`` -- so a merge partway through a stroke
    with real opcodes still remaining (not the case in ``addition.png``'s
    own merge, but not excluded either) still runs exactly those remaining
    ops once per pass, not the whole stroke from its own start.

    A vertex's *own* stroke is excluded from matching itself at that same
    vertex (a stroke's own final vertex trivially "matches" itself, which
    would make every leaf loop back to itself instead of a real halt).

    Building the whole tree before linking (rather than linking as each
    node is built) matters because a loop-back target can be defined
    *after* the leaf that jumps to it in build order -- e.g. a fork's
    ``zero`` arm looping back to the fork itself, which is built before
    ``walk_tree`` ever recurses into ``zero``.
    """
    # Every real (non-resume-point) stroke's own vertex/segment geometry,
    # kept alongside its compiled node and full ops list so a leaf's end
    # point can be tested against it (see find_merge below) -- both exact
    # vertex hits and a point landing partway along a segment.
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
                # A leaf's own final vertex/segment trivially "matches"
                # itself (it is where point came from); skip its own stroke
                # entirely rather than checking `target is leaf` after the
                # fact, so the search keeps going to find a real match on a
                # *different* stroke instead of stopping here.
                continue
            last = vertices[-1]
            if (last.y, last.x) == point:
                # This stroke's own final vertex -- always a real decision
                # point (a fork) or a genuine dead end, never an arbitrary
                # shared corner, so matching it exactly is safe and is the
                # common case: a loop-back reconnecting right at a `?`.
                return target, []
            for i in range(len(vertices) - 1):
                v0, v1 = vertices[i], vertices[i + 1]
                # Strictly interior to this segment -- (v0, v1) exclusive on
                # both ends.  Landing exactly on an interior *vertex*
                # (a corner within the stroke, not its own final one) is
                # deliberately excluded too, not just v0/v1 of the specific
                # segment being tested: every fork's two children start at
                # exactly the fork's own end coordinate by construction, so
                # a vertex-equality test alone matches *every* sibling arm
                # sharing that corner, not just a real continuation --
                # confirmed to misfire on a synthetic loop test, where it
                # matched an unrelated 1-segment sibling arm that happened to
                # start at the same point instead of the real ancestor fork.
                # A genuine drawn merge, by contrast, touches down *inside*
                # a real leg's own ink (confirmed on fixtures/addition.png's
                # merge point, which sits partway along the incoming stem's
                # straight run, not on any of its recorded vertices) -- so
                # requiring strict interior containment for anything other
                # than a stroke's own final vertex is not just a tiebreak,
                # it is what a real merge actually looks like geometrically.
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


def run(
    stroke: Stroke,
    io: IO | None = None,
    unit: int = DEFAULT_UNIT,
) -> dict[int, int]:
    """Execute ``stroke``'s full walked tree, returning the final tape.

    ``stroke`` is normally :func:`extract.extract`'s return value.  Each
    stroke's ops run in order; reaching a stroke with no ``zero``/``nonzero``
    children halts the program, unless its path reconnects to an earlier
    node (a real drawn loop -- see :func:`_compile`'s ``goto``), in which
    case execution jumps back there instead.  A stroke with children is a
    ``?``: after its own ops run, the *next* stroke is chosen by the current
    cell's value.

    This is where :mod:`lattice`'s ``Stroke.zero``/``Stroke.nonzero`` field
    *names* are actually misleading for execution, not just cosmetically
    different from ``render.py``'s own labeling as ``WIP.md`` describes:
    ``lattice._classify`` computes its ``right``/``left`` fork options
    relative to ``back`` (the direction arrived *from*), while
    ``render.py``'s ``_turn_right``/``_turn_left`` rotate relative to
    ``heading`` (the direction arrived *in*, the opposite of ``back``) --
    two rotations 180 degrees apart, which swaps which physical arm each
    walker calls "right" vs "left".  Confirmed concretely, not just derived
    algebraically: a synthetic ``render.py`` program with
    ``Node("?", zero=chain("+","+"), nonzero=chain("-",">"))`` -- whose
    ``zero`` arm render.py draws turning right, matching the wiki's "turn
    right if 0" -- round-trips through ``extract()`` with cell value 0
    actually taking the walked ``Stroke.nonzero`` child (the ``+, +`` arm),
    and a nonzero cell taking ``Stroke.zero`` (the ``-, >`` arm).  So this
    function takes the walked ``nonzero`` child on a zero cell and ``zero``
    on a nonzero cell -- the swap is intentional and load-bearing, not a
    typo.

    Does not guard against non-termination: a program whose only path is a
    cycle with no reachable dead end genuinely never halts, and this
    function hangs right along with it -- the wiki does not document a halt
    condition at all (see module docstring), and no other interpreter in
    this repo's plain ``run(code, io)`` imposes a step limit either.
    """
    if io is None:
        io = IO()
    compiled = _compile(stroke, unit)
    tape: dict[int, int] = defaultdict(int)
    pointer = 0

    node: _Compiled | None = compiled
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
            # A loop-back's target already carries only its own *remaining*
            # ops (see _compile's resume points), so node.ops above is
            # always exactly right to run here -- no separate flag needed to
            # skip ops that already ran on an earlier pass.
            node = node.goto
            if node is None:
                return dict(tape)
            continue
        # Swapped relative to the field names -- see docstring above for why
        # lattice.py's zero/nonzero labeling is rotated 180 degrees from the
        # wiki's actual "turn right if 0, left otherwise" rule.
        node = node.nonzero if tape[pointer] == 0 else node.zero

    return dict(tape)


if __name__ == "__main__":
    import sys

    from extract import extract

    result = extract(sys.argv[1])
    final_tape = run(result)
    nonzero_cells = {k: v for k, v in sorted(final_tape.items()) if v != 0}
    print(f"final tape (nonzero cells): {nonzero_cells}")
