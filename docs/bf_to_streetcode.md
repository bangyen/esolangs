# brainfuck -> Streetcode: how the lowering is total

`brainfuck -> Streetcode` is a registered transpiler
(`src/esolangs/transpilers/_bf_streetcode.py`, in `TRANSPILERS` under the
admission contract in `src/esolangs/transpilers/transpilers.py`). It is
total over brainfuck and equivalent on every completed run, with no
residue. This records the two ideas that make it work; the code is the
reference.

## The one branch Streetcode offers is brainfuck's loop test

A Streetcode car drives a network of two-wide streets and runs the glyph
under it at each cell. Its only conditional is a *junction* -- a gap in a
wall -- which reads whether the cell under the pointer is zero and steers
one way or the other. That is exactly brainfuck's `[`/`]` test, so a
brainfuck loop draws as a **room**: a hollow island the car laps, re-testing
the cell each time round, and leaves when it reaches zero. Plain glyphs run
on the street; rooms nest to any depth because a room's body run has the
same relation to its island's north wall that the street has to its south
wall, so the drawing recurses. Six of brainfuck's eight commands map one to
one (`>`->`==`, `<`->`__`, `+`->`^`, `-`->`~`, `.`->`O`, `,`->`I`, on a
doubled tape where brainfuck cell `i` is Streetcode cell `2i` and the odd
cells are steering scratch); `[` and `]` are the room.

## The wraparound is removed before the drawing, not during it

Streetcode cells are unbounded signed integers with no byte wraparound and
no left clamp built in (`_` at cell 0 saturates). brainfuck's are 8-bit
wrapping. If the two languages ran the same glyphs, a `+` past 255, a `-`
below 0, or a `,` of a code point above U+00FF would leave Streetcode
holding a value brainfuck never would -- and `O` on a negative or huge value
is a runtime error where brainfuck prints a byte.

Rather than teach the geometry to model wraparound, the transpiler rewrites
brainfuck to brainfuck first (`_lower`): every maximal `+`/`-` run and every
`,` is followed by a **canonicalizer** that reduces the cell mod 256. The
canonicalizer is the standard brainfuck divmod-by-256 idiom, chosen for two
properties that let it lower to geometry unchanged:

- it uses **no wraparound of its own** and keeps every cell `>= 0`
  throughout, so the drawing never has to reproduce a negative or oversized
  cell; and
- its loops **park the pointer on a cell they have just driven to zero** -- a
  loop that runs at most once is an `if` -- so it needs nothing beyond the
  room the geometry already draws. There is no special "if-zero" gadget.

The rewrite widens the tape to stride 8 (brainfuck cell `i` -> cell `8i`;
`>`/`<` -> `>`*8/`<`*8) so each canonicalizer's four scratch cells sit in the
gap `8i+1 .. 8i+4` and can never collide with the next data cell. The
geometry pass then doubles again for its own steering scratch, so a source
cell lands at Streetcode cell `16i`. Widening a disjoint scratch region is
what makes the two passes compose with no ordering constraint between
gadgets.

Because the canonicalizer is a *fixed* fragment per arithmetic run --
independent of the run's magnitude -- the output is linear in program size:
`+`*49 costs the same three-loop fragment a single `-` does. (An earlier,
abandoned approach expanded `+` into 255 copies of a wrap gadget; it was
correct but its grids grew with cell magnitude, and a single mid-size
multiply took minutes to run.)

## No residue

brainfuck and Streetcode agree on every observable once the cell values are
canonicalized:

- a blank input line reads 0 through both (`,` and `I` alike);
- exhausted input raises `EOFError` in both;
- `,`/`I` of a code point above U+00FF is reduced mod 256 in both -- the
  canonicalizer does it on the brainfuck side, and both languages already
  agree below 256;
- `.`/`O` print `chr(cell)`.

So the transpiler carries no divergence clause. Verified by a pinned battery
and a seeded differential fuzz in `tests/tools/test_transpilers.py`, both
running the two interpreters and comparing output; the battery pins the
cases the doubled non-wrapping model has to reproduce (underflow, overflow
inside a loop, a wrapping multiply, a pointer-moving loop body, `,` above
U+00FF, a skipped loop, and deep nesting).
