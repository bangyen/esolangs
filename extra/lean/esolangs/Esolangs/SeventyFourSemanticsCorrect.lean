import Mathlib
import Esolangs.seventy_four

/-! Number Seventy-Four interpreter equivalence

The reference interpreter ``src/esolangs/interpreters/other/seventy_four.py``
scans the program in repeated passes: ``0``/``1`` push their bit onto the
front of the output, ``H`` writes an ``H`` only if the output already starts
with ``0``, and once the output starts with ``H`` at a *pass boundary* the
program prints it and halts; a program whose output never starts with ``H``
restarts forever.  The ported interpreter (``Esolangs/seventy_four.lean``,
modelled purely below as ``leanRunAux``) instead walks the program once,
checking whether the output starts with ``H`` *before every command*, and
stops after ``limit`` commands.

The push semantics (``push``) are identical in both.  The two interpreters
agree exactly when the output first starts with ``H`` at the last meaningful
command and the port reaches it within its ``limit``: the port halts at the
next check and the reference at the pass boundary, both with the same string.
This is the guard below — ``NoEarlyH`` (no proper prefix of the meaningful
commands makes the output start with ``H``, so the port never halts early)
plus ``prog.length ≤ limit`` (the port reaches the last meaningful command)
plus ``front (outOf (meany prog)) = 'H'`` (the run halts at all).  The
divergence is real and documented: ``0H0H`` makes the output start with
``H`` mid-pass (after ``0H``), so the port prints ``H0`` while the reference
finishes the pass and prints ``H0H0``; here ``NoEarlyH`` fails.

``front`` facts below are reduced to ``s.toList.headD 'A'`` (``front_eq_headD``),
so the empty-output sentinel and the pushed front characters are just list
heads.
-/

namespace SeventyFourSemanticsCorrect

set_option linter.unusedVariables false

open SeventyFour

/-! ### 1. The push and the output -/

/-- One meaningful command: ``0``/``1`` push their bit, ``H`` writes an
``H`` only if the output starts with ``0``; anything else is a no-op.  This
is exactly the per-command transition both interpreters use. -/
def push (s : String) (c : Char) : String :=
  if c = '0' then "0" ++ s
  else if c = '1' then "1" ++ s
  else if c = 'H' then (if s.front = '0' then "H" else "") ++ s
  else s

/-- The meaningful commands of a program (the ``0``/``1``/``H`` pushes). -/
def meany : List Char → List Char :=
  List.filter (fun c => c = '0' ∨ c = '1' ∨ c = 'H')

lemma meany_cons_0 (rest : List Char) : meany ('0' :: rest) = '0' :: meany rest := by
  simp [meany]

lemma meany_cons_1 (rest : List Char) : meany ('1' :: rest) = '1' :: meany rest := by
  simp [meany]

lemma meany_cons_H (rest : List Char) : meany ('H' :: rest) = 'H' :: meany rest := by
  simp [meany]

lemma meany_cons_noop (c : Char) (rest : List Char) (h0 : c ≠ '0') (h1 : c ≠ '1')
    (hH : c ≠ 'H') : meany (c :: rest) = meany rest := by
  unfold meany
  simp [h0, h1, hH]

/-- The output after applying a list of pushes to empty output. -/
def outOf (l : List Char) : String :=
  l.foldl push ""

/-- One pass of the reference interpreter. -/
def onePass (prog : List Char) (s : String) : String :=
  prog.foldl push s

/-! ### 2. The ported interpreter, purely -/

/-- The port's run from output ``s`` with ``n`` commands left: it processes
the program (past the end as no-ops) until either the output starts with
``H`` or the limit runs out. -/
def leanRunAux (n : ℕ) (prog : List Char) (s : String) : String :=
  if n = 0 then s
  else if s.front = 'H' then s
  else match prog with
    | [] => leanRunAux (n - 1) [] s
    | c :: rest => leanRunAux (n - 1) rest (push s c)

/-- The port's output for a program. -/
def leanRun (prog : List Char) : String :=
  leanRunAux limit prog ""

/-! ### 3. The reference interpreter, purely -/

/-- The reference's repeated-pass run: halts when the output starts with
``H``, giving up (``none``) after ``k`` passes to model a program that never
halts. -/
def pyRunAux (k : ℕ) (prog : List Char) (s : String) : Option String :=
  if s.front = 'H' then some s
  else if k = 0 then none
  else pyRunAux (k - 1) prog (onePass prog s)

/-- The reference's output for a program (``none`` if it never halts).  A
program with no meaningful commands halts with no output, as the reference
does. -/
def pyRun (prog : List Char) : Option String :=
  if (meany prog).isEmpty then some ""
  else pyRunAux limit prog ""

/-! ### 4. Front of a pushed string -/

/-- The front of a string built from a list is its head. -/
lemma front_cons (c : Char) (rest : List Char) : (String.ofList (c :: rest)).front = c := by
  have hc : String.ofList (c :: rest) = String.singleton c ++ String.ofList rest := by
    apply String.ext
    simp
  rw [hc]
  simp [String.front, String.front?, String.Slice.front?, String.Slice.Pos.get?,
        String.Slice.Pos.get, String.decodeChar, ByteArray.utf8DecodeChar]

/-- ``String.front`` is the ``List`` head (with ``String``'s ``'A'``
sentinel for the empty string). -/
lemma front_eq_headD (s : String) : s.front = s.toList.headD 'A' := by
  by_cases hs : s = ""
  · subst s
    rfl
  · cases htl : s.toList with
    | nil =>
        exfalso
        apply hs
        apply String.ext
        simpa using htl
    | cons c rest =>
        have hs' : s = String.ofList (c :: rest) := String.ext (by simpa [htl])
        subst s
        rw [front_cons]
        simp

lemma front_append_0 (s : String) : ("0" ++ s).front = '0' := by
  rw [front_eq_headD]
  simp

lemma front_append_1 (s : String) : ("1" ++ s).front = '1' := by
  rw [front_eq_headD]
  simp

lemma front_append_H (s : String) : ("H" ++ s).front = 'H' := by
  rw [front_eq_headD]
  simp

lemma front_push_0 (s : String) : (push s '0').front = '0' := by
  change ("0" ++ s).front = '0'
  exact front_append_0 s

lemma front_push_1 (s : String) : (push s '1').front = '1' := by
  change ("1" ++ s).front = '1'
  exact front_append_1 s

lemma push_H_front0 (s : String) (h : s.front = '0') : push s 'H' = "H" ++ s := by
  unfold push
  rw [if_pos h]
  simp

lemma front_push_H_front0 (s : String) (h : s.front = '0') : (push s 'H').front = 'H' := by
  rw [push_H_front0 s h]
  exact front_append_H s

lemma push_H_not0 (s : String) (h : s.front ≠ '0') : push s 'H' = s := by
  unfold push
  rw [if_neg h]
  simp

lemma push_noop (s : String) {c : Char} (h0 : c ≠ '0') (h1 : c ≠ '1') (hH : c ≠ 'H') :
    push s c = s := by
  unfold push
  rw [if_neg h0, if_neg h1, if_neg hH]

/-! ### 5. The push fold only depends on the meaningful commands -/

lemma foldl_meany (prog : List Char) (s : String) :
    prog.foldl push s = (meany prog).foldl push s := by
  induction prog generalizing s with
  | nil => rfl
  | cons c rest ih =>
      by_cases h0 : c = '0'
      · subst c
        simp [meany, push, ih]
      · by_cases h1 : c = '1'
        · subst c
          simp [meany, push, ih]
        · by_cases hH : c = 'H'
          · subst c
            simp [meany, push, ih]
          · simp [meany, push, h0, h1, hH, ih]

/-- The reference's first pass from empty output reaches the output of the
meaningful commands. -/
lemma onePass_empty (prog : List Char) : onePass prog "" = outOf (meany prog) := by
  unfold onePass outOf
  exact foldl_meany prog ""

/-! ### 6. The guard -/

/-- ``NoEarlyH prog s``: from output ``s``, no proper prefix of the
meaningful commands makes the output start with ``H``, so the port never
halts before the last meaningful command. -/
def NoEarlyH (prog : List Char) (s : String) : Prop :=
  ∀ k, k < (meany prog).length →
    ((List.take k (meany prog)).foldl push s).front ≠ 'H'

/-- ``NoEarlyH`` survives a push when the pushed command is not the last
meaningful one. -/
lemma NoEarlyH_push {prog : List Char} {s : String} {c : Char}
    (hc : c = '0' ∨ c = '1' ∨ c = 'H') (hne : (meany prog) ≠ [])
    (hp : NoEarlyH (c :: prog) s) : NoEarlyH prog (push s c) := by
  intro k hk
  have hlen : (meany (c :: prog)).length = (meany prog).length + 1 := by
    rcases hc with rfl | rfl | rfl <;> simp [meany]
  have hk1 : k + 1 < (meany (c :: prog)).length := by
    rw [hlen]
    exact Nat.succ_lt_succ hk
  have htake :
      (List.take k (meany prog)).foldl push (push s c)
        = (List.take (k + 1) (meany (c :: prog))).foldl push s := by
    rcases hc with rfl | rfl | rfl <;> simp [meany, List.take_succ_cons, List.foldl_cons]
  rw [htake]
  exact hp (k + 1) hk1

/-! ### 7. The port reaches the last meaningful command -/

/-- From empty output the run with nothing left just returns the output. -/
lemma leanRunAux_empty (n : ℕ) (s : String) : leanRunAux n [] s = s := by
  induction n with
  | zero => simp [leanRunAux]
  | succ n ih =>
      by_cases h : s.front = 'H'
      · unfold leanRunAux
        rw [h]
        simp
      · unfold leanRunAux
        rw [if_neg h]
        simp [Nat.succ_sub_one]
        exact ih

/-- A run over no meaningful commands leaves the output alone. -/
lemma leanRunAux_noop (rest : List Char) (m : ℕ) (s : String) (hr : meany rest = []) :
    leanRunAux m rest s = s := by
  induction rest generalizing m s with
  | nil => exact leanRunAux_empty m s
  | cons c rest' ih =>
      have hc0 : c ≠ '0' := by
        intro h
        subst c
        simp [meany] at hr
      have hc1 : c ≠ '1' := by
        intro h
        subst c
        simp [meany] at hr
      have hcH : c ≠ 'H' := by
        intro h
        subst c
        simp [meany] at hr
      by_cases hm : m = 0
      · subst m
        unfold leanRunAux
        simp
      · by_cases hf : s.front = 'H'
        · rw [leanRunAux.eq_2]
          rw [if_neg hm, if_pos hf]
        · rw [leanRunAux.eq_2]
          rw [if_neg hm, if_neg hf]
          rw [push_noop s hc0 hc1 hcH]
          have hr' : meany rest' = [] := by
            rw [meany_cons_noop c rest' hc0 hc1 hcH] at hr
            exact hr
          exact ih (m - 1) s hr'

/-- **The port's run.**  Under the guard, the port processes all the
meaningful commands and halts with their full output: it never halts early
(``NoEarlyH``) and has budget enough to reach the last one. -/
lemma leanRunAux_guarded (prog : List Char) (n : ℕ) (s : String)
    (hs : s.front ≠ 'H') (hp : NoEarlyH prog s) (hn : prog.length ≤ n) :
    leanRunAux n prog s = (meany prog).foldl push s := by
  induction prog generalizing n s with
  | nil =>
      simp [meany]
      exact leanRunAux_empty n s
  | cons c rest ih =>
      by_cases h0 : c = '0'
      · subst c
        have hnz : n ≠ 0 := by
          intro h
          subst n
          simpa using hn
        by_cases hne : meany rest = []
        · have hrun : leanRunAux n ('0' :: rest) s = leanRunAux (n - 1) rest (push s '0') := by
            rw [leanRunAux.eq_2]
            rw [if_neg hnz, if_neg hs]
          rw [hrun]
          rw [leanRunAux_noop rest (n - 1) (push s '0') hne]
          rw [meany_cons_0]
          simp [hne]
        · have hprop : NoEarlyH rest (push s '0') := NoEarlyH_push (c := '0') (by simp)
            hne hp
          have hrun : leanRunAux n ('0' :: rest) s = leanRunAux (n - 1) rest (push s '0') := by
            rw [leanRunAux.eq_2]
            rw [if_neg hnz, if_neg hs]
          rw [hrun]
          have hs' : (push s '0').front ≠ 'H' := by
            rw [front_push_0]
            decide
          have hnrest : rest.length ≤ n - 1 := by
            have hlen : rest.length + 1 ≤ n := by simpa using hn
            omega
          rw [ih (n - 1) (push s '0') hs' hprop hnrest]
          simp [meany, List.foldl_cons]
      · by_cases h1 : c = '1'
        · subst c
          have hnz : n ≠ 0 := by
            intro h
            subst n
            simpa using hn
          by_cases hne : meany rest = []
          · have hrun : leanRunAux n ('1' :: rest) s = leanRunAux (n - 1) rest (push s '1') := by
              rw [leanRunAux.eq_2]
              rw [if_neg hnz, if_neg hs]
            rw [hrun]
            rw [leanRunAux_noop rest (n - 1) (push s '1') hne]
            rw [meany_cons_1]
            simp [hne]
          · have hprop : NoEarlyH rest (push s '1') := NoEarlyH_push (c := '1') (by simp)
              hne hp
            have hrun : leanRunAux n ('1' :: rest) s = leanRunAux (n - 1) rest (push s '1') := by
              rw [leanRunAux.eq_2]
              rw [if_neg hnz, if_neg hs]
            rw [hrun]
            have hs' : (push s '1').front ≠ 'H' := by
              rw [front_push_1]
              decide
            have hnrest : rest.length ≤ n - 1 := by
              have hlen : rest.length + 1 ≤ n := by simpa using hn
              omega
            rw [ih (n - 1) (push s '1') hs' hprop hnrest]
            simp [meany, List.foldl_cons]
        · by_cases hH : c = 'H'
          · subst c
            have hnz : n ≠ 0 := by
              intro h
              subst n
              simpa using hn
            by_cases hne : meany rest = []
            · have hrun : leanRunAux n ('H' :: rest) s = leanRunAux (n - 1) rest (push s 'H') := by
                rw [leanRunAux.eq_2]
                rw [if_neg hnz, if_neg hs]
              rw [hrun]
              rw [leanRunAux_noop rest (n - 1) (push s 'H') hne]
              rw [meany_cons_H]
              simp [hne]
            · have hprop : NoEarlyH rest (push s 'H') := NoEarlyH_push (c := 'H') (by simp)
                hne hp
              have hrun : leanRunAux n ('H' :: rest) s = leanRunAux (n - 1) rest (push s 'H') := by
                rw [leanRunAux.eq_2]
                rw [if_neg hnz, if_neg hs]
              rw [hrun]
              have hs' : (push s 'H').front ≠ 'H' := by
                intro hfront
                have hlen : 1 < (meany ('H' :: rest)).length := by
                  have hpos : 0 < (meany rest).length := by
                    exact Nat.pos_of_ne_zero (by
                      intro hz
                      exact hne (List.eq_nil_of_length_eq_zero hz))
                  rw [meany_cons_H]
                  simp
                  omega
                have hp0 := hp 1 hlen
                rw [show (List.take 1 (meany ('H' :: rest))).foldl push s = push s 'H' by
                  simp [meany, List.take_succ_cons, List.foldl_cons]] at hp0
                exact hp0 hfront
              have hnrest : rest.length ≤ n - 1 := by
                have hlen : rest.length + 1 ≤ n := by simpa using hn
                omega
              rw [ih (n - 1) (push s 'H') hs' hprop hnrest]
              simp [meany, List.foldl_cons]
          · have hc0 : c ≠ '0' := h0
            have hc1 : c ≠ '1' := h1
            have hcH : c ≠ 'H' := hH
            have hnz : n ≠ 0 := by
              intro h
              subst n
              simpa using hn
            have hrun : leanRunAux n (c :: rest) s = leanRunAux (n - 1) rest s := by
              rw [leanRunAux.eq_2]
              rw [if_neg hnz, if_neg hs]
              rw [push_noop s hc0 hc1 hcH]
            rw [hrun]
            have hnrest : rest.length ≤ n - 1 := by
              have hlen : rest.length + 1 ≤ n := by simpa using hn
              omega
            have hp' : NoEarlyH rest s := by
              unfold NoEarlyH at hp ⊢
              rw [meany_cons_noop c rest hc0 hc1 hcH] at hp
              exact hp
            rw [ih (n - 1) s hs hp' hnrest]
            rw [meany_cons_noop c rest hc0 hc1 hcH]

/-- **The port's output.**  Under the guard the port prints the output of
the meaningful commands. -/
lemma leanRun_output (prog : List Char) (hn : prog.length ≤ limit)
    (hp : NoEarlyH prog "") : leanRun prog = outOf (meany prog) := by
  unfold leanRun
  rw [leanRunAux_guarded prog limit "" (by native_decide) hp hn]
  rfl

/-! ### 8. The reference halts at the pass boundary -/

/-- **The reference's output.**  When the meaningful output starts with
``H`` the reference prints it after the first pass. -/
theorem pyRun_output (prog : List Char) (hh : (outOf (meany prog)).front = 'H') :
    pyRun prog = some (outOf (meany prog)) := by
  have hne : (meany prog) ≠ [] := by
    intro h
    have : (outOf (meany prog)) = "" := by simp [outOf, h]
    rw [this] at hh
    exact (by native_decide : ("".front : Char) ≠ 'H') hh
  unfold pyRun
  simp [hne]
  have hfront : "".front ≠ 'H' := by native_decide
  have hp0 : limit ≠ 0 := by simp [limit]
  rw [pyRunAux.eq_1]
  rw [if_neg hfront, if_neg hp0]
  rw [onePass_empty]
  rw [pyRunAux.eq_1]
  rw [if_pos hh]

/-! ### 9. The equivalence -/

/-- **Interpreter equivalence.**  For a program whose output first starts
with ``H`` at the last meaningful command, reached within the port's limit,
the reference and the port print the same string. -/
theorem interpreter_eq (prog : List Char)
    (hn : prog.length ≤ limit)
    (hh : (outOf (meany prog)).front = 'H')
    (hp : NoEarlyH prog "") :
    pyRun prog = some (leanRun prog) := by
  have hl : leanRun prog = outOf (meany prog) := leanRun_output prog hn hp
  have hp0 := pyRun_output prog hh
  rw [hl]
  exact hp0

end SeventyFourSemanticsCorrect
