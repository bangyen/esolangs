import Mathlib

set_option linter.unusedVariables false

/-! 74 interpreter, ported from the Lean 3 ``extra/lean/74.lean``.

A one-bit tape language.  ``0``/``1`` push onto the output string, ``H``
writes an ``H`` only if the output already starts with ``0`` (the first
character written); once the output starts with ``H`` the program prints it
and halts, otherwise it restarts from the beginning.  ``limit`` bounds the
instruction count so the ``#eval`` always terminates. -/

namespace SeventyFour

def limit : ℕ := 100
  -- max number of commands

def run (i : String.Legacy.Iterator) (c : Char) (b : Bool)
    (n : ℕ) (s : String) : IO Unit :=
  if n = 0 then
    IO.print s
  else if s.front = 'H' then
    IO.print s
  else if c = '0' then
    run i.next i.next.curr i.hasNext (n - 1) ("0" ++ s)
  else if c = '1' then
    run i.next i.next.curr i.hasNext (n - 1) ("1" ++ s)
  else if c = 'H' then
    let x := if s.front = '0' then "H" else ""
    run i.next i.next.curr i.hasNext (n - 1) (x ++ s)
  else
    run i.next i.next.curr i.hasNext (n - 1) s

end SeventyFour
