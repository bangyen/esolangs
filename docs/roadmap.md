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

  Twenty-five generators were queued and Interprogck8 was added by the
  registry-wide contract (`tests/proofs/deep/linearity.py`, per-entry cost
  to n=12 across all 65); all but two have closed, by construction or by a
  language-level lower bound.  An
  n=8 -> 9 ratio near 2 is not evidence of O(T), so the contract's verdicts
  read in one direction only.  The live audit is:

  | Language | Generation time | Output size |
  | --- | --- | --- |
  | Factor | Language lower bound | Language lower bound |
  | Polynomial | Open | Open |

  Closure requires a lower bound over every program in the language under
  the generator contract.  Super-linear output implies super-linear
  generation time; the time column is not an independent verdict.

  Polynomial's remaining question is a left-half-plane multiple of the
  mandatory root product with more terms than the Descartes minimum:
  instruction count, monomial count, right-half-plane coefficient mass, and
  the Descartes-minimal class are all language-forced, and every searched
  escape is closed.  [polynomial](polynomial.md) has the proofs,
  the measured negatives, and the literature match.

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
  the decode model, and takes the head of a ranked shortlist.  The rule is
  known -- folding the extremal same-colour pair is always legal, the
  argument that made the decode total -- but shipped as the decoder it
  builds the dense n=9 tables the current construction refuses, in seconds
  and a megabyte each, so a swap must keep the prompt refusal or beat it on
  executed programs.  A longer emitted program is an acceptable price for a
  rule, and the replaced search stays in the tests as the oracle.

- **`%^2^-1` fourteen inputs.**  The staged fold's endgame strands its last
  duplicated cofactor pairs.  Rank order is steerable (pulsed doubling), but
  a merge needs the pair's value gap `d` inside a wipe window, and diving
  the partner maps `d -> amount - d` with the amount free in the window --
  a derived, unbuilt alignment controller.  Build it only if a ~20x
  thirteen-input build cost (~430k plan ops, ~8MB templates, ~226 ops per
  merge) is acceptable.
