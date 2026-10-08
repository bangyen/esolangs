# Contributing

Add stable, deterministic languages verifiable through the repo's I/O model.
Each ships with an interpreter and a generator; only a famous language whose
specification precludes a generator may ship without one (see below). Record
rejections in [limitations](limitations.md).

## Development

```bash
just install-dev
source .venv/bin/activate        # or prefix each command with `uv run`
just test-quick
```

Run `just test` before committing; use `just test-full` for release-scale
changes (`test-full` includes slow tests; weekly probes run separately with
`just test-py`, or in scheduled CI). Regenerate committed examples with
`python scripts/generate.py examples`.

CI checks the wheel on Linux, macOS and Windows: packaged examples, CLI I/O,
Line/Piet PNG execution, and installation with and without the mathematics extra.

## What makes a candidate worth adding

A new language must add an uncovered construction, branch mechanism,
answer convention, or input interface:

- **Construction shape** -- decision tree (the default), minterm sum
  (`bfstack`, `vandevelo`), ANF/XOR-of-products (`fargo`), grid walk (`laserfuck`, `a_painter_ant`, `streetcode`).
- **Branch mechanism** -- explicit conditional, value-testable jump, skip
  guard, implicit comparator, pointer displacement (`123`).
- **Answer convention** -- print 0/1, landing colour (`a_painter_ant`),
  position-encoded (`minifuck`),
  termination as the answer (`123`, ArrowQueue, Crement, Vandevelo).
- **Input interface** -- read-and-route, bit-addressable index (`fargo`),
  parameterized embed.

These are generator tests. A language whose specification precludes a
generator qualifies only through the fame threshold under Curation in
[limitations](limitations.md). Such languages are interpreter-only, marked
`int` by `esolangs list --details`; Deadfish, HQ9+, Nope. and Unary qualify.
Curation also defines removal independently of admission. Generator audit
axes never remove a language; a stalled row moves to the
[roadmap](roadmap.md#parked)'s Parked section.

## Layout

| Path | Holds |
| --- | --- |
| `src/esolangs/interpreters/` | interpreter modules and `run(code, io)` |
| `src/esolangs/tools/` | generators |
| `src/esolangs/registry/` | the source of truth for public integration |
| `tests/` | interpreter and generator coverage |

The registry connects the API and CLI to generators and interpreters:

```text
language name
    │
    ▼
registry.Language ──► boolean generator ──► program or template
    │                                              │
    │                                      instantiate inputs
    ▼                                              │
interpreter module ◄──── source + encoded stdin ◄──┘
    │
    ├── run() ──► raw output ──► read_answer() ──► bit
    └── make_vm() ──► step-and-inspect state
```

- `src/esolangs/registry/` owns integration. `Language` records names,
  interpreter, source shape, optional generator and the typed input and
  answer `contract`; `resolve` normalizes spelling, and `RUNNERS` selects
  whole-source or split-line input.
- Generators live in `src/esolangs/tools/`. Most return runnable source;
  input-embedding languages return a `$`-run template for `instantiate`.
  `encode_inputs` handles stdin conventions, and `read_answer` reads printed
  and state-dump answers through the contract; termination answers (halt or
  diverge) are read by the evaluation harness, which runs every row.
- `run` loads the module from `src/esolangs/interpreters/` (grouped by
  execution model) and calls its `run(code, io)`; `make_vm` exposes its
  step-capable machine to the debugger and the hang proofs.
- `tests/interpreters/` and `tests/tools/` hold language suites and shared
  contract checks; `scripts/` holds verification, mutation and
  documentation tools.

## Interpreter conventions

Start from `src/esolangs/interpreters/_template.py`. Every interpreter:

- Exposes `run(code, io)` with required `IO`; uses `io` for all I/O.
  Most grids receive lines via registry `split=True`; A Painter Ant,
  B-tapemark and EGL receive whole source.
- Raises `ValueError` for a malformed program and `HaltError` for an
  invalid runtime operation, where the spec has one. An empty program the
  spec calls malformed is listed in `_EMPTY_REJECTIONS`
  (`tests/fuzz/test_interpreters_robustness.py`). Divergence is legal; tests bound execution of
  empty programs rather than requiring termination.
- Guards an input line before indexing it (`if val:`); an empty line is
  legal, and running out raises `EOFError` either way.
- Exposes `_Machine.step()`, `halted` and a complete `snapshot()`, including
  the input cursor; tests look up that exact name.
- Declares the VM views `ip`, `memory` and `stack` only where they say
  something: the VM defaults `ip` to `ind` and the other two to empty, so a
  language with no stack writes no `stack`.
- Writes the language as a pure transition (`_advance`) over an immutable
  state, with `step` as the shell doing the I/O; a store that cannot be
  threaded cheaply returns effects instead (`grapheme.py`).
- Follows explicit specification rules. Examples resolve omissions only when
  consistent with those rules; internal consistency alone does not establish
  author intent. Records contradictions rather than silently repairing them.
  When explicit rules conflict, records the conflict and justifies the chosen
  interpretation. Documents and tests any intentional deviation; documenting
  a deviation does not make it spec-conformant.
- Documents spec-gap decisions in its docstring (`suffolk.py`); never defines
  away invalid operations.
- Provides a `__main__` block calling `run(data, IO())`.

`tests/test_interpreter_conventions.py` checks the module docstring names
the language and mentions `EOF`, `HaltError` or `ValueError` wherever the
interpreter reads input or raises them.

## What makes a generator optimization worth shipping

A generator guarantees its size class (the Scaling column in
`docs/proofs/index.md`), not its constant. Every generator applies the
canonical set, or its docstring says why one does not apply: ignored inputs
dropped (`essential_inputs`, `read_at`), constant subtrees folded
(`constant_span_test`), repeated subtrees shared (`subtree_ids`). A
canonical piece ships at any saving: it is exempt only where the construction
leaves it nothing to act on, or where it makes the average program larger on
the tables it targets at the largest arity measured (cite the figure).

Anything else is a bespoke size optimization and must meet all of these
requirements:

- **10% or more** off the total emitted size at the largest arity where it
  runs: seeded random tables at n=7..8, or at its cap if it stops earlier,
  and 200 tables when the result is within two points of the bar. A trick
  aimed at a table class (ignored inputs, constants) is judged on that class;
  2D grids are judged by area, rows times the longest row. The n=3 total is
  context only: greedy order searches saved 8-15% there but at most 2.2% at
  n >= 7, and were retired. Cite the measurement beside the code.
- **No table grows**: checked exhaustively through three inputs, so keep the
  old build as a candidate when the new one is not uniformly shorter.
- **Every table executes**: exhaustively through three inputs and sampled at
  four to six. Pin the n=3 total before and after; update `just sizes` when its
  baseline moves.
- **The Boolean-generator conventions** in `docs/limitations.md`: reads and
  template runs in input order, one uniform `(zero, one)` fill pair, at most
  four named reorder candidates, no search, O(T) size and generation
  (`tests/proofs/deep/linearity.py`).
- **No interpreter leniency**: truncated keywords or missing operands do not
  count as shorter programs.

Execution-time optimizations require 5% fewer commands summed over every row
of the three-input tables (`scripts/screens/steps.py`), with no table slower
or larger. Choose candidates by size, breaking ties by steps.

Use `scripts/screens/` to bound the upside first.

## Checklist

1. `just new-language "Name" --category tape_based` (the matching category;
   `--interpreter-only` for a fame admission) writes the interpreter,
   generator and test stubs. Replace the placeholder semantics and tests.
2. `just check-language "Name"` lists every integration step still missing,
   each with the file and entry to add: registry, exports, contract,
   example, width policy, samples, curation, proof ledger and its formula
   tables. Repeat until it reports none; a test runs it over the registry,
   so the list matches what the suite enforces. It then runs the
   seconds-long tests `finish` would otherwise fail late: the language's
   own, the ledger's word limits and fold measure, its formula rows.
   Optional: the wiki page's own examples, with their stated output, go in
   `tests/fixtures/wiki_examples/<id>.json` (schema in
   `tests/interpreters/test_published_programs.py`).
3. Record generator evidence with `just benchmark "Name" TABLE`; compare
   `source_units` and `commands`, not wall-clock time. `python
   scripts/new_language.py bounds "Name"` prints the worst steps and
   written bits per arity, the numbers the ledger's cells state.
4. `just finish-language "Name"` regenerates examples, docs and the size
   baseline, then runs the full `verify.py`. That is the gate: `just
   test-quick` skips the slower contract sweeps every generator must pass.
   Added lines need 90% statement and branch coverage per file; the
   report separates them from older gaps. It takes minutes, so run it in
   the background; it reruns failed tests
   alone and says when every failure was machine load.

To take a language out, `just remove-language "Name"` deletes what `check`
asks for, regenerates, and lists the prose mentions left to edit.

### The Boolean I/O contract

A generated program reads the inputs and prints the answer the way its
`BooleanContract` (`registry/_contracts.py`) says; with no entry the
default is one `0`/`1` line per input and a printed `0`/`1`. Every program
reads all n inputs, in order, even when the table is constant or ignores an
input. `input_shape="char_stream"` reads the bits as bare characters, and also
covers languages whose stdin packs bits into bytes (Boolfuck, Smu);
`answer_mode` covers state-dump and termination answers.
