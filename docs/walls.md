# Generator and transpiler boundaries

A search result is not a wall unless its structural reason is recorded here.
Generated programs must be run before a size, equivalence, or impossibility
claim is accepted.

## Standing results

- **6-5:** only 35 branch labels are addressable; labels are global ordinals
  and cannot be reused. Do not use operands past `Z`.
- **3x, Dotlang, ROTfuck, 2dFish:** their documented input/control-flow
  mechanics do not support the proposed universal decision-tree construction.
- **`%^2^-1`:** a program reading its own inputs cannot compute a two-input
  function. The embedded-input ladder's twelve-input limit is only a
  construction limit; interleaving embedding and folds remains open.
- **WII2D:** routing plus accumulator decoding is the shipped construction;
  its remaining guards are source-cost policies, not language walls.
- **Termination convention:** use only where a specification supplies a
  reliable halt/loop verdict and the runtime can decide it soundly.

## Verification boundaries

Exact-state cycle detection decides only complete, deterministic state repeats.
Tape-growth and recursive-frame helpers cover their specific semantic shapes;
other nontermination still needs a wall-clock backstop. A negative corpus
search needs a positive control that exercises the proposed mechanism.

Historical attacks, measurements, and removed generators remain in git. Reopen
a result only with a new semantic mechanism, not a wider blind search.
