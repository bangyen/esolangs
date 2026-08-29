import Esolangs.MammalianTotality
import Esolangs.FactorCorrect
import Esolangs.PctBooleanWall

/-!
# Esolangs

The library root: importing `Esolangs` pulls in every proof the project
keeps.  This is also the `lakefile.toml` default target, so `lake build`
(and `just lint-lean`) check all of them.

That coupling is deliberate.  This file used to *be* the MAMMALIAN proof --
it started as `extra/lean/mammalian/LeanMammalian.lean` and was renamed to
the library root when the project grew, keeping its contents.  Back then the
root also imported every other proof, so the default target really did build
the whole project; when those modules were dropped the imports went with
them, and the target quietly narrowed to "MAMMALIAN only".  Nothing built
`FactorCorrect` or `PctBooleanWall` after that, which is how
`BfMintermCorrect` was able to rot into 35 elaboration errors unnoticed
before it was removed.

Keep every proof module imported here.  A proof outside this list is checked
by no automation.

* `Esolangs.MammalianTotality` -- the MAMMALIAN generator search is total
  (`search_total`), verified by computation over the finite state space.
* `Esolangs.FactorCorrect` -- the Factor prime search is total (Dirichlet)
  and `decode (encode code) = code`.
* `Esolangs.PctBooleanWall` -- `%^2^-1` has no two-input boolean generator
  at any program length (`computes_ignores`).  Its axiom audit lives in
  `Esolangs/PctWallCheck.lean`, which is deliberately *not* imported: it
  exists to be run by hand, and its `#print axioms` output is only visible
  when the file is elaborated directly.
-/
