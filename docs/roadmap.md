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

Previous architecture migrations are integrated. All 117 languages execute a
bounded independent semantic model and detect a live output fault. Models
cover their declared fragments; broader regressions, purity and snapshot
checks remain. Language-specific compatibility decisions stay in the
interpreter contracts. Brainfuck now projects a versioned workspace model;
cycle snapshots and Python backing storage retain separate contracts.

Public artifacts, independent lazy descriptors and shared execution results
are integrated. Decision analyses serve four backends; affine forms and
weighted lookups retain specialized emitters. Resource claims render from
structured evidence. The cost/fault pilot retained the current verification
budgets. Further migrations retain corpus, timing and growth gates.

Next experiments, in priority order. Price each pilot within the standing
compute budget before running it; these proposals do not change contracts.

1. **Artifact-first API:** prototype explicit source/file construction and
   program/template results using the existing artifacts and execution results.
   Map compatibility adapters that disappear and caller migrations required;
   changing public defaults needs a versioned compatibility plan.
2. **Typed interpreter lifecycle:** pilot declared preparation, machine factories
   and optional debugging/completion capabilities in place of private-name and
   signature discovery. Preserve lazy loading, source-step accounting, dialects
   and completion evidence; compare corpus traces and timings before expansion.
3. **State-storage policy:** measure an owned mutable-store prototype against
   the immutable core, including snapshot isolation, independent semantics and
   trace equivalence. Retain purity gates; adopting mutable storage requires an
   explicit policy decision backed by the pilot's costs and guarantees.
4. **Generator analysis boundaries:** identify duplicated analysis beyond the
   existing decision, affine and lookup helpers. Pilot shared validated inputs
   and analysis only where emitters benefit; associate the selected construction
   with its bounds and witnesses. Require byte-identical corpus output and
   preserved growth and timings; keep language-specific emission and selection.
5. **Certification boundaries:** audit operational imports and remaining
   duplicated evidence. Pilot moving certification dependencies outside runtime
   descriptors and rendering duplicated claims from structured evidence.
   Preserve lazy catalog access, installed-package behavior, independent oracles
   and live fault detection; replace private-name discovery with declarations
   only when equivalent checks execute.

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
