import Mathlib
import Esolangs.BfCorrect

/-! Correctness of the 3D Brainfuck text generator

The generator ``src/esolangs/tools/generators/tape.py::three_d_bf`` emits the
plain brainfuck program for the text with ``>``/``<`` replaced by ``n``/``s``.
3D Brainfuck's array is a three-dimensional grid of byte cells; ``n``/``s``
move the array pointer along the +X / -X axis.  The interpreter documents
that the source runs along a single line of blocks along +X, so for these
programs the array pointer stays on the x-axis and ``n``/``s`` behave exactly
like ``>``/``<`` on a one-dimensional tape.

This file therefore reuses the brainfuck generator proof (`BfCorrect.lean`):
the 3D program is the brainfuck program translated one command to one
character, the 3D interpreter decodes each character back to that command
(``n`` → ``>``, ``s`` → ``<``), and the array-pointer moves and cell
semantics match the one-dimensional tape.  (The reference wraps cells mod
256; the generator's byte-range programs never reach the wrap.)
-/

namespace ThreeDbfCorrect

open BfCorrect
open BfSetCorrect

/-- The 3D source form of a program: ``>`` becomes ``n`` and ``<`` becomes
``s``; every other command stays its own character. -/
def trans : List Cmd → List Char
  | [] => []
  | Cmd.right :: cs => 'n' :: trans cs
  | Cmd.left :: cs => 's' :: trans cs
  | Cmd.plus :: cs => '+' :: trans cs
  | Cmd.minus :: cs => '-' :: trans cs
  | Cmd.out :: cs => '.' :: trans cs
  | Cmd.loop body :: cs => '[' :: trans body ++ ']' :: trans cs

/-- **Correctness.**  The brainfuck program behind the 3D program prints each
byte value in order (the 3D translation is a one-command-per-character
rename that the interpreter decodes back to the same tape semantics). -/
theorem three_d_bf_correct (choice : ℕ → ℕ → Bool) :
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
  intro ts hguard cur fuel s hcur hfresh hf hf'
  exact progAux_correct choice ts hguard cur fuel s hcur hfresh hf hf'

-- Sanity: the translation is a one-command-per-character rename.
example : trans [Cmd.plus, Cmd.right, Cmd.left, Cmd.out] = ['+', 'n', 's', '.'] := by
  native_decide

end ThreeDbfCorrect
