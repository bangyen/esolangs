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
- **Wiki shortlist.** Six screened candidates advance to the next
  implementation pass. Each subset probe passed all 65,536 arity-four tables
  on all 16 inputs, plus sampled inputs through arity ten. Each emitter has
  O(T) generation time and source size. Order favors direct constructions
  using documented operations with few open questions on the generator's path.
    1. [Trml](https://esolangs.org/wiki/Trml) (rev. 140496).
       Three rules select a truth-table leaf by rewriting a single root.
       The result is the final term.
    2. [StrML](https://esolangs.org/wiki/StrML) (rev. 179266).
       A quoted source header carries the fixed base. One grouped test per
       immutable input bit selects the result. The artifact is `8T` characters.
    3. [Numlist](https://esolangs.org/wiki/Numlist) (rev. 138564).
       Each input binds one contiguous block of relative jumps. Shared
       suffix states keep the decimal source linear. One forward pass
       prints the selected bit and exits past the instruction list.
    4. [Thing of Shock](https://esolangs.org/wiki/Thing_of_Shock) (rev. 204327).
       An acyclic graph binds each input bit to one initial counter.
       Shared suffix graphs keep the serialized source linear. Read the
       designated counter at tick `4n+3` for `n` input bits.
    5. [1nteger](https://esolangs.org/wiki/1nteger) (rev. 180816).
       An `IF` tree reads one byte per decision and uses only byte values.
       `PNT` emits the selected bit. Source is exactly `28T−21` characters.
    6. [Pd.NA](https://esolangs.org/wiki/Pd.NA) (rev. 147169).
       One tape cell selects branches and emits the bit. An EOF witness
       exercised the NA catch path. Source is exactly `11T−7` characters.
  - *Admission:* refresh the public-implementation check and apply the
    [curation rules](limitations.md#curation). Verify the complete
    interpreter and generator before adding each language.

## Wiki candidate backlog

### Reserve (28)

- [AEAV](https://esolangs.org/wiki/AEAV)
- [ASCIIgibberish](https://esolangs.org/wiki/ASCIIgibberish)
- [StupLANG](https://esolangs.org/wiki/StupLANG)
- [XMLfuck](https://esolangs.org/wiki/XMLfuck)
- [AmogusScript](https://esolangs.org/wiki/AmogusScript)
- [Methylmercury](https://esolangs.org/wiki/Methylmercury)
- [Brainfive](https://esolangs.org/wiki/Brainfive)
- [TOPLWARLNTMIHTACAFFTPLAIHTASTNBIHTMAIAIU](https://esolangs.org/wiki/TOPLWARLNTMIHTACAFFTPLAIHTASTNBIHTMAIAIU)
- [FastBrain](https://esolangs.org/wiki/FastBrain)
- [CRAZYLANG](https://esolangs.org/wiki/CRAZYLANG)
- [kxgxyo](https://esolangs.org/wiki/Kxgxyo)
- [Tech Support Scam](https://esolangs.org/wiki/Tech_Support_Scam)
- [ASCII @](https://esolangs.org/wiki/ASCII_@). The translated subset ran
  on public `@`, which rejects raw ASCII source and differs on negative
  fractions. Refresh the search for a public ASCII runner at admission.
- [Dan](https://esolangs.org/wiki/Dan)
- [Helo PkmnQ](https://esolangs.org/wiki/Helo_PkmnQ)
- [GotoScript](https://esolangs.org/wiki/GotoScript)
- [Sonjalang](https://esolangs.org/wiki/Sonjalang)
- [诗(PSTF)](https://esolangs.org/wiki/%E8%AF%97(PSTF))
- [NoGolfersLand](https://esolangs.org/wiki/NoGolfersLand)
- [C!](https://esolangs.org/wiki/C!) (rev. 197732). The paired guards passed
  the full sweep with an independent nested `Q` parser.
- [Brаinfuck](https://esolangs.org/wiki/Br%D0%B0infuck) (rev. 202557). The
  two-cell generator passed the full sweep. The tape-edge rule for `&`
  remains unspecified.
- [Gridify](https://esolangs.org/wiki/Gridify) (rev. 201532). Numeric I/O and
  `G` lookup passed the full sweep. Both the stack index and grid width grow
  with the table length.
- [Teacher](https://esolangs.org/wiki/Teacher) (rev. 195882). Nested grade
  tests reuse one variable. The loop exit rule remains open.
- [Duzitdo?](https://esolangs.org/wiki/Duzitdo%3F) (rev. 203847). Postorder
  arithmetic selects the result with small integers. `ASK` follows the
  numeric input in the calculator example.
- [You wait here](https://esolangs.org/wiki/You_wait_here) (rev. 131213).
  A counter reset and two conditional blocks select each branch.
  `repeat`, `split` and `define` remain open outside this subset.
- [干！](https://esolangs.org/wiki/%E5%B9%B2%EF%BC%81) (rev. 166203).
  A numeric read and if/else select each branch. Assignment direction
  and division remain open outside the tested selector.
- [Globe](https://esolangs.org/wiki/Globe) (rev. 165023). State-dependent
  parity filters table symbols per embedded input bit. The last transition
  prints the remaining bit.
- [Turing Code](https://esolangs.org/wiki/Turing_Code) (rev. 204341).
  An acyclic `!!DTM` graph leaves one string bit on the trimmed tape in
  `n+1` transitions. The printed tape format remains open.

The original revision pins and screening sketches are in
`5f3bcddf3:docs/roadmap.md`.
