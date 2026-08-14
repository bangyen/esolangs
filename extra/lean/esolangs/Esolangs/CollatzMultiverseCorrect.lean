import Mathlib

/-! Correctness of the Collatz Multiverse text generator

Collatz Multiverse is an OISC whose every line is
``[var1] = [var2] x + [var3], [DO|NOT] PRINT.``: ``var1`` is read, the
Collatz rule applies (an odd or zero value becomes ``var1 * var2 + var3``,
an even value is halved), and ``DO`` prints the low byte of the result.  The
interpreter is ``src/esolangs/interpreters/register_based/collatz_multiverse.py``.
The generator (``tools/generators/register.py::collatz_multiverse``) first
bootstraps a constant table ``k1..kmaxval`` out of ``negativeOne`` using the
copy trick and parity-aware ``k1 x + k1`` / ``k1 x + k2`` increments
(``tools/generators/helpers.py::_cm_constants``), then emits one line per
character: ``o{i} = negativeOne x + k{byte}, DO PRINT.``.  This file models
exactly those line shapes (the generated programs never use arrays or jumps),
proves the table satisfies ``k n = n``, and that the output lines print the
bytes, so the generated program prints exactly the target text through the
interpreter's own Collatz transitions.
-/

namespace CollatzMultiverseCorrect

/-- Machine state: the constant registers ``k n``, the output registers
``o i``, and the printed output.  The interpreter's ``negativeOne`` and
``zero`` registers are read-only constants (-1 and 0), folded into the line
operations below. -/
@[ext]
structure State where
  k : ℕ → ℤ
  o : ℕ → ℤ
  out : List Char

/-- The initial state: every register is 0. -/
def init : State := { k := fun _ => 0, o := fun _ => 0, out := [] }

/-! ### 1. The Collatz rule -/

/-- One Collatz transition: odd (or zero) values become ``t * a + b``, even
values are halved (matching ``t // 2`` for the values that occur). -/
def collatz (t a b : ℤ) : ℤ :=
  if t = 0 ∨ t % 2 ≠ 0 then t * a + b else t / 2

lemma collatz_zero (a b : ℤ) : collatz 0 a b = b := by
  unfold collatz
  simp

lemma collatz_odd (t a b : ℤ) (h : Odd t) : collatz t a b = t * a + b := by
  unfold collatz
  have hmod : t % 2 ≠ 0 := by
    rw [Int.odd_iff] at h
    omega
  simp [hmod]

lemma collatz_neg_neg_zero : collatz (-1 : ℤ) (-1) 0 = 1 := by
  rw [collatz_odd (-1 : ℤ) (-1) 0 (by norm_num)]
  ring

lemma collatz_neg_neg_one : collatz (-1 : ℤ) (-1) 1 = 2 := by
  rw [collatz_odd (-1 : ℤ) (-1) 1 (by norm_num)]
  ring

/-! ### 2. Register updates -/

def updateK (n : ℕ) (v : ℤ) (s : State) : State :=
  { s with k := fun m => if m = n then v else s.k m }

def updateO (i : ℕ) (v : ℤ) (s : State) : State :=
  { s with o := fun m => if m = i then v else s.o m }

@[simp] lemma updateK_same (n : ℕ) (v : ℤ) (s : State) : (updateK n v s).k n = v := by
  simp [updateK]

@[simp] lemma updateK_noteq (n m : ℕ) (v : ℤ) (s : State) (h : m ≠ n) :
    (updateK n v s).k m = s.k m := by
  simp [updateK, h]

@[simp] lemma updateO_same (i : ℕ) (v : ℤ) (s : State) : (updateO i v s).o i = v := by
  simp [updateO]

@[simp] lemma updateO_noteq (i j : ℕ) (v : ℤ) (s : State) (h : j ≠ i) :
    (updateO i v s).o j = s.o j := by
  simp [updateO, h]

/-! ### 3. The generated line shapes -/

/-- ``k{n} = negativeOne x + negativeOne, NOT PRINT.`` -/
def kNegNeg (n : ℕ) (s : State) : State :=
  updateK n (collatz (s.k n) (-1) (-1)) s

/-- ``k{n} = negativeOne x + zero, NOT PRINT.`` -/
def kNegZero (n : ℕ) (s : State) : State :=
  updateK n (collatz (s.k n) (-1) 0) s

/-- ``k{n} = negativeOne x + k{v}, NOT PRINT.`` -/
def kNegV (n v : ℕ) (s : State) : State :=
  updateK n (collatz (s.k n) (-1) (s.k v)) s

/-- ``k{n} = k1 x + k{b}, NOT PRINT.`` -/
def kOneB (n b : ℕ) (s : State) : State :=
  updateK n (collatz (s.k n) 1 (s.k b)) s

/-- ``o{i} = negativeOne x + k{m}, DO PRINT.`` -/
def oNegK (i m : ℕ) (s : State) : State :=
  let t' := collatz (s.o i) (-1) (s.k m)
  { updateO i t' s with out := s.out ++ [Char.ofNat (Int.toNat (t' % 256))] }

/-- The low byte of ``(m : ℤ)`` for ``m < 256`` is just ``m``. -/
lemma byte_nat (m : ℕ) (hm : m < 256) :
    Char.ofNat (Int.toNat (((m : ℤ) % 256))) = Char.ofNat m := by
  congr
  rw [Int.emod_eq_of_lt (by exact_mod_cast Nat.zero_le m) (by exact_mod_cast hm)]
  exact Int.toNat_natCast m

/-- One output line: from ``o i = 0`` and ``k m = m`` it stores ``m`` into
``o i`` and prints the byte ``m``. -/
lemma oNegK_step (i m : ℕ) (s : State) (hk : s.k m = (m : ℤ)) (ho : s.o i = 0)
    (hlt : m < 256) :
    oNegK i m s = { s with
      o := fun j => if j = i then (m : ℤ) else s.o j,
      out := s.out ++ [Char.ofNat m] } := by
  unfold oNegK
  have ht : collatz (s.o i) (-1) (s.k m) = (m : ℤ) := by
    rw [ho, hk]
    exact collatz_zero (-1) (m : ℤ)
  rw [ht]
  change { updateO i (m : ℤ) s with
      out := s.out ++ [Char.ofNat (Int.toNat (((m : ℤ) % 256)))] } =
    { s with o := fun j => if j = i then (m : ℤ) else s.o j, out := s.out ++ [Char.ofNat m] }
  rw [byte_nat m hlt]
  ext <;> simp [updateO]

/-! ### 4. The constant table -/

/-- The predecessor of ``n`` used by the table: ``n - 1`` when ``n`` is even,
``n - 2`` when odd. -/
def cmV (n : ℕ) : ℕ := if n % 2 = 0 then n - 1 else n - 2

/-- The addend of the table: ``k1`` (=1) when ``n`` is even, ``k2`` (=2) when
odd. -/
def cmB (n : ℕ) : ℕ := if n % 2 = 0 then 1 else 2

lemma cmV_mod_two (n : ℕ) : cmV (n + 3) % 2 = 1 := by
  unfold cmV
  rcases Nat.mod_two_eq_zero_or_one (n + 3) with h | h
  · rw [if_pos h]
    rw [← Nat.odd_iff]
    have hE : Even (n + 3) := by
      rw [Nat.even_iff]
      exact h
    clear h
    rcases hE with ⟨k, hk⟩
    have hk1 : 1 ≤ k := by omega
    use k - 1
    omega
  · have hn : ¬(n + 3) % 2 = 0 := by omega
    rw [if_neg hn]
    clear hn
    rw [← Nat.odd_iff]
    have hO : Odd (n + 3) := by
      rw [Nat.odd_iff]
      exact h
    clear h
    rcases hO with ⟨k, hk⟩
    have hk1 : 1 ≤ k := by omega
    use k - 1
    omega

lemma cmV_add_cmB (n : ℕ) : cmV (n + 3) + cmB (n + 3) = n + 3 := by
  unfold cmV cmB
  rcases Nat.mod_two_eq_zero_or_one (n + 3) with h | h
  · rw [if_pos h, if_pos h]
    clear h
    rw [Nat.sub_add_cancel (by omega : 1 ≤ n + 3)]
  · have hn : ¬(n + 3) % 2 = 0 := by omega
    rw [if_neg hn, if_neg hn]
    clear hn h
    rw [Nat.sub_add_cancel (by omega : 2 ≤ n + 3)]

lemma cmV_lt (n : ℕ) : cmV (n + 3) < n + 3 := by
  unfold cmV
  rcases Nat.mod_two_eq_zero_or_one (n + 3) with h | h
  · rw [if_pos h]
    clear h
    omega
  · have hn : ¬(n + 3) % 2 = 0 := by omega
    rw [if_neg hn]
    clear hn h
    omega

lemma cmB_le (n : ℕ) : cmB (n + 3) ≤ n + 2 := by
  unfold cmB
  rcases Nat.mod_two_eq_zero_or_one (n + 3) with h | h <;> simp [h]

lemma cmV_odd_int (n : ℕ) : Odd ((cmV (n + 3) : ℕ) : ℤ) := by
  rw [Int.odd_iff]
  exact_mod_cast cmV_mod_two n

/-! ### 5. The constant table program -/

/-- The ``_cm_constants`` bootstrap: ``k1``, ``k2``, then ``k3..kmaxval``,
each reached by a copy line and an increment line. -/
def constProg : ℕ → List (State → State)
  | 0 => []
  | 1 => [kNegNeg 1, kNegZero 1]
  | 2 => [kNegNeg 1, kNegZero 1, kNegNeg 2, kNegV 2 1]
  | n + 3 => constProg (n + 2) ++ [kNegV (n + 3) (cmV (n + 3)), kOneB (n + 3) (cmB (n + 3))]

/-- Run a list of line operations from a state. -/
def run (prog : List (State → State)) (s : State) : State :=
  prog.foldl (fun s f => f s) s

lemma run_nil (s : State) : run [] s = s := by
  simp [run]

lemma run_cons (f : State → State) (p : List (State → State)) (s : State) :
    run (f :: p) s = run p (f s) := by
  simp [run]

lemma run_append (p q : List (State → State)) (s : State) :
    run (p ++ q) s = run q (run p s) := by
  induction p generalizing s with
  | nil => simp [run]
  | cons f p ih =>
      rw [List.cons_append]
      rw [run_cons]
      rw [ih]
      rw [run_cons]

/-- The ``k1`` bootstrap. -/
lemma constProg1_correct : run [kNegNeg 1, kNegZero 1] init =
    { k := fun n => if n = 1 then (1 : ℤ) else 0, o := fun _ => 0, out := [] } := by
  ext n
  · by_cases h : n = 1 <;> simp [run, kNegNeg, kNegZero, init, collatz_zero,
      collatz_neg_neg_zero, updateK, h]
  · simp [run, kNegNeg, kNegZero, init, collatz_zero, collatz_neg_neg_zero, updateK]
  · simp [run, kNegNeg, kNegZero, init, collatz_zero, collatz_neg_neg_zero, updateK]

/-- The ``k1``/``k2`` bootstrap. -/
lemma constProg2_correct : run [kNegNeg 1, kNegZero 1, kNegNeg 2, kNegV 2 1] init =
    { k := fun n => if n = 1 then (1 : ℤ) else if n = 2 then (2 : ℤ) else 0,
      o := fun _ => 0, out := [] } := by
  ext n
  · by_cases h1 : n = 1 <;> by_cases h2 : n = 2 <;> simp [run, kNegNeg, kNegZero,
      kNegV, init, collatz_zero, collatz_neg_neg_zero, collatz_neg_neg_one, updateK, h1, h2]
  · simp [run, kNegNeg, kNegZero, kNegV, init, collatz_zero,
      collatz_neg_neg_zero, collatz_neg_neg_one, updateK]
  · simp [run, kNegNeg, kNegZero, kNegV, init, collatz_zero,
      collatz_neg_neg_zero, collatz_neg_neg_one, updateK]

/-- The invariant of the constant table: after the bootstrap ``k n = n`` for
``n ≤ maxval``, untouched registers are 0, and nothing has printed. -/
def constInv (s : State) (maxval : ℕ) : Prop :=
  (∀ n, n ≤ maxval → s.k n = (n : ℤ)) ∧
  (∀ n, maxval < n → s.k n = 0) ∧
  (∀ i, s.o i = 0) ∧
  s.out = []

lemma constInv_zero : constInv init 0 := by
  constructor
  · intro n hn
    have : n = 0 := by omega
    subst n
    simp [init]
  · constructor
    · intro n hn
      simp [init]
    · constructor
      · intro i
        simp [init]
      · simp [init]

lemma constInv_base1 : constInv (run (constProg 1) init) 1 := by
  simp [constProg]
  rw [constProg1_correct]
  constructor
  · intro n hn
    by_cases h : n = 1
    · simp [h]
    · have hn0 : n = 0 := by omega
      simp [hn0]
  · constructor
    · intro n hn
      by_cases h : n = 1
      · simp [h]
        omega
      · simp [h]
    · constructor
      · intro i
        simp
      · simp

lemma constInv_base2 : constInv (run (constProg 2) init) 2 := by
  simp [constProg]
  rw [constProg2_correct]
  constructor
  · intro n hn
    by_cases h1 : n = 1
    · simp [h1]
    · by_cases h2 : n = 2
      · simp [h2]
      · have hn0 : n = 0 := by omega
        simp [hn0]
  · constructor
    · intro n hn
      by_cases h1 : n = 1
      · simp [h1]
        omega
      · by_cases h2 : n = 2
        · simp [h2]
          omega
        · simp [h1, h2]
    · constructor
      · intro i
        simp
      · simp

/-- The ``kNegV`` line: a fresh ``k n`` copies the already built ``k v``. -/
lemma kNegV_line (n v : ℕ) (s : State) (hk : s.k v = (v : ℤ)) (hn : s.k n = 0) :
    (kNegV n v s).k n = (v : ℤ) := by
  simp [kNegV, collatz_zero, hk, hn]

/-- The ``kOneB`` line: an odd ``k n`` at ``cmV n`` is raised to ``n``. -/
lemma kOneB_line (n b : ℕ) (s : State) (hkn : s.k n = (cmV n : ℤ)) (hkb : s.k b = (b : ℤ))
    (hodd : Odd ((cmV n : ℕ) : ℤ)) (hadd : cmV n + b = n) :
    (kOneB n b s).k n = (n : ℤ) := by
  simp [kOneB, collatz_odd, hkn, hkb, hodd]
  exact_mod_cast hadd

/-- The copy-and-increment step builds ``k (m + 3)`` from the already built
smaller constants. -/
lemma constInv_step (m : ℕ) (s : State) (h : constInv s (m + 2)) :
    constInv (kOneB (m + 3) (cmB (m + 3)) (kNegV (m + 3) (cmV (m + 3)) s)) (m + 3) := by
  have hk1 : (kNegV (m + 3) (cmV (m + 3)) s).k (m + 3) = (cmV (m + 3) : ℤ) := by
    apply kNegV_line
    · have hle : cmV (m + 3) ≤ m + 2 := by
        have := cmV_lt m
        omega
      exact h.1 (cmV (m + 3)) hle
    · exact h.2.1 (m + 3) (by omega)
  have hk2 : (kOneB (m + 3) (cmB (m + 3)) (kNegV (m + 3) (cmV (m + 3)) s)).k (m + 3)
      = (m + 3 : ℤ) := by
    have hkb : (kNegV (m + 3) (cmV (m + 3)) s).k (cmB (m + 3)) = (cmB (m + 3) : ℤ) := by
      have hnoteq : cmB (m + 3) ≠ m + 3 := by
        unfold cmB
        rcases Nat.mod_two_eq_zero_or_one (m + 3) with hh | hh <;> simp [hh]
      simp [kNegV, hnoteq]
      exact h.1 (cmB (m + 3)) (cmB_le m)
    apply kOneB_line
    · exact hk1
    · exact hkb
    · exact cmV_odd_int m
    · exact cmV_add_cmB m
  constructor
  · intro p hp
    by_cases hpm : p = m + 3
    · subst p
      exact hk2
    · have hle : p ≤ m + 2 := by omega
      have h1 : (kNegV (m + 3) (cmV (m + 3)) s).k p = s.k p := by
        simp [kNegV, hpm]
      have h2 : (kOneB (m + 3) (cmB (m + 3)) (kNegV (m + 3) (cmV (m + 3)) s)).k p =
          (kNegV (m + 3) (cmV (m + 3)) s).k p := by
        simp [kOneB, hpm]
      rw [h2, h1]
      exact h.1 p hle
  · constructor
    · intro p hp
      have hpm : p ≠ m + 3 := by omega
      have h1 : (kNegV (m + 3) (cmV (m + 3)) s).k p = s.k p := by
        simp [kNegV, hpm]
      have h2 : (kOneB (m + 3) (cmB (m + 3)) (kNegV (m + 3) (cmV (m + 3)) s)).k p =
          (kNegV (m + 3) (cmV (m + 3)) s).k p := by
        simp [kOneB, hpm]
      rw [h2, h1]
      exact h.2.1 p (by omega)
    · constructor
      · intro i
        simp [kNegV, kOneB]
        exact h.2.2.1 i
      · simp [kNegV, kOneB]
        exact h.2.2.2

/-- The constant table satisfies its invariant for every ``maxval``. -/
lemma constProg_inv : ∀ maxval : ℕ, constInv (run (constProg maxval) init) maxval := by
  intro maxval
  induction maxval with
  | zero => exact constInv_zero
  | succ n ih =>
      cases n with
      | zero => exact constInv_base1
      | succ n' =>
          cases n' with
          | zero => exact constInv_base2
          | succ n'' =>
              change constInv
                (run (constProg (n'' + 2) ++ [kNegV (n'' + 3) (cmV (n'' + 3)),
                  kOneB (n'' + 3) (cmB (n'' + 3))]) init) (n'' + 3)
              rw [run_append]
              exact constInv_step n'' (run (constProg (n'' + 2)) init) ih

/-! ### 6. The output lines -/

/-- The output lines ``o{i} = negativeOne x + k{b}, DO PRINT.`` for the bytes
``bs``, starting register ``i``. -/
def outProgFrom (i : ℕ) : List ℕ → List (State → State)
  | [] => []
  | b :: bs => oNegK i b :: outProgFrom (i + 1) bs

/-- The output lines, starting at ``o0``. -/
def outProg (bs : List ℕ) : List (State → State) := outProgFrom 0 bs

/-- Each output line prints exactly its byte, leaves ``k`` alone, and stores
the byte in its register. -/
lemma outProgFrom_correct :
    ∀ (i : ℕ) (bs : List ℕ) (s : State),
      (∀ m ∈ bs, s.k m = (m : ℤ)) → (∀ j, i ≤ j → s.o j = 0) → (∀ m ∈ bs, m < 256) →
      (run (outProgFrom i bs) s).k = s.k ∧
      (run (outProgFrom i bs) s).out = s.out ++ bs.map (fun b => Char.ofNat b) := by
  intro i bs
  induction bs generalizing i with
  | nil =>
      intro s hk ho hlt
      simp [outProgFrom, run]
  | cons b bs ih =>
      intro s hk ho hlt
      rw [outProgFrom]
      rw [run_cons]
      have hs1 : oNegK i b s = { s with
          o := fun j => if j = i then (b : ℤ) else s.o j,
          out := s.out ++ [Char.ofNat b] } := by
        apply oNegK_step
        · exact hk b (by simp)
        · exact ho i (by omega)
        · exact hlt b (by simp)
      have h'k : ∀ m ∈ bs, (oNegK i b s).k m = (m : ℤ) := by
        intro m hm
        rw [hs1]
        exact hk m (by simp [hm])
      have h'o : ∀ j, i + 1 ≤ j → (oNegK i b s).o j = 0 := by
        intro j hj
        rw [hs1]
        have hji : j ≠ i := by omega
        simp [hji]
        exact ho j (by omega)
      have h'lt : ∀ m ∈ bs, m < 256 := by
        intro m hm
        exact hlt m (by simp [hm])
      have ih' := ih (i + 1) (oNegK i b s) h'k h'o h'lt
      rcases ih' with ⟨h''k, h''out⟩
      constructor
      · rw [h''k, hs1]
      · rw [h''out, hs1]
        simp [List.append_assoc]

/-! ### 7. The whole program -/

/-- **Correctness.**  The generator's program — the constant table up to
``maxval`` followed by one print line per byte — prints exactly the target
bytes. -/
theorem cm_correct (bs : List ℕ) (maxval : ℕ)
    (hle : ∀ b ∈ bs, b ≤ maxval) (hlt : ∀ b ∈ bs, b < 256) :
    (run (constProg maxval ++ outProg bs) init).out = bs.map (fun b => Char.ofNat b) := by
  rw [run_append]
  have hinv := constProg_inv maxval
  have hk : ∀ m ∈ bs, (run (constProg maxval) init).k m = (m : ℤ) := by
    intro m hm
    exact hinv.1 m (hle m hm)
  have ho : ∀ j, 0 ≤ j → (run (constProg maxval) init).o j = 0 := by
    intro j hj
    exact hinv.2.2.1 j
  have h := outProgFrom_correct 0 bs (run (constProg maxval) init) hk ho hlt
  unfold outProg
  rw [h.2]
  simp [hinv.2.2.2]

-- Sanity round-trips: the bootstrap reaches every small constant and the
-- output lines print the bytes.
example : (run (constProg 5 ++ outProg [2, 5]) init).out = [Char.ofNat 2, Char.ofNat 5] := by
  native_decide
example : (run (constProg 255 ++ outProg [0, 255, 10]) init).out = [Char.ofNat 0, Char.ofNat 255, Char.ofNat 10] := by
  native_decide
example : (run (constProg 3 ++ outProg [3]) init).out = [Char.ofNat 3] := by
  native_decide

end CollatzMultiverseCorrect
