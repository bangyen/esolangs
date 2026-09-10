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
  its guards are source-cost policies, and the dense ten-input table is a
  wall of the **exactly-once embed convention**, not of the machine.  Under
  that convention the construction is closed: `^v<>` fills set the heading
  *absolutely*, so every prefix leaves a junction at an identical position
  and heading and only the accumulator differs, which makes any program op
  strings interleaved with the n branch pairs.  Within that family a
  512-point decode ratchets with every candidate enumerated; no op removes
  high accumulator bits, closing every shifted-table readout (verified
  exhaustively over op strings to length 5, against controls that fire);
  and a mid-chain collapse under 4-class labels ratchets too.
  **Drop the convention and the wall goes:** a per-node re-embed (a plain
  grid decision tree, one row per level) computes dense n=10 in 14432
  characters and dense n=13 in 146540, every row executed.  It embeds input
  `i` `2**i` times -- 512 copies of `{X9}` at n=10 -- which is what the
  invariant in `tests/tools/test_boolean_parameterized.py` forbids and why
  Dotlang and 2dFish were removed rather than exempted.  So this is a
  *deliberate* wall, and the thing to re-examine if it ever matters is the
  convention, not the fold algebra.  `docs/wii2d_generator.md` has the
  audit.
- **Termination convention:** use only where a specification supplies a
  reliable halt/loop verdict and the runtime can decide it soundly.
- **Empty input line:** `io.input_char` now returns `0`, matching every
  interpreter that guards `io.input_str` at its own call site; the package
  used to answer `10` through one path and `0` through the other, which no
  cross-camp translation could reconcile. Exhausted input is still `EOFError`.
  Pinned by `tests/interpreters/test_input_convention.py`, which enumerates
  the registry rather than a list. Open: whether any language's `0` was ever
  sourced from its own specification rather than chosen — the docstrings
  citing "the original" are the same author's earlier readings.

## Verification boundaries

Exact-state cycle detection decides only complete, deterministic state repeats.
Tape-growth and recursive-frame helpers cover their specific semantic shapes;
other nontermination still needs a wall-clock backstop. A negative corpus
search needs a positive control that exercises the proposed mechanism.

**Picking the wrong prover is silent, and costs the whole run.** Suptiftam's
boolean programs handed *no* input recurse without bound: `mulStep` counts
down toward a value the missing read never supplies, so a `_CallFrame` is
pushed and never popped. Measured on the XOR program at 3000 steps: 908 live
frames, and a snapshot growing about 32 bytes per step, so no state ever
repeats. `run_until_halt_or_cycle` therefore cannot conclude — it does not
merely run long, it *cannot* terminate, and holding the states OOM-killed the
probe. `run_until_halt_or_ancestor`, which Suptiftam supports (it defines
`frame_entry_key`), returns a bounded verdict on the same program in under a
second: undecided after 64 pushed frames.

Both facts are in `run_until_halt_or_cycle`'s own docstring — an
unbounded-growth loop never revisits a state, and the frame helper covers the
recursive shape — so this is the documented boundary being met, not a defect.
What it costs is a caller who reaches for the exact-state prover by default on
one of the nine languages that define `frame_entry_key`. Under-fed programs
are the way to reach it: with its inputs supplied, the same XOR program is
correct on all four rows.

Historical attacks, measurements, and removed generators remain in git. Reopen
a result only with a new semantic mechanism, not a wider blind search.
