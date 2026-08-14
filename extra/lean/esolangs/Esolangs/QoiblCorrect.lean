import Mathlib

/-! Correctness of the Qoibl text generator

A Qoibl expression ``tt <expr> tt`` parses ``<expr>`` and prints the result
as a character.  The generator ``src/esolangs/tools/generators/register.py::qoibl``
emits, for each character, ``tt`` followed by the character's binary digits
as ``y`` (1) / ``e`` (0), followed by ``tt``: the expression evaluates to the
character's code and ``tt`` prints it.  This file proves the program is
*correct*: for every byte-range text it prints exactly that text, through
the interpreter's own transitions.
-/

namespace QoiblCorrect

set_option linter.unusedVariables false

/-! ### 1. Binary digits -/

/-- A bit character's value: ``y`` is 1, anything else 0. -/
def bitVal (c : Char) : ℕ := if c = 'y' then 1 else 0

/-- The number a bit list spells (most significant first). -/
def binVal (bits : List Char) : ℕ :=
  bits.foldl (fun a b => a * 2 + bitVal b) 0

/-- The number a list of digit values spells (most significant first). -/
def binValNat (L : List ℕ) : ℕ :=
  L.foldl (fun a b => a * 2 + b) 0

/-- The generator's bits for a number: its binary digits as ``y``/``e``. -/
def bitsOf (n : ℕ) : List Char :=
  (Nat.digits 2 n).reverse.map (fun d => if d = 0 then 'e' else 'y')

/-- ``binVal`` and ``binValNat`` agree through the bit characters. -/
lemma binVal_eq_binValNat (bits : List Char) : binVal bits = binValNat (bits.map bitVal) := by
  unfold binVal binValNat
  rw [List.foldl_map]

/-- The ``y``/``e`` digits read back as the original digits. -/
lemma bitsOf_map (n : ℕ) : (bitsOf n).map bitVal = (Nat.digits 2 n).reverse := by
  unfold bitsOf
  rw [List.map_map]
  have hcongr : ∀ d ∈ (Nat.digits 2 n).reverse,
      (bitVal ∘ (fun d => if d = 0 then 'e' else 'y')) d = id d := by
    intro d hd
    by_cases h : d = 0
    · simp [h, bitVal]
    · have h1 : d = 1 := by
        have hmem : d ∈ Nat.digits 2 n := List.mem_reverse.mp hd
        have hlt : d < 2 := Nat.digits_lt_base (by norm_num) hmem
        omega
      subst d
      simp [bitVal]
  simpa using (List.map_congr_left (l := (Nat.digits 2 n).reverse) (g := id) hcongr)

/-- Appending one digit to the end doubles and adds. -/
lemma binValNat_append_one (X : List ℕ) (e : ℕ) : binValNat (X ++ [e]) = binValNat X * 2 + e := by
  unfold binValNat
  rw [List.foldl_append]
  simp

/-- Appending a digit to the front of a reversed list doubles the value. -/
lemma binValNat_reverse_cons (d : ℕ) (L : List ℕ) :
    binValNat (L.reverse ++ [d]) = binValNat L.reverse * 2 + d := by
  exact binValNat_append_one L.reverse d

/-- Reading the most-significant-first digits gives the number. -/
lemma binValNat_reverse_ofDigits (L : List ℕ) : binValNat L.reverse = Nat.ofDigits 2 L := by
  induction L with
  | nil => simp [binValNat, Nat.ofDigits]
  | cons d L ih =>
      rw [show (d :: L).reverse = L.reverse ++ [d] by simp]
      rw [binValNat_append_one L.reverse d]
      rw [ih]
      rw [Nat.ofDigits_cons]
      omega

/-- The generator's bits for ``n`` spell exactly ``n``. -/
lemma bitsOf_correct (n : ℕ) : binVal (bitsOf n) = n := by
  rw [binVal_eq_binValNat]
  rw [bitsOf_map]
  rw [binValNat_reverse_ofDigits (Nat.digits 2 n)]
  exact Nat.ofDigits_digits 2 n

/-! ### 2. The expression bits -/

/-- The bits of a ``tt`` expression: everything up to the closing ``t``. -/
def takeBits : List Char → List Char
  | 't' :: rest => []
  | c :: rest => c :: takeBits rest
  | [] => []

/-- The program after a ``tt`` expression: past its closing ``tt``. -/
def dropBits : List Char → List Char
  | 't' :: 't' :: rest => rest
  | _ :: rest => dropBits rest
  | [] => []

/-- ``dropBits`` drops a prefix, so it is a ``List.drop``. -/
lemma dropBits_eq_drop (rest : List Char) : ∃ n, dropBits rest = rest.drop n := by
  induction rest with
  | nil => refine ⟨0, ?_⟩; simp [dropBits]
  | cons c rest ih =>
      by_cases hc : c = 't'
      · subst c
        cases rest with
        | nil => refine ⟨2, ?_⟩; decide
        | cons d rest' =>
            by_cases hd : d = 't'
            · refine ⟨2, ?_⟩; simp [dropBits, hd]
            · rcases ih with ⟨n, hn⟩
              refine ⟨n + 1, ?_⟩
              rw [show dropBits ('t' :: d :: rest') = dropBits (d :: rest') by simp [dropBits, hd]]
              rw [hn]
              exact (List.drop_succ_cons (a := 't') (i := n)).symm
      · rcases ih with ⟨n, hn⟩
        refine ⟨n + 1, ?_⟩
        rw [show dropBits (c :: rest) = dropBits rest by simp [dropBits, hc]]
        rw [hn]
        exact (List.drop_succ_cons (a := c) (i := n)).symm

/-- Skipping a ``tt`` expression never lengthens the remaining program. -/
lemma dropBits_tail_le (rest : List Char) : (dropBits rest).length ≤ rest.length := by
  rcases dropBits_eq_drop rest with ⟨n, hn⟩
  rw [hn]
  rw [List.length_drop]
  omega

lemma takeBits_bits (bits : List Char) (rest : List Char)
    (hb : ∀ b ∈ bits, b ≠ 't') :
    takeBits (bits ++ 't' :: 't' :: rest) = bits := by
  induction bits with
  | nil => simp [takeBits]
  | cons b bits ih =>
      have hb' : b ≠ 't' := hb b (by simp)
      have hrest : ∀ b' ∈ bits, b' ≠ 't' := by
        intro x hx
        exact hb x (by simp [hx])
      simp [takeBits, hb', ih hrest]

lemma dropBits_bits (bits : List Char) (rest : List Char)
    (hb : ∀ b ∈ bits, b ≠ 't') :
    dropBits (bits ++ 't' :: 't' :: rest) = rest := by
  induction bits with
  | nil => simp [dropBits]
  | cons b bits ih =>
      have hb' : b ≠ 't' := hb b (by simp)
      have hrest : ∀ b' ∈ bits, b' ≠ 't' := by
        intro x hx
        exact hb x (by simp [hx])
      simp [dropBits, hb', ih hrest]

/-! ### 3. A pure interpreter with the interpreter's transitions -/

/-- The interpreter's transition: ``tt <bits> tt`` prints the number the
bits spell as a character; other tokens are skipped. -/
def run : List Char → String → String
  | 't' :: 't' :: rest, s => run (dropBits rest) (s ++ toString (Char.ofNat (binVal (takeBits rest))))
  | _ :: rest, s => run rest s
  | [], s => s
termination_by prog => prog.length
decreasing_by
  all_goals
    simp
    try exact le_trans (dropBits_tail_le rest) (show rest.length ≤ rest.length + 1 by omega)

/-- The output of a Qoibl program run from the reset state. -/
def exec (prog : List Char) : String := run prog ""

/-! ### 4. The emitted instruction sequence -/

/-- One character's program: ``tt <bits> tt``. -/
def charProg (c : Char) : List Char :=
  't' :: 't' :: bitsOf c.toNat ++ ['t', 't']

def textProgAux : List Char → List Char
  | [] => []
  | c :: cs => charProg c ++ '\n' :: textProgAux cs

def textProg (t : List Char) : List Char := textProgAux t

/-- One character's program prints its character before continuing. -/
lemma run_charProg_rest (c : Char) (s : String) (rest : List Char) :
    run (charProg c ++ '\n' :: rest) s = run rest (s ++ toString (Char.ofNat c.toNat)) := by
  unfold charProg
  simp only [List.cons_append]
  rw [run.eq_1]
  rw [show bitsOf c.toNat ++ ['t', 't'] ++ '\n' :: rest = bitsOf c.toNat ++ ('t' :: 't' :: '\n' :: rest) by
    simpa [List.cons_append, List.append_assoc]]
  have hb : ∀ b ∈ bitsOf c.toNat, b ≠ 't' := by
    intro b hb
    unfold bitsOf at hb
    rcases List.mem_map.mp hb with ⟨d, hd, rfl⟩
    by_cases h : d = 0
    · simp [h]
    · simp [h]
  have ht : takeBits (bitsOf c.toNat ++ 't' :: 't' :: '\n' :: rest) = bitsOf c.toNat :=
    takeBits_bits (bitsOf c.toNat) ('\n' :: rest) hb
  have hd : dropBits (bitsOf c.toNat ++ 't' :: 't' :: '\n' :: rest) = '\n' :: rest :=
    dropBits_bits (bitsOf c.toNat) ('\n' :: rest) hb
  simp [ht, hd, bitsOf_correct, run.eq_2]

/-! ### 5. The whole text -/

lemma String.ofList_cons (c : Char) (cs : List Char) :
    String.ofList (c :: cs) = toString c ++ String.ofList cs := by
  rw [← String.toList_inj]
  have hc : (toString c).toList = [c] := by
    rw [show toString c = String.singleton c by rfl]
    simp
  simp [hc, String.toList_ofList, String.toList_append]

lemma run_textProgAux (t : List Char) (s : String) :
    run (textProgAux t) s = s ++ String.ofList t := by
  induction t generalizing s with
  | nil => simp [textProgAux, run.eq_3]
  | cons c cs ih =>
      rw [textProgAux]
      rw [run_charProg_rest c s (textProgAux cs)]
      rw [Char.ofNat_toNat]
      rw [ih (s ++ toString c)]
      rw [String.ofList_cons]
      rw [String.append_assoc]

/-- **Correctness.**  For every text the generated Qoibl program prints
exactly that text. -/
theorem exec_correct (t : List Char) : exec (textProg t) = String.ofList t := by
  unfold exec textProg
  rw [run_textProgAux t ""]
  simp

example : exec (textProg ("Hi".toList)) = "Hi" := by native_decide
example : exec (textProg "\x00\x80\xff".toList) = "\x00\x80\xff" := by native_decide
example : exec (textProg "yey tt".toList) = "yey tt" := by native_decide
example : exec (textProg "".toList) = "" := by native_decide

end QoiblCorrect
