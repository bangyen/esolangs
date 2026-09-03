# A Painter Ant boolean generator: invariants and design rules

Why the construction must be cycle-stable for **every input count**, the
constraint that drives every design decision here.  Shipped generator:
`esolangs.tools.boolean.a_painter_ant.a_painter_ant`.

Language mechanics (conditional moves, paints, implicit loop) are in the
interpreter module's docstring, authoritative and not restated here.

- The interpreter's output is the **bounding box of visited cells** (`#`
  white / `.` black, ant's cell as `@` or `o`), which carries no
  coordinates, so the generator reads its answer from a *semantic grid
  model* (the ant's actual position and cell colours) instead.
- The answer is the **colour of the cell the ant lands on** at the end of
  a cycle (white is one, black is zero).

## Cycle-stability is non-negotiable

A valid generator must produce programs whose behaviour is independent of
how many whole cycles run: the interpreter's bounding-box output must be
identical for `limit = len(prog)` and `limit = 10 * len(prog)`.  Every
instantiated program must be a **cycle-stable fixed point**.

The reason this is hard, and must stay true of any future construction: a
program is origin-relative — its moves and paints are tuned to run from
the origin on a black grid — but the ant *ends* a cycle at its output
leaf.  On cycle 2 the ant starts at the output, so the origin-relative
setup commands misfire unless the cycle-2 run is a closed, zero-paint
dance back to the output.  Any modification to the head, body, or routing
must preserve that closed zero-paint dance on cycle 2 and every cycle
after — verify on the interpreter (1 vs. many cycles), not by inspection.

### Verification coverage (know what's untested before extending arity)

Exhaustive for `n <= 3` (256 tables x 8 inputs = 2048 cases, cycle-stable
and exact on the real interpreter); `n == 4` and `n == 5` spot-checked
against a handful of tables via `tests/tools/a_painter_ant_trace.py`;
`n == 6` and `n == 7` build and check out on ad hoc tables but have no
checked-in test.  Extending or refactoring arities above 3 should add
exhaustive or expanded spot-check coverage rather than assume the pattern
holds.

## Design principles (must hold for any future change here)

1. **Monotone painting** — use only `P`; represent a zero leaf as a space
   (unpainted), never `p`.  Non-monotone `p` reverts cells and breaks
   stability.
2. **Pre-painted two-layer stars** — paint the ring (distance 1) and axis
   (distance 2) cells around each output in the body; stability is a
   *closed, zero-paint dance* on the star, so a runtime-painted star is not
   usable.
3. **Paint one star per final-input value, not per leaf** — the final input
   just routes to a pre-painted star; it never re-embeds or re-paints.
4. **The ring rule** — from the top-middle, only north/west/east follow
   safely; from the middle-left, only north/south/west.  A leafward move
   (south from the top-middle, east from the middle-left) splits the ants:
   the black-output ant returns to the leaf while the white-output ant
   stays on the ring.  Use both ring cells so the flow direction always
   matches, and let only an `S/s`-style dual move leafward.
5. **Gap calculation** — the black moves between two stars are the center
   distance minus 2 (each ring reaches one cell toward the other).
6. **Return through the origin** — head paths back to the origin must avoid
   re-crossing painted cells (which block lowercase moves).
7. **Superincreasing weights** — give input `i` weight `2**i` on an
   alternating axis for a collision-free leaf layout.
8. **Make the last input east/west** — north routing for the final input is
   awkward; put it on the east/west axis.
9. **The landing dual must run from a ring cell, never the leaf** — the
   leaf's neighbours are white ring cells, so any uppercase move in the
   text that runs from the leaf on cycle 2 fires.  End the body dance on a
   ring cell and let a fixed mixed-case closing walk carry the ant onto
   the leaf, on every cycle.
10. **Keep cycle-2 starts unique** — a colour-dependent landing (leaf for a
    zero, a ring cell for a one) gives the head two different cycle-2
    starts and no single dance works from both.  The ant must land on the
    leaf for both colours.
11. **Route on the clean rows** — lowercasing the routing is the only way
    to keep it a cycle-2 no-op from the leaf, so it must fire on black
    cells: route north/south or east/west on rows the body never paints
    (`y = -3`, `y = -4`) rather than on the white routing row.
