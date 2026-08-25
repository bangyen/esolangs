# Contributing

## Is a language worth adding?

Not every language on the esolangs wiki belongs in this repo; the
assessed-and-rejected ledger in `docs/limitations.md` records the concrete
cases that were assessed and rejected.  A language is a candidate if it
meets all of these:

- **Complete, stable specification.**  The wiki page must fully define the
  commands and behavior.  A stub, a work-in-progress, an "in-development"
  definition, or a spec whose own author warns is unfinished does not give
  enough to verify an interpreter against (Chainlang, Fourfuck, Aaargh++,
  Binary ///, Welcome To...).
- **Deterministic, computable behavior.**  A program must have a definite
  result the tests can check.  Uncomputable languages (Gravity, something
  positive, Varigen) and languages whose commands are irreducibly random
  (LogicF---) cannot be verified.  *Seeded* randomness is fine — LaserFuck's
  initial heading and DSDLAI's are drawn from a seed the tests fix, so
  behavior stays checkable.
- **A usable file-based I/O protocol.**  The language must read input and
  write output as characters/lines through the repo's `IO` seam (see the
  interpreter conventions in `docs/limitations.md`).  Languages with no
  output (State and Main, Vandevelo), stderr-only output
  (Conveyor), or file/OS-based I/O (Unary Filesystem, Streetcode) do not
  fit.  A no-output language is admitted only as a self-contained
  interpreter with no generator — with one exception: Point Break was
  admitted with the first *termination-convention* boolean generator
  (halt for 0, loop for 1; see `docs/walls.md`), which the wiki's own
  truth-machine example defines and its Turing-complete arithmetic makes
  fully general.
- **A generator story.**  Either a boolean generator, or a text generator
  that can emit arbitrary bytes, or a documented reason the language cannot
  have one.  A text generator must exercise the language's computation
  (arithmetic encoding, bit manipulation, data-dependent construction), not
  merely embed the text as a literal: a literal-embed text generator is only
  a generator story when the language also has a boolean generator.  The
  generator is what makes the language testable end-to-end; a language with
  no plausible generator is a weaker addition.  A documented wall excuses
  the missing generator only when the language's output is still
  spec-defined and verifiable by hand; a language whose only observable
  result is an interpreter-invented state dump (no language-defined output
  at all) is admitted only as a self-contained interpreter, and is a
  standing candidate for removal.  A language with no data-dependent
  control flow (no input, or no conditional, so output is a fixed function
  of the program text) is likewise a standing removal candidate even with a
  computational text generator, since its boolean generator is structurally
  impossible.

Two judgment calls are applied case by case and recorded, rather than being
absolute rules:

- **Not a trivial reskin.**  A language that merely renames another's
  commands (Earfuck renames brainfuck's to musical notes) is "too easy to
  be worth a dedicated interpreter".  A dialect with genuinely different
  semantics (e.g. the S*bleq family's store variants) is a real interpreter.
- **Not already implemented elsewhere.**  A language already covered by an
  interpreter in this repo (or whose own page documents a working
  implementation) is not a gap.

If a candidate fails the criteria, record the assessment in the
assessed-and-rejected ledger in `docs/limitations.md` — the negative result
is as valuable as the interpreter, because it stops the assessment from
being redone.  The roadmap (`docs/roadmap.md`) tracks which candidates are
still
on the table.

## Layout

- `src/esolangs/interpreters/<category>/<name>.py` — one interpreter per
  language, each exposing `run(code, io)` (the program as a string, or a
  list of lines for grid/line-based languages, plus the `IO` object that
  owns input/output).  Categories are `tape_based`, `stack_based`,
  `register_based`, and `other`.  Copy `_template.py` to start; it encodes
  the I/O, error, and docstring conventions.
- `src/esolangs/tools/generators/` — text generators, one module per state
  model (`register.py`, `tape.py`, `stack.py`, `other.py`).  Each
  `def <name>(text)` returns a program whose output is exactly `text`, or
  raises `ValueError` for text the language cannot emit.
- `src/esolangs/tools/booleans/` — truth-table generators for languages with
  input and value branching.
- `src/esolangs/registry.py` — the single source of truth: which languages
  have a generator, an interpreter, how programs are handed to the
  interpreter, and the canonical id each language resolves to.  The public
  API and the test tables derive from it.
- `src/esolangs/__init__.py` — the public API (`generate`, `run`,
  `list_languages`); `src/esolangs/cli.py` — the `esolangs` command.
- `scripts/` — verification tooling (`check_docstrings.py`, the
  differential/emulation checks, `verify.py`).

## Adding a language

1. **Interpreter** — copy `_template.py` into the right category and fill in
   the dispatch.  Interpreters are typed and documented: the module
   docstring must name the language and document the EOF, `HaltError`, and
   `ValueError` behavior it actually exhibits (see `_template.py`;
   `scripts/check_docstrings.py` enforces the mechanical parts).
2. **Generator** (optional) — add `def <name>(text)` to the right module in
   `tools/generators/` and register it in `registry.py`.  If the language
   reads input and branches, add a truth-table generator to `tools/booleans/`.
3. **Registry** — add a `Language` entry in `registry.py` (display name,
   canonical id, generator, interpreter module, whether the program is split
   into lines, extra `run()` kwargs).  This single entry wires up the API
   and the tests.
4. **Tests** — add a round-trip test in `tests/tools/test_generate.py`.  The
   fuzz (`tests/fuzz/test_fuzz_generators.py`) and example
   (`tests/scripts/test_examples.py`) tables derive from the registry automatically;
   add a committed program under `examples/hello-world/<name>.txt` if the
   language has a generator.
5. **Verification** — run the interpreter on the generated program for a
   range of texts, then run the full check.

## Verifying changes

```sh
just test            # or: python scripts/verify.py
```

runs the full local check: pre-commit (lint, format, types), pytest, bandit,
cargo fmt + tests, the `extra/line` suites (via uv, skipped when uv is
missing), and the Python verify scripts (including `check_docstrings.py`).
To run it automatically on every push:

```sh
git config core.hooksPath .githooks
```

`python scripts/verify.py` additionally runs the RISC-V emulation stack
(compilers and cross-check generators under unicorn), which needs the native
toolchain; the qemu steps are CI-only.

## Conventions

- Interpreters follow the conventions in `_template.py` and
  `docs/limitations.md`: empty programs are a no-op by default, exhausted
  input raises `EOFError` (or follows the spec where it defines EOF),
  malformed programs raise `ValueError`, and invalid runtime operations
  raise `HaltError` — never a raw Python exception.
- New code must pass ruff (lint and format) and mypy, and keep line coverage at 100%
  (the coverage-badge CI job enforces it).
