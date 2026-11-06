# Migration completion ledger

Declaration audit: 2026-11-05. [Language rows](migration-status.csv) cover all
117 languages and 114 Boolean backends. Declarations and inherited adapters
are recorded separately; neither proves acceptance. Every completion row stays
open until its trace, resource, installed-package and retirement evidence is
checked against the current implementation. Refresh this snapshot after each
migration batch.

The [roadmap](roadmap.md#architecture-migrations) defines acceptance. The table
below inventories known retirement families; the final tree-wide audit must
also catch aliases introduced during migration. Target removal release: 2.0.
Owners are workstreams, not individual contributors.

| Retirement | Owner | Consumers to migrate | Canonical replacement |
| --- | --- | --- | --- |
| Source-returning `generate` / `instantiate` defaults | Artifact API | Retired; all ordinary repository callers retain artifacts; public surface and signature pins | Program/template artifacts and explicit `.source` |
| `_Tagged` | Artifact API | Retired with its module; import refusals in `tests/api/test_run_results.py` | Explicit artifact metadata |
| `_Template` | Artifact API | Retired; strict artifact filling and raw-source refusals in runtime tests | `TemplateArtifact` and bindings |
| `tagged.source_adapter` and artifact-to-tagged round trips | Artifact API | Retired; direct metadata encoding and source loading; raster retagging fault controls | Direct artifact/source handling |
| `_recover_template` and plain-string binding inference | Artifact API | Retired with `registry.recover_setters`; declared bindings and known-arity validation | Declared template bindings |
| Tagged-source `load_program` | Persistence | Retired; canonical loader preserves the existing version-1 format | Canonical artifact loading |
| Temporary `esolangs.compat` API | Artifact API | Retired; actual missing-import checks and live import barriers | Canonical API; delete the facade after migration |
| Temporary `generate_artifact` / `load_artifact` aliases | Registry | Retired; tools use canonical names; public and bound-method absence checks | `generate` / `load_program` |
| Shared plain-text fixture filler `tests.generators.fills` | Artifact API | Retired; native fixtures declare their bindings; negative import check in `tests/generators/test_generator_support.py` | Explicit `TemplateBindings` from declared native setters |
| `BooleanBackend(generate=...)` constructor alias | Registry | Retired; callers use `entrypoint`; negative constructor/replacement checks in `tests/api/test_boolean_backend.py` | Canonical entrypoint field |
| `registry.GENERATORS` | Registry | Retired; negative index checks in `tests/api/test_deferred_catalog.py` | Descriptor/backend entrypoints |
| `languages.generators` facade | Registry | Retired; callers use owned modules or backend declarations; negative import checks in `tests/api/test_deferred_catalog.py` | Artifact API or direct owned generator imports |
| Unused generator-module descriptor re-exports | Registry | Retired; owned metadata consumers use descriptors; all-backend checks in `tests/api/test_certification_capability.py` reject unused imports and `LANGUAGE` exports | Independent descriptors; retain constants actually used by emitters |
| Helpers' `AffineForm`, `affine_form`, `symmetric_outputs` re-exports | Analysis | Retired; callers migrated; negative export check in `tests/generators/test_symmetry.py` | `generation.algebraic` / `generation.lookup` |
| `runtime._result.ExecutionResult` shim | Results | Retired; imports migrated; negative import check in `tests/api/test_run_results.py` | `esolangs.results.ExecutionResult` |
| `_Machine` / `_for_run` discovery | Lifecycle | VM construction, diff/proof drivers and machine traits | Declared preparation/factories and capabilities |
| Implicit completion entrypoint defaults | Lifecycle | Runtime descriptors and native runners | Explicit completion declarations |
| Dialect metadata signature/default inspection | Lifecycle | Retired; all seven schemas declared; constructor/default and no-discovery checks in `tests/api/test_dialects.py` | Declared dialect schemas and defaults |
| Generator callable-option signature inference | Analysis | Retired; all 114 backends use declared options; independent signature oracle and no-discovery checks in `tests/api/test_artifact_defaults.py` and `tests/api/test_api_contracts.py` | Declared backend option capabilities |
| `FunctionRef.__signature__` proxy | Registry | Retired; recursive declaration checks reject its return in `tests/api/test_descriptor_loading.py` | Explicit callable parameter declarations |
| Snapshot-as-workspace fallback | Accounting | Retired; VM capture and `WrittenState` require models; missing/invalid adapters and raw values are rejected in runtime/tooling tests | Versioned semantic accounting models |
| Legacy worker-field defaults | Results | Retired; complete requests and explicit success/error observations; omission controls in `tests/runtime/test_worker_results.py` | Explicit canonical fields, including unavailable observations |
| Superseded serialization decoders/converters | Persistence | Persisted data and fixtures, if a format is superseded | One-time data migration, then remove the obsolete code |

For each family, locate consumers before changing it; close the row only after
those consumers migrate, the implementation disappears and a regression check
rejects its reintroduction. A version number or a new facade is not retirement.
Current version-1 serialization is not obsolete solely because its version is 1.

The 2.0 defaults are artifacts and execution results. Public API, CLI, scripts,
documentation and tests retain records through binding and execution. Native
measurements read explicit source; portable JSON retains template bindings.
Plain source cannot be instantiated. Native source exports retain their file
conventions; no serialized format was superseded by this cutover.

The source facade, string wrappers, inferred binding recovery and duplicate
artifact aliases are deleted. PNG persistence encodes record metadata directly;
execution carries settings and scale explicitly, checking provenance before
loading. `ProgramArtifact` retains native-container metadata at construction.

Missing-import and symbol checks reject retired APIs. Live import barriers
cover generation helpers, audit replay, examples, benchmarks and documentation;
raster retagging controls protect direct artifact paths. Raw raster/compressed
metadata operations remain native-container APIs.

Accounting and analysis rows require owned witnesses, not just a declared hook
or a recognized helper name. Certification needs an installed-package/lazy-import
acceptance audit after the active separation work lands. Catalog-wide acceptance
remains open even where an implementation pilot already passed.

Accounting now has 117 explicit or inherited semantic adapters. VM capture and
the meter reject missing models instead of using cycle snapshots. Proof drivers
use declared captures; synthetic and regrouping controls name their models.
Declarations do not close lifecycle or catalog-wide acceptance.

Storage decision: retain immutable transition boundaries and semantic captures;
choose backing stores per interpreter. Keep Brainfuck's tuple and Boolfuck's
mutable set. Across 4,332 pilot cases and 694,932 samples, alternatives preserve
traces, resource peaks and purity but fail the existing 0.9 timing gate:
Brainfuck's mutable shell reaches 2.382 native throughput but 0.543 with cycle
snapshots; Boolfuck's immutable set reaches 3.739 with cycle snapshots but 0.474
native. The 31 priced cohorts took 29.84 s total, each below its 60 s cap.
Future storage changes require native, cycle and accounting measurements;
purity and equivalence gates remain unchanged.

All seven dialect schemas now declare choices and defaults. Runtime metadata
queries and validation no longer inspect signatures or constructors. The other
110 languages have no dialect settings. All 114 Boolean backends now declare
layout and balancer options; generation and catalog queries no longer infer
them from callable signatures. Backend analysis audits remain open.

All ten post-halt interpreters now declare preparation and completion/debug
capabilities, alongside Brainfuck, NQ and Whitespace. The post-halt batch checks
pending dumps, repeated finalization, source-step counts, native/isolated results,
fault detection and lazy trait queries. Retirement and installed-package
acceptance remain open.

A Painter Ant declares periodic rendering after a repeated pass boundary. Suffolk
keeps stepped EOF completion and declares both EOF and evidenced native repeats.
Both declare factories and debug surfaces; retirement and package acceptance stay open.

The first ordinary text batch declares Deadfish, HQ9+, Nope., Home Row, BFStack
and ABCDirection. Their debug projections, EOF behavior and ordinary completion
remain unchanged. Cached, inherited, compressed and raster factories remain open.

Trace comparison takes declared completion policy explicitly, including mutant
controls and speed workloads; final dumps retain their views, state and output.
Historical class flags no longer select trace completion. Factory/RNG discovery
and remaining direct-machine completion consumers stay open.

Trace corpora retain generated artifacts through binding. Native trace and speed
constructors receive explicit source and retained raster scale; random-program
alphabets read source bodies. Factory/RNG discovery remains open.

The logical-store batch declares fifteen further models, flattening persistent
RAM and continuation spines and freezing unordered stores. Bitwise Cyclic Tag
counts live data and its answer, excluding the deleted-prefix storage cursor.
Read-only source tables and shell-only dump guards are excluded.

Boolfuck and Monotonic Boolfuck declare inherited bit-tape factories and debug
fields. Buffered byte flushing and monotonic reads stay unchanged.

Unary declares compressed-source preparation and inherited debug fields. Gzip
continues to decode in chunks, with zero-valued EOF and ordinary completion.
Other cached and raster factories and retirement acceptance remain open.

Streetcode declares cached geometry preparation with fresh per-run state and
grid debug fields. The last `_for_run` discovery hook and VM fallback are removed.

The grid/stack batch freezes mutable grids, hierarchical tapes, pointer memories
and scoped stacks without cycle serializers or storage caches. ABCDirection's cycle
model records write-epoch equality, preserving behavior under epoch renumbering.

Taglate declares cached token preparation, queue debug fields and ordinary
completion. Machines retain private token/pair copies; native rotation/pop
batching and partial fault state remain unchanged.

Malbolge declares cached-image preparation, opaque instruction positions and
ordinary completion. Mutable memory and dirty snapshot chunks stay per-run;
EOF remains 59048.

Interprogck8 declares cached program preparation, caller-owned RNG binding and
line/stack debug fields. Preparation draws nothing; captures, call frames and
`z` reloads remain per-run.

Qoibl declares cached parser preparation, variable debug fields and ordinary
completion. Statement lists and variables remain private; malformed-source
diagnostics and output flushed before reads/faults remain unchanged.
The register/rewriting batch declares twenty models, including typed call frames,
self-modifying instructions and nested block values. Grid hash caches and
read-only dialect names are excluded; the corresponding bit bound is tightened.

Line declares raster preparation, scale binding and grid debug fields. Cached
geometry, fresh step state and both native execution paths remain unchanged.
Ordinary lifecycle checks now cover raster sources.
The continuation/scope batch freezes nine more logical stores and frame stacks.
Persistent scope-map history, grid caches and accumulator list spines are excluded;
input and clock-read progress remain explicit.

Trace-speed comparisons warm both copies on the sized workload before timing.
An inherited warm prefix can no longer give the baseline a cheaper first lap.

Piet declares raster/scale preparation and grid/stack debug fields, completing
both raster factories. Normalized rows stay shared; stack, ports and successful
read counts stay per-run. EOF commands remain ignored.

BrainIf and Container declare split-text preparation with private line lists and
debug fields. Guarded reads, left-growing tape, zero-valued Container EOF and
the legacy Container EXIT return remain unchanged.




Unlambda captures typed logical terms and captured continuations without cached
depths. Constructor tags preserve value identity but carry no payload bits; deep
term hashing, comparison and accounting use iterative traversals. Constant-program
workspace is 32n+17+bl(n); the general bound retains its conservative allowance.

Dig and Flowchart declare split-grid preparation and debug fields. Mutable
stores, pointer/deque state, bit buffers and read counters remain per-run;
self-modification and final partial-byte flushing remain unchanged.

Alight declares dialect-aware preparation and grid/namespace debug fields.
Dialect constants and validators live outside the interpreter package, so
registry, trait and dialect queries no longer load Alight’s machine.
Walkers and lists stay per-run.
Native trace construction also retains artifact dialect choices.



The raster/store batch declares five more models. Logical cells, array dimensions,
stashed values, beam/tape state and bit buffers exclude persistent-map buckets,
chunk boundaries, immutable program fingerprints and final-dump guards.

Clockwise and Circuit Diagram declare split-grid factories and debug fields.
Cyclic input bits, output buffers, circuit events/latches and default clock
cursors remain per-run; topology caching and constructor input reads stay intact.

Befunge and Fish declare RNG-aware split-grid factories and debug fields.
Preparation freezes source/options without drawing; machines retain the caller's
RNG and own their codebox, stack and register state.



FRACTRAN records its chosen logical numeric representation explicitly: integer
registers or sparse prime exponents. Mutable cursors and immutable scans share
the exponent model; zero entries, guard indexes and selection caches are excluded.

Super SNUSP and thisthat declare RNG-aware split-grid factories and debug fields.
Preparation freezes source/options without drawing; tape, values, pointers,
transfer cells and input-set state remain per-run.

Malbolge accounts for its finite 59,049-word store and registers independently
of cycle-cache chunks. Canonical accounting pages retain immutable captures;
physical cache partitions and spare capacity are excluded.

Fargo declares typed numeric, array, callable and continuation values. Accounting
no longer renders values with repr; callable arity/raw arguments and unordered
bindings retain their semantics independently of cycle keys.

Packlang accounts for live frames, unordered stores and typed suspended
expressions independently of frame keys and repr. Input progress and successful
reads remain explicit; the read-only program fingerprint is excluded.

Ascenic and Caballo declare RNG-aware text factories and debug fields.
Preparation binds options without draws or IO; Caballo still reads its initial
stack at construction and draws weighted output only on the halting step.

Alight declares canonical reachable-list graphs, typed pending expressions and
walker fields. List aliases/cycles survive allocation and namespace reordering;
immutable parser-container sharing and cycle serialization are excluded. Its
exact default workspace formula counts logical payloads and both input cursors.

Modulous and Painfuck declare RNG-aware text factories and debug fields.
Preparation binds options without drawing; variables, tape, loop/repeat state,
input progress and draw counts remain per-run.

INTERCAL and Thue declare RNG-aware text factories and debug fields.
Preparation binds options without drawing; return/stash/abstention state and
rewrite text/match indexes remain per-run. Output-before-request flushing stays
in the interpreter shells.

Forbin declares source-located function references and canonical live lexical
environments, preserving closure capture, parent links and loop phase without
rendering or first-sight serials. Unreachable scope history and inactive loop
storage are excluded; its exact workspace bounds count one copy of bindings.

Basicfuck, bit~, Circlefuck, ROTfuck, 6-5, Dimensional, Pointless and What!?
declare text factories and debugger fields. Tape, compiled cursors, rotating
programs, hierarchical pointers and call frames remain per-run. ROTfuck dialect
metadata no longer imports its interpreter.

1 + i, 3x, Aprknia, Fackward, Freestajlo, Eval, Underload and Unsquare declare
text factories and debugger fields. Function/return frames, operand and inactive
stacks, variables and growing programs remain per-run; cursor shapes and EOF
conventions stay explicit.

Algebraic Programming Language declares typed numeric/function values and
source-relative continuation locations. Retained definitions survive redefinition;
immutable code sharing and cycle serials do not determine workspace. All 117
languages now declare accounting; catalog-wide acceptance stays open.

AddSubJump, Between, Blindfolded Arithmetic, CARP, CV(N)(C), Decleq, IEBEL,
Rubic, Subleq and S*bleq declare text factories and debugger fields.
Stores, flags, registers, cube/loop state and input progress remain per-run.
Blindfolded Arithmetic still reads initial input at construction; S*bleq binds
its native store/indirection options without shared memory.

B-tapemark, Balik, EGL, Movesum, Nandypants, NOR machine, Qrain, Pilas,
Quassaunt and SStack declare text factories and debugger fields.
Grids/markers, tapes/queues, output buffers, environments and stacks remain
per-run. B-tapemark binds swap behavior and keeps dialect metadata independent
of its interpreter.

VM accounting no longer falls back to cycle snapshots. All 117 catalog rows
require models; the 114 Boolean execution witnesses and three non-Boolean
checks reject cycle-key use. Full accounting acceptance stays open.

BASICER, Bleh, Chicken, Codesick, Collatz Multiverse, CreativeScript v2, DINAC,
Grapheme, Sonata and HQ9+ with headers declare text factories and debugger
fields. Heaps, arrays, scopes, frames and input state remain per-run.
Grapheme binds integer conversion and keeps dialect metadata independent of
its interpreter; constructor-time whole-input reads stay intact.

Crement, FALSE, Forþ, Inject, lol waht i cant edit talk pages, Parenthesys,
Retrograde, SendStuff, SLOW ACV MAMMALIAN and SwitchCase declare factories
and debugger fields. Instructions, lambdas/scopes, macros and buffers remain
per-run. Inject freezes split text; Mammalian binds all dialect fields and
loads dialect metadata independently of its interpreter.

Certification payloads for BFStack and Subleq live in their certification
modules; generators no longer import certification types. The live import
barrier covers catalog queries and artifact generation/round trips for all
114 backends, plus template filling where applicable. Payload ownership checks
reject a return to generator-owned certification. The installed wheel passes
this barrier on Python 3.12–3.15 with image support. Catalog-wide execution
and full installed-package acceptance remain open.
