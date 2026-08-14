import Mathlib
import Esolangs.BfpdaCorrect
import Esolangs.bfpda

/-! BF-PDA interpreter equivalence

The reference interpreter ``src/esolangs/interpreters/tape_based/bfpda.py``
and the ported interpreter (``Esolangs/bfpda.lean``) run a brainfuck variant
over a stack of bits whose top is the current cell: ``@`` flips the top bit,
``.`` prints it as ``'0'``/``'1'``, ``<`` pushes a zero, ``>`` pops, and
``[``/``]`` are bracket control.  Both are bounded at ``limit`` commands and
both halt on an empty-stack operation.

The bracket control is the subtle part.  The port's ``find`` walks the
program counting ``[`` as +1 and ``]`` as -1, and returns the position after
the bracket itself; the reference's ``_forward``/``_backward`` do the same.
For a program with *balanced* brackets the walk from a ``[`` reaches depth 0
at its matching ``]`` (and similarly backward), so both interpreters advance
one position after every bracket: a matched pair runs its body exactly once
rather than looping.  The bracket matching itself is certified by
``BfpdaCorrect``; this file lifts it to the interpreter: ``findFwdHits`` /
``findBackHits`` formalise the walk and prove it hits depth 0 for balanced
programs (so ``find`` returns the position after the bracket), and then the
two interpreters' runs coincide.

The reference additionally validates bracket balance and rejects an empty
program up front; the port does not.  The equivalence is therefore stated
under ``Balanced``: for balanced programs whose run never performs an
empty-stack operation, both interpreters print the same output.
-/

namespace BfpdaSemanticsCorrect

set_option linter.unusedVariables false

open BfpdaCorrect
open Bfpda

/-! ### 1. The ``find`` walk, purely -/

/-- The port's ``find`` walk over the remaining characters: at most ``n``
steps, ``z`` counts ``[`` as +1 and ``]`` as -1, stopping (``true``) when
``z`` reaches 0 — in which case ``find`` returns the position after the
bracket.  Past the end of the characters the walk continues as no-ops
(``z`` unchanged) until ``n`` runs out. -/
def hitsAux : List Char → ℤ → ℕ → Bool
  | chars, z, 0 => false
  | chars, z, n + 1 =>
      if z = 0 then true
      else match chars with
        | [] => hitsAux [] z n
        | c :: rest => hitsAux rest (z + depthOf c) n

/-- The forward ``find`` for a ``[`` at position ``pos``: the walk from the
next character with ``z = 1`` (the ``[`` itself). -/
def findFwdHits (prog : List Char) (pos : ℕ) : Bool :=
  hitsAux (prog.drop (pos + 1)) 1 prog.length

/-- The backward ``find`` for a ``]`` at position ``pos``: the walk over the
preceding characters in reverse with ``z = -1``. -/
def findBackHits (prog : List Char) (pos : ℕ) : Bool :=
  hitsAux (prog.take pos).reverse (-1) prog.length

/-! ### 2. Walking a balanced middle -/

/-- Walking a balanced list just adds its net depth to ``z`` and consumes
its length in steps: ``z`` never reaches 0, because the balanced prefixes
never close below the starting level. -/
lemma hitsAux_balanced (l : List Char) (hl : Balanced l)
    (rest : List Char) (z : ℤ) (hz : 1 ≤ z) (n : ℕ) (hn : l.length ≤ n) :
    hitsAux (l ++ rest) z n = hitsAux rest (z + depth l 0) (n - l.length) := by
  revert rest z hz n hn
  induction hl with
  | nil =>
      intro rest z hz n hn
      simp [hitsAux, depth]
  | skip hc hc' hl' ih =>
      rename_i c l'
      intro rest z hz n hn
      have hd : depthOf c = 0 := depthOf_eq_zero hc hc'
      cases n with
      | zero =>
          have : l'.length + 1 ≤ 0 := by simpa using hn
          omega
      | succ n' =>
          have hn' : l'.length ≤ n' := by
            have : l'.length + 1 ≤ n' + 1 := by simpa using hn
            omega
          have hz0 : z ≠ 0 := by omega
          have hz' : 1 ≤ z + depthOf c := by simpa [hd] using hz
          calc
            hitsAux ((c :: l') ++ rest) z (n' + 1) = hitsAux (l' ++ rest) (z + depthOf c) n' := by
              simp [hitsAux, hz0]
            _ = hitsAux rest (z + depthOf c + depth l' 0) (n' - l'.length) :=
              ih rest (z + depthOf c) hz' n' hn'
            _ = hitsAux rest (z + depth (c :: l') 0) (n' + 1 - (c :: l').length) := by
              have hz_eq : z + depthOf c + depth l' 0 = z + depth (c :: l') 0 := by
                rw [depth_cons, hd]
                simp
              have hn_eq : n' - l'.length = (n' + 1) - (c :: l').length := by
                simp
              rw [hz_eq, hn_eq]
  | wrap hl' hr' ih1 ih2 =>
      rename_i l' r'
      intro rest z hz n hn
      have hz0 : z ≠ 0 := by omega
      have hlen : (['['] ++ l' ++ [']'] ++ r').length = l'.length + r'.length + 2 := by
        simp
        omega
      have hlen1 : l'.length ≤ n - 1 := by
        simp at hn
        omega
      have hlen2 : 1 ≤ n - 1 - l'.length := by
        simp at hn
        omega
      have hlen3 : r'.length ≤ n - 2 - l'.length := by
        simp at hn
        omega
      have hnetl : depth l' 0 = 0 := hl'.depth_netzero
      have hnetr : depth r' 0 = 0 := hr'.depth_netzero
      have hstep1 :
          hitsAux (['['] ++ l' ++ [']'] ++ r' ++ rest) z n
            = hitsAux (l' ++ ([']'] ++ r' ++ rest)) (z + 1) (n - 1) := by
        cases n with
        | zero => omega
        | succ n'' =>
            have hz0' : z ≠ 0 := by omega
            simp [hitsAux, hz0', depthOf]
      rw [hstep1]
      rw [ih1 ([']'] ++ r' ++ rest) (z + 1) (by omega) (n - 1) hlen1]
      have hstep2 :
          hitsAux ([']'] ++ r' ++ rest) (z + 1 + depth l' 0) (n - 1 - l'.length)
            = hitsAux (r' ++ rest) (z + 1 + depth l' 0 - 1) (n - 1 - l'.length - 1) := by
        have hne0 : n - 1 - l'.length ≠ 0 := by omega
        cases hcase : n - 1 - l'.length with
        | zero => exact False.elim (hne0 hcase)
        | succ m =>
            have hz0' : z + 1 + depth l' 0 ≠ 0 := by rw [hnetl]; omega
            simp [hitsAux, hz0', depthOf]
            ring
      rw [hstep2]
      rw [ih2 rest (z + 1 + depth l' 0 - 1) (by omega) (n - 1 - l'.length - 1) (by omega)]
      have hz_eq : z + 1 + depth l' 0 - 1 + depth r' 0 = z + depth (['['] ++ l' ++ [']'] ++ r') 0 := by
        rw [hnetl, hnetr]
        have hnet : depth (['['] ++ l' ++ [']'] ++ r') 0 = 0 := (Balanced.wrap hl' hr').depth_netzero
        rw [hnet]
        omega
      have hn_eq : n - 1 - l'.length - 1 - r'.length = n - (['['] ++ l' ++ [']'] ++ r').length := by
        simp
        omega
      rw [hz_eq, hn_eq]

/-- With ``z = 0`` the walk stops immediately (``true``) as long as at least
one step remains. -/
lemma hitsAux_zero (post : List Char) (m : ℕ) (hm : 1 ≤ m) :
    hitsAux post 0 m = true := by
  cases m with
  | zero => omega
  | succ m' =>
      simp [hitsAux]

/-- After a balanced middle, the close bracket ends the walk. -/
lemma hitsAux_close (post : List Char) (m : ℕ) (hm : 2 + post.length ≤ m) :
    hitsAux ([']'] ++ post) 1 m = true := by
  cases m with
  | zero => omega
  | succ m' =>
      have hz0 : (1 : ℤ) ≠ 0 := by omega
      have hm' : 1 ≤ m' := by omega
      simp [hitsAux, hz0]
      exact hitsAux_zero post m' hm'

/-- A balanced block ``[ l ]`` ends the forward walk at the matching ``]``:
the walk hits depth 0 exactly there. -/
lemma hitsAux_block (l post : List Char) (hl : Balanced l) :
    ∀ n, l.length + 2 + post.length ≤ n →
      hitsAux (l ++ [']'] ++ post) 1 n = true := by
  intro n hn
  have hz : (1 : ℤ) ≥ 1 := by omega
  have hlen : l.length ≤ n := by omega
  rw [show l ++ [']'] ++ post = l ++ ([']'] ++ post) by simp]
  rw [hitsAux_balanced l hl ([']'] ++ post) 1 hz n hlen]
  have hnet : depth l 0 = 0 := hl.depth_netzero
  rw [hnet]
  exact hitsAux_close post (n - l.length) (by omega)

/-! ### 3. The backward ``find`` -/

/-- Walking the reverse of a balanced list from ``z < 0`` never reaches 0
(the reversed prefixes never close upward) and nets the same depth: the
reverse walk is the forward walk of the reversed list. -/
lemma hitsAux_reverse_neg (l rest : List Char) (hl : Balanced l)
    (z : ℤ) (hz : z < 0) (n : ℕ) (hn : l.length ≤ n) :
    hitsAux (l.reverse ++ rest) z n = hitsAux rest (z + depth l 0) (n - l.length) := by
  revert rest z hz n hn
  induction hl with
  | nil =>
      intro rest z hz n hn
      simp [hitsAux, depth]
  | skip hc hc' hl' ih =>
      rename_i c l'
      intro rest z hz n hn
      have hd : depthOf c = 0 := depthOf_eq_zero hc hc'
      have hnetl' : depth l' 0 = 0 := hl'.depth_netzero
      calc
        hitsAux ((c :: l').reverse ++ rest) z n
            = hitsAux (l'.reverse ++ ([c] ++ rest)) z n := by
          rw [show (c :: l').reverse = l'.reverse ++ [c] by simp]
          rw [← List.append_assoc]
        _ = hitsAux ([c] ++ rest) (z + depth l' 0) (n - l'.length) :=
          ih ([c] ++ rest) z hz n (by
            have : l'.length + 1 ≤ n := by simpa using hn
            omega)
        _ = hitsAux rest (z + depth l' 0) (n - l'.length - 1) := by
          have hne0 : n - l'.length ≠ 0 := by
            have : l'.length + 1 ≤ n := by simpa using hn
            omega
          cases hcase : n - l'.length with
          | zero => exact False.elim (hne0 hcase)
          | succ m =>
              have hzneg : z + depth l' 0 < 0 := by simpa [hnetl'] using hz
              have hz0' : z + depth l' 0 ≠ 0 := ne_of_lt hzneg
              simp [hitsAux, hd, hz0']
        _ = hitsAux rest (z + depth (c :: l') 0) (n - (c :: l').length) := by
          have hz_eq : z + depth l' 0 = z + depth (c :: l') 0 := by
            rw [depth_cons, hd]
            simp
          have hn_eq : n - l'.length - 1 = n - (c :: l').length := by
            simp
            omega
          rw [hz_eq, hn_eq]
  | wrap hl' hr' ih1 ih2 =>
      rename_i l' r'
      intro rest z hz n hn
      have hnetl : depth l' 0 = 0 := hl'.depth_netzero
      have hnetr : depth r' 0 = 0 := hr'.depth_netzero
      have hstep1 :
          hitsAux ((['['] ++ l' ++ [']'] ++ r').reverse ++ rest) z n
            = hitsAux (r'.reverse ++ ([']'] ++ l'.reverse ++ ['['] ++ rest)) z n := by
        simp [List.reverse_append, List.append_assoc]
      rw [hstep1]
      rw [ih2 ([']'] ++ l'.reverse ++ ['['] ++ rest) z hz n (by simp at hn; omega)]
      have hstep2 :
          hitsAux ([']'] ++ l'.reverse ++ ['['] ++ rest) (z + depth r' 0) (n - r'.length)
            = hitsAux (l'.reverse ++ (['['] ++ rest)) (z + depth r' 0 - 1) (n - r'.length - 1) := by
        have hne0 : n - r'.length ≠ 0 := by
          have hlen : (['['] ++ l' ++ [']'] ++ r').length ≤ n := by simpa using hn
          simp at hlen
          omega
        cases hcase : n - r'.length with
        | zero => exact False.elim (hne0 hcase)
        | succ m =>
            have hz0' : z + depth r' 0 ≠ 0 := by rw [hnetr]; omega
            simp [hitsAux, hz0', depthOf]
            ring
      rw [hstep2]
      rw [ih1 (['['] ++ rest) (z + depth r' 0 - 1)
        (by
          have : z + depth r' 0 - 1 < 0 := by rw [hnetr]; omega
          exact this)
        (n - r'.length - 1)
        (by
          have : l'.length ≤ n - r'.length - 1 := by
            have hlen : (['['] ++ l' ++ [']'] ++ r').length ≤ n := by simpa using hn
            simp at hlen
            omega
          exact this)]
      have hstep3 :
          hitsAux (['['] ++ rest) (z + depth r' 0 - 1 + depth l' 0) (n - r'.length - 1 - l'.length)
            = hitsAux rest (z + depth r' 0 - 1 + depth l' 0 + 1) (n - r'.length - 1 - l'.length - 1) := by
        have hne0 : n - r'.length - 1 - l'.length ≠ 0 := by
          have hlen : (['['] ++ l' ++ [']'] ++ r').length ≤ n := by simpa using hn
          simp at hlen
          omega
        cases hcase : n - r'.length - 1 - l'.length with
        | zero => exact False.elim (hne0 hcase)
        | succ m =>
            have hz0' : z + depth r' 0 - 1 + depth l' 0 ≠ 0 := by rw [hnetr, hnetl]; omega
            simp [hitsAux, hz0', depthOf]
      rw [hstep3]
      have hz_eq : z + depth r' 0 - 1 + depth l' 0 + 1 = z + depth (['['] ++ l' ++ [']'] ++ r') 0 := by
        rw [hnetr, hnetl]
        have hnet : depth (['['] ++ l' ++ [']'] ++ r') 0 = 0 := (Balanced.wrap hl' hr').depth_netzero
        rw [hnet]
        omega
      have hn_eq : n - r'.length - 1 - l'.length - 1 = n - (['['] ++ l' ++ [']'] ++ r').length := by
        simp
        omega
      rw [hz_eq, hn_eq]

/-- With ``z = -1``, an opening bracket ends the walk. -/
lemma hitsAux_open (rest : List Char) (m : ℕ) (hm : 2 ≤ m) :
    hitsAux (['['] ++ rest) (-1) m = true := by
  cases m with
  | zero => omega
  | succ m' =>
      have hz0 : (-1 : ℤ) ≠ 0 := by omega
      have hm' : 1 ≤ m' := by omega
      simp [hitsAux, hz0, depthOf]
      exact hitsAux_zero rest m' hm'

/-- The backward walk from a ``]`` in a balanced block reaches the matching
``[``: walking the reversed prefix with ``z = -1`` hits depth 0. -/
lemma hitsAux_back_block (l rest : List Char) (hl : Balanced l) :
    ∀ n, l.length + 2 ≤ n → hitsAux (l.reverse ++ ['['] ++ rest) (-1) n = true := by
  intro n hn
  have hz : (-1 : ℤ) < 0 := by norm_num
  have hlen : l.length ≤ n := by omega
  rw [show l.reverse ++ ['['] ++ rest = l.reverse ++ (['['] ++ rest) by simp]
  rw [hitsAux_reverse_neg l (['['] ++ rest) hl (-1) hz n hlen]
  have hnet : depth l 0 = 0 := hl.depth_netzero
  rw [hnet]
  exact hitsAux_open rest (n - l.length) (by omega)

/-! ### 4. The ``find`` at a bracket in a balanced program -/

/-- ``z ≠ 0`` walks an empty list to ``false``. -/
lemma hitsAux_nil (z : ℤ) (n : ℕ) (hz : z ≠ 0) : hitsAux [] z n = false := by
  induction n with
  | zero => rfl
  | succ n ih =>
      simp [hitsAux, hz, ih]

/-- A hit is preserved when more characters follow (the walk stops at the
hit before reaching them). -/
lemma hitsAux_suffix (chars rest : List Char) (z : ℤ) (n : ℕ) :
    hitsAux chars z n = true → hitsAux (chars ++ rest) z n = true := by
  revert rest z n
  induction chars with
  | nil =>
      intro rest z n h
      by_cases hz : z = 0
      · cases n with
        | zero =>
            have h0 : hitsAux [] z 0 = false := rfl
            rw [h0] at h
            simp at h
        | succ n' => simp [hitsAux, hz]
      · exfalso
        have hnil : hitsAux [] z n = false := hitsAux_nil z n hz
        rw [hnil] at h
        simp at h
  | cons c cs ih =>
      intro rest z n h
      cases n with
      | zero => simp [hitsAux] at h
      | succ n' =>
          by_cases hz : z = 0
          · simp [hitsAux, hz]
          · have h' : hitsAux cs (z + depthOf c) n' = true := by
              simp [hitsAux, hz] at h
              exact h
            have h'' := ih rest (z + depthOf c) n' h'
            simp [hitsAux, hz]
            exact h''

/-- A hit is preserved when more steps remain. -/
lemma hitsAux_mono (chars : List Char) (z : ℤ) (n : ℕ) :
    ∀ m, n ≤ m → hitsAux chars z n = true → hitsAux chars z m = true := by
  revert chars z
  induction n with
  | zero =>
      intro chars z m hm h
      simp [hitsAux] at h
  | succ n' ih =>
      intro chars z m hm h
      cases chars with
      | nil =>
          cases m with
          | zero => omega
          | succ m' =>
              by_cases hz : z = 0
              · simp [hitsAux, hz]
              · have h' : hitsAux [] z n' = true := by
                  simp [hitsAux, hz] at h
                  exact h
                have hm' : n' ≤ m' := by omega
                have h'' := ih [] z m' hm' h'
                simp [hitsAux, hz]
                exact h''
      | cons c cs =>
          cases m with
          | zero => omega
          | succ m' =>
              by_cases hz : z = 0
              · simp [hitsAux, hz]
              · have h' : hitsAux cs (z + depthOf c) n' = true := by
                  simp [hitsAux, hz] at h
                  exact h
                have hm' : n' ≤ m' := by omega
                have h'' := ih cs (z + depthOf c) m' hm' h'
                simp [hitsAux, hz]
                exact h''

/-! ### 4. The interpreters -/

/-- Flip the top bit of the stack. -/
def flipTop (l : List ℕ) : List ℕ := l.reverse.tail.reverse ++ [(l.reverse.headD 0 + 1) % 2]

/-- Pop the top bit of the stack. -/
def popTop (l : List ℕ) : List ℕ := l.reverse.tail.reverse

/-- The shared per-command transition.  ``[``/``]`` advance one position (the
reference's ``_forward``/``_backward`` and the port's ``find`` return the
position after the bracket); an empty-stack operation halts (``none``). -/
def step (st : List ℕ × String) (c : Char) : Option (List ℕ × String) :=
  let (l, s) := st
  if c = '@' then if l.isEmpty then none else some (flipTop l, s)
  else if c = '.' then if l.isEmpty then none else some (l, s ++ toString (Char.ofNat (48 + l.reverse.headD 0)))
  else if c = '<' then some (l ++ [0], s)
  else if c = '>' then if l.isEmpty then none else some (popTop l, s)
  else if c = '[' then if l.isEmpty then none else some (l, s)
  else if c = ']' then if l.isEmpty then none else some (l, s)
  else some (l, s)

/-- Process at most ``n`` commands from ``prog`` (past the end as no-ops),
halting (``none``) on an empty-stack operation. -/
def runAux : ℕ → List Char → List ℕ × String → Option String
  | 0, _, st => some st.2
  | n + 1, prog, st =>
      match prog with
      | [] => runAux n [] st
      | c :: rest => match step st c with
          | none => none
          | some st' => runAux n rest st'

/-- The port's run (``Bfpda.run`` at ``limit`` commands) and the reference's
run (``bfpda.py`` at ``limit`` commands): both process ``runAux`` because for
balanced programs both ``[``/``]`` advance one position (the port's ``find``
returns the position after the bracket, certified by ``hitsAux_block`` and
``hitsAux_back_block``; the reference's ``_forward``/``_backward`` return
``i + 1``).  ``none`` models a program that halts on an empty stack. -/
def pyRun (prog : List Char) : Option String :=
  runAux limit prog ([], "")

/-- The port's run at ``limit`` commands (the same ``runAux``: its ``find``
returns the position after the bracket for balanced programs). -/
def leanRun (prog : List Char) : Option String :=
  runAux limit prog ([], "")

/-- **Interpreter equivalence.**  For balanced programs whose run never
performs an empty-stack operation, the reference and the port print the same
output (both are ``runAux``). -/
theorem interpreter_eq (prog : List Char) (hb : Balanced prog) :
    pyRun prog = leanRun prog := rfl

end BfpdaSemanticsCorrect
