import Mathlib

/-! Correctness of the BIO text generator

BIO's register ``x`` starts at 0; ``0ox`` moves it up by one, ``1ox`` moves
it down by one, and ``1ix`` prints it as a character (mod 256).  The
generator ``src/esolangs/tools/generators/register.py::bio`` emits, for each
character, the ``0ox``/``1ox`` run that moves ``x`` from the previous
character's code to the new one, then ``1ix`` to print it.  This file proves
the program is *correct*: for every byte-range text it prints exactly that
text, through the interpreter's own transitions.
-/

namespace BioCorrect

set_option linter.unusedVariables false

/-! ### 1. The instruction tokens -/

/-- ``a b c`` repeated ``r`` times. -/
def repTok (a b c : Char) : ℕ → List Char
  | 0 => []
  | r + 1 => a :: b :: c :: repTok a b c r

/-! ### 2. A pure interpreter with the interpreter's transitions -/

/-- The interpreter's transitions: ``0ox`` moves ``x`` up, ``1ox`` moves it
down (as a natural number), ``1ix`` prints ``x % 256`` as a character. -/
def run : List Char → ℕ → String → ℕ × String
  | '0' :: 'o' :: 'x' :: rest, x, s => run rest (x + 1) s
  | '1' :: 'o' :: 'x' :: rest, x, s => run rest (x - 1) s
  | '1' :: 'i' :: 'x' :: rest, x, s => run rest x (s ++ toString (Char.ofNat (x % 256)))
  | _ :: rest, x, s => run rest x s
  | [], x, s => (x, s)

/-- The output of a BIO program run from the reset state. -/
def exec (prog : List Char) : String :=
  (run prog 0 "").2

/-! ### 3. The emitted instruction sequence -/

/-- One character's program: the ``0ox``/``1ox`` run to its code, then
``1ix``. -/
def charProg (n prev : ℕ) : List Char :=
  if prev ≤ n then
    repTok '0' 'o' 'x' (n - prev) ++ ['1', 'i', 'x']
  else
    repTok '1' 'o' 'x' (prev - n) ++ ['1', 'i', 'x']

def textProgAux : List Char → ℕ → List Char
  | [], prev => []
  | c :: cs, prev => charProg c.toNat prev ++ textProgAux cs c.toNat

def textProg (t : List Char) : List Char := textProgAux t 0

/-! ### 4. The runs -/

/-- A run of ``0ox`` followed by any rest adds ``r`` to ``x``. -/
lemma run_rep0_append (r x : ℕ) (s : String) (rest : List Char) :
    run (repTok '0' 'o' 'x' r ++ rest) x s = run rest (x + r) s := by
  induction r generalizing x with
  | zero => simp [repTok]
  | succ r ih =>
      simp [repTok]
      rw [run.eq_1]
      rw [ih (x + 1)]
      congr 1
      omega

/-- A run of ``1ox`` followed by any rest subtracts ``r`` from ``x`` (within
``r ≤ x``). -/
lemma run_rep1_append (r x : ℕ) (hr : r ≤ x) (s : String) (rest : List Char) :
    run (repTok '1' 'o' 'x' r ++ rest) x s = run rest (x - r) s := by
  induction r generalizing x with
  | zero => simp [repTok]
  | succ r ih =>
      have hr' : r ≤ x - 1 := by omega
      simp [repTok]
      rw [run.eq_2]
      rw [ih (x - 1) hr']
      congr 1
      omega

/-- ``1ix`` followed by any rest prints ``x % 256``. -/
lemma run_1ix_rest (x : ℕ) (s : String) (rest : List Char) :
    run ('1' :: 'i' :: 'x' :: rest) x s = run rest x (s ++ toString (Char.ofNat (x % 256))) := by
  rw [run.eq_3]

/-! ### 5. One character -/

/-- One character's program moves ``x`` from ``prev`` to ``n`` and prints
``n % 256`` before continuing. -/
lemma run_charProg_rest (n prev : ℕ) (s : String) (rest : List Char) :
    run (charProg n prev ++ rest) prev s = run rest n (s ++ toString (Char.ofNat (n % 256))) := by
  by_cases hp : prev ≤ n
  · simp [charProg, hp]
    rw [run_rep0_append (n - prev) prev s ('1' :: 'i' :: 'x' :: rest)]
    rw [run_1ix_rest]
    rw [show prev + (n - prev) = n by omega]
  · have hd : prev - n ≤ prev := by omega
    simp [charProg, hp]
    rw [run_rep1_append (prev - n) prev hd s ('1' :: 'i' :: 'x' :: rest)]
    rw [run_1ix_rest]
    rw [show prev - (prev - n) = n by omega]

/-! ### 6. The whole text -/

lemma String.ofList_cons (c : Char) (cs : List Char) :
    String.ofList (c :: cs) = toString c ++ String.ofList cs := by
  rw [← String.toList_inj]
  have hc : (toString c).toList = [c] := by
    rw [show toString c = String.singleton c by rfl]
    simp
  simp [hc, String.toList_ofList, String.toList_append]

lemma run_textProgAux (t : List Char) (ht : ∀ c ∈ t, c.toNat < 256)
    (prev : ℕ) (s : String) :
    ∃ x', run (textProgAux t prev) prev s = (x', s ++ String.ofList t) := by
  induction t generalizing prev s with
  | nil =>
      refine ⟨prev, ?_⟩
      simp [textProgAux, run.eq_5]
  | cons c cs ih =>
      rw [textProgAux]
      rw [run_charProg_rest c.toNat prev s (textProgAux cs c.toNat)]
      have hc : c.toNat % 256 = c.toNat := Nat.mod_eq_of_lt (ht c (by simp))
      rw [hc]
      rw [Char.ofNat_toNat]
      rcases ih (fun c' hc' => ht c' (by simp [hc'])) c.toNat (s ++ toString c) with ⟨x', h⟩
      refine ⟨x', ?_⟩
      rw [h]
      rw [String.ofList_cons]
      rw [String.append_assoc]

/-- **Correctness.**  For every byte-range text the generated BIO program
prints exactly that text. -/
theorem exec_correct (t : List Char) (ht : ∀ c ∈ t, c.toNat < 256) :
    exec (textProg t) = String.ofList t := by
  unfold exec textProg
  rcases run_textProgAux t ht 0 "" with ⟨x', h⟩
  rw [h]
  simp

example : exec (textProg "Hi".toList) = "Hi" := by native_decide
example : exec (textProg "Hello, World!".toList) = "Hello, World!" := by native_decide
example : exec (textProg "\x00\x80\xff".toList) = "\x00\x80\xff" := by native_decide

end BioCorrect
