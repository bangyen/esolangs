import Mathlib
import Esolangs.ExconCorrect

/-! EXCON interpreter equivalence

The reference interpreter ``src/esolangs/interpreters/tape_based/excon.py``
runs EXCON with an 8-cell bit pool: ``:`` resets the pool and the pointer to
cell 7, ``^`` flips the current cell, ``!`` prints the pool as a binary byte
(MSB first), and ``<`` moves the pointer down, raising ``HaltError`` if it
would go below cell 0.  This file proves the ported interpreter's state
transitions (``Esolangs/Excon.lean``, exposed purely as ``ExconCorrect.step``
/ ``ExconCorrect.runList``) compute exactly the reference interpreter's
output for every program that does not walk the pointer off the pool.

The two interpreters agree on ``:``, ``^``, ``!`` and on ``<`` within the
valid pointer range.  The only divergence is the reference's error handling:
when ``<`` is executed at cell 0 the Python interpreter halts with
``HaltError``, while the port's ``(n - 1) % 8`` keeps the pointer at 0 and
continues.  The equivalence is therefore stated under the guard that the
reference run succeeds (``pyRun`` returning ``some``): for programs where it
does not halt, both interpreters compute the same output and final state.

The Python model reuses the ported transitions (``flips``, ``to_s`` via
``pyToS``) rather than reimplementing them, so the theorem certifies the
ported interpreter itself.  ``pyToS`` expands ``to_s`` as the binary read
``128*pool[0] + 64*pool[1] + ... + pool[7]`` that the reference's
``int("".join(pool), 2)`` computes.
-/

namespace ExconSemanticsCorrect

set_option linter.unusedVariables false

open Excon
open ExconCorrect

/-! ### 1. The printed byte -/

/-- The byte the reference ``!`` prints: the pool read as a binary number,
i.e. ``int("".join(pool), 2)``. -/
def pyToS (l : List ℕ) : String :=
  toString (Char.ofNat
    (128 * gets l 0 + 64 * gets l 1 + 32 * gets l 2 + 16 * gets l 3 +
     8 * gets l 4 + 4 * gets l 5 + 2 * gets l 6 + gets l 7))

/-- The port's ``to_s`` reads the pool back as exactly that binary number. -/
lemma to_s_eq_pyToS (l : List ℕ) : to_s l 7 0 = pyToS l := by
  unfold pyToS
  simp [to_s]
  apply congrArg toString
  apply congrArg Char.ofNat
  ring

/-! ### 2. The reference interpreter as a pure model -/

/-- The reference interpreter's transition on one instruction.  ``<`` at cell
0 returns ``none`` (the reference halts with ``HaltError``); every other
instruction is the ported transition. -/
def pstep (st : State) (c : Char) : Option State :=
  let (l, n, s) := st
  if c = ':' then some (empty_list, 7, s)
  else if c = '^' then some (flips l n, n, s)
  else if c = '<' then if n = 0 then none else some (l, n - 1, s)
  else if c = '!' then some (l, n, s ++ pyToS l)
  else some st

/-- Run the reference interpreter, halting (``none``) on a pointer underflow. -/
def pRun : List Char → State → Option State
  | [], st => some st
  | c :: rest, st =>
      match pstep st c with
      | none => none
      | some st' => pRun rest st'

/-- The reference interpreter's output from a reset pool (``none`` if it
halts with ``HaltError``). -/
def pyRun (prog : List Char) (out : String) : Option String :=
  match pRun prog (empty_list, 7, out) with
  | some st => some st.2.2
  | none => none

/-! ### 3. Agreement within the valid pointer range -/

/-- Within ``0..7`` the reference and ported transitions agree, and the
pointer stays in range. -/
lemma pstep_some {st st' : State} {c : Char} (hptr : st.2.1 ≤ 7)
    (h : pstep st c = some st') : step st c = st' ∧ st'.2.1 ≤ 7 := by
  rcases st with ⟨l, n, s⟩
  have hn7 : n ≤ 7 := by simpa using hptr
  by_cases hc : c = ':'
  · subst c
    have hst' : st' = (empty_list, 7, s) := by
      simp [pstep] at h
      exact h.symm
    rw [hst']
    simp [step]
  · by_cases hc' : c = '^'
    · subst c
      have hst' : st' = (flips l n, n, s) := by
        simp [pstep, hc] at h
        exact h.symm
      rw [hst']
      constructor
      · simp [step]
      · simpa using hn7
    · by_cases hc'' : c = '<'
      · subst c
        by_cases hn : n = 0
        · simp [pstep, hn] at h
        · have hnpos : 0 < n := Nat.pos_of_ne_zero hn
          have hsub : (n - 1) % 8 = n - 1 := Nat.mod_eq_of_lt (by omega)
          have hst' : st' = (l, n - 1, s) := by
            simp [pstep, hn] at h
            exact h.symm
          rw [hst']
          constructor
          · simp [step, hsub]
          · simp
            omega
      · by_cases hc''' : c = '!'
        · subst c
          have hst' : st' = (l, n, s ++ pyToS l) := by
            simp [pstep, hc, hc', hc''] at h
            exact h.symm
          rw [hst']
          constructor
          · simp [step, to_s_eq_pyToS]
          · simpa using hn7
        · have hst' : st' = (l, n, s) := by
            simp [pstep, hc, hc', hc'', hc'''] at h
            exact h.symm
          rw [hst']
          constructor
          · simp [step, hc, hc', hc'', hc''']
          · simpa using hn7

/-- **Interpreter equivalence.**  If the reference run of ``prog`` from a
state with the pointer in ``0..7`` succeeds, the ported interpreter reaches
the same state. -/
theorem runList_eq_pRun (prog : List Char) :
    ∀ (st : State), st.2.1 ≤ 7 → ∀ (st' : State), pRun prog st = some st' → runList prog st = st' := by
  induction prog with
  | nil =>
      intro st hptr st' h
      simp [pRun] at h
      simpa [runList] using h
  | cons c rest ih =>
      intro st hptr st' h
      have hsome : ∃ st0 : State, pstep st c = some st0 := by
        cases hstep : pstep st c with
        | none =>
            simp [pRun, hstep] at h
        | some st0 => exact ⟨st0, rfl⟩
      rcases hsome with ⟨st0, hst0⟩
      have hstep := pstep_some hptr hst0
      rcases hstep with ⟨hs, hptr0⟩
      have hrun : runList (c :: rest) st = runList rest st0 := by
        rw [runList_cons, hs]
      rw [hrun]
      exact ih st0 hptr0 st' (by
        simp [pRun, hst0] at h
        exact h)

/-! ### 4. The output -/

/-- **Output equivalence.**  When the reference interpreter prints an output
for ``prog`` (i.e. does not halt with ``HaltError``), the ported interpreter
prints exactly the same string. -/
theorem output_eq (prog : List Char) (out s : String)
    (h : pyRun prog out = some s) :
    s = (runList prog (empty_list, 7, out)).2.2 := by
  have hst0 : ∃ st0 : State, pRun prog (empty_list, 7, out) = some st0 := by
    unfold pyRun at h
    cases hrun0 : pRun prog (empty_list, 7, out) with
    | none => simp [hrun0] at h
    | some st0 => exact ⟨st0, rfl⟩
  rcases hst0 with ⟨st0, hst0⟩
  have heq := runList_eq_pRun prog (empty_list, 7, out) (by simp) st0 hst0
  unfold pyRun at h
  rw [hst0] at h
  have hs : st0.2.2 = s := Option.some.inj h
  rw [heq]
  exact hs.symm

/-- **Output equivalence from a reset pool.**  Same statement in terms of
``exec``, the ported interpreter's output for a program. -/
theorem output_eq_exec (prog : List Char) (s : String)
    (h : pyRun prog "" = some s) : s = exec prog := by
  simpa [exec] using output_eq prog "" s h

end ExconSemanticsCorrect
