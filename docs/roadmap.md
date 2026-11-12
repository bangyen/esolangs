# Roadmap

This page lists work that is still open. Finished work lives in the git
history; standing rules and proved limits are in [limitations](limitations.md).

## Generator linearity

For truth-table length `T`, target O(T) generation time and emitted size.
Generation includes input ordering and writing the program. Close a gap with
an executed, loop-less construction or a language-wide lower bound; measured
scaling alone does not prove linearity. Preserve totality, execution, and
workspace contracts.

The [scaling status](proofs/index.md#scaling-status) records current verdicts.
Edit `[resource_evidence.scaling]` and `[proof_status.audit]` in its
`language.toml` and run
`just docs` to update it. Proved limits remain
evidence, not optimization tasks.

- **Malbolge:** generation at seventeen inputs is open (2026-10-26).
  - *Why it is hard:* a table cell cannot carry eight
    address-independent meanings (window conflict graph: independence
    number 8, twelve classes); lockstep adjacent-cell reads reach 110 of
    512 triples a phase; the seven-meaning build's 1,994 gotos have 2.77
    cells each in the complement against a 3.6-cell annealed routing
    floor (certified at least 2.99).
  - *Ruled out:* hub substrates in the shipped and re-addressed
    geometries, marching and data-initialized decoders, threaded and
    streaming emission, membership dispatch, the permutation families;
    see [limitations](limitations.md) for eligibility, mechanism or
    measured rates.
  - *Reopen with:* a decoder variant whose word-mediated landing is
    realized in a full build that passes its gates (parity contract,
    per-row cases and a fresh census at the new window embedding, then
    placement and threaded rates inside the 9,897-cell complement), or
    new mathematics toward the 46,076 bits an impossibility proof needs
    beyond counting.
  - *Next lead (2026-10-27; tested 2026-10-31, refuted as stated):*
    the deposit half of the claim is true -- a lockstep fall-through
    sweep deposits a full word for exactly one source cell (a real
    296-cell program in the shipped interpreter, 94 of 94 deposits
    matching the stepper), against 21 cells measured for the shipped
    label phase.  The application half fails: the sweep placed 0 of
    the 74 shipped label cells in every configuration (best steered
    case 8-10), because a prescribed word at a prescribed cell is
    exactly what a sweep cannot do (still about 21 cells, as shipped).
    The stated residue count matches nothing measured -- `p` sweeps
    leave 36-41 of 94 residues uncovered, the `*` family 11, never
    29; steering completes coverage only through two windows or the
    k=5 family at 5 cells per word.  The five value bands are not
    there either: `p` deposits form two narrow bands, `*` deposits
    three rotation rails of width at most 31.  Nor does the lead move
    the paused reseed's economics: the deposits its first stage
    counts are few (12) and all prescribed, so the saving is at most
    about 240 cells against that stage's 1,113-cell kill line; any
    value is bulk seeding at the later stages' scale, through a
    redesign inside the paused loop.
- **Open mathematics:** Whether some 17-input Malbolge table has no program
  is open; the Malbolge row above is the constructive side
  ([proofs](proofs/index.md#malbolge-bound)).

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.

## Architecture migrations

The earlier incremental migrations met their scoped acceptance criteria, not a repository-wide
compatibility-removal goal. Independent descriptors cover all 117 languages;
artifacts, shared results, construction analyses, structured evidence and semantic
accounting are integrated at differing scopes. Existing line, case, duration and
purity gates remain in force.

Finish the rollouts below, then delete their legacy API, import and protocol
adapters. Price each batch within the standing compute budget. Review active
migration work before assigning overlapping changes. Public breaking changes
require a versioned cutover and caller migration; moving adapters into
`esolangs.compat` does not complete their removal.

1. **Artifact-first API cutover:** finish explicit source/file inputs and
   program/template results across the public API, CLI, scripts, docs and tests.
   Migrate callers, then remove tagged-string defaults, `_Tagged`, `_Template`,
   source adapters and plain-string template/binding recovery. Done when the
   canonical API retains metadata without hidden tags or inferred bindings,
   rejects unfilled templates, and no runtime caller needs the legacy facade.
2. **Declared interpreter lifecycle:** migrate all 117 descriptors to declared
   preparation, machine factories, completion/debugging capabilities and dialect
   schemas. Remove `_Machine`/`_for_run` discovery, implicit entry-point defaults,
   signature inspection and legacy constructor adapters. Done when every native,
   stepped and isolated route uses declarations, with equivalent traces, source
   steps, errors, dialect behavior, completion evidence and acceptable timings.
3. **Semantic accounting and storage:** extend versioned workspace models to all
   117 interpreters, separating logical resource state from cycle snapshots and
   Python storage. Preserve input progress, snapshot isolation and independent
   semantics; remove snapshot-as-accounting fallbacks. The priced
   [storage decision](migration-ledger.md) keeps immutable transition boundaries
   and captures, with backing stores chosen per interpreter. Done when
   every interpreter has exact resource witnesses and trace-equivalence checks.
4. **Generator analysis rollout:** audit all 114 Boolean backends for duplicated
   validation and decision, algebraic or lookup analysis. Use canonical analyses
   where applicable; record justified target-specific constructions and retain
   emitter-owned reads, layout and selection. Remove superseded implementations
   and migrate imports off compatibility re-exports. Done when each backend is
   accounted for, corpus bytes match, growth bounds hold and timing gates pass.
5. **Certification and evidence separation:** finish separating certification
   dependencies from runtime descriptors across the catalog. Replace remaining
   private-name discovery and duplicated claims with declarations and structured
   evidence. Done when installed runtime/catalog operations avoid certification
   implementations, documented claims execute, and independent oracles and live
   fault controls retain their coverage. Keep current budgets unless a separately
   validated policy replacement is adopted.
6. **Result and persistence cutover:** migrate callers and persisted fixtures to
   canonical artifact/result schemas. Remove tagged-source loading adapters,
   legacy worker-field fallbacks and the private `_result` import shim; unavailable
   counters and observations remain explicit. For superseded formats, provide a
   one-time conversion path; retire legacy decoders and conversion scaffolding
   when the data migration is complete.
   Done when round trips and success/failure route witnesses use only canonical
   schemas, including EOF, partial output, post-halt dumps and periodic evidence.
7. **Registry and import retirement:** migrate legacy generator indexes/exports,
   `BooleanBackend(generate=...)` callers and duplicate descriptor exports to
   canonical declarations. Delete obsolete aliases, facade modules and helper
   re-exports after their consumers migrate. Preserve lazy implementation loading.
   Done when repository callers, docs, tests and installed-package checks use only
   the supported imports and constructors.
8. **Compatibility-removal acceptance:** maintain the [retirement inventory](migration-ledger.md)
   and [language/backend rows](migration-status.csv). Record every adapter,
   its owner, consumers, replacement and removal release, plus a per-language/backend
   rollout ledger. Close a migration only after all affected rows are migrated
   and its adapters are deleted, including any temporary `esolangs.compat`.
   Add checks preventing retired imports, defaults and protocol forms from
   returning; verify the installed package on supported Python versions. Finish
   with corpus, execution, timing, size/resource and required referee gates.

Remaining closure work (track evidence in the ledger and CSV, not declarations alone):

Prioritize concrete failures, then pending runtimes with complex state,
randomness, finalization, dialects or worker transport. Add focused regressions
within the line budgets. Reuse acceptance evidence
only where source hashes and scope still match. Validate one integrated wheel
through API/CLI generation, binding, persistence, execution and failure routes
on Python 3.12–3.15. Keep lower-priority gaps explicit; priority alone closes no row.

- [x] Complete lifecycle and exact accounting acceptance for all 117 languages:
  native, stepped and isolated traces, input progress, workspace witnesses,
  snapshot isolation, errors and completion evidence.
- [x] Complete installed certification/import isolation and runtime acceptance on
  Python 3.12–3.15, including stepped execution, failures and accounting.
- [x] Audit worker envelopes, nested evidence and persisted fixtures for obsolete
  or permissive protocol forms; reject retired forms with live negative controls.
  Retain supported canonical formats; version 1 alone does not imply obsolescence.
- [x] Audit the final source tree, public exports, docs, tests and installed wheel
  for compatibility modules, aliases, defaults, constructor adapters and import
  re-exports. Migrate any remaining consumers, then delete the layers and any
  one-time converters whose data migration is complete.
- [x] Reconcile every retirement family and all 117 language / 114 backend rows
  with current evidence. Close the eight workstreams only after corpus,
  execution, timing, resource/size and referee gates pass; leave unresolved
  acceptance rows open.

## Engineering

Next experiments; budgets are wall time, not permission for an unpriced search.

| Work | Next experiment | Success criterion | Budget |
| --- | --- | --- | --- |
| Mutation audits | Rank stale generators; price each baseline before sweeping | Triage every survivor before updating its swept revision | 60 s baseline; 240 s per initial batch |
| Unreached code | Triage new gaps from the weekly scan; the current baseline records invariant-backed unreachable arms | Executed witness, invariant, or byte-identical removal; confirm scoped gaps against whole-tree coverage before updating the baseline | 60 s per scoped scan; price whole-tree coverage separately |
| Timing regressions | Inspect weekly environment-matched timing report | Reproduce persistent increases locally before changing code | Existing weekly sweep; no extra generation runs |
| Trick prototypes | Follow the round 2 queue below | Executed control and CONTRIBUTING's size/command gate | Price each prototype before running |

A removal must leave the generated corpus byte-identical, including tiled,
constant and ignored-input tables. The completed constant-table audit is in
history at `f35aa4023`.

- **Malbolge navigation, inexpressibility for an algebraic
  signature:** the closed-form question is closed under the
  bounded-read definition in [limitations](limitations.md#searches)
  — a lower bound excludes every rule factoring through cycle data
  plus bounded algebraic features (a reproducing formula needs at
  least 59 forced cell reads; no navigation with at most three
  jumps per `goto` fits at n=1, the cheapest ending at 6,607).
  The open remainder is signature-relative: no term of any size
  over the restricted algebraic signature (reads only at derived
  indices, per-trit algebra, no equality against arbitrary value
  constants, no random access) computes the optimal first step.
  The preservation route to it was attempted (2026-10-31) and is
  closed: the invariant relations are fully classified (values
  admit only the trivial two; positions admit a period-94
  family), no surviving relation separates, and the joint
  domain test is empty.  What remains is a proof by
  non-product or non-uniform relations, unpriced, or a term
  exhibiting the contrary.  See
  [limitations](limitations.md#searches).
- **Wiki candidate screening:** continue the 2026-11-01 API screen: 2,537
  language pages outside `Implemented` and `Unimplemented`, 2,248 after the
  interpreter-link filter. Refresh categories and specs for the next batch.
  Missing links do not establish first-implementation eligibility: check
  public implementations, fixed core semantics and an executed loop-less
  O(T) Boolean construction under [curation](limitations.md#curation).
  Record candidates and rejection reasons.
- **Blind reimplementation of first implementations:** a clean-room
  interpreter written from the wiki page alone, diffed over the generated
  corpus.  With no outside interpreter, this is the only independent
  check a first implementation gets.  Found: one spec contradiction
  (Tiangou halted on underflow), five generators emitting forms the page
  does not license (Collatz Multiverse, Decleq, Minsky Swap, Modulous,
  SendStuff), the rest spec gaps now in the docstrings.  Record one as
  `[audits] blind_reimplementation = <date>`.
  - *Weakly grounded readings the generators rely on:* each record
    agrees only with the clean room patched to our reading.  Make the
    generator run under both, or find page evidence.
    - B-tapemark: FENCED (2026-10-31); evidence in
      [limitations](limitations.md#notes-on-individual-languages).  Reopen
      on new page evidence (Talk page, author statement, reference
      implementation), a folded or narrow construction beating the named
      obstructions, or a real consumer for the other reading (the dialect
      branch is ready).

- **Trick prototypes, round 2:** complete. All 325 named proposals from 109 raw
  files have recorded dispositions; five earlier zero-trick generators are
  also covered. The 2026-11-03 recheck includes both execution gates: six
  additional rules admitted; Sonata/Minsky variants rejected on measured
  costs. Proof-test arities are preserved. Line, Quassaunt and Stisp
  source and Suffolk workspace retain explicit upper bounds; their exact
  global maxima remain unproved.
