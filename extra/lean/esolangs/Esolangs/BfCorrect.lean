import Mathlib
import Esolangs.BfSetCorrect

/-! Correctness of the brainfuck text generator

The generator ``src/esolangs/tools/generators/tape.py::bf`` emits, per
character, either a ``+``/``-`` run to change the current cell to the byte
value and print in place, or ``[-]`` followed by the ``_bf_set`` multiply
segment (``BfSetCorrect.lean``), which zeroes the current cell, builds the
byte in the *next* cell with the multiply loop, and prints it.  The pointer
walks right one cell per character, so cells to the right of it are always
fresh.

This file proves the generator *correct* through the interpreter's own
transitions: the ``-`` runs and ``[-]`` zeroing are added here, the multiply
segment is reused from ``BfSetCorrect`` (generalised to an arbitrary cell),
and the walk lemma shows each character's segment prints exactly that byte.
-/

namespace BfCorrect

open BfSetCorrect

/-! ### 1. ``-`` runs and ``[-]`` -/

/-- ``-`` repeated ``a`` times subtracts ``a`` from the current cell. -/
lemma run_minusN (a k : ℕ) (s : State) (hk : a ≤ s.tape s.ptr) :
    run (List.replicate a Cmd.minus) k s
      = { s with tape := Function.update s.tape s.ptr (s.tape s.ptr - a) } := by
  induction a generalizing k s with
  | zero => simp [run]
  | succ a ih =>
      rw [List.replicate_succ]
      rw [run_minus]
      have hdec : a ≤ (State.dec s).tape (State.dec s).ptr := by
        simp [State.dec, Function.update]
        omega
      rw [ih k (State.dec s) hdec]
      apply State.ext
      · rfl
      · ext i <;> by_cases h : i = s.ptr
        · subst i
          simp [State.dec, Function.update]
          omega
        · simp [State.dec, Function.update, h]
      · rfl

lemma run_minus_single (k : ℕ) (s : State) : run [Cmd.minus] k s = State.dec s := by
  rw [run_minus, run_nil]

/-- The ``[-]`` zeroing loop: ``[ - ]`` decrements the current cell to zero. -/
lemma run_zero_loop (cur k : ℕ) (s : State) (hcur : s.tape s.ptr = cur) (hk : cur ≤ k) :
    runLoop (fun n s => run [Cmd.minus] n s) k s
      = { s with tape := Function.update s.tape s.ptr 0 } := by
  induction cur generalizing s k with
  | zero =>
      cases k with
      | zero =>
          simp [runLoop]
          apply State.ext
          · rfl
          · ext i <;> by_cases h : i = s.ptr
            · subst i; simp [hcur]
            · simp [h]
          · rfl
      | succ k =>
          rw [runLoop_exit (fun n s => run [Cmd.minus] n s) k s (by simp [hcur])]
          apply State.ext
          · rfl
          · ext i <;> by_cases h : i = s.ptr
            · subst i; simp [hcur]
            · simp [h]
          · rfl
  | succ cur ih =>
      cases k with
      | zero => omega
      | succ k =>
          have hnz : s.tape s.ptr ≠ 0 := by simp [hcur]
          rw [runLoop_step (fun n s => run [Cmd.minus] n s) k s hnz]
          rw [run_minus_single]
          have hcur' : (State.dec s).tape (State.dec s).ptr = cur := by
            simp [State.dec, Function.update, hcur]
          have hk' : cur ≤ k := by omega
          rw [ih k (State.dec s) hcur' hk']
          apply State.ext
          · rfl
          · ext i <;> by_cases h : i = s.ptr
            · subst i
              simp [State.dec, Function.update]
            · simp [State.dec, Function.update, h]
          · rfl

def zeroProg : List Cmd := [Cmd.loop [Cmd.minus]]

lemma run_zero (cur k : ℕ) (s : State) (hcur : s.tape s.ptr = cur) (hk : cur ≤ k) :
    run zeroProg k s = { s with tape := Function.update s.tape s.ptr 0 } := by
  rw [zeroProg, run_loop, run_nil]
  exact run_zero_loop cur k s hcur hk

/-! ### 2. The multiply segment at an arbitrary cell -/

/-- One iteration of ``[>+b<-]`` at pointer ``p``: cell ``p`` drops by one and
cell ``p+1`` gains ``b``. -/
lemma run_body_at (b p k : ℕ) (s : State) (hptr : s.ptr = p) :
    run (body b) k s
      = { s with
          ptr := p,
          tape := Function.update (Function.update s.tape (p + 1) (s.tape (p + 1) + b)) p (s.tape p - 1) } := by
  unfold body
  rw [run_append]
  rw [run_right]
  rw [run_plusN]
  rw [run_left]
  rw [run_minus]
  rw [run_nil]
  apply State.ext
  · simp [State.left, State.right, State.dec, hptr, Nat.add_sub_cancel]
  · ext i
    by_cases h0 : i = p
    · by_cases h1 : i = p + 1
      · simp [State.left, State.right, State.inc, State.dec, Function.update, h0, h1, hptr, Nat.add_sub_cancel]
      · subst i
        simp [State.left, State.right, State.inc, State.dec, Function.update, hptr, Nat.add_sub_cancel]
    · by_cases h1 : i = p + 1
      · subst i
        simp [State.left, State.right, State.inc, State.dec, Function.update, hptr]
      · simp [State.left, State.right, State.inc, State.dec, Function.update, h0, h1, hptr]
  · simp [State.left, State.right, State.dec, State.inc]

/-- **Loop invariant.**  Starting with cell ``p`` = ``a`` and cell ``p+1`` =
``c1``, ``[>+b<-]`` zeroes cell ``p`` and adds ``a*b`` to cell ``p+1``,
provided there is fuel for ``a`` iterations. -/
lemma runLoop_mult_at (a b c1 p k : ℕ) (s : State) (ha : a ≤ k)
    (h0 : s.tape p = a) (h1 : s.tape (p + 1) = c1) (hptr : s.ptr = p)
    (hfree : ∀ i, p + 2 ≤ i → s.tape i = 0) :
    runLoop (fun n s => run (body b) n s) k s
      = { ptr := p, tape := fun i => if i = p then 0 else if i = p + 1 then c1 + a * b else s.tape i,
          out := s.out } := by
  induction a generalizing c1 k s with
  | zero =>
      cases k with
      | zero =>
          simp [runLoop]
          apply State.ext
          · simp [hptr]
          · ext i <;> by_cases h : i = p <;> by_cases h' : i = p + 1
            · simp [h0, h1, h]
            · subst i; simp [h0]
            · subst i; simp [h1]
            · simp [h, h', hfree (by omega)]
          · rfl
      | succ k =>
          rw [runLoop_exit (fun n s => run (body b) n s) k s]
          · apply State.ext
            · simp [hptr]
            · ext i <;> by_cases h : i = p <;> by_cases h' : i = p + 1
              · simp [h0, h1, h]
              · subst i; simp [h0]
              · subst i; simp [h1]
              · simp [h, h', hfree (by omega)]
            · rfl
          · simpa [hptr] using h0
  | succ a ih =>
      have hk1 : 1 ≤ k := by omega
      cases k with
      | zero => omega
      | succ k' =>
      rw [runLoop_step (fun n s => run (body b) n s) k' s]
      · have hs := run_body_at b p (k' + 1) s hptr
        have htape0 : (run (body b) (k' + 1) s).tape p = a := by
          rw [hs]
          simp [h0]
        have htape1 : (run (body b) (k' + 1) s).tape (p + 1) = c1 + b := by
          rw [hs]
          simp [h1]
        have hptr' : (run (body b) (k' + 1) s).ptr = p := by
          rw [hs]
        have hfree' : ∀ i, p + 2 ≤ i → (run (body b) (k' + 1) s).tape i = 0 := by
          intro i hi
          have hnz : i ≠ p := by omega
          have hn1 : i ≠ p + 1 := by omega
          rw [hs]
          simp [hnz, hn1, hfree i hi]
        have ha' : a ≤ k' := by omega
        rw [ih (c1 + b) k' (run (body b) (k' + 1) s) ha' htape0 htape1 hptr' hfree']
        apply State.ext
        · simp [hptr]
        · ext i <;> by_cases h0' : i = p <;> by_cases h1' : i = p + 1
          · simp [h0', h1']
          · simp [h0']
          · subst i
            simp [h0']
            rw [Nat.succ_mul]
            omega
          · rw [hs]
            simp [h0', h1']
        · rw [hs]
      · intro hz
        have hz0 : s.tape p = 0 := by
          simpa [hptr] using hz
        omega

/-- **The ``_bf_set`` program at cell ``p``.**  ``+a[>+b<-]>+r.`` puts
``a*b + r`` in cell ``p+1`` (from a zero cell ``p``) and prints it. -/
lemma bf_set_at (a b r p fuel : ℕ) (s : State)
    (h0 : s.tape p = 0) (h1 : s.tape (p + 1) = 0) (hptr : s.ptr = p)
    (hfree : ∀ i, p + 2 ≤ i → s.tape i = 0) (ha : a ≤ fuel) :
    run (bf_set_prog a b r) fuel s
      = { ptr := p + 1,
          tape := fun i => if i = p then 0 else if i = p + 1 then a * b + r else s.tape i,
          out := s.out ++ [Char.ofNat (a * b + r)] } := by
  unfold bf_set_prog
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  have hplus0 : (run (List.replicate a Cmd.plus) fuel s).tape p = a := by
    rw [run_plusN]
    simp [h0, hptr]
  have hplus1 : (run (List.replicate a Cmd.plus) fuel s).tape (p + 1) = 0 := by
    rw [run_plusN]
    simp [h1, hptr]
  have hplusptr : (run (List.replicate a Cmd.plus) fuel s).ptr = p := by
    rw [run_plusN]
    simp [hptr]
  have hplusfree : ∀ i, p + 2 ≤ i → (run (List.replicate a Cmd.plus) fuel s).tape i = 0 := by
    intro i hi
    have hnz : i ≠ p := by omega
    rw [run_plusN]
    simp [hnz, hptr, hfree i hi]
  have hloop := runLoop_mult_at a b 0 p fuel (run (List.replicate a Cmd.plus) fuel s)
    ha hplus0 hplus1 hplusptr hplusfree
  rw [run_loop, run_nil]
  rw [hloop]
  rw [run_right]
  rw [run_nil]
  rw [run_plusN]
  rw [run_out]
  rw [run_nil]
  apply State.ext
  · simp [State.right, State.emit]
  · ext i
    by_cases h : i = p + 1
    · subst i
      simp [State.right, State.emit, Function.update]
    · by_cases h' : i = p
      · subst i
        simp [State.right, State.emit, Function.update, h, h0]
      · rw [run_plusN]
        simp [State.right, State.emit, Function.update, h, h', hptr]
  · simp [State.right, State.emit, run_plusN]

/-! ### 3. The generator's per-character segments -/

/-- The ``+``/``-`` run that changes the current cell from ``cur`` to ``v``. -/
def deltaRun (cur v : ℕ) : List Cmd :=
  if v ≥ cur then List.replicate (v - cur) Cmd.plus else List.replicate (cur - v) Cmd.minus

/-- One character's segment: either adjust-in-place (delta) or rebuild the
next cell with ``_bf_set``. -/
def seg (rebuild : Bool) (cur v a b r : ℕ) : List Cmd :=
  if rebuild then [Cmd.loop [Cmd.minus]] ++ bf_set_prog a b r
  else deltaRun cur v ++ [Cmd.out]

/-- **Delta path.**  Changing the current cell from ``cur`` to ``v`` and
printing it does not move the pointer. -/
lemma delta_run (cur v k : ℕ) (s : State) (hcur : s.tape s.ptr = cur) :
    run (deltaRun cur v ++ [Cmd.out]) k s
      = { ptr := s.ptr, tape := Function.update s.tape s.ptr v, out := s.out ++ [Char.ofNat v] } := by
  unfold deltaRun
  by_cases hv : v ≥ cur
  · rw [if_pos hv]
    rw [run_append]
    rw [run_plusN]
    rw [run_out]
    rw [run_nil]
    apply State.ext
    · rfl
    · ext i
      by_cases h : i = s.ptr
      · subst i
        simp [State.emit, Function.update]
        rw [hcur]
        exact Nat.add_sub_of_le hv
      · simp [State.emit, Function.update, h]
    · simp [State.emit]
      rw [hcur, Nat.add_sub_of_le hv]
  · have hlt : v < cur := by omega
    rw [if_neg hv]
    rw [run_append]
    have hk : cur - v ≤ s.tape s.ptr := by
      rw [hcur]
      omega
    rw [run_minusN _ _ _ hk]
    rw [run_out]
    rw [run_nil]
    apply State.ext
    · rfl
    · ext i
      by_cases h : i = s.ptr
      · subst i
        simp [State.emit, Function.update]
        rw [hcur]
        exact Nat.sub_sub_self (le_of_lt hlt)
      · simp [State.emit, Function.update, h]
    · simp [State.emit]
      rw [hcur]
      rw [show cur - (cur - v) = v by exact Nat.sub_sub_self (le_of_lt hlt)]

/-- **Rebuild path.**  ``[-]+a[>+b<-]>+r.`` zeroes the current cell, builds
the byte in the next cell and prints it, moving the pointer right. -/
lemma rebuild_run (a b r cur v p fuel : ℕ) (s : State) (hv : a * b + r = v)
    (hcur : s.tape s.ptr = cur) (hptr : s.ptr = p)
    (hfree : ∀ i, p + 2 ≤ i → s.tape i = 0) (hf1 : s.tape (p + 1) = 0)
    (hf2 : cur ≤ fuel) (hf3 : a ≤ fuel) :
    run ([Cmd.loop [Cmd.minus]] ++ bf_set_prog a b r) fuel s
      = { ptr := p + 1,
          tape := fun i => if i = p then 0 else if i = p + 1 then v else s.tape i,
          out := s.out ++ [Char.ofNat v] } := by
  rw [run_append]
  have hzero := run_zero cur fuel s hcur hf2
  rw [show run [Cmd.loop [Cmd.minus]] fuel s = run zeroProg fuel s by rfl]
  rw [hzero]
  have hfree0 : ∀ i, s.ptr + 2 ≤ i → ({ s with tape := Function.update s.tape s.ptr 0 }).tape i = 0 := by
    intro i hi
    have hnz : i ≠ s.ptr := by omega
    simp [hnz, hfree i (by simpa [hptr] using hi)]
  have h1' : ({ s with tape := Function.update s.tape s.ptr 0 }).tape (s.ptr + 1) = 0 := by
    have hn : s.ptr + 1 ≠ s.ptr := by omega
    simp [hn, hf1, hptr]
  have hset := bf_set_at a b r s.ptr fuel { s with tape := Function.update s.tape s.ptr 0 }
    (by simp) h1' rfl hfree0 hf3
  rw [hset]
  rw [hv]
  apply State.ext
  · simp [hptr]
  · ext i
    by_cases h0 : i = s.ptr
    · by_cases h1 : i = s.ptr + 1
      · simp [h0, h1, hptr]
      · subst i
        simp [hptr]
    · by_cases h1 : i = s.ptr + 1
      · subst i
        simp [hptr]
      · have hnz : i ≠ p := by omega
        have hn1 : i ≠ p + 1 := by omega
        simp [Function.update, hptr, hnz, hn1]
  · rfl

/-! ### 4. The whole walk -/

/-- The value held in the cell under the pointer after processing ``ts``. -/
def lastV : List (ℕ × ℕ × ℕ × ℕ) → ℕ → ℕ
  | [], cur => cur
  | (v, _, _, _) :: ts, _ => lastV ts v

/-- Concatenated per-character segments; each entry is ``(v, a, b, r)`` with
``a*b + r = v``.  ``cur`` is the value of the current cell. -/
def progAux (choice : ℕ → ℕ → Bool) : List (ℕ × ℕ × ℕ × ℕ) → ℕ → List Cmd
  | [], _cur => []
  | (v, a, b, r) :: ts, cur => seg (choice cur v) cur v a b r ++ progAux choice ts v

/-- **Correctness.**  For any per-character choice (adjust-in-place or
rebuild), the generated program prints each byte value in order. -/
theorem progAux_correct (choice : ℕ → ℕ → Bool) :
    ∀ ts : List (ℕ × ℕ × ℕ × ℕ),
      (∀ (v a b r : ℕ), (v, a, b, r) ∈ ts → a * b + r = v ∧ 1 ≤ a) →
      ∀ (cur fuel : ℕ) (s : State),
        s.tape s.ptr = cur →
        (∀ i, s.ptr < i → s.tape i = 0) →
        cur + 1 ≤ fuel →
        (∀ (v a b r : ℕ), (v, a, b, r) ∈ ts → v + 1 ≤ fuel ∧ a ≤ fuel) →
        let s' := run (progAux choice ts cur) fuel s
        s'.out = s.out ++ ts.map (fun (v, _, _, _) => Char.ofNat v) ∧
        s'.tape s'.ptr = lastV ts cur ∧
        (∀ i, s'.ptr < i → s'.tape i = 0) := by
  intro ts
  induction ts with
  | nil =>
      intro hguard cur fuel s hcur hfresh hf hf'
      simp [progAux, run]
      exact ⟨hcur, hfresh⟩
  | cons t ts ih =>
      intro hguard cur fuel s hcur hfresh hf hf'
      rcases t with ⟨v, a, b, r⟩
      have hvr : a * b + r = v := (hguard v a b r (by simp)).1
      have hfcur : cur ≤ fuel := by omega
      have hfv : v + 1 ≤ fuel := (hf' v a b r (by simp)).1
      have hfa : a ≤ fuel := (hf' v a b r (by simp)).2
      rw [progAux]
      unfold seg
      by_cases hc : choice cur v
      · rw [if_pos hc]
        rw [run_append]
        have hfree2 : ∀ i, s.ptr + 2 ≤ i → s.tape i = 0 := by
          intro i hi; exact hfresh i (by omega)
        have hf1 : s.tape (s.ptr + 1) = 0 := by
          exact hfresh (s.ptr + 1) (by omega)
        have hreb := rebuild_run a b r cur v s.ptr fuel s hvr hcur rfl hfree2 hf1 hfcur hfa
        rw [hreb]
        have ih' := ih (fun v a b r hmem => hguard v a b r (by simp [hmem]))
          v fuel { ptr := s.ptr + 1,
                   tape := fun i => if i = s.ptr then 0 else if i = s.ptr + 1 then v else s.tape i,
                   out := s.out ++ [Char.ofNat v] }
          (by simpa [show s.ptr + 1 ≠ s.ptr by omega]) (by
            intro i hi
            have hi2 : s.ptr + 2 ≤ i := by
              simpa [Nat.add_assoc] using Nat.succ_le_of_lt hi
            have hnz : i ≠ s.ptr := by omega
            have hn1 : i ≠ s.ptr + 1 := by omega
            simp [hnz, hn1, hfree2 i hi2]) hfv
          (fun v a b r hmem => hf' v a b r (by simp [hmem]))
        simp [ih'.1, List.append_assoc, lastV]
        exact ⟨ih'.2.1, ih'.2.2⟩
      · rw [if_neg hc]
        rw [run_append]
        have hd := delta_run cur v fuel s hcur
        rw [hd]
        have ih' := ih (fun v a b r hmem => hguard v a b r (by simp [hmem]))
          v fuel { ptr := s.ptr,
                   tape := Function.update s.tape s.ptr v,
                   out := s.out ++ [Char.ofNat v] }
          (by simp) (by
            intro i hi
            have hnz : i ≠ s.ptr := ne_of_gt hi
            simp [hnz, hfresh i hi]) hfv
          (fun v a b r hmem => hf' v a b r (by simp [hmem]))
        simp [ih'.1, List.append_assoc, lastV]
        exact ⟨ih'.2.1, ih'.2.2⟩

-- Sanity: the generator's delta and rebuild segments print their byte.
example : (run (deltaRun 0 7 ++ [Cmd.out]) 7
    { ptr := 0, tape := fun _ => 0, out := [] }).out = [Char.ofNat 7] := by
  native_decide
example : (run ([Cmd.loop [Cmd.minus]] ++ bf_set_prog 2 3 1) 100
    { ptr := 0, tape := fun _ => 0, out := [] }).out = [Char.ofNat 7] := by
  native_decide

end BfCorrect
