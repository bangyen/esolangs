import Mathlib

/-! Correctness of the huf text generator

Huf is a register-based language with two variables, ``num`` and ``mul``.
The interpreter (``src/esolangs/interpreters/register_based/huf.py``) runs
only the ``#...@`` segments of the program; ``#`` resets ``num`` and ``mul``,
``+`` increments ``num`` while ``mul`` is zero and ``mul`` otherwise, ``|``
sets ``mul`` to 1, ``!`` sets ``num = num * (mul - 1)`` and zeroes ``mul``,
and ``>`` prints ``num`` as a character (halting if it is out of the valid
range).  The generator (``tools/generators/register.py::huf``) emits, for
each character, a multiply segment ``# +*a | +*b ! +*r >``: a run of ``a``
builds ``num = a``, ``|`` starts the multiplier, a run of ``b`` raises it to
``b + 1``, and ``!`` multiplies ``num`` by ``mul - 1`` so it becomes ``a*b``;
a final run of ``r`` tops it up to the character code.  This file proves the
segment is *correct*: it prints ``a*b + r`` — the same multiply-loop
invariant as the ``_bf_set`` proof — and that a program of such segments
prints exactly the target text through the interpreter's own transitions.
-/

namespace HufCorrect

/-- Machine state: ``num``, ``mul``, and the output. -/
@[ext]
structure State where
  num : ℕ
  mul : ℕ
  out : List Char

/-- One interpreter transition.  ``>`` prints ``num`` only when it is a valid
code point (the reference raises ``HaltError`` otherwise). -/
def step (s : State) (c : Char) : State :=
  match c with
  | '#' => { s with num := 0, mul := 0 }
  | '|' => { s with mul := 1 }
  | '!' => { s with num := s.num * (s.mul - 1), mul := 0 }
  | '+' => if s.mul = 0 then { s with num := s.num + 1 } else { s with mul := s.mul + 1 }
  | '>' => if s.num ≤ 0x10FFFF then { s with out := s.out ++ [Char.ofNat s.num], num := 0 } else s
  | _ => s

/-- Run a program (the interpreter's segment body) from a state. -/
def run (code : List Char) (s : State) : State :=
  code.foldl step s

/-! ### 1. Single symbols -/

lemma run_nil (s : State) : run [] s = s := by
  simp [run]

lemma run_cons (c : Char) (cs : List Char) (s : State) :
    run (c :: cs) s = run cs (step s c) := by
  simp [run]

lemma run_append (p q : List Char) (s : State) :
    run (p ++ q) s = run q (run p s) := by
  induction p generalizing s with
  | nil => simp [run]
  | cons c p ih =>
      rw [List.cons_append]
      rw [run_cons]
      rw [ih]
      rw [run_cons]

lemma step_hash (s : State) : step s '#' = { s with num := 0, mul := 0 } := by
  simp [step]

lemma step_pipe (s : State) : step s '|' = { s with mul := 1 } := by
  simp [step]

lemma step_bang (s : State) : step s '!' = { s with num := s.num * (s.mul - 1), mul := 0 } := by
  simp [step]

lemma step_plus_num (n : ℕ) (o : List Char) :
    step { num := n, mul := 0, out := o } '+' = { num := n + 1, mul := 0, out := o } := by
  simp [step]

lemma step_plus_mul (n m : ℕ) (o : List Char) (hm : m ≠ 0) :
    step { num := n, mul := m, out := o } '+' = { num := n, mul := m + 1, out := o } := by
  simp [step, hm]

lemma step_print (v m : ℕ) (o : List Char) (hv : v ≤ 0x10FFFF) :
    step { num := v, mul := m, out := o } '>' = { num := 0, mul := m, out := o ++ [Char.ofNat v] } := by
  simp [step, hv]

/-! ### 2. Runs of ``+`` -/

/-- While ``mul`` is zero, a run of ``a`` plus signs increments ``num`` by
``a``. -/
lemma run_plusN_num (a n : ℕ) (o : List Char) :
    run (List.replicate a '+') { num := n, mul := 0, out := o }
      = { num := n + a, mul := 0, out := o } := by
  induction a generalizing n with
  | zero => simp [run]
  | succ a ih =>
      rw [List.replicate_succ]
      rw [run_cons]
      rw [step_plus_num]
      rw [ih (n + 1)]
      ext <;> simp [Nat.add_assoc, Nat.add_left_comm, Nat.add_comm]

/-- While ``mul`` is nonzero, a run of ``b`` plus signs increments ``mul``
by ``b``. -/
lemma run_plusN_mul (b m n : ℕ) (o : List Char) (hm : m ≠ 0) :
    run (List.replicate b '+') { num := n, mul := m, out := o }
      = { num := n, mul := m + b, out := o } := by
  induction b generalizing m with
  | zero => simp [run]
  | succ b ih =>
      rw [List.replicate_succ]
      rw [run_cons]
      rw [step_plus_mul n m o hm]
      rw [ih (m + 1) (by omega : m + 1 ≠ 0)]
      ext <;> simp [Nat.add_assoc, Nat.add_left_comm, Nat.add_comm]

/-! ### 3. One character: ``# +*a | +*b ! +*r >`` -/

/-- One character's segment (as executed; the interpreter strips the closing
``@``). -/
def seg (a b r : ℕ) : List Char :=
  '#' :: (List.replicate a '+' ++ ['|'] ++ List.replicate b '+' ++ ['!'] ++
    List.replicate r '+' ++ ['>'])

/-- **Correctness of a segment.**  ``# +*a | +*b ! +*r >`` prints ``a*b + r``
(a byte range value, so the print is in range) and resets the registers. -/
lemma seg_correct (a b r : ℕ) (o : List Char) (h : a * b + r ≤ 0x10FFFF) :
    run (seg a b r) { num := 0, mul := 0, out := o }
      = { num := 0, mul := 0, out := o ++ [Char.ofNat (a * b + r)] } := by
  have hb : 1 + b - 1 = b := by omega
  have h' : a * (1 + b - 1) + r ≤ 0x10FFFF := by
    rw [hb]
    exact h
  unfold seg
  rw [run_cons, step_hash]
  change run (List.replicate a '+' ++ ['|'] ++ List.replicate b '+' ++ ['!'] ++
      List.replicate r '+' ++ ['>']) { num := 0, mul := 0, out := o }
        = { num := 0, mul := 0, out := o ++ [Char.ofNat (a * b + r)] }
  simp [run_append, run_cons, run_nil, run_plusN_num, run_plusN_mul, step_pipe, step_bang, hb, h]
  · simp [step, hb, h]

/-! ### 4. The whole text -/

/-- Concatenated segments for a list of ``(a, b, r)`` multipliers. -/
def progAux : List (ℕ × ℕ × ℕ) → List Char
  | [] => []
  | (a, b, r) :: ts => seg a b r ++ progAux ts

/-- **Auxiliary.**  Appending the segments for ``ts`` to an existing output
prints the encoded values. -/
lemma progAux_aux :
    ∀ (ts : List (ℕ × ℕ × ℕ)) (o : List Char),
      (∀ (a b r : ℕ), (a, b, r) ∈ ts → a * b + r ≤ 0x10FFFF) →
      run (progAux ts) { num := 0, mul := 0, out := o }
        = { num := 0, mul := 0, out := o ++ ts.map (fun (a, b, r) => Char.ofNat (a * b + r)) } := by
  intro ts
  induction ts with
  | nil => intro o h; simp [progAux, run]
  | cons t ts ih =>
      intro o h
      rcases t with ⟨a, b, r⟩
      rw [progAux]
      rw [run_append]
      have hseg := seg_correct a b r o (h a b r (by simp))
      rw [hseg]
      rw [ih (o ++ [Char.ofNat (a * b + r)]) (fun a b r h' => h a b r (by simp [h']))]
      ext <;> simp [List.append_assoc]

/-- **Correctness.**  A program of multiply segments prints exactly the
value each segment encodes. -/
theorem progAux_correct (ts : List (ℕ × ℕ × ℕ))
    (h : ∀ (a b r : ℕ), (a, b, r) ∈ ts → a * b + r ≤ 0x10FFFF) :
    run (progAux ts) { num := 0, mul := 0, out := [] }
      = { num := 0, mul := 0, out := ts.map (fun (a, b, r) => Char.ofNat (a * b + r)) } := by
  rw [progAux_aux ts [] h]
  simp

/-- **In terms of the generator's ``divmod``.**  For ``value = a*b + r`` the
segment prints exactly ``value``. -/
theorem huf_value (a value : ℕ) (_ha : 0 < a) (hv : value ≤ 0x10FFFF) :
    run (seg a (value / a) (value % a)) { num := 0, mul := 0, out := [] }
      = { num := 0, mul := 0, out := [Char.ofNat value] } := by
  have h : a * (value / a) + value % a = value := Nat.div_add_mod value a
  have hg : a * (value / a) + value % a ≤ 0x10FFFF := by
    rw [h]
    exact hv
  rw [seg_correct a (value / a) (value % a) [] hg]
  simp [h]

-- Sanity round-trips: ``# +*a | +*b ! +*r >`` prints ``a*b + r``.
example : (run (seg 3 2 1) { num := 0, mul := 0, out := [] }).out = [Char.ofNat 7] := by
  native_decide
example : (run (seg 1 9 9) { num := 0, mul := 0, out := [] }).out = [Char.ofNat 18] := by
  native_decide
example : (run (seg 5 5 0) { num := 0, mul := 0, out := [] }).num = 0 := by
  native_decide

end HufCorrect
