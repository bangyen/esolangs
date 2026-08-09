import Mathlib

set_option linter.unusedVariables false

/-! AlbaBet interpreter, ported from the Lean 3 ``extra/lean/albabet.lean``.

A tape language: ``a``/``b`` move an accumulator by ±1, ``c``/``d`` swap
it with 0 or with ``x``, ``e``/``f`` copy ``x`` into ``y`` or clear ``y``,
``g``/``h`` multiply ``y`` by ``x`` or square ``x``, and ``i`` prints the
accumulator as a character. -/

namespace Albabet

def file_name : String := "test.txt"

def read_file : IO String := do
  IO.FS.readFile file_name

def run (n : ℕ) (i : String.Legacy.Iterator) (c : Char)
    (x y : ℕ) (s : String) : IO Unit :=
  if n = 0 then
    IO.print s
  else if c = 'a' then
    run (n - 1) i.next i.next.curr (x + 1) y s
  else if c = 'b' then
    run (n - 1) i.next i.next.curr (x - 1) y s
  else if c = 'c' then
    run (n - 1) i.next i.next.curr 0 y s
  else if c = 'd' then
    run (n - 1) i.next i.next.curr 0 x s
  else if c = 'e' then
    run (n - 1) i.next i.next.curr x x s
  else if c = 'f' then
    run (n - 1) i.next i.next.curr x 0 s
  else if c = 'g' then
    run (n - 1) i.next i.next.curr (x * y) y s
  else if c = 'h' then
    run (n - 1) i.next i.next.curr (x * x) y s
  else if c = 'i' then
    run (n - 1) i.next i.next.curr x y (s ++ toString (Char.ofNat x))
  else
    run (n - 1) i.next i.next.curr x y s

#eval do
  let c ← read_file
  run c.length (String.Legacy.mkIterator c) c.front 0 0 ""
end Albabet
