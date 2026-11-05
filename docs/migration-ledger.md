# Migration completion ledger

Declaration audit: `b66b55195`. [Language rows](migration-status.csv) cover all
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
| `registry.GENERATORS` | Registry | Generator lookup consumers | Descriptor/backend entrypoints |
| `languages.generators` facade | Registry | Scripts and generic/owned tests | Artifact API or direct owned generator imports |
| Unused generator-module descriptor re-exports | Registry | Legacy metadata consumers | Independent descriptors; retain constants actually used by emitters |
| Helpers' `AffineForm`, `affine_form`, `symmetric_outputs` re-exports | Analysis | Retired; callers migrated; negative export check in `tests/generators/test_symmetry.py` | `generation.algebraic` / `generation.lookup` |
| `runtime._result.ExecutionResult` shim | Results | Retired; imports migrated; negative import check in `tests/api/test_run_results.py` | `esolangs.results.ExecutionResult` |
| `_Machine` / `_for_run` discovery | Lifecycle | VM construction and machine traits | Declared preparation/factories and capabilities |
| Implicit completion entrypoint defaults | Lifecycle | Runtime descriptors and native runners | Explicit completion declarations |
| Dialect signature/default inspection | Lifecycle | Settings validation and metadata queries | Declared dialect schemas and defaults |
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

Accounting and analysis rows require owned witnesses, not just a declared hook
or a recognized helper name. Certification needs an installed-package/lazy-import
acceptance audit after the active separation work lands. Storage policy needs
its priced comparison and explicit decision. These remain open even where an
implementation pilot already passed.

Accounting now has ten explicit or inherited semantic adapters: Brainfuck,
Unary, Whitespace, Boolfuck, Monotonic Boolfuck, Deadfish, HQ9+, Nope, Home Row
and ROTfuck. The remaining 107 language rows still use snapshot accounting. These declarations
do not close lifecycle, storage-policy or catalog-wide acceptance requirements.
