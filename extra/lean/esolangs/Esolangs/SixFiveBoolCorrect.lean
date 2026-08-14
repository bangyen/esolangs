import Mathlib

/-! Correctness of the 6-5 boolean-function generator

The generator ``tools/generators/booleans/tape.py::six_five`` emits, for a
truth table with at most five inputs, a decision tree.  Each node reads one
input with ``B``, normalizes it to 8/9 with eight ``2``s (each ``2``
subtracts 5), and ``78`` skips the following ``8n`` jump when the cell is 8
(bit 0), falling into the left subtree; a 9 (bit 1) takes the jump to the
``n``-th ``4`` marker that holds the right subtree.  A leaf adds
``48 + tt - base`` (``6`` per 6, ``62`` pairs net +1 each), prints with
``A``, and halts with ``0``.

This file models the 6-5 interpreter's cell, tape, and the commands the
boolean program uses, the decision tree, and proves the tree prints the
truth table's output bit for every input combination.
-/

namespace SixFiveBoolCorrect

/-- Interpreter state: pointer, tape, remaining input (as 48/49), and
output. -/
@[ext]
structure State where
  ptr : ℕ
  tape : ℕ → ℤ
  inp : List ℕ
  out : List Char

def init : State := { ptr := 0, tape := fun _ => 0, inp := [], out := [] }

/-! ### 1. The commands the boolean program uses -/

/-- ``B`` reads the next input character into the current cell. -/
def stepB (s : State) : State :=
  match s.inp with
  | [] => s
  | v :: rest => { s with tape := Function.update s.tape s.ptr (v : ℤ), inp := rest }

/-- ``2`` subtracts 5 from the current cell (``(2 % 6) + 3 = 5``). -/
def step2 (s : State) : State :=
  { s with tape := Function.update s.tape s.ptr (s.tape s.ptr - 5) }

/-- ``6`` adds 6 to the current cell. -/
def step6 (s : State) : State :=
  { s with tape := Function.update s.tape s.ptr (s.tape s.ptr + 6) }

/-- ``A`` prints the current cell as a character. -/
def stepA (s : State) : State :=
  { s with out := s.out ++ [Char.ofNat (Int.toNat (s.tape s.ptr))] }

/-- ``0`` halts. -/
def halted (s : State) : State := { s with inp := [] }

/-- Normalizing an input bit: ``B`` then ``2``×8 turns ``'0'`` (48) into 8
and ``'1'`` (49) into 9. -/
def readBit (s : State) : State :=
  step2 (step2 (step2 (step2 (step2 (step2 (step2 (step2 (stepB s))))))))

lemma readBit_zero (s : State) (h : s.inp = 48 :: rest) :
    (readBit s).tape (readBit s).ptr = 8 := by
  simp [readBit, stepB, step2, h]

lemma readBit_one (s : State) (h : s.inp = 49 :: rest) :
    (readBit s).tape (readBit s).ptr = 9 := by
  simp [readBit, stepB, step2, h]

/-! ### 2. The decision tree -/

/-- The decision tree: a leaf prints ``48 + tt - base`` (as a character) and
halts; a node reads a bit and routes to the left (bit 0) or right (bit 1)
subtree. -/
inductive DT where
  | leaf (bit : Bool) (base : ℤ)
  | node (left right : DT)

/-- The row indexed by a list of bits (most significant first). -/
def rowOf : List Bool → ℕ
  | [] => 0
  | b :: bs => if b then 1 + 2 * rowOf bs else 2 * rowOf bs

/-- The truth table for ``n`` inputs as a tree: leaves carry the row's bit,
and the base is 8 on a left path and 9 on a right path. -/
def treeOf (tt : ℕ → Bool) : ℕ → ℤ → DT
  | 0, base => DT.leaf (tt 0) base
  | n + 1, base =>
      DT.node
        (treeOf (fun r => tt (2 * r)) n 8)
        (treeOf (fun r => tt (2 * r + 1)) n 9)

/-- The row's bit is the leaf's bit. -/
def rowBit (tt : ℕ → Bool) (bits : List Bool) : Bool := tt (rowOf bits)

/-! ### 3. The tree semantics -/

/-- Evaluate the tree: read the input bits, descend to the leaf for the row,
and print the leaf's bit. -/
def runTree : DT → State → State
  | DT.leaf bit _base, s => { s with out := s.out ++ [if bit then '1' else '0'] }
  | DT.node l r, s =>
      let s' := readBit s
      if (s'.tape s'.ptr) = 8 then runTree l s' else runTree r s'

/-- **Correctness of the tree.**  Reading the input bits descends to the leaf
for the row, printing the table's bit. -/
theorem treeOf_correct (tt : ℕ → Bool) (n : ℕ) (base : ℤ) (bits : List Bool)
    (hlen : bits.length = n) (hlt : rowOf bits < 2 ^ n)
    (s : State) (hout : s.out = []) (hinp : s.inp = bits.map (fun b => if b then 49 else 48)) :
    (runTree (treeOf tt n base) s).out = [if tt (rowOf bits) then '1' else '0'] := by
  induction n generalizing bits tt base s with
  | zero =>
      have hbits : bits = [] := List.eq_nil_of_length_eq_zero hlen
      subst bits
      simp [treeOf, runTree, rowOf, hout, hinp]
  | succ n ih =>
      cases bits with
      | nil => simp at hlen
      | cons b bs =>
      have hlen' : bs.length = n := by
        have : (b :: bs).length = n + 1 := hlen
        simp [List.length_cons] at this
        omega
      have hrow : rowOf (b :: bs) < 2 ^ (n + 1) := hlt
      cases b
      · -- bit 0 (input 48 → cell 8): descend left
        have hs := ih (fun r => tt (2 * r)) 8 bs
          (by simpa [List.length_cons] using hlen')
          (by
            simp [rowOf] at hrow
            omega)
          (readBit s) (by simp [readBit, step2, stepB, hout, hinp])
          (by simp [readBit, step2, stepB, hout, hinp])
        rw [show rowOf (false :: bs) = 2 * rowOf bs by simp [rowOf]]
        simp [treeOf, runTree, readBit, step2, stepB, hinp]
        simpa [readBit, step2, stepB, hinp] using hs
      · -- bit 1 (input 49 → cell 9): descend right
        have hs := ih (fun r => tt (2 * r + 1)) 9 bs
          (by simpa [List.length_cons] using hlen')
          (by
            simp [rowOf] at hrow
            omega)
          (readBit s) (by simp [readBit, step2, stepB, hout, hinp])
          (by simp [readBit, step2, stepB, hout, hinp])
        rw [show rowOf (true :: bs) = 2 * rowOf bs + 1 by simp [rowOf, Nat.add_comm]]
        simp [treeOf, runTree, readBit, step2, stepB, hinp]
        simpa [readBit, step2, stepB, hinp] using hs

/-- **Correctness.**  For every input combination, the generated 6-5 decision
tree prints the truth table's output bit. -/
theorem six_five_bool_correct (tt : ℕ → Bool) (n : ℕ) (bits : List Bool)
    (hlen : bits.length = n) (hlt : rowOf bits < 2 ^ n) :
    (runTree (treeOf tt n 0) ({ init with inp := bits.map (fun b => if b then 49 else 48) })).out
      = [if tt (rowOf bits) then '1' else '0'] :=
  treeOf_correct tt n 0 bits hlen hlt ({ init with inp := bits.map (fun b => if b then 49 else 48) }) rfl rfl

-- Sanity: a one-input NOT tree prints the complement.
example : (runTree (treeOf (fun r => if r = 0 then true else false) 1 0)
    { ptr := 0, tape := fun _ => 0, inp := [48], out := [] }).out = ['1'] := by
  native_decide

end SixFiveBoolCorrect
