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

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.

## Engineering

- **Malbolge navigation, inexpressibility for an algebraic
  signature:** the [bounded-read lower bound](limitations.md#searches)
  excludes rules based on cycle data and bounded algebraic features. The open question is whether a term over the restricted algebraic
  signature can compute the optimal first step. The classified invariant
  relations give no separation. Reopen with a separating non-product or
  non-uniform relation, or a term computing the step.
## Wiki shortlist

- Six screened candidates advance to the next implementation pass. Each subset probe passed all 65,536 arity-four tables
  on all 16 inputs, plus sampled inputs through arity ten. Each emitter has
  O(T) generation time and source size. Order favors direct constructions
  using documented operations with few open questions on the generator's path.
    1. [StrML](https://esolangs.org/wiki/StrML) (rev. 179266).
       A quoted source header carries the fixed base. One grouped test per
       immutable input bit selects the result. The artifact is `8T` characters.
    2. [Numlist](https://esolangs.org/wiki/Numlist) (rev. 138564).
       Each input binds one contiguous block of relative jumps. Shared
       suffix states keep the decimal source linear. One forward pass
       prints the selected bit and exits past the instruction list.
    3. [Pd.NA](https://esolangs.org/wiki/Pd.NA) (rev. 147169).
       One tape cell selects branches and emits the bit. An EOF witness
       exercised the NA catch path. Source is exactly `11T−7` characters.
    4. [Thing of Shock](https://esolangs.org/wiki/Thing_of_Shock) (rev. 204327).
       An acyclic graph binds each input bit to one initial counter.
       Shared suffix graphs keep the serialized source linear. Read the
       designated counter at tick `4n+3` for `n` input bits.
    5. [Globe](https://esolangs.org/wiki/Globe) (rev. 165023). State-dependent
       parity filters table symbols per embedded input bit. The last transition
       prints the remaining bit.
    6. [Turing Code](https://esolangs.org/wiki/Turing_Code) (rev. 204341).
       An acyclic `!!DTM` graph leaves one string bit on the trimmed tape in
       `n+1` transitions. The printed tape format remains open.
  - *Semantic screen:* StrML edits a base string through separate base and
    input cursors. Numlist prints the magnitude of an underflowing jump, so
    character output depends on instruction placement. Pd.NA propagates
    missing tape values and catches them at control boundaries.
  - *Admission:* refresh the public-implementation check and apply the
    [curation rules](limitations.md#curation). Verify the complete
    interpreter and generator before adding each language.

## Wiki candidate backlog

### Reserve (12)

- [XMLfuck](https://esolangs.org/wiki/XMLfuck)
- [Methylmercury](https://esolangs.org/wiki/Methylmercury)
- [Brainfive](https://esolangs.org/wiki/Brainfive)
- [FastBrain](https://esolangs.org/wiki/FastBrain)
- [kxgxyo](https://esolangs.org/wiki/Kxgxyo)
- [ASCII @](https://esolangs.org/wiki/ASCII_@). The translated subset ran
  on public `@`, which rejects raw ASCII source and differs on negative
  fractions. Refresh the search for a public ASCII runner at admission.
- [Helo PkmnQ](https://esolangs.org/wiki/Helo_PkmnQ)
- [诗(PSTF)](https://esolangs.org/wiki/%E8%AF%97(PSTF))
- [NoGolfersLand](https://esolangs.org/wiki/NoGolfersLand)
- [Brаinfuck](https://esolangs.org/wiki/Br%D0%B0infuck) (rev. 202557). The
  two-cell generator passed the full sweep. The tape-edge rule for `&`
  remains unspecified.
- [Gridify](https://esolangs.org/wiki/Gridify) (rev. 201532). Numeric I/O and
  `G` lookup passed the full sweep. Both the stack index and grid width grow
  with the table length.
- [You wait here](https://esolangs.org/wiki/You_wait_here) (rev. 131213).
  A counter reset and two conditional blocks select each branch.
  `repeat`, `split` and `define` remain open outside this subset.

The first-implementation screen dropped QuakeScript and 1nteger from the
shortlist. Their selectors use an accumulator, ordinary tests and jumps or
blocks. Fourteen reserve candidates likewise offered direct scripting
constructions. Reserve entries still need a worked example demonstrating
their semantic constraint before promotion.

The original revision pins and screening sketches are in
`5f3bcddf3:docs/roadmap.md`.
