import Esolangs

/-! Axiom audit for the kept proofs.

`#print axioms` reports what each theorem ultimately rests on.  Two names are
worth watching for:

* `sorryAx` -- a gap in the proof.  Should never appear.
* `Lean.ofReduceBool` -- a `native_decide` step, which trusts the Lean
  *compiler* in addition to the kernel.

The `%^2^-1` wall and the Factor proofs are kernel-only: they report just
`propext`, `Classical.choice`, and `Quot.sound`.  MAMMALIAN's totality
results legitimately carry `native_decide` axioms -- they are finite
exhaustive checks over 23 pointers x 256 SEED counts x 256 targets, which is
what `native_decide` is for -- so their entries name
`..._native.native_decide.ax_1_1`.  That distinction is expected, not a
defect; what matters is that it does not spread to the others.

This file is not imported by `Esolangs.lean`: `#print axioms` writes to the
message log, so it has to be elaborated directly to be read:

```
lake env lean Esolangs/AxiomAudit.lean
```
-/

-- The `%^2^-1` wall: kernel-only.
#print axioms PctBooleanWall.count_le_of_halts
#print axioms PctBooleanWall.lockstep_first
#print axioms PctBooleanWall.lockstep_two
#print axioms PctBooleanWall.computes_splits
#print axioms PctBooleanWall.computes_ignores
#print axioms PctBooleanWall.no_xor
#print axioms PctBooleanWall.no_and
#print axioms PctBooleanWall.no_two_input_generator

-- Factor: kernel-only (the prime search rests on Dirichlet, not computation).
#print axioms FactorCorrect.decode_encode

-- MAMMALIAN: `native_decide` axioms are expected here, and only here.
#print axioms MammalianTotality.even_q_solvable
#print axioms MammalianTotality.walk_reaches_even
#print axioms MammalianTotality.search_total
