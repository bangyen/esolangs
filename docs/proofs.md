# Proofs

Three results were machine-checked in Lean 4 + mathlib. The sources were
deleted in `4317b0bb` and stay recoverable at `528fe2c2`; what is kept here
is prose transcribed from each proof file's docstring, so the statements say
what the theorems said. Source and tests are the primary evidence.

The axiom note under each says what it rested on: `sorryAx` would mark a gap
and never appeared, and `Lean.ofReduceBool` marks a `native_decide` step,
which trusts the Lean compiler rather than the kernel alone.

- **MAMMALIAN generator totality.** The text generator is total over the byte
  range — the per-character search never reaches its `ValueError`. It rests
  on `gcd(q + 1, 256) = 1` for even `q`, and on the SPRINT walk reaching an
  even array within 46 steps from each of the 23 pointers. Carried
  `native_decide`, a finite exhaustive check over 23 pointers x 256 SEED
  counts x 256 targets; the only one of the three that used it.
- **Factor round-trip.** The renderer round-trips its encoded program.
  Kernel-only: `propext`, `Classical.choice`, `Quot.sound`. The prime search
  rests on Dirichlet, not on computation.
- **The `%^2^-1` wall.** A program reading its own inputs cannot compute a
  two-input Boolean function. Kernel-only across the whole chain. It bounds
  the *reading* model, and the shipped generator is parameterized, so it does
  not bound that.
- **The 123 geometry reduction.** A per-arity certificate, and of different
  provenance: a prose argument over a finite certificate the code recomputes
  from scratch every process, never a Lean theorem. Kept here because it
  plays the same role — it is what a size optimization's correctness rests on.

These results do not extend to parameterized programs beyond the construction
models they state. A new claim needs an executable witness or a checked proof.
