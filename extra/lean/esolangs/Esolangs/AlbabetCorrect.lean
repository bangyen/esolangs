import Mathlib
import Esolangs.Albabet

/-! Correctness of the AlbaBet text generator

AlbaBet is a two-register language: ``x`` (the accumulator) and ``y`` both
start at 0, ``a`` moves ``x`` up by one, ``c`` zeroes ``x``, and ``i`` prints
``Char.ofNat x``.  The generator ``src/esolangs/tools/generators/register.py::albabet``
emits, for each byte ``v``, the program ``c`` followed by ``v`` copies of
``a`` followed by ``i``: ``c`` zeroes the accumulator, the ``a`` run moves it
up to ``v``, and ``i`` prints the byte.  This file proves the program is
*correct*: for every byte-range text it prints exactly that text.

As with ``ExconCorrect``, ``step``/``runList`` below are the ported
interpreter's own pure state transitions (``Esolangs/Albabet.lean``) over a
``(x, y, out)`` state, so the theorem certifies the ported interpreter
itself.  The proof has three parts:

  1. **The ``a`` run.**  ``v`` copies of ``a`` add ``v`` to the accumulator,
     regardless of where it started (``runList_replicate_a``).
  2. **One character.**  ``c`` zeroes the accumulator, so the ``a`` run sets
     it to exactly ``v`` and ``i`` appends ``Char.ofNat v`` to the output;
     ``y`` is never touched (``run_charProgC``).
  3. **The whole text.**  Every character's program preserves ``y`` and only
     appends, so the text's programs concatenate their outputs
     (``runList_textProg``).

The main theorem is stated for ``List Char`` texts whose codes are all below
256 (the generator rejects larger codepoints with a documented
``ValueError``).
-/

namespace AlbabetCorrect

set_option linter.unusedVariables false

open Albabet

/-! ### 1. A pure interpreter with the ported state transitions -/

abbrev State := ℕ × ℕ × String

/-- One instruction, exactly the ``Albabet.run`` transition on that
character: ``a``/``b`` move ``x`` by +1 or -1 (``b`` clamping as a natural
number), ``c``/``d`` set ``x`` to 0 (``d`` parking the old ``x`` in ``y``),
``e``/``f`` copy ``x`` into ``y`` or clear ``y``, ``g``/``h`` multiply ``x``
by ``y`` or square ``x``, ``i`` prints ``x`` as a character. -/
def step (st : State) (c : Char) : State :=
  let (x, y, s) := st
  if c = 'a' then (x + 1, y, s)
  else if c = 'b' then (x - 1, y, s)
  else if c = 'c' then (0, y, s)
  else if c = 'd' then (0, x, s)
  else if c = 'e' then (x, x, s)
  else if c = 'f' then (x, 0, s)
  else if c = 'g' then (x * y, y, s)
  else if c = 'h' then (x * x, y, s)
  else if c = 'i' then (x, y, s ++ toString (Char.ofNat x))
  else st

/-- Run a list of instructions from a state. -/
def runList (prog : List Char) (st : State) : State :=
  prog.foldl step st

/-- The output of an AlbaBet program run from the reset state. -/
def exec (prog : List Char) : String :=
  (runList prog (0, 0, "")).2.2

lemma runList_nil (st : State) : runList [] st = st := rfl

lemma runList_cons (c : Char) (rest : List Char) (st : State) :
    runList (c :: rest) st = runList rest (step st c) := rfl

lemma runList_append (l1 l2 : List Char) (st : State) :
    runList (l1 ++ l2) st = runList l2 (runList l1 st) := by
  unfold runList
  rw [List.foldl_append]

/-! ### 2. The emitted instruction sequence -/

/-- One character's program: ``c`` zeroes the accumulator, ``v`` copies of
``a`` move it up to ``v``, ``i`` prints. -/
def charProg (v : ℕ) : List Char :=
  'c' :: (List.replicate v 'a' ++ ['i'])

def charProgC (c : Char) : List Char := charProg c.toNat

def textProg : List Char → List Char
  | [] => []
  | c :: cs => charProgC c ++ textProg cs

/-! ### 3. The ``a`` run -/

/-- ``v`` copies of ``a`` add ``v`` to the accumulator, leaving ``y`` and the
output untouched. -/
lemma runList_replicate_a (v x : ℕ) (y : ℕ) (s : String) :
    runList (List.replicate v 'a') (x, y, s) = (x + v, y, s) := by
  induction v generalizing x with
  | zero => simp [runList]
  | succ v ih =>
      rw [List.replicate_succ]
      rw [runList_cons]
      simp [step]
      rw [ih (x + 1)]
      apply Prod.ext
      · omega
      · rfl

/-! ### 4. One character -/

/-- ``c`` zeroes the accumulator; the ``a`` run sets it to ``v``; ``i``
prints ``Char.ofNat v``.  ``y`` and ``x``'s start value are never used. -/
lemma run_charProg (v x : ℕ) (y : ℕ) (s : String) :
    runList (charProg v) (x, y, s) = (v, y, s ++ toString (Char.ofNat v)) := by
  unfold charProg
  rw [runList_cons]
  rw [show step (x, y, s) 'c' = (0, y, s) by simp [step]]
  rw [runList_append]
  rw [runList_replicate_a v 0 y s]
  norm_num
  rw [runList_cons]
  rw [show step (v, y, s) 'i' = (v, y, s ++ toString (Char.ofNat v)) by simp [step]]
  rw [runList_nil]

/-- One character's program prints exactly that character (appending its
``toString`` to the output). -/
lemma run_charProgC (c : Char) (x y : ℕ) (s : String) :
    runList (charProgC c) (x, y, s) = (c.toNat, y, s ++ toString (Char.ofNat c.toNat)) := by
  unfold charProgC
  exact run_charProg c.toNat x y s

/-! ### 5. The whole text -/

lemma String.ofList_cons (c : Char) (cs : List Char) :
    String.ofList (c :: cs) = toString c ++ String.ofList cs := by
  rw [← String.toList_inj]
  have hc : (toString c).toList = [c] := by
    rw [show toString c = String.singleton c by rfl]
    simp
  simp [hc, String.toList_ofList, String.toList_append]

lemma runList_textProg (t : List Char) (ht : ∀ c ∈ t, c.toNat < 256)
    (x y : ℕ) (s : String) :
    ∃ x', runList (textProg t) (x, y, s) = (x', y, s ++ String.ofList t) := by
  induction t generalizing x y s with
  | nil =>
      refine ⟨x, ?_⟩
      simp [textProg, runList_nil]
  | cons c cs ih =>
      rw [textProg]
      rw [runList_append]
      rw [run_charProgC c x y s]
      rcases ih (fun c' hc' => ht c' (by simp [hc']))
          c.toNat y (s ++ toString (Char.ofNat c.toNat)) with ⟨x', h⟩
      refine ⟨x', ?_⟩
      rw [h]
      rw [Char.ofNat_toNat]
      rw [String.ofList_cons]
      rw [String.append_assoc]

/-- **Correctness.**  For every byte-range text the generated AlbaBet program
prints exactly that text. -/
theorem exec_correct (t : List Char) (ht : ∀ c ∈ t, c.toNat < 256) :
    exec (textProg t) = String.ofList t := by
  unfold exec
  rcases runList_textProg t ht 0 0 "" with ⟨x, h⟩
  rw [h]
  simp

end AlbabetCorrect
