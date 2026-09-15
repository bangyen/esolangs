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
  two, neither of them on the queue above.  Forþ spelled every tree node's
  scope index as a base-15 literal, an `O(n)` label on each of `2**(n+1)`
  nodes; the construction now labels each definition with the step from the
  previous one and passes the callee its own index, which is constant per node,
  and per-entry cost went from 14.2 climbing to 33.1 to a flat 14.4.
  Interprogck8 is the row added below.  It had been exempt for the wrong
  reason -- a `proofs.md` `exception` row about its repair budget's totality,
  which says nothing about size -- and the shipped construction is
  super-linear for a reason [limitations](limitations.md) carries in full.
  That reason now assumes its decision tree rather than forcing it: the
  pointer is not the only state crossing a read, because the function slot,
  the call stack and `z`-rewritten text each survive one
  (`notes/ick8_slot_probe.py` executes all three).  An n=8 -> 9 ratio near 2
  is still not evidence of O(T), which is why the contract's verdicts read in
  one direction only.
  The live audit is:

  | Language | Generation time | Output size |
  | --- | --- | --- |
  | Factor | Language lower bound | Language lower bound |
  | Interprogck8 | Open | Open |
  | Polynomial | Open | Open |

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

  SLOW ACV MAMMALIAN reads all n inputs in one chain: each read's 1-branch
  banks a binary weight (a multiple of 256) on a side array's non-head sum
  and re-merges -- both branches leave through trampolines aimed at the same
  address, which equalizes the sums the jump identities read -- and one
  final trampoline lands `nonhead + b = leaf_base + row * 256` in a flat
  table of fixed 256-token leaves.  Weights total under 2T*256 at a token
  per 14, so text and build are O(T); every table through n=3 executes every
  row, and sampled rows execute through n=12.

  Two cases remain open.

  Vandevelo's hang-set is exactly a union of affine cosets -- every bindable
  value is affine in the inputs and only `::` chains evaluate conditionally --
  so the generator peels the 1-set by iterated popular-difference cubes and
  emits one guard line per coset.  [Cohen--Shinkar][dnf-parities] bound the
  peel at `1 + 9*T/log2(T)` clauses, capping total guard parts at `9T + n`;
  the dense regime falls back to an exact Walsh--Hadamard autocorrelation, so
  the bound is not heuristic.  Constraints from reduced elimination are at
  most `dim+1` inputs wide and live in strict registers morphed one toggle at
  a time; that upkeep is the one unproven piece, `O(T log log T)` worst case
  and under half the text measured.  Dense random tables measure a flat
  8.1--8.9 characters per entry at n=8..12; parity is one hyperplane, 259
  characters at n=10 against the retired per-row spelling's 52,821.  Sampled
  rows at n=6/8 and every table through n=3 execute correctly.

  Polynomial's positive-factor bound is likewise construction-specific
  because signed real parts can cancel coefficients -- measured, not
  conceded: a negative real part decodes and runs
  (`notes/poly_negative_operand.py`).  Multiplying by ignored
  roots preserves the decoded program, but [generic sparse-multiple
  algorithms][sparse-multiples] are exponential in the requested sparsity.  A
  linear generator therefore needs a direct sparse multiple specialized to the
  prime-power instruction roots, not an optimization search.  Shipping the
  factored form instead is not available: the parser reads only summed
  monomials and misreads a product silently
  (`notes/poly_factored_probe.py`).

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
