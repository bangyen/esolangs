import Mathlib

set_option linter.unusedVariables false

/-! BF-PDA interpreter, ported from the Lean 3 ``extra/lean/bf-pda.lean``.

A brainfuck variant over a stack of bits (the top is the current cell).
``@`` flips the top bit, ``.`` prints the top bit as ``'0'``/``'1'``, ``<``
pushes a zero, ``>`` pops, and ``[``/``]`` loop on the top bit with the
bracket matching handled by ``find``.  ``limit`` bounds the instruction
count so the ``#eval`` always terminates. -/

namespace Bfpda

def limit : ℕ := 100
  -- max number of commands

def list.pop (l : List ℕ) : List ℕ := l.reverse.tail.reverse
def list.top (l : List ℕ) : ℕ := l.reverse.getD 0 0
  -- total (0 on an empty stack); the run loop checks `l.isEmpty` first

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

/-- A read of the top of an empty stack is an invalid operation (exit 3). -/
def empty : IO Nat := IO.eprint "empty stack\n" *> pure 3

def run (i : String.Legacy.Iterator) (c : Char) (m : ℕ)
    (l : List ℕ) (s : String) : IO Nat :=
  if m = 0 then
    IO.print s *> pure 0
  else if c = '@' then
    if l.isEmpty then empty
    else run i.next i.next.curr (m - 1) (list.flip l) s
  else if c = '.' then
    if l.isEmpty then empty
    else run i.next i.next.curr (m - 1) l (s ++ (toString (Char.ofNat (48 + list.top l))))
  else if c = '<' then
    run i.next i.next.curr (m - 1) (l ++ [0]) s
  else if c = '>' then
    if l.isEmpty then empty
    else run i.next i.next.curr (m - 1) (list.pop l) s
  else if c = '[' then
    if l.isEmpty then empty
    else
      let j := i.next
      let x := if list.top l = 0 then
        find i j j.curr true 1 i.toString.length
        else j
      run x x.curr (m - 1) l s
  else if c = ']' then
    if l.isEmpty then empty
    else
      let j := i.prev
      let x := if list.top l = 1 then
        find i j j.curr false (0 - 1) i.toString.length
        else i.next
      run x x.curr (m - 1) l s
  else
    run i.next i.next.curr (m - 1) l s

end Bfpda
