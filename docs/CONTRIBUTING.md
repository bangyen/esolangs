# Contributing

Add a language only when its specification is stable, deterministic, and
verifiable through this repository's I/O model. It needs a useful generator
story or a documented structural reason one is impossible. Do not add command
renames, incomplete specifications, or languages already implemented
elsewhere. Record rejected candidates in [limitations](limitations.md).

## Layout

- `src/esolangs/interpreters/`: interpreter modules and `run(code, io)`.
- `src/esolangs/tools/text/` and `boolean/`: generators.
- `src/esolangs/registry.py`: the source of truth for public integration.
- `tests/`: interpreter and generator coverage.

## Change checklist

1. Start from the appropriate template and document actual input, error, and
   halt behavior.
2. Register the language and any generator in `registry.py`.
3. Add end-to-end tests. Execute generated programs; source text alone is not
   evidence.
4. Run `just test`. Use `just test-full` for release-scale changes.

Follow nearby style and preserve generated-file contracts. Do not add a
language merely because a parser can be written: the repository values a
verifiable, end-to-end capability.
