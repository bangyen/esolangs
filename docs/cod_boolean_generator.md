# COD boolean generator: design notes (unbuilt proposal)

A design proposal for a COD boolean generator, written to be read cold.
This is **not** a verified construction: unlike
`docs/a_painter_ant_generator.md` (which records a working, tested generator),
COD has no interpreter in this repo yet, so nothing here has been run.  The
purpose of this document is to pin the design down to a concrete spec so
that when the interpreter lands — with a seeded-randomness decision per the
LaserFuck precedent (`docs/roadmap.md`) — the generator work is checked
against a stated plan rather than re-derived.  Open questions are marked
`O1`.. and collected at the bottom.

## Language mechanics (per the wiki)

COD programs are two-dimensional.  `~` is a wave (a wall); a space is water
(passable); every other command character is passable and executes when a
cod passes over it.  `>` is a cod: an instruction pointer with an unbounded
signed integer value starting at 0.

- `+` duplicates the cod; `-` removes it.
- `)` / `(` increment / decrement the cod's value.
- `<` removes the cod if its value is zero.
- `_` reacts only to upward motion: if the cod is going up when it hits the
  `_`, it is sent back down iff its value is nonzero; otherwise nothing.
- `---` (three dashes) touching the left or right edge with nothing between:
  print the cod's value, then remove the cod.  Anywhere else it counts as
  three `-` commands (three removals).
- `...` (three periods) touching the top or bottom edge with nothing between:
  read a number from STDIN into the cod's value.  Anywhere else it is ignored.

Cods move through anything except waves and other cods.  Motion: if a cod
can go multiple ways it chooses a random valid direction; at a dead end it
turns around; completely blocked in, it loops forever.  If at any moment
there are no cods, the program terminates.

The wiki's own truth-machine example (`~.~`, `~~.~~~~`, `~>.+---`, ...) is the
canonical demonstration that `_` and `<` behave as value gates and that cods
turn corners; it should be the interpreter's first validation target.

## Why a boolean generator at all

COD's only output is a number printed by `---`, so a text generator is
impossible.  A single `0`/`1` printed as the cod's value is a valid boolean
output, so the boolean generator is the whole generator story — the same
position the roadmap puts it in.

## The output convention

The generator emits one program per truth table.  The harness feeds the `n`
input bits as numbers over the `...` commands; the program prints the table
entry (`0` or `1`) via a terminal `---` and terminates.  Every run must print
exactly one line containing exactly `0` or `1`.

## The single-cod rule

The generated program contains exactly one `>` and no `+`, so there is never
concurrency and never a spurious `-` removal.  Randomness is then avoided
*structurally*: the program is laid out so no cell on any reachable path ever
offers the cod a choice, so the nondeterministic junction rule is never
invoked.  The only decision in the whole program is the `_` gate, which is
deterministic in the cod's value.

## The motion model the design assumes (`O1`)

The design assumes the standard grid-IP rule, which the wiki examples
imply but do not state precisely: a cod continues in its current direction
when the forward cell is open; only when the forward cell is blocked does it
consider alternatives — exactly one open perpendicular cell is a turn, two or
more is a random junction, none is a dead end (turn around).  A cell the cod
just left (the backtrack) is not counted as an alternative.  Under this rule,
a straight corridor with open side passages is not a junction (forward is
open).  This must be confirmed against the interpreter before the
construction is trustworthy; if the real rule counts open side cells (or the
backtrack) as choices, the layout below needs a different corner idiom.

## The abstract construction

A full binary decision tree over the `n` input bits, embedded as a
branch-free grid.  Each internal tree node owns one `_` gate; each internal
node owns one `...` input command on the bottom edge; each leaf ends at a
`---` on the left or right edge.  Input bit `i` is read at depth `i`, so every
root-to-leaf path reads the bits in index order `0..n-1`.

### The per-node cycle

Node `v` sits at column `c_v`; its gate is on the gate row at `c_v`; its
`...` is on the bottom edge at `c_v`.

1. The cod descends column `c_v` from above, through the gate row, onto the
   `...` — the value becomes `bit(v)`.
2. The cod ascends column `c_v` and hits the node's `_` gate going up:
   - `bit = 1` (nonzero): reflected back down into the **lower corridor**,
     which routes to the 1-child's column.
   - `bit = 0` (zero): passes through upward into the **upper corridor**,
     which routes to the 0-child's column.
3. At the child's column, descend to that child's `...` and repeat, until a
   leaf is reached.

Key facts that make this sound:

- The value is overwritten by each `...`, so the cod carries a nonzero value
  upward only through its *own* gate.  Descending through any `_` — including
  other nodes' gates at other columns — is harmless, because `_` ignores
  downward motion.
- Each node has a unique column, so while ascending column `c_v` the cod
  encounters exactly one `_`: its own.
- The two child subtrees live at columns on opposite sides of `c_v`, and the
  path to each child stays inside that child's column interval, so the two
  corridors never cross another node's gate.

### The two corridors

- **Lower corridor (1-branch):** a walled horizontal tube just above the
  bottom edge, from the node's column to the 1-child's descent shaft.  It
  dead-ends into the shaft so the cod is forced to turn down into it.
- **Upper corridor (0-branch):** a walled horizontal tube above the gate row,
  from the node's column to the 0-child's descent shaft, dead-ending into it
  the same way.

Descent shafts are vertical water columns from the bottom edge up through all
the gate rows to the header.  Shafts pass *through* the corridor rows: a cod
moving vertically through a crossing continues straight (forward is open);
a cod moving horizontally along a corridor continues straight through a shaft
cell (forward is open).  Crossings are therefore not junctions under `O1`.

### The branch-free invariant

Every cell on every reachable path has exactly one open exit *in the
direction the cod is moving*: forward open means continue, forward blocked
means exactly one perpendicular cell open (a forced turn), never two or more,
and never a fully blocked cell.  The union of all corridors, shafts, and leaf
tubes is vertex-disjoint except at the gate cells (each owned by exactly one
node, reached by exactly one path), which is what prevents a cell from ever
belonging to two different paths and becoming a junction.  Dead ends (which
would reverse the cod) and blocked-in cells (which would loop forever) are
forbidden by construction.

### The layout

- **Columns:** every internal node and every leaf gets a distinct column, in
  a balanced full-binary-tree order — each node centered between its two
  children, subtree column-ranges disjoint.  Width grows like `2^n`.
- **Rows (top to bottom):** header, then per level (root's level highest):
  upper-corridor row, gate row, lower-corridor row, then the bottom edge row
  of `...` commands.  Each tree level gets its own pair of corridor rows so
  tubes at different levels never share a row.  Depth grows like `6n`.
- **Edges:** every internal node's `...` sits on the bottom border at its
  column; every leaf's `---` sits on the left or right border at its row.
- **Walls:** every cell that is not on the intended path is `~`.  The whole
  program is one pond: the outer boundary is waves except where the `...`
  and `---` touch the edges, and the interior is one connected water region
  with access to the bottom, left, and right — satisfying the "every pond
  must have access to the left/right side" rule.

### Leaf output and value adjustment

At a leaf the cod's value is still the last bit, `bit_{n-1}`, because the
leaf is reached immediately after the depth-`n-1` gate.  The leaf's table
entry `ans` is fixed (the leaf *is* the full bit pattern).  If
`ans == bit_{n-1}` the leaf corridor is empty of value commands; otherwise it
contains exactly one `)` (when `1 - 0`) or one `(` (when `0 - 1`) that the
cod passes before reaching the edge `---`, which prints `ans` and removes the
cod.  With no cods left, the program terminates.

### Input semantics

COD *reads* input, so this is an input-reading generator, not a parameterized
one (no `{Xi}` placeholders).  Each run reads exactly `n` inputs: only the
active root-to-leaf path is executed, and it passes exactly one `...` per
depth.  The unused `...` commands of other nodes are never encountered.

## What `<` is, and is not, for

`<` removes the cod iff its value is zero.  In the single-cod design it
**cannot** be a branch: removing the last cod terminates the program with no
output, and every run must print.  This refines the roadmap's sketch, which
listed `<` alongside `_` as a routing gate (`docs/roadmap.md`): the decision
primitive is `_` alone.  `<` is only available as an optional *guard* — e.g.
a `<` in the header after the start cell, so a cod that is somehow
mis-routed (value still 0) is killed instead of wandering into a junction.
Whether any guard earns its place is deferred until the interpreter exists.

The concurrency alternative the roadmap's "concurrency-heavy" phrase hints at
— `+`-duplicating cods and pruning with `<` — is noted and rejected for this
design: multiple live cods make the output ordering nondeterministic, so the
printed answer would not be a clean single line.

## The delicate part: junction hazards

The abstract design is clean; the engineering difficulty is geometric, and it
is exactly where the roadmap's "heavy, unbuilt 2D construction" assessment
comes from.  The hazards to keep in mind while laying the grid out:

- A corridor cell whose forward cell is a wall but whose two perpendicular
  cells are both open is a random junction.  The corridor must dead-end into
  a shaft in such a way that only the intended turn is open.
- A shaft cell in a corridor row has up and down open; if a horizontally
  moving cod ever reaches it with its forward cell blocked, that is a
  junction.  So the corridor must terminate *at* the shaft, not beyond it,
  and the far side of the shaft must be walled.
- The header and corridor regions must be tubes, not open rooms: an open room
  makes every cell a junction.
- Vertical passages must never carry a nonzero value upward past anything but
  the owning gate.  The layout guarantees this only if columns are unique per
  node; a column reuse would silently turn an ascent into a wrong reflection.

These are verification-sweep problems, not impossibility: they are checked by
enumerating every root-to-leaf path against the interpreter once it exists.

## Grid-size cap

The full tree is inherently `2^n` in both dimensions: width ~ `2^n`, height ~
`2^n`, so program size grows like `2^(2n)` characters (roughly `n <= 6` at a
few thousand cells, `n <= 7` pushing tens of thousands).  The exact gate
should be chosen against the interpreter's practical limits once it exists,
mirroring how the ZTOALC L tree construction is gated at `2**22` lines.

## Open questions

- `O1` **Motion model.**  Confirm the forward-continue rule (side/backtrack
  cells are not choices when the forward cell is open) against the
  interpreter, using the truth-machine example as the test.
- `O2` **Initial heading.**  How a `>` cod's first move is chosen when placed
  in a corridor; the construction needs it to descend the root shaft first.
- `O3` **Input command spelling.**  The spec says `...` (three periods) but
  the wiki examples use single `.`; the interpreter must fix the spelling,
  and the generator matches whatever it picks.
- `O4` **Seeded randomness.**  The LaserFuck-style seeded-randomness decision
  (deterministic junctions for fuzzing) must land first; the generator
  produces programs that never invoke it, but the interpreter's choice of
  seed policy affects how the generator is fuzz-tested.
- `O5` **Terminal state.**  Confirm that after a `---` prints and removes the
  cod, the program terminates with the printed line as the only output, and
  that no other stray output is possible.

## Verification plan (once the interpreter exists)

Mirror the A Painter Ant generator's discipline:

1. Every `n <= 3` table exhaustively — all 256 three-input tables × 8 input
   combinations — asserting exactly one `0`/`1` line per run.
2. `n == 4..6` sampled, plus structured and constant edge tables.
3. Enumerate every root-to-leaf path and assert the cod's trajectory is the
   intended one: no junction, no dead-end turn, no wrong reflection, each bit
   read exactly once in order, and the printed value equals the table entry.
4. Re-run each program under the seeded random generator to confirm the
   junction rule is genuinely never invoked (the branch-free invariant).

## Relationship to the roadmap

This replaces the roadmap's one-line sketch (`docs/roadmap.md`) with a concrete
plan: single-cod, `_`-only decision tree, `...` at the bottom edge, `---` at
the left/right edges, branch-free by construction.  The roadmap's low
priority and risk assessment stand — this is a design with named hazards, not
a built generator — but the design is now specific enough that the remaining
blockers are the interpreter (with seeded randomness) and the layout
algorithm, not open design questions.