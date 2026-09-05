# Contributing

## Is a language worth adding?

Not every wiki language belongs here; rejected cases are recorded in the
assessed-and-rejected ledger in `docs/limitations.md`.  A candidate must
meet all of these:

- **Complete, stable specification.**  The wiki page must fully define the
  commands and behavior. A stub, work-in-progress, or spec the author
  calls unfinished isn't enough to verify an interpreter against.
- **Deterministic, computable behavior.**  Uncomputable or irreducibly
  random languages can't be verified. *Seeded* randomness is fine (e.g.
  LaserFuck's initial heading is drawn from a seed the tests fix).
- **A usable file-based I/O protocol.**  Input/output as characters/lines
  through the repo's `IO` seam (see interpreter conventions in
  `docs/limitations.md`).  No output, stderr-only, or file/OS-based I/O
  don't fit.  A no-output language is admitted only as a self-contained
  interpreter with no generator — except Point Break, admitted with the
  first *termination-convention* boolean generator (halt for 0, loop for 1;
  see `docs/walls.md`), licensed by the wiki's own truth-machine example
  and its Turing-complete arithmetic.
- **A generator story.**  A boolean generator, a text generator that can
  emit arbitrary bytes, or a documented reason neither is possible.  A text
  generator must exercise the language's computation (arithmetic encoding,
  bit manipulation, data-dependent construction) — a literal-embed text
  generator only counts alongside a boolean generator.  A documented wall
  excuses the missing generator only when output is still spec-defined and
  verifiable by hand.  A language whose only observable result is an
  interpreter-invented state dump (no language-defined output at all) is
  admitted only as a self-contained interpreter, and is a standing removal
  candidate.  A language with no data-dependent control flow (no input, no
  conditional — output is a fixed function of the program text) is
  likewise a standing removal candidate even with a computational text
  generator, since its boolean generator is structurally impossible.

Two judgment calls, applied case by case and recorded rather than absolute:

- **Not a trivial reskin.**  Renaming another language's commands
  (Earfuck → brainfuck's commands as musical notes) isn't worth a
  dedicated interpreter.  Genuinely different semantics (e.g. the S*bleq
  family's store variants) is.
- **Not already implemented elsewhere.**  Already covered by an
  interpreter here, or by a working implementation on its own wiki page,
  is not a gap.

Record rejected candidates in the assessed-and-rejected ledger in
`docs/limitations.md`, so the assessment isn't redone. `docs/roadmap.md`
tracks candidates still open.

## Layout

- `src/esolangs/interpreters/<category>/<name>.py` — one interpreter per
  language, exposing `run(code, io)` (program as a string, or a list of
  lines for grid/line-based languages, plus the `IO` object owning
  input/output).  Categories: `tape_based`, `stack_based`, `register_based`,
  `grid_based`, `queue_based`, `other`. Copy `_template.py` to start; it
  encodes the I/O, error, and docstring conventions.
- `src/esolangs/tools/text/` — text generators, one module per state model
  (`register.py`, `tape.py`, `stack.py`, `other.py`).  Each `def <name>(text)`
  returns a program whose output is exactly `text`, or raises `ValueError`
  for text it can't emit.  The only extra parameter allowed is `width`, and
  it must default.
- `src/esolangs/tools/boolean/` — truth-table generators for languages with
  input and value branching.  Two legal shapes:
  - *table-in, program-out*: `def <name>(truth_table)` returns a program
    reading n inputs and printing the table's answer. `n` is implied by
    table length, never a parameter.
  - *template-in, instantiated-per-row*: for a language with no input
    command, the generator emits a template the harness instantiates per
    input combination (see `parameterized.py`).
  Two generators take something other than a truth-table string, each for
  a reason in its docstring — `circlefuck_byte` is byte-valued, and
  `jaune_multiply` multiplies operands of any length.  Both are named in
  `scripts/check_generators.py` so the exemption is visible.
- `src/esolangs/compilers/` — RISC-V backends, one module per language, each
  exposing `comp(code)` returning assembly.  Further parameters need a
  default.  The `__main__` block delegates to `_riscv_common.main`, printing
  to stdout (Suffolk keeps its own block for an optional loop-count CLI arg,
  but prints the same way).  Register the module on its `Language` entry
  (`compiler="<module>"`) — `scripts/check_compilers.py` fails on an
  unregistered backend.
- `src/esolangs/registry.py` — single source of truth: which languages have
  a generator, a compiler, an interpreter, how programs are handed to the
  interpreter, and each language's canonical id.  The public API and test
  tables derive from it.  Registering something here is the whole of adding
  it — the `check_*` scripts walk the source directories and fail on
  anything missing from the registry.
- `src/esolangs/__init__.py` — public API (`generate`, `run`,
  `list_languages`); `src/esolangs/cli.py` — the `esolangs` command.
- `scripts/` — verification tooling (`check_docstrings.py`,
  `check_compilers.py`, `check_generators.py`, differential/emulation
  checks, `verify.py`).  The three `check_*` scripts each walk a source
  directory and fail on anything missing from the registry or departing
  from a signature convention; they run as steps in `verify.py`.

## Adding a language

1. **Interpreter** — copy `_template.py` into the right category and fill in
   the dispatch.  The module docstring must name the language and document
   the EOF, `HaltError`, and `ValueError` behavior it actually exhibits (see
   `_template.py`; `scripts/check_docstrings.py` enforces the mechanical
   parts).
2. **Generator** (optional) — add `def <name>(text)` to the right module in
   `tools/text/` and register it in `registry.py`. If the language reads
   input and branches, add a truth-table generator to `tools/boolean/`.
3. **Registry** — add a `Language` entry in `registry.py` (display name,
   canonical id, generator, interpreter module, whether the program is
   split into lines, extra `run()` kwargs).  This single entry wires up the
   API and the tests.
4. **Tests** — add a round-trip test in `tests/tools/test_generate.py`. The
   fuzz (`tests/fuzz/test_fuzz_generators.py`) and example
   (`tests/scripts/test_examples.py`) tables derive from the registry
   automatically; add a committed program under
   `examples/hello-world/<name>.txt` if the language has a generator.
5. **Verification** — run the interpreter on the generated program for a
   range of texts, then run the full check.

## Verifying changes

See `AGENTS.md` for the verification gate (`just test`, `scripts/verify.py`)
and its traps.  To run it automatically on every push:

```sh
git config core.hooksPath .githooks
```

`scripts/verify.py` additionally runs `check_docstrings.py` and the RISC-V
emulation stack (compilers and cross-check generators under unicorn), which
needs the native toolchain; the qemu steps are CI-only.

## Conventions

- Interpreters follow the conventions in `_template.py` and
  `docs/limitations.md`: empty programs are a no-op by default, exhausted
  input raises `EOFError` (or follows the spec where it defines EOF),
  malformed programs raise `ValueError`, and invalid runtime operations
  raise `HaltError` — never a raw Python exception.
- New code must pass ruff (lint and format) and mypy, and keep line coverage at 100%
  (the coverage-badge CI job enforces it).
