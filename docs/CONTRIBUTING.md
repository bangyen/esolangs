# Contributing

Add stable, deterministic languages verifiable through the repo's I/O model.
Each needs an interpreter and generator, except famous languages whose specs
preclude generation. Record rejections in [limitations](limitations.md).

## Start here

1. `just install-dev` (requires just >= 1.37), then `just test-quick`.
   Without `just`, run `uv sync --group dev` and
   `git config core.hooksPath .githooks`, then
   `uv run python scripts/verify/gate.py`.
2. Improve a language, or check a new one's [admission](#what-makes-a-candidate-worth-adding).
3. `just new-language "Name"` creates interpreter, generator and test stubs.
   Follow [interpreter conventions](#interpreter-conventions) and the
   [Boolean I/O contract](#the-boolean-io-contract).
4. Run `just test-quick` while editing; `just check-language "Name"` lists
   missing integration and checks the language.
5. Run `just test` before committing. For a new language,
   `just finish-language "Name"` regenerates artifacts and runs the full gate.

Read [Code shape](#code-shape) before refactoring and the
[optimization gate](#what-makes-a-generator-optimization-worth-shipping)
before changing generated programs.

## Development

Development requires uv. Use `uv run` or activate `.venv`. Without `just`,
run the underlying scripts:
`just test` is `python scripts/verify/gate.py`; language `check` and `finish`
are subcommands of `scripts/new_language.py`.
[Scripts reference](../scripts/README.md) maps the other recipes.

| Command | Use |
| --- | --- |
| `just test-quick` | inner loop |
| `just test` | required before committing; branch-scoped gate |
| `just test-full` | whole tree, slow tests and every local gate step; release-scale changes |
| `just test-py` | pytest, including weekly probes when selected; also scheduled in CI |
| `just examples` / `just docs` | regenerate committed examples / generated documentation |

Audit archives and replays pin earlier commits. Use a full Git checkout;
extend a shallow clone with `git fetch --unshallow`.

The gate checks generated docs, pre-commit, mypy, pytest, dead definitions,
size baselines, deep proofs and exception leaks. Out-of-scope steps stay in
CI; `test-full` runs them locally. Delete unused helpers or move test-only
helpers under `tests/`. Tests enforce a 1,200-line file cap, fewer than
10,000 non-contract cases, and test code below its source: `tests/` +
`src/**/tests` < `src`, `tests/tooling` < `scripts`. Per-language oracle and
accounting modules count apart under a ceiling that only drops.

Tests have scheduling bands: fast (default), medium, slow and weekly. Every
run retains hard hang deadlines. `just test-costs` checks the existing 1 s
fast and 5 s medium cost bounds separately, serially and without coverage;
the dedicated weekly serial cost jobs record environment, timings and completion.
Correctness runs retain all selected witnesses without cost-band failures.

The Brainfuck/Boolfuck/Subleq cost/fault pilot (0.80–1.08 s/cohort) retained
independent oracles and rejected inert checks. One injected output-fault class
is insufficient replacement evidence for the independent checks.

Make focused commits with short imperative subjects. CI checks wheels on
Linux, macOS and Windows, including examples, CLI I/O, PNG execution and
installation with and without the image extra.

## What makes a candidate worth adding

A new language must add an uncovered construction, branch mechanism, answer
convention or input interface:

| Axis | Examples |
| --- | --- |
| Construction | decision tree, minterm sum, ANF/XOR-of-products, grid walk |
| Branch | conditional, value-testable jump, skip guard, comparator, pointer displacement |
| Answer | printed bit, landing colour, position, termination |
| Input | read-and-route, bit-addressable index, parameterized embed |

- BFStack uses a minterm sum.
- Fargo uses ANF/XOR-of-products and a bit-addressable input index.
- LaserFuck uses a grid walk.
- A Painter Ant uses a grid walk and answers by landing colour.
- Streetcode uses a grid walk.
- ArrowQueue answers by termination.
- Crement answers by termination.

A spec that precludes generation qualifies only through the fame threshold
under Curation in [limitations](limitations.md). Interpreter-only entries
show `int` in `esolangs list --details`.

- Deadfish qualifies as interpreter-only.
- HQ9+ qualifies as interpreter-only.
- Nope. qualifies as interpreter-only.

Curation governs removal independently. Generator audits do not remove
languages; stalled rows remain open on the [roadmap](roadmap.md).

## Layout

| Path | Contents |
| --- | --- |
| `src/esolangs/runtime/` | shared runtime |
| `src/esolangs/generation/` | shared generator helpers |
| `src/esolangs/languages/<id>/` | interpreter, generator, tests, fixtures, packaged examples |
| `src/esolangs/registry/` | public integration |
| `tests/` | shared contracts, infrastructure, proof runners |
| `scripts/` / `checks/` | development tools / gate checks |
| `snapshot.json` | collection dates and slow-test durations |

Each package's `language.toml` owns its data. Aggregators read only their
section and skip absent files or sections. Resource evidence can name an owned
`witnesses` provider, a replacement `corpus`, or bounded `sparse` row cases.

Optional `certification.py` owns its `CERTIFICATION = CertificationSpec(...)`
verification policy. Checks load it separately; runtime descriptors and
ordinary execution do not import certification modules.

| Kind | Sections | Meaning |
| --- | --- | --- |
| Gates | `proof_status`, `evidence`, `resource_evidence`, `generator_sizes`, `construction_boundaries`, `catalogue`, `schemes`, `deep_arities` | claims consumed by checks; wrong data fails |
| Reference | `curation` | census facts; no gate |
| Record | `ablations`, `interpreter_ablations` | pinned historical records or measured replays; source cites `[ablations.<key>]` rather than duplicating figures (tested) |

Generator audits use `kind = "measurement"` for a first witness or `"replay"`
for a pinned baseline comparison. Declare rows, seed, units, scale and budget;
retirements also measure balanced output. Historical `archive_refs` lists
load unchanged payloads from their group's pinned `archive_revision`; context
and source citations remain checked.

`Language` records names, interpreter, source shape, optional generator and
typed I/O contract. `resolve` normalizes names; the catalog selects whole-source
or split-line input. Each language declares `LANGUAGE = Language(...)` in its `descriptor.py`,
including interpreter-only entries. Callable references load implementations
on use; generators import only descriptor definitions they use.
`scripts/docs/generate.py` derives documentation and examples from the registry
(`just docs`, `just examples`).

Execution follows this path:

```text
resolve name → Language → generator → source or template
                          instantiate → source + encode_inputs(stdin)
                                      → interpreter.run(code, io)
                                      → read_answer() → bit
```

Input-embedding generators return `$`-run templates for `instantiate`.
`read_answer` handles printed and state-dump answers; the evaluation harness
runs every row to read termination answers. `run` loads the language's
interpreter; `make_vm` exposes its step-capable machine for debugging and
hang proofs.

## Interpreter conventions

Start from `src/esolangs/runtime/_template.py`. Every interpreter:

- Exposes `run(code, io)` with required `IO`, using it for all I/O.
  Most grids use registry `split=True`.
- Raises `ValueError` for malformed source and `HaltError` for invalid runtime
  operations where specified. Declare spec-defined empty-program errors as
  `empty_program=` and EOF values as `eof=` in `LANGUAGE`. Divergence is legal;
  bound empty-program tests rather than requiring termination.
- Guards input lines before indexing (`if val:`). Empty lines are legal;
  exhausted input raises `EOFError` either way.
- Exposes `_Machine.step()`, `halted` and a complete `snapshot()`, including
  the input cursor. Diff snapshots directly without normalizing changes away.
  A declared `workspace_snapshot()` projects versioned semantic components for
  written-bit proofs; storage and cycle snapshots do not define its grouping.
- Treats public `_Machine` properties as debugger views. Declare `ip`,
  `memory` and `stack` only when meaningful; defaults are `ind`, empty, empty.
- Uses a pure `_advance` transition over immutable state, with `step` doing
  I/O. Stores too expensive to thread may return effects instead
  (`grapheme/interpreter.py`).
  Choose backing storage per interpreter. Require equivalent traces, isolated
  captures and resource peaks, plus native, cycle-snapshot and accounting
  timings under the existing 0.9 gate: Brainfuck's mutable tape reached 2.38x
  native but 0.54x with cycle snapshots, Boolfuck's immutable set the reverse
  (3.74x / 0.47x), so both keep their stores.
- Follows explicit spec rules. Examples resolve omissions only consistently
  with those rules; internal consistency does not establish author intent.
  Record contradictions, justify interpretations of conflicting rules, and
  document and test deviations. Documentation does not make a deviation
  conformant. Record spec gaps in the docstring; never define away invalid
  operations.
- Provides `__main__` calling `run(data, IO())`.

- A Painter Ant receives whole source.
- B-tapemark receives whole source.
- EGL receives whole source.

The interpreter module docstring is `describe()["spec"]`: prose, then
`Commands:`, `Input/output:`, `Errors:`, `Decisions:`. `Errors:` names public
exceptions, not internal builtins. Each needs a `[[spec_triggers]]` program
and expected exception in `tests/cases.toml`. Convention and trigger tests
check these; public API Google `Raises:` sections are checked too.

Generator docstrings use prose, then `Size:`, `Raises:`, `Decisions:`.
`Size:` needs a measured anchor in the exact machine-read form
`n=10 random 1847: 1,118 chars` or `n=16 and: 1,443,471 chars`.
Store figures in `language.toml` evidence; `just docs` renders their docstring
views. Tests independently regenerate emitted programs and check the figures. Declare `GeneratorCapError` wherever generation may refuse a table,
as `[[evidence.raises]]` with a raising `table` or an `untriggerable` reason;
`just docs` renders the `Raises:` entry. Do not duplicate docstring figures
elsewhere in the generator; helper-specific figures belong beside the helper.

## What makes a generator optimization worth shipping

Generators guarantee their Scaling class in [proofs](proofs/index.md), not
their constant. Apply the canonical set or explain why it does not apply:
ignored inputs (`essential_inputs`, `read_at`), constant subtrees
(`constant_span_test`), repeated subtrees (`subtree_ids`). Canonical rules
ship at any saving unless inapplicable or larger on average for their target
at the largest measured arity; cite that measurement. Minimal spelling
(no redundant grouping or trailing no-op) also needs no percentage gate.

Shared analyses return decision layers/DAGs, `AffineForm` and `WeightedLookup`.
Analysis stays O(T); target emitters own reads, labels, layout and candidate
selection.

Size counts characters. Packed literals may carry at most 8 bits per
character or grid cell; code points above U+00FF merely hide wider UTF-8.

For each new or revised optimization, record added construction paths and
state in its ablation record and explain why each is necessary. Remove
superseded paths and state. Numerical qualification does not excuse
avoidable complexity.

Other size optimizations must meet all these rules:

- **Saving:** at least 10% sustained or 20% declining at both of the two
  largest evaluation arities. Sustained means neither tending to zero nor
  clearly declining across those arities. The higher bar is a policy premium
  for limited persistence, not asymptotic equivalence.
- **Corpus:** use the same arities for both bars, normally seeded random
  tables at n=7 and n=8. Fix the range before judging; never shorten it to
  qualify. If saving is still growing at n=8, measure through its peak.
  Use 200 tables when either result is within two percentage points of its
  bar. Named functions (parity, majority, and/or, thresholds) are separate:
  qualifying on one keeps only that family's rule. Constructed firing
  classes (sparse rows, tilings, guarded affine residuals) do not qualify.
- **Caps:** an earlier cap counts only where the construction stops or
  loses; measure its two largest arities and cite the loss beyond it.
  A cap where saving merely diminishes is invalid. The n=3 total is context,
  not a qualifying corpus.
- **Metric:** text uses characters; grids (`grid=True`) use rows × longest
  row. Grid defaults race by `grid_rank`; Scaling counts cells. Cite evidence
  beside the code or through its ablation record. Failing size may still
  qualify with a 25% command reduction, from a proved bound or baseline counts.
- **Scaling:** no size-class breaks. Keep an old candidate only if the new
  build alone would leave the class. A fallback that only saves scattered
  tables a few characters must itself clear the gate.
- **Execution:** run every table exhaustively through n=3 and sample n=4..6.
  Pin the n=3 totals before and after; update `just sizes` when its baseline
  changes.
- **Construction:** follow [Boolean-generator conventions](limitations.md):
  input-order reads and template runs, one uniform `(zero, one)` fill pair,
  at most four named reorder candidates, no search, O(T) size and generation
  (`tests/proofs/deep/linearity.py`). Interpreter leniency, truncated keywords
  and missing operands cannot buy size savings.

B-tapemark's strip-width rule retains its separately approved exception:
area falls 46.8% at n=8, 22.1% at n=12 and 12.5% at n=14 despite tending to
zero. We accept n=8 costs of +23.9% commands, +15.4% written workspace and
+57.0% text for that footprint reduction. One extra closed-form candidate
needs no search, frozen table or arity cap. Correctness, exact resource bounds
and linear construction still apply; the exception covers only this rule.

Execution optimizations need 5% fewer commands summed over every row of the
three-input tables, with no table slower or larger. Choose by size, then
steps; bound each piece's upside before choosing it.

## Code shape

- Prefer a named rule to a frozen table, and either to search. A searched
  table stays only if no rule reproduces it; its comment names the search
  ([search policy](limitations.md#searches)).
- Keep one path per semantics. A parallel fast/plain path needs a reader
  the other cannot serve.
- A race, candidate or arity branch cites its measured saving at its largest
  arity, jointly with siblings, and meets the optimization gate.
- Indexes, caches and batches need timings at three sizes; replacements
  must preserve growth rate.
- Derive state rather than storing redundant fields. Beyond three fields,
  use a NamedTuple instead of a repeatedly unpacked positional tuple.
  Measure constructor overhead with `just tracediff <language> --speed`;
  a justified type alias may avoid a regression (Piet measured 11%).
- Docstrings teach syntax, a step, halt/output and spec decisions;
  implementation notes sit beside the code.
- Above the complexity cap, split dispatch by spec sections, not `noqa`.
  Commands absent from the corpus need dedicated checks. Existing
  `C901_EXCUSED` counts may only decrease; lower them in the same commit
  when removing an excuse.
- Keep validators and debugger views beside the step, outside it.
- New CLI flags need a shell workflow; API parity alone is insufficient.

## Checklist

1. `just new-language "Name"` asks for category (`--category` overrides;
   `--interpreter-only` requires fame admission), creates stubs and records
   `[curation] unassessed = true` in `language.toml`. Replace placeholders.
2. Repeat `just check-language "Name"` until no integration is missing.
   It names files and entries: registry, exports, contract, example, width
   policy, VM samples (derived for generators), curation, proof ledger and
   formulas. Registry tests enforce the same checklist. It also runs local
   tests, the committed example, generator shape, ledger word/fold checks
   and formulas, and lists regenerated files.
   `[semantic_evidence]` names owned pytest nodes and their interpreter contract.
   Derive expectations independently of production helpers and generators;
   retain unresolved readings in the contract’s Decisions. Admission runs
   clean and faulted copies in fresh processes, requiring executed assertions
   to detect an injected output byte (60 s total). Use `kind = "model"` for
   independent models; `"examples"` records bounded literal/arithmetic checks
   while model coverage remains open. Purity and snapshot gates still apply.
   Optional published examples belong in `tests/cases.toml` as `[[examples]]`
   with stated output (schema: `tests/interpreters/test_published_programs.py`).
   Bound potentially looping programs with `max_steps=10_000` or `timeout=5`.
3. `just benchmark "Name" TABLE` records source units and commands, not wall
   time, as JSON. `just bounds "Name"` prints worst steps and
   written bits and witnesses. “Worst” must be
   exact; otherwise say “at most”.
4. A first implementation (no outside interpreter) gets a blind
   reimplementation: a clean-room interpreter written from the wiki page
   alone, diffed over the generated corpus with live controls. Fix a
   generator form the page does not license; state a reading the page leaves
   open in the Decisions, or fence it in [limitations](limitations.md) with
   its evidence. Record `[audits] blind_reimplementation = <date>`.
5. `just finish-language "Name"` regenerates examples, docs and size baseline,
   runs the whole-tree `--full` gate, then CI-only checks. Quick tests alone
   do not qualify. Run this minutes-long check in the background; it reruns
   failures alone and identifies load-only failures. Missing checklist items
   are reported and fail the run, but do not prevent the gate from running.

Keep language facts in their package: `LANGUAGE`, interpreter and own tests
(`test_<id>.py`, `test_boolean_<id>.py`, `test_integration_<id>.py` for
interpreter, generator and API/CLI/VM/debugger respectively). Shared tests
must not key facts by language name; use `Language` metadata or local tests.
`tests/api/test_language_coupling.py` rejects name lists, id branches and
prose comparisons that state another language's facts.

Comment cohorts may declare `# language-owners: ["Name", "Other"]`; removing
an owner requires deleting the contiguous block. Keep shared invariants outside it.
Language-specific Markdown uses canonical-name bullets and indented continuations.

Remove a language manually: delete its package, owned tests and fixtures,
then remove references and unused helpers. Regenerate examples and docs and
run `just test-full`. Brainfuck is the shared reference language and must stay.

### The Boolean I/O contract

Generated programs follow `LANGUAGE`'s `BooleanContract`: by default, one
`0`/`1` line per input and a printed bit. Read all n inputs in order, even
for constant or ignored-input tables. `input_shape="char_stream"` uses bare
characters and also covers byte-packed stdin: each bit is byte `'0'` (0x30)
or `'1'` (0x31). A low-bit-first reader must consume the other seven bits
before the next input. `answer_mode` covers state-dump and termination answers.

- Boolfuck packs input bits into bytes.
- Smu packs input bits into bytes.

Contract tests must check answers and consumption together, including asymmetric
rows that expose input permutations. Fixed-frame readers leave a following record
untouched; whole-stream readers own stdin, and EOF probes are limited to one.
Crashes and timeouts are failures, never answers; divergence requires a proof
such as a repeated state.
Saved text, compressed source and PNGs execute independently of generator caches.
Width, wrapping and balancing preserve answers and input consumption.

Exercise constants, ignored inputs and every construction switch on both sides,
including the supported arity boundary. Keep expensive boundary witnesses in
language-owned tests; shared small-input checks do not establish their coverage.
Name their tables in `[construction_boundaries]`. Use `benchmark = true` for
tables also pinned by the default source-size sweep. Otherwise name the owned
pytest node in `test`. Run `uv run python -m checks.check_construction_witnesses`
to verify that every declared test executes and uses its tables.
