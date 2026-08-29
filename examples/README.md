# Example programs

This directory holds programs sampled from a *parameterized* generator, each
verified by `tests/scripts/test_examples.py` to run through the repo's interpreter and
produce its expected output.  Every file is exactly what its generator
produces today, and a companion test asserts that — the check is meaningful
precisely because the generator takes arguments and could produce something
else.

Fixed programs with no such space (cat, truth-machine, multiply) are test
fixtures rather than examples: a generator with no arguments would just be the
file wrapped in a function, and a sync test for it would assert a constant
equals itself.  Those live inline in the matching
`tests/interpreters/test_*.py`.

The committed files are wrapped to 80 columns so a long program stays
readable in a diff.  The wrap breaks only between whole commands, so the
program still means exactly the same thing, and the sync tests compare
against the wrapped form character for character rather than ignoring
newlines.  Languages whose newlines are semantic (the 2D grid ones) or that
reject them (NoComment) are committed unwrapped, as is any single token
longer than the width — a Polynomial coefficient cannot be split without
changing the number.

The three subleq-family OISCs (AddSubJump, Decleq, S*bleq) go one step
further and are laid out as a *grid*: each token is right-aligned in a
fixed-width cell, so the columns line up from one row to the next and a
changed operand stays in its column instead of shifting every token after
it.  The cell follows the program's own tokens rather than being fixed, and
a token too wide for one cell spans as many whole cells as it needs — the
ten-character jump sentinels in `boolean/decleq.txt` take three cells each
— so the tokens after it on the row still start on a cell boundary.  The
padding is only whitespace: these interpreters split on whitespace runs, so
a gridded program means exactly what it did unpadded.

BIO is laid out by *nesting* for the same reason, where it has any.  Its
boolean generator nests one loop per truth-table row, so `boolean/bio.txt`
is a telescoping chain of `0ix{ 1ox; ... };` levels — the shape its
generator's docstring describes, and the thing worth seeing in the file.
Packed flat to a width it read as one undifferentiated run, so a nested
program is now indented two spaces per level, with the straight `0oy;` runs
between levels still packed to whatever width the indent leaves them.
`hello-world/bio.txt` is a flat sequence of depth-1 groups where indenting
would show nothing packing does not, so it stays packed; the layout applies
only from two levels down.  The indent is whitespace *between* commands, and
a BIO command is a triple with the `;` that ends it (or, for a loop, the `{`
that opens its body), so no break ever lands inside one and an indented
program means exactly what the packed one did.

Refresh both directories with:

```bash
python scripts/write_examples.py
```

## hello-world

One `Hello, World!` program per language that the text generators
(`esolangs.tools.text`) support.  Each file is what its generator produces
for the text `Hello, World!`, wrapped as described above, so the
interpreter run is always correct;
`python scripts/write_examples.py hello-world` refreshes the files after a
generator changes.

Run a program with the language's interpreter, e.g.:

```bash
python -m esolangs.interpreters.register_based.sophie examples/hello-world/sophie.txt
```

Notes:

- `nevermind.txt` outputs `Hello, World!` followed by a newline (the language's
  `print` always adds one).
- `suffolk.txt` prints the text in one cycle; run it with the loop count set to
  one (`python -m esolangs.interpreters.tape_based.suffolk examples/hello-world/suffolk.txt 1`).
- `container.txt` halts by exiting with status 0.
- Some languages have a second, non-Python implementation under `extra/`
  (Forþ, LaserFuck, Painfuck, 123 in `extra/rust/`).  These still have an
  example here, verified against the Python interpreter like every other; the
  `extra/` version is an additional implementation, not the only one.

## boolean

One program per language whose boolean-function capability can be verified
end to end — the capability that is not an I/O truth machine (see
`docs/walls.md`).  Like the hello-world examples, each file is exactly what
its generator produces today; `tests/scripts/test_examples.py` asserts
that, and `python scripts/write_examples.py boolean` refreshes the files
after a
generator changes.

`esolangs.tools.boolean.examples` is the single source of truth: it records
for each program the generator, the truth table, and the input combination
that produced it.  Most are two-input AND (`0001`) run with the inputs
`0 1`, so the program prints `0`; a few use XOR (`0110`), and the notes
below cover the ones that differ.

Two kinds of generator appear here:

- **Input-reading** languages take their bits on stdin as `0`/`1` lines.
- **Parameterized** languages have no input mechanism, so the bits are
  embedded in the program text by substitution (see
  `esolangs.tools.boolean.parameterized`); they read nothing at run time.
   These are `arrowqueue`, `bf-pda`, `bio`, `bitdeque`, `cod`, `eval`,
   `home-row`, `lamfunc`, `nocomment`, and `wii2d`.

Notes:

- `arrowqueue.txt` and `point-break.txt` produce no output at all: their
  result is the halt-vs-loop convention, so the committed program is the
  halting (`0`) branch.  The same table with both inputs one would loop
  forever instead, so the `1` branch is not executed.
- `cod.txt` is a two-input XOR with both inputs one, printing `0`.  COD has
  no runtime input and no I/O other than a printed number, so this is the
  whole boolean story for the language (see `esolangs.tools.boolean.cod`).
- `nevermind.txt` and `bitdeque.txt` print their bit followed by a newline.
- `container.txt` halts by exiting with status 0.
- `suffolk.txt` must be run with the loop count set to one.
- `minifuck.txt` is the one file no current generator produces: it is
  recorded from Minifuck's (now-removed) boolean generator that covered the
  0-preserving two-input tables, and is kept as a record of that
  construction, so it is exempt from the generator-match test.

Languages absent here are those with no Python interpreter to run or
no boolean generator (`%^2^-1`, `123`, `SLOW ACV MAMMALIAN`).  Their
generators (if any) are covered by the `tests/tools/test_boolean_*.py` modules instead.
Every boolean generator whose answer is recoverable from what the program
prints — including those that dump state (`RAM0`'s `z`, `Minsky Swap`'s
second register) or paint (`A Painter Ant`'s `o`/`@`, `Back`'s answer
cell) — has a committed example.

