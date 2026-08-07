# Contributing

## Layout

- `src/esolangs/interpreters/<category>/<name>.py` — one interpreter per
  language, each exposing `run(code)`. Categories are `tape_based`,
  `stack_based`, `register_based`, and `other`. Copy
  `src/esolangs/interpreters/_template.py` to start; it encodes the I/O
  conventions.
- `src/esolangs/tools/generate.py` — text generators. Each `def <name>(text)`
  returns a program whose output is exactly `text`.
- `src/esolangs/tools/boolean.py` — truth-table generators for languages with
  input and value branching.
- `src/esolangs/registry.py` — the single source of truth: which languages
  have a generator, an interpreter, and how programs are handed to the
  interpreter. The public API and the test tables derive from it.
- `src/esolangs/__init__.py` — the public API (`generate`, `run`,
  `list_languages`); `src/esolangs/cli.py` — the `esolangs` command.
- `scripts/` — verification tooling (unicorn/qemu/simulator checks).

## Adding a language

1. **Interpreter** — copy `_template.py` into the right category and fill in
   the dispatch. The `run(code)` interface, the `input("\nInput: "[new:])`
   convention, and the `__main__` block are all in the template. Keep the
   interpreter self-contained and untyped (mypy exempts the legacy modules).
2. **Generator** (optional) — add `def <name>(text)` to `generate.py` and
   register it in `registry.py`. If the language reads input and branches,
   add a truth-table generator to `boolean.py`.
3. **Registry** — add a `Language` entry in `registry.py` (display name,
   generator, interpreter module, whether the program is split into lines,
   extra `run()` kwargs). This single entry wires up the API and the tests.
4. **Tests** — add a round-trip test in `tests/tools/test_generate.py`. The
   fuzz (`tests/test_fuzz_generators.py`) and example (`tests/test_examples.py`)
   tables derive from the registry automatically; add a committed program
   under `examples/hello-world/<name>.txt` if the language has a generator.
5. **Verification** — run the interpreter on the generated program for a
   range of texts, then run the full suite.

## Verifying changes

    python scripts/verify.py

runs pre-commit, pytest, and the emulation checks locally. The native x86
and qemu steps are CI-only (Linux).

## Conventions

- The public modules (`esolangs`, `registry`, `exceptions`, `cli`) must be
  typed and documented; the legacy interpreters/generators/compilers are
  grandfathered from strict typing and docstring rules and can be annotated
  incrementally.
- New code must pass ruff (`SIM`/`RUF`/`PT`/`D` rule sets are enabled), black,
  and mypy.
- Tests must keep line coverage at 100% (the coverage-badge CI job enforces
  it).
