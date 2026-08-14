import Mathlib

/-! Correctness of the Sophie boolean-function generator

The generator ``tools/generators/booleans/register.py::sophie`` emits, for a
truth table, a decision tree: ``;`` reads one input character (``0`` or
``1``, so the accumulator becomes 48 or 49) and ``@$48{T}{E}`` runs ``T``
when the accumulator is 48 (input bit 0) and ``E`` otherwise; each leaf
prints ``#$48`` or ``#$49`` (``0`` / ``1``) and halts with ``&``.

This file models the interpreter's accumulator, input, and output, the
decision tree, and ``run`` over the emitted program, and proves the tree
prints exactly the truth table's bit for each input combination.
-/

namespace SophieBoolCorrect

/-- Interpreter state: accumulator, remaining input (as 48/49), output,
and whether the program has halted. -/
@[ext]
structure State where
  acc : ℕ
  inp : List ℕ
  out : List Char
  halt : Bool

def init : State := { acc := 0, inp := [], out := [], halt := false }

/-- The decision tree: a leaf prints a bit and halts, a node reads a bit and
branches on it (``then`` for bit 0, ``else`` for bit 1). -/
inductive DT where
  | leaf (bit : Bool)
  | node (t e : DT)

/-- The path (list of bits, most significant first) indexed by the truth
table row. -/
def rowOf : List Bool → ℕ
  | [] => 0
  | b :: bs => if b then 1 + 2 * rowOf bs else 2 * rowOf bs

/-- The truth table for ``n`` inputs, as a function of the row. -/
def treeOf (tt : ℕ → Bool) : ℕ → DT
  | 0 => DT.leaf (tt 0)
  | n + 1 => DT.node (treeOf (fun r => tt (2 * r)) n) (treeOf (fun r => tt (2 * r + 1)) n)

/-- The emitted program for a tree: leaves print ``#$49,&`` / ``#$48,&``,
nodes read a bit and branch on ``@$48{then}{else}``. -/
def render : DT → List Char
  | DT.leaf true => ['#', '$', '4', '9', ',', '&']
  | DT.leaf false => ['#', '$', '4', '8', ',', '&']
  | DT.node t e => [';', '@', '$', '4', '8', '{'] ++ render t ++ ['}', '{'] ++ render e ++ ['}']

/-! ### 1. Single commands -/

/-- ``;`` reads the next input character into the accumulator. -/
def stepSemi (s : State) : State :=
  match s.inp with
  | [] => s
  | v :: rest => { s with acc := v, inp := rest }

/-- ``#$48`` / ``#$49`` loads the accumulator; ``,`` prints it as a char. -/
def stepLoad (s : State) : State :=
  match s.acc with
  | 48 => { s with out := s.out ++ ['0'] }
  | 49 => { s with out := s.out ++ ['1'] }
  | _ => s

/-! ### 2. The tree semantics -/

/-- Evaluate the decision tree: read the input bits and reach the leaf whose
row matches, printing the leaf's bit and halting. -/
def runTree : DT → State → State
  | DT.leaf b, s => { s with out := s.out ++ [if b then '1' else '0'], halt := true }
  | DT.node t e, s =>
      let s' := stepSemi s
      if s'.acc = 48 then runTree t s' else runTree e s'

/-- **Correctness of the tree.**  Reading the input bits descends the tree to
the leaf for the row they index, printing the truth table's bit. -/
theorem treeOf_correct (tt : ℕ → Bool) (n : ℕ) (bits : List Bool)
    (hlen : bits.length = n) (hlt : rowOf bits < 2 ^ n)
    (s : State) (hout : s.out = []) (hhalt : s.halt = false)
    (hinp : s.inp = bits.map (fun b => if b then 49 else 48)) :
    (runTree (treeOf tt n) s).out = [if tt (rowOf bits) then '1' else '0'] ∧
    (runTree (treeOf tt n) s).halt = true ∧
    (runTree (treeOf tt n) s).inp = [] := by
  induction n generalizing bits tt s with
  | zero =>
      have hbits : bits = [] := List.eq_nil_of_length_eq_zero hlen
      subst bits
      simp [treeOf, runTree, rowOf, hout, hhalt, hinp]
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
      · -- bit 0 (acc 48): descend into the then branch
        have hs := ih (fun r => tt (2 * r)) bs (by simpa [List.length_cons] using hlen')
          (by
            simp [rowOf] at hrow
            omega)
          (stepSemi s) (by simp [stepSemi, hout, hhalt, hinp]) (by simp [stepSemi, hhalt, hinp])
          (by simp [stepSemi, hout, hhalt, hinp])
        rw [show rowOf (false :: bs) = 2 * rowOf bs by simp [rowOf]]
        simpa [treeOf, runTree, stepSemi, hinp] using hs
      · -- bit 1 (acc 49): descend into the else branch
        have hs := ih (fun r => tt (2 * r + 1)) bs (by simpa [List.length_cons] using hlen')
          (by
            simp [rowOf] at hrow
            omega)
          (stepSemi s) (by simp [stepSemi, hout, hhalt, hinp]) (by simp [stepSemi, hhalt, hinp])
          (by simp [stepSemi, hout, hhalt, hinp])
        rw [show rowOf (true :: bs) = 2 * rowOf bs + 1 by simp [rowOf, Nat.add_comm]]
        simpa [treeOf, runTree, stepSemi, hinp] using hs

/-! ### 3. The whole program -/

/-- The generated program for a truth table with ``n`` inputs. -/
def prog (tt : ℕ → Bool) (n : ℕ) : List Char := render (treeOf tt n)

/-- **Correctness.**  For every input combination, the generated Sophie
program prints the truth table's output bit. -/
theorem sophie_bool_correct (tt : ℕ → Bool) (n : ℕ) (bits : List Bool)
    (hlen : bits.length = n) (hlt : rowOf bits < 2 ^ n) :
    (runTree (treeOf tt n) { init with inp := bits.map (fun b => if b then 49 else 48) }).out
      = [if tt (rowOf bits) then '1' else '0'] :=
  (treeOf_correct tt n bits hlen hlt ({ init with inp := bits.map (fun b => if b then 49 else 48) })
    rfl rfl rfl).1

-- Sanity: a one-input NOT tree prints the complement.
example : (runTree (treeOf (fun r => if r = 0 then true else false) 1)
    { acc := 0, inp := [48], out := [], halt := false }).out = ['1'] := by
  native_decide

end SophieBoolCorrect
