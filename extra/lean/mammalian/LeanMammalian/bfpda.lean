import Mathlib

set_option linter.unusedVariables false

/-! BF-PDA interpreter, ported from the Lean 3 ``extra/lean/bf-pda.lean``.

A brainfuck variant over a stack of bits (the top is the current cell).
``@`` flips the top bit, ``.`` prints the top bit as ``'0'``/``'1'``, ``<``
pushes a zero, ``>`` pops, and ``[``/``]`` loop on the top bit with the
bracket matching handled by ``find``.  ``limit`` bounds the instruction
count so the ``#eval`` always terminates. -/

namespace Bfpda

def file_name : String := "test.txt"
  -- name of the file containing the BF-PDA program
def limit : ℕ := 100
  -- max number of commands

def read_file : IO String := do
  IO.FS.readFile file_name

def list.pop (l : List ℕ) : List ℕ := l.reverse.tail.reverse
def list.top (l : List ℕ) : ℕ := l.reverse.head!

def list.flip (l : List ℕ) : List ℕ :=
  list.pop l ++ [(list.top l + 1) % 2]

/-- Walk the iterator from `j` (in the direction `b`) counting brackets:
`[` adds 1, `]` subtracts 1, stopping when the count returns to 0. -/
def find (i j : String.Legacy.Iterator) (c : Char) (b : Bool)
    (z : ℤ) (n : ℕ) : String.Legacy.Iterator :=
  if n = 0 then
    if b then j else j.next.next
  else if z = 0 then
    i.next
  else
    let x := if b then j.next else j.prev
    let k := if c = '[' then z + 1
      else if c = ']' then z - 1
      else z
    find i x x.curr b k (n - 1)

def run (i : String.Legacy.Iterator) (c : Char) (m : ℕ)
    (l : List ℕ) (s : String) : IO Unit :=
  if m = 0 then
    IO.print s
  else if c = '@' then
    run i.next i.next.curr (m - 1) (list.flip l) s
  else if c = '.' then
    run i.next i.next.curr (m - 1) l (s ++ (toString (Char.ofNat (48 + list.top l))))
  else if c = '<' then
    run i.next i.next.curr (m - 1) (l ++ [0]) s
  else if c = '>' then
    run i.next i.next.curr (m - 1) (list.pop l) s
  else if c = '[' then
    let j := i.next
    let x := if list.top l = 0 then
      find i j j.curr true 1 i.toString.length
      else j
    run x x.curr (m - 1) l s
  else if c = ']' then
    let j := i.prev
    let x := if list.top l = 1 then
      find i j j.curr false (0 - 1) i.toString.length
      else i.next
    run x x.curr (m - 1) l s
  else
    run i.next i.next.curr (m - 1) l s

#eval do
  let c ← read_file
  run (String.Legacy.mkIterator c) c.front limit [] ""
end Bfpda
