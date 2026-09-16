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
  walk (`laserfuck`, `wii2d`, `a_painter_ant`, `streetcode`).
- **Branch mechanism** -- explicit conditional, value-testable jump, skip
  guard, implicit comparator, pointer displacement (`123`).
- **Answer convention** -- print 0/1, landing colour (`a_painter_ant`),
  position-encoded (`minifuck`), decimal accumulator (`%^2^-1`),
  termination as the answer (`123`, ArrowQueue, Point Break).
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
| `src/esolangs/registry.py` | the source of truth for public integration |
| `tests/` | interpreter and generator coverage |

## Checklist

1. Start from the template; document actual input, error and halt behaviour.
2. Register the language and any generator in `registry.py`.
3. Add end-to-end tests, and execute the generated programs.
4. Run `just test`; `just test-full` for release-scale changes.

Preserve generated-file contracts, and require an end-to-end capability.
