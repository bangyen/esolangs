import Mathlib

/-! Correctness of the Sophie text generator

Sophie's accumulator starts at 0; ``#<char>`` loads the character's code
into it (``#$<code>`` the numeric form), and ``,`` prints it as a character.
The generator ``src/esolangs/tools/generators/register.py::sophie`` emits,
for each character ``c``, the program ``#<c>,`` (or ``#$<code>,`` for
``\n``/``$``, whose literal forms would be read as Sophie syntax): the load
puts ``c.toNat`` in the accumulator and the ``,`` prints it.  This file
proves the program is *correct*: for every byte-range text it prints exactly
that text, through the interpreter's own transitions.

The digit form ``#$<code>,`` is used only for ``\n`` (10) and ``$`` (36);
``readDigits`` reads the decimal digits and is checked against those two
codes by computation.
-/

namespace SophieCorrect

set_option linter.unusedVariables false

/-! ### 1. The digit form -/

/-- A decimal digit's value. -/
def digitVal (d : Char) : ℕ := d.toNat - 48

/-- A decimal digit character. -/
def isDig (d : Char) : Bool := 48 ≤ d.toNat ∧ d.toNat ≤ 57

/-- Read the leading decimal digits into a number, returning the remaining
characters. -/
def readDigitsAux (acc : ℕ) : List Char → ℕ × List Char
  | d :: rest => if isDig d then readDigitsAux (acc * 10 + digitVal d) rest else (acc, d :: rest)
  | [] => (acc, [])

def readDigits (rest : List Char) : ℕ × List Char := readDigitsAux 0 rest

/-- The remainder of a digit read does not depend on the accumulator. -/
lemma readDigitsAux_tail (acc acc' : ℕ) (rest : List Char) :
    (readDigitsAux acc rest).2 = (readDigitsAux acc' rest).2 := by
  induction rest generalizing acc acc' with
  | nil => simp [readDigitsAux]
  | cons d rest ih =>
      by_cases hd : isDig d
      · simpa [readDigitsAux, hd] using ih (acc * 10 + digitVal d) (acc' * 10 + digitVal d)
      · simp [readDigitsAux, hd]

/-- Reading the leading digits never lengthens the remainder. -/
lemma readDigitsAux_tail_le (acc : ℕ) (rest : List Char) :
    (readDigitsAux acc rest).2.length ≤ rest.length := by
  induction rest with
  | nil => simp [readDigitsAux]
  | cons d rest ih =>
      by_cases hd : isDig d
      · simp [readDigitsAux, hd]
        have htail : (readDigitsAux (acc * 10 + digitVal d) rest).2 = (readDigitsAux acc rest).2 :=
          readDigitsAux_tail _ acc rest
        rw [htail]
        omega
      · simp [readDigitsAux, hd]

/-! ### 2. A pure interpreter with the interpreter's transitions -/

/-- The interpreter's transitions: ``#<c>`` loads ``c.toNat``, ``#$<digits>``
loads the number they spell, and ``,`` prints the accumulator as a character. -/
def run : List Char → ℕ → String → ℕ × String
  | [], acc, s => (acc, s)
  | '#' :: '$' :: rest, acc, s =>
      run (readDigits rest).2 (readDigits rest).1 s
  | '#' :: c :: rest, acc, s => run rest c.toNat s
  | ',' :: rest, acc, s => run rest acc (s ++ toString (Char.ofNat acc))
  | _ :: rest, acc, s => run rest acc s
termination_by prog => prog.length
decreasing_by
  all_goals
    simp_wf
    try
      simp [readDigits]
      exact le_trans (readDigitsAux_tail_le 0 rest) (by omega)

/-- The output of a Sophie program run from the reset state. -/
def exec (prog : List Char) : String :=
  (run prog 0 "").2

/-! ### 3. The emitted instruction sequence -/

/-- One character's program: ``#<c>,``, or ``#$<code>,`` for ``\n`` and ``$``
(whose literal forms would be read as Sophie syntax). -/
def charProg (c : Char) : List Char :=
  if c = '\n' ∨ c = '$' then
    '#' :: '$' :: (toString c.toNat).toList ++ [',']
  else
    '#' :: c :: [',']

def textProg : List Char → List Char
  | [] => []
  | c :: cs => charProg c ++ textProg cs

/-! ### 4. The ``#$`` digit form -/

/-- The generator's digit forms spell ``\n`` (10) and ``$`` (36), so the
``#$`` load reads them back. -/
lemma readDigits_special (c : Char) (hc : c = '\n' ∨ c = '$') (rest : List Char) :
    (readDigitsAux 0 (Nat.toDigits 10 c.toNat ++ ',' :: rest)).1 = c.toNat ∧
    (readDigitsAux 0 (Nat.toDigits 10 c.toNat ++ ',' :: rest)).2 = ',' :: rest := by
  rcases hc with rfl | rfl
  · have hto : '\n'.toNat = 10 := by native_decide
    rw [hto]
    have htd : Nat.toDigits 10 10 = ['1', '0'] := by native_decide
    simp [readDigits, readDigitsAux, isDig, digitVal, htd]
  · have hto : '$'.toNat = 36 := by native_decide
    rw [hto]
    have htd : Nat.toDigits 10 36 = ['3', '6'] := by native_decide
    simp [readDigits, readDigitsAux, isDig, digitVal, htd]

/-- ``#`` at the start of a character program (normal form) loads the code
and the following ``,`` prints it. -/
lemma run_char (c : Char) (hne : c ≠ '$') (acc : ℕ) (s : String) (rest : List Char) :
    run ('#' :: c :: ',' :: rest) acc s = run rest c.toNat (s ++ toString (Char.ofNat c.toNat)) := by
  rw [run.eq_3]
  · rw [run.eq_4]
  · exact hne

/-- ``toString`` of the newline is the newline string. -/
lemma toString_newline : toString '\n' = "\n" := by native_decide

/-- ``toString`` of the dollar is the dollar string. -/
lemma toString_dollar : toString '$' = "$" := by native_decide

/-- One character's program loads its code and prints it, leaving the
previous accumulator irrelevant. -/
lemma run_charProg (c : Char) (acc : ℕ) (s : String) :
    run (charProg c) acc s = (c.toNat, s ++ toString (Char.ofNat c.toNat)) := by
  by_cases hc : c = '\n' ∨ c = '$'
  · rcases hc with rfl | rfl
    · simp [charProg, run.eq_2]
      have hrd := readDigits_special '\n' (Or.inl rfl) []
      have hto : '\n'.toNat = 10 := by native_decide
      rw [hto] at hrd
      unfold readDigits
      rw [hrd.1, hrd.2]
      rw [run.eq_4, run.eq_1]
      rw [← hto, Char.ofNat_toNat]
      rw [toString_newline]
    · simp [charProg, run.eq_2]
      have hrd := readDigits_special '$' (Or.inr rfl) []
      have hto : '$'.toNat = 36 := by native_decide
      rw [hto] at hrd
      unfold readDigits
      rw [hrd.1, hrd.2]
      rw [run.eq_4, run.eq_1]
      rw [← hto, Char.ofNat_toNat]
      rw [toString_dollar]
  · have hne : c ≠ '$' := by
      intro h
      apply hc
      exact Or.inr h
    simp [charProg, hc]
    rw [run.eq_3]
    · rw [run.eq_4, run.eq_1, Char.ofNat_toNat]
    · exact hne

/-! ### 5. The whole text -/

lemma String.ofList_cons (c : Char) (cs : List Char) :
    String.ofList (c :: cs) = toString c ++ String.ofList cs := by
  rw [← String.toList_inj]
  have hc : (toString c).toList = [c] := by
    rw [show toString c = String.singleton c by rfl]
    simp
  simp [hc, String.toList_ofList, String.toList_append]

/-- One character's program, followed by any rest, loads the code and prints
it before continuing. -/
lemma run_charProg_rest (c : Char) (acc : ℕ) (s : String) (rest : List Char) :
    run (charProg c ++ rest) acc s = run rest c.toNat (s ++ toString (Char.ofNat c.toNat)) := by
  by_cases hc : c = '\n' ∨ c = '$'
  · rcases hc with rfl | rfl
    · simp [charProg, run.eq_2]
      have hrd := readDigits_special '\n' (Or.inl rfl) rest
      have hto : '\n'.toNat = 10 := by native_decide
      rw [hto] at hrd
      unfold readDigits
      rw [hrd.1, hrd.2]
      rw [run.eq_4]
      rw [← hto, Char.ofNat_toNat]
      rw [toString_newline]
    · simp [charProg, run.eq_2]
      have hrd := readDigits_special '$' (Or.inr rfl) rest
      have hto : '$'.toNat = 36 := by native_decide
      rw [hto] at hrd
      unfold readDigits
      rw [hrd.1, hrd.2]
      rw [run.eq_4]
      rw [← hto, Char.ofNat_toNat]
      rw [toString_dollar]
  · have hne : c ≠ '$' := by
      intro h
      apply hc
      exact Or.inr h
    simp [charProg, hc]
    rw [run.eq_3]
    · rw [run.eq_4, Char.ofNat_toNat]
    · exact hne

/-- **Correctness.**  For every text the generated Sophie program prints
exactly that text. -/
lemma run_textProg (t : List Char) (acc : ℕ) (s : String) :
    ∃ acc', run (textProg t) acc s = (acc', s ++ String.ofList t) := by
  induction t generalizing acc s with
  | nil =>
      refine ⟨acc, ?_⟩
      simp [textProg, run]
  | cons c cs ih =>
      rw [textProg]
      rw [run_charProg_rest c acc s (textProg cs)]
      rw [show s ++ toString (Char.ofNat c.toNat) = s ++ toString c by rw [Char.ofNat_toNat]]
      rcases ih c.toNat (s ++ toString c) with ⟨acc', h⟩
      refine ⟨acc', ?_⟩
      rw [h]
      rw [String.ofList_cons]
      rw [String.append_assoc]

theorem exec_correct (t : List Char) : exec (textProg t) = String.ofList t := by
  unfold exec
  rcases run_textProg t 0 "" with ⟨acc', h⟩
  rw [h]
  simp

example : exec (textProg "Hi".toList) = "Hi" := by native_decide
example : exec (textProg "a\nb$c".toList) = "a\nb$c" := by native_decide
example : exec (textProg "Hello, World!".toList) = "Hello, World!" := by native_decide

end SophieCorrect
