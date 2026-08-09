import Mathlib

set_option linter.unusedVariables false

/-! EXCON interpreter, ported from the Lean 3 ``extra/lean/excon.lean``.

EXCON operates on an 8-cell bit pool plus a cell pointer.  ``:`` resets the
pool to zero and the pointer to the last cell (7); ``^`` flips the current
bit; ``!`` prints the pool as a binary number's character; ``<`` moves the
pointer down (with no bounds check, matching the reference Python
interpreter). -/

namespace Excon

def file_name : String := "test.txt"

def read_file : IO String := do
  IO.FS.readFile file_name

def empty_list : List ℕ := List.replicate 8 0

def gets (l : List ℕ) (n : ℕ) : ℕ :=
  l.getD n 0

def flips (l : List ℕ) (n : ℕ) : List ℕ :=
  l.set n ((gets l n + 1) % 2)

def to_s : List ℕ → ℕ → ℕ → String
  | l, 0, m => toString (Char.ofNat m)
  | l, n + 1, m => to_s l n (m + (2 ^ (6 - n)) * gets l (n + 1))

def run (m : ℕ) (i : String.Legacy.Iterator) (c : Char)
    (l : List ℕ) (n : ℕ) (s : String) : IO Unit :=
  if m = 0 then
    IO.print s
  else if c = ':' then
    run (m - 1) i.next i.next.curr empty_list 7 s
  else if c = '^' then
    run (m - 1) i.next i.next.curr (flips l n) n s
  else if c = '!' then
    run (m - 1) i.next i.next.curr l n (s ++ to_s l 7 0)
  else if c = '<' then
    run (m - 1) i.next i.next.curr l ((n - 1) % 8) s
  else
    run (m - 1) i.next i.next.curr l n s

#eval do
  let c ← read_file
  run c.length (String.Legacy.mkIterator c) c.front empty_list 7 ""
end Excon
