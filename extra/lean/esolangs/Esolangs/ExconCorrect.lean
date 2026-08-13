import Mathlib
import Esolangs.Excon

/-! Correctness of the EXCON text generator

The generator ``src/esolangs/tools/generators/tape.py::excon`` emits, for each
byte ``v``, a program that resets the 8-cell pool with ``:``, walks the
pointer left to every bit of ``v`` that is set (emitting ``<`` runs and ``^``
flips), and prints the pool with ``!``.  This file proves the program is
*correct*: for every byte text it prints exactly that text.

``exec`` below runs the ported interpreter's own pure state transitions
(``Excon.empty_list``, ``Excon.flips``, ``Excon.gets``, ``Excon.to_s``) over
the emitted instruction stream, so the theorem certifies the ported
interpreter itself rather than a reimplementation.  The two structural facts:

  1. **Bit-flip induction.**  The pointer walk visits each set bit exactly
     once, so after the flips ``gets pool k = bit v k`` for every cell ``k``.
     This is proven by induction on the bit index, with ``GoodPool`` tracking
     which high bits are already correct and which low bits are still zero.
  2. **Binary value.**  ``to_s`` reads the pool back as
     ``128*pool[0] + 64*pool[1] + ... + pool[7]``, which equals ``v`` for
     every byte; the byte range is verified by computation.

The main theorem is stated for ``List Char`` texts whose codes are all below
256 (the generator rejects larger codepoints with a documented
``ValueError``).
-/

namespace ExconCorrect

set_option linter.unusedVariables false

open Excon

/-! ### 1. The generator's bit layout -/

/-- The ``j``-th bit of ``v`` (``j = 0`` is the most significant bit),
matching ``format(v, "08b")``. -/
def bit (v j : ℕ) : ℕ := (v / 2 ^ (7 - j)) % 2

lemma bit_lt_two (v j : ℕ) : bit v j < 2 := by
  unfold bit
  exact Nat.mod_lt _ (by norm_num)

lemma bit_eq_zero_of_ne_one {v j : ℕ} (h : bit v j ≠ 1) : bit v j = 0 := by
  have hlt : bit v j < 2 := bit_lt_two v j
  omega

/-! ### 2. A pure interpreter with the ported state transitions -/

abbrev State := List ℕ × ℕ × String

/-- One instruction, exactly the ``Excon.run`` transition on that character. -/
def step (st : State) (c : Char) : State :=
  let (l, n, s) := st
  if c = ':' then (empty_list, 7, s)
  else if c = '^' then (flips l n, n, s)
  else if c = '<' then (l, (n - 1) % 8, s)
  else if c = '!' then (l, n, s ++ to_s l 7 0)
  else st

/-- Run a list of instructions from a state. -/
def runList (prog : List Char) (st : State) : State :=
  prog.foldl step st

/-- The output of an EXCON program run from a reset pool. -/
def exec (prog : List Char) : String :=
  (runList prog (empty_list, 7, "")).2.2

lemma runList_nil (st : State) : runList [] st = st := rfl

lemma runList_cons (c : Char) (rest : List Char) (st : State) :
    runList (c :: rest) st = runList rest (step st c) := rfl

lemma runList_append (l1 l2 : List Char) (st : State) :
    runList (l1 ++ l2) st = runList l2 (runList l1 st) := by
  unfold runList
  rw [List.foldl_append]

/-! ### 3. The pointer walk -/

/-- The cell after ``k`` runs of ``<`` (each ``<`` moves ``(n - 1) % 8``). -/
def cellDown : ℕ → ℕ → ℕ
  | 0, n => n
  | k + 1, n => cellDown k ((n - 1) % 8)

/-- Within ``0..7`` the pointer never wraps, so ``k`` ``<``s move ``n`` to
``n - k``. -/
lemma cellDown_eq_sub (k n : ℕ) (hk : k ≤ n) (hn : n ≤ 7) : cellDown k n = n - k := by
  induction k generalizing n with
  | zero => simp [cellDown]
  | succ k ih =>
      have hnpos : 0 < n := by omega
      have hmod : (n - 1) % 8 = n - 1 := by
        exact Nat.mod_eq_of_lt (by omega)
      have hk1 : k ≤ n - 1 := by omega
      have hn1 : n - 1 ≤ 7 := by omega
      calc
        cellDown (k + 1) n = cellDown k ((n - 1) % 8) := by rfl
        _ = cellDown k (n - 1) := by rw [hmod]
        _ = (n - 1) - k := ih (n - 1) hk1 hn1
        _ = n - (k + 1) := by omega

lemma runList_replicate_lt (k n : ℕ) (l : List ℕ) (out : String) :
    runList (List.replicate k '<') (l, n, out) = (l, cellDown k n, out) := by
  induction k generalizing n with
  | zero => simp [runList, cellDown]
  | succ k ih =>
      rw [List.replicate_succ]
      rw [runList_cons]
      have hstep : step (l, n, out) '<' = (l, (n - 1) % 8, out) := by
        simp [step]
      rw [hstep]
      rw [ih ((n - 1) % 8)]
      rfl

/-! ### 4. The emitted instruction sequence -/

/-- For character code ``v``, the ``<``/``^`` run that sets the bits at
positions ``i..0``, starting with the pointer at ``pos`` (the previous set bit,
or 7 at the start). -/
def charProgAux (v pos : ℕ) : ℕ → List Char
  | 0 => if bit v 0 = 1 then List.replicate pos '<' ++ ['^'] else []
  | j + 1 =>
      if bit v (j + 1) = 1 then
        List.replicate (pos - (j + 1)) '<' ++ ['^'] ++ charProgAux v (j + 1) j
      else
        charProgAux v pos j

lemma charProgAux_zero (v pos : ℕ) :
    charProgAux v pos 0 = if bit v 0 = 1 then List.replicate pos '<' ++ ['^'] else [] := rfl

lemma charProgAux_succ (v pos j : ℕ) :
    charProgAux v pos (j + 1) =
      if bit v (j + 1) = 1 then
        List.replicate (pos - (j + 1)) '<' ++ ['^'] ++ charProgAux v (j + 1) j
      else
        charProgAux v pos j := rfl

/-- One character's whole program: ``:`` reset, the bit walk, ``!`` print. -/
def charProg (v : ℕ) : List Char := ':' :: (charProgAux v 7 7 ++ ['!'])

def charProgC (c : Char) : List Char := charProg c.toNat

def textProg : List Char → List Char
  | [] => []
  | c :: cs => charProgC c ++ textProg cs

/-! ### 5. The pool after the bit walk -/

/-- Invariant while walking down the bits: high bits (index ``> j``) already
hold ``bit v k``, low bits (index ``≤ j``) are still zero. -/
def GoodPool (v j : ℕ) (l : List ℕ) : Prop :=
  (∀ k, k ≤ 7 → k > j → gets l k = bit v k) ∧ (∀ k, k ≤ 7 → k ≤ j → gets l k = 0)

lemma gets_flips_self (l : List ℕ) (n : ℕ) (hn : n < l.length) :
    gets (flips l n) n = (gets l n + 1) % 2 := by
  unfold flips gets
  rw [List.getD_eq_getElem?_getD, List.getD_eq_getElem?_getD]
  rw [List.getElem?_set_self']
  have hge : l[n]? = some (l.getD n 0) := by
    rw [List.getElem?_eq_getElem hn]
    rw [← List.getD_eq_getElem l 0 hn]
  rw [hge]
  simp

lemma gets_flips_ne (l : List ℕ) (n k : ℕ) (hk : k < l.length) (hne : k ≠ n) :
    gets (flips l n) k = gets l k := by
  unfold flips gets
  rw [List.getD_eq_getElem?_getD, List.getD_eq_getElem?_getD]
  rw [List.getElem?_set']
  simp [hne.symm]

/-- Flipping the next set bit keeps the invariant. -/
lemma GoodPool.flips_next {v j : ℕ} (hj : j + 1 ≤ 7) (hb : bit v (j + 1) = 1) {l : List ℕ}
    (hl : l.length = 8) (hg : GoodPool v (j + 1) l) : GoodPool v j (flips l (j + 1)) := by
  constructor
  · intro k hk hgt
    by_cases hkj : k = j + 1
    · subst k
      rw [gets_flips_self l (j + 1) (by omega)]
      rw [hg.2 (j + 1) (by omega) (by omega)]
      omega
    · rw [gets_flips_ne l (j + 1) k (by omega) hkj]
      exact hg.1 k hk (by omega)
  · intro k hk hle
    rw [gets_flips_ne l (j + 1) k (by omega) (by omega)]
    exact hg.2 k hk (by omega)

/-- A skipped (unset) bit leaves the invariant pool untouched. -/
lemma GoodPool.skip_next {v j : ℕ} (hj : j + 1 ≤ 7) (hb : bit v (j + 1) = 0) {l : List ℕ}
    (hg : GoodPool v (j + 1) l) : GoodPool v j l := by
  constructor
  · intro k hk hgt
    by_cases hkj : k = j + 1
    · subst k
      rw [hg.2 (j + 1) (by omega) (by omega)]
      exact hb.symm
    · exact hg.1 k hk (by omega)
  · intro k hk hle
    exact hg.2 k hk (by omega)

/-- The reset pool satisfies the invariant at the top. -/
lemma GoodPool.empty (v : ℕ) : GoodPool v 7 empty_list := by
  constructor
  · intro k hk hgt
    omega
  · intro k hk hle
    unfold gets empty_list
    by_cases hk8 : k < 8
    · exact List.getD_replicate (x := 0) (n := 8) (i := k) (y := 0) hk8
    · exact List.getD_eq_default (l := List.replicate 8 0) (d := 0) (n := k) (by omega)

/-- **Bit-flip induction.**  Walking the set bits of ``v`` from ``i`` down to
0, starting from any pool satisfying ``GoodPool v i`` with the pointer at
``pos`` (``i ≤ pos ≤ 7``), leaves every cell holding ``bit v k``. -/
lemma run_charProgAux (v : ℕ) (out : String) (i : ℕ) :
    ∀ (pos : ℕ) (l : List ℕ), l.length = 8 → i ≤ 7 → i ≤ pos → pos ≤ 7 → GoodPool v i l →
      ∀ k, k ≤ 7 → gets (runList (charProgAux v pos i) (l, pos, out)).1 k = bit v k := by
  induction i with
  | zero =>
      intro pos l hl hi hpi hpos hg k hk
      by_cases hb : bit v 0 = 1
      · have hpool : (runList (charProgAux v pos 0) (l, pos, out)).1 = flips l 0 := by
          rw [charProgAux_zero, if_pos hb]
          rw [runList_append]
          rw [runList_replicate_lt]
          rw [cellDown_eq_sub pos pos (by omega) hpos]
          simp [runList_cons, runList_nil, step]
        rw [hpool]
        by_cases hk0 : k = 0
        · subst k
          rw [gets_flips_self l 0 (by omega)]
          rw [hg.2 0 (by omega) (by omega)]
          omega
        · rw [gets_flips_ne l 0 k (by omega) hk0]
          exact hg.1 k hk (by omega)
      · have hb0 : bit v 0 = 0 := bit_eq_zero_of_ne_one hb
        have hpool : (runList (charProgAux v pos 0) (l, pos, out)).1 = l := by
          rw [charProgAux_zero, if_neg hb]
          simp [runList_nil]
        rw [hpool]
        by_cases hk0 : k = 0
        · subst k
          rw [hg.2 0 (by omega) (by omega)]
          exact hb0.symm
        · exact hg.1 k hk (by omega)
  | succ j ih =>
      intro pos l hl hi hpi hpos hg k hk
      by_cases hb : bit v (j + 1) = 1
      · have hpool : (runList (charProgAux v pos (j + 1)) (l, pos, out)).1 =
            (runList (charProgAux v (j + 1) j) (flips l (j + 1), j + 1, out)).1 := by
          have hmove : cellDown (pos - (j + 1)) pos = j + 1 := by
            rw [cellDown_eq_sub (pos - (j + 1)) pos (by omega) hpos]
            omega
          rw [charProgAux_succ, if_pos hb]
          rw [runList_append]
          rw [runList_append]
          rw [runList_replicate_lt]
          rw [hmove]
          rw [runList_cons, runList_nil]
          simp [step]
        rw [hpool]
        exact ih (j + 1) (flips l (j + 1)) (by simp [flips, hl]) (by omega) (by omega) (by omega)
          (GoodPool.flips_next (by omega) hb hl hg) k hk
      · have hb0 : bit v (j + 1) = 0 := bit_eq_zero_of_ne_one hb
        have hrun : charProgAux v pos (j + 1) = charProgAux v pos j := by
          rw [charProgAux_succ, if_neg hb]
        rw [hrun]
        exact ih pos l hl (by omega) (by omega) hpos (GoodPool.skip_next (by omega) hb0 hg) k hk

/-- The bit walk never changes the output. -/
lemma runList_out_preserve {prog : List Char} (h : ∀ c ∈ prog, c = '<' ∨ c = '^')
    (l : List ℕ) (n : ℕ) (out : String) : (runList prog (l, n, out)).2.2 = out := by
  induction prog generalizing l n with
  | nil => rfl
  | cons c rest ih =>
      rw [runList_cons]
      rcases h c (by simp) with hc | hc
      · subst c
        simp [step]
        exact ih (by intro x hx; exact h x (by simp [hx])) l ((n - 1) % 8)
      · subst c
        simp [step]
        exact ih (by intro x hx; exact h x (by simp [hx])) (flips l n) n

lemma mem_charProgAux (v : ℕ) :
    ∀ (pos i : ℕ), ∀ c : Char, c ∈ charProgAux v pos i → c = '<' ∨ c = '^' := by
  intro pos i
  induction i generalizing pos with
  | zero =>
      intro c h
      by_cases hb : bit v 0 = 1
      · rw [charProgAux_zero, if_pos hb] at h
        rcases List.mem_append.mp h with h | h
        · have : c = '<' := (List.mem_replicate.mp h).2
          simp [this]
        · simp at h
          right
          exact h
      · rw [charProgAux_zero, if_neg hb] at h
        simp at h
  | succ j ih =>
      intro c h
      by_cases hb : bit v (j + 1) = 1
      · rw [charProgAux_succ, if_pos hb] at h
        rcases List.mem_append.mp h with h | h
        · rcases List.mem_append.mp h with h | h
          · have : c = '<' := (List.mem_replicate.mp h).2
            simp [this]
          · simp at h
            right
            exact h
        · exact ih (j + 1) c h
      · rw [charProgAux_succ, if_neg hb] at h
        exact ih pos c h

/-! ### 6. The printed value -/

/-- The byte the pool ``to_s`` prints, expanded: ``128*l[0] + 64*l[1] + ...
+ l[7]``, exactly the binary string ``to_s`` joins. -/
def poolSum (f : ℕ → ℕ) : ℕ :=
  128 * f 0 + 64 * f 1 + 32 * f 2 + 16 * f 3 + 8 * f 4 + 4 * f 5 + 2 * f 6 + f 7

/-- ``to_s`` reads the pool back as that binary number. -/
lemma to_s_eq_poolSum (l : List ℕ) {v : ℕ} (h : ∀ k, k ≤ 7 → gets l k = bit v k) :
    to_s l 7 0 = toString (Char.ofNat (poolSum (bit v))) := by
  simp [to_s, poolSum, h]
  apply congrArg toString
  apply congrArg Char.ofNat
  ring

/-- Every byte's binary decomposition sums back to itself (verified over the
byte range). -/
theorem byte_value (v : ℕ) (hv : v < 256) : poolSum (bit v) = v := by
  have hcheck :
      (List.range 256).all (fun w => decide (poolSum (bit w) = w)) = true := by
    native_decide
  have hall : ∀ w ∈ List.range 256, decide (poolSum (bit w) = w) = true :=
    List.all_eq_true.mp hcheck
  have hmem : v ∈ List.range 256 := List.mem_range.mpr hv
  exact of_decide_eq_true (hall v hmem)

/-! ### 7. One character -/

/-- One character's program, run from any state, prints exactly that character
(appending its ``toString`` to the output). -/
lemma run_charProgC (c : Char) (hc : c.toNat < 256) (l : List ℕ) (n : ℕ) (out : String) :
    ∃ pool cell, runList (charProgC c) (l, n, out) = (pool, cell, out ++ toString (Char.ofNat c.toNat)) := by
  let v := c.toNat
  have hv : v < 256 := hc
  have hbits :
      ∀ k, k ≤ 7 → gets (runList (charProgAux v 7 7) (empty_list, 7, out)).1 k = bit v k :=
    run_charProgAux v out 7 7 empty_list (by simp [empty_list]) (by omega) (by omega) (by omega)
      (GoodPool.empty v)
  have hout : (runList (charProgAux v 7 7) (empty_list, 7, out)).2.2 = out :=
    runList_out_preserve (mem_charProgAux v 7 7) empty_list 7 out
  have hprint :
      to_s (runList (charProgAux v 7 7) (empty_list, 7, out)).1 7 0 =
        toString (Char.ofNat c.toNat) := by
    rw [to_s_eq_poolSum _ hbits]
    rw [byte_value v hv]
  refine ⟨(runList (charProgAux v 7 7) (empty_list, 7, out)).1,
          (runList (charProgAux v 7 7) (empty_list, 7, out)).2.1, ?_⟩
  unfold charProgC charProg
  rw [runList_cons]
  rw [show step (l, n, out) ':' = (empty_list, 7, out) by simp [step]]
  rw [runList_append]
  rw [runList_cons]
  rcases hst : runList (charProgAux v 7 7) (empty_list, 7, out) with ⟨p, m, s⟩
  have hs : s = out := by simpa [hst] using hout
  have hp : to_s p 7 0 = toString (Char.ofNat c.toNat) := by
    simpa [hst] using hprint
  rw [show step (p, m, s) '!' = (p, m, s ++ to_s p 7 0) by simp [step]]
  rw [hs, hp]
  rw [runList_nil]

/-! ### 8. The whole text -/

lemma String.ofList_cons (c : Char) (cs : List Char) :
    String.ofList (c :: cs) = toString c ++ String.ofList cs := by
  rw [← String.toList_inj]
  have hc : (toString c).toList = [c] := by
    rw [show toString c = String.singleton c by rfl]
    simp
  simp [hc, String.toList_ofList, String.toList_append]

lemma runList_textProg (t : List Char) (ht : ∀ c ∈ t, c.toNat < 256)
    (l : List ℕ) (n : ℕ) (out : String) :
    ∃ pool cell, runList (textProg t) (l, n, out) = (pool, cell, out ++ String.ofList t) := by
  induction t generalizing l n out with
  | nil =>
      refine ⟨l, n, ?_⟩
      simp [textProg, runList_nil]
  | cons c cs ih =>
      rw [textProg]
      rw [runList_append]
      rcases run_charProgC c (ht c (by simp)) l n out with ⟨pool, cell, hc⟩
      rw [hc]
      rcases ih (by
        intro x hx
        exact ht x (by simp [hx])) pool cell (out ++ toString (Char.ofNat c.toNat)) with
        ⟨pool', cell', hcs⟩
      refine ⟨pool', cell', ?_⟩
      rw [hcs]
      rw [Char.ofNat_toNat]
      rw [String.ofList_cons]
      rw [String.append_assoc]

/-- **Correctness.**  For every byte-range text the generated EXCON program
prints exactly that text. -/
theorem exec_correct (t : List Char) (ht : ∀ c ∈ t, c.toNat < 256) :
    exec (textProg t) = String.ofList t := by
  unfold exec
  rcases runList_textProg t ht empty_list 7 "" with ⟨pool, cell, h⟩
  rw [h]
  simp

end ExconCorrect
