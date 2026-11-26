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
  - *Native decoder:* scratch builds ran from reset on all 131,072 inputs
    of four tables. One layout reached 130,347 and 130,277 correct
    answers on the two random tables. Both reads and the output slot
    matched on every row. All 130,949 legal reads per table printed the
    stored bit and halted. On the first table, 58 misses read an invalid
    packed byte and 667 read the wrong stored bit. An earlier one-cell
    return shift freed 42 words. All eight values at each word ran natively.
    After swapping the highest address trit, 103 groups reread their
    selector to choose among three spill routes. This moved 4,944 primary
    words and preserved every spill address. Two other layouts used a
    second selector. The same 64 groups kept 3,072 primary moves and
    reassigned all 4,096 of their spill bits. Both layouts reached 131,072
    distinct bit positions. A separate layout moved 448 primary words by
    reassigning 3,008 spill bits. All eight values worked at 434 of the
    new destinations in 10,416 runs.
  - *Bank capacity:* six navigation edits freed 153 three-bit words while
    preserving both reads and the output slot on every row. All eight labels
    worked at every word in 3,672 native runs. Shortening initialization
    freed 871 consecutive cells for decoder code and a 408-word output
    lookup. Moving the lookup and the final decoder block freed 369 and
    77 three-bit words, respectively. All eight values at each word
    passed in 10,704 row executions across the two layouts. Moving the
    phase read 94 cells earlier made room for a pointer shortcut. Clearing
    one temporary register and rotating the calibration byte earlier freed
    161 more three-bit words. All eight values passed in 3,864 executions.
    Routing startup around one output routine reduced the fixed-bank
    shortfall from 1,213 bits to 961 across eight banks, with 2,048 bits
    per 729-word bank and control words and calibration markers reserved.
    Both reads and the output slot matched on all 131,072 rows of each
    random table. This layout answered 129,805 and 129,560 rows correctly.
    Moving all three output routines into startup memory freed 261 more
    three-bit words. All eight labels worked at every word in 6,264 native
    runs. The displaced startup code raised the shortfall to 3,869 bits.
    A separate layout moved 24 primary words between
    banks, kept every spill address, and gained three writable bit positions
    net. All eight labels worked at
    all 24 destinations.
  - *Storage shared with the decoder:* 93 words in the jump workspace
    stored three answer bits each. In the same layout, 63 fixed instructions
    encoded three bits each through selectable markers. All eight values
    at each word worked across 64 paired patterns (29,952 row executions).
    A separate marker distinguished two fixed instructions while preserving
    all eight values at 101 writable words in its bank. Placing arbitrary
    table bits across the full program remains open.
- **Open mathematics:** Whether some 17-input Malbolge table has no program
  is open; the Malbolge row above is the constructive side
  ([proofs](proofs/index.md#malbolge-bound)).

Keep the registry-wide scaling regressions in `tests/proofs/deep/linearity.py`.
An unresolved bound stays open; it does not authorize removing its regression
check or weakening a contract.

## Engineering

- **Malbolge read-only decoder placement.** Filling each bounded hole
  exactly with movable code blocks fits 22 one-port targets: 283 native
  decoder words, 841 host-staged, 7,112 queries with zero writes to the
  packed table. At 23 targets the zero-slack fill leaves 40 contiguous cells
  for seven late frames that need 56. Free 16 cells by shortening the writer
  or counted code, or place frames across fixed cells.

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
