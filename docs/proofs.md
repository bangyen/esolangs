# Proofs

Two results were machine-checked in Lean 4 + mathlib. The sources were
deleted in `4317b0bb` and stay recoverable at `528fe2c2`; what is kept here
is prose transcribed from each proof file's docstring, so the statements say
what the theorems said. Source and tests are the primary evidence.

A third, MAMMALIAN generator totality, is not kept: it stated that the text
generator's per-character search never reaches its `ValueError`, and the
text generators were removed. It was the only one carrying `native_decide`;
the two below are kernel-only, and `sorryAx` would mark a gap and never
appeared in any of them.

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
