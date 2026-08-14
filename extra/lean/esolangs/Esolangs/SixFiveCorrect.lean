import Mathlib

/-! Correctness of the 6-5 text generator

6-5's cell starts at 0 (the data pointer never leaves cell 0): ``6`` adds 6,
``5`` adds 5, ``2`` subtracts 5, ``9`` subtracts 6, and ``A`` prints the
cell as a character.  The generator ``src/esolangs/tools/generators/tape.py::six_five``
emits, for each character, the ``_six_five_path`` that moves the cell from
the previous character's code to the new one — ``6``-runs with ``62`` pairs
(``+6`` then ``-5``, net ``+1``) going up, ``9``-runs with ``95`` pairs
(``-6`` then ``+5``, net ``-1``) going down — then ``A`` to print it.  This
file proves the program is *correct*: for every byte-range text it prints
exactly that text, through the interpreter's own transitions.

The cell is an integer (the reference allows negative cells mid-path).
-/

namespace SixFiveCorrect

set_option linter.unusedVariables false

/-! ### 1. The emitted instruction sequence -/

/-- ``c1 c2`` repeated ``r`` times. -/
def pairRep (c1 c2 : Char) : ℕ → List Char
  | 0 => []
  | r + 1 => c1 :: c2 :: pairRep c1 c2 r

/-- The ``_six_five_path`` from ``src`` to ``dst``: ``6``s with ``62`` pairs
going up, ``9``s with ``95`` pairs going down. -/
def path (src dst : ℤ) : List Char :=
  if h : 0 ≤ dst - src then
    let d := (dst - src).toNat
    List.replicate (d / 6) '6' ++ pairRep '6' '2' (d % 6)
  else
    let d := (-(dst - src)).toNat
    List.replicate (d / 6) '9' ++ pairRep '9' '5' (d % 6)

/-! ### 2. A pure interpreter with the interpreter's transitions -/

/-- The interpreter's transitions: ``6``/``5`` add, ``2``/``9`` subtract, and
``A`` prints the cell as a character. -/
def run : List Char → ℤ → String → ℤ × String
  | '6' :: rest, cell, s => run rest (cell + 6) s
  | '5' :: rest, cell, s => run rest (cell + 5) s
  | '2' :: rest, cell, s => run rest (cell - 5) s
  | '9' :: rest, cell, s => run rest (cell - 6) s
  | 'A' :: rest, cell, s => run rest cell (s ++ toString (Char.ofNat cell.toNat))
  | _ :: rest, cell, s => run rest cell s
  | [], cell, s => (cell, s)

/-- The output of a 6-5 program run from the reset state. -/
def exec (prog : List Char) : String :=
  (run prog 0 "").2

/-! ### 3. One character -/

/-- One character's program: the path to its code, then ``A``. -/
def charProg (n prev : ℤ) : List Char := path prev n ++ ['A']

def textProgAux : List Char → ℤ → List Char
  | [], prev => []
  | c :: cs, prev => charProg (c.toNat : ℤ) prev ++ textProgAux cs (c.toNat : ℤ)

def textProg (t : List Char) : List Char := textProgAux t 0

/-! ### 4. The path runs -/

/-- A run of ``6``s adds ``6 * q``. -/
lemma run_replicate6_append (q : ℕ) (cell : ℤ) (s : String) (rest : List Char) :
    run (List.replicate q '6' ++ rest) cell s = run rest (cell + (6 * q : ℤ)) s := by
  induction q generalizing cell with
  | zero => simp [List.replicate]
  | succ q ih =>
      simp [List.replicate_succ]
      rw [run.eq_1]
      rw [ih (cell + 6)]
      congr 1
      omega

/-- A run of ``62`` pairs adds ``r``. -/
lemma run_pairRep62_append (r : ℕ) (cell : ℤ) (s : String) (rest : List Char) :
    run (pairRep '6' '2' r ++ rest) cell s = run rest (cell + (r : ℤ)) s := by
  induction r generalizing cell with
  | zero => simp [pairRep]
  | succ r ih =>
      simp [pairRep]
      rw [run.eq_1]
      rw [run.eq_3]
      rw [ih (cell + 6 - 5)]
      congr 1
      omega

/-- A run of ``9``s subtracts ``6 * q``. -/
lemma run_replicate9_append (q : ℕ) (cell : ℤ) (s : String) (rest : List Char) :
    run (List.replicate q '9' ++ rest) cell s = run rest (cell - (6 * q : ℤ)) s := by
  induction q generalizing cell with
  | zero => simp [List.replicate]
  | succ q ih =>
      simp [List.replicate_succ]
      rw [run.eq_4]
      rw [ih (cell - 6)]
      congr 1
      omega

/-- A run of ``95`` pairs subtracts ``r``. -/
lemma run_pairRep95_append (r : ℕ) (cell : ℤ) (s : String) (rest : List Char) :
    run (pairRep '9' '5' r ++ rest) cell s = run rest (cell - (r : ℤ)) s := by
  induction r generalizing cell with
  | zero => simp [pairRep]
  | succ r ih =>
      simp [pairRep]
      rw [run.eq_4]
      rw [run.eq_2]
      rw [ih (cell - 6 + 5)]
      congr 1
      omega

/-- The path moves the cell from ``src`` to ``dst``, then continues. -/
lemma run_path_append (src dst : ℤ) (s : String) (rest : List Char) :
    run (path src dst ++ rest) src s = run rest dst s := by
  unfold path
  by_cases h : 0 ≤ dst - src
  · have hd : ((dst - src).toNat : ℤ) = dst - src := Int.toNat_of_nonneg h
    rw [dif_pos h]
    rw [List.append_assoc]
    simp [run_replicate6_append, run_pairRep62_append]
    congr 1
    rw [show (max (dst - src) 0 : ℤ) = dst - src by simpa using hd]
    have hround : 6 * ((dst - src) / 6) + (dst - src) % 6 = dst - src := by
      rw [← add_comm, ← mul_comm]
      exact Int.emod_add_ediv_mul (dst - src) 6
    rw [add_assoc]
    rw [hround]
    omega
  · have hneg : 0 ≤ -(dst - src) := by omega
    have hd : ((-(dst - src)).toNat : ℤ) = -(dst - src) := Int.toNat_of_nonneg hneg
    rw [dif_neg h]
    rw [List.append_assoc]
    simp [run_replicate9_append, run_pairRep95_append]
    congr 1
    rw [show (max (src - dst) 0 : ℤ) = -(dst - src) by
      have hd' : (max (src - dst) 0 : ℤ) = src - dst := by simpa using hd
      omega]
    have hround : 6 * (-(dst - src) / 6) + (-(dst - src)) % 6 = -(dst - src) := by
      rw [← add_comm, ← mul_comm]
      exact Int.emod_add_ediv_mul (-(dst - src)) 6
    simp [hround]
    omega

/-- One character's program moves the cell to ``n`` and prints it before
continuing. -/
lemma run_charProg_rest (n prev : ℤ) (s : String) (rest : List Char) :
    run (charProg n prev ++ rest) prev s = run rest n (s ++ toString (Char.ofNat n.toNat)) := by
  unfold charProg
  rw [show path prev n ++ ['A'] ++ rest = path prev n ++ (['A'] ++ rest) by simp]
  rw [run_path_append prev n s (['A'] ++ rest)]
  change run rest n (s ++ toString (Char.ofNat n.toNat)) = run rest n (s ++ toString (Char.ofNat n.toNat))
  rfl

/-! ### 5. The whole text -/

lemma String.ofList_cons (c : Char) (cs : List Char) :
    String.ofList (c :: cs) = toString c ++ String.ofList cs := by
  rw [← String.toList_inj]
  have hc : (toString c).toList = [c] := by
    rw [show toString c = String.singleton c by rfl]
    simp
  simp [hc, String.toList_ofList, String.toList_append]

lemma run_textProgAux (t : List Char) (ht : ∀ c ∈ t, c.toNat < 256)
    (prev : ℤ) (s : String) :
    ∃ cell', run (textProgAux t prev) prev s = (cell', s ++ String.ofList t) := by
  induction t generalizing prev s with
  | nil =>
      refine ⟨prev, ?_⟩
      simp [textProgAux]
      exact run.eq_7 prev s
  | cons c cs ih =>
      rw [textProgAux]
      rw [run_charProg_rest (c.toNat : ℤ) prev s (textProgAux cs (c.toNat : ℤ))]
      have hto : (c.toNat : ℤ).toNat = c.toNat := rfl
      rw [hto]
      rw [Char.ofNat_toNat]
      rcases ih (fun c' hc' => ht c' (by simp [hc'])) (c.toNat : ℤ) (s ++ toString c) with ⟨cell', h⟩
      refine ⟨cell', ?_⟩
      rw [h]
      rw [String.ofList_cons]
      rw [String.append_assoc]

/-- **Correctness.**  For every byte-range text the generated 6-5 program
prints exactly that text. -/
theorem exec_correct (t : List Char) (ht : ∀ c ∈ t, c.toNat < 256) :
    exec (textProg t) = String.ofList t := by
  unfold exec textProg
  rcases run_textProgAux t ht 0 "" with ⟨cell', h⟩
  rw [h]
  simp

example : exec (textProg "Hi".toList) = "Hi" := by native_decide
example : exec (textProg "Hello, World!".toList) = "Hello, World!" := by native_decide
example : exec (textProg "\x00\x80\xff".toList) = "\x00\x80\xff" := by native_decide

end SixFiveCorrect
