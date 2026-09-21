# Contributing

Add stable, deterministic languages verifiable through this repository's I/O
model.  Each needs a generator, or a documented reason one is impossible --
record rejections in [limitations](limitations.md).

Read the [architecture overview](architecture.md) for how registration,
generation, execution, and answer extraction connect.

## What makes a candidate worth adding

A language earns a place by forcing a point the existing set does not
already occupy.  Four axes, with what currently sits on each:

- **Construction shape** -- decision tree (the default), minterm sum
  (`circuit_diagram`), ANF/XOR-of-products (`fargo`, the only one), grid
  walk (`laserfuck`, `a_painter_ant`, `streetcode`).
- **Branch mechanism** -- explicit conditional, value-testable jump, skip
  guard, implicit comparator, pointer displacement (`123`).
- **Answer convention** -- print 0/1, landing colour (`a_painter_ant`),
  position-encoded (`minifuck`),
  termination as the answer (`123`, ArrowQueue, Crement, Vandevelo).
- **Input interface** -- read-and-route, bit-addressable index (`fargo`),
  parameterized embed.

This is an admission test.  The removal test is different and is recorded
under Curation in [limitations](limitations.md): a language can be dropped
for being an ordinary imperative language in costume, or for sharing a
generator shim with no downstream consumer, however novel it looked going
in.

## Layout

| Path | Holds |
| --- | --- |
| `src/esolangs/interpreters/` | interpreter modules and `run(code, io)` |
| `src/esolangs/tools/` | generators |
| `src/esolangs/registry/` | the source of truth for public integration |
| `tests/` | interpreter and generator coverage |

## Interpreter conventions

`src/esolangs/interpreters/_template.py` is the starting point.  Every
interpreter:

- Exposes `run(code, io)` with a required `IO` (grid languages get
  `split=True` in the registry and receive lines).  Prints and reads
  through `io`; never `print`/`input`.
- Raises `ValueError` for a malformed program and `HaltError` for an
  invalid runtime operation, and terminates by construction: the fuzz
  suites feed random and empty programs.
- Guards an input line before indexing it (`if val:`); an empty line is
  legal, and running out raises `EOFError` either way.
- Keeps the run state in a class named `_Machine` with `step()`, `halted`
  and `snapshot()` (the complete state, input cursor included).  The name
  is looked up by the tests: when `dimensional.py` used it for something
  else the language was silently skipped.
- Writes the language as a pure transition (`_advance`) over an immutable
  state, with `step` as the shell doing the I/O; a store that cannot be
  threaded cheaply returns effects instead (`grapheme.py`).
- Documents decisions for genuine spec gaps in the module docstring
  (`suffolk.py` shows one), never to define away invalid operations.
- Provides a `__main__` block calling `run(data, IO())`.

`tests/test_interpreter_conventions.py` checks the module docstring starts
`Interpreter for <Language>.` and mentions `EOF`, `HaltError` or
`ValueError` wherever the interpreter reads input or raises them.

## Checklist

1. Run `just new-language "Name" --category tape_based` (using the matching
   category), then replace the placeholder semantics and test.
2. Register the language and any generator in `registry/_table.py`.
3. Add end-to-end tests, and execute the generated programs.
4. Record generator evidence with `just benchmark "Name" TABLE`; compare
   `source_units` and `commands`, not wall-clock time.
5. Regenerate docs, then run `just test`; `just test-full` for release-scale
   changes.

Preserve generated-file contracts, and require an end-to-end capability.
