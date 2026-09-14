# Contributing

Add stable, deterministic languages verifiable through this repository's I/O
model.  Each needs a generator, or a documented reason one is impossible --
record rejections in [limitations](limitations.md).

Read the [architecture overview](architecture.md) for how registration,
generation, execution, and answer extraction connect.

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
