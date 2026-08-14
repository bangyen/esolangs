import Mathlib

/-! Correctness of the Eval text generator

The generator ``src/esolangs/tools/generators/register.py::eval`` emits the
program ``"<text with " -> `>".`` : a string literal (with double quotes
escaped as backticks, since a literal quote would end the literal early),
followed by ``.`` which prints it.  The interpreter
(``src/esolangs/interpreters/stack_based/eval.py``) keeps two stacks and an
active pointer; ``"`` starts a literal that runs until the next ``"``,
expanding backticks back to quotes, and ``.`` prints the popped value.

This file models the interpreter (values, the two stacks, the literal scan,
and ``run``) and proves the generator *correct*: for text with no literal
backtick (which the generator refuses), ``"<escaped>".`` prints exactly the
text through the interpreter's own transitions.
-/

namespace EvalCorrect

/-- A stack value: an integer or a string. -/
inductive Val where
  | int (n : ℤ)
  | str (s : String)

/-- Machine state: active stack pointer, two stacks, and the output. -/
@[ext]
structure State where
  ptr : ℕ
  stk0 : List Val
  stk1 : List Val
  out : List Char

def State.active (s : State) : List Val := if s.ptr = 0 then s.stk0 else s.stk1

def State.push (s : State) (v : Val) : State :=
  if s.ptr = 0 then { s with stk0 := v :: s.stk0 } else { s with stk1 := v :: s.stk1 }

/-- Pop the top of the active stack (``none`` when empty). -/
def State.pop (s : State) : State × Option Val :=
  if s.ptr = 0 then
    match s.stk0 with
    | [] => (s, none)
    | v :: rest => ({ s with stk0 := rest }, some v)
  else
    match s.stk1 with
    | [] => (s, none)
    | v :: rest => ({ s with stk1 := rest }, some v)

/-- ``.`` prints the popped value: a string's characters, or an integer's
decimal digits. -/
def printValue (out : List Char) (v : Val) : List Char :=
  match v with
  | Val.str s => out ++ s.toList
  | Val.int n => out ++ (toString n).toList

/-- The string literal: take characters until the closing ``"`` (not
consumed), expanding backticks to quotes; return the content and the
remainder after the closing quote. -/
def scanStringAux : List Char → List Char → List Char × List Char
  | [], acc => (List.reverse acc, [])
  | '"' :: rest, acc => (List.reverse acc, rest)
  | '`' :: rest, acc => scanStringAux rest ('"' :: acc)
  | c :: rest, acc => scanStringAux rest (c :: acc)

def scanString (code : List Char) : List Char × List Char := scanStringAux code []

lemma scanString_rest_le (code acc : List Char) :
    (scanStringAux code acc).2.length ≤ code.length := by
  induction code generalizing acc with
  | nil => simp [scanStringAux]
  | cons c code ih =>
      by_cases hc : c = '"'
      · subst c
        simp [scanStringAux]
      · by_cases hbt : c = '`'
        · subst c
          simp [scanStringAux]
          have h := ih ('"' :: acc)
          omega
        · simp [scanStringAux, hc, hbt]
          have h := ih (c :: acc)
          omega

/-- Run a program from a state.  A string literal consumes its content plus
the closing quote; the continuation is ``cs.drop (content.length + 1)``, which
is structurally smaller than ``'"' :: cs``.  (``!`` would evaluate the popped
string recursively; the generator's programs never emit it, so it is modelled
as a pop.) -/
def run : List Char → State → State
  | [], s => s
  | '"' :: cs, s =>
      run (cs.drop ((scanString cs).1.length + 1))
        (State.push s (Val.str (String.ofList (scanString cs).1)))
  | '\'' :: cs, s =>
      run (cs.drop ((scanString cs).1.length + 1))
        (State.push s (Val.str ("\"" ++ String.ofList (scanString cs).1 ++ "\"")))
  | '.' :: cs, s =>
      let (s', v) := s.pop
      match v with
      | some val => run cs { s' with out := printValue s'.out val }
      | none => s
  | c :: cs, s => run cs s
termination_by code => code.length
decreasing_by
  all_goals
    simp_wf
    try
      rw [List.length_drop]
      omega

/-! ### 1. The generator's escaping -/

/-- The generator replaces double quotes with backticks. -/
def escape : List Char → List Char
  | [] => []
  | c :: cs => (if c = '"' then '`' else c) :: escape cs

lemma reverse_cons_append (a : Char) (as : List Char) :
    List.reverse (a :: as) = List.reverse as ++ [a] := by
  rw [List.reverse_cons]

lemma scan_aux (text acc : List Char) (hbt : '`' ∉ text) :
    (scanStringAux (escape text ++ ['"', '.']) acc).1 = List.reverse acc ++ text ∧
    (scanStringAux (escape text ++ ['"', '.']) acc).2 = ['.'] := by
  induction text generalizing acc with
  | nil => simp [escape, scanStringAux]
  | cons c text ih =>
      have hcbt : c ≠ '`' := by
        intro hcbt; exact hbt (by exact List.mem_cons.mpr (Or.inl hcbt.symm))
      by_cases hcq : c = '"'
      · subst c
        simp [escape, List.cons_append]
        rw [scanStringAux]
        have h := ih ('"' :: acc) (by intro h; exact hbt (by exact List.mem_cons.mpr (Or.inr h)))
        rcases h with ⟨h1, h2⟩
        refine ⟨?_, ?_⟩
        · rw [h1]
          simp [reverse_cons_append, List.append_assoc, List.cons_append]
        · exact h2
      · simp [escape, List.cons_append, hcq]
        simp [scanStringAux, hcq, hcbt]
        have h := ih (c :: acc) (by intro h; exact hbt (by exact List.mem_cons.mpr (Or.inr h)))
        rcases h with ⟨h1, h2⟩
        refine ⟨?_, ?_⟩
        · rw [h1]
          simp [reverse_cons_append, List.append_assoc, List.cons_append]
        · exact h2

/-! ### 2. The whole generator program -/

/-- ``"<escaped>".`` — the program the generator emits for ``text``. -/
def prog (text : List Char) : List Char :=
  '"' :: escape text ++ ['"', '.']

lemma escape_length (text : List Char) : (escape text).length = text.length := by
  induction text with
  | nil => simp [escape]
  | cons c text ih => simp [escape, ih]

/-- The literal's scan consumes the text plus the closing quote, leaving the
trailing ``.``. -/
lemma drop_after_literal (text : List Char) :
    (escape text ++ ['"', '.']).drop (text.length + 1) = ['.'] := by
  induction text with
  | nil => simp [escape]
  | cons c text ih =>
      simp [escape, List.cons_append, Nat.add_assoc]
      exact ih

/-- **Correctness.**  For text with no literal backtick, ``"<escaped>".``
prints exactly that text. -/
theorem eval_correct (text : String) (hbt : '`' ∉ text.toList) :
    (run (prog text.toList) { ptr := 0, stk0 := [], stk1 := [], out := [] }).out
      = text.toList := by
  unfold prog
  have hscan := scan_aux text.toList [] hbt
  have hdrop := drop_after_literal text.toList
  simp [run, printValue, scanString, State.push, State.pop, hscan.1, hdrop]

-- Sanity: the escaped literal round-trips through the interpreter.
example : (run (prog "Hi".toList) { ptr := 0, stk0 := [], stk1 := [], out := [] }).out
    = "Hi".toList := by
  native_decide
example : (run (prog "say \"hi\" now".toList) { ptr := 0, stk0 := [], stk1 := [], out := [] }).out
    = "say \"hi\" now".toList := by
  native_decide

end EvalCorrect
