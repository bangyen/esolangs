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
  other traversals linear but do not remove their super-linear output.  The
  n=8 -> 9 parity sweep already exposes super-linear output in A Painter Ant
  (135016 -> 534124), 123 (94579 -> 230034), Circuit Diagram
  (7910330 -> 11394987), COD (942692 -> 3668705), Minifuck
  (57601 -> 203089), and Factor (24113 -> 50090); dense tables also expose
  Polynomial.  The construction audit also leaves AddSubJump, ArrowQueue, Back,
  Bitdeque, BrainIf, Clockwise, Container, Dig, Flowchart, Forþ,
  Inject, Jaune, LaserFuck, RAM0, S*bleq,
  SLOW ACV MAMMALIAN, Streetcode, and Vandevelo.  Their quiet factors
  are minterms, rectangular tree layouts, widening labels or addresses, and
  per-depth padding; an n=8 -> 9 ratio near 2 is not evidence of O(T).
  The live audit is:

  | Language | Generation time | Output size |
  | --- | --- | --- |
  | A Painter Ant | Linear | Linear |
  | 123 | Open | Open |
  | Circuit Diagram | Linear | Linear |
  | COD | Open | Open |
  | Minifuck | Open | Open |
  | Factor | Language lower bound | Language lower bound |
  | Polynomial | Open | Open |
  | AddSubJump | Linear | Linear |
  | ArrowQueue | Linear | Linear |
  | Back | Linear | Linear |
  | Bitdeque | Linear | Linear |
  | BrainIf | Linear | Linear |
  | Clockwise | Linear | Linear |
  | Container | Open | Open |
  | Dig | Open | Open |
  | Flowchart | Linear | Linear |
  | Forþ | Linear | Linear |
  | Inject | Linear | Linear |
  | Jaune | Linear | Linear |
  | LaserFuck | O(T) | O(T) |
  | RAM0 | Linear | Linear |
  | S\*bleq | Linear | Linear |
  | SLOW ACV MAMMALIAN | Open | Open |
  | Streetcode | Open | Open |
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
  pass; weighted routing along that corridor totals T-1 moves.  ArrowQueue's
  marker arms have lengths `1+2+4+...+T/2 = T-1`, then one sentinel selects a
  constant-size table row.  Flowchart preloads T answers and discards opposite
  deque halves; both arms merge through a switch with a normalized heading.
  LaserFuck prewrites the table, conditionally walks the same geometric arm
  lengths, and uses a fixed overshoot to align the selected cell for cleanup.
  Clockwise alternates horizontal and vertical subtree composition; each pair
  of levels doubles both dimensions, keeping the rendered rectangle linear.
  Circuit Diagram recursively quarters its minterm tree in an H-layout whose
  side is O(sqrt(T)); the fixed-catalogue router occupies O(T) cells.
  Median-of-three dense and parity measurements for `n=1..9` are plotted as
  [characters per table entry](boolean-scaling-size.svg) and
  [seconds per table entry](boolean-scaling-speed.svg).  The timing plot is
  diagnostic only; finite measurements do not establish an asymptotic bound.
  Factor's Brainfuck tree has O(T) characters but Theta(T)
  command runs; assigning each run the next prime makes its numeral
  Theta(T log T) digits.  It needs a run-compressed Brainfuck lookup.
  Circuit Diagram now uses a linear one-pass Shannon fold and
  indexed layout guards, but its persistent selector rails leave the ASCII
  area O(T log T): parity keeps all `n` selector rails live across Theta(T)
  columns.  Route each selector only across its mux level.  Treat every
  emitted character as build work.  Input reordering is optional around the
  construction, but its work still counts toward end-to-end generation time.
  Order selection builds at most four named candidates and its generic greedy
  scorer stops at n=10; factorial and exponential contests are test-only
  oracles.  No generator construction may
  use BFS or DFS; test-only oracle searches and prose about retired searches may
  remain.  Circuit Diagram's H-layout temporarily uses a bounded local dogleg
  scan with cell-indexed collision checks; derive its first-free lanes into a
  direct routing rule without changing the emitted programs.

- **A Painter Ant shared-head proof.**  While auditing A Painter Ant above, the
  depth-first head cuts dense n=9
  from 517348 to 19684 characters and executes every n=3 program plus sampled
  programs through n=8, but invalidates the uniform proof check's independent
  per-leaf rest-point and motif decomposition.  Rewrite those lemmas around
  shared prefix entry/exit states, then restore `just apa-proof` to green and
  rescreen input order now that the construction is tree-shaped.

- **Reorder EGL inputs.**  EGL hoists every read into addressable one-hot cells,
  so a tree can test cell `perm[depth]` while the `x` commands remain in stream
  order.  Exhaustive n=3 measurement over all 256 tables gives 61304 -> 53592
  total characters (12.6%); all 2048 rows of the shortest candidates execute
  correctly.  Generalize that prototype through `best_input_order` and keep
  the identity on ties.

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
