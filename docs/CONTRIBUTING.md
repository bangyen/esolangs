# Contributing

Add a language only when its specification is stable, deterministic, and verifiable through this repository's I/O model.

## Layout

- `src/esolangs/interpreters/`: interpreter modules and `run(code, io)`.
- `src/esolangs/tools/boolean/`: generators.
- `src/esolangs/registry.py`: the source of truth for public integration.
- `tests/`: interpreter and generator coverage.

## Change checklist

1. Start from the appropriate template and document actual input, error, and halt behavior.
2. Register the language and any generator in `registry.py`.
3. Add end-to-end tests.
4. Run `just test`.

Follow nearby style and preserve generated-file contracts.
