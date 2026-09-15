# Roadmap

Only live work belongs here. Completed findings and negative results go to
[limitations](limitations.md).

## New interpreters

The candidate list is empty.

## Conditional follow-up

- **Linear Boolean generators.**  Make build time and emitted size O(T), where
  T is the truth-table length.  For each remaining generator, either add a
  loop-less O(T) construction and an executed scaling regression, or record a
  structural proof that the language or required encoding forces super-linear
  output and continue with the next generator.  Generation time includes
  choosing an input order and writing the result.  Finish with a registry-wide
  scaling contract.

  Work in this order: A Painter Ant, 123, Circuit Diagram, COD, Minifuck,
  Factor, Polynomial, AddSubJump, ArrowQueue, Back, Bitdeque, BrainIf,
  Clockwise, Container, Dig, Flowchart, Forþ, Inject, Jaune, LaserFuck, RAM0,
  S*bleq, SLOW ACV MAMMALIAN, Streetcode, and Vandevelo.  B-tapemark already
  meets both bounds; indexed spans and constant-time fold tests make several
  other traversals linear but do not remove their super-linear output.

  The n=8 -> 9 parity sweep already exposes super-linear output in A Painter Ant
  (135016 -> 534124), 123 (94579 -> 230034), Circuit Diagram
  (7910330 -> 11394987), COD (942692 -> 3668705), Minifuck
  (57601 -> 203089), and Factor (24113 -> 50090); dense tables also expose
  Polynomial.

  That audit is now measured rather than pending: `tests/proofs/deep/linearity.py`
  tracks per-entry cost to n=12 across all 65 generators, so the quiet factors
  it was looking for -- minterms, rectangular tree layouts, widening labels or
  addresses, per-depth padding -- are each either absent or showing.  It caught
  one: Forþ spelled every tree node's scope index as a base-15 literal, an
  `O(n)` label on each of `2**(n+1)` nodes.  The construction now labels each
  definition with the step from the previous one and passes the callee its own
  index, which is constant per node; per-entry cost went from 14.2 climbing to
  33.1 to a flat 14.4.  An n=8 -> 9 ratio near 2 is still not evidence of O(T),
  which is why the contract's verdicts read in one direction only.
  The live audit is:

  | Language | Generation time | Output size |
  | --- | --- | --- |
  | Factor | Language lower bound | Language lower bound |
  | Polynomial | Open | Open |
  | SLOW ACV MAMMALIAN | Open | Open |
  | Vandevelo | Open | Open |

  The limitations file proves only that the shipped constructions are
  super-linear.  None closes a row above: closure requires a lower bound over
  every program in the language under the generator contract.  Super-linear
  output implies super-linear generation time; the time column is not an
  independent empirical verdict.

  AddSubJump stores Theta(log T) table bits per numeric cell.
  A fixed repeated-subtraction loop selects a chunk and extracts its indexed
  bit; its self-modified operand advances through Theta(T/log T) cells.  Chunk
  values and their addresses each cost O(log T) digits, so both construction
  and source are O(T).  Small tables retain the faster tree; every legacy
  three-input table and sampled rows of the packed eight-input parity program
  have executed through the interpreter.

  S*bleq uses the same chunk bound with native subtract-and-branch loops;
  sampled six-input rows across chunk boundaries execute correctly.

  RAM0 initializes one RAM cell per table row with a runtime address counter,
  then conditionally adds unary binary weights whose total is 2T-2.  Only
  O(log T) direct jumps remain; sampled six-input rows execute correctly.

  Jaune lays outputs beside travelling counter cells.  Unary input weights sum
  to T-1, and a fixed two-label loop carries the counter to its output; sampled
  six-input rows execute correctly.

  BrainIf alternates output cells with fresh input-routing cells.  Both the
  table initialization and all unary binary-weight paths contain O(T) lines;
  sampled six-input rows execute correctly.

  Inject keeps the table in one block and conditionally deletes one half per
  input with literal regexes.  Their total length is under 2T; sampled
  six-input rows execute correctly.

  Bitdeque pushes the table, then each zero input removes its weight from the
  tail and each one removes its weight from the head.  Exactly T-1 entries are
  discarded; sampled six-input rows execute correctly.

  A Painter Ant paints a white corridor and its adjacent answer cells in one
  pass; weighted routing along that corridor totals T-1 moves.

  ArrowQueue's marker arms have lengths `1+2+4+...+T/2 = T-1`, then one
  sentinel selects a constant-size table row.

  Flowchart preloads T answers and discards opposite deque halves; both arms
  merge through a switch with a normalized heading.

  LaserFuck prewrites the table, conditionally walks the same geometric arm
  lengths, and uses a fixed overshoot to align the selected cell for cleanup.

  Clockwise alternates horizontal and vertical subtree composition; each pair
  of levels doubles both dimensions, keeping the rendered rectangle linear.

  Circuit Diagram recursively quarters its minterm tree in an H-layout whose
  side is O(sqrt(T)); the fixed-catalogue router occupies O(T) cells.

  Minifuck preloads one control per row below a shifted binary-weight
  separator.  A fixed four-addition identity crosses that strip without
  changing it; one left run selects the row and one parity sweep prints it.

  Dig lets each `#` turn directly into the next branch axis.  The recursive
  bounds swap width and height each level and double one, so both dimensions
  double per level pair and the full grid has O(T) cells.

  Container spells the table backwards as one decimal 0/1 integer.  A fixed
  two-bank network divides it by ten once per selected row, while binary input
  weights total `T-1`; the literal, source, and construction are O(T).

  123 converts each embedded bit into one separator mark per earlier prefix.
  Level `i` paints and spans O(2^i) cells, then one replay separates every
  prefix group; the geometric sums bound both direct emission and source by
  O(T), without materializing every row's tape state.

  Streetcode thickens an alternating-axis H-tree into two-lane roads.  Its
  branch distance is geometric on every other level, so its height and width
  are both O(sqrt(T)); the shared input normalizer occupies only O(log(T)^2)
  cells beside it.  Sampled paths through six inputs execute correctly.

  COD lays all T answers in one row.  Each once-only placeholder contributes
  its binary-weight horizontal displacement, selecting one answer column;
  the filled four-row grid is `4T+23` characters.

  Three cases remain open.

  SLOW ACV MAMMALIAN need not discard its control label when reading:
  `ACCEPT` appends `byte XOR acc` and leaves `acc` intact, so an accumulator
  congruent to 48 appends the input bit while remaining an absolute
  `LEAPFROG` label.  This removes the current per-node trampoline in
  principle.  The open step is a constant-token transition from either child
  state to that child's next label; `DIGEST` only XORs the current whole-array
  sum, while rebuilding an arbitrary sum recreates the skipped-child cost.

  Vandevelo reduces to covering the selected inputs by affine subspaces.
  [Cohen--Shinkar's DNF-of-parities theorem][dnf-parities] covers every set
  with at most `1 + 9*T/log2(T)` subspaces, but counts clauses rather than
  source:
  spelling the subspaces' dense parity equations can still cost
  `Theta(T*log(T))` variable references.  Splitting the inputs in half and
  precomputing every parity in each half reduces the XOR-gate count to O(T),
  but each later selection names one of `Theta(sqrt(T))` retained values and
  therefore still costs `Theta(log(T))` characters.  Removing that textual
  addressing cost remains open; minterms are not a language lower bound.

  Polynomial's positive-factor bound is likewise construction-specific
  because signed real parts can cancel coefficients.  Multiplying by ignored
  roots preserves the decoded program, but [generic sparse-multiple
  algorithms][sparse-multiples] are exponential in the requested sparsity.  A
  linear generator therefore needs a direct sparse multiple specialized to the
  prime-power instruction roots, not an optimization search.

  Treat every emitted character as build work.  Input reordering is optional
  around the construction, but its work still counts toward end-to-end
  generation time.  Order selection builds at most four named candidates and
  its generic greedy scorer stops at n=10; factorial and exponential contests
  are test-only oracles.

  No generator construction may use BFS or DFS; test-only oracle searches and
  prose about retired searches may remain.  Circuit Diagram's H-layout
  temporarily uses a bounded local dogleg scan with cell-indexed collision
  checks; derive its first-free lanes into a direct routing rule without
  changing the emitted programs.

  [dnf-parities]: https://eccc.weizmann.ac.il/report/2014/099/
  [sparse-multiples]: https://arxiv.org/abs/1009.3214

- **ArrowQueue reusable drain.**  Ship the verified deep-fold drain only if
  a proof makes folding meaningfully testable at `n >= 5`; current coverage
  does not reach its crossover.

- **Reorder ArrowQueue inputs.**  The three-input screen leaves 12.4%
  headroom, but its queued inputs cannot be renamed in place.  Find a
  re-enqueue and grid-routing construction, then compare emitted, executed
  programs against the current template; abandon it if the routing spends
  the apparent gain.

- **`%^2^-1` fourteen inputs.**  The staged fold's endgame strands its last
  duplicated cofactor pairs.  Rank order is steerable (pulsed doubling), but
  a merge needs the pair's value gap `d` inside a wipe window, and diving
  the partner maps `d -> amount - d` with the amount free in the window --
  a derived, unbuilt alignment controller.  Build it only if a ~20x
  thirteen-input build cost (~430k plan ops, ~8MB templates, ~226 ops per
  merge) is acceptable.
