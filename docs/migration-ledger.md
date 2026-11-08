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
| Temporary `esolangs.compat` API | Artifact API | Retired; actual missing-import checks and live import barriers | Canonical API |
| Temporary `generate_artifact` / `load_artifact` aliases | Registry | Retired; tools use canonical names; public and bound-method absence checks | `generate` / `load_program` |
| Shared plain-text fixture filler `tests.generators.fills` | Artifact API | Retired; native fixtures declare their bindings; negative import check in `tests/generators/test_generator_support.py` | Explicit `TemplateBindings` from declared native setters |
| `BooleanBackend(generate=...)` constructor alias | Registry | Retired; callers use `entrypoint`; negative constructor/replacement checks in `tests/api/test_boolean_backend.py` | Canonical entrypoint field |
| `_table.Generator` / `_table.SourceKind` forwarding imports | Registry | Retired; public registry imports canonical owners; actual old imports fail in deferred catalog controls | `registry._backend.Generator` / `runtime._definition.SourceKind`; supported public registry names retained |
| `registry.GENERATORS` | Registry | Retired; negative index checks in `tests/api/test_deferred_catalog.py` | Descriptor/backend entrypoints |
| `languages.generators` facade | Registry | Retired; callers use owned modules or backend declarations; negative import checks in `tests/api/test_deferred_catalog.py` | Artifact API or direct owned generator imports |
| Unused generator-module descriptor re-exports | Registry | Retired; owned metadata consumers use descriptors; all-backend checks in `tests/api/test_certification_capability.py` reject unused imports and `LANGUAGE` exports | Independent descriptors; retain constants actually used by emitters |
| Helpers' `AffineForm`, `affine_form`, `symmetric_outputs` re-exports | Analysis | Retired; callers migrated; negative export check in `tests/generators/test_symmetry.py` | `generation.algebraic` / `generation.lookup` |
| Helpers' `_parity_bias` and duplicate parity recognizers | Analysis | Retired; audited backends and REFRACTRAN ablations use canonical analysis; independent affine oracle and removed-export checks | `generation.algebraic.parity_bias` |
| `generation.raster_lookup` and its layout submodules | Analysis | Retired; Piet's generator and three owned test modules migrated; actual missing-import checks | `languages.piet.generator.operations`, `.balance` and `.packing` |
| `brainfuck.bf_tree` and Grapheme's `_program` wrapper | Registry | Retired; owned tests and installed-package checks reject both imports | Owned `brainfuck` / `grapheme` entrypoints |
| Quassaunt's `_short_name` clone | Analysis | Retired; size provider uses the canonical helper; owned and installed-package import refusals | `generation.helpers.short_name` |
| `runtime._result.ExecutionResult` shim | Results | Retired; imports migrated; negative import check in `tests/api/test_run_results.py` | `esolangs.results.ExecutionResult` |
| Private cycle helpers/protocols re-exported by `vm` | Registry | Retired; five caller files use their owner; 16 actual import refusals in `tests/api/test_run_results.py` | `esolangs._cycles`; public VM detector imports remain supported |
| `_Machine` / `_for_run` discovery | Lifecycle | Retired; runtime and verification drivers use declared factories; raw native machines remain independent oracles | Declared preparation/factories and capabilities |
| Generator proof-function re-exports | Certification | Retired; five package generators dropped unused imports; all-backend import barrier rejects proof loading | Explicit owned proof providers |
| Implicit completion entrypoint defaults | Lifecycle | Retired; required declaration fields and explicit driver policies; rejection controls in `tests/runtime/test_lifecycle.py` | Explicit completion declarations |
| Interpreter `supports_scale` lookup/default | Lifecycle | Retired; two raster declarations replace module globals; crossed declaration/flag controls in `tests/runtime/raster/test_contract.py` | Declared machine scale capability |
| Interpreter `load_source` lookup/text fallback | Lifecycle | Retired; declared policies replace discovery and four module exports; source-loading import barriers and native CLI controls retain formats | Declared text, literal-newline, compressed and raster loading |
| Dialect metadata signature/default inspection | Lifecycle | Retired; all seven schemas declared; constructor/default and no-discovery checks in `tests/api/test_dialects.py` | Declared dialect schemas and defaults |
| Generator callable-option signature inference | Analysis | Retired; all 114 backends use declared options; independent signature oracle and no-discovery checks in `tests/api/test_artifact_defaults.py` and `tests/api/test_api_contracts.py` | Declared backend option capabilities |
| `FunctionRef.__signature__` proxy | Registry | Retired; recursive declaration checks reject its return in `tests/api/test_descriptor_loading.py` | Explicit callable parameter declarations |
| Snapshot-as-workspace fallback | Accounting | Retired; VM capture and `WrittenState` require models; missing/invalid adapters and raw values are rejected in runtime/tooling tests | Versioned semantic accounting models |
| Noninteger cycle counters and unhashable cycle snapshots | Results | Retired; constructor, JSON and parent-decoder controls retain zero-stride completion and partial output | Integer ordered boundaries and hashable snapshots |
| Empty, disconnected, mutable or draw-dependent branch verdicts | Results | Retired; constructor, wire and parent-decoder refusal controls preserve partial output | Immutable root-reachable graphs; run-specific termination decisions |
| Legacy worker-field defaults | Results | Retired; complete typed requests and explicit success/error observations; omission, flag, integer-tag and raster-run controls in `tests/runtime/test_worker_results.py` | Explicit canonical fields, including unavailable observations |
| Permissive worker envelopes and nested proof fields | Results | Retired; missing/extra fields, unknown error kinds, duplicate terminals and contradictory output fail with retained prefixes | Exact canonical stream, result and evidence schemas |
| Normalized worker hex spellings and duplicate snapshot-set members | Results | Retired; request, result and parent-decoder refusals retain signed huge integers, byte snapshots and partial output | Encoder spellings and distinct immutable members |
| Malformed PNG metadata version downgrade | Persistence | Retired; missing, mistyped and nonpositive versions fail with live controls in `tests/runtime/raster/test_png.py` | Plain PNG, valid v1 provenance and future positive-integer versions |
| Absent gzip member accepted as an empty program | Persistence | Retired; constructor, portable and worker refusals retain actual empty members and explicit unavailable execution | Valid UTF-8 gzip members, including empty and concatenated streams |
| Superseded serialization decoders/converters | Persistence | Not applicable: no persisted format was superseded; version-1 JSON/PNG and unlabelled native files remain supported | Retain canonical decoders; convert only after a format cutover |

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

REFRACTRAN uses shared decision reduction and parity analysis. Signed rail
chains, zero-first rail allocation, controlled swaps and wrapping remain owned;
their ordering preserves 632 corpus programs byte for byte. Shared-analysis
faults change executed answers; disabling parity sharing preserves answers and
increases emitted size. Size pins, the n=10 anchor and declared resource scopes
remain unchanged. Other backend analysis rows still require their own audits.

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

Hot, Kiss, Smu and Unlambda declare factories and debugger fields. Term graphs,
continuations, variables and input/output buffers remain per-run. Kiss keeps
its native exit-code result and declares completion on both native routes.

The remaining nine runtimes declare text factories and debugger fields: ///,
Algebraic Programming Language, Fargo, Forbin, FRACTRAN, Object disoriented,
Packlang, REFRACTRAN and Shakespeare. Each construction owns execution state;
Packlang captures literal policy and loads its metadata without execution.
All 117 preparation declarations are present; lifecycle retirement remains open.

Back, Befunge, Blindfolded Arithmetic, Dig, Fish, Interprogck8 and NQ join
REFRACTRAN on canonical parity analysis. Reads, stencils, layout and selection
remain owned.
Each matches 632 corpus requests; 384 additional parity/layout witnesses match
and 480 rows execute per tree. Other backend analyses remain unaudited.

Runtime construction and traits no longer discover `_Machine`, class flags or
public properties. Runtime declarations require preparation, completion and
capabilities; native drivers require explicit completion policy. The scaffold
and synthetic descriptors follow the same contract. Missing declarations and
policies fail; absent debugger views retain their defaults.
Final lifecycle acceptance remains open.

CreativeScript v2 uses canonical dependency/projection analysis; arithmetic
indexing remains owned. Movesum retains its halt-on-equality rung lookup and
Parenthesys its packed character/index arithmetic; neither constructs a
decision graph. Both use canonical validation. Kiss uses canonical subtree
ids without duplicate validation, retaining SK emission and draining reads.
These four backend audits preserve source, execution and resource bounds;
catalog-wide runtime and certification acceptance remain open.

BASICER uses shared ordered decision layers, preserving constant-input menus
and leaf numbering. Fackward uses the shared memoized subtable fold; its native
terminals, draining reads and copied block syntax remain emitter-owned.
Each retains all 632 corpus programs byte for byte, with executed shared-analysis
fault controls. Size pins, anchors and declared exact resource scopes are unchanged.

Lol waht i cant edit talk pages uses canonical memoized subtable folding.
Its emitter retains draining reads, final-bit echoing and one-arm termination;
constant programs validate and emit without initializing decision machinery.
The local analysis traversal and emitted-arm comparison are gone. All 632
corpus requests and 160 larger layouts match; 3,128 native/stepped rows retain
traces, input progress and resource peaks. Original bounds and arities remain.

Trace construction now uses declared hooks, source splitting, RNG support and
completion. Baselines and mutants without factories fail before tracing.
Semantic probes identify the native fault target through a representative
factory-built machine; raw models retain their independent constructor references.
No driver inspects machine signatures or guesses private constructor names.

Hot uses canonical subtree ids and symmetric profiles for majority admission;
the exact one-count rejects other families before a full scan. Its Church
terms, tie rule and readers remain owned. NQ derives arity from canonical
subtree analysis; parity grouping, draining reads and both dialects remain.
Neither repeats validation on nonconstant inputs. Bitwise Cyclic Tag and
Cyclic tag use canonical weighted lookup; seven-character cells, production
markers and embedded inputs remain owned. Their unused `_program` wrappers
are removed. These four backend audits retain source and resource bounds;
catalog-wide runtime and certification acceptance remain open.

IEBEL, SendStuff and Stisp use canonical ordered decision layers; duplicate
reachable-node discovery is deleted. Fallthrough paths, macro spelling and
cost-bounded literal inlining remain owned. Aprknia reuses validated arity;
its zero-exit stack analysis remains owned. Caballo and Monotonic Boolfuck
retain canonical subtree ids with signed-sum and pointer-divergence emission.
Bleh and Codesick retain canonical layers with native names, polarity and
input ordering. Constant fast paths keep validation ahead of decision analysis.
All eight have executed canonical-analysis fault controls, unchanged corpus
bytes, size/resource scopes and passing generation-timing comparisons.

Dig, Line, SStack, Circuit Diagram and Malbolge generators no longer import
unused proof functions or metadata types. Bounds remain owned by their explicit
proof providers. The all-backend barrier rejects proof-formula imports as well
as certification imports; unused metadata re-exports are checked across all
114 backends. The wheel passes generation/round trips and native execution for
all 117 runtimes with both import controls on Python 3.12–3.15, using cached
ABI-matched Pillow 13.0. Broader installed acceptance remains open.

The certification barrier also covers all 117 debugger witnesses: 116 match
native completion, output and input observations after normalizing step counts;
the periodic witness reaches the reported boundary without inventing completion.
Three guarded reference workers cover success, step exhaustion and EOF; both
failure routes preserve unfinished observations and partial output. Worker guards
run positive import controls before execution. The wheel passes this witness
matrix on Python 3.12–3.15.

Smu uses canonical ordered layers; macro ordering, delimiter pricing and
constant pads remain owned. SwitchCase uses a canonical reduced diagram,
retaining zero-first case placement. Retrograde derives arity from canonical
subtree ids; its backward-function involution and lexical turns remain owned.
Rubic retains canonical subtree ids with cube-neutral instructions. These
four audits preserve source bytes, EOF behavior, bounds and the timing floor,
with executed shared-analysis fault controls.

Worker transport rejects extra or missing cycle, branch and snapshot-record fields,
unknown error names and malformed error options. Output frames and terminal
results require exact envelopes; repeated verdicts, trailing malformed records
and contradictory output fail while preserving the validated prefix. Deadline
expiry still retains completed output records. Existing tests exercise valid
proofs and malformed fields through both direct and parent decoding.

A 117-language witness matrix retains canonical text, PNG and gzip artifacts,
native/isolated results, bounded periodic observations and six termination-proof
cases. Source and installed-wheel observations match on Python 3.12–3.15.
These live execution and JSON witnesses do not close the catalog's independent
trace, failure or resource audits. No persisted format was superseded, so the
supported version-1 loader remains canonical.

All 117 native-result cases now guard both native workers and one-step bounded
workers, without adding collected tests. The shared guard runs two import
controls in each fresh interpreter. The installed matrix matches all 117 native
results, including periodic evidence; at one step, 112 witnesses retain exact
unfinished observations and five complete. Direct bounded execution matches
the debugger too. All four supported Python versions pass. This is witness
coverage, not whole-corpus equivalence; exact workspace accounting and broader
lifecycle acceptance remain open.

Basicfuck uses canonical affine analysis and a reduced decision diagram;
local equal-half reduction and representative-subtable discovery are deleted.
Breadth-first flag placement, gain pricing, complemented output and unconditional
reads remain owned. All 632 corpus programs and 75 larger layouts match byte
for byte; 2,286 paired native/stepped rows retain traces and resource peaks.
The canonical-analysis fault control changes executed answers. Existing bounds,
size pins and the n=4 parity anchor remain unchanged. The wheel matches these
witnesses on Python 3.12–3.15; catalog acceptance stays open.

Workspace witnesses now compare every sample with an independent full-component
width oracle across all 117 models; positive counts alone no longer suffice.
The three non-Boolean samples reach exactly 8, 3 and 1 bits. Missing peaks and
mutable payloads have live refusal controls. Installed Python 3.12–3.15 matches
13,778 accounting observations, including model components, written peaks,
input counters, source steps and output, under the certification import barrier.
An altered baseline is rejected. These are executed witness traces; independent
language-owned component semantics and whole-corpus acceptance remain open.

BrainIf uses canonical decision layers for the default DAG and memoized subtable
folding for width-constrained trees. Local residual interning and string-span
sharing are deleted; jump placement, unconditional reads, spatial markers and
width selection remain owned. All 632 corpus requests and 300 larger layouts
match byte for byte. Both analysis queries have executed fault controls;
2,938 paired rows retain traces and resource peaks, including both width paths.
Bounds, size pins and anchors remain unchanged. Installed witnesses match on
Python 3.12–3.15; catalog acceptance stays open.

The VM no longer re-exports 16 private cycle names. Its annotation uses the
owner module; executable function bodies are identical. The random-machine
protocol check now constructs declared factories instead of inspecting private
class names and constructor signatures. Across 117 runtimes, 16,623 cases and
1,097,759 states match, including 15,647 clean halts, 960 bounded cases and 16
matching runtime faults. Each runtime has output/view fault controls; all timing
ratios pass 0.9. Scope: n<=2, Malbolge n=1, at most 400 steps per case.
The wheel rejects all 16 retired imports on Python 3.12–3.15 while preserving
13,778 accounting observations. Broader semantic/corpus acceptance remains open.

Bitdeque consumes canonical decision layers directly. The emitter no longer
carries source-table copies, a subtree matrix or fixed rotation lists;
address placement, last-level forms, short loads and input polarity remain owned.
All 632 corpus requests and 375 larger layouts match byte for byte. The live
analysis fault changes answers; 2,950 paired rows retain traces, input progress
and resource peaks, including short-load, wrapped and balanced paths. Bounds,
size pins and anchors remain unchanged; catalog acceptance stays open.

Constant-span queries and DINAC share canonical prefix counts. DINAC derives
singleton rows from prefix increments; native flags, reads and polarity stay
owned. Pilas uses canonical subtree ids and inline chunks, deleting its span
memo and rendered-child comparisons; residue cancellation stays owned.

Chicken, Home Row, Sonata, Freestajlo, Unsquare and Whitespace retain canonical
projection, weights and symmetric profiles with native row alignment, pair/run
layouts, literal packing and arithmetic selection. These eight audits retain
bytes and resource scopes with executed analysis faults. The shared-prefix
change preserves all 6,840 catalog artifact requests and declared refusals;
its fingerprint fault control changes all 60 injected requests.

Native, raw-step and debugger parity compares execution observations over all 20
one- and two-input tables for 110 steppable output/dump backends: 7,920 rows,
7,272 ordinary completions and 648 post-halt dumps. Each answer is checked
against its truth table; seeded routes use the same declared seed. Raw active
commands match debugger counts at the exact completion budget, excluding dump
calls. Exhausted budgets fail; idle-step checks cannot skip unfinished runs. All 109 eligible machines preserve observations through three idle steps.
Counter corruption, incorrect source counts and a nonhalting drive have live
controls. The wheel passes the same matrix on Python 3.12–3.15 under the
certification barrier.
Existing slow markers and command/wall budgets remain unchanged. This scope
does not close the remaining periodic, termination, resource or corpus audits.

Termination acceptance covers all 20 one-/two-input tables for three backends:
216 row requests, with 180 executed (91 halts, 89 cycles) and 36 refused by the
unchanged table-dependent source cap. Unary's owned test derives the seven
admitted and nine refused two-input tables from the nine-command budget.
Manual debugger replay checks command counts, input/output observations and
both cycle boundaries. Halting proofs retain unfinished observations before
output finalization; subsequent completion and idle steps match ordinary runs.
All 180 guarded workers match native proofs. Damaged cycle states, counters and
command counts are rejected. The same matrix passes installed Python 3.12–3.15
under the certification barrier. Existing worker deadlines and collected case
counts remain unchanged; larger, branching and periodic acceptance stays open.

Between uses a canonical reduced diagram; local reduction is deleted while
one-first fallthrough and address placement remain owned. 1 + i and Ascenic
use canonical parity recognition instead of building whole parity tables;
complex arithmetic tails and threshold scans remain owned. Balik retains
canonical projection and constant spans with native spatial boxes. All four
have executed query-fault controls. The shared parity query compares bounded,
derived words without copying the table; late faults across word boundaries fail.

All eleven affected backends retain their standard corpus bytes. The four
analysis audits retain 9,144 execution records and 960 larger layouts; the seven
existing parity consumers retain 320 native records and 192 full stepped records,
with Befunge's thirteen-input cap preserved. Their full resource traces above
eight inputs remain unverified: Interprogck8's twelve-input trace reached the
60-second cap at about 24,600 steps. No high-arity peak or full-corpus acceptance
is claimed. Existing bounds, size pins and anchors remain unchanged.

What!? shares change-point analysis across direct and 15-bit block emission.
EGL's redundant generator wrapper is removed. EGL and Qrain retain canonical
projection/symmetry and shared flag analysis; grid layout, queue splitting and
command budgets remain owned. HQ9+ with headers retains native integer packing
and checksums; Unary retains its zero-count codec, canonical dependency/tree
analysis and generation/export caps.

These five audits preserve 3,160 artifact requests (550 declared Unary refusals),
8,580 executed rows and retained accounting captures. All original size/resource
scopes pass; additional paired executions cover every size witness through 22
inputs, including What!?'s 48,912,569-character programs. Existing pins, anchors
and the 0.9 timing floor hold, including block-boundary timings. Installed
Python 3.12–3.15 passes the admitted corpus, six live fault controls and isolated
route comparisons. README and usage guidance no longer advertise the retired
source facade. Catalog-wide acceptance remains open.

Periodic acceptance covers all 72 one-/two-input rows plus the valid empty
program: 73 guarded workers match native results, including zero-stride
completion. Debugger replay reaches both cycle boundaries without publishing
completed output. The independent complex-coordinate model checks grid,
position, instruction, workspace components, visited extent and rendered output;
repeated dumping preserves workspace and output. Damaged states, strides and
pictures have live controls. The matrix passes installed Python 3.12–3.15.
Together the small-table route audits account for all 8,208 row requests across
114 Boolean backends: 8,172 executed and 36 capped. The matrices are repeated against the current operational implementations. Larger-corpus, branching and
remaining semantic-resource acceptance stays open.

Branch evidence requires immutable transition containers and root reachability
for every recorded state and halting endpoint. A terminal cannot be recorded
as an expanded nonhalting state. Partial exploration remains valid evidence of
an any-path halt, but a forked halt cannot decide this run; native and wire
validation now agree. Existing tests reject disconnected graphs, mutable rows,
expanded terminals and unsupported decisions through constructors and worker
decoding, retaining validated output prefixes. Actual random-backend witnesses
require exactly two guarded proofs and ten explicit unforkable-input refusals.
Installed Python 3.12–3.15 passes the same checks. Larger branching coverage and
remaining migration acceptance stays open.

CARP consumes canonical decision layers without retaining a table, prefix
classifier or subtree matrix; register/address placement remains owned.
BFStack retains canonical weighted/symmetric analysis and derives byte alignment
from the last zero row without enumerating starts. bit~ retains canonical affine
and projection queries with native paired windows. Dimensional shares canonical
change points across both paint polarities; counted movement and physical pair
encoding remain owned. All four have executed query-fault controls.

All 2,528 standard requests and 960 larger layouts match byte for byte;
9,144 paired execution records preserve traces and resource peaks. Boundary
witnesses add 1,283 native and 30 stepped records, including all byte rows for
five BFStack tables, CARP at fourteen inputs and refusals above its cap.
Bounds, size pins and anchors remain unchanged; catalog acceptance stays open.

AddSubJump consumes canonical residual constants instead of building a second
constant-span index; recursive emission no longer retains redundant row spans.
Self-modifying branch placement, shared labels and packed selection remain
owned. All 632 corpus requests and 240 larger layouts retain their bytes;
2,286 native/stepped records retain 77,350 resource and snapshot samples.
A live constant-map fault complements the executed tree. Bounds, size pins and
anchors remain unchanged; catalog-wide acceptance stays open.

Back uses canonical subtree IDs for constant folding in both comb and H-tree
layouts; duplicate prefix-count indexes and the context's classifier field are
removed. Native beam placement, pair finishers and fall-through planning remain
owned. The independent drawing oracle retains its prefix classifier. All 632
corpus requests and 240 larger layouts retain their bytes; 2,286 paired rows
retain 75,368 semantic samples. Live ID faults damage both executed layouts.
Bounds, size pins and anchors remain unchanged; catalog acceptance stays open.

Cycle construction now rejects Boolean, fractional, nonfinite and unavailable
counters before comparison, matching transport's actual-integer requirement.
Snapshots must be hashable. Existing tests cover each boundary/stride position,
mutable snapshots, valid zero-stride records, JSON round trips and rejected
worker frames retaining their output prefix. Installed Python 3.12–3.15 passes
these checks plus the 73-case periodic and 180-row termination matrices.
Canonical fields and generation/resource budgets are unchanged. Remaining
larger-corpus, branching and semantic-resource acceptance stays open.

Container uses canonical subtree IDs to skip equal halves, without retaining
or slicing a second truth table in its planner. Threshold emission uses canonical
change points and a base bit, removing the full integer/delta arrays. Tick pulses,
shared-parent relays, names, signed rules and block encoding remain owned.
All 632 corpus requests and 240 larger layouts retain their bytes; 2,286 paired
execution records retain 20,988 semantic samples. Live query faults damage both
executed constructions. Bounds, size pins and anchors remain unchanged;
catalog-wide acceptance stays open.

RAM0's width-one fallback uses canonical subtree IDs instead of repeated slice
classification. Unary pair leaves lower directly to native NAND references;
gate interning, allocation order and unary addresses remain owned. The ordinary
tree retains canonical subtree slots. Both routes have executed ID-fault controls.
All 632 corpus requests and 240 larger layouts retain their bytes; 4,406 paired
rows include exhaustive width-one execution through three inputs, preserving
1,330,216 semantic samples. Bounds, pins and anchors remain unchanged;
catalog acceptance stays open.

Alight retains canonical weighted projection; notation-specific literal packing,
width planning and the fold remain owned. ABCDirection retains canonical
input dependency/projection; byte teeth, tape moves and helix planning remain
owned. Neither emitter duplicates Boolean analysis or needs a compatibility
adapter. Their imported canonical queries have executed fault controls in both
default and balanced routes, including Alight's two expression notations.

All 1,264 corpus requests and 1,200 larger layouts retain their bytes; 11,430
paired records preserve 1,176,344 semantic samples. Alight's four dialect
combinations cover all small tables and larger layouts through ten inputs,
including packed pairs; ABCDirection's byte progress and final cycle agree.
Emitter source, bounds, pins and anchors remain unchanged; catalog acceptance
stays open.

Operational JSON objects now reject duplicate fields, including nested and
Unicode-escaped equivalent names. One parser hook covers portable programs,
PNG source metadata, CLI settings, registry scaling data and worker requests
and responses. Malformed worker frames retain only the validated output prefix;
capped streams still kill and reap their child. Existing tests include equal
repeated values and preserve separate CLI overrides and future PNG versions.
Canonical version-1 formats remain supported; catalog acceptance stays open.

Deadfish, HQ9+ and Nope. workspace captures now match independent semantic
traces at every observed boundary, including idle steps after halting. Charged
peaks are checked against complete independently predicted components, rather
than machine state copied into a second model. Ten live component-erasure
faults preserve execution but fail capture checks. Deadfish/HQ9+ long traces
remain bounded at 64 commands; this does not close whole-corpus acceptance.

thisthat uses canonical essential-input queries in all four consumers and
canonical decision layers for its shared DAG. The duplicate dependency detector,
representative-row map, child reconstruction and strip-span scan are removed.
The strip uses canonical constant IDs. Distinct-parent counts, terminal buses,
router placement and the admission envelope remain owned.
All 632 corpus requests and 240 larger layouts retain their bytes; 4,406 paired
execution records retain 174,086 semantic samples, including every small strip.
Dependency, projection, strip and DAG queries have executed fault controls.
Bounds, pins and anchors remain unchanged; catalog acceptance stays open.

Forþ, Unlambda, Circlefuck, Eval and Object disoriented retain canonical
projection, symmetry and subtree analysis. Heap dispatch, promise binding,
base-128 deletion, Gray stack layout and class pricing remain owned.
Circlefuck's redundant generator wrapper is removed; Eval's unused stack-role
constants move to their sole test consumer. Eight live analysis faults change
executed answers, including false residual sharing and both Eval stack layouts.

The five audits preserve 3,160 artifact requests, 10,600 executed rows and
2,341,769 complete state samples. Unlambda's rendering-based audit hit 60 s;
C graph serialization retains every sample and per-step snapshot-isolation
check, completing within the same cap. Timing preconditions equalize initial
GC state and include induced cleanup; same-function and double-work controls
validate the unchanged 0.9 floor. Original resource, scaling, pin and anchor
scopes remain. Installed Python 3.12–3.15 retains corpus execution, artifact
round trips, retired-import refusals and guarded workers without certification
imports. Catalog-wide acceptance remains open.

Seven more independent models predict workspace captures and charged peaks:
AddSubJump, ArrowQueue, Back, BASICER, Blindfolded Arithmetic, Crement and
HQ9+ with headers. They retain bounded traces, failed steps, input progress
and post-halt dumps. Thirty new live controls reject erased fields or phantom
storage without relying on output changes. The independent AddSubJump witness
found writes below −9 retaining unreadable cells; those writes now drop as
specified. Of 5,200 paired traces (3,217 clean halts; 250,694 states), all 59
changes consist only of discarded negative cells. Catalog acceptance stays open.

6-5 shares canonical subtree IDs across marker counting, lazy-read counts and
emission, removing three constant-span indexes and the tree's classifier field.
Private marker callers now pass IDs; no old-signature adapter remains. Label
budgets, held-cell arithmetic, positional walks and conditional strides stay
owned. All 632 corpus requests and 240 larger layouts retain their bytes;
2,286 paired records preserve 58,808 semantic samples. Another 1,344 private
candidates retain marker counts and bytes, with 9,104 native rows executed.
Subtree, stored-input and weighted-lookup queries have live faults. Bounds,
pins and anchors remain unchanged; catalog acceptance stays open.

Ten more owned models predict complete workspace captures and charged peaks:
B-tapemark, Balik, Between, Bit~, Bitdeque, Bitwise Cyclic Tag, BrainIf, CARP,
Cyclic Tag and Taglate. Reference payloads retain marker-grid coordinates,
rebased tape extents, live tag suffixes, answer latches, variables and input
progress. Thirty-eight live component-erasure controls preserve execution but
fail resource checks. Failed and post-halt boundaries remain covered at each
model's existing step cap; whole-corpus and catalog acceptance stays open.

Eight more owned models predict workspace payloads and charged peaks:
Aprknia, Ascenic, Circlefuck, Clockwise, Codesick, Collatz Multiverse,
Container and DINAC's straight-line fragment. DINAC independently derives
future scope slots, root-block cursors and retained null declarations, including
empty frames after halt. Thirty-one field-erasure controls, a null-type
omission and reversed scope slots preserve execution but fail resource checks. The common observer
accepts a modeled null state only at a halted boundary; malformed-source
controls remain strict. Existing step caps remain; broader acceptance stays open.

Shakespeare uses canonical parity analysis. Grapheme's wrapper and brainfuck's
`bf_tree` alias are removed. These backends, /// and Underload retain canonical
projection, weights, affine or subtree queries. Signed packing, decimal lifts,
flag budgets, directional rewrite sweeps and terminal/carry pricing remain
owned target constructions. Nine live analysis faults change executed answers.

The five audits preserve 3,912 artifact requests, 16,960 executed rows and
1,348,793 complete state samples, including both Grapheme dialects and narrow
Underload selectors. Another 1,050 layouts and 253 size witnesses retain bytes
and paired execution; original resource, scaling, pin and anchor scopes pass.
All 72 balanced generation comparisons pass the unchanged 0.9 floor. Adaptive
repeat counts fix an audit timeout without changing its 60 s cap or sample
floor; double-work controls still fail. Installed Python 3.12–3.15 preserves
execution, round trips, retired-import refusals and guarded isolated workers.
Catalog-wide acceptance remains open.

DINAC has independent call-frame witnesses for nested overloads, recursive IFs,
WHILE calls, void fallthrough, input/EOF and three typed-call failures. Named
call and block rules derive all 38 traces without the production parser or
transition. Raw, VM and debugger routes match complete frame payloads and
charged peaks; native and 38 import-guarded workers match results and partial
failures. Ten live faults cover caller retention, pending/returned values,
block stacks, function identity, scope, frame order, output, input and stalls.
All traces remain within 48 commands; larger-program acceptance stays open.

Boolfuck uses canonical constant IDs for normalized-gate folding, removing a
second span index and its classifier field. Affine, symmetry, projection and
flag queries remain canonical; two-input normalization is native gate lowering.
Painfuck retains canonical affine/flag-bank analysis and its command-cycle codec.
Pointless retains canonical subtree analysis and native function inlining.
Canonical queries have executed fault controls; the latter two emitters are
unchanged. No compatibility adapters are needed for these constructions.

All 1,896 corpus requests and 720 larger layouts retain their bytes; 6,858 paired
records preserve 1,138,437 semantic samples. All sixteen normalized gate words
execute across 8,192 nine-input rows with matching bytes and answers; timed
programs add 165 sampled native rows through twelve inputs. Original bounds,
pins and anchors remain unchanged; catalog acceptance stays open.

FRACTRAN uses canonical decision reduction, retaining first-encounter postorder
for state-prime assignment. Quassaunt's duplicate name encoder is removed;
its size provider uses the canonical helper. Modulous, NOR machine and
Nandypants retain canonical projection, symmetry or subtree analysis. Pair
walks, accumulator muxes, read-depth ladders and forward-label layout remain
owned. Eight live query faults alter executed answers, including leaf-name
collisions and Modulous's paired counter path.

The five audits preserve 3,260 artifacts, 16,960 rows and 1,575,849 complete
state samples, including narrow Modulous and FRACTRAN layouts. Another 875
layouts and every declared size witness retain bytes and paired execution.
Quassaunt retains all size arities through 21: executed witnesses reach
28,512,257 characters and 5,119,370 commands, each below its unchanged 60 s
cap. Original resource, size, pin and anchor scopes pass; all 60 generation
timings pass the 0.9 floor. Installed Python 3.12–3.15 preserves round trips,
execution, live faults, retired imports and guarded isolated workers.
Catalog-wide acceptance remains open.

Eleven more independent models predict complete workspace payloads and peaks:
CreativeScript v2, CVNC, Decleq, DIG, EGL, Fackward, Freestajlo's linear
fragment, Grapheme, Home Row, Hot and IEBEL. Fifty-seven component-erasure
controls preserve execution but reject incomplete captures. DIG models read
operations before numeric conversion; Freestajlo predicts token positions,
stack orientation and inactive stores. Decleq's memory observer accepts an
explicit independent resource projection. IEBEL reuses immutable views of equal
register maps; 2,735 before/after model comparisons and a live comparison fault
retain the corpus while meeting the fast band. Existing caps and broader
acceptance remain open; Dimensional still needs allocated-hierarchy modeling.
Shared immutable model declarations compact 39 owned resource fixtures without
changing cases: before/after digests retain 414,385 captures, 310 refusals and
101,919 observed records; an altered-width control is detected. The existing
source/test line budget remains enforced.

Flowchart reuses canonical subtree IDs for stacked constant spans and repeated
shared drawings, removing a second span index and its classifier field.
The unpruned band frontier no longer indexes dummy data. Dependency projection
and flat span queries remain canonical; deque addressing, drawing order,
sharing eligibility and grid layout remain owned. Four executed query faults
alter answers; a forbidden-query control covers the dummy frontier.

All 632 corpus requests and 240 larger public layouts retain their bytes.
Native/stepped pairs preserve 2,286 records and 108,219 state/resource samples.
All 1,344 private layouts preserve source and ordered sharing counts; 9,020
native rows execute through eight inputs. The combined audit exceeded 60 s;
priced arity cohorts pass. A ten-input dense baseline exceeded its existing
2 s execution cap: its source matches, but execution acceptance stays open.
Another 144 native rows cover timing fixtures at four and eight inputs.

All 36 generation timings through twelve inputs pass the 0.9 floor (minimum
median 0.979), with matched hash seeds and garbage collection included.
Installed Python 3.12–3.15 preserves the paired records and larger layouts.
All 915 size measurements, original bounds, pins and anchors remain unchanged;
the referee gate passes. Catalog-wide acceptance remains open.

Dimensional's bounded independent model now predicts allocated hierarchy,
height, empty levels and stored zero cells. The prior semantic projection
retains 367 comparisons and 3,388 boundaries; an altered-trace control fires.
Six component erasures and three allocation-only faults supplement the three
semantic faults. Installed Python 3.12–3.15 runs the raw corpus and 13 public
cases across VM, debugger, native and guarded isolated routes, including input
failures: 164 VM/debug boundaries and literal peaks 2, 5, 11 and 14 bits.
Deadfish and HQ9+ drop duplicate same-payload meters while retaining independent
peak predictions. Whole-language and catalog-wide acceptance remain open.
Eight owned models share ordered component-name parsing; corpus digests retain
62,382 captures, 79 refusals and 14,038 observations, with an altered-width
positive control. This preserves the source/test line budget after integration.

Worker requests reject truthy flag substitutes, untagged decimal integer
fallbacks, incoherent setting tags and malformed raster runs before execution.
The baseline executed numeric flags and untagged step limits; raster decoding
also discarded fourth channels and zero-count rows, and accepted Boolean
counts. Live refusal controls retain text, gzip and raster requests, signed
seeds and limits beyond the decimal-rendering cap. No persisted format changes;
canonical version-1 artifacts remain supported. Final tree-wide retirement and
catalog acceptance remain open.


Owned PNG metadata requires a positive integer version; malformed or missing
versions no longer discard provenance by falling back to plain pixels.
Eleven refusal controls retain plain PNG, optional v1 metadata and future
integer-version pixel readability. Both raster backends retain portable
bytes and four executed answers. No supported persisted format is retired.
Broader compatibility and catalog acceptance remain open.


Scale acceptance uses declared machine capabilities, removing both interpreter
flags and the absent-flag fallback. Crossed declaration/flag controls retain
explicit PNG scale overrides and reject a disabled declaration. All 117
capability queries run without importing an interpreter; a blocked-import
positive control fires. Both raster corpora preserve 2,192 clean halts and
traces each, with output-fault controls and unchanged throughput above 0.9.
Source loading uses declared policies instead of discovering interpreter hooks.
All 1,414 container/error records match across 117 languages, including literal
file newlines and retained gzip objects. Native entry points use canonical
loaders; Unary now reads its exported gzip files with unchanged prompts.
Snapshot-record refusal controls traverse nested as well as root records.
Raw non-finite cycle scalars are rejected before encoding and after decoding;
finite floats and Chicken’s canonical snapshot sentinels remain supported.
Four native corpora retain 6,718 programs, 6,651 clean halts and 218,321
trace observations. Five public file routes retain matching results and
median throughput ratios of 0.994–1.016 against the baseline.
Unrelated acceptance remains open.

Worker hexadecimal scalars use their encoder spelling; byte tags no longer
accept whitespace or uppercase, and snapshot sets reject duplicate/equal members
instead of discarding evidence. The bounded 114-backend probe retains 1,584
supported snapshots and 86 halts with matching baseline records. It exposed
ten unsupported snapshot families, addressed by the following batch. This probe
is not full lifecycle acceptance.

Snapshot transport retains exact rational numerators/denominators and declared
frozen records. Three owned codecs project persistent grid marks, scope bindings
and continuation frames without changing native structures. Malformed fractions,
unknown codecs and lossy container payloads fail with retained output prefixes.
All 114 Boolean backends round-trip 1,734 bounded snapshots; the ten repaired
families additionally execute 1,482 corpus programs (1,469 clean halts and
65,801 observations), checking successful snapshots through JSON. Native and
worker termination evidence agrees on nine cycles and thisthat’s closed graph.
Seven changed native interpreters retain 53,492 matching observations and
throughput ratios 0.996–1.002, with live output-fault controls for each.
The CSV’s `snapshot_transport` column records this bounded evidence separately
from whole-language acceptance; interpreter-only transport follows below.

The installed runtime/import witness now covers all 117 languages on Python
3.12–3.15: catalog/describe, 114 generated artifact round trips, native execution,
116 debugger halts and one periodic boundary replay. Every language also runs
in a fresh worker behind a fatal certification-import barrier, matching its
native result; barrier controls fire before execution. Reference-language EOF
and step-limit failures retain their prefixes and observations. All 832 packaged Python files
match tracked source, with no extra wheel modules. Known retired imports,
constructor aliases, callable proxies and source/scale hooks remain absent.
Source tests guard the existing ordinary, post-halt, periodic and dynamic
completion workers without duplicating their runs. Snapshot checks now include
the three interpreter-only languages: VM and debugger retain 1,747 boundaries
each, with transported history unchanged by later steps. The CSV records runtime
import isolation separately from pending certification claims; bounded route
parity does not complete independent accounting or whole-language acceptance.

Compressed source requires an actual gzip member. Zero-byte payloads no longer
masquerade as valid empty programs through constructors, version-1 documents
or workers; failures precede execution. Valid empty, padded and concatenated
members retain their bytes and UTF-8 behavior. Before/after portable records
and executed results match for all 117 languages, including 115 gzip-wrapped
text executions and 345 empty-member documents with present, null or omitted
limits. Supported version-1 settings and limit forms remain unchanged.
Installed Python 3.12–3.15 repeats these checks with the image extra and all
115 text languages without it; PNG still requires the extra. All 832 packaged
Python modules match source bytes.

Qoibl and Taglate use canonical input projection; live complemented-analysis
controls change every executed answer. Packed-literal polarity/Horner layout
and 16-bit nibble/queue selection remain emitter-owned: the shared OISC decoder
emits different instructions. All 2,760 programs through n=3 retain bytes across
default, widths 1/3/20 and balanced layouts; 21,200 rows execute correctly with
19,087,176 command boundaries checked against raw-state widths and proof bounds.
All 16 existing size/command pins retain 152 executed rows; measured generator
throughput ratios are 0.987 and 1.000. The emitters and size anchors are unchanged.
Qoibl bounds now count actual assignment markers and Horner scratch/cursors.
Width-1 `01` needs 40 commands and 35 bits, versus the prior 7 and 24; default
n=10 parity reaches 2,072 bits, exceeding 2,071. The corrected default-layout
formula, generated proof table and n=10 regression retain exact witnesses.
These two analysis rows are audited; broader lifecycle/accounting acceptance
and the remaining backend rows stay open.
Installed Python 3.12–3.15 repeats both default corpora, raw-language oracles,
analysis faults, narrow layouts and n=10 bounds against byte-checked modules.

Forbin uses canonical input projection, constant spans and subtree IDs; three
live analysis faults change executed answers. Painted blocks, lexical names,
register dispatch and width selection remain emitter-owned. All 1,400 programs
retain bytes across default, widths 1/4/13 and balanced layouts: exhaustive
n=1..3 plus projected, constant-span and repeated-block witnesses at n=8..9.
All 11,100 selected rows execute correctly; default command/workspace bounds
hold. Eight size/command pins retain 76 executed rows, and the 80/3,111/10,224
character anchors retain executed witnesses. Generator throughput ratio is
1.004; emitter, bounds and size anchors are unchanged. Installed Python
3.12–3.15 repeats the corpus, projection/subtree faults and pins against all
832 byte-checked Python modules. Only this backend's analysis row is closed;
catalog lifecycle, accounting and certification acceptance remain open.

3x groups repeated blocks by canonical subtree IDs, replacing its duplicate
string recognizer. Gain, overlap selection, flags, key allocation and emission
order remain owned. Disabling shared analysis removes an executed size saving;
projection faults change answers. Inject retains canonical projection/subtree
analysis; complemented tree, halving and narrow-chunk controls change answers.
Forward escapes, regex spelling and chunk/width selection remain owned.
All 2,890 programs retain bytes across default, widths 1/3/20 and balanced
layouts: exhaustive n=1..3 and structured witnesses through n=10. All 22,690
selected rows execute correctly over 3,037,934 command boundaries. Default
resource/size bounds hold within declared scopes; exact n=5 resource witnesses,
16 size/command pins and six executed size anchors remain unchanged.
Generator throughput ratios are 0.980 and 0.985, above 0.9. Installed Python
3.12–3.15 repeats both default corpora, larger layouts, analysis faults, pins,
anchors and the independent 3x native oracle against 832 byte-checked modules.
These two analysis rows are audited; broader acceptance remains open.

Decleq classifies constants through canonical subtree IDs, removing its duplicate
span index and classifier fields. Zero-selector private builders retain their
literal base case. Subleq and S*bleq retain canonical branch/packed queries.
S*bleq's streaming cost census stays owned: a canonical DAG prototype matches
296 floors but takes 29% more unit time and twice the peak RSS at n=20.
Six semantic query faults and two executed cost-selection controls remain live.

The audits preserve 1,956 artifact requests, 6,360 paired rows and 548,834
complete semantic samples. Larger layouts, pins and declared size witnesses
retain bytes. All 70 S*bleq size families at n=19..25 execute; the largest is
13,427,166 characters. Original scaling nodes pass through n=25. Subleq's
n=9 resource node exceeds its unchanged 60 s audit cap; separate full-table
checks cover all eleven tables and 5,632 rows under that cap, reaching both
exact bounds. The whole-node timeout remains a finding. Catalog acceptance
stays open.

Fargo's packed ANF transform and word-width rule move to canonical analysis;
its two test consumers migrate and the emitter exports neither old helper.
Davio/OR choices, scalar/word grains, expression interning, profitable names
and width/balance races remain owned. An injected coefficient fault changes
all executed answers. All 652 corpus artifacts, 2,120 paired rows and 48,262
semantic samples match; another 175 layouts and 57 size witnesses retain
bytes and paired execution. Pins, resource/scaling/anchor scopes and twelve
balanced timings pass unchanged. Catalog acceptance remains open.

INTERCAL and SStack retain canonical decision, subtree and repeat queries.
Mux frames, selector aliases, array spill, guarded labels and binary-bank
prices remain owned constructions. Two semantic query faults change executed
answers; disabling SStack's repeat query grows an executed bank from 19,879
to 22,097 characters. INTERCAL's generator `TEMPLATE_CHAR` re-export is removed
in 2.0; its sole test consumer imports the descriptor declaration.

The audits preserve 1,304 artifact requests, 4,240 paired rows and 54,420
semantic samples. Set captures compare canonically across hash seeds; an
erased-component control changes traces while preserving source and results.
Another 350 layouts and all declared size families retain bytes and execute.
All 87 INTERCAL families at n=17..24 execute, reaching 16,504,601 characters;
all original scaling arities through 24 pass. Pins, resource/anchor scopes and
24 balanced timing comparisons pass unchanged. Catalog acceptance stays open.

APL's complemented decision indexing moves to canonical analysis; selector
names, arithmetic twins and width/balance prices remain owned. Its `_Key`,
`_Ref` and `subtree_ids` exports disappear. Blindfolded Arithmetic and Minsky
Swap retain canonical parity, projection and weight queries; signed octal
register construction, held-input cascades and setter bindings remain owned.
Five query faults change executed answers. Disabling the arithmetic parity
query grows an executed program from 1,415 to 1,709 characters.

All 1,956 corpus artifacts, 6,360 paired rows and 210,047 semantic samples
match. Captures omit only the salted workspace hash cache; an integer-payload
fault changes traces while preserving results and counters. Another 525
layouts retain bytes and execute; all declared size, resource, scaling and
anchor scopes pass. Pins and 36 default timing comparisons pass unchanged;
eight APL balance trials retain a 0.996 speed ratio. Catalog acceptance
remains open.

FALSE uses canonical child layers; lambda stores, formula split prices and
signed literal packets remain owned. B-tapemark retains canonical projection;
copy, narrow/folded geometry and both swap-marker dialects remain owned.
Four public query faults and twenty direct nonconstant shared-diagram rows
change executed answers. Disabling projection grows the new/old dialect grids
from 1,500/1,425 to 6,426 cells; both enlarged programs execute correctly.

All 1,956 artifacts, 6,360 paired rows and 784,830 semantic samples match.
Another 276 direct FALSE diagrams retain bytes and execute every small row.
All 525 larger layouts, 162 size witnesses, pins, scaling/anchor scopes and
36 balanced timing comparisons pass. Constant-input checks share one runner
without dropping arities, layouts, read ordering or following-record checks.
The eight-input B-tapemark resource aggregate hits its unchanged 60-second
cap; all ten full-table checks pass separately, retaining all 2,560 rows and
both exact maxima. Other resource arities pass, including FALSE at nine.
Catalog acceptance remains open.

Interprogck8 retains canonical subtree/parity queries and native flight windows.
Its cap moves to `descriptor.MAX_INPUTS`; both old `_MAX_INPUTS` exports vanish.
ROTfuck retains canonical dependency/projection/symmetry queries and native
rotation, seek padding and radix choices; `_ROTFUCK_CHAIN` disappears.
Super SNUSP derives its four intrinsic gates without `_TWO_INPUT_SHORT`;
its test owns independent spellings. General projection remains canonical.
Canonical queries made two-input projection generation 5.47 times slower;
the native operator rule passes all sixteen timing cases, minimum ratio 0.9385.

All 2,608 artifacts, 8,480 paired rows and 2,430,158 semantic samples match.
Six query-fault contexts change answers; four cost controls enlarge executed
programs. All 700 larger layouts and 318 size witnesses retain bytes and run,
including both rotations and the sixteen-input decimal literals. Pins,
scaling/anchor scopes and 48 larger-input timing comparisons pass unchanged.
The ten-input Interprogck8 resource aggregate hits its unchanged 60-second
cap; all twelve full families pass separately, retaining all 12,288 rows and
the exact 18,878-command maximum. Other resource arities pass. Catalog
acceptance remains open.

Befunge, Fish and Piet use canonical little-endian packed cells, preserving
partial-word complements. Piet's literal/majority classifiers and Ant's
threshold classifier move to lookup analysis; reads, candidate prices, corridors,
nibble interleaving, coordinate precision and codel geometry remain native.
Piet's former generic raster package is deleted; its operations and layouts
belong to the backend. Ant's `_near_unanimity` and Befunge's generator
`MAX_INPUTS` exports disappear; the declared Befunge cap remains thirteen.

All 2,628 artifacts, 8,552 paired rows and 434,724 semantic samples match,
including periodic Ant evidence and Piet scale two. Six live query faults change
50 executed answers; disabling Ant's threshold shortcut enlarges three executed
programs. All 700 larger layouts, 191 size witnesses, 35 pins, ten anchors and
original resource/scaling nodes retain their results. The twelve-input Ant
parity aggregate hits its unchanged 60-second cap; separate layout checks retain
all rows under that cap. All 60 timing comparisons pass (minimum ratio 0.9918),
including separate cold and hot Piet construction. Installed Python 3.12–3.15
checks execute 8,552 rows and fifteen isolated workers each with the image extra;
retired imports fail and certification/proof imports remain blocked. Sixteen
backend audits remain; catalog acceptance stays open.


Clockwise, ArrowQueue, Collatz Multiverse, Crement and CV(N)(C) use canonical
constant analysis. Collatz packing and exceptional endpoints move to lookup;
Crement uses canonical reduced diagrams, retaining native patch/address order.
Its independent unshared oracle moves into tests; `_Ref` and `_crement_ordered`
are removed. Queue folds, ring geometry, Collatz code prices and CV(N)(C)
syllable/jump construction remain emitter-owned.

The four-backend corpus preserves 2,608 artifacts, 8,480 rows and 401,708 semantic
samples; Clockwise separately preserves 652 artifacts, 8,480 layout rows and
1,556,056 samples. The four retain 700 larger layouts, 225 size witnesses,
32 pins, ten anchors and all 43 resource/scaling nodes. All 64 timing contexts
pass (minimum ratio 0.9493); Clockwise's 28 pass at 0.9759 minimum. Twelve live
query faults change 79 executed answers; five cost controls enlarge correct
programs. Installed Python 3.12–3.15 checks execute 8,480 rows, fourteen isolated
workers and all fault controls each; retired imports fail and certification/proof
imports stay blocked. Clockwise has separate installed and resource evidence.
Eleven backend audits remain; catalog acceptance stays open.


Nonhalting branch proofs reject empty successor rows at construction, decoding
and search. Interprogck8 propagates unknown-instruction errors instead of
turning them into a false divergence verdict. Native, Boolean, proof and result
routes raise the same `HaltError`; valid halts and closed cycles remain accepted.
Constructor, wire and worker-envelope controls retain partial-output assertions.
Branching IO observation acceptance remains open.


Thue uses canonical constants at the root and folded halves, alongside its
canonical projection, subtree and residual queries. Bit-reversed entry emission,
pair-expansion symbols, chunk names and native rule/layout prices remain owned.
The parent replay binds all archived callbacks, including balancing: 1,932
artifacts, 12,720 paired rows and 293,472 semantic samples match exactly.

All 336 larger layouts and 1,344 executions retain bytes, answers, unique
rewrites and input progress, including every twelve-input row leaf from the
original timed-out aggregate. Sixty timing contexts pass (minimum ratio 0.9949).
Six semantic faults change 263 executed answers; fifteen cost controls enlarge
correct programs, including three actual subtree-sharing candidates. All eight
pins, three size anchors and seven resource/scaling nodes pass unchanged.
Installed Python 3.12–3.15 checks each execute 6,360 rows, five guarded workers
and all fault controls; certification/proof imports stay blocked. Ten backend
audits remain; catalog acceptance stays open.


Circuit Diagram uses canonical constants throughout scalar, forest and pool
classification, and canonical full-parity recognition. Reduced diagrams and
projection remain shared; wire geometry, gate/read accounting, H sites, class
masks and candidate prices remain emitter-owned. All 1,932 artifacts, 14,840
paired rows and 97,326 semantic samples match; 336 larger layouts and 1,344
paired rows also match. Ten pins, four size anchors and seven resource/scaling
nodes pass unchanged. Sixty timing contexts pass (minimum ratio 0.9887).

The twelve-input dense width-one aggregate hits its original 60-second cap
because large topologies are intentionally reparsed per machine. The harness
reuses one exact compiled topology, delegating nested function compilations;
all original rows and native/counted checks pass without raising the cap.
Eight live semantic faults change 31 answers; two validation probes and eleven
executed cost controls also fire. Installed Python 3.12–3.15 checks each execute
6,360 rows and five guarded workers, including EOF-as-zero and malformed-source
result equivalence; certification imports stay blocked. Nine backend audits
remain; catalog acceptance stays open.

Dig shares binary row weights between alternating and indexed leaves; the
duplicate leaf helper is retired. Parity, dependency, projection and span
queries remain canonical. Adder clearance, forced reads, corridor sharing,
prefix stamps and ordered one-digit class admission remain emitter-owned.
All 1,932 artifacts, 16,960 paired rows and 603,272 semantic samples match
across seven public layouts and the private unshared construction. All 240
larger layouts and 960 paired rows match; six direct constructions add 37
rows and 10,218 samples, including thirteen- and seventeen-input gaps.

Eight pins, two size anchors and ten resource/scaling nodes pass unchanged.
Sixty timing contexts pass (minimum ratio 0.9913). Seven semantic faults change
334 answers; two validation probes fire. Consolidated test imports preserve
every prior assertion, case and oracle. Installed Python 3.12.11, 3.13.15,
3.14.7 and cached 3.15.0rc1 checks each execute 6,360 rows, five guarded workers
and all faults; every binary mask through seven inputs passes. EOF and invalid
operation errors retain partial output and agree across native/isolated routes.
Eight backend audits remain; catalog acceptance stays open.


LaserFuck uses canonical constant recognition; weighted lookup and subtree
identities remain shared. Reader placement, beam funnels and path-sized leaf
retirement remain native: equal residuals retire different path bits. All
1,932 artifacts across seven layouts match. Default execution through three
inputs and seven layouts through two inputs retain 2,552 paired rows and
3,726,956 semantic samples. All 288 larger layouts and 1,152 paired rows match;
twenty direct constructions retain 256 rows and 301,628 samples over all four
verified initial headings, including constants through sixteen inputs.

The sixteen-input AND emits 984,713 characters, occupies 2,165,193 character-grid
cells and executes 721,794 steps on its all-ones row. Four faults change 120
executed answers; eight cost controls retain correct answers across 176 runs.
Two validation controls fire; all 170 owner/budget tests pass, with prior test
assertions, cases and oracles preserved after import consolidation.
Eight pins, six size anchors and eleven resource/scaling nodes pass unchanged.
Sixty timing contexts pass (minimum ratio 0.9911); all 160 default-constant
heading witnesses satisfy their execution bounds. Installed Python 3.12.11,
3.13.15, 3.14.7 and cached 3.15.0rc1 each round-trip 828 artifacts and execute
408 rows from 84 programs, plus five guarded workers and all fault/cost controls.
EOF after zero or one input preserves progress and agrees across native/isolated
routes; certification imports stay blocked.
Seven backend audits remain; catalog acceptance stays open.


Line already uses canonical residual IDs, dependencies, projection and
permutation. No analysis implementation needs replacement. Read schedules,
correction opcodes, stroke extents, interior joins, return bays and layout
selection remain native; this audit changes no executable code.

All 572 artifacts execute through serialized PNGs with no retained graph
payload: 4,312 PNG/VM/graph row comparisons retain 58,708 semantic samples.
Default and balanced layouts cover every table through three inputs; scale two
covers every table through two. Eighteen larger layouts execute 72 native/counted
row pairs, including the 23,976,000-pixel anchor and sixteen-input projection.
Five query faults change 114 bitmap-executed answers; two cost controls retain
correct output across 256 runs while increasing actual pixel area.

All 335 selected fast/medium owner tests, eight pins, three size anchors and eight
resource/scaling nodes pass. Sixteen cases remain outside that selection;
one support module defines no tests. Executable identity is checked against
803b83ae8; measured acceptance scopes retain their original sixty-second caps,
without claiming a before/after performance ratio for unchanged code.
Installed Python 3.12.11, 3.13.15, 3.14.7 and cached 3.15.0rc1, with the declared
image extra, each round-trip 572 artifacts and execute 344 rows from 76 programs,
plus five guarded workers and all fault/cost controls. Native/isolated EOF
observations agree after zero and one input; certification imports stay blocked.
Six backend audits remain; catalog acceptance stays open.


Malbolge uses canonical constant, dependency, projection and popcount queries;
three local analysis helpers are retired. Digit gadgets, discarded-read placement,
navigation and source-cell labels remain native. Canonical single-input projection
uses block slices: 263,900 comparisons match the former gather, exhaustive through
four inputs and sampled through seventeen. Seventeen timing contexts pass eight
alternating trials per side (minimum ratio 0.9897); failed scan/gather probes remain
recorded without changing the 0.9 floor.

All 1,445 artifacts match the saved generator across default, widths 1/13/200 and
balanced layouts; 11,005 native rows execute, including both seventeen-input
families and multiple ignored inputs. Five direct before/after traces retain
62,314 semantic samples. Four query faults change executed answers; three admission
controls fire. Eight pins, one size anchor, constant size ranges and eight
resource/scaling nodes pass unchanged. Consolidated tests retain their cases,
independent oracles and input/output/sentinel checks; `just test` passes 16,259
cases with twelve skips.

Installed Python 3.12.11, 3.13.15, 3.14.7 and cached 3.15.0rc1 each round-trip
1,380 artifacts and execute 680 native/VM rows, 3,669,670 commands and 6,120
command/final workspace samples. Six guarded workers cover success, EOF-as-value
and command-limit failures; three installed query faults fire. Certification
imports stay blocked. Five backend audits remain; stable 3.15 final and the
catalog-wide lifecycle/accounting acceptance stay open.


Packlang already uses canonical dependency/projection weights and subtree IDs.
No executable change is needed. Block offers, array writes, fill/punch/run costs,
alias prices, alternating counters, literal spelling and token/statement packing
remain native. Source identity is checked against 601fe5c7e; all original
sixty-second acceptance caps hold, with no invented before/after timing ratio.

Both literal policies pass all seven layouts through three inputs: 3,864
artifacts, 29,680 native/VM row comparisons and 714,644 semantic samples.
Thirty-two larger layouts retain 128 row comparisons, including sixteen-input
gaps and repeated blocks. Three semantic faults change 207 answers. Disabling
subtree sharing grows an executed witness from 2,892 to 3,621 characters across
eighteen correct runs; two validation controls fire. All 140 owner/budget tests,
eight pins, three size anchors and fifteen resource/scaling nodes pass.

Installed Python 3.12.11, 3.13.15, 3.14.7 and cached 3.15.0rc1 each round-trip
3,864 artifacts and execute 1,904 native/VM rows from 392 programs, plus twelve
guarded workers and all fault/cost controls. EOF-as-value and command-limit
failures agree across native/isolated routes; certification imports stay blocked.
Four backend audits remain; stable 3.15 final and catalog acceptance stay open.


SLOW ACV MAMMALIAN uses canonical constant recognition; dependency and projection
queries remain shared. Native weights, pools, address/merge arithmetic, coprime
plans and resume guards remain unchanged. All eight cell/I/O/resume dialects
retain 15,456 artifacts through three inputs over seven layouts. All 30,208
native rows execute correctly: every default row and at least one row per other
artifact. Forty full trace scopes retain 832 native/VM row pairs and 1,679,780
semantic samples; their source hashes match the artifact corpus. Ninety-six
larger layouts retain 464 native/VM rows, including sixteen-input gaps.

Forty-eight constant timing contexts pass eight alternating trials per side
(minimum ratio 0.9848). Eight pins, two declared size anchors, the 119-character
constant witness and eighteen resource/scaling nodes pass unchanged. Twenty-eight
query faults change sixty executed answers; three validation controls fire.
Removing a projection candidate grows a correct witness from 170,335 to 178,487
characters across ten runs. `just test` passes 8,466 cases with six skips.

Installed Python 3.12.11, 3.13.15, 3.14.7 and cached 3.15.0rc1 each round-trip
15,456 artifacts across all eight dialects and execute 832 native/VM rows from
192 programs, plus forty-eight guarded workers and sixteen constant-query faults.
EOF and command-limit failures retain progress and agree across native/isolated
routes; certification imports stay blocked. Three backend audits remain; stable
3.15 final and catalog-wide acceptance stay open.


Smallfuck uses canonical constant recognition and row-indexed ANF coefficients
for its two-input Davio leaves. Canonical ANF has a closed four-row path;
band cells, paired-root codes, deferred definitions and pointer costs remain
native. All 2,093 template requests retain baseline bytes across seven layouts,
including constants through sixteen inputs; 15,911 native rows execute correctly.
The complete small-table trace scope retains 14,840 native/VM rows and 1,310,589
semantic samples, coupled to filled-program hashes. Ten direct plain, deferred,
banked and paired constructions retain 1,280 rows and their construction limits.

The original aggregate trace hits its sixty-second cap. The same seven-layout
scope passes as sixty-three bounded leaves; immutable tuple caching is checked
against uncached digests and live mutation controls. All 65,817 ANF comparisons
match, with independent subset-XOR oracles through three inputs. All forty-two
prior test assertions, cases and oracles survive import consolidation.
Five query faults change nineteen answers; disabling sharing grows a correct
witness from 1,170 to 1,473 characters across 512 runs. Three validation/template
controls fire. Sixteen timing contexts pass (minimum ratio 0.9724); eight pins,
three size anchors and thirteen resource/scaling nodes pass unchanged.
`just test` passes 16,259 cases with twelve skips.

Installed Python 3.12.11, 3.13.15, 3.14.7 and cached 3.15.0rc1 each round-trip
1,932 templates and execute 728 native/VM rows from 168 templates, plus six
guarded workers and all fault/cost controls. Template rejection, post-halt output
without duplication, malformed source, command limits and a post-halt output cap
pass; certification imports stay blocked. Two backend audits remain; stable
3.15 final and catalog-wide acceptance stay open.


Streetcode uses canonical constant recognition alongside its existing span and
weighted projection analyses. Sibling drawing reuse, minority painting, room
folds and layout costs stay native: a constant tree still draws two leaves,
eight rows. All 2,072 artifact requests retain baseline bytes across seven
layouts; 15,764 native rows execute correctly. The complete small-table scope
passes as 119 bounded leaves: 14,840 native/VM rows, 13,014,396 semantic samples,
all coupled to baseline source hashes. Twenty direct layouts retain 105 row
pairs, including nonadjacent ignored inputs at sixteen inputs.

Integer-tuple memoization retains uncached digest checks, mutation controls and
all seventy-two pre-cache baseline traces. Three semantic faults change fourteen
answers; disabling sibling drawing reuse grows a correct witness from 440 to
1,408 character-grid cells across sixteen runs. Sixteen timing contexts pass
(minimum ratio 0.9685); nine pins, four anchors and sixteen resource/scaling
nodes pass unchanged. `just test` passes in 162 seconds.

Installed Python 3.12.11, 3.13.15, 3.14.7 and cached 3.15.0rc1 each round-trip
1,932 artifacts and execute 952 native/VM rows, 649,964 commands and 8,568
workspace samples, plus six guarded workers and all fault/cost controls. EOF
and command-limit failures agree across native/isolated routes; certification
imports stay blocked. One backend audit remains; stable 3.15 final and
catalog-wide acceptance stay open.


Suffolk uses canonical constant recognition, dependency/projection and subtree
IDs. Countdown transitions, NOR cells, pointer pricing and workspace admission
stay native. All 2,072 artifact requests retain baseline bytes across seven
layouts; 15,764 native rows execute correctly. All 119 bounded trace leaves
retain 14,840 native/VM rows and 8,980,092 semantic samples, coupled to baseline
source hashes; seventy-two saved baseline traces match exactly. Eight direct
candidates cover stored/streaming sweeps, shared circuits, nonadjacent ignored
inputs and pointer boundaries: thirty-two native/VM resource rows and twenty-four
repeated native records pass.

Four query faults change 268 answers; disabling DAG admission grows a correct
witness from 214 to 373 characters across 512 runs. Sixteen timing contexts pass
(minimum ratio 1.0006); eight pins, three anchors and sixteen resource/scaling
nodes pass unchanged. Import consolidation preserves all seventeen prior
assertions and cases while satisfying the line budget. `just test` passes in
135.5 seconds after the initial line-budget failure.

Installed Python 3.12.11, 3.13.15, 3.14.7 and cached 3.15.0rc1 each round-trip
1,932 artifacts and execute 952 native/VM rows, 402,852 commands and 8,568
workspace samples, plus six guarded workers and all fault/cost controls. EOF
and command-limit routes agree; certification imports stay blocked. Every
Boolean backend now has an analysis disposition. Final reconciliation, stable
3.15 acceptance and catalog-wide lifecycle/accounting/evidence acceptance remain
open.


Termination results observe a real path through retained branch evidence before
capturing IO. Fish's `"A"o;` previously proved a halt but reported empty output;
it now retains `A`, as do deterministic cycles and a closed Modulous random
loop. Each live transition must belong to the proved graph, ending at its halt
or first repeated state. Graph exploration and Boolean verdicts stay unchanged;
post-halt output finalization is not requested. Native/worker controls retain
output, reject malformed decisions and detect disabled observation. Catalog-wide
acceptance remains open.


The current 951-file wheel passes the 117-runtime witness matrix on Python
3.12.11, 3.13.15, 3.14.7 and final 3.15.0. Each version round-trips all 114
Boolean backends, matches 116 stepped completions and one periodic boundary,
and retains 13,778 complete accounting observations against the current source
baseline. Native, debugger and bounded/isolated routes agree: 112 witnesses
retain unfinished one-step observations and five complete. All 240 workers per
version guard certification and proof imports with live positive controls;
retired imports fail. An altered accounting width is rejected on final 3.15.
The dependency cache contains the final interpreter without system shims.

This replaces release-candidate-only installed witness evidence. It does not
close independent component semantics, broader corpus/failure coverage, claims
or the final retirement reconciliation. All language completion rows stay open.


The CSV's `semantic_accounting` column records reviewed witness scopes;
`review-pending` does not assert that a model is absent. Existing declarations
and source/installed accounting traces remain separate evidence.

/// now predicts source, nullable pattern, replacement and input cursor from its
independent iterator/list rewrite model. All 924 prior cases retain 8,813 semantic
observations at the unchanged 64-command cap, including growing rewrites and
post-halt steps. Four component erasures preserve execution but fail resource
checks; all six prior semantic faults remain. Literal charged peaks are 16,
80 and 536 bits. Import consolidation preserves all fifty-seven assertions and
cases in the two owned tests; the source/test line count stays unchanged.

The unchanged installed package passes this complete raw/VM/debugger corpus on
Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0, with 884 native halts, four
component faults and four guarded workers per version. The partial-step error
retains output and agrees across native/isolated routes. `just test` passes in
230.6 seconds. This is bounded semantic accounting evidence; final language and
catalog acceptance stay open.


1 + i uses one-i-v2 captures: inexact values retain typed 128-bit IEEE payloads,
and cycle keys retain the same lossless bits. Previously `ie` could not be
accounted, signed-zero states aliased despite opposite logarithm outputs, and
inexact cycles could not cross worker transport. Finite and nonfinite cycles
now round-trip without permissive wire fallbacks; NaN payloads survive.

The independent Gaussian-rational/frame corpus retains all 1,202 cases and
4,060 observations at 64 commands. Three field erasures preserve execution but
fail resources; all three prior semantic faults remain. Hand-derived inexact
witnesses reach 131 bits. A 5,193-program interpreter comparison retains 2,296
clean halts and zero execution differences after only the intended key encoding
is normalized; a mutant changes 2,454 programs. Native speed ratio is 1.0005.
Thirty duplicate native test runners are consolidated with EOF suppression
disabled: all 599 collected cases, 1,953 calls and 191 errors match exactly.

Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0 each pass the complete owned
raw/VM/debugger corpus, 219 native halts, 981 failed steps, three field faults
and six guarded workers. The refreshed 951-file wheel also matches all 117
catalog witnesses and 13,778 accounting samples on all four versions; only
the declared model label changes in the default corpus. `just test` passes in
233.6 seconds. All language completion rows remain open.


3x predicts instruction, rational operands, loop returns, bindings and input
cursor independently. All 1,221 prior cases and 10,348 observations remain at
the 64-command cap. Five component erasures preserve execution but fail resource
checks; all ten prior semantic faults remain. The shared witness now rejects an
extra machine observation with an assertion. Literal charged peaks are 4, 7,
27 and 5 bits; the growing-loop witness reaches 99 bits at 64 commands.

The unchanged 951-file package passes the complete raw/VM/debugger corpus on
Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0: 211 native halts, 927 failed
steps, five field faults and five guarded workers per version. Native/isolated
failures agree, including retained output and a failed loop scan ending at EOF.
`just test` passes in 229.6 seconds. Language completion remains open.


6-5 independently predicts tape position, tape contents, instruction and input
cursor. All 1,535 cases and 17,506 observations remain at 64 commands. Four
component erasures retain execution but fail resources; all nine prior semantic
faults remain. Literal charged peaks are 6, 3, 13 and 25 bits; a marker loop
reaches one bit at 64 commands, and invalid output retains its prior character
with a five-bit peak.

The unchanged 951-file installed package passes the full raw/VM/debugger corpus
on Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0, with 1,174 native halts,
257 failed steps, four field faults and five guarded workers per version.
Native/isolated input, operand and output failures agree. `just test` passes
in 230.2 seconds. Language and catalog completion remain open.


A Painter Ant uses a-painter-ant-v2: visited bounds join grid, position and
instruction. Previously `ew` restored an equal capture while changing the
render from `o` to `o.`. The model records the rectangle independently of the
visited-set backing; full-content cache invalidation preserves changed bounds.
Cycle keys remain unchanged. The workspace upper bound adds four signed
coordinate widths within the at-most-2L-command walk; its proof table is updated.

All 1,076 raw/generated cases retain 19,176 semantic observations, including
periodic rendering and repeated dumping. Five component erasures preserve
execution but fail resources; the reversed-colour fault remains. Literal peaks
are 6, 3, 50, 10 and zero bits. All 35 resource tables and 836 rows pass.
The full 5,195-program, 400-step comparison has zero differences and 3,514 mutant
differences. Zero self-halts are expected; 73 separate periodic completions
provide completed-output evidence. Native speed ratio is 0.9952; snapshot and
repeated accounting-capture pilots are 1.0025 and 1.1046.

The final 951-file wheel passes the full raw/VM/debugger corpus on Python
3.12.11, 3.13.15, 3.14.7 and final 3.15.0, with 74 guarded workers per version.
The refreshed 117-runtime/13,778-sample matrix and 240 guarded workers per
version pass; only Painter Ant accounting changes. An altered accounting width
is rejected. `just test` passes in 247.2 seconds. The monolithic trace run hit
60 seconds; the identical full scope passed bounded batches without raising
caps. Language and catalog completion remain open.


ABCDirection's independent complex-grid/deque model predicts all ten workspace
components, including bit buffers and the exact silent-cycle phase. Relative
anchor validity is modeled without production epoch numbers. All 135 prior
cases and 7,783 observations remain at 96 commands; every component is written
in the corpus. Ten component erasures preserve semantics but fail resources;
the stalled-machine control remains. Literal charged peaks are 23, 32, 33 and
13 bits. Eight test modules consolidate imports with identical normalized test
bodies and all 245 assertions retained, keeping the source/test line budget.

All 951 package files remain byte-identical. The installed raw/VM/debugger
corpus passes on Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0, with 85
native halts and 89 guarded workers per version. Three syntax failures agree;
a printing loop retains twelve NUL characters and an unfinished observation
after 96 commands across bounded/isolated routes. `just test` passes in 233.6
seconds. Language and catalog completion remain open.


AddSubJump's existing dense-memory model independently predicts sparse cells,
logical extent, instruction, flags and input cursor. Its 192 cases retain
1,008 observations at the 16-command cap; all seven components are written.
Seven erasures preserve execution but fail resources, and the phantom-cell
control remains. Two additional witnesses cover a 16-command loop and EOF
after emitting `A`, adding twenty independently checked boundaries.

The unchanged 951-file package passes raw/VM/debugger captures, retained
snapshots and exact charged peaks on Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0. Per version, 144 native completions, 48 input failures and 196 guarded
workers agree; malformed assembly, unfinished loop observations and partial
output survive transport. The extra witnesses charge zero and three bits.
This reviews existing evidence without changing production or test code.
Language and catalog completion remain open.


Algebraic Programming Language's independent terminal oracle now preserves
exact integer quotients and promotes exact floating quotients before later
arithmetic. Executed counterexamples were `(2**80+1)/1` and `10**30/1.0+1`;
the interpreter already returned the correct final increment. All 164 prior
cases/traces remain, with three additions. Six unchanged output assertions
move into the existing matrix; remaining test bodies are identical.

An independent expression-frame prototype matches 167 cases and 1,991 complete
semantic/resource captures, including typed values, structural instruction
locations, early returns and failed-step rollback. Four erasures preserve
execution but fail resources; the observed corpus peak is 260 bits. The
unchanged 951-file package passes this raw/VM/debugger scope on Python 3.12.11,
3.13.15, 3.14.7 and final 3.15.0, with 145 native completions, 22 failures and
167 guarded workers per version. `just test` passes in 232.8 seconds.

APL remains review-pending: the frame prototype needs function/custom-operator
coverage and permanent owned regression checks. No language completion closes.


APL's frame audit now includes function calls and custom operators: all 167
expression cases plus 57 new cases match 3,080 complete semantic/resource
captures. Coverage includes local/global lookup, assignments, retained aliases
after redefinition, multiline/early returns, custom patterns, recursive frames,
large integers and nonfinite/nonreal errors. Two loops retain unfinished
observations at 128 commands; one configured guard fails at forty work steps.

A permanent witness in the declared oracle entry point independently constructs
the two-frame activation state for function and postfix calls. Frames cost
2w+28 bits, globals w+8, the line two, and the input cursor its bit length:
integer/floating inputs charge 45/232 bits. Four component erasures fail.
Four activation programs add 36 checked raw/VM/debugger boundaries.
Twenty-four existing assertions move into existing matrices with identical
calls/results and explanations; remaining test bodies are unchanged. Four
obsolete semantic selectors are removed because their already-declared
matrices now contain those assertions. Between, DINAC and Freestajlo retain
clean baselines and live fault detection.

The refreshed 951-file wheel passes this scope on Python 3.12.11, 3.13.15,
3.14.7 and final 3.15.0: 188 native completions, 34 failures, two bounded loops
and 228 guarded workers per version. The 117-runtime/13,778-sample catalog
matrix and 240 guarded workers per version remain unchanged. An altered width
is rejected. Only three packaged evidence-selector records change;
runtime/generation code is unchanged. `just test` passes in 245.2 seconds.
APL's bounded accounting scope is reviewed; language/catalog completion stays
open.


Alight's independent linear-grid audit matches 568 programs and 3,552 complete
semantic/resource captures in four walking directions: arithmetic, input/EOF,
list aliases, suspended calls and both list-update dialects. All five components
are written; five erasures and a stalled transition fail. The observed corpus
peak is 209 bits. Turns, skips and arbitrary recursive graphs remain outside
this bounded model.

The declared 117-case arithmetic oracle now independently constructs every
walker/binding capture and recounts written state, including post-halt samples.
Thirty redundant imports are removed from sixteen test modules; remaining
normalized ASTs and all prior assertions are unchanged. Six file-size checks
pass; `just test` passes in 11.3 seconds at changed-test scope.

The unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 568 native completions and 145 guarded workers per version, with exact
raw/VM/debugger captures, held snapshots and post-halt stability. Alight's
bounded accounting scope is reviewed; language/catalog completion stays open.


Aprknia's existing declared stack oracle passes all 3,665 cases and fifteen
live faults. Eight added audit cases extend the review to 3,673 programs and
7,570 boundaries: completed 80-item storage, a bounded loop, partial-output
EOF and paired Unicode inputs. All three components are written; independent
recounts match exact captures. Literal charges are 87/3/14 bits for the first
three witnesses; the observed corpus maximum is 104 bits, not a global bound.

The unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 180 native completions, 1,347 execution failures, 2,125 constructor
failures and 21 bounded runs. All raw/VM/debugger traces match; 118 guarded
workers per version agree on completion/failure/unfinished observations.
Three installed resource erasures fail; the declared semantic entry point
retains a clean baseline and live output-fault detection. No runtime/test
source changes. This bounded accounting scope is reviewed; completion stays
open.


ArrowQueue-v2 adds halt/dump flags: an empty pop changes only the former,
and a post-halt dump changes only the latter. Each generated halting run
writes both, adding two bits. Resource measurement now samples declared
finalization while preserving source-command counts. This also exposes
Stisp's rendered bit: its bounds add one. Exact resource checks pass at
ArrowQueue n=1..6 and Stisp n=1..7; skipped finalization fails the new owned
regression. The earlier global queue-bound investigation remains open.

The independent complex-grid model matches 479 cases/3,089 raw boundaries,
including explicit halting/sustaining rings and seventeen live controls.
All six mutable components are written; input stays read-only. Literal
charges are 2/1/4/6 bits; the bounded corpus peak is 71. Public line splitting
normalizes one CR-bearing raw line; its 3,088-boundary model is checked
separately. Two runs retain unfinished observations at 64 steps.

The full 5,193-program corpus retains its execution traces: 4,097
clean halts, 1,096 cycles, no 400-step cutoffs; a turn mutant changes 3,166.
Native step speed ratio is 0.99976. The 951-file wheel passes Python 3.12.11,
3.13.15, 3.14.7 and final 3.15.0: 477 native completions, 116 owned guarded
workers and 240 catalog workers per version. All 117-runtime/13,778-sample
catalog observations stay identical; only ArrowQueue accounting changes.
An altered width is rejected. `just test` passes 16,260 tests in 230.6 seconds.
This bounded accounting scope is reviewed; language/catalog completion stays
open.


Ascenic's existing oracle passes 4,356 scripted cases and eight live controls.
Its seeded public audit covers 4,856 cases/30,271 boundaries, including 495
seed-one cases, completed 80-item stacks, output followed by EOF and numeric
whitespace exhaustion. All three components are written; independent captures
and charged peaks match. Five literal charges are 447/87/10/2/7 bits; the
observed maximum of 14,306 bits is not a global bound. The current oracle
regenerates the saved model and both corpora byte-identically.

Current source matches all 951 package files in the tested wheel. Python 3.12.11,
3.13.15, 3.14.7 and final 3.15.0 each pass 4,444 native completions, 401 runtime
failures, six constructor failures and five bounded runs. Raw/VM/debugger
captures preserve held snapshots, post-halt stability, input progress and
1,022 actual random draws. Debugger source-command counts and explicit halted
versus unfinished reports match. Ninety-five guarded workers per version preserve
results, partial-output failures and unfinished observations. Three installed
resource erasures and a same-width seeded-draw fault fail. No runtime or test
source changes. This bounded accounting scope is reviewed; language/catalog
completion remains open.


B-tapemark's declared complex-grid oracle passes all 613 cases and three live
controls. Eighteen added cases cover both marker dialects, four directions,
Unicode/space input, partial-output EOF, wiki examples and completed 80-cell
writes. Independent captures and charged peaks match at 631 cases/9,389
boundaries, capped at 24–192 commands. Both components are written; literal
charges are 17/40/30/40/3,671 bits. The 3,671-bit observed maximum is not a
global bound. A same-state output fault supplements the marker fault and two
resource erasures.

Current source matches all 951 package files in the tested wheel. Python
3.12.11, 3.13.15, 3.14.7 and final 3.15.0 each pass 309 native completions,
46 input failures, sixteen constructor failures and 260 bounded runs.
Raw/VM/debugger captures preserve held snapshots, post-halt stability,
input counters and source-command counts. Sixty-one guarded workers per
version preserve both dialects, explicit completion, partial-output failures
and unfinished observations. No runtime or test source changes. This bounded
accounting scope is reviewed; language/catalog completion remains open.


Back-v2 records stopped/dumped separately from its unchanged cycle key. A
minimal `*` charged no bits through either phase; it now charges one for
halt and one for the dump, stable on repeated finalization. Every generated
halting run adds exactly two bits. Bounds and generated proof tables retain
the original execution/area claims; resource witnesses pass through n=6.
The deep workspace measurer now samples declared post-halt finalization.
Owned regressions preserve all cases while reusing existing imports.

All 5,195 generated/example/random programs retain execution traces across
787,609 boundaries, including 3,359 clean halts. A mirror mutant changes
3,040 programs. The initial monolithic trace run reached its unchanged 60 s
cap; all priced 128-program cohorts pass. Native step speed is 0.99727 of
baseline. Interpreter code outside workspace declaration/capture is
AST-identical. The fresh 951-file wheel passes Python 3.12.11, 3.13.15,
3.14.7 and final 3.15.0: three owned phase witnesses, 96 boundaries and three
guarded workers per version, with exact 2/4/97-bit charges, held captures,
input preservation and post-halt completion. Back's broader accounting and
catalog acceptance remain open.


Back-v2's declared oracle retains 404 cases and fourteen live controls.
Seven added witnesses cover completed 81-cell tapes grown in either
direction, long beam walks and raw/public line normalization. Independent
captures and charged peaks match 411 cases/16,895 raw boundaries under
64–96-command caps. All eight mutable components are written; input remains
read-only. Literal charges are 2/4/97/9 bits, with a 97-bit observed maximum
rather than a global bound. Six raw-line cases change under public
`splitlines()` preparation; their 16,986-boundary model is checked separately.

Current source matches the tested 951-file wheel. Python 3.12.11, 3.13.15,
3.14.7 and final 3.15.0 each pass 166 raw completions, 165 public completions,
five constructor failures and 241 bounded public runs. Raw/VM/debugger
captures retain held snapshots, post-halt stability, untouched input and
source-command counts. Nine resource erasures and a same-state wrong-dump
fault fail; forty-six guarded workers per version preserve post-halt results
and unfinished/failure observations. No runtime or test source changes.
This bounded accounting scope is reviewed; language/catalog completion
remains open.


Balik's declared sparse-trit oracle retains 1,744 cases and eighteen live
controls. Eight added witnesses complete 81-cell tapes containing trits 0,
1 and 2, consume eighty inputs, exhaust long whitespace and preserve output
before EOF or invalid input. Independent captures and charged peaks match
1,752 cases/10,907 boundaries under 64–288-command caps. All six components
are written; eight literal charges are 95/96/176/183/11/1/3/2 bits. The
183-bit observed maximum is not a global bound. Halting follows captured
position rather than an omitted stored flag.

Current source matches the tested 951-file wheel. Python 3.12.11, 3.13.15,
3.14.7 and final 3.15.0 each pass 1,201 native completions, 503 execution
failures, forty constructor failures and eight bounded runs. Raw/VM/debugger
captures preserve held snapshots, post-halt stability, exact input counters
and source-command counts. Six resource erasures fail; a wrong-trit output
with unchanged captures and length fails independently. Sixty-seven guarded
workers per version preserve completion, partial-output failures and
unfinished observations. No runtime or test source changes. This bounded
accounting scope is reviewed; language/catalog completion remains open.


BASICER's declared label-map oracle retains 1,832 cases and thirteen live
controls. Eighteen added witnesses cover completed 81-menu and 80-print
runs, LF/CRLF, duplicate numeric labels, blank-line addressing, equivalent
menu targets, Unicode line separators and failures after partial output.
Independent captures and charged peaks match 1,850 cases/18,993 boundaries
under 64–96-command caps. Both components are written; literal charges span
0–14 bits. The observed 14-bit peak is not a global bound. Raw digit-cap
`ValueError` and public `InterpreterLimitError` are modeled separately at
the recorded host limit of 4,300 digits.

Current source matches the tested 951-file wheel. Python 3.12.11, 3.13.15,
3.14.7 and final 3.15.0 each pass 1,397 completions, 291 execution failures,
eighteen constructor failures and 144 bounded runs. Raw/VM/debugger captures
preserve held snapshots, post-halt stability, line-read/character-progress
counters and source-command counts. Constructor failures retain unavailable
VM observations versus native zero-IO observations. Two resource erasures
and a same-state/same-length wrong-text fault fail. All 214 guarded workers
per version compare independent IO counters, including unfinished runs.
Independent subagent review tightened these counter and constructor witnesses.
No runtime or test source changes. This bounded accounting scope is reviewed;
language/catalog completion remains open.


Basicfuck adds an independent parser and compiled-control-flow workspace
oracle: 315 cases/2,669 boundaries under 40–192-command caps, retaining all
108 closed-form programs. Witnesses cover branch/back-jump boundaries,
variable-operand temporary reservation, empty tapes and zero-count aliases,
lazy bounds, READ consumption before failure, range modes, Unicode numbers
and surrogate output. All three components are written; a literal 11-bit
charge passes. The observed 81-bit peak is not a global bound. Seven live
controls reject resource erasure, stalled execution, overread, wrong overflow
and extra output. Broader grammar, nesting/allocation limits and exact error
messages remain unproven.

Current runtime source matches the tested 951-file wheel. Python 3.12.11,
3.13.15, 3.14.7 and final 3.15.0 each pass 184 native completions, 71 execution
failures, 58 constructor failures and two bounded runs. Raw/VM/debugger
captures preserve held snapshots, post-halt stability, exact input counters
and command counts; 97 guarded workers per version preserve native/isolated
results and unfinished observations. Constructor failures retain unavailable
VM observations versus native zero-IO observations. Independent review found
no blocker within this bounded scope.

Import hoisting in 152 existing language test modules recovers 541 lines
for the oracle within the unchanged test/source budget. Independent AST
comparison preserves every non-import statement and binding origin; native
imports move only where the same module was already imported unconditionally.
No cases or assertions are removed. This bounded accounting scope is reviewed;
language/catalog completion remains open.


Befunge's independent byte-torus model now checks all nine workspace
components: 1,068 cases/26,702 boundaries under 32-command caps, retaining
all 1,048 original Cartesian cases and existing direction/range witnesses.
Nine erasures and both original semantic controls fail. Chunked ASCII
accumulation models 5,000-digit input without production parsing helpers.
Halt advances the captured cursor. Equal-content and changed `p` writes
charge 16 and 16,017 bits respectively, including different stack peaks;
new backing storage alone never charges the grid. Other literal anchors
are 2/4/11 bits. All nine components are written; the 16,163-bit observed
scripted maximum is not a global bound.

Current runtime source matches the tested 951-file wheel. Python 3.12.11,
3.13.15, 3.14.7 and final 3.15.0 each pass an independently seeded
1,078-case/27,817-boundary audit: 205 completions, 63 execution failures,
24 constructor failures and 786 bounded runs. The model draws 148 actual
seeded directions, including repeated draws across a full `?` torus.
Raw/VM/debugger checks retain every boundary snapshot, preserve failing-step
state and compare successful-read, past-end and consumed-character counters.
Constructor metadata distinguishes unavailable VM/debugger observations
from native zero-IO results. Ninety-six guarded workers per version preserve
native/isolated results, partial output and unfinished observations. The
seeded observed maximum is 16,017 bits, not a global bound.

Independent review tightened constructor and held-snapshot checks. The
expanded source check exceeded the fast limit alone (1.02 seconds), so its
existing hook and admission helper use the medium band; no cases, assertions
or limits change. This bounded accounting scope is reviewed; broader
language/catalog completion remains open.


Between's independent variable-machine model retains all 204 original
AST cases and five malformed-source fixtures. All seven pure operations,
strict group/operand types, eager jump-target evaluation, identity-True
conditions and post-read declaration failures now match 986 cases/3,555
boundaries under 16-command caps. Ten distinct faults fail in fourteen
executions, including four erasures, wrong read ordering/conditions and
same-state/same-length wrong text. Six literal charges are 0/1/10/74/12/20
bits. Repeated EOF preserves machine parts and input progress. All four
components are written; the observed 28,580-bit peak is not a global bound.

Current runtime source matches the tested 951-file wheel. Python 3.12.11,
3.13.15, 3.14.7 and final 3.15.0 each pass 993 cases/3,562 boundaries:
294 completions, 652 execution failures, 43 constructor failures and four
bounded runs. Four execution failures and two constructor fixtures hit the
recorded 4,300-digit host cap; raw ValueError and public InterpreterLimitError
are distinguished. Long leading zeros and arithmetic growth before failed
formatting are included. Raw/VM/debugger checks retain every snapshot and
compare independent LF-line read, past-end, position and progress counters,
including undeclared reads after consumption and partial output. Constructor
metadata preserves unavailable VM/debugger observations versus native zero-IO
results. All 79 guarded workers per version compare native/isolated failures,
completion and unfinished observations.

Import hoisting in 54 existing language test modules recovers 225 lines
within the unchanged test/source budget. Parent AST proof preserves every
non-import statement, binding origin and unaffected scoped import; native
interpreter/generator modules were already loaded unconditionally. Patched
bindings stay local. No cases or assertions are removed. Independent review
found no blocker in the bounded generated-AST scope; this is not a general
parser model. This accounting scope is reviewed; language/catalog completion
remains open.


BFStack and bit~ share one frozen-wheel acceptance batch. BFStack retains
all 3,580 original cases; ten additions bring its independent four-part
corpus to 3,590 cases/9,957 boundaries at cap 64. Completed `,+.`/FF and
`,-.`/NUL witnesses reach wrapping that the old 256-increment fixture's
cap misses. Unicode input remains an unmasked code point until arithmetic.
Six faults fail, including four erasures and unchanged-state/same-length
wrong text. Seven literal charges are 0/2/5/3/11/11/20 bits. Skipped unmatched
`[` moves IP to the end before raising: halted state does not declare
successful completion or count the failed command. EOF retries and later
steps after this syntax error preserve the predicted parts and counters.
The legacy stack worktree's Underload/False edits remain separate.

bit~ retains all 2,175 original cases and traces; ten additions bring its
four-part corpus to 2,185 cases/18,465 boundaries at caps 64–192. Witnesses
complete 81-position growth both ways and eighty reads, exercise Unicode
truncation, CR/LF, XOR restoration and partial-output EOF. All twelve existing
semantic/resource controls remain. Six literal charges are 0/9/11/10/11/103
bits. Both languages write every declared component; observed maxima of
37 and 103 bits are not global bounds.

The batch found an isolation defect: JSON merged adjacent Python surrogate
code points. BFStack native input D800/DFFF completed with two reads; the
worker instead read U103FF once and raised EOF. The same merge changed source
step counts. Worker-only canonical UTF-8/surrogatepass tags now preserve
text values, including snapshots, errors and streamed output; literal tag
objects are escaped. Duplicate fields, malformed tags and output caps stay
strict. Lone surrogates and scalar non-BMP characters are positive controls.
BFStack's IO docstring now states the executed Unicode behavior.

The final 951-file wheel differs in three packaged modules: the IO docstring
and two transport modules. Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0
reuse that frozen wheel for 5,782 independent cases each. BFStack checks
3,595 cases/11,721 boundaries: 497 completions, 3,081 failures (84 halted
syntax failures) and seventeen bounded runs. bit~ checks 2,187 cases/18,476
boundaries: 1,369 completions, 745 failures and 73 bounded runs. Raw/VM/debugger
captures retain every snapshot; independent IO counters, command counts,
public views and completion agree. All 159 guarded workers per version
preserve native/isolated results, partial output and unfinished observations.
Ten additional codec controls cover nested literal tags, malformed objects,
periodic snapshot text and error arguments/notes; capped paired output is
also executed.

Shared charge recounts replace duplicate pin scaffolding; all four affected
corpora and reference traces remain identical. Safe import hoisting recovers
39 lines in 27 tests. Inlining two factory-test helpers preserves 548 assertion
nodes and twenty error contexts across ten files, saving another 30 lines.
No cases, assertions or budget limits are removed. Independent review found
no blocker in the bounded scopes; language/catalog completion remains open.

Lol waht i cant edit talk pages, Pilas, Underload, Nope. and Taglate have
independent full-component accounting across 4,008 cases/16,094 boundaries.
Original corpora and 64-command caps remain; Taglate retains 16. Case/boundary
counts are 804/5,352, 1,564/3,893, 265/1,166, 210/1,050 and 1,165/4,633.
Raw, VM and debugger captures match every independent state, IO counter,
source-step count and retained cycle/workspace snapshot, including failed
steps and repeated halts. Underload's growth guard never ends a bounded
trace before its command cap. Taglate includes split command fragments.

The frozen wheel matches all 951 packaged source files. Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0
pass this matrix and 140 selected guarded workers each, retaining native/
isolated failures, partial output and unfinished observations. Fourteen
frozen-written components change charged peaks; two constant-field
omissions, five same-state wrong-text faults and five declared-view faults
fail. Underload and Nope never write their input cursors. Observed maxima
are 16,633/48/735/1/1,071 bits, not global bounds; literal anchors include
Underload's 172-bit splice and Nope's one-bit transition. Full language and
catalog completion remain open.

The existing bounded-step helper replaces 21 duplicate loops in
18 owned test files. Expanded non-import ASTs preserve every step,
workspace sample, increment and cap assertion; reviewed immutable cap
arguments make their earlier evaluation safe. Corpus bytes and 2,368
independent model traces match before/after local factoring. Shared witnesses
retain all captures and verify them at trace completion, including failures,
while preserving their previous-snapshot assertion. No cases, assertions,
resource scopes or limits are removed.


Earlier final-dump exclusions describe the initial accounting scope.
ArrowQueue-v2, Stisp and Back-v2 instead count language-owned guards that
change future native-step output. Bitdeque's `PUSH` and Bitwise Cyclic Tag's
`0,1` have identical cycle keys and other logical fields before/after the
dump, but only the earlier phase emits output on its next native step.
Their v2 models follow that semantic distinction; VM/debugger/report-only
mirrors remain excluded. This changes the old metric by one bit, not the
program's output, cycle keys or generated bytes.


Bitdeque-v2 adds its rendered latch and one bit to both workspace bounds;
its generated resource witness now samples finalization. All 1,096 original
cases and ten controls remain; seven added cases complete 81-item growth,
drain/restoration, Unicode targets and taken/untaken host-limit targets.
The 1,103-case corpus has 13,611 boundaries under 64–192-command caps.
Eleven controls include all five erasures. Literal charges are 1/3/5/89 bits;
the observed 335-bit peak is not a global bound. Shared tracing preserves
all 1,096 old observer results. All 1,103 native state/cycle/output/IO traces
match before/after. Forty-eight generated templates are byte-identical;
1,008 instantiated programs execute correctly, with declared normal-load
resource checks through n=6.

Bitwise Cyclic Tag-v2 adds its language-owned completion latch and one bit
to the exact workspace expression. All original cases/assertions/controls
remain; malformed long source and an 80-step completed tape extend the
corpus to 609 cases under 64–80-command caps. Fifteen controls include five
erasures; literal charges are 1/17/18/648/649 bits. All 609 native traces,
cycle keys and IO match before/after. Thirty-one generated tables/404 rows
retain bytes and correct outputs; exact workspace peaks at n=1/2/3/5 are
45/70/119/409 bits. Failed terminal output preserves the latch; retry sets it.
The observed 649-bit corpus maximum is not a global bound.

One frozen 951-file wheel passes installed Python 3.12.11, 3.13.15, 3.14.7
and final 3.15.0. Each version checks 1,712 cases/33,321 boundaries with
held raw/VM/debugger captures, declared views, untouched input and phase-aware
completion/command counts. Bitdeque: 950 completions, 72 execution failures,
nine constructor failures and 72 bounded runs; raw digit-limit ValueError
is distinguished from public InterpreterLimitError. BCT: 359 completions,
four constructor failures and 246 bounded runs. Constructor observations
remain unavailable in VM/debugger versus native zero-IO results. All 73
guarded workers per version retain completion, partial-output failure and
unfinished observations. Ten installed component erasures fail on populated
witnesses; the initial None-answer erasure probe was corrected before this
matrix. Empty finalization charges one bit while cycle keys stay unchanged.
Both models write four logical components and keep input read-only. Generator
code, source size and execution claims stay unchanged; these bounded accounting
scopes are reviewed, while broader language/catalog completion stays open.


Blindfolded Arithmetic retains all 5,690 cases, thirteen controls and its
16-command squaring cap; three populated erasures supplement the original
three. Its independent decimal fold handles long input. Permanent probes
retain constructor counters, unread delimiters and native halt-before-write
failure timing without retry. Literal charges are 1/9 bits; declared exact
workspace witnesses at n=3/5 pass. Six installed additions cover long valid
input, a surrogate token and positive-output/negative-diagnostic host limits
under CPython's explicit 4,300-digit configuration.

Monotonic Boolfuck retains 2,563 cases/nine controls at 64 commands. Shared
observation preserves its original flattened traces and adds full capture
history; literal charges are 0/7/8/15 bits. Unary retains 5,283 cases/fourteen
controls, 64/600-command caps and 81 compressed sources. Its octal encoder
matches the old recurrence; the independent 12-bit charge remains exact.
Independent bracket matching replaces duplicate test parsers, preserving
54 error/positive controls. No production parser is reused.

Smallfuck-v2 counts its native dump latch, deliberately adding one bit to
the workspace bound. The `>>*` cycle key stays identical across finalization,
but only the earlier phase prints on the next native step. All 582 original
corpus traces/cycle keys/IO remain identical: 543 completed charges rise by
one; 39 bounded charges stay unchanged. All old assertions/controls remain;
four populated erasures and 1/2/3/5/8-bit pins pass. Two factored generated
resource checks retain all 28 original parameters and assertions.

A frozen 951-file wheel passes the accounting matrix on Python 3.12.11,
3.13.15, 3.14.7 and final 3.15.0: 14,124 cases/132,428 boundaries and 146 guarded
native/isolated workers
per version. Held raw/VM/debugger captures, independent width/charge recounts,
views, input counters and source-step/completion timing agree. Fourteen
populated installed erasures fail. A later CLI usage-only rebuild preserves
the other 950 packaged files and all non-usage AST. Installed gzip/help checks
on all four versions verify the final 951 files; the accounting runtime is
unchanged. Blindfolded has 3,517 completions, one
execution failure, 105 constructor failures and 2,073 bounded runs; its cursor
is read-only after construction. Monotonic/Smallfuck/Unary completions are
1,403/543/1,478; constructors 921/0/3,781; bounded runs 239/39/24. Their observed
peaks are 67/45/30 bits; Blindfolded's is 267,882, not global bounds.

Existing workspace helper reuse in 22 owned oracles saves forty test lines.
Expanded non-import ASTs, namespace-binding checks and all old/new cohort
digests agree: 28,018 observations/199,702 boundaries and 191 rejected controls
per side. This funds Blindfolded's forty permanent lines; final combined tests are
115,687 lines against 115,688 source lines. No cases, assertions, caps or
budget limits are removed. Generator code and size pins stay unchanged;
Smallfuck is the only accounting implementation changed. These bounded
accounting scopes are reviewed; language/catalog completion remains open.

Home Row, Hot and HQ9+ retain their 725/446/395 cases, 14/7/9 controls and
64–300/16/64-command caps. Their independent models check all declared state,
IO counters, views, source-step timing and retained raw/VM/debugger captures.
HQ9+ reuses the existing observer, preserving every old trace while adding
complete snapshot-history checks and saving four test lines.

A frozen 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 1,566 cases/13,295 boundaries and 44 guarded native/isolated pairs
per version. Home Row has 482 completions, 239 constructor failures and four
bounded runs; Hot has 377 completions, 25 execution failures, 25 constructor
failures and nineteen bounded runs; HQ9+ has 393 completions and two bounded
runs. Eleven frozen-written components and one omitted constant cursor fail.
HQ9+'s cursor is read-only. Observed peaks are 42/352/14 bits, not global
bounds. Runtime, generators and size pins stay unchanged; these bounded
accounting scopes are reviewed, while language/catalog completion stays open.

EGL, Dimensional and Fackward retain all 2,606/355/395 cases, 18/12/7 controls
and 64/64/24-command caps. Dimensional's independent ASCII decimal fold removes
its model-only host digit limit; six added cases check long signed input,
unread delimiters and rejected tokens. All old observer traces remain exact.
EGL adds a populated movement/input witness; Fackward adds a cat witness and
three constructor failures. Dimensional's scope remains axes 2–5; Fackward's
transition model uses canonical integer/operator/block programs.

The unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 3,367 cases/16,275 boundaries and 87 guarded native/isolated pairs per
version. Independent models check all workspace components, state/cycle keys,
declared views, IO counters, step/completion timing and retained captures.
Nineteen frozen-written component controls fail, including a consumed-input
failure boundary. EGL has 1,074 completions, 731 execution failures, 791
constructor failures and eleven bounded runs; Dimensional has 300/52/8/1;
Fackward has 388/7/3/1. Fackward's exhausted reading swap halts normally with
an EOF attempt; explicit halt need not read. Observed peaks are 110/41/157
bits, not global bounds. Runtime, generators and size pins stay unchanged;
these bounded accounting scopes are reviewed. Broader completion stays open.

Chicken-v2 counts its existing halt latch. After nonempty `chicken` halts,
resetting only `done` preserves the old capture/cycle key but makes the next
step print `0`. The conservative workspace bound rises by one bit; constant
charges become 8n+5/8n+9. All 102 original families retain identical native
traces across 586 boundaries. Forty templates retain bytes; 496 generated
programs retain outputs, traces and IO, with exactly one added charged bit.
All eight size-baseline tables/76 rows pass. All 256 three-input tables execute
2,048 rows correctly and retain their 305,139-character total; four-input
parity remains 1,678 characters. Declared resource witnesses pass at n=1/2/3/5.

The frozen 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 496 generated programs/10,404 raw boundaries, twelve independent
raw/VM/debugger literal boundaries and fourteen guarded native/isolated pairs
per version. Halt-before-output failure, bounded execution and constructor
observations remain distinct. Two populated latch faults fail; the nonempty
literal charges 62 bits. The generated corpus peaks at 344 bits, not a global
bound. General independent Chicken accounting and broader completion stay open.

Shared observer reuse in 25 oracles saves 85 test lines. Expanded module ASTs,
import bindings, contexts and returns agree; every original cohort executes
before/after: 35,151 observed calls, 260,527 returned boundaries, 257,031
workspace samples and 293 live assertion controls per side. No cases,
assertions or caps are removed. This funds Chicken's 35 test lines and one
source line; tests remain 115,636 lines against 115,692 source lines.

Dig-v2 counts its halt latch, including the silent `@` transition whose old
parts/cycle key stay unchanged. Both workspace formulas rise by one bit.
Its independent numeric model accepts native unlimited signed Unicode decimal
input and formats large negative output; character failures follow the exact
host `chr` policy. Python 3.12 raises OverflowError for a huge code point;
3.13–3.15 raise ValueError. The previously uncalled oracle now runs through
an existing pytest node. All 474 original cases/eleven controls remain;
v2/numeric additions and a separate bounded ring give 491 installed cases.

RAM0-v2 counts its posthalt dump latch and raises both workspace bounds by one
bit. Its model converts only executed numeric tokens, preserving native host
limits and skipped huge literals. All 1,386 cases/six controls remain; empty
phase and lazy-token probes give 1,393 installed cases. A controlled writer
failure leaves the latch false and charge zero; retry commits one bit once.
Both models pass default-cap positive controls and uncapped model checks.

One frozen 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 1,884 cases/29,321 raw/VM/debugger boundaries and 46 guarded
native/isolated pairs per version. Every public result also matches; failed
steps, constructors, unfinished runs and pending/finalized dumps stay distinct.
Fourteen populated freezes and ten schema omissions fail. Dig has 458
completions, 28 execution failures, three constructor failures and two bounded
runs; RAM0 has 812/292/0/289. Corpus peaks are 16,633/335 bits, not global bounds.

All 1,656 templates and 12,720 instantiated programs retain bytes, outputs,
native traces and IO; finalized charges rise by exactly one bit. RAM0's
width-one NAND circuits use their loopless token-count bound. Both eight-table
size baselines pass all 152 rows; n=10 anchors retain 405/7,097 and 557/3,885
characters with executed boundary rows. Declared workspace witnesses pass.
Shared erasure reuse saves 82 test lines across 35 clients/36 loops. Typed
trace dumps and all 146 ordered erasures match before/after, retaining every
case, assertion and cap. Tests/source remain 115,668/115,702 lines. These bounded
accounting scopes are reviewed; broader language/catalog completion stays open.

Qoibl, Qrain and REFRACTRAN now compare independent workspace projections
at every modeled boundary. All 5,374 original cases retain state, cycle, IO
and resource traces; all 25 controls remain live. Qrain adds one populated
FIFO/output probe. Caps stay 32/64/64, including eight-evaluation finite loops.
Qoibl's previously uncalled oracle now runs through an existing pytest node.
Permanent omissions cover all twelve components; REFRACTRAN's input cursor
stays zero and its required presence is checked separately from charged writes.

One unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 5,375 cases/18,145 native boundaries and 21 guarded native/isolated
pairs per version. Every local public result also matches. Full captures,
state/cycle keys, views, IO counters, step/completion timing and held snapshots
agree with independent models and width recounts. Eleven populated freezes
lose their predicted charge; omitting REFRACTRAN's constant cursor changes no
charge but fails capture equality. Corpus peaks are 17/44/17 bits, not bounds.

Qoibl has 125 completions, eighteen execution failures and four constructor
failures; Qrain has 1,632/595/2,580 and nineteen bounded runs; REFRACTRAN has
389/0/12 and one bounded run. Canonical program artifacts preserve exact source
bytes including `.x`; the raw filename guard still rejects it. A valid
4,301-digit REFRACTRAN literal separately confirms host-limit refusal rather
than malformed syntax. All production bytes and generator pins are unchanged.
Tests/source remain 115,687/115,702 lines with no new collected node. These
bounded accounting scopes are reviewed; general catalog completion stays open.

Clockwise, Codesick and CreativeScript v2 pass bounded independent accounting
review. All 2,915 original cases and 37 semantic/schema controls remain; eight
extra IO/resource cases give 2,923. Caps stay 64/8/64. All original hooks also
run against the installed wheel with their exact frozen test helpers.

Clockwise separately checks 998 raw lists and 998 public-prepared inputs:
130 original shapes change through join/splitlines. Raw outcomes are 33 clean,
955 failed transitions, five constructors and five bounded; prepared outcomes
are 33/950/10/5. Codesick has 598/0/12/208; CreativeScript has 452/639/11/5.
Whole-input constructor cursors stay read-only; failed internal bit reads do
not increment IO EOF counters. String maps remain in Codesick's workspace
despite its empty debugger memory view. Invalid numeric tokens count as reads;
EOF and whitespace progress remain distinct. The 5,000-digit numeric probe passes.

One unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 23,021 native boundaries including raw/prepared, anchor and selected
probes, with 21 guarded native/isolated pairs per version. Every prepared
public result matches. State/cycle keys, captures, declared views, IO counters,
step/completion timing and held snapshots match independent predictions.
Eleven populated freezes and two read-only cursor omissions fail; six IO
faults detect wrong output or extra reads. Five executed written-bit anchors
are 4/70, 1/25 and 6; observed corpus peaks 225/6,184/16,625 are not bounds.

Six clients reuse the existing erasure helper, saving twelve test lines.
Expanded ASTs and full typed before/after dumps agree, including all 23
ordered erasures and nonstandard stack/memory observers. Every case, control,
cap and return remains. Tests/source are 115,675/115,702 lines; no node is added.
These accounting scopes are reviewed; all broader completion rows stay open.

DINAC now checks 403 independent straight-line cases and forty small-step
call cases, including nullable declarations inside suspended calls. The old
38 call traces stay identical; all eighteen semantic/schema controls pass.
The previously uncalled straight-line checker now runs in an existing pytest
node. Both source caps stay 48; nested overloads, recursion, WHILE, void returns,
failed overload/return and partial output remain covered.

One unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 443 modeled cases plus three literal constructor refusals, 3,032 native
boundaries and 52 guarded native/isolated pairs per version. All public results,
state/cycle keys, captures, debugger views, input counters, successful-step and
completion timing, attached failure observations and held snapshots match.
There are 372 completions, 71 failed transitions and three failed constructors;
the observed 1,874-bit corpus peak is not a global bound.

Both populated component freezes lose their exact predicted charge; both schema
omissions fail. A nested nullable declaration costs 49 bits: full frames change
119 to 169 bits, while omitting that retained type yields 120. Four cursorless
IO cases preserve progress independently of reported position; three populated
position substitutions fail. Injected writer failures preserve committed state,
partial output and successful-step counts, normalize exactly on wrapped routes,
and do not retry the lost write when execution resumes.

Nine clients reuse the erasure helper without hoisting fresh source or variant
arguments out of their exception contexts. Full lambda/helper expansion restores
the original module AST. Typed before/after dumps match, retaining every case,
assertion, cap, return and all 54 ordered component faults. Reuse saves 21 lines;
DINAC adds twelve. Tests/source are 115,666/115,702 lines, with no new node.
This bounded accounting scope is reviewed; broader completion stays open.

Grapheme's independent model now retains deferred X skips, clamps negative V
counts and commits state before Y rendering. N uses independent unlimited
decimal formatting. All 300 original cases/eight controls remain; seventeen
new cases give 317/fourteen, still capped at 64. The previously uncalled
checker now runs through an existing pytest node. Both integer dialects remain.

One unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 323 cases including six signed/dialect numeric cross-cases, 3,343 native
boundaries and fifteen guarded native/isolated pairs per version. All public
results, captures, cycle state, debugger views, IO counters, successful steps,
completion, attached failures and held snapshots match independent predictions.
Outcomes are 249 clean, 68 failed transitions, two bounded and four constructors;
the 40,059-bit corpus peak is a measurement. Five populated component freezes
lose their exact peak charge; five required-field omissions fail. Literal
written-bit witnesses are 4/70/73. Twelve cursorless cases, eight populated
position substitutions and eight repeated EOF attempts preserve IO semantics.

Builtin positive controls distinguish successful decimal formatting from the
configured host limit and restore it; no fixed host setting is required. Y
failures keep committed state and no completion, while large N succeeds. A
second-write refusal retains its output prefix and failure metadata on raw,
VM, debugger and public routes. Idle calls neither retry it nor turn a failed
final write into successful completion.

A shared checker factory replaces ten repeated observer wrappers, saving
fourteen test lines net. Existing required calls, defaults, return identity,
assertion contexts and fresh witnesses remain; stateless views and predictors
bind once. Private callable metadata changes. Typed native/observer/resource
before/after dumps are byte-identical; every case, control and cap remains.
Grapheme adds forty formatted test lines, leaving tests/source at
115,692/115,702 with no new node. The queued usage correction identifies saving
as top-level save_program. This accounting scope is reviewed; general catalog
completion stays open.

Crement, Cyclic tag and Circlefuck retain independent resolved-instruction,
FIFO and mutable-byte-ring models at caps 16/64/24. All original cases and
21 semantic/erasure controls remain. Circlefuck adds an empty-program
constructor prediction and one regression: 347 cases; its old 346 typed
traces stay identical. All three hooks already have collected callers.

The unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 6,013 cases/46,459 native boundaries, all local public results and
27 guarded native/isolated pairs per version, including caps zero and one.
Full state, component captures, cycle records, debugger views, IO counters,
step counts, completion, attached failures and held captures match independent
predictions. Outcomes: 3,372 completions, 1,875 failed transitions, 760 bounded
runs and six constructors. Corpus peaks are 34/1,067/56 written bits.

Eleven populated capture faults and two required read-only omissions retain
execution while rejecting lost component/subfield writes or missing fields. Literal written-bit anchors are
0/12/31, 0/17/18 and 1/3 respectively. Five cursorless runs, three populated
position substitutions and three repeated caught-EOF attempts preserve IO
progress. Eight raw/VM/debug/public writer probes distinguish Circlefuck's
pre-transition failure from Cyclic tag's failed post-halt print; successful
active/dump retries recover with the predicted prefix, state and step counts.
Cyclic tag's initially empty queue reports completion only after the post-halt
call, even when its state and printed flag never change.

The bounded Crement corpus uses resolved rows and canonical labeled source;
general label/term parsing remains open. Circlefuck's byte encoder and empty
constructor do not establish general escape parsing. Only three permanent
test lines are added, with every existing case/control/cap retained.
Tests/source are 115,695/115,702; no node is added. These accounting scopes
are reviewed; 66 accounting rows and all 117 completion rows remain open.

Eval's unchanged independent two-stack/suspended-reader model now checks all
four workspace components. All 2,751 old cases and the caller-discard fault
remain; three added cases and six controls give 2,754/seven at cap 24. Old
typed traces stay identical; the existing pytest hook remains the caller.

The unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 2,754 core cases/10,159 boundaries, 633 completions and 2,121 failed
transitions per version. Separate probes retain a bounded run; ten guarded
native/isolated pairs include cap-zero/cap-one boundaries. Full stacks, frames,
pointer, input progress, cycle records, declared views, IO counters, successful
steps, completion, attached errors and retained snapshots match independent
predictions and full-width recounts. The measured corpus peak is 80,037 bits.

Three populated freezes lose their predicted component charge; a required
read-only cursor omission fails. Output, caught-EOF and discarded-caller faults
are live. Executed literal written-bit anchors are 0/19/10/88. A second-write
refusal preserves the output prefix and the pre-transition stack/frame state
on raw/VM/debug/public routes. A successful active retry prints and commits;
frame return then completes with the predicted step count.

Fourteen wrappers share fixed-option workspace, source-context workspace or
plain full-trace checkers. Twenty-four complete hook replays, including ten
existing clients, retain 38,303 observed calls, 403,275 returned boundaries,
215,299 resource samples, 399,016 native boundaries, 191,738 meter samples,
299 live assertion controls and 84 ordered component controls per side. Typed
traces match byte-for-byte after binding observation defaults through the
unchanged signature; four plain wrappers make cap 64 explicit. Model, view,
context, return and call order remain; private callable metadata is excluded.
No case, assertion, control, cap or node is removed.

Helper reuse saves 32 formatted test lines; Eval adds 33. Tests/source are
115,696/115,702. This bounded accounting scope is reviewed; 65 accounting rows
and all 117 completion rows remain open.

CARP's independent parser and input reader now fold validated ASCII digits
without the host conversion cap. Three numeric regressions join its old
1,800 cases; every old typed trace and ten controls remain. IEBEL retains
2,719 cases/fifteen controls. Both keep cap 64 and their existing callers.

The unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 4,522 cases/41,514 boundaries, 3,057 completions, 1,128 failed
transitions, 242 bounded runs and 95 constructor refusals per version. Full
registers, source positions, cycle records, captures, declared debugger views,
IO counters, successful steps, completion, attached failures and held histories
match independent predictions. Six populated capture freezes lose their exact
component charges. Measured corpus peaks are 30/294 written bits; literal
anchors are 2/21/30 and 0/1/265. Eighteen guarded native/isolated pairs include
cap-zero/cap-one boundaries.

Six cursorless cases and four position substitutions preserve progress. Eight
writer probes retain prefixes, committed halted state and unsuccessful-step
metadata; idle calls neither retry the write nor clear the debugger fault.
Signed host-format controls distinguish capped CARP diagnostics from ordinary
range errors and restore the initial policy. IEBEL's rewritten constructor
message retains its chained host-limit classification; ordinary malformed
literals remain ProgramError. These are executed checks, not inferred phases.

Fourteen independent readers share only whitespace/token span scanning; grammar,
conversion, EOF and commit policy stay local. Expanding the helper restores
each entire original module AST. Complete typed replays match: 17,853 observed
calls, 160,234 returned boundaries, 127,149 resource samples, 158,976 recorded
native boundaries, 112,702 meter samples, 114 live assertion controls and 39
ordered component controls per side. All cached fields remain; fixed hash
seeds resolve process-randomized native caches. Original Line PNG fixture bytes
are retained. Each reader also rejects a wrong-span positive control.

Reuse saves 31 test lines; CARP adds sixteen. Tests/source are 115,681/115,702;
no case, assertion, control, cap or node is removed. These bounded accounting
scopes are reviewed; 63 accounting rows and all 117 completion rows remain open.

Declared VM views now render host-capped integers inside exact builtin data
graphs without changing the process digit limit. A valid Container initial
value with 5,001 digits previously made VM/debugger views raise ValueError;
it now displays the correct decimal prefix. Its 16,610-bit typed value,
workspace, cycle state, memory and IO remain unchanged.

Ordinary repr stays the fast path. On a confirmed digit-cap failure, a full
plain-data check precedes recursive formatting; unsupported custom repr is
never retried or reconstructed. Identity checks prevent overloaded metaclass
equality from admitting custom types. Cycles and aliases retain their markers;
scalar truncation at 60 characters and the first-eight sequence rule stay.
Custom dataclasses, namedtuples and subclasses retain their existing repr and
errors. No record adapter or global policy mutation is introduced.

Only one of 951 packaged files changes. The fresh wheel passes Python 3.12.11,
3.13.15, 3.14.7 and final 3.15.0: 117 runtime witnesses, 114 artifact round
trips, 116 stepped completions, one periodic boundary and 13,778 accounting
samples per version. All 9,033 ordinary view renderings match the previous
formatter on the same values. The 240 guarded workers per version retain
112 unfinished one-step results, five completions and partial-output failures.
Large-value, cyclic/aliased builtin and custom-error controls pass separately.
Existing test nodes carry the regressions; no generator or accounting schema
changes. Broader language/accounting completion remains open.

Container retains its independent simultaneous-network model, all 55 original
cases, five controls and the existing pytest caller at cap eight. Seven
supplements cover populated input/EOF, a 5,001-digit initial value, three
constructor refusals and an undeclared condition's first-tick failure.

The unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 62 cases/495 boundaries, ten completions, one failed transition,
48 bounded runs and three constructor refusals per version. Eleven guarded
native/isolated pairs include cap-zero/cap-one boundaries. Full state, tick,
cycle, four workspace components, fixed rules, declared views, IO counters,
step counts, completion, attached errors and held snapshots match independent
predictions. Full-width recounts match WrittenState; peak charge is 16,668 bits.
The large-value view succeeds without changing the host digit policy.

Four populated freezes lose their exact component charges; four populated
omissions fail. A literal 135-bit anchor and cursorless position substitution
are live. Writer refusal on raw/VM/debug/public routes precedes state, tick
and input commit; raw/VM/debug retries attempt the write again and retain the
old capture. General source parsing and unbounded growth remain open.
No tracked code or test changes are needed; 62 accounting rows and all 117
completion rows remain open.
