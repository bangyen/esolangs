# Contributing

Add stable, deterministic languages verifiable through this repository's I/O
model. They need a generator or a documented reason one is impossible; record
rejections in [limitations](limitations.md).

## Layout

- `src/esolangs/interpreters/`: interpreter modules and `run(code, io)`.
- `src/esolangs/tools/boolean/`: generators.
- `src/esolangs/registry.py`: the source of truth for public integration.
- `tests/`: interpreter and generator coverage.

## Change checklist

1. Start from the template; document actual input, error, and halt behavior.
2. Register the language and any generator in `registry.py`.
3. Add end-to-end tests; execute generated programs.
4. Run `just test`. Use `just test-full` for release-scale changes.

Preserve generated-file contracts and require an end-to-end capability.
