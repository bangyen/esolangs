import Esolangs.PctBooleanWall

/-! Axiom audit for the `%^2^-1` wall.

`#print axioms` on the main theorems must report only Lean's three standard
axioms (`propext`, `Classical.choice`, `Quot.sound`) — in particular no
`sorryAx`, which would mean a gap in the proof, and no `Lean.ofReduceBool`,
which would mean a `native_decide` kernel-external step. -/

open PctBooleanWall

#print axioms count_le_of_halts
#print axioms lockstep_first
#print axioms lockstep_two
#print axioms computes_splits
#print axioms computes_ignores
#print axioms no_xor
#print axioms no_and
#print axioms no_two_input_generator
