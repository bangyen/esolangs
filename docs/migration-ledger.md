# Migration completion ledger

Declaration audit: 2026-11-05. [Language rows](migration-status.csv) cover all
117 languages and 114 Boolean backends. Declarations and inherited adapters
are recorded separately; neither proves acceptance. Every completion row stays
open until its trace, resource, installed-package and retirement evidence is
checked against the current implementation. Refresh this snapshot after each
migration batch.

The roadmap's eight workstreams defined acceptance; all closed. The table
below inventories known retirement families; the final tree-wide audit must
also catch aliases introduced during migration. Target removal release: 2.0.
Owners are workstreams, not individual contributors.

The 2026-11-11 v2 cutover additionally retires Between's definition facade,
binding and VM type forwarding imports, and the old Unlambda pickle layout.
Portable template spans and gzip limits are now required; the older incomplete
version-1 records are retired. Unknown PNG metadata versions are rejected.
Historical replay derives template slots for reference execution. The older
statements below describe their dated snapshots.

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
| Shared plain-text fixture filler `tests.generators.fills` | Artifact API | Retired; native fixtures declare their bindings; module lookup check in `tests/generators/test_generator_support.py` | Explicit `TemplateBindings` from declared native setters |
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
| Permissive worker envelopes and nested proof fields | Results | Retired; missing/extra fields, unknown error kinds, duplicate terminals, inconsistent output-limit markers and contradictory output fail with retained prefixes | Exact canonical stream, result and evidence schemas |
| Normalized worker hex spellings and duplicate snapshot-set members | Results | Retired; request, result and parent-decoder refusals retain signed huge integers, byte snapshots and partial output | Encoder spellings and distinct immutable members |
| Malformed PNG metadata version downgrade | Persistence | Retired; missing, mistyped and nonpositive versions fail with live controls in `tests/runtime/raster/test_png.py` | Plain PNG and valid v1 provenance; unknown versions fail |
| Absent gzip member accepted as an empty program | Persistence | Retired; constructor, portable and worker refusals retain actual empty members and explicit unavailable execution | Valid UTF-8 gzip members, including empty and concatenated streams |
| Incomplete version-1 template/gzip records | Persistence | Retired; missing spans or limits are rejected | Explicit spans and limits |

For each family, locate consumers before changing it; close the row only after
those consumers migrate, the implementation disappears and a regression check
rejects its reintroduction. A version number or a new facade is not retirement.
Current version-1 serialization is not obsolete solely because its version is 1.

The 2.0 defaults are artifacts and execution results. Public API, CLI, scripts,
documentation and tests retain records through binding and execution. Native
measurements read explicit source; portable JSON retains template bindings.
Plain source cannot be instantiated. Native source exports retain their file
conventions; portable template and gzip records require their current fields.

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

Fargo's owned frame/value renderer now preserves ordinary cycle and ancestor
keys while formatting large integers without changing the host digit policy.
A valid 20,000-bit literal previously halted in three steps but made its
second-step cycle and VM/debugger views raise ValueError. Frame text retains
field order, tuple spelling, custom callable repr and recursive markers;
workspace encoding and language output/error semantics stay separate.

The complete tracediff corpus retains 5,195 programs, 2,290 clean halts and
zero ordinary differences; the stalled control differs on 2,553 programs.
Measured stepping speed is 210,653 to 211,781 steps/s. One of 951 wheel files
changes. Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0 each pass the prepared
independent model's 266 cases/10,398 boundaries and 33 guarded route pairs,
plus populated frame, callable, array, IO and failure-phase controls.

The existing frame-entry test carries a capped large-binding regression;
no node is added. The complete independent frame model remains an archived
proposal until funded within the test/source budget. Fargo's accounting row
and all broader completion rows remain open.

Collatz Multiverse's independent reader now folds signed ASCII digits without
the host conversion cap. All 327 old cases/five controls retain identical
typed traces; eight numeric/populated cases make 335 permanent cases at cap16.
Three exact constructor refusals supplement installed acceptance. CVNC keeps
its independent AST evaluator and validates tokens before converting reached
literals to bindings. Formatting precedes deque removal; failed steps retain
the advanced pointer. Its 535 old structured cases/seven constructor refusals,
eight controls and ten extras give 552 cases at cap48. The previously orphaned
hook now runs from an existing test. General source parsing remains open.

The unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 890 cases/5,593 boundaries, 430 completions, 413 failed transitions,
37 bounded runs and ten constructor refusals per version. Independent models
match full state, cycle, declared views, IO, successful steps, completion,
attached failures and held snapshots. Peak written charges are 33,333/32,777
bits. Sixteen/seventeen guarded native/isolated pairs include cap-zero/cap-one
boundaries. A separate CVNC shunting-yard predictor agrees on all 545 modeled
cases; its seven constructor records remain exact-source refusal witnesses.

Nine populated freezes lose their exact component charges; nine omissions
fail. Literal anchors are 147/35 bits, with cursorless/position controls.
Eight writer routes retain committed state, output prefix and failed-step
metadata; following steps do not retry the lost write. CVNC's two host-format
phases retain their distinct deque/output commit timing. Collatz accepts long
signed ASCII tokens; CVNC deliberately keeps builtin integer grammar and its
zero-on-invalid/capped-input policy. Host digit settings remain unchanged.

Forty-one clients share constant-source fixture construction. Expanding the
helper restores every original module after unused binding/import cleanup.
All 399 enclosing tests pass. Forty-nine complete hook/inline invocations
retain 3,474 fixtures, 8,232 generation calls, 11,631 constructors, 338,368
native boundaries, 240,102 meter samples, 66,975 IO calls and 1,080 Taglate bulk
transitions per side; typed dumps and emitted fixture bytes match exactly.
An opposite-output source control fails the unchanged native assertions.

Reuse saves 144 formatted test lines; the numeric corrections/cases/caller
add 62. Tests/source are 115,722/115,808, with no node, assertion, case, control
or cap removed. These bounded accounting scopes are reviewed; 60 accounting
rows and all 117 completion rows remain open.

Decleq's independent numeric loader now folds signed Unicode decimal digits
and underscores without host conversion caps. All 1,141 old cases/four controls
retain identical traces; eight extras give 1,149 at cap32. Its existing dense
allocation cutoff remains explicit: the sole 4096-target witness checks only
construction/initial state and a cap-zero public refusal. Writes into valid
large stores remain unverified; no allocation closure follows from that case.

SwitchCase now captures the full case/arm/command/environment activation and
input progress. All 169 old cases and the lost-selection control remain;
fourteen extras and two erasures give 183 cases/three controls at
cap24. Input keeps signed ASCII grammar with unlimited folding. Decimal
output and invalid-character diagnostic formatting fail before activation
commit; physical writer refusal follows it. Both existing callers remain.

The unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 1,332 cases/10,015 boundaries, 837 completions, 358 failed transitions,
125 bounded runs and twelve constructor refusals per version. Full state,
cycle, declared views, IO counters, steps, failures and held histories match
independent predictions and complete-width recounts. Fifteen/twenty guarded
pairs include cap-zero/cap-one boundaries and two separate surrogate values.
Five populated freezes lose exact charges; five omissions and all four
activation-subfield faults fail. Literal anchors are 23/15 bits. Default-policy
peaks are 16,612/16,635 bits; disabled-limit SwitchCase reaches 16,636.

Eight writer routes preserve the predicted committed/uncommitted state and
failure envelope. Decleq retries refused output; SwitchCase does not. Separate
640-digit/disabled-limit source and worker runs retain exact numeric, formatting
and constructor phases, restoring the host policy. All 1,310 old semantic
traces remain byte-identical; old controls remain live. The complete additions
cost 85 test lines; tests/source are 115,807/115,808, with no node or cap removed.
These bounded accounting scopes are reviewed; 58 accounting rows and all 117
completion rows remain open.

Codesick's n4/n5 workspace checks also pass a Python 3.14.7 calibration: all
22 generated witnesses/528 measured rows return their literal truth-table bits
while retaining every resource inequality. Real positive/opposite programs
run another 32 rows; the opposite vector is specifically rejected. Exact-node
collection, completion, JUnit and hash-pinned duration/companion receipts agree.
This supplies two workspace claim receipts; other execution/scaling claims,
arities and the four-version claim matrix remain open.

BrainIf/Deadfish bounded accounting passes the unchanged 951-file wheel on
Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0. BrainIf checks 995 cases at
cap32; Deadfish checks 1,823 at cap64. Per version: 22,040 boundaries, 2,665
completions, 49 failed transitions and 104 bounded runs. State, cycle, declared
views, IO counters, failure envelopes and held captures match independent
predictions; complete-width recounts match the meter. Peaks are 23/25,974 bits.
Nine/six guarded worker pairs include cap-zero/cap-one boundaries.

Seven populated freezes and nine omissions fail with exact lost charges;
Deadfish's source and unused input cursor remain readonly and uncharged.
Literal anchors are 13/5 bits. BrainIf's cursorless input retains real progress.
Twelve writer routes preserve commit order: BrainIf retries before commit;
Deadfish commits before refusal, with distinct idle/active debugger recovery.
Three Deadfish routes retry capped decimal formatting before commit. Separate
640-digit/disabled-limit source and worker runs preserve the policy; disabling
it completes the large output witness and adds three checked idle boundaries.
Named decimal views are predicted independently through base-10^9 chunks.

Deadfish's existing model now captures decimal-format refusal and includes
both large arithmetic/output witnesses. Four lines saved by reusing a pure
validated decimal fold fund its four-line addition. CARP, Collatz, SwitchCase
and Decleq retain local validation; IEBEL's capped conversion stays unchanged.
All 9,003 original cases/53 controls retain byte-identical replay data. No node,
assertion or cap is removed; tests/source remain 115,807/115,808. BrainIf's huge
numeric-source parser and unbounded Deadfish growth remain outside this cohort.
These bounded accounting scopes are reviewed; 56 accounting rows and all 117
completion rows remain open.

Thue's existing independent hook is now collected and checks text/input progress
at cap12. All 511 original records/three controls retain byte-identical traces;
two component erasures add controls without adding nodes. Model/choice/matching
ASTs and complete ordered original constructions are unchanged.

A fresh 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0:
518 cases/2,574 boundaries, 457 completions, thirty failed transitions, 27 bounded
runs and four constructor refusals per version. Full state, cycle, views, IO,
steps, failures, held captures and complete-width recounts agree; peak136,000
bits. Fifteen guarded pairs include both live and halted cap-zero/cap-one cases.
Every indexed match and ordered branching successor is checked, retaining
duplicates; input-rule branches decline without drawing.

Two populated freezes/two live omissions lose exact charges. Literal workspace
is ten bits; cursorless input retains real progress. A corrupted derived match
count is rejected despite an unchanged capture. Four writer routes commit the
rewrite before refusal; idle stepping neither retries output nor clears the
debugger's fault/completion. An actual equal-capture rewrite followed by a
different external draw confirms the relation scope. Snapshot docs now limit
same-future/loop guarantees to deterministic live execution. Provider futures
and general whitespace-left-side grammar remain outside this cohort.

Seven fixture modules reuse the existing step/sample helper, saving 34 formatted
lines with equivalent integer caps. Fourteen full hook invocations retain exact
sources/native/IO/meter traces: 3,170 public generation calls, 48 directly emitted
INTERCAL texts, 2,270 native instances and 60,807 steps. Private caller-frame
locals on escaping exceptions are excluded. Thue's formatted bridge/hook costs
fourteen lines; tests/source are 115,787/115,814, with no node or cap removed.
This bounded accounting scope is reviewed; 55 accounting rows and all 117
completion rows remain open.

Sonata/SStack now compare complete independent text/stopped/rendered and
pc/seven-stack/input-progress states. Their 1,332/2,063 originals and nine/five
controls remain; three component erasures each add controls without new nodes.
Sonata retains default cap16 and the separate original growth cap8; SStack
retains cap64. All model/parser/transition helpers and complete ordered
construction records remain unchanged.

HQ9+ headers' existing orphan hook is collected. Independent Decimal conversion
fixes capped model assignment spelling, ASCII-prefix readn and numeric output;
native arithmetic/input/output already lift those caps. Ten permanent numeric
cases give 101 records/six controls at cap64; installed extras give 106. All 91
old records retain exact traces. Ordinary host-capped flow/jump literals stay
distinct from unlimited data; signs/Unicode/underscores stop readn immediately.

The unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 3,501 cases/32,823 boundaries per version, 2,317 completions, 201 failed
transitions, 957 bounded runs and 26 constructor refusals. Full native/VM/debug/
public state, cycles, named views, IO counters, steps, failures and retained
histories agree with independent predictions and complete-width recounts.
Sonata/SStack/HQ9 peaks are 4,096/16,611/33,226 bits; 37 guarded pairs include
live cap-zero/cap-one boundaries. Nine populated freezes/nine live omissions
lose exact charges; literal anchors are 18/9/10 bits, with cursorless probes.

Twenty-eight writer routes retain halt-before-render retry for Sonata,
preassignment retry for SStack and postcommit no-retry/idle/active recovery for
HQ9. Separate 640/disabled digit-policy model and installed/worker profiles
retain exact errors and restore policy, including huge diagnostics/output.
All 3,486 old cases/twenty controls retain byte-identical replay data; SStack's
omitted/explicit default is normalized only in recorded call metadata.

Two existing constant-fixture loops reuse count_steps, saving ten formatted
lines with loop-invariant integer cap n+1. Full hooks retain 449 generation
calls, 496 native instances, 3,505 steps and 3,492 meter samples with identical
traces. The three complete proposals cost 35 lines; tests/source 115,812/115,814.
Initial copied-support and lint/default-metadata adapter failures are archived.
No generator, node, case or cap is removed. General HQ9 fork/conditional/song
parsing remains outside this structured cohort. These bounded accounting scopes
are reviewed; 52 accounting rows and all 117 completion rows remain open.

Forþ's independent hook is now collected and captures stack, stored scopes,
all frame code/pc/loop fields, input progress and logical reads at cap96.
The raw view also checks the terminal abort flag. All 278 cases/three controls
retain byte-identical traces; five component erasures add controls. Model and
parser-free dispatch/scan helpers remain unchanged; no node or cap is removed.

The unchanged 951-file wheel passes Python 3.12.11, 3.13.15, 3.14.7 and final
3.15.0: 278 cases/4,391 boundaries, 225 completions, 51 failed transitions and
two bounded runs per version. Full raw/VM/debug/public state, persistent scope
maps, frame-entry keys, cycles, views, IO, success-only steps, failure envelopes,
held histories and independent full-width recounts agree; peak 971 bits.
Seven guarded pairs include live cap-zero/cap-one and real bounded cases.

Five populated freezes/five native omissions lose exact charges. Literal 63-bit
workspace has component peaks 8/9/44/1/1; additional anchors are 30/29/10 bits.
Cursorless CRLF input retains offset 3/progress 1. Twelve EOF/conditional/abort
routes preserve preadvanced frames and consumed operands; EOF/conditional
failures finalize on the next active step without new IO and clear debug fault,
while top abort idles retain it. Eight writer routes keep advanced pc/unpopped
stack without retry, distinguishing terminal and active recovery.

Eleven IO fault constructors across ten full hooks now share bound-method
setup before native init. Both ordinary and mutant trajectories remain byte
identical: 11,752 constructor attempts, 54,020 steps, 77,386 observations, 36,876
meter samples and 17,392 IO events; all 63 old rejection controls remain live.
The exact callbacks/call order expand to the original ASTs after private alias
renaming. A real HQ9 constructor refusal leaves the replacement installed;
a tagged bound-method failure survives restoring the class method. Only
positional source/IO calls are admitted; private signatures/names/tracebacks
are excluded. All hooks were invoked explicitly; collection is not inferred.

That reuse saves seven lines; two constant-fixture loops save ten more through
unchanged count_steps with total invariant integer caps n+2/n+1. Both full hooks
retain 192 generation calls/492 native instances/3,738 steps and samples. These
seventeen savings fund the complete seventeen-line Forþ bridge/hook. Tests/source
remain 115,812/115,814. Initial setup and naming-adapter failures are archived.
This bounded accounting scope is reviewed; 51 accounting rows and all 117 broader
completion rows remain open.


Unsquare's independent hook is now collected at cap32, preserving all 6,615
cases and its loop fault. Six erasures check instruction, accumulator, stack,
jumps, input progress and own successful reads. Python 3.12.11–final 3.15.0
installed checks cover 25,907 boundaries: 1,919 completions, 4,684 failed
transitions and twelve bounded runs; peak 43 bits. Raw/VM/debug/public state,
source/partner cache, cycles, views, IO, success-only steps, held histories and
independent full-width recounts agree. Eight guarded pairs retain live cap-zero,
cap-one, bounded and surrogate-input probes.

Six populated freezes/native omissions lose exact charges against a separate
23-bit anchor (component peaks 3/7/7/2/2/2). Cursorless input, corrupted partner
cache, unmatched-loop idle and repeated EOF remain distinct. Eight writer routes
retry preadvance failures and recover. Separate load probes retain detached
stacks and unchanged control/input fields; signed 5,001-digit outputs retain
exact formatting failures or success under default, 640 and disabled policies.
Loaded states are explicit supplements, not empty-state or guarded-worker claims.

Six fault callbacks now reuse after_step; delimiter scans share only their
first-zero recurrence. Full ordinary/mutant hook replays are byte-identical:
30,122/46,747 steps and 41/26 rejection controls respectively. Whitespace's full
fixture retains 96 generation calls, 218 native instances and 6,650 steps with
a total invariant integer cap. This saves sixteen formatted test lines; the
complete bridge/hook costs twelve. Tests/source are 115,808/115,814. No node,
case or cap is removed; initial adapter/lint failures are archived. This bounded
accounting scope is reviewed; 50 accounting rows and all 117 completion rows
remain open.


Kiss's collected independent hook captures complete expression trees, ended
input, bits, exit code and input progress at cap16. Its lossless DAG decoder
preserves shared subterms; all 835 cases, five old controls and return(835,5)
remain. Five schema erasures add controls. All 835 ordinary native/state/output
traces remain byte-identical; no parser, model, corpus, node or cap is removed.

Python 3.12.11–final 3.15.0 installed checks retain 507 completions, 154 input
failures, 126 argument failures, 42 constructor refusals and six bounded runs:
5,360 valid boundaries plus 42 unavailable constructor states, peak 352 bits.
Full raw/VM/debug/public captures, cycles, views, exit codes, IO counters,
success-only steps, held histories and independent full-width recounts agree.
Compact DAG preflight retains every case and a shared-node positive control;
the full native accounting hook passes in 0.270s under its 60s limit.

Five late initial-value substitutions and five always-None native omissions
retain full witness trajectories, cycles, IO and histories; measured and
independent charges lose each component's exact peak. The monotone ended flag
uses late False substitution at True. A native 43-bit anchor counts expression
40 plus bits/exit/cursor 1 each; shared-reference decoding retains multiplicity.
Seven read and six writer phases preserve repeated EOF/newline, invalid-input
recovery and expression commit before writer refusal, followed by exit/idle
without retry. Nine guarded pairs retain actual failures, bounded runs and
live cap-zero/cap-one execution, checking exit codes alongside HALTED completion.

Five token-scan clients reuse unchanged token_span, saving eighteen
formatted lines. Full ordinary/mutant replays retain 6,594 constructor attempts,
63,437 steps, 76,357 observations, 50,978 meter samples, 4,832 IO events and
42 rejection controls with byte-identical typed streams. Scripted coin and
random-direction objects retain every field/draw; Befunge before/after leaves
finish in 41.84/42.54s under separate 60s limits. Numeric grammar, host caps,
invalid-token consumption, character reads and unread whitespace are unchanged.

The complete bridge costs twenty-one lines; tests/source 115,811/115,814.
Initial serializer and installed-alias setup failures are archived. This bounded
accounting scope is reviewed; 49 accounting rows and all 117 completion rows
remain open.


Worker output-limit flags now match the producer's exact error-class/message
predicate in both directions. Six contradictory envelopes were accepted before;
all six are now rejected. The real capped worker retains its output byte and
two successful steps. Python 3.12.11–final 3.15.0 installed probes each cover
49 observations, including that real worker; all 24 canonical results remain
identical, with notes, bounds, prefixes, trailing records and reap behavior.
Three guard mutants fail the retained regression node. The rebuilt 951-file
wheel changes only the decoder module; no request, persistence or native format
changes. Tests/source 115,818/115,819; no node or old case is removed. The
38-family source inventory still needs final acceptance reconciliation;
49 accounting rows and all 117 completion rows remain open.

The rebuilt wheel also retains the unchanged installed catalog regression:
117 runtimes, 114 one-bit generator roundtrips, 13,778 accounting samples,
9,033 ordinary views and 240 guarded workers per version on Python 3.12–3.15.
Twelve leaves pass in 58.26s total, maximum 10.78s against separate 60s caps;
all old golden data is unchanged, including Fargo's eleven ordinary samples.
This is native regression evidence, not independent semantic model closure.


Stisp's independent proper-list hook is now collected, preserving all 257 cases,
cap12, three old controls and implicit None return. Three schema erasures add
controls. Complete cons heads, ordered frames/arguments and rendered latch are
predicted independently; all old ordinary/native traces remain byte-identical.
Python 3.12.11–final 3.15.0 installed checks retain 180 completions, 36 unmatched
frame failures, 36 bounded runs and five constructor refusals: 1,620 valid
boundaries per raw/VM/debug route, peak 113 bits. All captures, cycles, views,
IO, successful active steps, held histories and independent full-width recounts
agree. All 257 bounded public calls and 221 terminating/error cases through both
native entrypoints and unbounded public execution retain their envelopes.

Fixed source-index schemas/lookups are checked independently; two real cache
corruptions change future behavior while captures stay initially equal. Late
head/frame freezes, argument-only loss and omissions reject. Constructor
omissions lose exact 24/72/1-bit peaks. Monotone rendered distinguishes late
False substitution (one-bit loss), late None (no loss), and always-None schema
erasure (one-bit loss). Ten writer probes retain dump-before-latch retries and
partial-prefix duplication without counting a dump as an active command.
Literal charges 1/57/97/0/416/257 are executed; eleven guarded workers retain
live cap-zero/cap-one and a real one-character output-limit prefix. The separate
14-rewrite drain does not change the original cap12 corpus. Improper-cons,
general unbound grammar and deep independent accounting remain open.

Thirteen rejection loops reuse the exact stalled/wrong/overread cohort, saving
33 formatted lines. Full ordinary/mutant replays retain 5,295 constructor
attempts, 45,838 steps, 56,280 observations, 10,394 meter samples, 24,721 IO events
and all 67 rejection controls, including 39 moved calls. A real correct native
middle factory fails its expected-assertion context; a tagged RuntimeError
escapes with committed state intact. Line's first 60s replay timed out after
1.39GB of diagnostic serialization. Lossless raster-row run lengths preserve
all fields/caches and roundtrip every unique immutable row tuple; complete
before/after hooks finish in 0.922/0.946s, including all 84 compiled execution
calls. No source, case, cap or assertion is dropped. The complete 32-line
bridge leaves tests/source 115,817/115,819. This bounded accounting scope is
reviewed; 48 accounting rows and all 117 completion rows remain open.


NOR machine, Movesum and Nandypants now check complete independently predicted
workspace components in their collected hooks. All 3,176/2,297/1,569 cases,
64/64/32 caps, 24 original controls and returns remain; thirteen schema erasures
add controls. Ordinary native traces retain byte-identical 96,255 steps and
103,238 captures. No model, source case, assertion, node or cap is removed.

Installed Python 3.12.11–final 3.15.0 checks retain 75,810/16,976/10,452 valid
boundaries per raw/VM/debug route, peaks 232/37/23 bits, and 59 unavailable
constructor states. Full views, cycles, IO, successful steps, held histories
and independent component recounts agree. Read-only commands, lexical seeds,
label maps and Movesum's insertion-ordered memory keys are checked separately.
All 7,042 bounded public cases remain; finite ordinary/native entrypoints and
34 selected guarded workers retain their envelopes and live cap-zero/cap-one
controls. Separate NOR huge-number probes add four guarded pairs.

Populated freezes, omissions and literal anchors distinguish state errors from
lost charges. Nandypants additionally retains 48 complete masked trajectories,
including actual schema omissions and rejected late schema switches. Its twelve
writer probes distinguish preadvance byte output from postadvance final flush.
NOR's twenty writer probes retry before its done latch; Movesum's ten retain
command/quiet/printed commits and advance past a failed print. Separate
5,001-digit probes preserve default/640 formatting failures and disabled-cap
success: NOR retains its queued value for retry; Movesum commits before format.
Physical writer refusal uses an explicit independent formatter where needed.
Broader numeric/source grammar and huge Nandypants labels remain open.

Nine existing step loops reuse count_steps, saving 42 formatted lines; complete
bridges cost 39. Full hooks retain 1,556 public and 608 direct generator calls,
3,033 native instances, 129,155 steps, 135,221 captures, 80,528 meter samples and
32,087 IO events with byte-identical traces. Every inert helper is rejected;
tagged exceptions escape after a real native step. Tests/source are
115,814/115,819. Probe-format, bookkeeping and import-order failures are
archived. These bounded accounting scopes are reviewed; 45 accounting rows
and all 117 completion rows remain open.


Suffolk's collected independent hook now checks all six workspace components.
All 1,985 cases, four native runner witnesses, cap64, twelve original controls
and return(1989,12) remain; six erasures add controls. Complete ordinary hook
traces retain byte-identical 69,139 step attempts and 71,124 captures.

Installed Python 3.12.11–final 3.15.0 retains 71,104 valid boundaries per
raw/VM/debug route, five constructor refusals and peak 79 bits. Full captures,
cycles, IO/newline state, successful steps, seven named views and independent
component recounts agree. All 1,985 bounded public cases remain. Independent
certificates admit 1,096 EOF halts, 430 periodic returns, 54 character errors
and five constructor refusals to ordinary execution; 400 uncertified cases
stay bounded. Native periodic reports retain their exact cycle witnesses.

Seventy-two actual masked trajectories retain all canonical state/IO/views and
histories. Whole-schema omissions lose exact component peaks; late schema
switches reject, while late None retains initial width, including exhausted's
one-bit charge. Ten writer probes retry preadvance failures, including partial
prefixes; EOF provider and invalid-character retries retain their distinct
states. Six literal anchors include a 17-bit all-field witness; read-only code,
progress-only IO and two real cycle corruptions are checked separately. Ten
guarded workers retain active cap-zero/cap-one and a real output-limit prefix.
Unbounded growth, huge-integer character/view policy and arbitrary IO providers
remain open.

Back, Kiss and two Suffolk loops reuse count_steps, saving twelve formatted
lines; the complete bridge costs eleven. Full hooks retain 137 public generation
calls, two direct lookup builds, 37 instantiations, 321 native instances,
159,080 step attempts, 159,722 captures, 61,275 meter samples and 2,628 IO events
with byte-identical typed traces. Inert helpers reject and tagged exceptions
escape after real steps. Exact integer counter probes preserve the original
1,000/5,000-step failures and empty assertion arguments. No case, assertion,
node or cap is removed. Tests/source are 115,813/115,819; 44 accounting rows
and all 117 completion rows remain open.


Minsky Swap's v2 workspace and cycle key retain the post-halt dump latch.
Two actual '+' runs previously had equal captures but different next-step
outputs ('1 0' versus empty); v2 distinguishes them and counts four completed
bits instead of three. Parser and transition/output logic are unchanged.
All 610 independent cases, cap64, seven controls and return(610,7) remain;
five erasures add controls. Complete native state, readonly program/targets,
IO and outputs retain byte-identical 11,872 step attempts/12,477 captures;
intentionally corrected public projections are archived separately.

Installed Python 3.12.11–final 3.15.0 retains 475 completed runs, 130 bounded
runs, five constructor refusals and 12,477 valid boundaries per raw/VM/debug
route, peak eleven bits. Full views, successful active steps, post-halt
completion, IO, held histories and independent recounts agree. Sixty actual
masking trajectories distinguish charged fields from the ordinary read-only
zero cursor: freezing it is a no-op, late None adds a phantom bit, and a
constructor omission charges zero. Three actual caller-read supplements add
two cursor bits without inventing native input instructions or replacing state.
Six writer refusals preserve dump-before-latch retries and partial prefixes;
nine guarded workers retain live caps and a real output-limit prefix.

The completed-run bound and constant pins add one bit. Per version, 246 constant
runs, 2,124 pinned/exhaustive-three-input runs and 856 arity1/2/3/6 bound runs
retain exact source bytes, full outputs and active commands; every completed
charge adds exactly one. Measured attained bounds are 10/12/12/16 bits.
All committed generator size/command pins remain unchanged: commands selects
the last input row; worst_row_commands is separate. An initially incorrect
new verifier compared that selected pin to the maximum; producer/consumer
review corrected the verifier, preserving all per-row assertions and evidence.
Generated proof docs are current. The rebuilt 951-file wheel changes only the
interpreter and workspace formula modules.

Existing source_checker plus a single-use independent projection keeps the
complete bridge at four test lines; the necessary native correction removes
one obsolete source line overall. Tests/source are 115,817/115,818. No node,
case, cap or old assertion is removed. Giant-target/register and broader source
policies remain open; 43 accounting rows and all 117 completion rows remain open.


NQ's independent hook now checks all six workspace components under both
guard bindings. All 1,573 cases, cap64, eight controls and return(1573,8)
remain; six erasures add controls. Complete ordinary traces retain byte-identical
23,536 step attempts and 24,994 valid captures, including IO/newline state.

Installed Python 3.12.11–final 3.15.0 retains 24,994 boundaries per raw/VM/debug
route, 115 constructor refusals and peak 130 bits. Invalid guard settings refuse
before IO or worker launch; raw constructors retain their distinct ValueError.
Full histories, readonly parsed/source metadata, seven views, active commands,
cycle keys and independent component recounts agree. All 1,573 bounded public
cases remain; 1,272 also run ordinarily, while 301 uncertified cases stay bounded.
Seventy-two actual masks retain complete canonical trajectories; monotone flags
retain their initial one-bit charge under late None. Three queue omissions from
construction lose four bits, and three recursive-binding positives remain.

Sixty writer routes plus six wrapped-write routes verify state commits before
writer failures and next-instruction retries. EOF, invalid-input and underflow
retries retain their distinct states and IO counters; whole-input reads count
once even when empty or invalid. Fourteen literal anchors, six real metadata
corruptions and seventeen guarded workers retain active caps and output prefixes.
Two finite 5,001-trit supplements attain 10,005/10,018 bits without widening the
original corpus; arbitrary source grammar and unbounded execution remain open.

Four complete Suffolk/Nandypants/NOR/BrainIf hooks inline single-use projections,
saving thirteen formatted lines against the nine-line NQ bridge. Typed ordered
traces retain 7,771 constructor attempts, 158,329 step attempts, 173,765 captures,
158,304 meter samples, 8,994 IO events and all 44 rejection controls byte-identically.
Each actual callback rejects a concrete erased field; ordered dictionaries,
deque capacity and bool/int identity have positive codec controls. No case,
assertion, node or cap is removed. Tests/source are 115,813/115,818; 42 accounting
rows and all 117 completion rows remain open.


Retrograde's seven components are reconstructed from complete independent
legacy histories. Popcount changes toggle the previous signed coordinate;
encoding those coordinates gives both packed tape halves without another engine.
Actual '*<<*>>>>'/'*>>*<<>>' runs share the boundary-six legacy memory view but
have halves(2,1)/(0,5) and future outputs0/1. Full histories distinguish them.
Actual '<<>>' returns blank memory(0): visited extent is not persistent state.
The original model remains unchanged, with all 543 cases, cap64, ten controls
and return(543,10); seven component erasures add controls.

Installed Python 3.12.11–final 3.15.0 retains 3,334 valid boundaries per raw/VM/debug
route, 231 constructor refusals and peak sixteen bits. All 543 bounded public
cases remain; 311 completed runs and 231 constructor refusals also run ordinarily,
while one uncertified case stays bounded. Full state, readonly source/pairs/offsets,
cycle keys, views, held histories, active commands and independent recounts agree.
Eighty-four actual masks distinguish six written fields from the read-only zero
cursor; freezing that cursor is a no-op, while late None adds a phantom bit.
Three cursor omissions from construction retain the ten-bit native charge.
Three actual caller-read trajectories change cycle keys and add two cursor bits
without replacing native state.

The final dump is active and latches printed only after successful output.
Six writer refusals retain state, retry the same bit and preserve partial prefixes;
ten guarded workers retain live caps and a real output-limit refusal. Literal
charges empty1/<**6/<<>>7 retain cleared-cell peaks; pair corruption changes
real future execution. Complete original callers pass before and after, retaining
2,947/2,954 constructor attempts, including all Boolean and serialized witnesses.

Five FRACTRAN/HOT/Container/Sbleq/RAM0 hooks inline only single-use native views,
saving eighteen lines against the twenty-line bridge. Complete typed traces retain
5,273 constructor attempts, 57,028 steps, 67,510 captures, 28,147 meter samples,
2,658 IO events and all 23 controls byte-identically. Concrete callback erasures
reject; no case, assertion, node or cap is removed. Tests/source are 115,815/115,818.
Broader grammar and unbounded execution remain open; 41 accounting rows and all
117 completion rows remain open.


Interprogck8's independent hook now checks all six workspace components.
All 461 cases, cap48, three original controls and the None return remain;
six component erasures add controls. The complete original model, helpers and
corpus are unchanged. Ordinary native/IO traces retain byte-identical 2,423
step attempts and 2,884 captures.

Installed Python 3.12.11–final 3.15.0 retains 2,884 boundaries per raw/VM/debug
route, peak 196 bits. All 461 bounded public cases remain; 355 completed runs,
97 native halts and eight EOF failures also run ordinarily. One uncertified case
stays bounded. Full state, cycle keys, views, held histories, IO/newline counters,
active commands and independent recounts agree. Readonly compiled metadata tracks
the old program immediately after z, then reloads before the next active step,
including a failed input step; no eager-refresh assumption is introduced.

Seventy-two actual masks and eighteen complete reduced-model trajectories retain
a 92-bit all-field witness. Late None retains initial widths, including the full
64-bit program charge; schema omissions lose the independently predicted peaks.
Thirty writer routes plus six final-write/idle routes retain commit-before-write
behavior: continuation advances, while a failed final write leaves an already
halted machine whose retries do not print. EOF retries, malformed reads, readonly
corruptions, two prepared-source routes, three literal anchors and seven guarded
workers retain exact states, prefixes and active caps. Deterministic developer,
random/range commands and broader grammar remain outside the independent scope.

Three Nandypants/Between/Forþ hooks inline only single-use actual views, saving
thirteen lines against the fifteen-line bridge. Complete typed ordered traces
retain 2,872 constructor attempts, 15,619 steps, 21,281 captures, 15,615 meter
samples, 1,593 IO events, 27 assertion controls and Between's three EOF retries
byte-identically. The codec retains mutable aliasing, every Forþ scope backing
slot, undo links, sentinel and unset keys; real root reversals and concrete
callback erasures are positive controls. No case, assertion, node or cap is
removed. Tests/source are 115,817/115,818; 40 accounting rows and all 117 completion
rows remain open.


ROTfuck's full rotation count is reconstructed from successful command
transitions in the unchanged independent rewrite history. Comments, idle steps,
EOF and firing partnerless brackets do not increment it. An actual ninth-command
run retains twelve written bits; truncating the counter modulo eight preserves
the legacy view but drops the charge to eleven. All 2,933 cases, both directions,
cap24, the original control and None return remain; five erasures add controls.
Ordinary native/IO traces retain byte-identical 12,773 steps and 15,706 captures;
the original negative still rejects, now after one native step rather than five.

Installed Python 3.12.11–final 3.15.0 retains 15,706 boundaries per raw/VM/debug
route, peak 22 bits. All 2,933 bounded cases also run ordinarily: 1,765 complete,
730 raise HaltError and 438 reach EOF. Full state, immutable source/direction,
cycle keys, views, IO/newline counters, held histories and independent recounts
agree. Sixty actual masks plus fifteen reduced-model trajectories retain exact
peaks, including late None's initial-width charge. Both-direction sixteen-bit
witnesses, ten literal anchors, six metadata corruptions, detached preparation
and eleven guarded workers retain actual states, live caps and output prefixes.
Sixty writer routes preserve output-before-restore failures and same-command
retries, including duplicate partial prefixes. Broader grammar and unbounded
execution remain open.

Nine complete funding scopes save twenty-eight lines against the twenty-eight-line
bridge. Existing reject_faults replaces five identical control loops; three
checkers reuse agrees' exact returned object, NQ inlines its sole actual view,
and BrainIf research reuses count_steps. All module inverses preserve models,
cases, assertions, control order, caps and returns. Complete typed traces retain
12,504 constructor attempts, 523,597 native step calls, 547,851 captures, 43,243
meter samples, 39,502 IO events and 59 rejections byte-identically. BrainIf's
594 generator calls retain exact emitted programs and all 5,808 executed runs.

Codecs retain persistent-map buckets, continuation depth, cache order and exact
node bindings, regex metadata and RGB data; checked program dictionaries reject
mutation. Correct-native, tagged-exception, concrete-erasure and codec corruption
controls reject. The original and reused counters both fail after 10,001 real
steps with empty assertion arguments. Tests/source remain 115,817/115,818;
39 accounting rows and all 117 completion rows remain open.


FRACTRAN's independent integer history now predicts source-selected integer or
prime-exponent register variants, the printed latch and input cursor. Literal
source bounds choose the representation; native values never supply expected
factors. All 2,576 original cases, seven syntax cases, cap12, three old controls
and None return remain. Two finite positives reach integer fallback and indexed
scan alongside Cursor; three erasures add controls. Ordinary traces retain
byte-identical 26,535 steps and 29,111 captures. The old negatives still reject,
now after five native steps in total rather than eight.

Installed Python 3.12.11–final 3.15.0 passes all thirty-six leaves: 2,578 cases
and 29,123 boundaries per raw/VM/debug route, peak14 bits. All bounded public
cases run; 616 independently certified finite cases also run ordinarily, while
1,962 remain bounded. Source-derived rule/index maps, selected-rule caches,
Cursor cleanup trees, cycle keys, views, IO and retained histories agree with
independent recounts. Twenty-four actual masks, six reduced trajectories and
six readonly-cursor trajectories retain exact peaks; late None loses zero on
the four-bit witness. Fifteen literal/backend anchors, nine metadata corruptions,
detached preparation, a real caller read and twelve guarded workers pass.
Thirty writer routes retain printed-before-write behavior: failure leaves the
machine halted; retries never repeat even a partial prefix. Broader Unicode,
huge formatting/materialization and arbitrary IO callbacks remain open.

The unchanged trial factorizer moves from its proof module to a stdlib-only
owned test helper. All sixteen original proof cases retain byte-identical calls
and results, including 217,322 choices and 6,502 factorizations. Five complete
funding scopes save thirty lines against the thirty-line bridge: Unary/Between
reuse agrees, Collatz inlines its actual view, and Piet/Super SNUSP reuse the
existing read-call guard. Models, assertions, cases, caps and returns remain.
Traces retain 6,913 constructor attempts, 23,799 native steps, 29,981 captures,
23,354 meter samples, 4,764 IO events, 33 rejections and 362 public generator
calls byte-identically, including full lazy raster closures and RGB source.
Actual extra reads before native output reject in both old and shared guards,
including empty writes; returned-object identity and tagged native exceptions
remain intact. Tests/source stay 115,817/115,818; 38 accounting rows and all
117 completion rows remain open.


S*bleq's existing independent sparse-memory model now exposes its stopped
latch alongside memory, instruction and input progress. All 773 cases, six
native variants, cap12, the original output control and None return remain;
four erasures add controls. Native/IO traces retain byte-identical 2,328 steps
and 3,101 captures; the old negative retains four native calls. Exposing the
existing model flag requires no second engine or private compatibility wrapper.

Installed Python 3.12.11–final 3.15.0 passes all thirty-six leaves. Raw and
native preparation each retain all 773 cases/3,101 boundaries, peak34 bits;
765 finite native cases also run ordinarily and eight stay bounded. Actual
VM/debug/public routes retain exactly the 133 registered-default cases,
579 boundaries per stepped route, peak30 bits; 131 finite public cases run
ordinarily and two stay bounded. The other 640 cases use native variants that
public settings cannot express; they are never counted as public coverage.
A source-only census of all 117 preparation declarations finds this sole
unregistered semantic option pair, store/indirect. Public variant registration
requires a separate whole generator migration; lifecycle/completion stays open.

Sixty-four live masks and sixteen consistent reductions retain exact peaks.
The default mask witness charges29 bits; late None loses zero for memory,
input and stopped, while instruction loses one. A negative pointer write
retains stopped=True outside memory; the nondefault erasure witness changes
all four fields and charges27 bits. Sixty-four physical writer routes retain
read-before-write/control-after-write behavior: failure leaves the instruction
active; retry reads the next character or EOF0, then advances. Repeated
output-before-negative-branch errors preserve control while accumulating IO.
Two readonly-choice corruptions, detached factory options, nine unsupported
settings/input/worker refusals and seven guarded workers pass. Broader parsing,
huge/cell-limit inputs and arbitrary callbacks remain open.

Thirteen complete funding scopes save fifteen lines against the fifteen-line
bridge. Five sole expected aliases disappear, eight duplicate helper imports
use their existing namespace, and Dig reuses the existing rejection helper.
Every model, assertion, case, control order, cap and return remains. Dig's one
shared literal list replaces three equal fresh lists; model/native copies
preserve logical data without claiming source-allocation identity. Typed traces
retain 9,646 constructor attempts, 103,596 native steps, 122,082 captures,
102,037 meter samples, 14,443 IO events, 124 rejections and 96 public generator
calls byte-identically. The codec retains all 1+i code fields, offset arrays
and function identities. Correct-native, tagged-exception, returned-identity
and codec-corruption controls pass. Tests/source remain 115,817/115,818;
37 accounting rows and all 117 completion rows remain open.


Modulous's existing independent assembled-module model now predicts instruction,
stack, variables, input cursor, stopped and input reads; draws remains readonly0.
All 127 cases, five constructor syntax cases, cap48, three old controls and None
return remain; seven erasures add controls. Ordinary traces retain byte-identical
1,047 steps and 1,174 captures. The old controls still reject, now after two
native steps rather than twelve. The 140-bit witness populates six mutable fields;
it makes no populated-draw claim.

Installed Python 3.12.11–final 3.15.0 passes all thirty-six leaves. Raw, prepared,
VM and debug routes each cover 127 cases/1,174 boundaries, peak142 bits. All
bounded public cases run; 119 independently finite cases also run through native
and public ordinary entry points, while eight stay bounded. Ninety-six live
masks, twenty-four consistent reductions and eight readonly-draw trajectories
retain exact peaks. Forty native/prepared/VM/debug writer trajectories and eight
public writer trajectories retain print-before-transition behavior: failure
leaves the command active and stack intact; retry can repeat a partial prefix.
Twelve repeated EOF/character-error routes, four consumed-token retries,
detached preparations and eight guarded workers pass. A verifier ownership fix
retains actual bounded Seeded and ordinary None public providers; injected
NoDraw remains mandatory. The rejecting RND guard fires once, without certifying
RND semantics. Named RND, bare INP, missing operands, huge numeric inputs,
broader grammar and arbitrary callbacks remain open.

Twelve contract clients share an explicit native/IO constructor factory, saving
thirty lines against the nineteen-line bridge. Fresh IO is created on every
call; all 78 inherited nodes remain, with 77 passes and one existing skip.
Typed traces retain 66 constructors, 120 steps, 252 captures and 55 IO calls
byte-identically, including full injected snapshot-function metadata. Twenty-four
old/new constructor controls retain object identity, IO-before-native ordering,
constructor refusals and actual-class patches. The helper is appended to preserve
all existing shared-contract code positions. Production and generators remain
byte-identical. Tests/source are 115,806/115,818; 36 accounting rows and all 117
completion rows remain open.


Painfuck's existing independent tape/conditional model now predicts all nine
workspace fields. All 1,951 original cases, three constructor translation
assertions, cap32, three old controls and None return remain; nine erasures add
controls. Ordinary traces retain byte-identical 11,530 steps and 13,484 captures,
including the three constructor-only checks. Old negatives still reject, now
after two native steps rather than eleven. A 19-bit supplemental witness writes
all nine fields, including origin, repeat, input reads and RNG draws.

Installed Python 3.12.11–final 3.15.0 passes all thirty-six leaves. Constant-coin
raw/prepared routes each retain 1,951 cases/13,481 boundaries. Genuine VM/debug
routes separately predict both seeds for every original source/input, yielding
3,902 cases/26,966 boundaries each; original-corpus peak16 bits. All 3,902 bounded
public runs execute; ordinary runs cover 1,947 finite native cases and 5,821
finite public projections, with four native and twelve public projections kept
bounded. Public default None is used only without random commands; seeded
routes retain actual providers and independently checked stdlib RNG states.

One hundred forty-four live masks and thirty-six reductions retain exact peaks.
Forty-eight stepped writer trajectories, twenty public writer trajectories,
four provider refusals and nine guarded workers pass. Physical refusal retains
pre-step control while completed IO/draws persist; retry consumes fresh RNG.
V1's supplemental continuation wrongly executed the command after repeat0.
Independent installed probes and V2's thirty-two error/loop continuations plus
eight public continuations establish its actual no-effect command consumption,
including repeated EOF and two consumed invalid tokens. The original model
still stops at its first error and remains unchanged. Repeat families c/t,
broader source/numeric grammar, huge formatting and arbitrary callbacks stay
open; trailing y/py/yy remain included.

FALSE, Forþ and LaserFuck share their exact signed32 scalar rule, saving five
lines against the fifteen-line bridge. Full hooks retain 3,974 constructor
attempts, 22,022 steps, 29,962 captures, 4,119 meter samples, 2,291 IO calls and
fourteen rejections. Complete flow traces match after the proved source-line
relocations: the two injected IO lambdas move four lines, with all other code
and closure fields unchanged; raw metadata is retained separately. No full
metadata byte identity is claimed. Fifty-one signed boundary values and eleven
codec controls pass. The shared helper is appended, preserving all existing
shared code positions. Production/generators remain byte-identical.
Tests/source are 115,816/115,818; 35 accounting rows and all 117 completion rows
remain open.


Fish's existing independent linear model now exposes its stopped flag in both
rich state and halt status. All 471 cases, including one constructor refusal,
cap48, three old controls and None return remain; twelve erasures add controls.
Transition code is unchanged. Projecting only the added flag from rich views
retains byte-identical 3,727 native steps and 4,197 captures; old negatives still
reject, now after four native steps rather than fourteen.

Installed Python 3.12.11–final 3.15.0 passes all thirty-six leaves. Raw, prepared,
VM and debug routes each cover 471 cases/4,197 captured boundaries, peak82 bits,
with constructor refusals checked separately. All bounded public cases run;
467 finite native/public cases also run ordinarily, plus the empty constructor,
while three remain bounded. Actual public seeded/ordinary-None providers stay
intact; injected NoDraw protects raw/prepared routes. The real random-turn guard
fires once, without certifying random-turn semantics.

Ninety-six mutable masks, twenty-four reductions and forty-eight readonly
trajectories retain exact peaks. The 27-bit witness writes x, stacks, registers,
quote, stopped and input cursor; y/dx/dy/cells/width/height remain readonly.
Fifty-six stepped writer routes and twenty-eight public routes retain committed
pop/advance before physical output: refusal leaves the next command active;
resume never repeats the failed write. Sixteen repeated halts, four provider
refusals and twelve extra EOF/quoted-command traces pass. Nine guarded children
cover eight native/worker parity pairs and one isolated output-limit witness.
V2's rejected in-process output limit is retained as a zero-IO preflight control;
V3 compares its separate step-bounded prefix only as execution metadata, without
claiming equal control after the failed write. Multidimensional movement, code
writes, random turns, huge arithmetic/formatting and general grid grammar stay open.

Four funding scopes save seventeen lines against the seventeen-line bridge:
shared residual-count math, explicit reader factories, Dimensional factory reuse
and Balik page-source construction. All thirty inherited/constructor nodes retain
27 constructor attempts, 79 steps, 129 captures and 28 IO calls byte-identically,
including both malformed-constructor refusals and full Dimensional slot graphs.
Twenty-one scaling nodes retain all 217 bound calls and intermediate math values.
Balik retains its full 1,744-case/eighteen-control hook and all seven raw tests;
raw-test flows retain 8,601 steps, 12,057 captures, 8,499 meter samples and 1,291
IO calls. Two injected IO callbacks move ten source lines; all other code/closure
fields agree and raw metadata is retained. No full metadata byte identity is
claimed. Ten old/new constructor routes, eleven codec controls and a live bad
residual-count control pass. Shared helpers are appended, retaining existing code
positions. Production/generators stay byte-identical. Tests/source remain
115,816/115,818; 34 accounting rows and all 117 completion rows remain open.


Positive installed certification consumers now reconcile all 117 languages on
macOS Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0. Thirteen owned records
and 104 default fallbacks match all eleven source-declared fields, including
callable identity/signatures. All 185 declared callable references match their
exact dataclass field paths and load their declared signatures across all 114
backends. Deferred metadata reads leave implementations unloaded; explicit
loading observes target mutation without restoring signature proxies.

Twelve fresh installed checks retain the unchanged 951-file wheel and actual
host numeric policy. Genuine owned/default loading, wrong-record TypeError,
nested dependency propagation and five malformed parameter declarations pass
live controls. Existing release smokes already load certification in their 114
backend children; this adds complete record/default/reference reconciliation.
Formula values, resource claims and broader certification/runtime acceptance are
not established by declaration loading. All claims remain pending; 34 accounting
rows and all 117 completion rows remain open.


SLOW ACV MAMMALIAN's independent array model now exposes its existing stopped
flag and checks all six workspace components. All 1,600 cases/eight dialect
profiles, cap24, zero old controls and None return remain; six erasures add
controls. Projecting only the added rich-state flag retains byte-identical
12,240 native steps and 13,840 captures. The 104-bit witness writes all six
components and stops at instruction four within five tokens.

Installed Python 3.12.11–final 3.15.0 passes all thirty-six SAM leaves. Raw,
prepared, VM and debug routes each retain 1,600 cases/13,840 boundaries, peak143
bits. All 1,600 native/public cases also run ordinarily, retaining modeled
errors. Actual dialect settings cover all eight profiles; defaults remain
implicit. Ninety-six mutable masks and twenty-four reductions retain exact
peaks, including three zero-loss late-None fields. Across eight profiles,
128 stepped writer routes and 64 public routes retain precommit refusal and
retry. Thirty-two repeated EOF, thirty-two provider refusal and thirty-two
empty-program traces pass. Sixteen unknown-word constructor routes and explicit
invalid-option preflights pass; fourteen guarded children cover thirteen parity
pairs and one isolated output-limit witness. General source grammar and arbitrary
external failures remain open.

Freestajlo's existing eight-component bridge needs no source change. All 1,494
linear cases, seven syntax refusals, cap64, three old controls, eight erasures
and None return remain. Thirty-two installed leaves pass on the same four
versions: raw, prepared, VM and debug routes each retain 1,494 cases/17,830
boundaries, peak27 bits; all 1,494 cases run ordinarily on native/public routes.
Independent literal IR predicts token positions, operands and source offsets.
Calls/functions remain readonly throughout this vocabulary; no populated-frame
coverage is claimed. The six mutable components have a 23-bit witness.

Ninety-six actual masks, twenty-four reductions and sixteen readonly
trajectories pass. Fifty-six stepped writer routes and twenty-eight public
routes retain postcommit pop/advance across physical refusal. Sixteen repeated
halts, eight provider refusals, four partial scanner refusals, eight surrogate
continuations and twelve extra IO traces pass. Ten guarded children cover nine
parity pairs and one isolated output-limit witness. Function/control/string
grammar, huge numeric policy and arbitrary external failures remain open.

Nine existing size nodes share an appended helper, saving thirty-three lines
against SAM's eighteen-line bridge. Their full 2,304 generated artifacts and
portable records remain byte-identical, totaling 1,564,386 source characters;
all nine local literal assertions remain. Separate ordinary execution checks
all 18,432 input rows with actual defaults; random provider paths are sampled,
not exhaustive. A real appended source character at table137 is rejected after
all 256 generation calls. All 951 production files stay byte-identical; no
case, assertion, cap or node is removed. Tests/source are 115,801/115,818;
32 accounting rows and all 117 completion rows remain open.


Super SNUSP's existing independent single-row model now checks all nine
workspace components. All 231 normal cases, two constructor refusals, cap64,
three old controls and None return remain; nine erasures add controls.
Model transitions and constructor callbacks stay unchanged; all 2,211 native
steps/2,442 captures remain byte-identical. The 22-bit witness writes seven
components; row and heading remain readonly.

Thirty-six V2 installed leaves pass on Python 3.12.11–final 3.15.0. Raw and
prepared routes each retain 231 cases/2,442 boundaries, peak89 bits. Actual
seeded VM/debug routes each retain 462 cases/4,884 boundaries. All 231 public cases
run ordinarily with the real default None provider, including eighteen
single-draw sources checked against independently enumerated finite full-trace
and result relations. Explicit seeded public profiles add 462 bounded and
462 ordinary runs. Wrong output, wrong draw upper and double draws fail live
controls; random paths are sampled, not exhaustive. V1's missing frozen helper
binding is retained; V2 binds it and checks every removed import before loading.

One hundred twelve mutable masks, twenty-eight reductions and sixteen readonly
trajectories pass. Fifty-six stepped and twenty-eight public writer routes
retain committed control across physical refusal. Eight repeated EOF, eight
provider refusals, twelve repeated halts and four argument retries pass.
Eleven guarded children cover ten parity pairs and an isolated output-limit
witness. Mirrors, general grids, huge valid numeric input and output policy
remain outside this independent cohort.

Rubic and IEBEL reuse the unchanged size helper, saving seven lines against
the twenty-two-line bridge. Their complete owning nodes retain 706 artifacts,
including 48 nested balance calls, plus 498 native constructions, 6,072 steps,
6,570 captures and 8,000 IO calls byte-identically. Both local literals,
all constant arities/options/rows and IEBEL's analysis-complement control remain.
All 512 size-corpus programs execute all 4,096 input rows; an appended source
character is rejected and ten typed codec controls pass. All 951 production
files stay byte-identical. Tests/source are 115,816/115,818; no case, assertion,
control, node or cap is removed. 31 accounting rows and all 117 completion rows
remain open.


Piet's existing independent flood-fill/stack model now checks all seven
workspace components. All 911 cases, cap32, three old controls and None return
remain; seven erasures add controls. All 22,304 native steps/23,215 captures
remain byte-identical. Separate numeric, chooser and halt pictures collectively
write every component; their charges are 9, 7 and 1 bits. Initial black charges
zero written bits despite eight bits of initial width.

Thirty-six V2 installed leaves pass on Python 3.12.11–final 3.15.0. Raw,
prepared, VM and debug routes each retain 911 cases/23,215 boundaries, peak67
bits. All 911 public cases run bounded; 255 independently finite cases also run
ordinarily through native/public entrypoints. The other 656 remain bounded.
Independent Port events supply EOF attempts, successful reads and newline flags;
all RGB cells, source keys, dimensions and explicit scale1 agree. V2 preserves
byte keys and tuples in mask receipts; V1's encoding failure remains archived.
Its ordinary-public counter names calls already present in V1.

One hundred twelve actual masks and twenty-eight reductions use separate
populated witnesses. Sixteen propagating writer refusals and eight public
routes retain precommit control; eight character ValueError routes instead
retain the native swallowed-error commit. Character RuntimeError remains plain;
numeric ValueError retains its ProgramError envelope. Eight provider refusals
and twenty extra IO traces pass. Nine guarded children cover eight parity pairs
and an isolated output-limit witness. White/sliding paths, inferred scales,
huge valid numeric input and broader grid acceptance remain open.

Basicfuck, Hot and CARP share the unchanged size helper, saving fifteen lines
against the fourteen-line bridge. Their complete owning nodes retain 997
artifacts, 582 native constructions, 13,188 steps, 13,770 captures and 21,086
IO calls byte-identically, including constant/majority cases and live controls.
All 768 size-corpus programs execute all 6,144 input rows. A real source-length
fault and thirteen graph-codec controls pass; graph sharing and complete typed
fields remain captured without changing test bands. All 951 production files
stay byte-identical. Tests/source are 115,815/115,818; no case, assertion,
control, node or cap is removed. 30 accounting rows and all 117 completion rows
remain open.


SendStuff's unchanged eager-message model now reconstructs canonical lazy
frames from independent history and graph, including singleton CountUp/Down
steps, fanout cursors and residual ancestors. All 263 normal/five syntax cases,
caps48/64, three old controls and None return remain; two workspace erasures
add controls. All 1,750 steps/2,013 captures stay byte-identical. The input2
witness writes both components, charging 7+1 bits.

Thirty-six installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared,
VM and debug retain 263 cases/2,013 boundaries each, peak471 bits. All 263 run
publicly bounded; 262 independently finite cases also run ordinarily through
native/public entrypoints. The growing Add cycle remains bounded. Thirty-two
actual masks, eight reduced schemas and eight constructor-None trajectories
retain captures, cycles, IO and meter histories.

Thirty-two physical writer trajectories and sixteen public routes retain
postcommit refusal state, including fanout retry printing13 after refused12.
Eight provider refusals, eight token-error/EOF continuations, four repeated-EOF
routes and two readonly-program corruptions pass. Thirteen guarded children
cover twelve bounded parity pairs and an isolated output-limit witness.
Macros, extended syntax, huge numeric host policies and unbounded growth
remain outside this independent cohort.

Ten size assertions reuse the unchanged helper, saving fifty-four lines
against the fifty-two-line bridge. Their complete owning nodes retain 3,936
artifacts, 821 instantiations, 4,974 native constructions, 150,080 steps,
155,054 captures and 66,447 IO calls byte-identically. Raw callback-code
sidecars also match. All 2,560 measured programs execute all 20,480 input rows,
including template filling; all ten local character-count pins remain.
A real extra-character fault and forty-two complete graph-codec controls pass.
All 951 production files stay byte-identical. Tests/source are 115,813/115,818;
no case, assertion, control, node or cap is removed. 29 accounting rows and
all 117 completion rows remain open.


FALSE's unchanged linear model now checks stack, variables, retained raw
frames and input cursor. All 201 normal/four syntax cases, cap64, three old
controls and None return remain; four erasures add controls. All 1,814 steps/
2,015 captures stay byte-identical. The input-A witness writes all four
components at 11+4+8+1=24 bits; its completed raw frame remains(8,8).

Thirty-six V2 installed leaves pass on Python 3.12.11–final 3.15.0. Raw,
prepared, VM and debug each retain 201 cases/2,015 boundaries, peak76 bits.
All 201 independently finite cases run ordinarily through native/public
entrypoints and publicly bounded. V1's wrong raw-constructor error expectation
remains archived; V2 requires exact ValueError for raw/prepared syntax refusal
and retains ProgramError's distinct public envelopes and original hints.

Sixty-four actual masks, sixteen reduced schemas and sixteen constructor-None
trajectories retain snapshots, cycles, IO, histories and meters. Thirty-two
physical writer trajectories and sixteen public routes preserve postcommit
state. Four provider refusals, eight repeated-failure routes, twelve EOF traces
and actual frame-end, future-source and empty-closer corruptions pass. Twelve
guarded children cover eleven bounded parity pairs and an output-limit witness.
General lambda/call/loop values and huge numeric host policies remain open.

Six size assertions reuse the unchanged helper, saving fourteen lines against
the eighteen-line bridge. Complete owning nodes retain 2,124 artifacts,
252 instantiations, 1,528 native constructions, 24,503 steps, 26,031 captures
and 17,738 IO calls in matching complete graph streams. Forbin's function-ID
keys are validated against full function objects before relocation; raw address
sidecars remain archived. Callback-code sidecars match without relocation.
All 1,536 measured programs execute 12,288 ordinary rows, including 4,096
template fills, retaining all six character-count pins (477,319 total).
INTERCAL retains 2,048 default-None provider bindings and makes zero draws in
this corpus; random paths are not exhaustive. A real extra-character size
fault and ninety-nine graph-codec controls pass. All 951 production files stay
byte-identical. Tests/source are 115,817/115,818; no case, assertion, control,
node or cap is removed. 28 accounting rows and all 117 completion rows remain
open.


Pointless's unchanged straight-line model now checks frames, pointer, tape,
bang latch and input cursor. All 2,202 cases, cap64, three post-halt steps,
old LostWrite control and None return remain; five erasures add controls.
The complete owning node retains its two earlier runs and three assertions;
all 9,863 steps/12,067 captures remain byte-identical.

Thirty-six installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared,
VM and debug each retain 2,202 cases/12,054 boundaries, peak540 bits. All 2,202
independently finite cases also run ordinarily through native/public and
publicly bounded. Physical allocation, including zero writes, is independently
tracked separately from canonical trailing-zero trimming. Populated witnesses
charge 23 and 2,061 bits.

Eighty actual masks, twenty reduced schemas and twenty constructor-None
trajectories preserve snapshots, cycles, IO, histories and meters. Thirty-two
physical writer trajectories and sixteen public routes retain postcommit
state. Four provider refusals, twelve repeated failures, eight repeated EOF
routes, twelve allocation traces and actual readonly/future-opcode corruptions
pass. Ten guarded children cover nine bounded parity pairs and an output-limit
witness. Functions, calls, brackets, declarations, parser failures and unbounded
growth remain outside this independent cohort.

Ten size assertions reuse the unchanged helper, saving the twenty-line bridge.
All eleven complete owning nodes, including both HQ parameter nodes, retain
3,825 artifacts, 5,209 native constructions, 708,810 steps, 714,019 captures,
81,112 IO calls, 42 public runs and 698 direct generator calls in matching graph
streams. Brainfuck retains actual immutable states and all 625,192 workspace
calls; serialization follows the timed test. Its unchanged five-second band
passes at 4.74/4.66 seconds. Compiled public runs retain result/IO coverage.
Raw callback sidecars remain; 254 code locations relocate with code otherwise
equal after first-line normalization.

All 2,816 measured programs execute all 22,528 ordinary rows, retaining every
local character-count pin (504,281 total). SuperSNUSP's 256 size artifacts have
builtin-string sources before/after; its former str wrapper is identity here.
Three random-capable languages retain 6,144 default-None bindings and make no
draws in this corpus; random paths remain nonexhaustive. A real extra-character
size fault and 118 codec/deferred-recorder controls pass. All 951 production
files stay byte-identical. Tests/source remain 115,817/115,818; no case,
assertion, control, node or cap is removed. 27 accounting rows and all 117
completion rows remain open.


LaserFuck's workspace v2 includes the existing dumped latch. A post-halt dump
changes future output; it now charges one bit. Native transitions and cycle
keys stay unchanged. All 3,477 cases retain 16,073 steps/19,550 captures;
comparison excludes only the model name and added component, with both full
workspace streams retained. The six-step mirror preserves ordinary state while
branching keys distinguish fresh heading choice from a fixed beam.

Sixteen focused installed leaves pass on Python 3.12.11–final 3.15.0: all four
headings, sixteen literal trajectories/112 boundaries, four mirrors, twelve
public routes, thirty-two writer retries, eighteen public fault routes and
sixteen actual latch corruptions per interpreter. Eight guarded children cover
six bounded parity pairs and output-cap refusal/success. Every process checks
all 951 packaged files and forbids operational certification imports.

All 256 three-input artifacts remain byte-identical (87,555 source characters).
Their 8,192 heading/input rows run through dump and three idle steps. These
controlled headings and later seed0 do not exhaust random paths or establish
all-step workspace peaks. Parity at n=6/7 retains source and active steps; its
measured peaks rise from 74/1,492 to 75/1,493 bits. Proof bounds add the latch.
Benchmark sampling now includes completion and failed native steps; real Stisp
regressions reproduce missing peaks of 33 and 32 bits and pass after repair.
Twenty-seven sampling cases cover all nine eligible Boolean backends within
an existing tooling node; its original cases and assertions remain.

Two constant-test loops reuse the unchanged helper, saving eight lines. Both
complete owning nodes retain 968 artifacts, 2,556 constructions, 83,644 steps,
86,200 captures and 28,600 IO calls in byte-identical graph streams. All 512
size programs execute 4,096 ordinary rows, preserving the 30,652/31,572
character pins; twenty-five codec controls and two real extra-character faults
pass. Tests/source are 115,814/115,820; no pre-existing case, assertion, control, node or cap
is removed. This fixes the latch, not the full LaserFuck accounting review:
27 accounting rows and all 117 completion rows remain open.


Constant fixtures now retain actual artifacts in a shared iterator. Eight
clients use it directly; the source iterator delegates and projects `.source`
once. All 42 existing consumers and eight new clients retain their full
58 owning cases. Module expansion restores every old body, assertion, control,
cap and marker; private frames and artifact lifetime changes are explicit.

Both complete replays retain 12,254 artifacts, 3,784 instantiations, 32,295
constructions, 2,893,863 steps, 2,952,317 captures, 477,118 IO calls, 2,757
public runs and 340 direct generations in matching graph streams. Raw address
records remain; 54,764 binding records compare after proved object relocation.
Callback source metadata stays byte-identical; arbitrary callback-object
equivalence is not claimed.

Deferred recording preserves the existing bands: Brainfuck 4.56/4.57 seconds,
Circlefuck 4.42/4.30, Unlambda's larger owner 2.21/2.18 and What!? 0.93/0.91.
Circlefuck retains all 711,449 edits, including 808 equal-valued writes; its
full transcript agrees with all 2,139 actual workspace captures. Immutable
Unlambda graphs retain complete cache contents and LRU order. Source-qualified
readonly descriptors remain distinct from logical accounting.

All 5,632 measured programs execute all 45,056 ordinary rows, including
8,192 template fills, preserving 919,606 source characters. Random-capable
corpora retain 6,144 ordinary-None bindings; random paths are not exhaustive.
Identity, lazy iteration, fresh options, failure prefixes, hidden template
spans and live recorder faults pass; a real extra-character size fault is
rejected and its modified program executes all eight rows. All 951 production
files remain unchanged. The net twenty-two test lines leave tests/source
115,792/115,820 and twenty-seven strict spare lines. LaserFuck's full accounting
review remains pending: 27 accounting rows and all 117 completion rows stay open.


LaserFuck's independent flat tape/beam oracle now checks all ten workspace
components. All 3,477 records, cap 48, three post-halt steps and three old
controls remain; ten component erasures are rejected. Before/after captures
match at all 19,550 boundaries. Prepared execution retains the scripted paths;
VM/debugger each check 19,493 boundaries using independently predicted seeded
draws, including actual provider calls and retained capture/cycle hashes.

Thirty-six installed leaves pass on Python 3.12.11–final 3.15.0. Each version
runs all 3,477 seeded public records bounded and ordinary; 3,469 ordinary
None-provider records have prior finite certificates, with eight kept bounded.
Branch checks cover 6,954 records/39,043 boundaries, including skipped reads
and splits. The populated witness measures 29 written bits across nine mutable
components; second-start remains readonly. Actual capture overrides cover
144 masks, 36 reduced schemas and 40 readonly controls; twelve natural source
futures check start coordinates and fresh branching. Sixty physical writer
refusals, twelve provider refusals, four repeated-EOF and two public EOF routes
check partial state/output and manual retries. Twelve guarded children cover ten native/worker
parities and output-cap refusal/success. Random paths are not exhaustive.

All 951 production files remain unchanged. The permanent bridge adds exactly
twenty-seven test lines: tests/source are 115,819/115,820, with no strict spare
line. No existing case, assertion, control, node or cap is removed. Accounting
reviews still pending: 26; all 117 completion rows remain open.


Nope.'s completion row is closed on Python 3.12.11, 3.13.15, 3.14.7 and
final 3.15.0. Its source-independent two-state semantics retain exact one-bit
accounting. Per version, all 210 cases and five boundaries agree across raw,
prepared, VM and debugger routes: 4,200 captures, fresh siblings and immutable
histories. Twelve physical failure routes retain committed state and partial
output without retry; four real workers check step and output limits, and
five native entrypoints check UTF-8/gzip acquisition. Source-matched earlier
erasure, resource and semantic controls remain applicable. Current installed
persistence, CLI and retirement controls pass; backend analysis and proof
claims are inapplicable. The other 116 completion rows and 26 accounting
reviews remain open.

The same 951-file wheel passes 776 additional API/CLI leaves across 97 runtimes
and all four Python versions: 6,208 cases, 31,816 startup markers, 7,130 seconds
and a 19.82-second maximum against the unchanged 60-second leaf cap. This
closes that default-profile execution batch, not the remaining dialect,
accounting or catalog acceptance work.


Whitespace's independent oracle now checks all six workspace components.
All 549 cases, six syntax refusals, cap 48, post-halt steps and three original
controls remain; six erasures and a wrong-number control are rejected.
Old/new model results agree for every original case. A literal populated
witness measures 23 written bits; independent ASCII decimal folding adds
five long-input/refusal cases without changing the host digit policy.

All 44 installed leaves pass on Python 3.12.11–final 3.15.0. Per version,
raw, prepared, VM and debugger each match 7,512 original-corpus boundaries;
all 549 public cases run bounded and 548 independently finite cases run
ordinary. One hundred twenty capture-mask trajectories include 24 constructor-None
and 24 consistent reduced schemas. Sixteen physical writer, four provider
and four repeated-EOF trajectories retain failure phases and retry history;
fourteen real workers cover selected traces, syntax, step and output limits.
The numeric cases reach 33,243 written bits. Interpreters and generators stay
unchanged; no collected nodes are added. Whitespace's bounded accounting
review is complete; full
parser/public-fault acceptance remains open. Accounting reviews pending: 25;
116 completion rows remain open.


Caballo now refuses a zero branching-outcome budget before evaluating a
transition, including naturally halted states. The existing done-flag test
retains its original case and adds zero/one-budget controls against a real
empty-program step, with zero-budget evaluation forbidden. No node is added.
All 687 source/input records and 703 weighted tickets match before/after on
raw and declared prepared routes: 1,406 paired runs and 10,316 boundaries.
All 30,948 positive-budget outcomes agree; 10,316 zero-budget calls refuse.
A stale-successor mutant is detected. Caballo's accounting review remains
pending; the 25 accounting and 116 completion counts are unchanged.


Caballo's independent AST/path/frame oracle now checks all four workspace
components. All 687 original records, 703 weighted tickets, cap 256, old
assertions and None return remain. Pure model extraction preserves 5,805
modeled boundaries and twenty supplemental cases; twelve permanent controls
reject semantic, capture, draw-bound and Boolean/integer faults.

Forty installed leaves pass on Python 3.12.11–final 3.15.0. Per version,
raw/prepared cover 1,406 trajectories and 10,316 boundaries; seeded VM and
debugger each cover 1,374 trajectories and 9,790 boundaries. All 687 records
run bounded with default seed zero, ordinary with seed one, and ordinary
with a genuine None provider checked against independently computed finite
alternatives. Eighty capture-mask trajectories include readonly-cursor
controls; populated witnesses measure 29/35/37/30 written bits.

Twenty-eight constructor refusals, method/physical writer phases, provider
refusals, prepared siblings and a readonly-program future control preserve
state, IO and retry history. Seventeen real workers check fifteen selected
parities and two output limits. Raw host-digit limits stay distinct from
unverified public huge-format normalization. The permanent oracle adds 874
lines with no collected nodes; the 951-file runtime wheel is unchanged.
Caballo's bounded accounting review is complete; general grammar, public
fault matrices and full branching acceptance remain open. Accounting reviews
pending: 24; 116 completion rows remain open.


Bleh's independent lazy-heap/continuation oracle checks all six workspace
components. All 118 cases, 91 original families, caps 128/256/768 and eight
original controls remain. Oracle-only control-label renaming preserves all
2,605 typed model boundaries byte-for-byte; no collected nodes are added.

Sixty installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared, VM
and debugger each match 2,605 boundaries and three constructor refusals;
public execution covers 118 bounded and 116 independently finite ordinary cases.
Each version checks 120 actual capture masks, eight physical writer and four
provider histories, readonly-code corruption and 2,605 snapshot round trips.
The 33-bit anchors and 16,021-bit written-state peak match the independent model.
All 118 cases execute in real workers; constructor/limit and proof controls
bring the total to 127 children per version. The saved reader and 18 corruption
controls pass. The wheel is pinned to `19bc9784c`; runtime/support code still
matches that revision. The interpreter and generator are unchanged.

Bleh's bounded accounting review is complete. General grammar, arbitrary
providers and broader completion remain open. Accounting reviews pending: 23;
116 completion rows remain open.


The dialect matrix completes all 372 leaves on Python 3.12.11–final 3.15.0:
50 API and 43 CLI selectors per version across eight runtimes. All one-input
tables retain 2,976 truth rows through generation, binding, persistence and
execution. Typed settings distinguish defaults, explicit empty values and
overrides; Line retains scale two. Fatal startup guards verify 14,288 process
markers and 13,916 spawns: 12,208 CLI children and 1,708 workers.

The independent reader and ten full-matrix corruption/relocation controls pass;
seven earlier pricing-reader controls remain. Active leaf time is 3,331.62s,
maximum 24.13s against unchanged 60s caps. This evidence is pinned to wheel
`75c312bb9`; accounting and whole-catalog completion remain open.


What!?'s independent dual-tape oracle checks all five workspace components.
All 142 original vectors, six manual assertions and cap 128 remain; 34 cases
extend the corpus to 176. The existing fast owner passes in 0.33s; no collected
nodes are added.

Forty-four installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared,
VM and debugger each match 1,969 boundaries and ten constructor refusals.
Each version checks 352 public calls, 100 actual capture masks, 64 native and
30 public fault histories, eight readonly-metadata future controls and four
typed-result controls. Twenty-one real workers cover twenty parity pairs and
an isolated output limit. The independent written-state peak is 2,050 bits.

The saved reader, relocation and sixteen corruption controls pass. Four real
certification imports fail fatally under the 952-file startup guard; the new
Fackward certification module is present and hashed. The wheel is pinned to
`8e4e4632b`; active leaf time is 66.21s against unchanged 60s caps. The interpreter
and generator are unchanged. What!?'s bounded accounting review is complete;
general grammar, arbitrary providers and broader completion remain open.
Accounting reviews pending: 22; 116 completion rows remain open.


Line's independent stroke graph derives the four and ten frames of its two PNG
fixtures. All 92 original cases, cap 1000, three old controls and 84 compiled
complements remain. An existing medium owner carries the new workspace checks;
the original fast hook is byte-identical, with no collected nodes added.

Forty-eight installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared,
VM and debugger each match 6,821 boundaries, including readonly metadata, visited
zeros, IO and held captures. Each version checks five component erasures, six
retry histories, 100 actual capture trajectories, 24 manual fault histories,
16 repeated EOF histories and twelve public failure histories. Public execution
checks 92 ordinary and 92 bounded results; 92 real workers retain their outcomes.
The independent written-state peak is 30 bits, with populated 14/25-bit anchors.

The saved reader, relocation and seventeen corruption controls pass. All 368
children and 416 startup markers reconcile under the 952-file guard. Active leaf
time is 198.51s against unchanged 60s caps; the wheel is pinned to `8e4e4632b`.
The interpreter and generator are unchanged. Line's bounded accounting review
is complete; other rasters, scale-two metadata and final lifecycle/transport
reconciliation remain open. Accounting reviews pending: 21; 116 completion rows
remain open.


Flowchart's independent declared layouts check all eight workspace components,
readonly grid metadata and held captures. All 153 original vectors and caps
64/8 remain; fifteen cases extend the corpus to 168. The unchanged fast owner
is byte-identical; an existing medium owner retains all 64 old rows and adds
the accounting checks. No collected nodes are added.

Sixty installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared, VM
and debugger each match 3,666 boundaries and a 702-bit written-state peak. Each
version checks 334 public results, 160 actual capture profiles, 32 manual and
sixteen public fault histories. All raw snapshots round-trip; 168 corpus workers,
ten consumer workers and three proof workers run per version.

The saved reader, relocation and twenty corruption controls pass; result-counter
mutations also change saved stdout. All 724 children and 784 startup markers
reconcile under the 952-file guard. Active leaf time is 478.13s against unchanged
60s caps; the wheel is pinned to `8e4e4632b`. The interpreter and generator are
unchanged. Flowchart's bounded accounting review is complete; general layouts,
arbitrary providers and broader completion remain open. Accounting reviews
pending: 20; 116 completion rows remain open.


Deadfish, HQ9+, CARP and AddSubJump completion rows are closed on Python 3.12.11,
3.13.15, 3.14.7 and final 3.15.0. Their independent corpora retain
1,823/395/1,803/194 cases and 13,456/4,491/16,517/1,028 boundaries; step caps
remain 64 for the first three and 16 for AddSubJump. Raw,
prepared, VM and debugger captures, fresh siblings and held histories agree;
physical IO failures and selected real workers retain committed state and
partial output. Existing owners retain all 11/9/10/8 fault controls.

The unchanged API/CLI/persistence consumer cases pass in the current wheel;
all 952 packaged files match the frozen source. Exact certification-import
refusals, source-qualified retirement checks and relocated saved readers pass.
Backend claims are inapplicable to Deadfish and HQ9+. CARP's ten and
AddSubJump's sixteen named size/resource/scaling owners reuse source-identical
CI at `5f4dfb781`:
3.12/3.13/3.15 passes are explicit; 3.14 passes are source-derived from complete
successful receipts and the absence of skip/xfail paths. Scope remains the
declared witnesses. Evidence: `notes/migration-completion-batch-1`; shared
retirement scope: `notes/retirement-imports-8e4e4632b`.
Accounting reviews pending: 20; 112 completion rows remain open.


Declared certification scopes are reconciled for 114 Boolean backends: 259
source anchors and 1,499 distinct finite owner nodes retain their named
arities, units, exactness and construction on CI run 42682388228 (5f4dfb781).
Python 3.12, 3.13 and 3.15 have explicit PASS outcomes, including the four-node
serial batch containing Malbolge n=2. Python 3.14.10 is SOURCE_DERIVED_PASS:
all owner nodes finished without failure, and pinned owner, marker, fixture
and reachable runtime sources exclude skip/xfail paths; raw outcome labels
remain unrecorded. Nine qualitative scaling cells retain their existing
named construction or explicit lower-bound/cap argument, separately source
reviewed; finite probes do not supply their asymptotic proof.

Deadfish, HQ9+ and Nope. have no Boolean backend, so these generator claims
are not applicable. Runtime-isolation and declaration scopes remain separate.
This reconciliation strengthens no declared claim and closes no language
completion, lifecycle/accounting or whole-catalog retirement row.


Canonical retirement controls pass in 32 installed leaves on Python
3.12.11–final 3.15.0: 59 cases per version, 236 overall, with every setup, call
and teardown passing. All 42 copied definitions retain their original bodies
and decorators, apart from two exact fixture-import prebindings. Actual pytest
9.2.0, timeout 2.4.0 and four dependencies match six locked wheels and 493 payload
members. The existing fast/medium duration policy is unchanged.

The 952-file guard reconciles 36 markers and four actual pickle children. The
worker-request controls execute the real worker in the parent; they add no
process claim. Active leaf time is 38.30s against unchanged 60s caps. The saved
reader, relocation and 23 corruption controls pass; repeated metadata freezes
are byte-identical. The wheel remains pinned to `8e4e4632b`.

Two rejected evidence revisions remain: version-dependent AST formatting and
Python 3.15's explicit import-laziness field. Complete typed field encoding now
retains that field, supplies integer zero for older eager-import grammar and
rejects lazy or Boolean flags. All 84 original/adopted definition hashes match
on all four versions. This verifies the named canonical controls; all-language
retirement and the twenty pending accounting reviews remain open.


Subleq retains the existing independent prefix oracle and all 327 invocations,
cap 200 and three post-halt idles. Rich observations add all three workspace
components, visited zeros, full IO and held captures. An existing medium owner
retains its old body; no collected nodes or duration limits change. Its complete
335-constructor placement is checked in the repository, separately from installed
traces; certification-only assertions remain excluded by the fatal barrier.

Eighty installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared, VM
and debugger each match 15,290 boundaries, two constructor refusals, 126 active
failures and 64 live cap-200 runs. Each version checks 327 bounded and 263 finite
ordinary public calls, all 327 cases in real workers, 72 capture profiles and
sixteen failure/retry histories. All raw snapshots round-trip. The written-state
peak is 505 bits; separate populated 36/56-bit witnesses detect genuine losses.

The saved reader, full relocation and 25 corruption controls pass; counter
mutations also change saved stdout. All 1,352 children and 1,432 startup markers
reconcile under the 952-file guard. Active leaf time is 700.09s, maximum 25.23s
against unchanged 60s caps; the wheel remains pinned to `8e4e4632b`. Native and
generator code are unchanged. Subleq's bounded accounting review is complete;
arbitrary syntax, host allocation and provider universality remain open.
Accounting reviews pending: 19; language completion is reconciled separately.


Ninety-two more completion rows are closed at their declared finite witness
scopes. The 92 reviewed languages have exact semantic-admission owners in CI
run 42682388228 (`5f4dfb781`): baseline cases pass without skips or errors, and
live output faults reach assertions. Eighty-nine complete owned packages and
their shared implementation, oracle and fixture dependencies match that source.
Flowchart, Line and What!? instead retain their newer installed corpus packets.
Python 3.12/3.13/3.15 have literal PASS records; 3.14 remains explicitly
SOURCE_DERIVED_PASS from finished journals and closed owner/fixture control flow.
The combined source/evidence reader and twelve corruption controls pass.

Declared preparation, VM/debugger histories and successful API/CLI paths reuse
source-qualified records. The two changed shared exception paths match the
current 112-call constructor/IO cohort; the 236 canonical protocol cases and
four-version 117-runtime catalog supply current installed integration checks.
All 38 retirement families have explicit joins: 37 applicable control scopes
and unchanged-format N/A. The final whole-migration referee remains pending.

Alight's permanent 117 scalar witnesses and retained 568-case archive remain
separate scopes. Smallfuck retains 194 programs across three stdin values and
six controls. Suffolk retains its periodic certificates and EOF witnesses;
default halting consumer rows do not replace them. Grapheme's existing frame
model already covers calls, so its stale calls-pending label is removed.
Six gaps have fresh complete semantic-admission passes on Python 3.12.11,
3.13.15, 3.14.7 and final 3.15.0. BrainIf adds seven long-decimal/parser cases;
Decleq writes, prints and overwrites a 4,097-cell store; Freestajlo populates
functions and nested calls. Fish populates directions and an expanded grid,
Modulous counts two real provider draws, and Super SNUSP changes row/heading.
Independent boundary and charge checks include populated-component erasures.
Every original case, fault, assertion and step cap remains; no nodes are added.
The last three source-verifier profiles take 22.63s within their 60s cohort cap.
Their 952 production-file hashes match the installed wheel; these source runs
retain their own provenance separately from guarded installed receipts.
Evidence: `notes/migration-closure-batch2`. Completion rows: 97 closed, 20 open;
19 accounting reviews remain pending.

Forbin retains all 78 original definitions and adds an independent 343-record
bounded accounting model: 69 base/extra cases, all 256 byte inputs, seventeen
error records and the original finite closure-loop tail. Existing caps and
three post-halt idles remain unchanged; the selected medium owner retains its
old body, with no new nodes or duration changes.

Forty-eight installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared,
VM and debugger each match 2,453 boundaries, eight constructor refusals and
1,135 successful steps; the written-state peak is 144 bits. Each version checks
343 bounded and 343 ordinary public calls, nineteen representative workers,
four worker caps and twelve physical failure/retry histories. Ten actual
capture erasures, two typed IO controls, two readonly futures and six touched
raw-cycle mutations are detected. Full workspace envelopes round-trip; native
closure-bearing cycle snapshot serialization remains open.

The saved reader, full relocation and 23 corruption controls pass; result
mutations also change saved stdout. All 92 children and 140 startup markers
reconcile under the 952-file guard. Active leaf time is 89.55s, maximum 5.05s
against unchanged 60s caps. The fatal proof-import selector exits 87: installed
permanent coverage is the new hook, with zero whole-owner credit; the required
repository gate covers the preserved original tests. Native and generator code
are unchanged. Forbin's bounded accounting review is complete; arbitrary
grammar, raw closure persistence and universal accounting remain open.
Accounting reviews pending: 18; language completion is reconciled separately.

Fargo retains all 266 existing records and cap 64. Independent expected plans
are compiled once per row; every actual capture remains fully compared at every
boundary. The old fast owner is unchanged. Two existing medium owners retain
their old bodies and cover 96/170 accounting cases; no nodes or bands change.

Sixty-four installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared,
VM and debugger each match 10,398 model observations and a 180,002-bit peak.
Each version checks 266 bounded and 264 finite ordinary public calls, twenty
representative workers, four cap workers and three proof workers. All supported
raw snapshots round-trip: 10,391 across 266 cases. Eight constructor provider
refusals and two prepared writer histories preserve their actual phases. Twenty
actual capture omissions and twenty positives fire across all four routes.
The complete installed medium owners make 388/745 constructor attempts; the
original operator owner separately makes 384.

The strict saved reader, full relocation and 24 corruption controls pass; result
mutations also change saved stdout. Its exact argv order was corrected to the
recorded commands without changing evidence. All 108 children and 172 startup
markers reconcile under the 952-file guard. Active leaf time is 156.34s; all
leaves retain 60s caps. Native and generator code are unchanged. Fargo's bounded
accounting review is complete; arbitrary grammar, host allocation and provider
universality remain open. Accounting reviews pending: 17; completion joins are
tracked separately.

Boolfuck retains all 695 original oracle invocations and adds nineteen existing
byte, hint and lifecycle cases. The independent transition engine is unchanged;
its final observation wrapper exposes all state. Bounds remain 200, the three
old lifecycle limits remain 100, and manual prefixes keep their exact bounds.
The existing medium owner retains its old body; no nodes or bands change.

Fifty-six installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared,
VM and debugger each match 14,172 boundaries, three constructor refusals,
11,451 successful steps and 41 live cap-200 runs. All three workspace parts,
full IO, readonly source/brackets and retained captures are independently
checked. The corpus peak is 24 bits; separate populated 17/19-bit witnesses
exercise every component. Each version checks 714 bounded and 673 finite
ordinary public calls, 72 actual capture masks and 28 physical fault histories.
A populated ones freeze has zero bit loss and remains a detected state error.
Full-byte writer refusal is retryable; terminal partial-flush refusal occurs
after committing the halted state and does not retry on idle calls.

All 14,172 raw snapshots round-trip per version. Twenty-four representative
workers, four cap workers and three proof workers produce 124 children and
180 startup markers overall under the 952-file guard. The strict saved reader,
full relocation and 25 corruption controls pass; result mutations also change
saved stdout. Active leaf time is 136.13s; 60s caps remain unchanged. Native and
generator code are unchanged. Boolfuck's bounded accounting review is complete;
arbitrary syntax, allocation and provider universality remain open. Accounting
reviews pending: 16; completion joins are tracked separately.

Packlang retains all 1,132 existing scalar cases and cap 48. Its four old
independent engine functions and ordered case recipe are unchanged. Rich
observations add all three workspace parts, full IO, readonly program metadata,
held captures and complete raw cycle keys. The existing medium owner retains
its two literal-policy rows; no nodes, bands or bounds change.

Forty-eight installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared,
VM and debugger each match 9,167 boundaries, 4,645 successful commands and
three active failures; the corpus peak is 126 bits. A separate 122-bit witness
writes all three components. Each version checks 1,132 bounded and 1,132
ordinary public calls, 21 representative workers, four cap workers and twelve
physical refusal/retry histories. Twelve actual capture erasures, four typed IO
controls, four readonly futures and a typed Result control fire. Every raw
cycle snapshot round-trips. The complete original hook makes 1,135 constructor
attempts; the complete installed medium owner makes 1,134.

The strict saved reader, full relocation and 24 corruption controls pass; result
mutations also change saved stdout. All 100 children and 148 startup markers
reconcile under the 952-file guard. Active leaf time is 130.88s, maximum 5.97s
against unchanged 60s caps. All package bytes are checked before and after each
leaf. Native and generator code are unchanged. Packlang's bounded scalar
accounting review is complete; arrays, calls, structured control and host
expansion remain open. Accounting reviews pending: 15; completion joins remain
separate.

Nine populated accounting witnesses pass complete registered semantic owners on
Python 3.12.11, 3.13.15, 3.14.7 and final 3.15.0. Quassaunt retains 164 cases plus
14 named traces; Smu retains 1,541 plus eight; Shakespeare covers six. Circuit
Diagram retains 686 gate/input cases plus clock and output-failure witnesses;
Inject checks 30 old cat inputs plus eighteen cases; Parenthesys retains 57
loops plus four focused traces. Their caps remain 64/64/32/8/64/256.

Unlambda retains 1,130 runtime cases and seven constructor sources, application
fuel 128 and native cap 256; six focused traces cover delay, continuations and
IO. INTERCAL retains 489 scalar cases at cap 16, three constructors at 64, four
rich traces at 32 and a physical output failure. Rubic retains 55 cases, seven
focused traces and a writer failure at cap 80. Every declared component has
independent state/charge, read/EOF, capture-history and sibling observations,
with populated erasures. Original cases, assertions, faults, bands and nodes
remain; native and generator code are unchanged.

Two strict timing failures were fixed without changing budgets. Unlambda's
1.10s fast-band overrun is removed by observing resources during its original
native execution. Fargo's medium-band overrun is removed by equivalent explicit
comparison loops: 739,737 live capture comparisons agree across 266 cases and
10,398 boundaries; fourteen forced-hash field corruptions are rejected by both
versions. Fargo's two exact accounting medium owners separately pass all four
Python versions. Its declared semantic owner does not reach these helpers and
is not credited for that execution. Nine models have 36 actual profile joins;
Fargo adds four distinct named-owner joins. Source-verifier provenance remains
separate from unchanged guarded installed runtime receipts.

Subleq, Forbin, Fargo, Boolfuck and Packlang close their completion rows using
accepted accounting packets, current source qualifications and forty actual
historical API/CLI success leaves (320 finite rows). Those successes retain their
original wheel provenance; current catalog, constructor, canonical protocol,
retirement and failure joins remain separate. Fargo's changed test comparator
has an explicit execution-qualified exception. Forbin's native closure-cycle
key transport remains unsupported; canonical workspace envelopes round-trip.
Packlang retains its finite scalar scope. Grammar, provider, host-allocation and
raw-closure limits remain explicit. Evidence: `notes/migration-closure-batch3-final`.
Completion rows: 111 closed, six open; six accounting reviews remain pending.
The combined branch referee receipt is retained with this batch; the final
whole-migration referee remains pending.

Brainfuck retains all 1,670 original oracle invocations and seven existing
tail/hint cases. The independent transition engine is unchanged; its final
wrapper exposes full allocated tape and control state. Bounds remain 200,
with the old wrap-tail's exact 257 limit and three post-halt idles. The existing
medium owner retains its old body; no nodes or bands change.

Fifty-six fresh installed leaves pass on Python 3.12.11–final 3.15.0. Raw,
prepared, VM and debugger each match 29,492 boundaries, seventeen constructor
refusals, 225 active failures, 23,569 successful steps and 89 live cap-200 runs.
All four workspace parts, full IO, readonly code/brackets and retained captures
are checked; the corpus peak is 26 bits. Each version checks 1,677 bounded
public calls, 1,588 finite ordinary calls, 96 actual masks and sixteen physical
fault histories. The ordinary API is compiled: its IO/Result checks provide
zero raw-history boundaries. The installed mask witness is 16 bits; the
separate 14-bit native witness belongs to the repository owner.

All 29,492 raw snapshots round-trip per version. Twenty-four representative
workers, four cap workers, four ordinary workers and three proof workers yield
140 children and 196 startup markers overall under the 952-file guard. The
strict saved reader, full relocation and 28 corruption controls pass; result
mutations also change saved stdout. V1's empty-views assertion failed on the
real VM; V2 derives the declared ind/ptr/tape text and pointer independently.
All 56 leaves were rerun, with 172.70s active time and unchanged 60s caps. Native
and generator code are unchanged. Brainfuck's bounded accounting review is
complete; arbitrary syntax, allocation and provider universality remain open.
Accounting reviews pending: 5; completion joins remain separate.

Streetcode retains all 511 original one-row cases, the existing junction and
four constructor refusals, with caps 48/17 and three post-halt idles. The old
fast oracle and medium owner body remain; five helpers add no nodes or bands.
The bounded model covers these rows and junction, not arbitrary geometry.

Sixty-four installed leaves pass on Python 3.12.11–final 3.15.0. Raw, prepared,
VM and debugger each match 8,182 boundaries, 6,852 successful steps, 212 halts
and 182 failures including four constructors. All six workspace components,
full IO and retained captures are checked; the measured peak is 113 bits.
Each version checks 516 bounded public calls and 398 finite ordinary calls;
118 ordinary cases are explicitly inapplicable. Compiled graph and memo data
remain readonly sidecars with changed-future controls.

The packet checks 140 populated erasures, four honest stopped no-ops, four
canonical positives, twenty physical fault histories and four repeated EOF
histories. Two prepared siblings retain independent histories. Representative,
cap and proof workers yield 124 children and 188 startup markers overall under
the 952-file guard. The whole original hook constructs 518 machines; the whole
medium owner constructs 526. Its repository run passes in 1.67 seconds.
The strict saved reader, relocation and thirty corruption controls pass;
stdout is changed alongside result mutations. All 64 leaves took 125.71 seconds
with unchanged 60-second caps. Native and generator code are unchanged.
Accounting reviews pending: 4; completion joins remain separate.

Chicken retains its 102 original case families and all 128 existing reference
cases, unchanged individual caps and three post-halt idles. The independent
cell/instruction model checks 1,047 modeled boundaries, including three
constructor refusals; each native route checks the remaining 1,044. All four
workspace parts, full IO, captures and raw keys are checked; the measured
corpus peak is 221 bits. Unified code/data cells remain mutable. Input cursor
is readonly after construction; stopped-state erasures include honest no-ops.

Sixty installed leaves pass on Python 3.12.11–final 3.15.0. Each version checks
128 bounded and 127 finite ordinary calls, 72 workspace masks, forty readonly
cursor controls and 32 physical histories. Sixteen constructor failures retry
the same port; sixteen terminal writer failures commit state before raising
and cannot retry. All 1,044 raw snapshots round-trip. All 128 bounded workers,
eight cap/ordinary profile workers, three proof workers and two children from
each complete old/new owner yield 572 children and 632 startup markers overall.
The whole original owner constructs 107 parent machines; its expanded version
constructs 245. The existing fast owner and all original assertions remain;
no nodes, bands, native or generator code change.

The first 60-run packet failed the reader's exact map-path check despite
identical map bytes. The launcher now uses the frozen bundle's map path;
all sixty leaves were rerun in 155.37 seconds with unchanged 60-second caps.
The strict reader, relocation and 23 corruption controls pass, including
coupled stdout mutations. Allocation beyond the model's existing 512-cell
refusal, arbitrary parser/numeric behavior and provider universality remain
unclaimed. Accounting reviews pending: 3; completion joins remain separate.

Malbolge retains all 27 original greeting cases and their fault control, with
five focused cases, cap 128 and three post-halt idles. Its independent model
checks 510 observations: 506 native captures and four constructor refusals,
with 26 halts and two live caps. All six workspace parts, full IO, raw keys,
charge and retained captures are checked. Logical memory has 59,049 words;
accounting pages and cycle-key chunks remain distinct representations.

Sixty-eight fresh installed leaves pass on Python 3.12.11–final 3.15.0 under
the unchanged 952-file guard. Each of four wire leaves replays all 32 cases
and 506 captures; only transport is partitioned into [0,128), [128,256),
[256,384), [384,506), covering every capture exactly once per version.
Two same-factory prepared siblings retain independent full histories; four
physical failure histories retain exact state, IO and charge. Six populated
erasures remain live. The 128 real workers and eight separate forbidden-import
controls yield 204 startup markers overall; proof imports exit 87 after valid
startup. No synthetic worker or collected-node credit is claimed.

The complete existing medium owner executes the 32-case accounting hook on
all four versions within its unchanged five-second band, using real pinned
pytest wheel payloads. The registered semantic owner reaches only the old
27-case greeting and receives no new accounting credit. No nodes, caps, bands,
native or generator code change.

The saved reader, full relocation, 26 original corruptions and two separately
bound wire-window corruptions pass. The old/new
comparison predicates agree on 2,551 actual pairs, including eleven negative
controls. V1's bounded timer failure and V2's whole-wire timeout remain retained;
neither supplies V3 outcome credit. Evidence: `notes/malbolge-accounting-final`.
Finite corpus accounting is complete; arbitrary grammar, allocation and provider
universality remain unclaimed. Accounting reviews pending: 2; completion
reconciliation remains separate.

Object disoriented retains all 376 original normal cases and five constructor
sources, cap 512 and three post-halt idles. Forty-eight installed leaves pass
on Python 3.12.11–final 3.15.0. Each native route matches 16,112 boundaries,
14,662 successful steps and 27 active failures; the corpus peak is 199 bits.
All six workspace components, IO, readonly compiler data, retained captures
and complete raw keys are checked. A populated all-six witness costs 47 bits.

Raw/prepared syntax checks attempt five constructors. VM/debugger and public
APIs reject `dmain.orzzz` during path preflight, before IO or construction;
the other four reach constructors. Worker receipts prove per-source child
counts 1/1/0/1/1. This corrects V2's failed 26-child assumption without crediting
a parent refusal as a constructor. Each version checks 381 bounded and 381
ordinary public calls, 24 populated erasures, four readonly-future controls,
four typed-IO controls, one typed-result control and sixteen physical histories.
Two same-factory siblings retain complete independent state histories.

All 16,112 raw snapshots round-trip per version. Twenty-one normal workers,
four syntax workers and four cap/profile workers per version yield 116
children and 164 startup markers overall under the 952-file guard. The exact
old hook constructs 384 machines; all 23 complete medium-owner parameters run.
The saved reader, relocation and 28 corruption controls pass; result edits
also change saved stdout. All 48 leaves take 485.88 seconds at unchanged
60-second caps. No nodes, bands, native or generator code change. Arbitrary
syntax, allocation and providers remain unclaimed. Accounting reviews pending:
1; completion joins remain separate.

Packlang now compares every retained capture/key value and original hash at
each later boundary. Genuine old-frame `cached_hash` corruptions, including
0/False aliasing, pass the old hash-only check and fail the stronger check;
canonical/restored positives and two same-factory histories pass. The existing
medium owner constructs 1,140 machines, retaining its original body and all
1,132 cases at cap 48. Expected-only plans reuse scalar shapes; every actual
field/type is reread. V3–V5 Python 3.14 timing failures remain recorded; V6
passes alone in 4.23 seconds against the unchanged five-second limit.

All 48 fresh V6 installed leaves pass in 123.22 seconds. Their saved result
payloads match V3 across all 48 leaves, excluding volatile guard PID inventories.
The strict reader, two relocation positives and 34 negative controls pass.
The 9,167 raw boundaries, 126-bit peak, 100 children and 148 startup markers
remain unchanged. This strengthens the existing finite scalar scope; broader
Packlang syntax and host behavior remain unclaimed.

thisthat retains all 66 original cases: 63 Cat inputs at cap 256, truth 0/1
at cap 200 and Kolakoski at cap 4,000. One LF case at cap 32 supplies the
seventh written-component witness. An independent box-rule model checks all
seven workspace parts, readonly grids, full IO, typed raw keys, retained values
and original hashes. Raw/prepared routes use FirstDraw(0); VM/debugger/public
and workers use Seeded(0). The two policies have separate predictions.

Each native route checks every current boundary and final retained value.
All non-Kolakoski histories are complete. Eight origin windows per route
partition all 8,006,001 Kolakoski history pairs; each window also checks all
4,001 current/wire boundaries and final holds. Nine complete existing medium
owners retain their bodies and decorators, adding two-statement tails.
Their permanent hook checks all 67 cases and final holds without new wire
work; the external cohort owns full transport and historical comparisons.

All 192 installed leaves pass on Python 3.12.11–final 3.15.0, with 296 real
children and 488 startup markers under the unchanged 952-file guard. Source
qualification retains 38 V4 nonpure leaves, five V5 leaves and 149 V7 leaves;
each keeps its original argv, nonce and receipts. Earlier failed probes and
the replaced V4 pure result remain archived without acceptance credit.
The final proof checks full independently predicted branch graphs, native/
worker equality and typed wire; branching decisions correctly have no command
count. The strict reader, two relocation positives and 34 corruption controls
pass. No nodes, bands, caps, native or generator code change. General grammar,
default-entropy histories and provider universality remain unclaimed.
Accounting reviews pending: 0; completion reconciliation remains separate.

All 117 language completion rows and 114 backend scopes are reconciled at their named finite evidence bounds. All 38 retirement families retain current source/consumer/control joins (37 applicable, unchanged-format N/A). Final production 952-file membership/hashes and required corpus/execution/timing/resource-size/referee receipts qualify the retained integrated wheel. Python 3.14 source-derived outcomes remain labelled; canonical version 1 remains supported. Arbitrary grammar, provider universality, host allocation and unsupported raw closure persistence are not newly claimed. The eight roadmap workstreams meet their declared scoped acceptance.

Evidence: `notes/migration-final-reconciliation`; required `just test` passes on the exact 2,250 final source inputs. The full run retains its sandbox process-listing failure (17,248 passed, 25 skipped); that same lifecycle test passes outside the sandbox, giving 17,249 passing outcomes across the two runs. No failed full-command result is relabeled.
