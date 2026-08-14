import Mathlib

/-! Correctness of the brainfuck minterm boolean generator

The boolean generator ``src/esolangs/tools/booleans/tape.py::_bf_minterm``
emits, for a truth table, a brainfuck program that reads the ``n`` input
bits, computes the sum of the table's one-rows' minterms (each minterm is
the product of the input bits or their complements selecting that row), and
prints ``48 + sum`` as ``'0'``/``'1'``.  Brainfuck has no branching that
would let a leaf skip its sibling, so the generator uses the branch-free sum
of minterms.  The model here extends the ``BfSetCorrect`` tape with an
``,`` input command and an input list, and proves the copy / complement /
AND / add scratch machinery and the minterm construction: after reading the
bits of a combination ``combo``, the program prints the character for the
table's value at ``combo``.
-/

namespace BfMintermCorrect

/-! ### 1. Model -/

/-- Brainfuck commands, with ``,`` reading the next input byte. -/
inductive Cmd where
  | plus | minus | right | left | in_ | out | loop (body : List Cmd)

/-- Machine state: pointer, tape (natural-number cells), the remaining
input bytes, and the output. -/
@[ext]
structure State where
  ptr : ℕ
  tape : ℕ → ℕ
  inp : List ℕ
  out : List Char

def State.inc (s : State) : State :=
  { s with tape := Function.update s.tape s.ptr (s.tape s.ptr + 1) }

def State.dec (s : State) : State :=
  { s with tape := Function.update s.tape s.ptr (s.tape s.ptr - 1) }

def State.right (s : State) : State := { s with ptr := s.ptr + 1 }

def State.left (s : State) : State := { s with ptr := s.ptr - 1 }

/-- ``,`` reads the next input byte into the current cell. -/
def State.read (s : State) : State :=
  match s.inp with
  | [] => s
  | x :: xs => { s with inp := xs, tape := Function.update s.tape s.ptr x }

def State.emit (s : State) : State := { s with out := s.out ++ [Char.ofNat (s.tape s.ptr)] }

/-- ``[body]`` run as a while loop for at most ``n`` iterations. -/
def runLoop (step : ℕ → State → State) : ℕ → State → State
  | 0, s => s
  | k + 1, s => if s.tape s.ptr = 0 then s else runLoop step k (step (k + 1) s)

/-- Run a program from a state with a fuel bound; loops consume one unit of
fuel per iteration. -/
def run : List Cmd → ℕ → State → State
  | [], _n, s => s
  | Cmd.plus :: cs, n, s => run cs n (State.inc s)
  | Cmd.minus :: cs, n, s => run cs n (State.dec s)
  | Cmd.right :: cs, n, s => run cs n (State.right s)
  | Cmd.left :: cs, n, s => run cs n (State.left s)
  | Cmd.in_ :: cs, n, s => run cs n (State.read s)
  | Cmd.out :: cs, n, s => run cs n (State.emit s)
  | Cmd.loop body :: cs, n, s => run cs n (runLoop (fun n s => run body n s) n s)

lemma run_nil (n : ℕ) (s : State) : run [] n s = s := by
  simp [run]

lemma run_plus (cs : List Cmd) (n : ℕ) (s : State) :
    run (Cmd.plus :: cs) n s = run cs n (State.inc s) := by
  simp [run]

lemma run_minus (cs : List Cmd) (n : ℕ) (s : State) :
    run (Cmd.minus :: cs) n s = run cs n (State.dec s) := by
  simp [run]

lemma run_right (cs : List Cmd) (n : ℕ) (s : State) :
    run (Cmd.right :: cs) n s = run cs n (State.right s) := by
  simp [run]

lemma run_left (cs : List Cmd) (n : ℕ) (s : State) :
    run (Cmd.left :: cs) n s = run cs n (State.left s) := by
  simp [run]

lemma run_in (cs : List Cmd) (n : ℕ) (s : State) :
    run (Cmd.in_ :: cs) n s = run cs n (State.read s) := by
  simp [run]

lemma run_out (cs : List Cmd) (n : ℕ) (s : State) :
    run (Cmd.out :: cs) n s = run cs n (State.emit s) := by
  simp [run]

lemma run_loop (body cs : List Cmd) (n : ℕ) (s : State) :
    run (Cmd.loop body :: cs) n s = run cs n (runLoop (fun n s => run body n s) n s) := by
  simp [run]

lemma run_append (p q : List Cmd) (n : ℕ) (s : State) :
    run (p ++ q) n s = run q n (run p n s) := by
  induction p generalizing n s with
  | nil => simp [run_nil]
  | cons c p ih =>
      cases c <;> simp [run_plus, run_minus, run_right, run_left, run_in, run_out, run_loop, ih]

/-- ``+`` repeated ``a`` times adds ``a`` to the current cell. -/
lemma run_plusN (a k : ℕ) (s : State) :
    run (List.replicate a Cmd.plus) k s
      = { s with tape := Function.update s.tape s.ptr (s.tape s.ptr + a) } := by
  induction a generalizing k s with
  | zero => simp [run]
  | succ a ih =>
      rw [List.replicate_succ]
      rw [run_plus]
      rw [ih k (State.inc s)]
      apply State.ext
      · rfl
      · ext i <;> by_cases h : i = s.ptr
        · subst i
          simp [State.inc, Function.update]
          omega
        · simp [State.inc, Function.update, h]
      · rfl
      · rfl

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
      · rfl

lemma runLoop_exit (step : ℕ → State → State) (k : ℕ) (s : State) (hz : s.tape s.ptr = 0) :
    runLoop step (k + 1) s = s := by
  simp [runLoop, hz]

lemma runLoop_step (step : ℕ → State → State) (k : ℕ) (s : State) (hnz : s.tape s.ptr ≠ 0) :
    runLoop step (k + 1) s = runLoop step k (step (k + 1) s) := by
  simp [runLoop, hnz]

/-- ``>`` repeated ``a`` times moves the pointer ``a`` cells right. -/
lemma run_rightN (a k : ℕ) (s : State) :
    run (List.replicate a Cmd.right) k s = { s with ptr := s.ptr + a } := by
  induction a generalizing s with
  | zero => simp [run]
  | succ a ih =>
      rw [List.replicate_succ]
      rw [run_right]
      rw [ih (State.right s)]
      apply State.ext
      · simp [State.right]
        omega
      · rfl
      · rfl
      · rfl

/-- ``<`` repeated ``a`` times moves the pointer ``a`` cells left. -/
lemma run_leftN (a k : ℕ) (s : State) (ha : a ≤ s.ptr) :
    run (List.replicate a Cmd.left) k s = { s with ptr := s.ptr - a } := by
  induction a generalizing s with
  | zero => simp [run]
  | succ a ih =>
      rw [List.replicate_succ]
      rw [run_left]
      have ha' : a ≤ (State.left s).ptr := by
        simp [State.left]
        omega
      rw [ih (State.left s) ha']
      apply State.ext
      · simp [State.left]
        rw [Nat.sub_sub]
        omega
      · rfl
      · rfl
      · rfl

/-- ``>``/``<`` runs moving the pointer from ``f`` to ``t``. -/
def move (f t : ℕ) : List Cmd :=
  if t ≥ f then List.replicate (t - f) Cmd.right else List.replicate (f - t) Cmd.left

lemma run_move (f t k : ℕ) (s : State) (hptr : s.ptr = f) :
    run (move f t) k s = { s with ptr := t } := by
  unfold move
  by_cases h : t ≥ f
  · rw [if_pos h]
    rw [run_rightN (t - f) k s]
    apply State.ext
    · change s.ptr + (t - f) = t
      omega
    · rfl
    · rfl
    · rfl
  · rw [if_neg h]
    have hlt : t < f := by omega
    rw [run_leftN (f - t) k s (by omega)]
    apply State.ext
    · change s.ptr - (f - t) = t
      omega
    · rfl
    · rfl
    · rfl

/-! ### 2. The scratch macros -/

/-- ``[-]`` zeroing the cell ``c`` (pointer home at 0). -/
def zeroCell (c : ℕ) : List Cmd := move 0 c ++ [Cmd.loop [Cmd.minus]] ++ move c 0

/-- ``+`` repeated ``a`` times at cell ``c`` (pointer home at 0). -/
def plusN (c : ℕ) (a : ℕ) : List Cmd := move 0 c ++ List.replicate a Cmd.plus ++ move c 0

/-- Copy ``src`` to ``dst`` (``dst += src``), preserving ``src``, using the
two scratch cells ``a``, ``b``.  The pointer starts and ends at 0. -/
def copy (src dst a b : ℕ) : List Cmd :=
  move 0 a ++ [Cmd.loop [Cmd.minus]] ++
  move a b ++ [Cmd.loop [Cmd.minus]] ++
  move b src ++
  [Cmd.loop (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus])] ++
  move src a ++ [Cmd.loop (move a src ++ [Cmd.plus] ++ move src a ++ [Cmd.minus])] ++
  move a b ++ [Cmd.loop (move b dst ++ [Cmd.plus] ++ move dst b ++ [Cmd.minus])] ++
  move b 0

/-- Complement: ``dst = 1 - src`` for ``src : ℕ`` with ``src = 0 ∨ src = 1``,
preserving ``src``, using ``tmp`` and the copy scratch cells ``a``, ``b``.
The pointer starts and ends at 0. -/
def complement (src dst tmp a b : ℕ) : List Cmd :=
  move 0 dst ++ [Cmd.loop [Cmd.minus]] ++ [Cmd.plus] ++ move dst 0 ++
  copy src tmp a b ++
  move 0 tmp ++ [Cmd.loop (move tmp dst ++ [Cmd.minus] ++ move dst tmp ++ [Cmd.minus])] ++
  move tmp 0

/-- AND: ``dst = a AND b`` for ``a, b : ℕ`` with ``a = 0 ∨ a = 1`` and
``b = 0 ∨ b = 1``, preserving ``a`` and ``b``, using the copy scratch pairs
``(c1, d1)``, ``(c2, d2)`` and the loop scratch ``t1``, ``t2``.  The pointer
starts and ends at 0. -/
def and_ (a b dst t1 t2 c1 d1 c2 d2 : ℕ) : List Cmd :=
  move 0 dst ++ [Cmd.loop [Cmd.minus]] ++ move dst 0 ++
  copy a t1 c1 d1 ++
  copy b t2 c2 d2 ++
  move 0 t1 ++
  [Cmd.loop (move t1 t2 ++
    [Cmd.loop (move t2 dst ++ [Cmd.plus] ++ move dst t2 ++ [Cmd.minus])] ++
    move t2 t1 ++ [Cmd.minus])] ++
  move t1 0

/-- Add: ``sum += src``, preserving ``src``, using ``tmp`` and the copy
scratch ``a``, ``b``.  The pointer starts and ends at 0. -/
def add (src sum tmp a b : ℕ) : List Cmd :=
  copy src tmp a b ++
  move 0 tmp ++ [Cmd.loop (move tmp sum ++ [Cmd.plus] ++ move sum tmp ++ [Cmd.minus])] ++
  move tmp 0

/-- A whole-cell zero loop lemma: ``[ - ]`` at a cell zeroes it. -/
lemma zeroLoop_at (cur k : ℕ) (s : State) (hcur : s.tape s.ptr = cur) (hk : cur ≤ k) :
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
          · rfl
      | succ k =>
          rw [runLoop_exit (fun n s => run [Cmd.minus] n s) k s (by simp [hcur])]
          apply State.ext
          · rfl
          · ext i <;> by_cases h : i = s.ptr
            · subst i; simp [hcur]
            · simp [h]
          · rfl
          · rfl
  | succ cur ih =>
      cases k with
      | zero => omega
      | succ k =>
          have hnz : s.tape s.ptr ≠ 0 := by simp [hcur]
          rw [runLoop_step (fun n s => run [Cmd.minus] n s) k s hnz]
          rw [run_minus]
          rw [run_nil]
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
          · rfl

/-! ### 3. The copy loops -/

/-- One iteration of ``[>tgt+ >cur-]``: cell ``cur`` drops by one and cell
``tgt`` gains one. -/
lemma run_body_move (cur tgt n : ℕ) (s : State) (hptr : s.ptr = cur) (hne : tgt ≠ cur) :
    run (move cur tgt ++ [Cmd.plus] ++ move tgt cur ++ [Cmd.minus]) n s
      = { s with
          ptr := cur,
          tape := Function.update (Function.update s.tape tgt (s.tape tgt + 1)) cur (s.tape cur - 1) } := by
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_move cur tgt n s hptr]
  rw [run_plus]
  rw [run_nil]
  have hmove := run_move tgt cur n ({ s with ptr := tgt }).inc (by simp [State.inc])
  rw [hmove]
  rw [run_minus]
  rw [run_nil]
  apply State.ext
  · simp [State.inc, State.dec, hptr]
  · ext i
    by_cases h0 : i = cur
    · by_cases h1 : i = tgt
      · omega
      · subst i
        have hc : ¬ cur = tgt := by exact fun h => hne h.symm
        simp [State.inc, State.dec, Function.update, hptr, hc]
    · by_cases h1 : i = tgt
      · subst i
        have hc : ¬ cur = tgt := by exact fun h => hne h.symm
        simp [State.inc, State.dec, Function.update, hptr, hc]
      · simp [State.inc, State.dec, Function.update, h0, h1, hptr, hne]
  · rfl
  · rfl

/-- **Copy loop.**  ``[>tgt+ >cur-]`` moves the value ``v`` of cell ``cur``
into ``tgt`` (zeroing ``cur``), provided there is fuel for ``v`` iterations. -/
lemma runLoop_move (cur tgt k v w : ℕ) (s : State) (hv : s.tape cur = v) (hw : s.tape tgt = w)
    (hs : v ≤ k) (hptr : s.ptr = cur) (hne : tgt ≠ cur) :
    runLoop (fun n s => run (move cur tgt ++ [Cmd.plus] ++ move tgt cur ++ [Cmd.minus]) n s) k s
      = { ptr := cur, tape := fun i => if i = cur then 0 else if i = tgt then w + v else s.tape i,
          inp := s.inp, out := s.out } := by
  induction v generalizing s k w with
  | zero =>
      have hcur : s.tape cur = 0 := by simpa [hv]
      cases k with
      | zero =>
          simp [runLoop]
          apply State.ext
          · simp [hptr]
          · ext i
            by_cases h : i = cur
            · subst i
              simp [hcur, hv]
            · by_cases h' : i = tgt
              · subst i
                simp [hw, hne]
              · simp [h, h']
          · rfl
          · rfl
      | succ k =>
          rw [runLoop_exit (fun n s => run (move cur tgt ++ [Cmd.plus] ++ move tgt cur ++ [Cmd.minus]) n s) k s (by simp [hcur, hptr])]
          apply State.ext
          · simp [hptr]
          · ext i
            by_cases h : i = cur
            · subst i
              simp [hcur, hv]
            · by_cases h' : i = tgt
              · subst i
                simp [hw, hne]
              · simp [h, h']
          · rfl
          · rfl
  | succ v ih =>
      cases k with
      | zero => omega
      | succ k =>
          have hnz : s.tape s.ptr ≠ 0 := by simp [hptr, hv]
          rw [runLoop_step (fun n s => run (move cur tgt ++ [Cmd.plus] ++ move tgt cur ++ [Cmd.minus]) n s) k s hnz]
          have hs' := run_body_move cur tgt (k + 1) s hptr hne
          have hcur' : (run (move cur tgt ++ [Cmd.plus] ++ move tgt cur ++ [Cmd.minus]) (k + 1) s).tape cur = v := by
            rw [hs']
            simp [hv]
          have htgt' : (run (move cur tgt ++ [Cmd.plus] ++ move tgt cur ++ [Cmd.minus]) (k + 1) s).tape tgt = w + 1 := by
            rw [hs']
            simp [hw, hne]
          have hptr' : (run (move cur tgt ++ [Cmd.plus] ++ move tgt cur ++ [Cmd.minus]) (k + 1) s).ptr = cur := by
            rw [hs']
          have hv' : v ≤ k := by omega
          rw [ih k (w + 1) (run (move cur tgt ++ [Cmd.plus] ++ move tgt cur ++ [Cmd.minus]) (k + 1) s) hcur' htgt' hv' hptr']
          apply State.ext
          · rfl
          · ext i <;> by_cases h0 : i = cur <;> by_cases h1 : i = tgt
            · omega
            · subst i
              simp
            · subst i
              simp [hne]
              omega
            · rw [hs']
              simp [h0, h1]
          · rw [hs']
          · rw [hs']

/-- One iteration of ``[>a+ >b+ >src-]``: cell ``src`` drops by one and cells
``a`` and ``b`` gain one. -/
lemma run_body_spread (src a b n : ℕ) (s : State) (hptr : s.ptr = src)
    (hna : a ≠ src) (hnb : b ≠ src) (hnab : a ≠ b) :
    run (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus]) n s
      = { s with
          ptr := src,
          tape := Function.update (Function.update (Function.update s.tape a (s.tape a + 1)) b (s.tape b + 1)) src (s.tape src - 1) } := by
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_move src a n s hptr]
  have hp1 : run [Cmd.plus] n ({ s with ptr := a }) = ({ s with ptr := a }).inc := by
    rw [run_plus, run_nil]
  rw [hp1]
  have hmove1 := run_move a b n ({ s with ptr := a }).inc (by simp [State.inc])
  rw [hmove1]
  have hp2 : run [Cmd.plus] n ({ { s with ptr := a }.inc with ptr := b })
      = ({ { s with ptr := a }.inc with ptr := b }).inc := by
    rw [run_plus, run_nil]
  rw [hp2]
  have hmove2 := run_move b src n ({ { s with ptr := a }.inc with ptr := b }).inc (by simp [State.inc])
  rw [hmove2]
  rw [run_minus]
  rw [run_nil]
  apply State.ext
  · simp [State.inc, State.dec, hptr]
  · ext i
    by_cases h0 : i = src
    · by_cases h1 : i = a
      · omega
      · by_cases h2 : i = b
        · omega
        · subst i
          have hc1 : ¬ src = a := by exact fun h => hna h.symm
          have hc2 : ¬ src = b := by exact fun h => hnb h.symm
          simp [State.inc, State.dec, Function.update, hptr, hc1, hc2]
    · by_cases h1 : i = a
      · by_cases h2 : i = b
        · omega
        · subst i
          have hc1 : ¬ a = src := by exact fun h => hna h
          have hc2 : ¬ a = b := by exact fun h => hnab h
          simp [State.inc, State.dec, Function.update, hptr, hc1, hc2]
      · by_cases h2 : i = b
        · subst i
          have hc1 : ¬ b = src := by exact fun h => hnb h
          have hc2 : ¬ b = a := by exact fun h => hnab h.symm
          simp [State.inc, State.dec, Function.update, hptr, hc1, hc2]
        · simp [State.inc, State.dec, Function.update, h0, h1, h2, hptr, hna, hnb, hnab]
  · rfl
  · rfl

/-- **Spread loop.**  ``[>a+ >b+ >src-]`` copies the value ``v`` of cell
``src`` into both ``a`` and ``b`` (zeroing ``src``). -/
lemma runLoop_spread (src a b k v wa wb : ℕ) (s : State) (hv : s.tape src = v)
    (hwa : s.tape a = wa) (hwb : s.tape b = wb) (hs : v ≤ k) (hptr : s.ptr = src)
    (hna : a ≠ src) (hnb : b ≠ src) (hnab : a ≠ b) :
    runLoop (fun n s => run (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus]) n s) k s
      = { ptr := src,
          tape := fun i => if i = src then 0 else if i = a then wa + v else if i = b then wb + v else s.tape i,
          inp := s.inp, out := s.out } := by
  induction v generalizing s k wa wb with
  | zero =>
      have hcur : s.tape src = 0 := by simpa [hv]
      cases k with
      | zero =>
          simp [runLoop]
          apply State.ext
          · simp [hptr]
          · ext i
            by_cases h0 : i = src
            · subst i
              simp [hcur, hv]
            · by_cases h1 : i = a
              · subst i
                simp [hwa, hna, hnb, hnab.symm]
              · by_cases h2 : i = b
                · subst i
                  simp [hwb, hnb, hnab.symm, hna]
                · simp [h0, h1, h2]
          · rfl
          · rfl
      | succ k =>
          rw [runLoop_exit (fun n s => run (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus]) n s) k s (by simp [hcur, hptr])]
          apply State.ext
          · simp [hptr]
          · ext i
            by_cases h0 : i = src
            · subst i
              simp [hcur, hv]
            · by_cases h1 : i = a
              · subst i
                simp [hwa, hna, hnb, hnab.symm]
              · by_cases h2 : i = b
                · subst i
                  simp [hwb, hnb, hnab.symm, hna]
                · simp [h0, h1, h2]
          · rfl
          · rfl
  | succ v ih =>
      cases k with
      | zero => omega
      | succ k =>
          have hnz : s.tape s.ptr ≠ 0 := by simp [hptr, hv]
          rw [runLoop_step (fun n s => run (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus]) n s) k s hnz]
          have hs' := run_body_spread src a b (k + 1) s hptr hna hnb hnab
          have hcur' : (run (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus]) (k + 1) s).tape src = v := by
            rw [hs']
            simp [hv]
          have ha' : (run (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus]) (k + 1) s).tape a = wa + 1 := by
            rw [hs']
            simp [hwa, hna, hnab]
          have hb' : (run (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus]) (k + 1) s).tape b = wb + 1 := by
            rw [hs']
            simp [hwb, hnb, hnab]
          have hptr' : (run (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus]) (k + 1) s).ptr = src := by
            rw [hs']
          have hv' : v ≤ k := by omega
          rw [ih k (wa + 1) (wb + 1) (run (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus]) (k + 1) s) hcur' ha' hb' hv' hptr']
          apply State.ext
          · rfl
          · ext i
            by_cases h0 : i = src
            · by_cases h1 : i = a
              · omega
              · by_cases h2 : i = b
                · omega
                · subst i
                  simp [hna, hnb]
            · by_cases h1 : i = a
              · by_cases h2 : i = b
                · omega
                · subst i
                  simp [hna, hnab.symm]
                  omega
              · by_cases h2 : i = b
                · subst i
                  simp [hnb, hnab.symm]
                  omega
                · rw [hs']
                  simp [h0, h1, h2]
          · rw [hs']
          · rw [hs']

/-! ### 4. The macros -/

/-- ``[-]`` at the current cell zeroes it. -/
lemma run_zero_here (k : ℕ) (s : State) (hk : s.tape s.ptr ≤ k) :
    run [Cmd.loop [Cmd.minus]] k s = { s with tape := Function.update s.tape s.ptr 0 } := by
  rw [run_loop, run_nil]
  exact zeroLoop_at (s.tape s.ptr) k s (by rfl) hk

/-- **The ``zeroCell`` macro.** -/
lemma run_zeroCell (c k : ℕ) (s : State) (hptr : s.ptr = 0) (hc : s.tape c ≤ k) :
    run (zeroCell c) k s = { s with tape := Function.update s.tape c 0, ptr := 0 } := by
  unfold zeroCell
  rw [run_append]
  rw [run_append]
  rw [run_move 0 c k s hptr]
  have hz := run_zero_here k { s with ptr := c } (by simp [hc])
  rw [hz]
  have hm := run_move c 0 k { s with ptr := c, tape := Function.update s.tape c 0 } (by simp)
  rw [hm]

/-- **The ``plusN`` macro.** -/
lemma run_plusN_at (c a k : ℕ) (s : State) (hptr : s.ptr = 0) :
    run (plusN c a) k s = { s with tape := Function.update s.tape c (s.tape c + a), ptr := 0 } := by
  unfold plusN
  rw [run_append]
  rw [run_append]
  rw [run_move 0 c k s hptr]
  rw [run_plusN]
  have hm := run_move c 0 k { s with ptr := c, tape := Function.update s.tape c (s.tape c + a) } (by simp)
  rw [hm]

/-- **The ``copy`` macro.**  ``dst += src``, ``src`` preserved, the scratch
cells ``a`` and ``b`` zeroed, pointer home at 0. -/
lemma run_copy (src dst a b k : ℕ) (s : State) (hptr : s.ptr = 0)
    (hsrc : s.tape src ≤ k) (ha : s.tape a = 0) (hb : s.tape b = 0)
    (hna : a ≠ src) (hnb : b ≠ src) (hnab : a ≠ b)
    (hdst : dst ≠ src) (hdstA : dst ≠ a) (hdstB : dst ≠ b) :
    run (copy src dst a b) k s
      = { ptr := 0,
          tape := fun i => if i = a then 0 else if i = b then 0 else if i = dst then s.tape dst + s.tape src else s.tape i,
          inp := s.inp, out := s.out } := by
  let t5 : ℕ → ℕ := fun i => if i = src then 0 else if i = a then 0 + s.tape src else if i = b then 0 + s.tape src else (Function.update (Function.update s.tape a 0) b 0) i
  let S5 : State := { ptr := src, tape := t5, inp := s.inp, out := s.out }
  let S6 : State := { ptr := a, tape := S5.tape, inp := s.inp, out := s.out }
  let t7 : ℕ → ℕ := fun i => if i = a then 0 else if i = src then S6.tape src + S6.tape a else S6.tape i
  let S7 : State := { ptr := a, tape := t7, inp := s.inp, out := s.out }
  let S8 : State := { ptr := b, tape := S7.tape, inp := s.inp, out := s.out }
  let t9 : ℕ → ℕ := fun i => if i = b then 0 else if i = dst then S8.tape dst + S8.tape b else S8.tape i
  let S9 : State := { ptr := b, tape := t9, inp := s.inp, out := s.out }
  let S10 : State := { ptr := 0, tape := S9.tape, inp := s.inp, out := s.out }
  let tF : ℕ → ℕ := fun i => if i = a then 0 else if i = b then 0 else if i = dst then s.tape dst + s.tape src else s.tape i
  unfold copy
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_move 0 a k s hptr]
  have hz1 : run [Cmd.loop [Cmd.minus]] k { s with ptr := a } = { s with ptr := a, tape := Function.update s.tape a 0 } := by
    apply run_zero_here
    simp [ha]
  rw [hz1]
  have hm1 := run_move a b k { s with ptr := a, tape := Function.update s.tape a 0 } (by simp)
  rw [hm1]
  have hz2 : run [Cmd.loop [Cmd.minus]] k { s with ptr := b, tape := Function.update s.tape a 0 }
      = { s with ptr := b, tape := Function.update (Function.update s.tape a 0) b 0 } := by
    apply run_zero_here
    simp [ha, hb, hnab.symm]
  rw [hz2]
  have hm2 := run_move b src k { s with ptr := b, tape := Function.update (Function.update s.tape a 0) b 0 } (by simp)
  rw [hm2]
  have hspread := runLoop_spread src a b k (s.tape src) 0 0
    { s with ptr := src, tape := Function.update (Function.update s.tape a 0) b 0 }
    (by simp [hna.symm, hnb.symm]) (by simp [ha, hnab]) (by simp [hb]) hsrc (by simp) hna hnb hnab
  have hloop1 : run [Cmd.loop (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus])] k
      { s with ptr := src, tape := Function.update (Function.update s.tape a 0) b 0 }
      = runLoop (fun n s => run (move src a ++ [Cmd.plus] ++ move a b ++ [Cmd.plus] ++ move b src ++ [Cmd.minus]) n s) k
      { s with ptr := src, tape := Function.update (Function.update s.tape a 0) b 0 } := by
    rw [run_loop, run_nil]
  rw [hloop1]
  rw [hspread]
  change run (move b 0) k (run [Cmd.loop (move b dst ++ [Cmd.plus] ++ move dst b ++ [Cmd.minus])] k
      (run (move a b) k (run [Cmd.loop (move a src ++ [Cmd.plus] ++ move src a ++ [Cmd.minus])] k
      (run (move src a) k S5)))) = { ptr := 0, tape := tF, inp := s.inp, out := s.out }
  have hm3 := run_move src a k S5 (by simp [S5])
  rw [hm3]
  have hloop2 : run [Cmd.loop (move a src ++ [Cmd.plus] ++ move src a ++ [Cmd.minus])] k { S5 with ptr := a }
      = runLoop (fun n s => run (move a src ++ [Cmd.plus] ++ move src a ++ [Cmd.minus]) n s) k { S5 with ptr := a } := by
    rw [run_loop, run_nil]
  rw [hloop2]
  have hmoveback := runLoop_move a src k (S5.tape a) (S5.tape src) { S5 with ptr := a }
    (by simp [S5, t5, hna]) (by simp [S5, t5]) (by simp [S5, t5, hsrc, hna]) (by simp [S5]) hna.symm
  rw [hmoveback]
  have hm4 := run_move a b k S7 (by simp [S7])
  rw [hm4]
  have hloop3 : run [Cmd.loop (move b dst ++ [Cmd.plus] ++ move dst b ++ [Cmd.minus])] k { S7 with ptr := b }
      = runLoop (fun n s => run (move b dst ++ [Cmd.plus] ++ move dst b ++ [Cmd.minus]) n s) k { S7 with ptr := b } := by
    rw [run_loop, run_nil]
  rw [hloop3]
  have hmoveback2 := runLoop_move b dst k (S8.tape b) (S8.tape dst) { S7 with ptr := b }
    (by simp [S8, S7, S6, S5, t5, t7, hna, hnb]) (by simp [S8, S7, S6, S5, t5, t7, hdst, hdstA, hdstB])
    (by simp [S8, S7, S6, S5, t5, t7, hsrc, hna, hnb, hnab.symm]) (by simp [S8]) hdstB
  rw [hmoveback2]
  have hm5 := run_move b 0 k { S8 with tape := S9.tape } (by simp [S8])
  rw [hm5]
  apply State.ext
  · rfl
  · ext i
    by_cases h0 : i = a
    · subst i
      change t9 a = tF a
      simp [S9, S8, S7, S6, S5, t5, t7, t9, tF, hna, hna.symm, hnb, hnb.symm, hnab, hnab.symm, hdst, hdst.symm, hdstA, hdstA.symm, hdstB, hdstB.symm]
    · by_cases h1 : i = b
      · subst i
        change t9 b = tF b
        simp [S9, S8, S7, S6, S5, t5, t7, t9, tF, hna, hna.symm, hnb, hnb.symm, hnab, hnab.symm, hdst, hdst.symm, hdstA, hdstA.symm, hdstB, hdstB.symm]
      · by_cases h2 : i = dst
        · subst i
          change t9 dst = tF dst
          simp [S9, S8, S7, S6, S5, t5, t7, t9, tF, hna, hna.symm, hnb, hnb.symm, hnab, hnab.symm, hdst, hdst.symm, hdstA, hdstA.symm, hdstB, hdstB.symm]
        · by_cases h3 : i = src
          · subst i
            change t9 src = tF src
            simp [S9, S8, S7, S6, S5, t5, t7, t9, tF, hna, hna.symm, hnb, hnb.symm, hnab, hnab.symm, hdst, hdst.symm, hdstA, hdstA.symm, hdstB, hdstB.symm]
          · change t9 i = tF i
            simp [S9, S8, S7, S6, S5, t5, t7, t9, tF, h0, h1, h2, h3, hna, hna.symm, hnb, hnb.symm, hnab, hnab.symm, hdst, hdst.symm, hdstA, hdstA.symm, hdstB, hdstB.symm]
  · rfl
  · rfl


/-- One iteration of ``[>tgt- >cur-]``: cells ``cur`` and ``tgt`` both drop
by one. -/
lemma run_body_sub (cur tgt n : ℕ) (s : State) (hptr : s.ptr = cur) (hne : tgt ≠ cur) :
    run (move cur tgt ++ [Cmd.minus] ++ move tgt cur ++ [Cmd.minus]) n s
      = { s with
          ptr := cur,
          tape := Function.update (Function.update s.tape tgt (s.tape tgt - 1)) cur (s.tape cur - 1) } := by
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_move cur tgt n s hptr]
  have hm0 : run [Cmd.minus] n ({ s with ptr := tgt }) = ({ s with ptr := tgt }).dec := by
    rw [run_minus, run_nil]
  rw [hm0]
  have hm := run_move tgt cur n ({ s with ptr := tgt }).dec (by simp [State.dec])
  rw [hm]
  have hm2 : run [Cmd.minus] n ({ ({ s with ptr := tgt }).dec with ptr := cur }) = ({ ({ s with ptr := tgt }).dec with ptr := cur }).dec := by
    rw [run_minus, run_nil]
  rw [hm2]
  apply State.ext
  · simp [State.dec, hptr]
  · ext i
    by_cases h0 : i = cur
    · by_cases h1 : i = tgt
      · omega
      · subst i
        have hc : ¬ cur = tgt := by exact fun h => hne h.symm
        simp [State.dec, Function.update, hptr, hc]
    · by_cases h1 : i = tgt
      · subst i
        have hc : ¬ cur = tgt := by exact fun h => hne h.symm
        simp [State.dec, Function.update, hptr, hc]
      · simp [State.dec, Function.update, h0, h1, hptr, hne]
  · rfl
  · rfl

/-- **Subtract loop.**  ``[>tgt- >cur-]`` subtracts the value ``v`` of cell
``cur`` from ``tgt`` (zeroing ``cur``). -/
lemma runLoop_sub (cur tgt k v w : ℕ) (s : State) (hv : s.tape cur = v) (hw : s.tape tgt = w)
    (hs : v ≤ k) (hptr : s.ptr = cur) (hne : tgt ≠ cur) :
    runLoop (fun n s => run (move cur tgt ++ [Cmd.minus] ++ move tgt cur ++ [Cmd.minus]) n s) k s
      = { ptr := cur, tape := fun i => if i = cur then 0 else if i = tgt then w - v else s.tape i,
          inp := s.inp, out := s.out } := by
  induction v generalizing s k w with
  | zero =>
      have hcur : s.tape cur = 0 := by simpa [hv]
      cases k with
      | zero =>
          simp [runLoop]
          apply State.ext
          · simp [hptr]
          · ext i
            by_cases h : i = cur
            · subst i
              simp [hcur, hv]
            · by_cases h' : i = tgt
              · subst i
                simp [hw, hne]
              · simp [h, h']
          · rfl
          · rfl
      | succ k =>
          rw [runLoop_exit (fun n s => run (move cur tgt ++ [Cmd.minus] ++ move tgt cur ++ [Cmd.minus]) n s) k s (by simp [hcur, hptr])]
          apply State.ext
          · simp [hptr]
          · ext i
            by_cases h : i = cur
            · subst i
              simp [hcur, hv]
            · by_cases h' : i = tgt
              · subst i
                simp [hw, hne]
              · simp [h, h']
          · rfl
          · rfl
  | succ v ih =>
      cases k with
      | zero => omega
      | succ k =>
          have hnz : s.tape s.ptr ≠ 0 := by simp [hptr, hv]
          rw [runLoop_step (fun n s => run (move cur tgt ++ [Cmd.minus] ++ move tgt cur ++ [Cmd.minus]) n s) k s hnz]
          have hs' := run_body_sub cur tgt (k + 1) s hptr hne
          have hcur' : (run (move cur tgt ++ [Cmd.minus] ++ move tgt cur ++ [Cmd.minus]) (k + 1) s).tape cur = v := by
            rw [hs']
            simp [hv]
          have htgt' : (run (move cur tgt ++ [Cmd.minus] ++ move tgt cur ++ [Cmd.minus]) (k + 1) s).tape tgt = w - 1 := by
            rw [hs']
            simp [hw, hne]
          have hptr' : (run (move cur tgt ++ [Cmd.minus] ++ move tgt cur ++ [Cmd.minus]) (k + 1) s).ptr = cur := by
            rw [hs']
          have hv' : v ≤ k := by omega
          rw [ih k (w - 1) (run (move cur tgt ++ [Cmd.minus] ++ move tgt cur ++ [Cmd.minus]) (k + 1) s) hcur' htgt' hv' hptr']
          apply State.ext
          · rfl
          · ext i <;> by_cases h0 : i = cur <;> by_cases h1 : i = tgt
            · omega
            · subst i
              simp
            · subst i
              simp [hne]
              omega
            · rw [hs']
              simp [h0, h1]
          · rw [hs']
          · rw [hs']

/-- **The ``complement`` macro.**  ``dst = 1 - src`` for ``src : ℕ`` with
``src = 0 ∨ src = 1``; ``src`` preserved, scratch zeroed, pointer home. -/
lemma run_complement (src dst tmp a b k : ℕ) (s : State) (hptr : s.ptr = 0)
    (hsrc1 : s.tape src ≤ 1) (hsrc : s.tape src ≤ k) (ha : s.tape a = 0) (hb : s.tape b = 0)
    (hdst0 : s.tape dst = 0) (htmp0 : s.tape tmp = 0)
    (hna : a ≠ src) (hnb : b ≠ src) (hnab : a ≠ b)
    (hst : src ≠ tmp) (hdt : dst ≠ tmp) (hdst2 : dst ≠ src)
    (hdstA : dst ≠ a) (hdstB : dst ≠ b) (htA : tmp ≠ a) (htB : tmp ≠ b) :
    run (complement src dst tmp a b) k s
      = { ptr := 0, tape := fun i => if i = dst then 1 - s.tape src else s.tape i,
          inp := s.inp, out := s.out } := by
  unfold complement
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_move 0 dst k s hptr]
  have hz := run_zero_here k { s with ptr := dst } (by simp [hdst0])
  rw [hz]
  rw [run_plus]
  rw [run_nil]
  have hmv := run_move dst 0 k ({ s with ptr := dst, tape := Function.update s.tape dst 0 }).inc (by simp [State.inc])
  rw [hmv]
  let Sd : State := { ({ s with ptr := dst, tape := Function.update s.tape dst 0 }).inc with ptr := 0 }
  have hcopy := run_copy src tmp a b k Sd
    (by simp [Sd]) (by simp [Sd, State.inc, hdst2, hdst2.symm, hsrc]) (by simp [Sd, State.inc, ha, hdstA, hdstA.symm])
    (by simp [Sd, State.inc, hb, hdstB, hdstB.symm]) hna hnb hnab hst.symm htA htB
  rw [hcopy]
  have hm0 := run_move 0 tmp k { ptr := 0, tape := fun i => if i = a then 0 else if i = b then 0 else if i = tmp then Sd.tape tmp + Sd.tape src else Sd.tape i, inp := Sd.inp, out := Sd.out } (by simp [Sd])
  rw [hm0]
  let St : ℕ → ℕ := fun i => if i = a then 0 else if i = b then 0 else if i = tmp then Sd.tape tmp + Sd.tape src else Sd.tape i
  have hloop4 : run [Cmd.loop (move tmp dst ++ [Cmd.minus] ++ move dst tmp ++ [Cmd.minus])] k
      { ptr := tmp, tape := St, inp := Sd.inp, out := Sd.out }
      = runLoop (fun n s => run (move tmp dst ++ [Cmd.minus] ++ move dst tmp ++ [Cmd.minus]) n s) k
      { ptr := tmp, tape := St, inp := Sd.inp, out := Sd.out } := by
    rw [run_loop, run_nil]
  rw [hloop4]
  have hsub := runLoop_sub tmp dst k (St tmp) (St dst)
    { ptr := tmp, tape := St, inp := Sd.inp, out := Sd.out }
    (by simp [St, Sd, State.inc, htmp0, hdst2, hdst2.symm, hdt, hdt.symm, htA, htB, htA.symm, htB.symm, hsrc1, hsrc])
    (by simp [St, Sd, State.inc, hdstA, hdstB, hdst2, hdt, htA, htB]) (by simp [St, Sd, State.inc, htmp0, hdst2, hdst2.symm, hdt, hdt.symm, htA, htB, htA.symm, htB.symm, hsrc1, hsrc]) (by simp [St]) hdt
  rw [hsub]
  have hm1 := run_move tmp 0 k { ptr := tmp, tape := fun i => if i = tmp then 0 else if i = dst then St dst - St tmp else St i, inp := Sd.inp, out := Sd.out } (by simp)
  rw [hm1]
  apply State.ext
  · rfl
  · ext i
    by_cases h0 : i = dst
    · subst i
      simp [St, Sd, State.inc, htmp0, hdst2, hdst2.symm, hdt, hdt.symm, htA, htB, htA.symm, htB.symm, hsrc1, hdstA, hdstB]
    · by_cases h1 : i = tmp
      · subst i
        simp [St, Sd, State.inc, htmp0, hdt, hdst2, htA, htB]
        omega
      · by_cases h2 : i = a
        · subst i
          simp [St, Sd, State.inc, ha, hdstA, hdstA.symm, hdst2, hdt, htmp0, htA, hdstB]
        · by_cases h3 : i = b
          · subst i
            simp [St, Sd, State.inc, hb, hdstB, hdstB.symm, hdst2, hdt, htmp0, htB, hdstA]
          · simp [St, Sd, State.inc, ha, hb, h0, h1, h2, h3, hdst2, hdst2.symm, hdstA, hdstA.symm, hdstB, hdstB.symm, hdt, htmp0, htA, htB]
  · rfl
  · rfl


/-- **The ``add`` macro.**  ``sum += src``, ``src`` preserved, scratch
zeroed, pointer home. -/
lemma run_add (src sum tmp a b k : ℕ) (s : State) (hptr : s.ptr = 0)
    (hsrc : s.tape src ≤ k) (ha : s.tape a = 0) (hb : s.tape b = 0) (htmp0 : s.tape tmp = 0)
    (hna : a ≠ src) (hnb : b ≠ src) (hnab : a ≠ b)
    (hst : src ≠ tmp) (hsum : sum ≠ tmp) (htA : tmp ≠ a) (htB : tmp ≠ b)
    (hsumS : sum ≠ src) (hsumA : sum ≠ a) (hsumB : sum ≠ b) :
    run (add src sum tmp a b) k s
      = { ptr := 0, tape := fun i => if i = tmp then 0 else if i = sum then s.tape sum + s.tape src else s.tape i,
          inp := s.inp, out := s.out } := by
  unfold add
  rw [run_append]
  rw [run_append]
  rw [run_append]
  have hcopy := run_copy src tmp a b k s hptr hsrc ha hb hna hnb hnab hst.symm htA htB
  rw [hcopy]
  have hm0 := run_move 0 tmp k { ptr := 0, tape := fun i => if i = a then 0 else if i = b then 0 else if i = tmp then s.tape tmp + s.tape src else s.tape i, inp := s.inp, out := s.out } (by simp)
  rw [hm0]
  have hloop5 : run [Cmd.loop (move tmp sum ++ [Cmd.plus] ++ move sum tmp ++ [Cmd.minus])] k
      { ptr := tmp, tape := fun i => if i = a then 0 else if i = b then 0 else if i = tmp then s.tape tmp + s.tape src else s.tape i, inp := s.inp, out := s.out }
      = runLoop (fun n s => run (move tmp sum ++ [Cmd.plus] ++ move sum tmp ++ [Cmd.minus]) n s) k
      { ptr := tmp, tape := fun i => if i = a then 0 else if i = b then 0 else if i = tmp then s.tape tmp + s.tape src else s.tape i, inp := s.inp, out := s.out } := by
    rw [run_loop, run_nil]
  rw [hloop5]
  let St2 : ℕ → ℕ := fun i => if i = tmp then 0 else if i = sum then s.tape sum + (s.tape tmp + s.tape src) else (if i = a then 0 else if i = b then 0 else if i = tmp then s.tape tmp + s.tape src else s.tape i)
  have hmove := runLoop_move tmp sum k (s.tape tmp + s.tape src) (s.tape sum)
    { ptr := tmp, tape := fun i => if i = a then 0 else if i = b then 0 else if i = tmp then s.tape tmp + s.tape src else s.tape i, inp := s.inp, out := s.out }
    (by simp [htA, htB]) (by simp [hsumA, hsumB, hsumS, hsum]) (by simp [htmp0, hsrc, htA, htB]) (by simp) hsum
  rw [hmove]
  have hm1 := run_move tmp 0 k { ptr := tmp, tape := St2, inp := s.inp, out := s.out } (by simp)
  rw [hm1]
  apply State.ext
  · rfl
  · ext i
    by_cases h0 : i = sum
    · subst i
      simp [St2, hsum, hsumA, hsumB, htmp0]
    · by_cases h1 : i = tmp
      · subst i
        simp [St2, htmp0]
      · by_cases h2 : i = a
        · subst i
          simp [St2, ha, hsumA, htmp0, hsum]
        · by_cases h3 : i = b
          · subst i
            simp [St2, hb, hsumB, htmp0, hsum]
          · simp [St2, h0, h1, h2, h3, htmp0, hsum]
  · rfl
  · rfl


/-- One iteration of ``[>t2[>dst+ >t2-]>t1-]``: cell ``t1`` drops by one and
the value of ``t2`` (0/1) is moved into ``dst``. -/
lemma run_body_and (t1 t2 dst k w : ℕ) (s : State) (hptr : s.ptr = t1) (hw : s.tape t2 = w)
    (hd : s.tape dst = 0) (hne1 : t1 ≠ t2) (hne2 : t1 ≠ dst) (hne3 : t2 ≠ dst)
    (hw1 : w ≤ k) :
    run (move t1 t2 ++ [Cmd.loop (move t2 dst ++ [Cmd.plus] ++ move dst t2 ++ [Cmd.minus])] ++ move t2 t1 ++ [Cmd.minus]) k s
      = { s with ptr := t1, tape := Function.update (Function.update s.tape t1 (s.tape t1 - 1)) dst (0 + w) } := by
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_move t1 t2 k s hptr]
  have hloopi : run [Cmd.loop (move t2 dst ++ [Cmd.plus] ++ move dst t2 ++ [Cmd.minus])] k
      { s with ptr := t2 }
      = runLoop (fun n s => run (move t2 dst ++ [Cmd.plus] ++ move dst t2 ++ [Cmd.minus]) n s) k { s with ptr := t2 } := by
    rw [run_loop, run_nil]
  rw [hloopi]
  have hmove := runLoop_move t2 dst k w 0 { s with ptr := t2 }
    (by simp [hw]) (by simp [hd]) (by simp [hw1]) (by simp) hne3.symm
  rw [hmove]
  have hmv := run_move t2 t1 k ({ ptr := t2, tape := (fun i => if i = t2 then 0 else if i = dst then 0 + w else s.tape i), inp := s.inp, out := s.out }) (by simp)
  rw [hmv]
  rw [run_minus]
  rw [run_nil]
  apply State.ext
  · rfl
  · ext i
    by_cases h0 : i = t1
    · by_cases h1 : i = dst
      · omega
      · subst i
        have hc : ¬ t1 = dst := by exact fun h => hne2 h
        simp [hptr, hc]
    · by_cases h1 : i = dst
      · subst i
        have hc : ¬ t1 = dst := by exact fun h => hne2 h
        simp [hptr, hc]
        omega
      · by_cases h2 : i = t2
        · subst i
          simp [hne1, hne2]
        · simp [h0, h1, h2]
  · rfl
  · rfl

/-- **The AND loop.**  ``[>t2[>dst+ >t2-]>t1-]`` sets ``dst`` to ``v AND w``
(the ``0/1`` values of cells ``t1`` and ``t2``), zeroing ``t1`` and ``t2``. -/
lemma runLoop_and (t1 t2 dst k v w : ℕ) (s : State) (hv : s.tape t1 = v) (hw : s.tape t2 = w)
    (hv01 : v = 0 ∨ v = 1) (hd : s.tape dst = 0) (hs : v ≤ k) (hptr : s.ptr = t1)
    (hne1 : t1 ≠ t2) (hne2 : t1 ≠ dst) (hne3 : t2 ≠ dst) (hw1 : w ≤ k) :
    runLoop (fun n s => run (move t1 t2 ++ [Cmd.loop (move t2 dst ++ [Cmd.plus] ++ move dst t2 ++ [Cmd.minus])] ++ move t2 t1 ++ [Cmd.minus]) n s) k s
      = { ptr := t1, tape := fun i => if i = t1 then 0 else if i = dst then v * w else s.tape i,
          inp := s.inp, out := s.out } := by
  rcases hv01 with h0 | h1
  · subst v
    have hcur : s.tape t1 = 0 := by simpa [hv]
    have hz : s.tape s.ptr = 0 := by simp [hptr, hcur]
    cases k with
    | zero =>
        simp [runLoop]
        apply State.ext
        · simp [hptr]
        · ext i <;> by_cases h : i = t1 <;> by_cases h' : i = dst <;> simp [h, h', hcur, hd]
        · rfl
        · rfl
    | succ k =>
        rw [runLoop_exit (fun n s => run (move t1 t2 ++ [Cmd.loop (move t2 dst ++ [Cmd.plus] ++ move dst t2 ++ [Cmd.minus])] ++ move t2 t1 ++ [Cmd.minus]) n s) k s (by simp [hptr, hcur])]
        apply State.ext
        · simp [hptr]
        · ext i <;> by_cases h : i = t1 <;> by_cases h' : i = dst <;> simp [h, h', hcur, hd]
        · rfl
        · rfl
  · subst v
    cases k with
    | zero => omega
    | succ k =>
        have hnz : s.tape s.ptr ≠ 0 := by simp [hptr, hv]
        rw [runLoop_step (fun n s => run (move t1 t2 ++ [Cmd.loop (move t2 dst ++ [Cmd.plus] ++ move dst t2 ++ [Cmd.minus])] ++ move t2 t1 ++ [Cmd.minus]) n s) k s hnz]
        have hs' := run_body_and t1 t2 dst (k + 1) w s hptr hw hd hne1 hne2 hne3 hw1
        rw [hs']
        have hz : (run (move t1 t2 ++ [Cmd.loop (move t2 dst ++ [Cmd.plus] ++ move dst t2 ++ [Cmd.minus])] ++ move t2 t1 ++ [Cmd.minus]) (k + 1) s).tape (State.left ({ s with ptr := t1, tape := Function.update (Function.update s.tape t1 (s.tape t1 - 1)) dst (0 + w) }.ptr)) = 0 := by
          simp
        have hexit : runLoop (fun n s => run (move t1 t2 ++ [Cmd.loop (move t2 dst ++ [Cmd.plus] ++ move dst t2 ++ [Cmd.minus])] ++ move t2 t1 ++ [Cmd.minus]) n s) k
            { s with ptr := t1, tape := Function.update (Function.update s.tape t1 (s.tape t1 - 1)) dst (0 + w) }
            = { s with ptr := t1, tape := Function.update (Function.update s.tape t1 (s.tape t1 - 1)) dst (0 + w) } := by
          cases k with
          | zero => simp [runLoop]
          | succ k => rw [runLoop_exit _ k _ hz]; rfl
        rw [hexit]
        apply State.ext
        · rfl
        · ext i <;> by_cases h0 : i = t1 <;> by_cases h1 : i = dst
          · simp [h0, h1]
          · subst i
            simp [h0]
          · subst i
            rw [hs']
            simp [hne2]
            omega
          · rw [hs']
            simp [h0, h1]
        · rfl
        · rw [hs']

/-- **The ``and_`` macro.**  ``dst = a AND b`` for ``a, b : ℕ`` with
``a = 0 ∨ a = 1`` and ``b = 0 ∨ b = 1``; ``a`` and ``b`` preserved, scratch
zeroed, pointer home. -/
lemma run_and (a b dst t1 t2 c1 d1 c2 d2 k : ℕ) (s : State) (hptr : s.ptr = 0)
    (ha1 : s.tape a ≤ k) (hb1 : s.tape b ≤ k)
    (hdst0 : s.tape dst = 0) (ht1 : s.tape t1 = 0) (ht2 : s.tape t2 = 0)
    (hc1 : s.tape c1 = 0) (hd1 : s.tape d1 = 0) (hc2 : s.tape c2 = 0) (hd2 : s.tape d2 = 0)
    (hnd : dst ≠ a) (hnd2 : dst ≠ b) (hne1 : t1 ≠ a) (hne2 : t1 ≠ b)
    (hne3 : t2 ≠ a) (hne4 : t2 ≠ b) (hne5 : t1 ≠ t2) (hne6 : t2 ≠ dst) (hne7 : t1 ≠ dst)
    (hac : a ≠ c1) (had : a ≠ d1) (hbc : b ≠ c1) (hbd : b ≠ d1)
    (haa : a ≠ c2) (hab : a ≠ d2) (hbb : b ≠ c2) (hbd2 : b ≠ d2)
    (ht1c1 : t1 ≠ c1) (ht1d1 : t1 ≠ d1) (hc1d1 : c1 ≠ d1)
    (ht2c2 : t2 ≠ c2) (ht2d2 : t2 ≠ d2) (hc2d2 : c2 ≠ d2) :
    run (and_ a b dst t1 t2 c1 d1 c2 d2) k s
      = { ptr := 0, tape := fun i => if i = dst then s.tape a * s.tape b else s.tape i,
          inp := s.inp, out := s.out } := by
  unfold and_
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_move 0 dst k s hptr]
  have hz := run_zero_here k { s with ptr := dst } (by simp [hdst0])
  rw [hz]
  have hmv := run_move dst 0 k { s with ptr := dst, tape := Function.update s.tape dst 0 } (by simp)
  rw [hmv]
  have hcopy1 := run_copy a t1 c1 d1 k { s with tape := Function.update s.tape dst 0 }
    (by simp) (by simp [ha1]) (by simp [hc1]) (by simp [hd1])
    hac.symm had.symm hc1d1 hne1 ht1c1 ht1d1
  rw [hcopy1]
  have hcopy2 := run_copy b t2 c2 d2 k { ptr := 0,
      tape := fun i => if i = c1 then 0 else if i = d1 then 0 else if i = t1 then s.tape a else if i = dst then 0 else s.tape i,
      inp := s.inp, out := s.out }
    (by simp) (by simp [hb1, hbc, hbd, hc2, hd2]) (by simp [hc2]) (by simp [hd2])
    hbb.symm hbd2.symm hc2d2 hne2 ht2c2 ht2d2
  rw [hcopy2]
  have hm0 := run_move 0 t1 k { ptr := 0,
      tape := fun i => if i = c1 then 0 else if i = d1 then 0 else if i = t1 then s.tape a else if i = t2 then s.tape b else if i = dst then 0 else s.tape i,
      inp := s.inp, out := s.out } (by simp)
  rw [hm0]
  have hloop6 : run [Cmd.loop (move t1 t2 ++ [Cmd.loop (move t2 dst ++ [Cmd.plus] ++ move dst t2 ++ [Cmd.minus])] ++ move t2 t1 ++ [Cmd.minus])] k
      { ptr := t1,
        tape := fun i => if i = c1 then 0 else if i = d1 then 0 else if i = t1 then s.tape a else if i = t2 then s.tape b else if i = dst then 0 else s.tape i,
        inp := s.inp, out := s.out }
      = runLoop (fun n s => run (move t1 t2 ++ [Cmd.loop (move t2 dst ++ [Cmd.plus] ++ move dst t2 ++ [Cmd.minus])] ++ move t2 t1 ++ [Cmd.minus]) n s) k
      { ptr := t1,
        tape := fun i => if i = c1 then 0 else if i = d1 then 0 else if i = t1 then s.tape a else if i = t2 then s.tape b else if i = dst then 0 else s.tape i,
        inp := s.inp, out := s.out } := by
    rw [run_loop, run_nil]
  rw [hloop6]
  have hand := runLoop_and t1 t2 dst k (s.tape a) (s.tape b)
    { ptr := t1,
      tape := fun i => if i = c1 then 0 else if i = d1 then 0 else if i = t1 then s.tape a else if i = t2 then s.tape b else if i = dst then 0 else s.tape i,
      inp := s.inp, out := s.out }
    (by simp) (by simp) (by simp) (by simp [hdst0]) (by simp [ha1]) (by simp) hne5 hne7 hne6 hb1
  rw [hand]
  have hm1 := run_move t1 0 k { ptr := t1,
      tape := fun i => if i = t1 then 0 else if i = dst then s.tape a * s.tape b else if i = c1 then 0 else if i = d1 then 0 else if i = t2 then s.tape b else s.tape i,
      inp := s.inp, out := s.out } (by simp)
  rw [hm1]
  apply State.ext
  · rfl
  · ext i
    by_cases h0 : i = dst
    · subst i
      simp [hnd, hnd2]
    · by_cases h1 : i = t1
      · subst i
        simp
      · by_cases h2 : i = t2
        · subst i
          simp
        · by_cases h3 : i = c1
          · subst i
            simp
          · by_cases h4 : i = d1
            · subst i
              simp
            · simp [h0, h1, h2, h3, h4]
  · rfl
  · rfl

end BfMintermCorrect
