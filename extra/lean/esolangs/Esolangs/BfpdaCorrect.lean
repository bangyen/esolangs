import Mathlib

/-! Bracket matching in the BF-PDA interpreter

The BF-PDA interpreter's ``find`` (`Esolangs/bfpda.lean`) walks the program
counting bracket depth: ``[`` adds 1, ``]`` subtracts 1, and it stops when the
count returns to 0.  This file proves that walk is correct: for a balanced
program, walking forward from an opening bracket reaches depth 0 *exactly* at
the matching closing bracket (the depth is strictly positive everywhere
before it), so the walk terminates within the program and lands on the
matching bracket.

The walk is formalised purely over ``List Char`` (``find``'s recursion over
the string iterator does exactly this: it advances one character at a time
and adds ``depthOf c`` to the running count).  The interpreter's bracket
handling inherits a quirk from the Lean 3 original — ``find`` always returns
the position after the bracket itself — so the certified property here is the
matching logic ``find`` computes, not the jump it returns.
-/

namespace BfpdaCorrect

/-- Depth contribution of a character: ``[`` opens, ``]`` closes. -/
def depthOf (c : Char) : ℤ :=
  if c = '[' then 1 else if c = ']' then -1 else 0

/-- Depth after walking the prefix ``l`` starting from ``z``. -/
def depth (l : List Char) : ℤ → ℤ
  | z => l.foldl (fun z c => z + depthOf c) z

/-- Balanced bracket sequences: ``ε | c S | [ S ] S`` where ``c`` is any
non-bracket character (the depth walk ignores it). -/
inductive Balanced : List Char → Prop
  | nil : Balanced []
  | skip {c : Char} {l : List Char} (hc : c ≠ '[') (hc' : c ≠ ']') (hl : Balanced l) :
      Balanced (c :: l)
  | wrap {l r : List Char} (hl : Balanced l) (hr : Balanced r) :
      Balanced (['['] ++ l ++ [']'] ++ r)

lemma depthOf_open : depthOf '[' = 1 := by
  simp [depthOf]

lemma depthOf_close : depthOf ']' = -1 := by
  simp [depthOf]

lemma depthOf_eq_zero {c : Char} (hc : c ≠ '[') (hc' : c ≠ ']') : depthOf c = 0 := by
  simp [depthOf, hc, hc']

lemma depth_cons (c : Char) (l : List Char) (z : ℤ) : depth (c :: l) z = depth l (z + depthOf c) := by
  rfl

lemma depth_append (l1 l2 : List Char) (z : ℤ) : depth (l1 ++ l2) z = depth l2 (depth l1 z) := by
  unfold depth
  rw [List.foldl_append]

lemma depth_open (z : ℤ) : depth ['['] z = z + 1 := by
  simp [depth, depthOf]

lemma depth_close (z : ℤ) : depth [']'] z = z - 1 := by
  simp [depth, depthOf]
  ring

/-- A balanced block contributes net zero to the depth. -/
lemma Balanced.depth_netzero : Balanced l → depth l z = z
  | .nil => by simp [depth]
  | @Balanced.skip c l hc hc' hl => by
      rw [depth_cons, depthOf_eq_zero hc hc']
      rw [Balanced.depth_netzero hl]
      omega
  | @Balanced.wrap l r hl hr => by
      rw [depth_append (['['] ++ l ++ [']']) r]
      rw [Balanced.depth_netzero hr]
      rw [depth_append (['['] ++ l) [']']]
      rw [depth_append ['['] l]
      rw [Balanced.depth_netzero hl]
      rw [depth_close]
      rw [depth_open]
      ring

/-- Walking a balanced block never drops below the starting depth. -/
lemma Balanced.depth_prefix : Balanced l → ∀ z, ∀ k, k ≤ l.length → depth (List.take k l) z ≥ z
  | .nil, z, k, hk => by
      have hk0 : k = 0 := Nat.eq_zero_of_le_zero (by simpa using hk)
      subst k
      simp [depth]
  | @Balanced.skip c l hc hc' hl, z, k, hk => by
      by_cases hk0 : k = 0
      · subst k
        simp [depth]
      · have hk1 : 1 ≤ k := by omega
        have htake : List.take k (c :: l) = c :: List.take (k - 1) l := by
          rw [show k = (k - 1) + 1 by omega]
          rw [List.take_succ_cons]
          congr 1
        rw [htake]
        rw [depth_cons, depthOf_eq_zero hc hc']
        rw [show z + 0 = z by omega]
        rw [show (c :: l).length = l.length + 1 by simp] at hk
        have hkk : k - 1 ≤ l.length := by omega
        have hpre := hl.depth_prefix z (k - 1) hkk
        omega
  | @Balanced.wrap l r hl hr, z, k, hk => by
      let block := ('[' :: l) ++ [']']
      have hb : Balanced block := by
        unfold block
        simpa using Balanced.wrap hl Balanced.nil
      have hlen : block.length = l.length + 2 := by
        unfold block
        simp
      change k ≤ (block ++ r).length at hk
      have hmain : ∀ k, k ≤ block.length → depth (List.take k block) z ≥ z := by
        intro k hk
        by_cases hk0 : k = 0
        · subst k
          simp [depth]
        · have hk1 : 1 ≤ k := by omega
          by_cases hkl : k ≤ l.length + 1
          · have htake : List.take k block = '[' :: List.take (k - 1) l := by
              unfold block
              rw [show ('[' :: l) ++ [']'] = '[' :: (l ++ [']']) by simp]
              rw [show k = (k - 1) + 1 by omega]
              rw [List.take_succ_cons]
              rw [List.take_append_of_le_length (by omega)]
              simp
            rw [htake]
            simp [depth_cons, depthOf_open]
            have hkk : k - 1 ≤ l.length := by omega
            have hpre := hl.depth_prefix (z + 1) (k - 1) hkk
            omega
          · have hk2 : k = l.length + 2 := by omega
            have htake : List.take k block = '[' :: l ++ [']'] := by
              unfold block
              rw [hk2]
              simp
            rw [htake]
            simp [depth_cons, depthOf_open]
            rw [depth_append]
            rw [hl.depth_netzero]
            rw [depth_close]
            omega
      by_cases hkb : k ≤ block.length
      · change depth (List.take k (block ++ r)) z ≥ z
        rw [List.take_append_of_le_length hkb]
        simp
        exact hmain k hkb
      · change depth (List.take k (block ++ r)) z ≥ z
        have hkr : block.length < k := by omega
        rw [List.take_append]
        rw [List.take_of_length_le (by omega)]
        rw [depth_append]
        rw [hb.depth_netzero]
        have hlenr : (block ++ r).length = block.length + r.length := by simp
        have hkk : k - block.length ≤ r.length := by
          rw [Nat.sub_le_iff_le_add]
          rw [hlenr] at hk
          omega
        have hpre := hr.depth_prefix z (k - block.length) hkk
        exact hpre

/-- **Bracket matching.**  For a balanced ``[ l ]`` block, walking from the
opening bracket the depth returns to zero exactly at the matching closing
bracket: it is strictly positive at every position in between (so ``find``
never stops early) and reaches zero at the ``]`` itself (so ``find`` stops
there). -/
theorem match_forward (hl : Balanced l) :
    depth (['['] ++ l ++ [']']) 0 = 0 ∧
      ∀ k, 1 ≤ k → k < (['['] ++ l ++ [']']).length →
        depth (List.take k (['['] ++ l ++ [']'])) 0 > 0 := by
  constructor
  · have hb : Balanced (['['] ++ l ++ [']']) := by
      simpa using Balanced.wrap hl Balanced.nil
    exact hb.depth_netzero
  · intro k hk1 hklt
    have hkl : k ≤ l.length + 1 := by
      have hlen : (['['] ++ l ++ [']']).length = l.length + 2 := by simp
      omega
    have htake : List.take k (['['] ++ l ++ [']']) = '[' :: List.take (k - 1) l := by
      rw [show (['['] ++ l) ++ [']'] = '[' :: (l ++ [']']) by simp]
      rw [show k = (k - 1) + 1 by omega]
      rw [List.take_succ_cons]
      rw [List.take_append_of_le_length (by omega)]
      simp
    rw [htake]
    rw [depth_cons, depthOf_open]
    have hkk : k - 1 ≤ l.length := by omega
    have hpre := hl.depth_prefix 1 (k - 1) hkk
    rw [show (0 + 1 : ℤ) = 1 by omega]
    omega

end BfpdaCorrect
