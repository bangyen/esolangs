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
- **Wiki candidates (2026-11-18).** Re-screened after the stale novelty
  rule left `CONTRIBUTING.md` (`e4c52ad73`).
  No page revision, backlink, subpage, creator page or same-name GitHub account
  shows a public implementation; none is a token substitution of a member.
  Each construction has a proved-linear analogue in the collection, but none
  is prototyped.
    1. [CRAZYLANG](https://esolangs.org/wiki/CRAZYLANG) (rev. 197061): table
       integer built from fixed-size chunks; skip-next multiplies in 2^(2^i).
       Open: integer division.
    2. [Teacher](https://esolangs.org/wiki/Teacher) (rev. 195882): nested `IF
       … OR ELSE … NOW SHOW ME YOUR GRADE` tree reusing one variable. Open:
       loop exit rule.
    3. [Calculation](https://esolangs.org/wiki/Calculation) (rev. 155994):
       nested `?` blocks reusing one variable. Open: input framing; jumps are
       1-based in both examples.
    4. [干！](https://esolangs.org/wiki/%E5%B9%B2%EF%BC%81) (rev. 166203):
       branch-free: table by doubling, row by `X^Y`, floor division and mod.
       Open: assignment direction.
    5. [Duzitdo?](https://esolangs.org/wiki/Duzitdo%3F) (rev. 203847):
       chunk-built table integer, `DIV`/`REM` by 2^row. Open: `ASK` framing;
       `DEF` bodies skipped in flow.
    6. [GotoScript](https://esolangs.org/wiki/GotoScript) (rev. 149969): one
       `PRINT` indexing a T-character table string. Open: `INPUT` typing;
       `GOTO WHEN`/`ONCE` raise.
    7. [1-866-025-4037](https://esolangs.org/wiki/1-866-025-4037) (rev.
       201974): `?`-read bit tree (Bruijndejx's shape). Open: when an
       unapplied I/O combinator fires (its truth machine needs it); EOF.
    8. [My cat predicted a rain of ash and
       dust](https://esolangs.org/wiki/My_cat_predicted_a_rain_of_ash_and_dust)
       (rev. 201869): as 1-866-025-4037, D2 K' R** W** basis. Open: same I/O
       call.
    9. [Methylmercury](https://esolangs.org/wiki/Methylmercury) (rev. 201813):
       Lazy K I/O, K ф Θ combinator tree. Open: none beyond Lazy K.
    10. [Helo PkmnQ](https://esolangs.org/wiki/Helo_PkmnQ) (rev. 203900): Lazy
        K I/O combinator tree;
        [Psychologist](https://esolangs.org/wiki/Psychologist) (rev. 203875)
        is its renamed PKN subset, so at most one. Open: syntax from examples.
    11. [FastBrain](https://esolangs.org/wiki/FastBrain) (rev. 134496):
        brainfuck construction on a 15-D tape. Open: EOF, cell width.
    12. [Brаinfuck](https://esolangs.org/wiki/Br%D0%B0infuck) (rev. 202557):
        brainfuck construction (Cyrillic а; adds `&`, `0`-`9`, `@`, `;`).
        Open: `&` at the tape edge.
    13. [Sonjalang](https://esolangs.org/wiki/Sonjalang) (rev. 165968): table
        string indexed by `kipisi X lon Y`. Open: FizzBuzz breaks the `.`
        terminator and elif form; int/int `kipisi` type.
    14. [C!](https://esolangs.org/wiki/C!) (rev. 197732): table string read by
        `L[x,n]`. Open: `^`/`V` precedence; `D` has no call syntax.
  - *Admission:* a subset prototype per language -- every table to n=4,
    random to n=10, size measured against T, a mutant that fires -- then
    `/new-language`. Build a decimal table from chunks: one T-bit decimal
    literal converts in superlinear time (2^22 bits: 373 ms decimal, 1 ms hex).
