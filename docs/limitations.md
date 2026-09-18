# Limitations and contracts

Standing contracts and walls. Closed scaling work belongs in its commit;
Polynomial's proved wall is in [polynomial](polynomial.md).

## Interpreter conventions

- Empty input is a no-op unless a language requires a seed or grid.
- Exhausted input raises `EOFError`; malformed programs raise `ValueError`;
  runtime failure raises `HaltError`, unless the language says otherwise.
- Character input is line-delimited; a blank line means `0` by package
  convention, not language inference.
- Explicit frame stacks are uncapped. Forbin expression calls retain their
  documented host-recursion limit.
- Streetcode's four-way junction is an implementation convention: the source
  specifies only a two-road choice.

## Source positions

`esolangs debug --tui` marks only a source position. `ip_shape` is `offset`
(45 languages), `grid` (11), `line` (2), or `opaque` (7); undeclared tuples
are refused and opaque positions have no program mark.

Line extraction accepts anti-aliased PNGs only when strokes retain a connected
dark core. The 3px scan fixture executes addition; a one-third-pixel shift of
a 1px stroke is rejected with 921 unaccounted pixels rather than silently
changing the program.

## Boolean generators

Parameterized generators embed each input exactly once. Every emitted
character is build work. Reordering is optional around a construction, but
its selection cost counts; named candidates are capped at four and the generic
greedy scorer stops at n=10. Generator constructions may not use BFS or DFS;
test-only oracles may.

`%^2^-1` cannot compute every table as a template: its accumulator has 6,263
classes between placeholders, while the dense 17-input fixture exceeds that
at every 13-input cut ([proofs](proofs.md)). The shipped planner builds every
table tried through fourteen inputs (dense: 1.59 MB in about 10 s) and refuses
the dense fifteen-input fixture: its 11-cut has 2,017 cofactors among 2,048
rows and the fold's landing window jams. This is a planner wall, not a language
lower bound; the language has an unimplemented reset move and its
transformation monoid remains the finite question.

The screen script measures permuted-table builds, not an admissible reorder
under a fixed input template and fill mapping. Interprogck8, Dig, Flowchart,
BrainIf, Sophie, and SLOW ACV MAMMALIAN must read streams in order; BF-PDA uses
its fixed stack order. No instruction-only wire is derived for 123, Minifuck,
WII2D, or COD. ArrowQueue re-enqueue remains open.

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Polynomial | 10 | 10 | 1,934-instruction guard; dense n=11 is priced at 267 s and >100 MB. |
| WII2D | 9 | 10 | Dense n=10 exceeds the admitted 256-domain cost policy. |

WII2D n=9 is partial: 54 of 64 sampled dense tables build; the magnitude guard
is load-bearing. A total extremal-fold decode reaches domain 512 but is refused
on cost (the four refusing dense n=9 cases cost 0.8–1.6 MB). It is not a
drop-in replacement: under shipped caps it refuses from n=7 and is 3x size at
n=6. The open issue is a constant-factor readout rule, not whether folding is
necessary: no instruction reads a value into control, so the fold is the only
branching primitive.

Polynomial's mandatory root product has minimum mass at the product itself;
the slack certificate proves `Theta(L**2 log L) = Theta(T**2 / log T)` digits
for every multiple, cofactor, and operand sign. Factor has a language floor
`Omega(T log T / log log T)` because exponents are unary-priced and primes are
distinct and ascending; its folded tree is `Theta(T log T)`.

### Scaling

Size is measured from rendered output, and correctness claims require running
the generated program. Execution measurements exclude loading and use the
worst sampled parity row. A sub-10 ms run does not establish an exponent.
Loading dominates Factor (integer factorization) and Circuit Diagram (parsing
super-linear area); it is intentionally excluded from execution time.

The execution contract in `tests/proofs/deep/execution.py` holds every
generator's command count linear. Bracket matching is precomputed at load.
Persistent stores use shared 32-cell chunks; RAM0 also indexes addresses.
Those choices prevent repeated scans, but command cost and source size remain
separate axes.

### Searched negatives

- **COD:** tested routing has no compact two-exit zero test. Joins leak a copy
  and a kill is required per zero-set per copy; this is not a lower bound.
  Scoped to disjoint routed-cascade arms, the reason is exact: a residual
  ``r`` reaches ``<`` only after at least ``r`` net ``(`` cells, so selecting
  index ``T - 1`` prices ``sum(range(T)) = T(T - 1)/2`` cells. Shared lanes
  are outside that lemma; the executed shared-column attempt re-enters its
  ``+`` and doubles live cods.
  COD has no packed scalar escape: every value operation changes by one, and
  ``<``/``_`` distinguish only zero from nonzero. Executed probes for
  ``2**k`` versus ``2**k + 1`` stay control-equivalent for a ``k``-cell probe;
  the first probe that distinguishes them spends ``2**k`` decrements.
- **Interprogck8:** a depth-d read costs `3 + 2 floor(d / 14)` lines. The
  constant-width gadget costs about 8x per node; transfers wrap modulo 256,
  and function capture cannot nest.
- **WII2D:** one-step centre rules, scalar keys, added merge-free vocabulary,
  and bounded-beam lookahead do not match the shipped depth predictor. The
  total extremal-fold fallback was also executed: on the 5-bit maximal-LFSR
  sequence it emits 29, 88, and 8,978,977 op cells at domains 8, 16, and 32
  while reproducing every bit (the proof oracle is
  `tests/proofs/test_negatives.py::TestWii2dExtremalRule`). Exact small
  optima cost 1.4–2.4 characters per entry; these are readout-model
  obstructions, not a language bound. `@` does not add prefix state under
  exactly-once embedding: an executed two-route geometry reaches the shared
  second input with different headings, but that cell resets both routes to
  the same position and heading (`TestWii2dAtCannotPreservePrefixState`).
  A deterministic two-ply rule (scale, fold the canonical extreme pair,
  then halve by the smallest opposite-colour gap) is total and runs a full
  domain-8 grid, but its LFSR domain-16 readout is 1,430,153 cells versus
  the shipped 110; it is not a constant-loss construction
  (`TestWii2dCanonicalExtremePair`). Exact two-prefix minima beat the shipped
  readout 15–37% on the LFSR witness and sampled dense patterns (80 vs 110
  at 16, 282 vs 333 at 32, 898 vs 1127 at 64) but need the pair search
  itself (238/903/4063 prefixes, 40.8 s at 64), and per-entry cost still
  grows (5.0/8.8/14.0); a named second pick is worse than shipped twice in
  five (`TestWii2dTwoPrefixBeatsShipped`). No per-epoch floor lifts this
  into a bound: one shipped step in, a 3+-merge fold costs 7 at live 28
  (domain 32) and at live 59 (domain 64), so later epochs go cheap and the
   ratchet is cumulative unary-centre spend, not terminal magnitude
   (`TestWii2dNoPerEpochFloor`). A loop-less max-pair first fold plus shipped
   tail recovers nothing at domain 16 (110/29/63/63/128 vs shipped
   110/30/63/63/115, LFSR-16 30 over the 80-pair optimum)
   (`TestWii2dFragRankerFailsLikeTwoPly`). A four-scorer by two-tie-break
   loop-less step-1 sweep gains one cell at best (29/110/333/63/63 vs
   shipped 30/110/333/63/63) and the ratio scorer blows domain 32 to 467;
   a local one-step lookahead over the top-3 fires yet gives 115 on
   LFSR-16, 35 over the optimum (`TestWii2dRankerSweep`).
- **%^2^-1:** the shortest 2/3 descent cuts dense fourteen inputs from 1.84 MB
  to 1.59 MB but does not bound relocations. Its size contract only reaches
  n=12 past the route change.

## Curation

The collection has 63 languages; its floor is 34. Ordinary imperative entries
with shared-shim generators and no consumer were removed. Nopstacle and
ZTOALC L left on 2026-09-17: the former cannot meet embed conventions, the
latter was a searched syntax-level lookup table. The 2D candidate screen is
kept because re-running it is expensive: 1,543 unimplemented pages intersected
with 567 two-dimensional-language pages, then filtered to 36 by implemented
verdicts, co-categories, I/O/branch vocabulary, and 1,500-character pages.
Super SNUSP and Alight were admitted; Pinyin was rejected.

## Specification decisions

- 6-5 accepts operands beyond its specification; generators use `0..35`.
- Jaune dispatch to an undefined marker is unspecified.
- Alight expressions are infix and left-to-right; three-argument `at` mutates.
- Packlang literals are decimal; its cat cannot receive byte 10 under
  line-oriented input.
- Pinyin is rejected: its spelling rule contradicts its examples and its
  input-1 truth-machine example has no deterministic reading.

Generated programs are evidence only after execution through their interpreter.
