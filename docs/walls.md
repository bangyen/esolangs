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
  function. The staged cofactor fold reaches generic thirteen-input tables;
  its walls are measured, not open: no ladder lays `2**12` distinct
  positions inside the 3003 footprint (so no fourteen-input prefix), the
  256-class compaction a fourteen needs converges at ~226 ops per merge but
  strands its last duplicated pairs in a rules cycle -- pulsed doubling
  breaks the rank rigidity, yet a merge still needs the pair's *value* gap
  steered into a wipe window, an unbuilt controller -- and fifteen-plus
  generic tables are closed by counting: 16-bit cofactors over 2048 prefix
  points are nearly all distinct, so compaction stops biting.
- **WII2D:** routing plus accumulator decoding is the shipped construction;
  its remaining guards are source-cost policies, not language walls.
- **Termination convention:** use only where a specification supplies a
  reliable halt/loop verdict and the runtime can decide it soundly.
- **Empty input line:** `io.input_char` now returns `0`, matching every
  interpreter that guards `io.input_str` at its own call site; the package
  used to answer `10` through one path and `0` through the other, which no
  cross-camp transpiler could reconcile. Exhausted input is still `EOFError`.
  Pinned by `tests/interpreters/test_input_convention.py`, which enumerates
  the registry rather than a list. Open: whether any language's `0` was ever
  sourced from its own specification rather than chosen — the docstrings
  citing "the original" are the same author's earlier readings.

## Verification boundaries

Exact-state cycle detection decides only complete, deterministic state repeats.
Tape-growth and recursive-frame helpers cover their specific semantic shapes;
other nontermination still needs a wall-clock backstop. A negative corpus
search needs a positive control that exercises the proposed mechanism.

Historical attacks, measurements, and removed generators remain in git. Reopen
a result only with a new semantic mechanism, not a wider blind search.
