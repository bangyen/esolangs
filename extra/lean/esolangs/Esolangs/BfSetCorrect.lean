import Mathlib

/-! Correctness of the brainfuck ``_bf_set`` multiply loop

The brainfuck generator ``src/esolangs/tools/generators/tape.py::_bf_set``
emits ``+a[>+b<-]>+r.`` to set the next cell to ``a*b + r`` (the ``divmod``
of the target value) and print it, in ``O(sqrt)`` rather than ``O(value)``.
This file models a minimal brainfuck interpreter (a tape of natural-number
cells, a pointer, and an output list) and proves the loop invariant:
after ``a`` iterations of ``[>+b<-]`` the first cell is zeroed and the
second holds ``a*b``; the trailing ``>+r.`` then prints ``a*b + r``.

The interpreter runs with an explicit fuel bound so loops are total; the
multiply loop needs ``a`` units of fuel, which is exactly what the program
is started with.
-/

namespace BfSetCorrect

/-- Brainfuck commands: ``+ - > < .`` and ``[body]``. -/
inductive Cmd where
  | plus | minus | right | left | out | loop (body : List Cmd)

/-- Machine state: pointer, tape (cells are natural numbers), output. -/
@[ext]
structure State where
  ptr : ℕ
  tape : ℕ → ℕ
  out : List Char

def State.inc (s : State) : State :=
  { s with tape := Function.update s.tape s.ptr (s.tape s.ptr + 1) }

def State.dec (s : State) : State :=
  { s with tape := Function.update s.tape s.ptr (s.tape s.ptr - 1) }

def State.right (s : State) : State := { s with ptr := s.ptr + 1 }

def State.left (s : State) : State := { s with ptr := s.ptr - 1 }

def State.emit (s : State) : State := { s with out := s.out ++ [Char.ofNat (s.tape s.ptr)] }

/-- ``[body]`` run as a while loop for at most ``n`` iterations; ``step``
executes the body once from a given state with a given fuel. -/
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
  | Cmd.out :: cs, n, s => run cs n (State.emit s)
  | Cmd.loop body :: cs, n, s => run cs n (runLoop (fun n s => run body n s) n s)

/-! ### 1. Straight-line execution -/

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
      cases c <;> simp [run_plus, run_minus, run_right, run_left, run_out, run_loop, ih]

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

lemma inc_tape (s : State) (i : ℕ) :
    (State.inc s).tape i = if i = s.ptr then s.tape s.ptr + 1 else s.tape i := by
  simp [State.inc, Function.update]

lemma left_after_right (s : State) : State.left (State.right s) = s := by
  ext <;> simp [State.left, State.right]

/-! ### 2. One iteration of ``[>+b<-]`` -/

/-- The body of the multiply loop: ``>+b<-``. -/
def body (b : ℕ) : List Cmd := Cmd.right :: List.replicate b Cmd.plus ++ [Cmd.left, Cmd.minus]

lemma run_body (b k : ℕ) (s : State) (hptr : s.ptr = 0) :
    run (body b) k s
      = { s with
          ptr := 0,
          tape := Function.update (Function.update s.tape 1 (s.tape 1 + b)) 0 (s.tape 0 - 1) } := by
  unfold body
  rw [run_append]
  rw [run_right]
  rw [run_plusN]
  rw [run_left]
  rw [run_minus]
  rw [run_nil]
  apply State.ext
  · simp [State.left, State.right, State.dec, hptr]
  · ext i
    by_cases h0 : i = 0
    · by_cases h1 : i = 1
      · simp [State.left, State.right, State.inc, State.dec, Function.update, h0, h1, hptr]
      · subst i
        simp [State.left, State.right, State.inc, State.dec, Function.update, hptr]
    · by_cases h1 : i = 1
      · subst i
        simp [State.left, State.right, State.inc, State.dec, Function.update, hptr]
      · simp [State.left, State.right, State.inc, State.dec, Function.update, h0, h1, hptr]
  · simp [State.left, State.right, State.dec, State.inc]

lemma runLoop_exit (step : ℕ → State → State) (k : ℕ) (s : State) (hz : s.tape s.ptr = 0) :
    runLoop step (k + 1) s = s := by
  simp [runLoop, hz]

lemma runLoop_step (step : ℕ → State → State) (k : ℕ) (s : State) (hnz : s.tape s.ptr ≠ 0) :
    runLoop step (k + 1) s = runLoop step k (step (k + 1) s) := by
  simp [runLoop, hnz]

/-! ### 3. The multiply loop -/

/-- **Loop invariant.**  Starting with cell 0 = ``a`` and cell 1 = ``c1``,
``[>+b<-]`` zeroes cell 0 and adds ``a*b`` to cell 1, provided there is fuel
for ``a`` iterations. -/
lemma runLoop_mult (a b c1 k : ℕ) (s : State) (ha : a ≤ k)
    (h0 : s.tape 0 = a) (h1 : s.tape 1 = c1) (hptr : s.ptr = 0)
    (hfree : ∀ i, 2 ≤ i → s.tape i = 0) :
    runLoop (fun n s => run (body b) n s) k s
      = { ptr := 0, tape := fun i => if i = 0 then 0 else if i = 1 then c1 + a * b else 0,
          out := s.out } := by
  induction a generalizing c1 k s with
  | zero =>
      -- cell 0 is already zero: the loop exits immediately
      cases k with
      | zero =>
          simp [runLoop]
          apply State.ext
          · simp [hptr]
          · ext i <;> by_cases h : i = 0 <;> by_cases h' : i = 1
            · subst i; simp [h0, h1]
            · subst i; simp [h0]
            · subst i; simp [h1]
            · simpa [h, h'] using hfree i (by omega)
          · rfl
      | succ k =>
          rw [runLoop_exit (fun n s => run (body b) n s) k s]
          · apply State.ext
            · simp [hptr]
            · ext i <;> by_cases h : i = 0 <;> by_cases h' : i = 1
              · subst i; simp [h0, h1]
              · subst i; simp [h0]
              · subst i; simp [h1]
              · simpa [h, h'] using hfree i (by omega)
            · rfl
          · simpa [hptr] using h0
  | succ a ih =>
      -- cell 0 is a+1 > 0: run one iteration, then apply the invariant
      have hk1 : 1 ≤ k := by omega
      cases k with
      | zero => omega
      | succ k' =>
      rw [runLoop_step (fun n s => run (body b) n s) k' s]
      · have hs := run_body b (k' + 1) s hptr
        have htape0 : (run (body b) (k' + 1) s).tape 0 = a := by
          rw [hs]
          simp [h0]
        have htape1 : (run (body b) (k' + 1) s).tape 1 = c1 + b := by
          rw [hs]
          simp [h1]
        have hptr' : (run (body b) (k' + 1) s).ptr = 0 := by
          rw [hs]
        have hfree' : ∀ i, 2 ≤ i → (run (body b) (k' + 1) s).tape i = 0 := by
          intro i hi
          have hnz : i ≠ 0 := by omega
          have hn1 : i ≠ 1 := by omega
          rw [hs]
          simp [hnz, hn1, hfree i hi]
        have ha' : a ≤ k' := by omega
        rw [ih (c1 + b) k' (run (body b) (k' + 1) s) ha' htape0 htape1 hptr' hfree']
        apply State.ext
        · simp [hptr]
        · ext i <;> by_cases h0' : i = 0 <;> by_cases h1' : i = 1
          · simp [h0', h1']
          · simp [h0']
          · subst i
            simp [h0']
            rw [Nat.succ_mul]
            omega
          · simp [h0', h1']
        · rw [hs]
      · intro hz
        have hz0 : s.tape 0 = 0 := by
          simpa [hptr] using hz
        omega

/-! ### 4. The whole program -/

/-- ``+a[>+b<-]>+r.``  (the ``_bf_set`` program). -/
def bf_set_prog (a b r : ℕ) : List Cmd :=
  List.replicate a Cmd.plus ++
    [Cmd.loop (body b)] ++
    [Cmd.right] ++ List.replicate r Cmd.plus ++ [Cmd.out]

/-- **Correctness.**  From an all-zero tape, ``+a[>+b<-]>+r.`` prints the
value ``a*b + r`` from the next cell and leaves the pointer on it. -/
theorem bf_set_correct (a b r : ℕ) :
    let s0 : State := { ptr := 0, tape := fun _ => 0, out := [] }
    run (bf_set_prog a b r) a s0
      = { ptr := 1,
          tape := fun i => if i = 1 then a * b + r else 0,
          out := [Char.ofNat (a * b + r)] } := by
  intro s0
  unfold bf_set_prog
  rw [run_append]
  rw [run_append]
  rw [run_append]
  rw [run_append]
  have h1 : (run (List.replicate a Cmd.plus) a s0).tape 1 = 0 := by
    rw [run_plusN]
    simp [s0]
  have h0 : (run (List.replicate a Cmd.plus) a s0).tape 0 = a := by
    rw [run_plusN]
    simp [s0]
  have hptr : (run (List.replicate a Cmd.plus) a s0).ptr = 0 := by
    rw [run_plusN]
  have hfree : ∀ i, 2 ≤ i → (run (List.replicate a Cmd.plus) a s0).tape i = 0 := by
    intro i hi
    have hnz : i ≠ 0 := by omega
    rw [run_plusN]
    simp [s0, hnz]
  have hloop := runLoop_mult a b 0 a (run (List.replicate a Cmd.plus) a s0)
    (le_rfl : a ≤ a) h0 h1 hptr hfree
  rw [run_loop, run_nil]
  rw [hloop]
  rw [run_right]
  rw [run_nil]
  rw [run_plusN]
  rw [run_out]
  rw [run_nil]
  apply State.ext
  · simp [State.right, State.emit]
  · ext i <;> by_cases h : i = 1
    · subst i
      simp [State.right, State.emit, Function.update]
    · simp [State.right, State.emit, Function.update, h]
  · simp [State.right, State.emit, run_plusN]
    rfl

/-- **In terms of the generator's ``divmod``.**  For ``value = a*b + r`` the
printed cell holds exactly ``value``. -/
theorem bf_set_value (a value : ℕ) (_ha : 0 < a) :
    let b := value / a
    let r := value % a
    let s0 : State := { ptr := 0, tape := fun _ => 0, out := [] }
    run (bf_set_prog a b r) a s0
      = { ptr := 1,
          tape := fun i => if i = 1 then value else 0,
          out := [Char.ofNat value] } := by
  intro b r s0
  dsimp [b, r]
  have h : a * (value / a) + value % a = value := Nat.div_add_mod value a
  rw [bf_set_correct a (value / a) (value % a)]
  apply State.ext
  · rfl
  · ext i <;> by_cases h1 : i = 1 <;> simp [h, h1]
  · simp [h]

-- Sanity round-trips: ``+a[>+b<-]>+r.`` prints ``a*b + r``.
example : (run (bf_set_prog 3 2 1) 3 { ptr := 0, tape := fun _ => 0, out := [] }).out
    = [Char.ofNat 7] := by native_decide
example : (run (bf_set_prog 3 2 1) 3 { ptr := 0, tape := fun _ => 0, out := [] }).ptr
    = 1 := by native_decide
example : (run (bf_set_prog 1 9 9) 1 { ptr := 0, tape := fun _ => 0, out := [] }).out
    = [Char.ofNat 18] := by native_decide

end BfSetCorrect
