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
  - *Bulk seeding lead:* a 296-cell fall-through sweep matched all 94 word
    deposits against the stepper but placed 0 of the 74 shipped label cells
    without steering (best steered case: 8–10). Revisit for bulk deposits inside
    the paused loop.
    Sweep results in `a7b3f7abd:docs/roadmap.md`.
- **Open mathematics:** Whether some 17-input Malbolge table has no program
  is open; the Malbolge row above is the constructive side
  ([proofs](proofs/index.md#malbolge-bound)).

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.

## Engineering

Next experiments; budgets are wall time, not permission for an unpriced search.

| Work | Next experiment | Success criterion | Budget |
| --- | --- | --- | --- |
| Unreached code | Triage new gaps from the weekly scan; the current baseline records invariant-backed unreachable arms | Executed witness, invariant, or byte-identical removal; confirm scoped gaps against whole-tree coverage before updating the baseline | 60 s per scoped scan; price whole-tree coverage separately |
| Timing regressions | Inspect weekly environment-matched timing report | Reproduce persistent increases locally before changing code | Existing weekly sweep; no extra generation runs |

A removal must leave the generated corpus byte-identical, including tiled,
constant and ignored-input tables. The completed constant-table audit is in
history at `f35aa4023`.

- **Malbolge navigation, inexpressibility for an algebraic
  signature:** the [bounded-read lower bound](limitations.md#searches)
  excludes rules based on cycle data and bounded algebraic features. The open question is whether a term over the restricted algebraic
  signature can compute the optimal first step. The classified invariant
  relations give no separation. Reopen with a separating non-product or
  non-uniform relation, or a term computing the step.
- **Wiki candidates, in admission order.** All nine subset probes passed
  28,444 generated cases in the screening recheck. No qualifying public
  implementation surfaced for these dialects.
    1. [OBrainfuck](https://esolangs.org/wiki/OBrainfuck) (rev. 163644):
       ordinal bracket pairing, 3,080 cases and 64 earlier C-lowering
       checks. Empty and truncated input raise in the probe. EOF is open.
    2. [Bruijndejx](https://esolangs.org/wiki/Bruijndejx) (rev. 139554):
       zero, one and EOF continuations, 2,122 cases in the binding probe.
       Macro capture and ordinary declaration lookup differ. Evaluation
       timing, duplicate declarations and unbound-index errors are open.
    3. [Bytemap](https://esolangs.org/wiki/Bytemap) (rev. 169841):
       grid comparison with two jump targets, 3,610 cases. The greeting
       uses an even-height grid. The ASCII probe raises before writing
       on a short read. EOF is open.
    4. [Ser2](https://esolangs.org/wiki/Ser2) (rev. 70987): eager rewrite
       selection and linear I/O, 5,146 cases. Escaped names, wildcard
       validation and ambiguous matches were checked. Verify optional
       signals and remaining special-object grammar at admission.
    5. [Flipscript](https://esolangs.org/wiki/Flipscript) (rev. 188418):
       direction-dependent jumps, 3,610 cases. Tested a 114,685-line
       jump. The probe uses one exact decimal per line and raises at EOF.
       The spec leaves numeric width, framing and EOF open.
    6. [Tubes](https://esolangs.org/wiki/Tubes) (rev. 78300): modulo
       selects ordered exits, 3,616 cases. The probe skips characters
       outside ASCII digits 0–3 and raises at EOF. EOF is open, and the
       reported C interpreter in development has no public copy found.
    7. [NOR Machine](https://esolangs.org/wiki/NOR_Machine) (rev. 154406):
       zero-based indexed input and top-first stack output, 2,680 cases.
       The probe caches bits on demand and raises for a missing bit.
       Consumption and error handling remain implementation choices.
    8. [Artppeice](https://esolangs.org/wiki/Artppeice) (rev. 201757):
       dequeued words select payload destinations, 2,458 byte-exact
       cases. The probe checks wraparound and rename. Word framing,
       EOF, output separators and rename collisions are open.
    9. [Tamerlane](https://esolangs.org/wiki/Tamerlane) (rev. 93756):
       runtime rewrite queries and a stop callback, 2,122 cases. The
       shared graph and message stream have an O(T) character bound.
       The probe uses line framing and serial literal deletion on
       positive-weight arcs.
  - *Admission:* check public implementations, fixed core semantics and
    an executed loop-less O(T) Boolean construction under
    [curation](limitations.md#curation).
