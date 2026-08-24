# Example programs

This directory holds programs sampled from a *parameterized* generator, each
verified by `tests/test_examples.py` to run through the repo's interpreter and
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
changing the number.  Refresh both directories with:

```bash
python scripts/write_hello_world_examples.py
python scripts/write_boolean_examples.py
```

## hello-world

One `Hello, World!` program per language that the text generators
(`esolangs.tools.text`) support.  Each file is what its generator produces
for the text `Hello, World!`, wrapped as described above, so the
interpreter run is always correct;
`python scripts/write_hello_world_examples.py` refreshes the files after a
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
its generator produces today; `tests/test_examples.py` asserts that, and
`python scripts/write_boolean_examples.py` refreshes the files after a
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
  These are `arrowqueue`, `bfpda`, `bio`, `bitdeque`, `cod`, `eval`,
  `home-row`, `lamfunc`, `nocomment`, and `wii2d`.

Notes:

- `arrowqueue.txt` and `point-break.txt` produce no output at all: their
  result is the halt-vs-loop convention, so the committed program is the
  halting (`0`) branch.  The same table with both inputs one would loop
  forever instead, so the `1` branch is not executed.
- `cod.txt` is a two-input XOR with both inputs one, printing `0`.  COD has
  no runtime input and no I/O other than a printed number, so this is the
  whole boolean story for the language (see `docs/cod_boolean_generator.md`).
- `nevermind.txt` and `bitdeque.txt` print their bit followed by a newline.
- `container.txt` halts by exiting with status 0.
- `suffolk.txt` must be run with the loop count set to one.
- `minifuck.txt` is the one file no current generator produces: it is
  recorded from Minifuck's (now-removed) boolean generator that covered the
  0-preserving two-input tables, and is kept as a record of that
  construction, so it is exempt from the generator-match test.

Languages absent here are those whose boolean result is a machine state
rather than program output — Back's cell under the head, RAM0's and Minsky
Swap's register dumps, A Painter Ant's landing cell — and those with no
Python interpreter to run.  Their generators are covered by
`tests/tools/test_boolean.py` instead.

