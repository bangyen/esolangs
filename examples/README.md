# Example programs

Programs sampled from a *parameterized* generator, verified by
`tests/scripts/test_examples.py` to run through the repo's interpreter and
produce the expected output.  Each file must be exactly what its generator
produces; a sync test asserts that.

Fixed programs with no such space (cat, truth-machine, multiply) are test
fixtures, not examples, and live inline in the matching
`tests/interpreters/test_*.py`.

Committed files are wrapped to 80 columns, breaking only between whole
commands, so the sync tests compare wrapped form character for character.
Languages with semantic newlines (2D grid ones) or that reject them
(NoComment) must be committed unwrapped, as must any token longer than the
width.

AddSubJump, Decleq, and S*bleq must be laid out as a *grid*: each token
right-aligned in a fixed-width cell so a changed operand stays in its
column.  BIO must be laid out by *nesting*, one indent level per
truth-table loop depth.  Both layouts are whitespace-only and must mean
exactly what the unpadded/unindented form would.

Refresh both directories with:

```bash
python scripts/write_examples.py
```

## hello-world

One `Hello, World!` program per language supported by the text generators
(`esolangs.tools.text`).  Run a program with the language's interpreter,
e.g.:

```bash
python -m esolangs.interpreters.register_based.sophie examples/hello-world/sophie.txt
```

A language may have a second, non-Python implementation under `extra/`;
that version is an additional implementation, verified against the Python
interpreter like every other, not a replacement for the example here.

## boolean

One program per language whose boolean-function capability can be verified
end to end — the capability that is not an I/O truth machine (see
`docs/walls.md`).

`esolangs.tools.boolean.examples` is the single source of truth: it records
for each program the generator, the truth table, and the input combination
that produced it.

Two kinds of generator appear here:

- **Input-reading** languages take their bits on stdin as `0`/`1` lines.
- **Parameterized** languages have no input mechanism, so the bits are
  embedded in the program text by substitution (see
  `esolangs.tools.boolean.parameterized`); they read nothing at run time.

A language with an interpreter and a boolean generator in the registry but
no entry in `esolangs.tools.boolean.examples` has no committed file; its
generator is covered by the `tests/tools/test_boolean_*.py` modules
instead.

An answer does not have to be printed to count: a language that dumps state
or paints it onto the tape/grid can still have a committed example here.
