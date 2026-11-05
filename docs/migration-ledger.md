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
| Source-returning `generate` / `instantiate` defaults | Artifact API | Public callers, CLI, scripts, docs, tests | Program/template artifacts and explicit `.source` |
| `_Tagged` | Artifact API | Source guards, settings, persistence, generator adapters | Explicit artifact metadata |
| `_Template` | Artifact API | Instantiation, layout, serialization | `TemplateArtifact` and bindings |
| `tagged.source_adapter` and artifact-to-tagged round trips | Artifact API | Source loading, generation and execution boundaries | Direct artifact/source handling |
| `_recover_template` and plain-string binding inference | Artifact API | Legacy instantiation callers | Declared template bindings |
| Tagged-source `load_program` | Persistence | CLI, scripts and saved-program callers | Canonical artifact loading |
| Temporary `esolangs.compat` API | Artifact API | Callers moved there by the in-flight defaults migration | Canonical API; delete the facade after migration |
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
| Snapshot-as-workspace fallback | Accounting | Benchmarking, proof drivers and custom VM callers | Versioned semantic accounting adapters |
| Legacy worker-field defaults | Results | Retired; complete requests and explicit success/error observations; omission controls in `tests/runtime/test_worker_results.py` | Explicit canonical fields, including unavailable observations |
| Superseded serialization decoders/converters | Persistence | Persisted data and fixtures, if a format is superseded | One-time data migration, then remove the obsolete code |

For each family, locate consumers before changing it; close the row only after
those consumers migrate, the implementation disappears and a regression check
rejects its reintroduction. A version number or a new facade is not retirement.
Current version-1 serialization is not obsolete solely because its version is 1.

The 2.0 defaults are artifacts and execution results. Output-only `compat.run`
and public `run_result` aliases are retired; `tests/api/test_run_results.py`
rejects their return. Source adapters in `esolangs.compat` remain open.

Benchmarks retain artifacts through generation, binding and execution. Source
size and hashes read `.source`; caller checks fence off the temporary facade
for all 114 backends. Release checks, audit replay, documentation and scaffolding
also use artifacts; replay loads preserve explicit bindings. Other source-returning
callers remain open.

Example builders return runnable artifacts through layout, binding and scaling.
Regeneration writes them through `save_program`; the example builder no longer
converts artifacts into tagged source.

Shared generation, VM-row and proof-measurement helpers retain artifacts through
execution. Size callbacks and native sample fixtures read explicit source after
binding. Shared support modules no longer call the source facade; remaining
owned test callers still require migration.

Accounting and analysis rows require owned witnesses, not just a declared hook
or a recognized helper name. Certification needs an installed-package/lazy-import
acceptance audit after the active separation work lands. Storage policy needs
its priced comparison and explicit decision. These remain open even where an
implementation pilot already passed.

Accounting now has sixty explicit or inherited semantic adapters; 57 language
rows still use snapshot accounting. Declarations do not close lifecycle,
storage-policy or catalog-wide acceptance requirements.

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

The logical-store batch declares fifteen further models, flattening persistent
RAM and continuation spines and freezing unordered stores. Bitwise Cyclic Tag
counts live data and its answer, excluding the deleted-prefix storage cursor.
Read-only source tables and shell-only dump guards are excluded.

Boolfuck and Monotonic Boolfuck declare inherited bit-tape factories and debug
fields. Buffered byte flushing and monotonic reads stay unchanged.

Unary declares compressed-source preparation and inherited debug fields. Gzip
continues to decode in chunks, with zero-valued EOF and ordinary completion.
Cached and raster factories and retirement acceptance remain open.
