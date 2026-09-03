# Example programs

Programs sampled from a *parameterized* generator, verified by
`tests/scripts/test_examples.py` to run through the repo's interpreter and
produce the expected output.  Each file is exactly what its generator
produces today; a sync test asserts that.

Fixed programs with no such space (cat, truth-machine, multiply) are test
fixtures, not examples, and live inline in the matching
`tests/interpreters/test_*.py`.

Committed files are wrapped to 80 columns, breaking only between whole
commands, so the sync tests compare wrapped form character for character.
Languages with semantic newlines (2D grid ones) or that reject them
(NoComment) are committed unwrapped, as is any token longer than the width.

AddSubJump, Decleq, and S*bleq are laid out as a *grid*: each token is
right-aligned in a fixed-width cell so a changed operand stays in its
column.  BIO is laid out by *nesting*, one indent level per truth-table
loop depth (`hello-world/bio.txt` has only depth-1 groups, so it stays
packed). Both layouts are whitespace-only and mean exactly what the
unpadded/unindented form did.

Refresh both directories with:

```bash
python scripts/write_examples.py
```

## hello-world

One `Hello, World!` program per language that the text generators
(`esolangs.tools.text`) support.  `python scripts/write_examples.py
hello-world` refreshes the files after a generator changes.

Run a program with the language's interpreter, e.g.:

```bash
python -m esolangs.interpreters.register_based.sophie examples/hello-world/sophie.txt
```

Notes:

- `nevermind.txt` outputs `Hello, World!` followed by a newline (the language's
  `print` always adds one).
- `suffolk.txt` prints the text in one cycle and halts on its own via cycle
  detection: `python -m esolangs.interpreters.tape_based.suffolk examples/hello-world/suffolk.txt`.
- `container.txt` halts by exiting with status 0.
- Some languages have a second, non-Python implementation under `extra/`
  (NoComment, BF-PDA, RAM0, BIO, Minsky Swap in `extra/assembly/`).  These
  still have an example here, verified against the Python interpreter like
  every other; the `extra/` version is an additional implementation, not the
  only one.

## boolean

One program per language whose boolean-function capability can be verified
end to end — the capability that is not an I/O truth machine (see
`docs/walls.md`).  Each file is exactly what its generator produces today;
`tests/scripts/test_examples.py` asserts that, and `python
scripts/write_examples.py boolean` refreshes the files after a generator
changes.

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
   These are `a-painter-ant`, `arrowqueue`, `back`, `bf-pda`, `bio`,
   `bitdeque`, `cod`, `eval`, `home-row`, `lamfunc`, `minsky-swap`,
   `nocomment`, `ram0`, and `wii2d` (the `_embedded` entries in
   `esolangs.tools.boolean.examples`).

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
- `suffolk.txt` halts on its own via cycle detection after one pass.
- `minifuck.txt` is the one file no current generator produces: it is
  recorded from Minifuck's (now-removed) boolean generator that covered the
  0-preserving two-input tables, and is kept as a record of that
  construction, so it is exempt from the generator-match test.

Languages absent here (`%^2^-1`, `123`, `SLOW ACV MAMMALIAN`) have both an
interpreter and a boolean generator in the registry, but no entry in
`esolangs.tools.boolean.examples`, so no committed file exists yet.  Their
generators are covered by the `tests/tools/test_boolean_*.py` modules
instead.

An answer does not have to be printed to count: the languages that dump state
(`RAM0`'s `z`, `Minsky Swap`'s second register) or paint it (`A Painter Ant`'s
`o`/`@`, `Back`'s answer cell) all have committed examples.

