# COD boolean generator: construction notes

A working document recording how the COD boolean generator is built and
verified.  Unlike the design this replaces (see "History" below), this is
a **shipped, tested construction**: the interpreter is
`esolangs.interpreters.grid_based.cod`, the generator is
`esolangs.tools.boolean.parameterized.cod`, and both are exercised by
`tests/interpreters/test_cod.py` and `tests/tools/test_boolean.py`.

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
- `...` (three periods) touching the top or bottom edge with nothing
  between: read a number from STDIN into the cod's value.  Anywhere else it
  is ignored.  The wiki's own truth-machine example writes its `...` one
  period per row (vertically, still three in a row touching the top edge),
  not three periods side by side on one line — easy to misread as a bare
  `.`; the interpreter follows the prose spec (a genuine three-in-a-row,
  edge-touching run) and documents this explicitly.

Cods move through anything except waves and other cods.  Motion: if a cod
can go multiple ways it chooses a random valid direction; at a dead end it
turns around; completely blocked in, it loops forever.  If at any moment
there are no cods, the program terminates.

**The `+` rule is not the same as the general motion rule.**  The wiki
states it separately: "if there are two branches, one of them will continue
and one of them will go back; if there are three branches, they will each
go different forward branches; more, then they will each go different, but
otherwise random, ways."  Reading "branches" as *every* open direction
(including the one the cod entered from) makes this precise: two branches
is a plain corridor (forward and back only, so "goes back" is the ordinary
backward branch — no fork at all); three branches is a T-junction, and the
two *forward-facing* options (excluding backward) each get one of the two
duplicates, deterministically; four branches is a crossroads, and the three
forward-facing options are split similarly (the wiki's "otherwise random"
case cannot occur on a rectangular grid, where at most three cells besides
the entry exist).  This makes `+` at a genuine fork a **deterministic**
primitive, unlike the plain motion rule's random choice at an ordinary
junction — the whole generator is built on this fact, so it never needs
seeded randomness.

## Why a boolean generator at all

COD's only output is a number printed by `---`, so a text generator is
impossible.  A single `0`/`1` printed as the cod's value is a valid boolean
output, so the boolean generator is the whole generator story.

## The shipped construction (`n <= 3`)

`cod(truth_table)` is a **parameterized** generator (like `bio`/`back`/
`nocomment`/`bfpda`): the truth table's answers are embedded as compile-time
constants directly in the returned template, and the `n` input bits are
left as `{X0}`/`{X1}`/`{X2}` placeholders for `instantiate` to fill per run
(`)` for a one bit, a space for a zero) — not read at runtime via `...`.
This is a deliberate departure from the original design sketch (which
assumed COD's real input command had to be used); baking the bits into the
program text sidesteps every open question about `...`'s exact behavior.

`n <= 2` uses one hand-built template (`_COD_TEMPLATE`); `n == 3` uses a
second, independently hand-built and verified template (`_COD_TEMPLATE_3`).
They are related in spirit (both use `+`-fork-and-gauntlet routing) but are
**not** generated from a shared formula — see "Generalizing past `n == 3`"
below for why, and for the formula a future general-`n` version should
follow.

### The per-bit fork-and-gauntlet idiom (`n <= 2`)

Each input bit gets its own `+` fork, reached by the cod moving forward
with its value already set to that bit (0 or 1) by the embedded placeholder:

- One branch **continues forward**.  Its gauntlet is `(` then `<`: a
  value of 1 becomes 0 and dies at `<`; a value of 0 becomes -1 (nonzero)
  and survives.  This branch is the "bit == 0" survivor.
- The other branch **peels off to the side** (down, in the shipped
  layout).  Its gauntlet is just `<`: a value of 0 dies immediately; a
  value of 1 survives unchanged.  This branch is the "bit == 1" survivor.

Exactly one of the two duplicates survives each fork, so after `n` forks
exactly one cod remains, carrying no leftover bit information (its value at
that point is a fixed function of the routing, not the input) — the next
bit's placeholder resets the value fresh for the next fork.  Every fork is
a genuine 2-way split (forward + one side, excluding the entry direction),
so it is resolved by the wiki's deterministic `+` rule, never the random
motion rule.

### The leaf rows (`n <= 2`)

After both bits are consumed, the surviving cod is routed onto one of four
rows — one per input combination — via a short corridor.  Each row is a
compile-time-fixed **leaf tail**: a run of `(` characters (or none) that
brings the cod's known, fixed arrival value down to exactly `0`, followed
by a single embedded output bit (`)` for a `1` table entry, nothing for a
`0`) and the row's own edge-touching `---`.  Because the arrival value at
each leaf is fixed by construction (not input-dependent — the input
already determined *which* row the cod is on), the leaf tail is pure
arithmetic, not a second decision.

### `n == 1`

`cod` reuses the exact same two-input template for `n == 1`: the second
input's placeholder is filled with the **literal** `" "` (bit 0) directly
in the returned template, not left as `{X1}` for the harness — so only
`{X0}` remains, and the harness's `bits` list has length 1.  This is sound
because COD's `+`/gauntlet routing does not care *why* a branch was taken,
only what value arrives at it; fixing the second fork's outcome at
generation time is no different from a caller who happens to always pass
the same bit.

### The `n == 3` construction: index assembly + a leaf cascade

The three-input template (`_COD_TEMPLATE_3`) uses a different, more
economical idiom than repeated fork-and-gauntlet nesting.  It was hand-built
and verified against the real interpreter (every one of the 256 three-input
truth tables, all 8 input combinations each — see Verification below), then
traced cell-by-cell afterward to recover the mechanism it implements:

**Phase 1 — index assembly.**  A single main row holds `n - 1` forks (one
per bit `0..n-2`) and `n - 1` "merge" cells, one after each fork.  Fork `i`
has weight `2**(n-1-i)`:

- **Forward branch** (bit `i` == 0): a net-zero gauntlet — a `(<)`
  formality triplet, then (for weight > 1) a `)`-run up by `weight`, a
  `<` gate, and a `(`-run back down by `weight`.  The value entering and
  leaving the branch is unchanged.
- **Side branch** (bit `i` == 1, on a lower row): starts at `1` (the
  placeholder already added it), then a `<` gate and a `)`-run of
  `weight - 1` more, landing at exactly `weight`.  A vertical shaft then
  carries it back up into the merge cell.

Both branches converge on the single merge cell after fork `i`, entered
either from the west (forward, arriving already at the correct value) or
from the south (side, via its shaft).  The merge cell forks east (the real
path, continuing to fork `i+1`, or to the final bit if `i` was the last
fork) and west — a **sacrificial retrace**: it walks back (in reverse)
through the *same physical cells* fork `i`'s (and, if it survives past
fork `i`'s own gate, fork `i-1`'s, and so on) forward-gauntlet decrement
segments, subtracting off each fork's weight in turn, gated between
segments, until it lands on exactly `0` and dies at one of those forks'
own `<` gate.  No separate geometry is built for this — it reuses the
forward gauntlets' own cells, walked backwards.

The last bit (`n-1`) is read directly after the last merge, with **no
fork of its own**: its weight is `2**0 == 1`, so the placeholder's own
increment already produces the correctly-weighted contribution, and the
value — now the full combo index `V = sum(bit_i * 2**(n-1-i))` — drops
down a shaft into Phase 2.

**Phase 2 — the leaf cascade.**  A dedicated row holds a chain of
`2**n - 1` `"+<("` blocks.  Each one sends one copy **north** into a
dedicated leaf row and continues the other copy **east** with the value
decremented by one.  Leaf `k`'s own row is a gate chain of `(2**n-1-k)`
`(<` pairs (plus a trailing `<`) that only lets a cod carrying *exactly*
that many more decrements survive, followed by that many `)`s to zero the
survivor, the embedded answer bit, and the row's own edge `---`.  The
`2**n`-th leaf sits directly on the cascade row itself, reached by the
cascade's final surviving copy with no further forking needed.

This is a genuinely different shape from the `n <= 2` idiom (which nests
gauntlets per bit and lands on one of `2**n` independent leaf *rows* with
no shared cascade); it was not derived by extending that idiom, and a
general-`n` version should follow this mechanism, not the `n <= 2` one —
see "Generalizing past `n == 3`" below.

## Verification

Mirrors the A Painter Ant generator's discipline (`docs/a_painter_ant_generator.md`):

- All 16 two-input truth tables, all 4 input combinations each (64 runs),
  through the real interpreter: exactly one `0`/`1` line printed, program
  halts (no cod remains).  `tests/tools/test_boolean.py::TestParameterizedCOD`.
- All 4 one-input truth tables (NOT, identity, both constants), both inputs.
- All 256 three-input truth tables, all 8 input combinations each (2048
  runs), through the real interpreter.
- The interpreter itself (`tests/interpreters/test_cod.py`) is checked
  independently against the wiki's truth-machine example (`0` halts with a
  single `0`; any nonzero input loops forever echoing that value) and
  against every command in isolation (`+`, `-`, `)`, `(`, `<`, `_`, edge
  `---`/non-edge `---`, malformed programs), at 100% line coverage.

## Generalizing past `n == 3`

The `n == 3` construction's mechanism (Phase 1 index assembly with
sacrificial-retrace merges, Phase 2 leaf cascade) generalizes in
*principle* to any `n`, but a from-scratch attempt at general-`n` code
this session did not converge — the honest state is recorded here so a
future attempt does not have to re-derive the mechanism from scratch.

**What's solid:**

- The Phase 1 arithmetic (weight `2**(n-1-i)` per fork, net-zero forward
  gauntlet, side gauntlet netting to the full weight, index accumulates
  to the combo's numeric value) was confirmed by tracing every fork's
  entry value across all 8 three-input combinations against the real
  interpreter.
- The Phase 2 cascade (a `+<(` chain of length `2**n - 1`, leaf `k`'s gate
  chain of length `2**n - 1 - k`) was confirmed the same way, and its
  leaf-row start columns and end columns were checked to converge on a
  shared right edge algebraically.
- The merge cells' sacrificial-retrace mechanism (reusing prior forks'
  own gauntlet cells, walked backwards) was confirmed for both the
  single-stage case (merge after fork 0, one weight to unwind) and the
  two-stage case (merge after fork 1, two weights to unwind in sequence,
  gated between stages).

**What broke a from-scratch general-`n` attempt:** a merge cell built by
mechanically following the above recipe ended up with **more than the
intended two live branches**, because it can be *physically re-entered*
from more than one direction across different steps (from the west via
the forward path, from the south via the side path's shaft, and — once
a west-bound sacrificial retrace from a *later* merge passes back through
an *earlier* merge's own cell — from the east too).  Each entry excludes
a different "came from" direction per the wiki's `+` rule, so a cell that
looks like a clean 2-way fork from one entry direction can still act as a
3-way fork from another, and if the resulting branches aren't each
independently gated to die cleanly, cods accumulate rather than being
consumed — observed as an exploding cod population (30+ live cods within
40 steps) rather than a clean halt.  The `n == 3` template avoids this
because its two merges never both get walked-through by a west-bound
retrace at once (there's only one merge deep enough for a two-stage
retrace, and it's the *last* one, so no retrace from it ever needs to
pass through *another* merge cell) — a coincidence of `n == 3`'s small
size, not a property the mechanism guarantees for `n >= 4`.  A working
general version needs to either avoid this re-entry (e.g. give every
merge a genuinely private set of cells, at the cost of not reusing prior
forward gauntlets for the retrace) or prove it can't happen for any `n`
before trusting the reuse.

- **A `2**n`-leaf layout** for the cascade's own column bookkeeping
  (leaf `k`'s start/end columns, the shared right edge) is otherwise
  straightforward once the merge re-entry issue above is resolved.
- The grid-size cap consideration from the original design still applies:
  a `2**n`-leaf cascade grows the program at least linearly in `2**n`, so
  a practical cap on `n` will be needed once a general construction
  exists.

## History

The original design (single-cod, `_`-only decision tree with `...` inputs
on the bottom edge and `---` outputs on the left/right edges, needing a
seeded-randomness decision before the interpreter could exist) was
superseded before being built.  Tracing a hand-built `n == 2` XOR program
against the real interpreter (once it existed) showed the `+`-fork-and-
gauntlet idiom above works without any `_` gate and without touching
random junctions at all, which is materially simpler to lay out and to
verify — so the `_`-gate tree was dropped in favor of the construction this
document now describes.
