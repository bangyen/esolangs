# Generator and transpiler boundaries

A search result is not a wall unless its structural reason is recorded here.

## Standing results

- **6-5:** only 35 branch labels are addressable; labels are global ordinals and cannot be reused.
- **3x, Dotlang, ROTfuck, 2dFish:** their documented input/control-flow mechanics do not support the proposed universal decision-tree construction.
- **`%^2^-1`:** a program reading its own inputs cannot compute a two-input function.
- **Polynomial, Modulous:** cannot test inputs out of stream order, so their measured reorder upside (15.9% / 16.4% at n=3, `scripts/screen_input_reorder.py`) is unreachable.
- **WII2D:** routing plus accumulator decoding is the shipped construction; its guards are source-cost policies, and the dense ten-input table is a wall of the **exactly-once embed convention**, not of the machine.
- **Termination convention:** use only where a specification supplies a reliable halt/loop verdict and the runtime can decide it soundly.
- **Empty input line:** `io.input_char` now returns `0`, matching every interpreter that guards `io.input_str` at its own call site; the package used to answer `10` through one path and `0` through the other, which no cross-camp translation could reconcile.

## Verification boundaries

Exact-state cycle detection decides only complete, deterministic state repeats.

**Picking the wrong prover is silent, and costs the whole run.** Suptiftam's boolean programs handed *no* input recurse without bound: `mulStep` counts down toward a value the missing read never supplies, so a `_CallFrame` is pushed and never popped.

Both facts are in `run_until_halt_or_cycle`'s own docstring — an unbounded-growth loop never revisits a state, and the frame helper covers the recursive shape — so this is the documented boundary being met, not a defect.

Historical attacks, measurements, and removed generators remain in git.
