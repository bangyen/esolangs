# Roadmap

Only live work belongs here. Contracts and standing walls go to
[limitations](limitations.md); a closed row leaves, and its commit is the record.

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

  All 65 generators are audited on four axes.  Totality is the `proofs.md`
  ledger's own label (`Cap`: refuses some tables on cost; `Exception`: no
  totality argument).  Output size is the registry-wide contract
  (`tests/proofs/deep/linearity.py`, per-entry cost to n=12).  Generation
  time and execution time were measured by hand (Sep 2026): the fitted
  growth per added input over the top five arities, best of three,
  execution on the worst sampled parity row with loading excluded, and a
  figure on a run under ten milliseconds is not read as an exponent.  A row
  is present while any axis is open and leaves when all four close; an
  n=8 -> 9 ratio near 2 is not evidence of O(T), so every verdict reads in
  one direction only.  The live audit is:

  | Language | Totality | Generation time | Output size | Execution time |
  | --- | --- | --- | --- | --- |
  | %^2^-1 | Exception | Open | Linear | Linear |
  | 6-5 | Cap | Linear | Linear | Linear |
  | Circlefuck | Total | Open | Linear | Linear |
  | Factor | Cap | Language lower bound | Language lower bound | Linear |
  | NoComment | Cap | Linear | Linear | Linear |
  | Polynomial | Cap | Open | Open | Linear |
  | Vandevelo | Total | Open | Linear | Linear |
  | WII2D | Cap | Open | Open | Linear |
  | ZTOALC L | Cap | Linear | Linear | Linear |

  Generation time, growth per added input at the top arity: %^2^-1 x4.2
  dense (0.9 s at n=10, parity x2.6), Polynomial x3.4 dense (1.1 s at
  n=9), WII2D x4.8 dense (1.1 s at n=9), Factor x2.7 (1.2 s at n=11).
  B-tapemark, Streetcode, 6-5, Forth and Circuit Diagram past its n=8
  route change all read x2.2, between the size contract's x2.15 and what
  these arities separate from noise; they are held linear until a wider
  measurement says otherwise.  Interprogck8 and Unsquare left this table
  with their builds byte-identical -- printer flights laid once per shared
  channel (x3.3 -> x2.03, 2.8 s -> 0.2 s at n=12), and an incremental tree
  price that re-tests only the levels a sink moves (x2.4 -> x2.02).
  Circlefuck x2.19 (30 ms at n=12, from x2.5): its greedy order scores
  every candidate in one pass per level and now carries the subtree keys
  between levels rather than rekeying every row from the whole prefix, so
  what is left is the n passes themselves, Theta(T log T) by
  construction; the measured slope is that log factor's own 2 * 12/11.
  A linear order needs a level's scores derived from the level above
  without touching the rows, and a subtree's split-by-any-input masks do
  not come from its parent's.  Vandevelo x2.9 dense (0.27 s at n=12,
  from x3.6 and 1.3 s, parity x1.9): the peel scores ~50 candidate
  directions per round on a 2**n-bit mask over Theta(T) rounds, the
  integer bit-vector class, Theta(T^2 / word) with a small constant; a
  linear build needs a different popularity count, not a faster shift.
  BFStack, BrainIf, LaserFuck, RAM0
  and Jaune left the execution column the same way: BFStack's ``[`` scanned
  for its ``]`` on every skip, and the other four rebuilt a whole immutable
  tape per write, now a chunked persistent tape
  (`esolangs.interpreters.persistent`); they read x1.5-x2.0
  with every output and step count unchanged.

  Closure requires a lower bound over every program in the language under
  the generator contract.  Super-linear output implies super-linear
  generation time; the time column is not an independent verdict there,
  but a linear output can still be built super-linearly, which is what the
  eight open generation-time cells record.

  Polynomial's remaining question is a left-half-plane multiple of the
  mandatory root product with more terms than the Descartes minimum:
  instruction count, monomial count, right-half-plane coefficient mass, and
  the Descartes-minimal class are all language-forced, and every searched
  escape is closed.  [polynomial](polynomial.md) has the proofs,
  the measured negatives, and the literature match.

  WII2D's remaining question is the decode: the last junction's two
  branches turn the Horner index into the table's columns by folding
  (`'-' * c + 's'`, one character per unit of the centre) and halving, and
  the emitted size per table entry climbs 11 -> 16 -> 15 -> 58 -> 153 from
  n=5 to n=9 on the suite's dense fixture.  A linear construction needs the
  answer readable as the accumulator's *top* bit -- floor-halving discards
  low bits and a digit discards everything, so nothing discards the bits
  above -- and every cheap placement found (shifts by `2 ** q`, squaring's
  cross terms, a dot product by multiplication) leaves other entries or
  monomials above it.  Refuted by an op-string family of length O(T) that
  computes an arbitrary column from the index, or from `2 ** (K +- q)`,
  which the chain can emit in O(n) characters.

  Treat every emitted character as build work.  Input reordering is optional
  around the construction, but its work still counts toward end-to-end
  generation time.  Order selection builds at most four named candidates and
  its generic greedy scorer stops at n=10; factorial and exponential contests
  are test-only oracles.

  No generator construction may use BFS or DFS; test-only oracle searches and
  prose about retired searches may remain.

- **ArrowQueue reusable drain.**  Ship the verified deep-fold drain only if
  a proof makes folding meaningfully testable at `n >= 5`; current coverage
  does not reach its crossover.

- **Reorder ArrowQueue inputs.**  The three-input screen leaves 12.4%
  headroom, but its queued inputs cannot be renamed in place.  Find a
  re-enqueue and grid-routing construction, then compare emitted, executed
  programs against the current template; abandon it if the routing spends
  the apparent gain.

- **Replace WII2D's build-time fold search.**  "Uses a simulator" means
  the module drives an interpreter or an execution model while generating,
  and only one of the three ways that happens is a defect: driving a
  *search* over candidate codes.  Simulation used as bookkeeping for what is
  already being emitted is fine, and size contests run no simulator at all.
  WII2D's decode still enumerates the legal folds, validates each against
  the decode model, and takes the head of a ranked shortlist.  The
  compressed-magnitude contest is load-bearing: on a 230-table seeded
  corpus the one-shot rules lose (nearest-midpoint centre 1.06x the size
  and 0 of 8 dense n=9 against 4 of 8; most-merges and cheapest-centre
  build nothing past n=6), and the extremal same-colour fold -- always
  legal, the argument that made the decode total -- refuses from n=7 under
  the shipped centre and magnitude caps and needs them lifted to build
  dense n=9 at a megabyte.  A closing rule must keep the prompt refusal or
  beat the contest on executed programs; a longer emitted program is an
  acceptable price, and the replaced search stays in the tests as the
  oracle.

- **`%^2^-1` fourteen inputs.**  The staged fold's endgame strands its last
  duplicated cofactor pairs.  Rank order is steerable (pulsed doubling), but
  a merge needs the pair's value gap `d` inside a wipe window, and diving
  the partner maps `d -> amount - d` with the amount free in the window --
  a derived, unbuilt alignment controller.  Build it only if a ~20x
  thirteen-input build cost (~430k plan ops, ~8MB templates, ~226 ops per
  merge) is acceptable.
