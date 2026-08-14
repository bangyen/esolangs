import Mathlib
import Esolangs.AlbabetCorrect

/-! AlbaBet interpreter equivalence

The reference interpreter ``src/esolangs/interpreters/other/albabet.py``
runs AlbaBet on two registers ``x`` and ``y``: ``a``/``b`` move ``x`` by
+1 or -1 (clamping at 0), ``c``/``d`` set ``x`` to 0 (``d`` parking the old
``x`` in ``y``), ``e``/``f`` copy ``x`` into ``y`` or clear ``y``,
``g``/``h`` multiply ``x`` by ``y`` or square ``x``, and ``i`` prints ``x``
as a character.  Every character is a defined operation or a no-op, so the
reference interpreter is *total*: unlike EXCON there is no ``HaltError``
underflow to guard against.

The ported interpreter (``Esolangs/Albabet.lean``, exposed purely as
``AlbabetCorrect.step`` / ``AlbabetCorrect.runList``) agrees with the
reference on every instruction except the state ``i`` leaves behind when it
prints an invalid scalar value: the reference zeroes ``x`` (its
``Char.ofNat`` analog is ``chr``), while the port keeps ``x`` — Lean's
``Char.ofNat`` yields NUL for the invalid scalar (the surrogate range
0xD800-0xDFFF, or values at or above 0x110000) without touching ``x``.
Both print NUL in that case, so the current output agrees, but the different
``x`` value changes what a *later* ``i`` prints.  The equivalence is
therefore stated under the guard ``Clean``: the program never runs ``i``
with an invalid scalar in ``x``.  Under that guard the reference never
zeroes ``x`` at an ``i``, so the two interpreters reach the same state and
print the same output, for every program.

As with ``ExconSemanticsCorrect``, the reference model ``pstep`` reuses the
ported transitions (via ``AlbabetCorrect.step``) so the theorem certifies
the port itself; ``validScalar`` is the reference's "no zeroing" condition
copied from the interpreter's ``i`` handler.
-/

namespace AlbabetSemanticsCorrect

set_option linter.unusedVariables false

open AlbabetCorrect

/-! ### 1. Valid scalars -/

/-- A valid Unicode scalar value, exactly the reference ``i`` handler's
"does not zero ``x``" condition: below the surrogates, or between the
surrogate range and 0x110000. -/
@[reducible] def validScalar (x : ℕ) : Prop :=
  x < 0xD800 ∨ 0xDFFF < x ∧ x < 0x110000

/-! ### 2. The reference interpreter as a pure model -/

/-- The reference interpreter's transition on one instruction.  It matches
``AlbabetCorrect.step`` except that ``i`` zeroes ``x`` when it prints an
invalid scalar. -/
def pstep (st : State) (c : Char) : State :=
  let (x, y, s) := st
  if c = 'a' then (x + 1, y, s)
  else if c = 'b' then (x - 1, y, s)
  else if c = 'c' then (0, y, s)
  else if c = 'd' then (0, x, s)
  else if c = 'e' then (x, x, s)
  else if c = 'f' then (x, 0, s)
  else if c = 'g' then (x * y, y, s)
  else if c = 'h' then (x * x, y, s)
  else if c = 'i' then
    let x' := if validScalar x then x else 0
    (x', y, s ++ toString (Char.ofNat x'))
  else st

/-- Run the reference interpreter from a state (it never halts). -/
def pRun : List Char → State → State
  | [], st => st
  | c :: rest, st => pRun rest (pstep st c)

/-- The reference interpreter's output from a reset pool. -/
def pRunOut (prog : List Char) (out : String) : String :=
  (pRun prog (0, 0, out)).2.2

/-! ### 3. The guard -/

/-- ``Clean prog st``: running ``prog`` from ``st`` never executes ``i`` with
an invalid scalar in ``x``.  Under this guard the reference never zeroes
``x`` at an ``i``, so it and the port agree. -/
def Clean : List Char → State → Prop
  | [], st => True
  | c :: rest, st => (c = 'i' → validScalar st.1) ∧ Clean rest (step st c)

/-- Cleanliness is preserved by the ported transition. -/
lemma Clean_append (l1 l2 : List Char) (st : State) :
    Clean l1 st → Clean l2 (runList l1 st) → Clean (l1 ++ l2) st := by
  induction l1 generalizing st with
  | nil =>
      intro h1 h2
      rw [runList_nil] at h2
      simpa [Clean] using h2
  | cons c rest ih =>
      intro h1 h2
      rcases h1 with ⟨hi, hrest⟩
      unfold Clean
      rw [show (c :: rest) ++ l2 = c :: (rest ++ l2) by simp]
      constructor
      · exact hi
      · rw [runList_cons] at h2
        exact ih (step st c) hrest h2

/-! ### 4. Agreement under the guard -/

/-- Under ``validScalar`` at an ``i`` the reference and ported transitions
agree. -/
lemma pstep_eq_step {st : State} {c : Char} (hi : c = 'i' → validScalar st.1) :
    pstep st c = step st c := by
  rcases st with ⟨x, y, s⟩
  by_cases hc : c = 'a'
  · subst c
    simp [pstep, step]
  · by_cases hc' : c = 'b'
    · subst c
      simp [pstep, step, hc]
    · by_cases hc'' : c = 'c'
      · subst c
        simp [pstep, step, hc, hc']
      · by_cases hc3 : c = 'd'
        · subst c
          simp [pstep, step, hc, hc', hc'']
        · by_cases hc4 : c = 'e'
          · subst c
            simp [pstep, step, hc, hc', hc'', hc3]
          · by_cases hc5 : c = 'f'
            · subst c
              simp [pstep, step, hc, hc', hc'', hc3, hc4]
            · by_cases hc6 : c = 'g'
              · subst c
                simp [pstep, step, hc, hc', hc'', hc3, hc4, hc5]
              · by_cases hc7 : c = 'h'
                · subst c
                  simp [pstep, step, hc, hc', hc'', hc3, hc4, hc5, hc6]
                · by_cases hc8 : c = 'i'
                  · subst c
                    have hv : validScalar x := hi rfl
                    simp [pstep, step, hc, hc', hc'', hc3, hc4, hc5, hc6, hc7, hv]
                  · simp [pstep, step, hc, hc', hc'', hc3, hc4, hc5, hc6, hc7, hc8]

/-- **Interpreter equivalence.**  For a clean program the reference and
ported interpreters reach the same state. -/
theorem runList_eq_pRun (prog : List Char) (st : State) (hc : Clean prog st) :
    pRun prog st = runList prog st := by
  induction prog generalizing st with
  | nil => rfl
  | cons c rest ih =>
      rcases hc with ⟨hi, hrest⟩
      have hstep : pstep st c = step st c := pstep_eq_step hi
      rw [show pRun (c :: rest) st = pRun rest (pstep st c) by rfl]
      rw [hstep]
      exact ih (step st c) hrest

/-! ### 5. The output -/

/-- **Output equivalence.**  For a clean program the reference and ported
interpreters print exactly the same string. -/
theorem output_eq (prog : List Char) (out : String) (hc : Clean prog (0, 0, out)) :
    pRunOut prog out = (runList prog (0, 0, out)).2.2 := by
  unfold pRunOut
  rw [runList_eq_pRun prog (0, 0, out) hc]

/-- **Output equivalence from a reset pool.**  Same statement in terms of
``exec``, the ported interpreter's output for a program. -/
theorem output_eq_exec (prog : List Char) (hc : Clean prog (0, 0, "")) :
    pRunOut prog "" = exec prog := by
  simpa [exec] using output_eq prog "" hc

/-! ### 6. Generated programs are clean -/

/-- A run of ``a``s is clean: none of them are ``i``. -/
lemma Clean_replicate_a (v x : ℕ) (y : ℕ) (s : String) :
    Clean (List.replicate v 'a') (x, y, s) := by
  induction v generalizing x with
  | zero => simp [Clean]
  | succ v ih =>
      rw [List.replicate_succ]
      simp [Clean, step]
      exact ih (x + 1)

/-- One character's program ``c`` + ``a``s + ``i`` is clean from any state:
``c`` zeroes ``x`` and the ``a`` run leaves it at ``v`` (a valid scalar when
``v < 0xD800``), so the ``i`` never prints an invalid scalar. -/
lemma Clean_charProg (v x : ℕ) (y : ℕ) (s : String) (hv : v < 0xD800) :
    Clean (charProg v) (x, y, s) := by
  unfold charProg
  have hc_neq : 'c' ≠ 'i' := by decide
  simp [Clean, step, hc_neq]
  apply Clean_append
  · exact Clean_replicate_a v 0 y s
  · rw [runList_replicate_a v 0 y s]
    simp [Clean]
    exact Or.inl hv

/-- The generated program for a byte-range text is clean from any state:
every ``i`` prints the character's own code, which is below 256. -/
lemma Clean_textProg (t : List Char) (ht : ∀ c ∈ t, c.toNat < 256) :
    ∀ (x y : ℕ), ∀ s : String, Clean (textProg t) (x, y, s) := by
  induction t with
  | nil => intro x y s; simp [textProg, Clean]
  | cons c cs ih =>
      intro x y s
      rw [textProg]
      apply Clean_append
      · apply Clean_charProg c.toNat x y s
        have hc256 : c.toNat < 256 := ht c (by simp)
        omega
      · rw [run_charProgC c x y s]
        exact ih (fun c' hc' => ht c' (by simp [hc'])) c.toNat y (s ++ toString (Char.ofNat c.toNat))

/-- **Generator programs agree.**  For every byte-range text the reference
and ported interpreters print exactly the same thing, so the generator
program's output is well-defined across both. -/
theorem generator_output_eq (t : List Char) (ht : ∀ c ∈ t, c.toNat < 256) :
    pRunOut (textProg t) "" = exec (textProg t) := by
  exact output_eq_exec (textProg t) (Clean_textProg t ht 0 0 "")

end AlbabetSemanticsCorrect
