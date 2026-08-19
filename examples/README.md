# Example programs

This directory holds example programs, each verified by `tests/test_examples.py`
to run through the repo's interpreter and produce its expected output.

## hello-world

One `Hello, World!` program per language that the program generator
(`esolangs.tools.generate`) supports.  Each file is exactly what
`python -m esolangs.tools.generate` produces for the text `Hello, World!`, so
the interpreter run is always correct.

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
- Languages whose interpreters live in `extra/` (Forþ, LaserFuck, Magnitude,
  Painfuck, 123) have generators but no example here, since there is no Python
  interpreter to verify them against.

## cat

Echoes input to output, for a curated set of input-capable languages:

- `nevermind.txt` reads a line and prints it back (`print` adds a newline).
- `6-5.txt` reads one character and prints it (the language has no loop).
- `modulous.txt` reads a line, then pops and prints its characters.

## truth-machine

Outputs `0` and halts when given `0`, and outputs `1` forever when given `1`:

- `modulous.txt`, `brainif.txt`, `between.txt`, `circlefuck.txt`, and
  `factor.txt`.  The tests exercise only the terminating `0` branch; the `1`
  branch loops forever by definition.

## boolean

Demonstrates a language's boolean-function capability that is not an I/O
truth machine (see `docs/walls.md`):

- `minifuck.txt` is a committed two-input AND, recorded from Minifuck's
  (now-removed) boolean generator that covered the 0-preserving two-input
  tables, reading `0`/`1` input lines; the committed inputs `0 1` exercise
  the "one input zero" AND row.
- `arrowqueue.txt` is what
  `_instantiate_arrowqueue(arrowqueue("0001"), [0, 1])` produces — a
  two-input AND with one input zero, which halts (the `0` branch of the
  halt-vs-loop convention).  The same table with both inputs one would loop
  forever instead (the `1` branch is not executed).  This is the language's
  boolean convention (see `docs/walls.md`).

## multiply

Reads two sentinel-delimited decimal operands (the digits of the first, a
`*` line, the digits of the second, a `#` line) and prints their product:

- `jaune.txt` is what `esolangs.tools.boolean.jaune_multiply()` generates —
  Jaune's sentinel construction works for any operand length, which is why
  the multiply capability takes no digit-count parameter (see
  `docs/walls.md`).
