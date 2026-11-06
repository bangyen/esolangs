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
| `registry.GENERATORS` | Registry | Retired; negative index checks in `tests/api/test_deferred_catalog.py` | Descriptor/backend entrypoints |
| `languages.generators` facade | Registry | Retired; callers use owned modules or backend declarations; negative import checks in `tests/api/test_deferred_catalog.py` | Artifact API or direct owned generator imports |
| Unused generator-module descriptor re-exports | Registry | Retired; owned metadata consumers use descriptors; all-backend checks in `tests/api/test_certification_capability.py` reject unused imports and `LANGUAGE` exports | Independent descriptors; retain constants actually used by emitters |
| Helpers' `AffineForm`, `affine_form`, `symmetric_outputs` re-exports | Analysis | Retired; callers migrated; negative export check in `tests/generators/test_symmetry.py` | `generation.algebraic` / `generation.lookup` |
| Helpers' `_parity_bias` and duplicate parity recognizers | Analysis | Retired; audited backends and REFRACTRAN ablations use canonical analysis; independent affine oracle and removed-export checks | `generation.algebraic.parity_bias` |
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
| Disconnected, mutable or draw-dependent branch verdicts | Results | Retired; constructor, wire and parent-decoder refusal controls preserve partial output | Immutable root-reachable graphs; run-specific termination decisions |
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
