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
  is a cycle with no reachable leaf would then never halt on its own, same
  as an unbounded Brainfuck ``[]`` loop; :func:`run`'s ``step_limit`` exists
  for exactly that case, raising rather than hanging forever.

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
``extract.py``: every fork node (one with ``zero``/``nonzero`` children --
the only kind of node a loop can meaningfully return control to) is indexed
once by its own *final* vertex's ``(y, x)``, the actual decision-point pixel;
any leaf whose own final vertex matches that coordinate becomes a jump back
to that fork's decision at runtime, skipping straight to re-checking the
tape rather than re-running the fork's incoming stem (see :attr:`_Compiled.goto`).

Unverified against a real drawn loop end to end: neither wiki fixture
contains one (confirmed by checking both fixtures' every stroke's start/end
coordinates for a match -- none), and ``render.py``'s own ``Node``/
``_layout`` cannot produce one either, since ``Node`` is a plain tree walked
recursively with no cycle support (confirmed: a hand-built cyclic ``Node``
graph passed to ``render()`` hits Python's recursion limit rather than
rendering).  The coordinate-matching mechanism itself is covered by a
synthetic test that builds a looping ``lattice.Stroke`` tree directly
(bypassing both ``render.py`` and ``extract.py``, which cannot produce a
real one yet), not by a round-trip through a rendered image.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from extract import DEFAULT_UNIT, OpCall, Stroke, classify_ops

# Generous headroom above anything either wiki fixture's own program needs
# (the addition/multiplication examples each run in well under 1000 steps) --
# exists only to turn a genuinely non-halting program into a raised error
# instead of an actual infinite loop, matching the other interpreters in this
# repo's own instruction-limited run pattern (see
# ``src/esolangs/interpreters/oisc_cli.py``); not tuned to any particular
# program's real cost.
DEFAULT_STEP_LIMIT = 1_000_000


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
    ``None``) whose drawn path reconnects to an earlier node -- see
    :func:`_compile`'s own docstring for how that is recovered.
    """

    ops: list[OpCall]
    end: tuple[int, int]
    zero: _Compiled | None
    nonzero: _Compiled | None
    # Set only on a leaf whose drawn path reconnects to an earlier fork (see
    # _compile).  Points at that fork's *own* zero/nonzero pair directly,
    # deliberately bypassing the fork node itself -- jumping to the fork
    # node the ordinary way would re-run its own `ops` (whatever the stem
    # leading into that decision point does, e.g. a leading read), which a
    # real loop-back must not repeat every iteration; only the decision
    # itself repeats.
    goto: _Compiled | None = None


def _compile(stroke: Stroke, unit: int) -> _Compiled:
    """Classify every stroke in ``stroke``'s tree exactly once, recursively.

    Also recovers the loop-back link :mod:`lattice`'s walker discards (see
    module docstring): every *fork* node (one with ``zero``/``nonzero``
    children -- a ``?``, the only kind of node a loop can meaningfully
    return control to) is indexed by its own ``end`` vertex's ``(y, x)`` --
    the actual decision-point pixel, not its ``entry`` -- since that is
    where the drawing's ink visually branches and where a loop-back arm's
    path would reconnect.  Every leaf's *final* vertex is then checked
    against that index; a match means the drawing's ink physically
    reconnects to a real decision point, and the leaf's ``goto`` is wired
    there instead of leaving it a real halt.

    Indexing by ``end`` rather than ``entry``, and forks only rather than
    every node, both matter: a fork's own two children always start
    (``entry``) exactly where the fork itself ends, so indexing every
    node's ``entry`` (tried first) makes a fork's *own child* shadow the
    fork itself at that shared coordinate -- a loop-back leaf then wrongly
    resolves to whichever child happened to be indexed first instead of the
    fork it actually needs to re-decide at, silently breaking the loop
    after one iteration (confirmed with a synthetic decrementing loop: cell
    stopped at 2 instead of reaching 0, since the loop arm resolved its own
    ``goto`` to itself).  Indexing by ``end`` sidesteps this entirely, since
    only the fork itself -- never its children -- ends at that coordinate.

    Building the whole tree before linking (rather than linking as each
    node is built) matters because a loop-back target can be defined
    *after* the leaf that jumps to it in build order -- e.g. a fork's
    ``zero`` arm looping back to the fork itself, which is built before
    ``walk_tree`` ever recurses into ``zero``.
    """
    by_fork_end: dict[tuple[int, int], _Compiled] = {}
    leaves: list[_Compiled] = []

    def build(node: Stroke) -> _Compiled:
        last = node.vertices[-1]
        compiled = _Compiled(
            ops=classify_ops(node.vertices, unit),
            end=(last.y, last.x),
            zero=None,
            nonzero=None,
        )
        if node.zero is not None:
            compiled.zero = build(node.zero)
        if node.nonzero is not None:
            compiled.nonzero = build(node.nonzero)
        if compiled.zero is None and compiled.nonzero is None:
            leaves.append(compiled)
        else:
            by_fork_end.setdefault(compiled.end, compiled)
        return compiled

    root = build(stroke)
    for leaf in leaves:
        leaf.goto = by_fork_end.get(leaf.end)
    return root


def run(
    stroke: Stroke,
    io: IO | None = None,
    unit: int = DEFAULT_UNIT,
    step_limit: int = DEFAULT_STEP_LIMIT,
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

    Raises :class:`RuntimeError` past ``step_limit`` single-opcode steps,
    rather than looping forever on a program whose only path is a cycle with
    no reachable dead end (the wiki does not document a halt condition at
    all -- see module docstring).
    """
    if io is None:
        io = IO()
    compiled = _compile(stroke, unit)
    tape: dict[int, int] = defaultdict(int)
    pointer = 0
    steps = 0

    node: _Compiled | None = compiled
    run_ops = True
    while node is not None:
        if run_ops:
            for call in node.ops:
                if steps >= step_limit:
                    raise RuntimeError(
                        f"execution exceeded the {step_limit}-step limit "
                        "(the program may not halt)"
                    )
                steps += 1
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
            if node.goto is None:
                return dict(tape)
            # Land directly on the branch dispatch below, skipping node.ops:
            # a loop-back returns control to the fork's *decision*, not to
            # the stem leading into it (see _Compiled.goto's docstring) --
            # that stem's ops already ran the first time this fork was
            # reached and must not repeat every iteration.
            node = node.goto
            run_ops = False
            continue
        # Swapped relative to the field names -- see docstring above for why
        # lattice.py's zero/nonzero labeling is rotated 180 degrees from the
        # wiki's actual "turn right if 0, left otherwise" rule.
        node = node.nonzero if tape[pointer] == 0 else node.zero
        run_ops = True

    return dict(tape)


if __name__ == "__main__":
    import sys

    from extract import extract

    result = extract(sys.argv[1])
    final_tape = run(result)
    nonzero_cells = {k: v for k, v in sorted(final_tape.items()) if v != 0}
    print(f"final tape (nonzero cells): {nonzero_cells}")
