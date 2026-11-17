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
- **Wiki candidate admission checks, in order:**
    1. [OBrainfuck](https://esolangs.org/wiki/OBrainfuck) (rev. 163644):
       ordinal brackets select a Boolean arm, 3,080 subset runs and 64
       independent C-lowering checks. The pinned spec leaves EOF open.
       The repo's EOF-error convention passed on truncated input.
       No public interpreter surfaced in the targeted search.
    2. [Bruijndejx](https://esolangs.org/wiki/Bruijndejx) (rev. 139554):
       one native read selects the zero, one or EOF continuation. The
       subset passed 5,146 runs. Check lambda and declaration semantics.
    3. [Hopscotch (Asa-z)](https://esolangs.org/wiki/Hopscotch_(Asa-z))
       (rev. 193077): a relative jump loads the destination's predecessor
       literal. The subset passed 5,144 runs. Pin EOF and recheck the WIP
       implementation.
    4. [Bytemap](https://esolangs.org/wiki/Bytemap) (rev. 169841): the
       two-operand grid comparison selects independent jump targets,
       3,610 subset runs. The greeting works with an unreachable padding
       row under the even-row rule. Pin console EOF.
    5. [Ser2](https://esolangs.org/wiki/Ser2) (rev. 70987): eager rewrites
       select the most specific input pattern and return the original
       I/O object. The subset passed 5,146 runs and selected zero, one
       and EOF in both rule orders. Check full grammar and execution.
    6. [Flipscript](https://esolangs.org/wiki/Flipscript) (rev. 188418):
       direction reversal and relative line jumps, 3,610 subset runs.
       Pin numeric input framing and line-offset range.
    7. [Tubes](https://esolangs.org/wiki/Tubes) (rev. 78300): modulo-selected
       exits in a Unicode grid, 3,616 subset runs. Pin EOF and ignored-symbol
       handling for the numeric stream. Check the reported C interpreter.
    8. [NOR Machine](https://esolangs.org/wiki/NOR_Machine) (rev. 154406):
       indexed bit input and final-stack output, 2,680 subset runs. Pin
       input framing and check implementation coverage for this dialect.
    9. [Artppeice](https://esolangs.org/wiki/Artppeice) (rev. 201757):
       dequeued words select destination queues for literal payloads.
       A linear-character tree passed 2,458 byte-exact cases with no
       implicit output separator. Check full command semantics, word
       framing and public implementation coverage.
  - *Admission:* check public implementations, fixed core semantics and
    an executed loop-less O(T) Boolean construction under
    [curation](limitations.md#curation).
