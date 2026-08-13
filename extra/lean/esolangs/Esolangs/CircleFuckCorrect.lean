import Mathlib

/-! Correctness of the CircleFuck text generator

The generator ``src/esolangs/tools/generators/tape.py::circlefuck`` emits, for
each byte ``v``, a ``+``/``-`` run that moves the current cell to ``v``, a
``.`` that prints it, and a ``>`` that advances.  CircleFuck's tape *is* the
program text: every cell starts out holding the character code of the
instruction that occupies that position.  So the generator builds the program
left to right, and for cell ``i`` it reads the byte already sitting at
position ``i`` of the program it is still constructing — the cell's value
when the pointer arrives — and emits the shortest ``+``/``-`` path from that
base to ``v`` (mod 256).

This file proves the generator is *correct*: for every byte text, running the
generated program through a pure model of the interpreter's execution prints
exactly that text.  The two structural facts:

  1. **Self-reference is consistent.**  ``ord(prog[i])`` — the byte the
     generator reads at position ``i`` — really is the value of cell ``i``
     when the data pointer first reaches it: blocks are appended rightward,
     each block's instructions lie to the *right* of the cell it targets, and
     the pointer moves exactly one cell per block.
  2. **Delta arithmetic.**  With ``delta = (target - base) % 256``, a run of
     ``delta`` ``+``s (or ``256 - delta`` ``-``s, or nothing when
     ``delta = 0``) moves the cell from ``base`` to ``target`` mod 256.

The main theorem ``circle_correct`` states that for every ``List Char`` text
whose codes are below 256, the output of the pure interpreter on the
generated program equals ``String.ofList t``.
-/

namespace CircleFuckCorrect

set_option linter.unusedVariables false

/-! ### 1. Program and interpreter -/

def plusB : ℕ := 43
def minusB : ℕ := 45
def dotB : ℕ := 46
def gtB : ℕ := 62
def atB : ℕ := 64

/-- Mod 256 decrement, matching Python's floor ``(x - 1) % 256`` (so ``0``
wraps to ``255``). -/
def decMod (x : ℕ) : ℕ := (x + 255) % 256

/-- ``delta`` is the non-negative residue of ``target - base`` mod 256 (the
Python generator's floor ``%``), for ``base, target < 256``. -/
def deltaMod (base target : ℕ) : ℕ :=
  if base ≤ target then target - base else 256 - (base - target)

/-- The ``+``/``-`` run that moves a cell from ``base`` to ``target``.  The
first cell cannot read ``prog[0]`` (the program is still empty), so its run
is chosen from ``target`` directly; the base then is the run's first byte. -/
def runFor (isFirst : Bool) (base target : ℕ) : List ℕ :=
  if isFirst then
    if 44 ≤ target then List.replicate (target - 43) plusB
    else if target = 43 then [plusB, minusB]
    else List.replicate (45 - target) minusB
  else
    let d := deltaMod base target
    if d = 0 then []
    else if d ≤ 128 then List.replicate d plusB
    else List.replicate (256 - d) minusB

/-- The byte the first run leaves cell 0 on. -/
def firstBase (target : ℕ) : ℕ := if 44 ≤ target then 43 else if target = 43 then 43 else 45

/-- One character's block: the run, a print, and (unless last) a move right. -/
def blockFor (isLast isFirst : Bool) (base target : ℕ) : List ℕ :=
  runFor isFirst base target ++ [dotB] ++ (if isLast then [] else [gtB])

def circleProgAux (i : ℕ) (prog : List ℕ) : List Char → List ℕ
  | [] => prog ++ [atB]
  | c :: cs =>
      let base := prog.getD i 0
      circleProgAux (i + 1) (prog ++ blockFor cs.isEmpty (i = 0) base c.toNat) cs

def circleProg (t : List Char) : List ℕ := circleProgAux 0 [] t

/-- A pure model of the interpreter, run over the generated program.  Generated
programs are straight-line (``+`` ``-`` ``.`` ``>`` ``@`` only), and the cells
are the program bytes themselves. -/
def runInstructions : List ℕ → List ℕ → ℕ → String → (List ℕ × ℕ × String)
  | cells, [], ptr, out => (cells, ptr, out)
  | cells, cmd :: rest, ptr, out =>
      if cmd = atB then (cells, ptr, out)
      else if cmd = plusB then runInstructions (cells.set ptr ((cells.getD ptr 0 + 1) % 256)) rest ptr out
      else if cmd = minusB then runInstructions (cells.set ptr (decMod (cells.getD ptr 0))) rest ptr out
      else if cmd = dotB then runInstructions cells rest ptr (out ++ toString (Char.ofNat (cells.getD ptr 0)))
      else if cmd = gtB then runInstructions cells rest ((ptr + 1) % cells.length) out
      else runInstructions cells rest ptr out

/-- Cell value after ``k`` increments. -/
def incRun (k x : ℕ) : ℕ := (x + k) % 256

/-- Cell value after ``k`` decrements. -/
def decRun (k x : ℕ) : ℕ := (x + 255 * k) % 256

/-! ### 2. getD / set on the mutable cells -/

lemma getD_set_self (l : List ℕ) (i v : ℕ) (hi : i < l.length) : (l.set i v).getD i 0 = v := by
  rw [List.getD_eq_getElem _ 0 (by simpa using hi)]
  exact List.getElem_set_self (by simpa using hi)

lemma getD_set_ne (l : List ℕ) (i j v : ℕ) (hj : j < l.length) (hij : i ≠ j) :
    (l.set i v).getD j 0 = l.getD j 0 := by
  rw [List.getD_eq_getElem?_getD, List.getD_eq_getElem?_getD]
  rw [List.getElem?_set']
  simp [hij]

/-! ### 3. One instruction -/

lemma runInstructions_at (cells : List ℕ) (rest : List ℕ) (ptr : ℕ) (out : String) :
    runInstructions cells (atB :: rest) ptr out = (cells, ptr, out) := by
  rfl

lemma runInstructions_plus (cells : List ℕ) (rest : List ℕ) (ptr : ℕ) (out : String) :
    runInstructions cells (plusB :: rest) ptr out =
      runInstructions (cells.set ptr ((cells.getD ptr 0 + 1) % 256)) rest ptr out := by
  rfl

lemma runInstructions_minus (cells : List ℕ) (rest : List ℕ) (ptr : ℕ) (out : String) :
    runInstructions cells (minusB :: rest) ptr out =
      runInstructions (cells.set ptr (decMod (cells.getD ptr 0))) rest ptr out := by
  rfl

lemma runInstructions_dot (cells : List ℕ) (rest : List ℕ) (ptr : ℕ) (out : String) :
    runInstructions cells (dotB :: rest) ptr out =
      runInstructions cells rest ptr (out ++ toString (Char.ofNat (cells.getD ptr 0))) := by
  rfl

lemma runInstructions_gt (cells : List ℕ) (rest : List ℕ) (ptr : ℕ) (out : String) :
    runInstructions cells (gtB :: rest) ptr out =
      runInstructions cells rest ((ptr + 1) % cells.length) out := by
  rfl

/-! ### 4. Runs and mod-256 arithmetic -/

lemma delta_lt (base target : ℕ) (ht : target < 256) : deltaMod base target < 256 := by
  unfold deltaMod
  by_cases h : base ≤ target
  · rw [if_pos h]
    omega
  · rw [if_neg h]
    omega

/-- ``(a % n + b) % n = (a + b) % n``. -/
lemma add_mod_left (a b n : ℕ) : (a % n + b) % n = (a + b) % n := by
  rw [Nat.add_mod]
  simp only [Nat.mod_mod]
  rw [← Nat.add_mod]

lemma incRun_succ (k x : ℕ) : incRun (k + 1) x = (incRun k x + 1) % 256 := by
  unfold incRun
  rw [add_mod_left (x + k) 1 256]
  congr 1

lemma decRun_succ (k x : ℕ) : decRun (k + 1) x = decMod (decRun k x) := by
  unfold decRun decMod
  rw [add_mod_left (x + 255 * k) 255 256]
  apply congrArg (· % 256)
  rw [Nat.mul_add]
  norm_num
  rw [← Nat.add_assoc]

/-- ``255 * (256 - d) = 256 * (255 - d) + d`` for ``d ≤ 255``. -/
lemma mul255_sub (d : ℕ) (hd : d ≤ 255) : 255 * (256 - d) = 256 * (255 - d) + d := by
  omega

/-- ``256 - d`` decrements move ``x`` to ``(x + d) % 256`` (for ``d ≤ 255``). -/
lemma decRun_of_sub (d x : ℕ) (hd : d ≤ 255) : decRun (256 - d) x = (x + d) % 256 := by
  unfold decRun
  rw [mul255_sub d hd]
  rw [Nat.add_comm (256 * (255 - d)) d]
  rw [← Nat.add_assoc]
  rw [← Nat.mul_comm (255 - d) 256]
  rw [Nat.add_mul_mod_self_right]

/-- A ``+`` run of length ``deltaMod base target`` reaches ``target``. -/
lemma delta_inc_reach (base target : ℕ) (hb : base < 256) (ht : target < 256) :
    (base + deltaMod base target) % 256 = target := by
  unfold deltaMod
  by_cases h : base ≤ target
  · rw [if_pos h]
    have hsum : base + (target - base) = target := by omega
    rw [hsum]
    exact Nat.mod_eq_of_lt ht
  · rw [if_neg h]
    have hsum : base + (256 - (base - target)) = 256 + target := by omega
    rw [hsum]
    rw [Nat.add_comm]
    rw [Nat.add_mod_right]
    exact Nat.mod_eq_of_lt ht

/-- A ``-`` run of length ``256 - deltaMod base target`` reaches ``target``. -/
lemma delta_dec_reach (base target : ℕ) (hb : base < 256) (ht : target < 256) :
    decRun (256 - deltaMod base target) base = target := by
  have hd : deltaMod base target ≤ 255 := by
    have h := delta_lt base target ht
    omega
  rw [decRun_of_sub (deltaMod base target) base hd]
  exact delta_inc_reach base target hb ht

/-- If ``delta = 0`` then ``base = target`` (for ``base < 256``). -/
lemma delta_zero_eq (base target : ℕ) (hb : base < 256) (ht : target < 256)
    (hd : deltaMod base target = 0) : base = target := by
  unfold deltaMod at hd
  by_cases h : base ≤ target
  · rw [if_pos h] at hd
    omega
  · rw [if_neg h] at hd
    have hlt : target < base := by omega
    have hd2 : 256 ≤ base - target := Nat.sub_eq_zero_iff_le.mp hd
    have hbase : base = target + (base - target) := by
      rw [Nat.add_comm]
      exact (Nat.sub_add_cancel (by omega)).symm
    have hbig : 256 ≤ base := by
      rw [hbase]
      omega
    omega

/-! ### 5. Executing a run -/

/-- Setting a cell to its own value changes nothing. -/
lemma set_getD_self (l : List ℕ) (i : ℕ) (hi : i < l.length) : l.set i (l.getD i 0) = l := by
  rw [List.getD_eq_getElem _ 0 hi]
  exact List.set_getElem_self hi

/-- A run of ``k ≥ 1`` ``+``s adds ``k`` to the cell. -/
lemma runInstructions_plus_run (cells : List ℕ) (rest : List ℕ) (ptr k : ℕ) (out : String)
    (hk : 0 < k) (hpin : ptr < cells.length) :
    runInstructions cells (List.replicate k plusB ++ rest) ptr out =
      runInstructions (cells.set ptr (incRun k (cells.getD ptr 0))) rest ptr out := by
  induction k generalizing cells with
  | zero => omega
  | succ k ih =>
      rw [List.replicate_succ, List.cons_append]
      rw [runInstructions_plus]
      by_cases hk' : 0 < k
      · have hb' : (cells.set ptr ((cells.getD ptr 0 + 1) % 256)).getD ptr 0 < 256 := by
          rw [getD_set_self _ _ _ hpin]
          exact Nat.mod_lt _ (by norm_num)
        have hpin' : ptr < (cells.set ptr ((cells.getD ptr 0 + 1) % 256)).length := by
          simp [hpin]
        rw [ih (cells.set ptr ((cells.getD ptr 0 + 1) % 256)) hk' hpin']
        have hbase' : (cells.set ptr ((cells.getD ptr 0 + 1) % 256)).getD ptr 0 = (cells.getD ptr 0 + 1) % 256 := by
          rw [getD_set_self _ _ _ hpin]
        rw [hbase']
        rw [List.set_set]
        have hinc : incRun k ((cells.getD ptr 0 + 1) % 256) = incRun (k + 1) (cells.getD ptr 0) := by
          unfold incRun
          rw [add_mod_left (cells.getD ptr 0 + 1) k 256]
          congr 1
          omega
        rw [hinc]
      · have hk0 : k = 0 := by omega
        subst k
        rfl

/-- A run of ``k ≥ 1`` ``-``s subtracts ``k`` from the cell (mod 256). -/
lemma runInstructions_minus_run (cells : List ℕ) (rest : List ℕ) (ptr k : ℕ) (out : String)
    (hk : 0 < k) (hpin : ptr < cells.length) :
    runInstructions cells (List.replicate k minusB ++ rest) ptr out =
      runInstructions (cells.set ptr (decRun k (cells.getD ptr 0))) rest ptr out := by
  induction k generalizing cells with
  | zero => omega
  | succ k ih =>
      rw [List.replicate_succ, List.cons_append]
      rw [runInstructions_minus]
      by_cases hk' : 0 < k
      · have hb' : (cells.set ptr (decMod (cells.getD ptr 0))).getD ptr 0 < 256 := by
          rw [getD_set_self _ _ _ hpin]
          unfold decMod
          exact Nat.mod_lt _ (by norm_num)
        have hpin' : ptr < (cells.set ptr (decMod (cells.getD ptr 0))).length := by
          simp [hpin]
        rw [ih (cells.set ptr (decMod (cells.getD ptr 0))) hk' hpin']
        have hbase' : (cells.set ptr (decMod (cells.getD ptr 0))).getD ptr 0 = decMod (cells.getD ptr 0) := by
          rw [getD_set_self _ _ _ hpin]
        rw [hbase']
        rw [List.set_set]
        have hdec : decRun k (decMod (cells.getD ptr 0)) = decRun (k + 1) (cells.getD ptr 0) := by
          unfold decRun decMod
          rw [add_mod_left (cells.getD ptr 0 + 255) (255 * k) 256]
          congr 1
          omega
        rw [hdec]
      · have hk0 : k = 0 := by omega
        subst k
        rfl

/-- The first run leaves the cell on ``firstBase target``. -/
lemma runFor_first_base (target : ℕ) : (runFor true 0 target).getD 0 0 = firstBase target := by
  by_cases hge : 44 ≤ target
  · have hrun : runFor true 0 target = List.replicate (target - 43) plusB := by
      simp [runFor, hge]
    rw [hrun]
    rw [List.getD_replicate plusB (by omega)]
    simp [firstBase, hge, plusB]
  · by_cases heq : target = 43
    · have hrun : runFor true 0 target = [plusB, minusB] := by
        simp [runFor, heq]
      rw [hrun]
      simp [firstBase, heq, plusB]
    · have hrun : runFor true 0 target = List.replicate (45 - target) minusB := by
        simp [runFor, hge, heq]
      rw [hrun]
      rw [List.getD_replicate minusB (by omega)]
      simp [firstBase, hge, heq, minusB]

/-- ``k ≤ base`` decrements move ``base`` to ``base - k``. -/
lemma decRun_le (k base : ℕ) (hk : k ≤ base) (hb : base < 256) : decRun k base = base - k := by
  unfold decRun
  have hk255 : 255 * k = 256 * k - k := by omega
  rw [hk255]
  have hsum : base + (256 * k - k) = 256 * k + (base - k) := by omega
  rw [hsum]
  rw [Nat.add_comm (256 * k) (base - k)]
  rw [← Nat.mul_comm k 256]
  rw [Nat.add_mul_mod_self_right]
  exact Nat.mod_eq_of_lt (by omega)

/-- The later-cell run is empty exactly when ``delta = 0``. -/
lemma runFor_zero (base target : ℕ) (h : deltaMod base target = 0) :
    runFor false base target = [] := by
  simp [runFor, h]

/-- A ``delta ≤ 128`` later-cell run is ``delta`` ``+``s. -/
lemma runFor_inc (base target : ℕ) (h0 : deltaMod base target ≠ 0)
    (h128 : deltaMod base target ≤ 128) :
    runFor false base target = List.replicate (deltaMod base target) plusB := by
  simp [runFor, h0, h128]

/-- A ``delta > 128`` later-cell run is ``256 - delta`` ``-``s. -/
lemma runFor_dec (base target : ℕ) (h0 : deltaMod base target ≠ 0)
    (h128 : ¬ deltaMod base target ≤ 128) :
    runFor false base target = List.replicate (256 - deltaMod base target) minusB := by
  simp [runFor, h0, h128]

/-- The ``+``/``-`` run moves the cell from its current value to ``target``,
leaving the output and pointer untouched. -/
lemma run_ok (cells : List ℕ) (rest : List ℕ) (i : ℕ) (out : String)
    (isFirst : Bool) (target : ℕ)
    (hin : i < cells.length) (ht : target < 256)
    (hb : cells.getD i 0 < 256)
    (hfirst : isFirst → cells.getD i 0 = firstBase target) :
    runInstructions cells (runFor isFirst (cells.getD i 0) target ++ rest) i out =
      runInstructions (cells.set i target) rest i out := by
  cases isFirst with
  | false =>
      let d := deltaMod (cells.getD i 0) target
      by_cases hd0 : d = 0
      · have htarget : cells.getD i 0 = target := delta_zero_eq _ _ hb ht (by simpa [d] using hd0)
        have hset : cells.set i target = cells := by
          rw [← htarget]
          exact set_getD_self cells i hin
        have hrun : runFor false (cells.getD i 0) target = [] :=
          runFor_zero _ _ (by simpa [d] using hd0)
        rw [hrun]
        simp [hset]
      · by_cases hd128 : d ≤ 128
        · have hd0' : deltaMod (cells.getD i 0) target ≠ 0 := by simpa [d] using hd0
          have hrun : runFor false (cells.getD i 0) target = List.replicate d plusB := by
            rw [show List.replicate d plusB = List.replicate (deltaMod (cells.getD i 0) target) plusB by simp [d]]
            exact runFor_inc (cells.getD i 0) target hd0' hd128
          rw [hrun]
          rw [runInstructions_plus_run cells rest i d out (by omega) hin]
          have hinc : incRun d (cells.getD i 0) = target := by
            unfold incRun
            exact delta_inc_reach (cells.getD i 0) target hb ht
          rw [hinc]
        · have hd0' : deltaMod (cells.getD i 0) target ≠ 0 := by simpa [d] using hd0
          have hdlt : d < 256 := by simpa [d] using delta_lt (cells.getD i 0) target ht
          have hrun : runFor false (cells.getD i 0) target = List.replicate (256 - d) minusB := by
            rw [show List.replicate (256 - d) minusB = List.replicate (256 - deltaMod (cells.getD i 0) target) minusB by simp [d]]
            exact runFor_dec (cells.getD i 0) target hd0' hd128
          rw [hrun]
          rw [runInstructions_minus_run cells rest i (256 - d) out (by omega) hin]
          have hdec : decRun (256 - d) (cells.getD i 0) = target := by
            simpa [d] using delta_dec_reach (cells.getD i 0) target hb ht
          rw [hdec]
  | true =>
      by_cases hge : 44 ≤ target
      · have hb43 : cells.getD i 0 = 43 := by
          have hf := hfirst rfl
          unfold firstBase at hf
          rw [if_pos hge] at hf
          exact hf
        have hrun : runFor true (cells.getD i 0) target = List.replicate (target - 43) plusB := by
          simp [runFor, hge]
        rw [hrun]
        rw [runInstructions_plus_run cells rest i (target - 43) out (by omega) hin]
        have hinc : incRun (target - 43) (cells.getD i 0) = target := by
          rw [hb43]
          unfold incRun
          have hsum : 43 + (target - 43) = target := by omega
          rw [hsum]
          exact Nat.mod_eq_of_lt ht
        rw [hinc]
      · by_cases heq : target = 43
        · have hb43 : cells.getD i 0 = 43 := by
            have hf := hfirst rfl
            unfold firstBase at hf
            rw [if_neg hge] at hf
            rw [if_pos heq] at hf
            exact hf
          have hrun : runFor true (cells.getD i 0) target = [plusB, minusB] := by
            simp [runFor, heq]
          rw [hrun]
          rw [show [plusB, minusB] ++ rest = plusB :: minusB :: rest by simp]
          rw [runInstructions_plus]
          rw [runInstructions_minus]
          have hbase' : (cells.set i ((cells.getD i 0 + 1) % 256)).getD i 0 = (cells.getD i 0 + 1) % 256 := by
            rw [getD_set_self _ _ _ hin]
          rw [hbase']
          rw [List.set_set]
          have hcell : decMod (incRun 1 (cells.getD i 0)) = target := by
            rw [hb43, heq]
            unfold decMod incRun
            norm_num
          rw [show decMod ((cells.getD i 0 + 1) % 256) = decMod (incRun 1 (cells.getD i 0)) by rfl]
          rw [hcell]
        · have hb45 : cells.getD i 0 = 45 := by
            have hf := hfirst rfl
            unfold firstBase at hf
            rw [if_neg hge] at hf
            rw [if_neg heq] at hf
            exact hf
          have hrun : runFor true (cells.getD i 0) target = List.replicate (45 - target) minusB := by
            simp [runFor, hge, heq]
          rw [hrun]
          rw [runInstructions_minus_run cells rest i (45 - target) out (by omega) hin]
          have hdec : decRun (45 - target) (cells.getD i 0) = target := by
            rw [hb45]
            rw [decRun_le (45 - target) 45 (by omega) (by norm_num)]
            omega
          rw [hdec]

/-! ### 6. One block -/

/-- Every block byte is a valid instruction byte (< 256). -/
lemma mem_runFor (isFirst : Bool) (base target : ℕ) :
    ∀ c ∈ runFor isFirst base target, c = plusB ∨ c = minusB := by
  intro c hc
  cases isFirst with
  | false =>
      by_cases h0 : deltaMod base target = 0
      · simp [runFor, h0] at hc
      · by_cases h128 : deltaMod base target ≤ 128
        · have hrun : runFor false base target = List.replicate (deltaMod base target) plusB := runFor_inc base target h0 h128
          rw [hrun] at hc
          left
          exact (List.mem_replicate.mp hc).2
        · have hrun : runFor false base target = List.replicate (256 - deltaMod base target) minusB := runFor_dec base target h0 h128
          rw [hrun] at hc
          right
          exact (List.mem_replicate.mp hc).2
  | true =>
      by_cases hge : 44 ≤ target
      · have hrun : runFor true base target = List.replicate (target - 43) plusB := by
          simp [runFor, hge]
        rw [hrun] at hc
        left
        exact (List.mem_replicate.mp hc).2
      · by_cases heq : target = 43
        · have hrun : runFor true base target = [plusB, minusB] := by
            simp [runFor, heq]
          rw [hrun] at hc
          simpa using hc
        · have hrun : runFor true base target = List.replicate (45 - target) minusB := by
            simp [runFor, hge, heq]
          rw [hrun] at hc
          right
          exact (List.mem_replicate.mp hc).2

lemma mem_blockFor_lt (isLast isFirst : Bool) (base target : ℕ) :
    ∀ c ∈ blockFor isLast isFirst base target, c < 256 := by
  intro c hc
  unfold blockFor at hc
  rcases List.mem_append.mp hc with hc | hc
  · rcases List.mem_append.mp hc with hc | hc
    · rcases mem_runFor isFirst base target c hc with hc | hc
      · rw [hc]
        norm_num [plusB]
      · rw [hc]
        norm_num [minusB]
    · simp at hc
      subst c
      norm_num [dotB]
  · by_cases his : isLast
    · simp [his] at hc
    · simp [his] at hc
      simp [hc, gtB]

lemma blockFor_bytes_ok (isLast isFirst : Bool) (base target : ℕ) :
    ∀ j, j < (blockFor isLast isFirst base target).length → (blockFor isLast isFirst base target).getD j 0 < 256 := by
  intro j hj
  rw [List.getD_eq_getElem _ 0 hj]
  exact mem_blockFor_lt isLast isFirst base target (blockFor isLast isFirst base target)[j] (List.getElem_mem hj)

/-- Every block is at least one byte. -/
lemma blockFor_length (isLast isFirst : Bool) (base target : ℕ) :
    1 ≤ (blockFor isLast isFirst base target).length := by
  unfold blockFor
  cases isLast <;> simp

/-- Executing one block prints ``target`` and advances the pointer. -/
lemma block_ok (cells : List ℕ) (future : List ℕ) (i : ℕ) (out : String)
    (isLast isFirst : Bool) (target : ℕ)
    (hin : i < cells.length) (hi1 : ¬ isLast → i + 1 < cells.length)
    (ht : target < 256) (hb : cells.getD i 0 < 256)
    (hfirst : isFirst → cells.getD i 0 = firstBase target) :
    runInstructions cells (blockFor isLast isFirst (cells.getD i 0) target ++ future) i out =
      runInstructions (cells.set i target) future (if isLast then i else i + 1) (out ++ toString (Char.ofNat target)) := by
  rw [show blockFor isLast isFirst (cells.getD i 0) target ++ future =
      runFor isFirst (cells.getD i 0) target ++ (dotB :: ((if isLast then [] else [gtB]) ++ future)) by
    simp [blockFor]]
  rw [run_ok cells (dotB :: ((if isLast then [] else [gtB]) ++ future)) i out isFirst target hin ht hb hfirst]
  rw [runInstructions_dot]
  rw [getD_set_self _ _ _ hin]
  cases isLast with
  | true => simp
  | false =>
      simp
      rw [runInstructions_gt]
      have hmod : (i + 1) % (cells.set i target).length = i + 1 :=
        Nat.mod_eq_of_lt (by simpa using hi1 (by simp))
      rw [hmod]

/-! ### 7. The whole program -/

/-- ``circleProgAux`` keeps the accumulated prefix intact. -/
lemma circleProgAux_take (t : List Char) (i : ℕ) (prog : List ℕ) :
    (circleProgAux i prog t).take prog.length = prog := by
  induction t generalizing i prog with
  | nil =>
      rw [circleProgAux]
      rw [List.take_append_length]
  | cons c cs ih =>
      let block := blockFor cs.isEmpty (i = 0) (prog.getD i 0) c.toNat
      rw [circleProgAux]
      have h := ih (i + 1) (prog ++ block)
      have htake : (circleProgAux (i + 1) (prog ++ block) cs).take prog.length =
          ((circleProgAux (i + 1) (prog ++ block) cs).take (prog.length + block.length)).take prog.length := by
        rw [List.take_take]
        congr 1
        omega
      rw [htake]
      rw [show prog.length + block.length = (prog ++ block).length by simp]
      rw [h, List.take_append_length]

/-- ``circleProgAux i prog t = prog ++ (the future blocks)``. -/
lemma circleProgAux_eq_append (t : List Char) (i : ℕ) (prog : List ℕ) :
    circleProgAux i prog t = prog ++ (circleProgAux i prog t).drop prog.length := by
  have ht := circleProgAux_take t i prog
  rw [show prog ++ (circleProgAux i prog t).drop prog.length =
      (circleProgAux i prog t).take prog.length ++ (circleProgAux i prog t).drop prog.length by
    rw [ht]]
  rw [List.take_append_drop]

/-- The program is longer than the text it prints. -/
lemma circleProgAux_length (t : List Char) (i : ℕ) (prog : List ℕ) :
    prog.length + t.length + 1 ≤ (circleProgAux i prog t).length := by
  induction t generalizing i prog with
  | nil => simp [circleProgAux]
  | cons c cs ih =>
      rw [circleProgAux]
      have htlen : (c :: cs).length = 1 + cs.length := by
        simp
        omega
      have hih := ih (i + 1) (prog ++ blockFor cs.isEmpty (i = 0) (prog.getD i 0) c.toNat)
      rw [List.length_append] at hih
      have hb : 1 ≤ (blockFor cs.isEmpty (i = 0) (prog.getD i 0) c.toNat).length :=
        blockFor_length _ _ _ _
      omega

/-- The accumulated program keeps all its bytes below 256. -/
lemma circleProgAux_ok (t : List Char) (i : ℕ) (prog : List ℕ)
    (h : ∀ j, j < prog.length → prog.getD j 0 < 256) :
    ∀ j, j < (circleProgAux i prog t).length → (circleProgAux i prog t).getD j 0 < 256 := by
  induction t generalizing i prog with
  | nil =>
      intro j hj
      rw [circleProgAux]
      rw [circleProgAux] at hj
      simp at hj
      by_cases hjl : j < prog.length
      · rw [List.getD_append _ _ _ _ hjl]
        exact h j hjl
      · have hjl2 : prog.length ≤ j := by omega
        rw [List.getD_append_right _ _ _ _ hjl2]
        have hj0 : j - prog.length = 0 := by omega
        rw [hj0]
        norm_num [atB]
  | cons c cs ih =>
      rw [circleProgAux]
      exact ih (i + 1) (prog ++ blockFor cs.isEmpty (i = 0) (prog.getD i 0) c.toNat) (by
        intro j hj
        by_cases hjl : j < prog.length
        · rw [List.getD_append _ _ _ _ hjl]
          exact h j hjl
        · have hjl2 : prog.length ≤ j := by omega
          rw [List.getD_append_right _ _ _ _ hjl2]
          rw [List.length_append] at hj
          exact blockFor_bytes_ok (cs.isEmpty) (i = 0) (prog.getD i 0) c.toNat (j - prog.length) (by omega))

/-- The first run is nonempty, so it sets the cell's base. -/
lemma runFor_first_nonempty (target : ℕ) (ht : target < 256) : 0 < (runFor true 0 target).length := by
  by_cases hge : 44 ≤ target
  · have hpos : 0 < target - 43 := by omega
    simp [runFor, hge, List.length_replicate, hpos]
  · by_cases heq : target = 43
    · simp [runFor, heq]
    · have hpos : 0 < 45 - target := by omega
      simp [runFor, hge, heq, List.length_replicate, hpos]

lemma circle_aux (t : List Char) (i : ℕ) (prog : List ℕ) (ht : ∀ c ∈ t, c.toNat < 256)
    (hprog : i < prog.length ∨ i = 0)
    (hspace : i + t.length < (circleProgAux i prog t).length)
    (hprog0 : i = 0 → prog = [])
    (hbytes : ∀ j, j < prog.length → prog.getD j 0 < 256) :
    ∀ (cells : List ℕ) (out : String),
      (∀ j, i ≤ j → j < (circleProgAux i prog t).length → cells.getD j 0 = (circleProgAux i prog t).getD j 0) →
      cells.length = (circleProgAux i prog t).length →
      (runInstructions cells ((circleProgAux i prog t).drop prog.length) i out).2.2
        = out ++ String.ofList t := by
  induction t generalizing i prog with
  | nil =>
      intro cells out hcells hlenc
      simp [circleProgAux, runInstructions_at]
  | cons c cs ih =>
      intro cells out hcells hlenc
      let target := c.toNat
      let isLast := cs.isEmpty
      let isFirst := i = 0
      let block := blockFor isLast isFirst (prog.getD i 0) target
      let P := circleProgAux i prog (c :: cs)
      let future := P.drop (prog.length + block.length)
      have htarget : target < 256 := ht c (by simp)
      have hP : P = circleProgAux (i + 1) (prog ++ block) cs := by rfl
      have hdrop : P.drop prog.length = block ++ future := by
        unfold future
        rw [hP]
        rw [circleProgAux_eq_append cs (i + 1) (prog ++ block)]
        rw [List.drop_append]
        simp [List.length_append]
      have hin : i < cells.length := by
        have hiP : i < P.length := by
          change i < (circleProgAux i prog (c :: cs)).length
          have htlen : 1 ≤ (c :: cs).length := by simp
          omega
        omega
      have hi1 : ¬ isLast → i + 1 < cells.length := by
        intro hnot
        have hcs : cs ≠ [] := by
          unfold isLast at hnot
          simpa using hnot
        have htlen : (c :: cs).length = 1 + cs.length := by
          simp
          omega
        have hcs1 : 1 ≤ cs.length := by
          have hlen0 : cs.length ≠ 0 := by
            intro h
            apply hcs
            exact List.length_eq_zero_iff.mp h
          exact Nat.pos_of_ne_zero hlen0
        have hiP : i + 1 < P.length := by
          change i + 1 < (circleProgAux i prog (c :: cs)).length
          omega
        omega
      have hcellP : ∀ j, i ≤ j → j < P.length → cells.getD j 0 = P.getD j 0 := by
        intro j hj hjP
        change cells.getD j 0 = (circleProgAux i prog (c :: cs)).getD j 0
        exact hcells j hj hjP
      have hblock : block = blockFor isLast isFirst (cells.getD i 0) target := by
        unfold block
        by_cases his : isFirst
        · unfold blockFor
          simp [runFor, isFirst, his]
        · have hprog' : i < prog.length := by
            rcases hprog with h | h
            · exact h
            · contradiction
          have hbaseeq : prog.getD i 0 = P.getD i 0 := by
            rw [hP]
            rw [circleProgAux_eq_append cs (i + 1) (prog ++ block)]
            have hlen : (prog ++ block).length = prog.length + block.length := by simp
            have h1 : i < (prog ++ block).length := by omega
            rw [List.getD_append _ _ _ _ h1]
            rw [List.getD_append _ _ _ _ hprog']
          have hiP : i < P.length := by
            change i < (circleProgAux i prog (c :: cs)).length
            have htlen : 1 ≤ (c :: cs).length := by simp
            omega
          rw [hbaseeq]
          rw [hcellP i (by omega) hiP]
      have hb : cells.getD i 0 < 256 := by
        have hok := circleProgAux_ok (c :: cs) i prog hbytes
        have hiP : i < P.length := by
          change i < (circleProgAux i prog (c :: cs)).length
          have htlen : 1 ≤ (c :: cs).length := by simp
          omega
        rw [hcellP i (by omega) hiP]
        exact hok i hiP
      have hfirst : isFirst → cells.getD i 0 = firstBase target := by
        intro his
        have hiP : i < P.length := by
          change i < (circleProgAux i prog (c :: cs)).length
          have htlen : 1 ≤ (c :: cs).length := by simp
          omega
        rw [hcellP i (by omega) hiP]
        -- P.getD i 0 = firstBase target
        have his0 : i = 0 := by
          unfold isFirst at his
          exact his
        have hprog0' : prog = [] := hprog0 his0
        unfold P target
        rw [his0]
        rw [hprog0']
        rw [circleProgAux]
        rw [show ([] ++ blockFor cs.isEmpty (decide (0 = 0)) ([].getD 0 0) c.toNat) = blockFor cs.isEmpty true 0 c.toNat by
          simp]
        rw [circleProgAux_eq_append cs 1 (blockFor cs.isEmpty true 0 c.toNat)]
        rw [List.getD_append _ _ _ _ (by have hb1 := blockFor_length cs.isEmpty true 0 c.toNat; omega)]
        unfold blockFor
        rw [List.getD_append _ _ _ _ (by simp)]
        rw [List.getD_append _ _ _ _ (runFor_first_nonempty c.toNat htarget)]
        exact runFor_first_base c.toNat
      rw [hdrop]
      have hrun := block_ok cells future i out isLast (decide isFirst) target hin hi1 htarget hb
        (fun hdec => hfirst (of_decide_eq_true hdec))
      rw [← hblock] at hrun
      rw [hrun]
      have hout :
          (runInstructions (cells.set i target) future (if isLast then i else i + 1) (out ++ toString (Char.ofNat target))).2.2
            = out ++ String.ofList (c :: cs) := by
        by_cases hislast : isLast
        · have hcs0 : cs = [] := by
            unfold isLast at hislast
            exact List.isEmpty_iff.mp hislast
          have hfuture : future = [atB] := by
            unfold future
            have hblock' : block = blockFor true (decide (i = 0)) (prog.getD i 0) c.toNat := by
              unfold block isLast isFirst target
              rw [hcs0]
              simp
            have hPcs : P = (prog ++ block) ++ [atB] := by
              unfold P
              rw [hcs0]
              rw [circleProgAux]
              rw [circleProgAux]
              simp
              rw [hblock']
              rfl
            rw [hPcs]
            rw [show prog.length + block.length = (prog ++ block).length by simp]
            rw [List.drop_append_length]
          rw [hfuture]
          rw [hcs0]
          simp [runInstructions_at]
          rw [Char.ofNat_toNat]
          rw [show toString c = String.singleton c by rfl]
          rfl
        · -- non-last: pointer moves to i+1
          have hrec := ih (i + 1) (prog ++ block) (by
            intro x hx
            exact ht x (by simp [hx])) (by
              rcases hprog with h | h
              · left
                have hb1 : 1 ≤ block.length := blockFor_length isLast isFirst (prog.getD i 0) target
                have hlen : (prog ++ block).length = prog.length + block.length := by simp
                omega
              · left
                have hprog0' : prog = [] := hprog0 h
                have hb2 : 2 ≤ block.length := by
                  unfold block
                  rw [hprog0']
                  simp [blockFor, isLast, isFirst, h, target]
                  have hnon : 0 < (runFor true 0 c.toNat).length := runFor_first_nonempty c.toNat htarget
                  omega
                rw [hprog0']
                simp
                omega) (by
                rw [show circleProgAux i prog (c :: cs) = circleProgAux (i + 1) (prog ++ block) cs by rfl] at hspace
                have htlen : (c :: cs).length = 1 + cs.length := by
                  simp
                  omega
                omega) (by
                intro hzero
                omega) (by
                intro j hj
                by_cases hjl : j < prog.length
                · rw [List.getD_append _ _ _ _ hjl]
                  exact hbytes j hjl
                · have hjl2 : prog.length ≤ j := by omega
                  rw [List.getD_append_right _ _ _ _ hjl2]
                  rw [List.length_append] at hj
                  have hlb : j - prog.length < block.length := by omega
                  exact blockFor_bytes_ok isLast isFirst (prog.getD i 0) target (j - prog.length) hlb)
            (cells.set i target) (out ++ toString (Char.ofNat target))
            (by
              intro j hj hjP
              have hne : j ≠ i := by omega
              rw [show (cells.set i target).getD j 0 = cells.getD j 0 by
                rw [List.getD_eq_getElem?_getD, List.getD_eq_getElem?_getD]
                rw [List.getElem?_set']
                simp [hne.symm]]
              exact hcellP j (by omega) hjP)
            (by
              simp [hlenc]
              rw [← hP])
          -- hrec : runInstructions (cells.set i target) (drop (prog++block).length P) (i+1) out' = out' ++ String.ofList cs
          -- future = drop (prog++block).length P
          have hfuture : future = (circleProgAux (i + 1) (prog ++ block) cs).drop (prog.length + block.length) := by
            unfold future P
            rw [show circleProgAux i prog (c :: cs) = circleProgAux (i + 1) (prog ++ block) cs by rfl]
          rw [show (if isLast then i else i + 1) = i + 1 by simp [hislast]]
          rw [hfuture]
          rw [show (prog.length + block.length) = (prog ++ block).length by simp]
          rw [hrec]
          rw [Char.ofNat_toNat]
          simp [String.ofList_cons, String.append_assoc]
          rfl
      exact hout

/-- **Correctness.**  For every byte-range text the generated CircleFuck program
prints exactly that text. -/
theorem circle_correct (t : List Char) (ht : ∀ c ∈ t, c.toNat < 256) :
    (runInstructions (circleProg t) (circleProg t) 0 "").2.2 = String.ofList t := by
  unfold circleProg
  have h := circle_aux t 0 [] ht (by simp) (by
    have hlen := circleProgAux_length t 0 []
    omega) (by
    intro hz
    rfl) (by
    intro j hj
    simp at hj)
  -- apply with cells = circleProgAux 0 [] t, hcells, hlenc
  have hcells : ∀ j, 0 ≤ j → j < (circleProgAux 0 [] t).length →
      (circleProgAux 0 [] t).getD j 0 = (circleProgAux 0 [] t).getD j 0 := by
    intro j hj hjP
    rfl
  have hlenc : (circleProgAux 0 [] t).length = (circleProgAux 0 [] t).length := rfl
  have hresult := h (circleProgAux 0 [] t) "" hcells hlenc
  simpa using hresult
end CircleFuckCorrect
