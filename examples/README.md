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

- `modulous.txt` and `brainif.txt`.  The tests exercise only the terminating
  `0` branch; the `1` branch loops forever by definition.
- `minifuck.txt` echoes the input bit (its identity boolean function) and
  halts; Minifuck's generator has no looping branch, so the file is a
  boolean-function truth table rather than a loop-on-1 machine.
- `arrowqueue.txt` is the halt-vs-hang ring template: the committed program
  is the `0` branch (halts on an empty-queue pop), and replacing the center
  cell's space with `~` makes the ring hang forever — the `1` branch.  This
  is the language's boolean convention (see `docs/walls.md`).

## multiply

Reads two sentinel-delimited decimal operands (the digits of the first, a
`*` line, the digits of the second, a `#` line) and prints their product:

- `jaune.txt` is what `esolangs.tools.boolean.jaune_multiply()` generates —
  Jaune's sentinel construction works for any operand length, which is why
  the multiply capability takes no digit-count parameter (see
  `docs/walls.md`).
