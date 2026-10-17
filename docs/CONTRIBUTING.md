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
`python scripts/docs/generate.py examples`.

CI checks the wheel on Linux, macOS and Windows: packaged examples, CLI I/O,
PNG execution, and installation with and without the mathematics extra.

## What makes a candidate worth adding

A new language must add an uncovered construction, branch mechanism,
answer convention, or input interface:

- **Construction shape** -- decision tree (the default), minterm sum
  and ANF/XOR-of-products, grid walk.
- **Branch mechanism** -- explicit conditional, value-testable jump, skip
  guard, implicit comparator, pointer displacement.
- **Answer convention** -- print 0/1, landing colour, position-encoded,
  termination as the answer.
- **Input interface** -- read-and-route, bit-addressable index,
  parameterized embed.

- BFStack uses a minterm sum.
- Vandevelo uses a minterm sum and answers by termination.
- Fargo uses ANF/XOR-of-products and a bit-addressable input index.
- LaserFuck uses a grid walk.
- A Painter Ant uses a grid walk and answers by landing colour.
- Streetcode uses a grid walk.
- Minifuck gives a position-encoded answer.
- ArrowQueue answers by termination.
- Crement answers by termination.

These are generator tests. A language whose specification precludes a
generator qualifies only through the fame threshold under Curation in
[limitations](limitations.md). Such languages are interpreter-only, marked
`int` by `esolangs list --details`.

- Deadfish qualifies as interpreter-only.
- HQ9+ qualifies as interpreter-only.
- Nope. qualifies as interpreter-only.

Curation also defines removal independently of admission. Generator audit
axes never remove a language; a stalled row stays open on the
[roadmap](roadmap.md).

## Layout

| Path | Holds |
| --- | --- |
| `src/esolangs/runtime/` | shared runtime machinery |
| `src/esolangs/generation/` | shared generator helpers |
| `src/esolangs/languages/<id>/` | interpreter, generator, tests, fixtures and examples |
| `src/esolangs/registry/` | the source of truth for public integration |
| `tests/` | shared contracts, infrastructure and proof runners |
| `ledgers/` | cross-language records: proof status, curation, catalogues, size and timing baselines |

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
  whole-source or split-line input. A language with a generator declares
  its own `LANGUAGE = Language(...)` at the end of its generator module, and
  generated exports collect those explicitly for the registry. Only
  interpreter-only languages are listed
  in `registry/_table.py`. `esolangs.languages.generators`'s imports come from
  the declarations (`scripts/docs/generate.py`, run by `generate.py docs`
  and by `check`).
- Interpreters and generators live in `src/esolangs/languages/<id>/`, each
  as a module or package. Shared generator helpers live in `src/esolangs/generation/`.
  Most generators return runnable source;
  input-embedding languages return a `$`-run template for `instantiate`.
  `encode_inputs` handles stdin conventions, and `read_answer` reads printed
  and state-dump answers through the contract; termination answers (halt or
  diverge) are read by the evaluation harness, which runs every row.
- `run` loads `src/esolangs/languages/<id>/interpreter`
  and calls its `run(code, io)`; `make_vm` exposes its
  step-capable machine to the debugger and the hang proofs.
- Each language’s `tests/` holds its unit and integration suites, fixtures
  and proofs; packaged examples live beside its modules. Shared contracts and
  proof infrastructure live in `tests/`; `scripts/` holds development tools.

## Interpreter conventions

Start from `src/esolangs/runtime/_template.py`. Every interpreter:

- Exposes `run(code, io)` with required `IO`; uses `io` for all I/O.
  Most grids receive lines via registry `split=True`.
- Raises `ValueError` for a malformed program and `HaltError` for an
  invalid runtime operation, where the spec has one. An empty program the
  spec calls malformed declares its error as `empty_program=` in the
  `LANGUAGE`, and an input command the spec gives an EOF value declares it
  as `eof=`. Divergence is legal; tests bound execution of
  empty programs rather than requiring termination.
- Guards an input line before indexing it (`if val:`); an empty line is
  legal, and running out raises `EOFError` either way.
- Exposes `_Machine.step()`, `halted` and a complete `snapshot()`, including
  the input cursor; tests look up that exact name. Its top-level grouping is
  measured: the workspace ledger counts each part only once written, so
  splitting Cyclic tag's `(answer, printed)` dropped a bit from an exact
  formula (`tests/proofs/test_workspace_formulas.py`). Regroup fields
  inside, not in the snapshot, and diff it as is: mapping `///`'s nested
  rule back to the old layout before comparing hid a 16-bit drop.
- Treats every public `_Machine` property as a debugger view; adding or
  renaming one changes what the debugger shows.
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

- A Painter Ant receives whole source.
- B-tapemark receives whole source.
- EGL receives whole source.

The module docstring is the language's spec (`describe()["spec"]`); its
shape (prose, then `Commands:`, `Input/output:`, `Errors:`, `Decisions:`) is
`_template.py`'s own docstring, which `just new-language` copies.  `Errors:`
names the public exception a caller catches, not the builtin the interpreter
raises. `tests/interpreters/test_interpreter_conventions.py` checks the shape
and that `Errors:` lists what the source raises; every entry needs a trigger
in the language's own `tests/cases.toml` (`[[spec_triggers]]`: a program and
the exception `run` gives), which `tests/interpreters/test_spec_triggers.py` runs. The exported API's Google
`Raises:` sections are held to the same standard by
`tests/api/test_public_docstrings.py`.

A generator's module docstring follows the `just new-language` stub: prose,
then `Size:`, `Raises:`, `Decisions:`.  `Size:` gives at least one anchor,
`n=10 random 1847: 1,118 chars`, which
`tests/generators/test_generator_docstrings.py` regenerates, so a size change
updates it.  `Raises:` lists `GeneratorCapError` wherever the generator can
refuse a table, with a `[[generator_triggers]]` entry in `tests/cases.toml`.  A figure
in `Size:` or `Decisions:` appears nowhere else in the generator: a figure
about one helper lives beside it instead.

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
  n >= 7, and were retired. A saving still growing at n=8 is measured on
  past it, to its peak. Named functions (parity, majority, and/or,
  thresholds) are reported apart; 10% on one keeps a rule for that family,
  not the whole race. Smallfuck's residual forms saved 2.2% on random tables
  at n=8, 0% at n >= 9 and at most 1.0% on a named function, and were
  retired. Cite the measurement beside the code.
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
of the three-input tables, with no table slower or larger. Choose candidates
by size, breaking ties by steps. Bound the per-piece upside before choosing.

## Code shape

Judge a module by what the language does not demand.

- A named rule beats a frozen table, and both beat a search. A searched
  table stays only when no rule reproduces it, and its comment names the
  search (Malbolge's `_INITS`).
- One path per semantics. A fast path beside the plain one needs a reader
  the fast path cannot serve (Thue keeps `_advance` for
  `branching_successors`); otherwise delete one.
- A race, candidate or n-specific branch cites its saving at the largest n
  where it runs, measured jointly with its siblings: Line's five extra folds
  each saved 0% alone, yet streaming alone lost 25% on lifted cores until
  projected streaming stayed beside it. Under 10% it goes: Circuit Diagram's
  cofactor bank won 0.00% at n=8..11, Back's bend 0-2.7%.
- An index, cache or batch carries timings at three sizes; a replacement
  must grow the same way.
- Derive state; don't store it. A field computable from others is a
  property: Cyclic tag deletes one bit a step, so `head` is
  `read % len(program)` and `answer` is `data[read - 1]`, and four fields
  became one counter. Try this before the next rule.
- State past three fields is a NamedTuple, not a positional tuple
  re-unpacked in every branch. Its constructor is Python code, so a step
  that rebuilds the state pays for it: run `just tracediff <language>
  --speed`. Piet lost 11% and kept a
  type alias whose comment names the fields.
- The module docstring teaches the language: source syntax, one step, halt
  and output, then spec-gap decisions. Implementation notes are comments
  beside the code they explain.
- Past the complexity cap, split dispatch by the spec's sections, not with
  a `noqa`: Fish's regular commands became tables (`_STACK_OPS`, `_TURNS`)
  and the rest one `match`. A command the corpus never runs needs its own
  check: no Fish program ran `@`, so old and new `_advance` were diffed on
  200,000 random single steps.
- Validators and debugger views sit beside the step, not inside it
  (Streetcode's `interpreter/validation.py`).
- A new CLI flag needs a shell workflow it serves; API parity is not one.
  Ten `list` filters, `debug` and `--portable` went in 1.1.0 for lack of
  one.

## Checklist

1. `just new-language "Name" --category tape_based` (the matching category;
   `--interpreter-only` for a fame admission) writes the interpreter,
   generator and test stubs, and records the language as
   `{ unassessed = true }` in `ledgers/curation.toml`. Replace
   the placeholder semantics and tests.
2. `just check-language "Name"` lists every integration step still missing,
   each with the file and entry to add: registry, exports, contract,
   example, width policy, samples (interpreter-only languages; a
   generator's VM sample is derived from its program), curation, proof
   ledger and its formula tables. Repeat until it reports none; a test runs it over the registry,
   so the list matches what the suite enforces. It then runs the
   seconds-long checks `finish` would otherwise fail late: the language's
   own tests, its committed example, the generator's shape, the ledger's
   word limits and fold measure, and its formula rows. It lists the generated
   files it refreshed.
   Optional: the wiki page's own examples, with their stated output, go in
   `src/esolangs/languages/<id>/tests/cases.toml` as `[[examples]]` (schema
   in `tests/interpreters/test_published_programs.py`).
   To try a program that may loop, bound it:
   `esolangs.run("Name", program, stdin=..., max_steps=10_000)` or
   `timeout=5`, never a bare `run`.
3. Record generator evidence with `just benchmark "Name" TABLE`; compare
   `source_units` and `commands`, not wall-clock time. `python
   scripts/new_language.py bounds "Name"` prints the worst steps and
   written bits per arity, with the table reaching each: a cell's "worst"
   must equal them exactly, else it says "at most".
4. `just finish-language "Name"` regenerates examples, docs and the size
   baseline, then runs the full `verify/gate.py`. That is the gate: `just
   test-quick` skips the slower contract sweeps every generator must pass.
   Added lines need 90% statement and branch coverage per file; the
   report separates them from older gaps. It takes minutes, so run it in
   the background; it reruns failed tests
   alone and says when every failure was machine load. Steps `check`
   still lists don't stop it: it reports them, runs the gate anyway, and
   fails.

A comment cohort can declare `# language-owners: ["Name", "Other"]`.
Removal drops that contiguous comment block when any owner goes; keep shared
invariants outside it. Language-specific Markdown belongs in canonical-name
bullets with indented continuations.

To take a language out, `just remove-language "Name"` deletes what `check`
asks for and every test file `tests/api/test_language_coupling.py` counts as
the language's own (committed or not), prunes the helper modules only it
imported and the per-language code the shared generators and
`wrap.py` no longer reference, drops its wiki fixtures, timing rows and
prose entries, regenerates, and
lists the mentions left to edit by hand (display name and aliases, quoted
ids, dotted module paths), each labelled with the edit it needs -- a
runnable example, prose, or a comment. brainfuck is the reference language
shared tests, the examples and `scripts/docs/generate.py` spell out, so
`remove` refuses it rather than leave a tree that cannot build.

A language should live in its own files: its generator module's
`LANGUAGE`, its interpreter, and its own test files. A fact another file
keys by a language's name (a list of names in a shared test, a branch on
an id) is coupling, and `tests/api/test_language_coupling.py` allows
none. Put such a fact on `Language`, or the test in the language's own
test file under `src/esolangs/languages/<id>/tests/`: `test_<id>.py` for
its interpreter, `test_boolean_<id>.py` for its generator, and
`test_integration_<id>.py` for its API, CLI, VM and debugger checks. A shared file states a language's own facts, never a second
language's: an example or comparison that names another language (`as in
X`, `unlike X`, `X's axis`) is coupling in prose too, and
`tests/api/test_language_coupling.py` rejects it.

### The Boolean I/O contract

A generated program reads the inputs and prints the answer the way its
`BooleanContract` (the `contract=` of its `LANGUAGE`) says; with none the
default is one `0`/`1` line per input and a printed `0`/`1`. Every program
reads all n inputs, in order, even when the table is constant or ignores an
input. `input_shape="char_stream"` reads the bits as bare characters, and also
covers languages whose stdin packs bits into bytes: each
input is then the byte `'0'` (0x30) or `'1'` (0x31), whose low bit is the
input's value, so a program that reads low bit first takes that bit and must
read and drop the byte's other seven before the next input (see
the language's generator). `answer_mode` covers state-dump and termination
answers.

- Boolfuck packs input bits into bytes.
- Smu packs input bits into bytes.
