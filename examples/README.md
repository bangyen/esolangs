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
