# Limitations and contracts

Standing contracts and walls. Closed scaling work belongs in its commit;
Polynomial's proved wall is in [polynomial](proofs/polynomial.md).

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
- Line and Piet carry a raster source: `generate` returns an
  `esolangs.raster.Raster`, `run` takes it or a PNG path through the shared
  codec, and `describe` reports `source_kind="raster"`. They stay outside
  text-only `RUNNERS` and its VM, step, and fuzz contracts. Line retains its
  graph for repeated rows; Piet emits and executes the pixels.

## Source positions

`esolangs debug --tui` marks only a source position. `ip_shape` is `offset`,
`grid`, `line`, or `opaque` -- `tests/test_vm_protocol.py` sweeps every language
and refuses an undeclared or misspelled value. Opaque positions have no program
mark.

Line extraction accepts anti-aliased PNGs only when strokes retain a connected
dark core. The 3px scan fixture executes addition; a one-third-pixel shift of
a 1px stroke is rejected with 921 unaccounted pixels rather than silently
changing the program.

## Boolean generators

Parameterized generators embed each input exactly once. Every emitted
character is build work. Five conventions govern the *embed* -- the text
standing for one input, not the program around it: one ordered run per input,
constant width, a single embed, no padded spaces, and a uniform `(zero, one)`
pair. The first three are the template constructor's shape; the last two are
measured off filled programs at n=2, 3, 5 by
`tests/proofs/test_conventions.py`, and every embedding generator holds both.
A relaxed-width toggle is worth adding only for a smaller executed build; a
space toggle has no remaining use. Reordering is optional around a construction, but
its selection cost counts; named candidates are capped at four and the generic
greedy scorer stops at n=10. Generator constructions may not use BFS or DFS;
test-only oracles may.

The screen script measures permuted-table builds, not an admissible reorder
under a fixed input template and fill mapping. Dig, Flowchart,
BrainIf, Sophie, and SLOW ACV MAMMALIAN must read streams in order; BF-PDA uses
its fixed stack order. No instruction-only wire is derived for 123 or Minifuck.
ArrowQueue re-enqueue remains open.

Malbolge registers a generator through eleven inputs, source-embedded with no
initializer. Through ten, a branch-free five-cell mixer (13 operations per input bit, inits
52/90/83/70/92, then a 16-operation post-map) folds the row index into a
distinct address `h(row)` in `[1083, 59048]` with pairwise gap at least three,
and a three-cell source stub at `h(row)` prints the answer: `p` then `<` for a
1 row, `o` then `<` for a 0 row, with `A` preloaded to `'0'`.

The store is the program. `i`/`j` let the pointer revisit a cell, and a cell
whose content is the unique NOP character `f(a) = 33 + ((35 - a) % 94)` at its
address is walked over harmlessly, so the mixer inits, the navigation
constants and the stubs all live in the source. Malbolge re-enciphers every
cell it executes, so a walked-over cell's value is not `f(a)` but
`g(a) = XLAT2[f(a) - 33]`; the generator places each state and navigation cell
at the address whose `g` value it wants and computes `h` against those values.

The stub construction stops at ten inputs: no searched mixer is gap-3
injective at eleven bits (best 1836 of 2048 rows over ~40k schedules whose
full state stays distinct, and even distinct-only readouts top out at 1862),
because collisions arrive in low-trit clusters. Eleven inputs ship through a
two-level pointer cascade that needs only distinct readouts. Each row owns one
table cell at `X + 1 + k` holding one of the eight source characters the
loader admits there; the decoder runs `j`, `j`, `i`, so the character `T` names
the walked-region cell `T + 1` and that cell names the jump. Seventeen pairs
`[P0, P1]` (`P1 = rot(113)`, `P0` its 0/1-swapped twin, filled by one chained
`p` over all-1 cells) serve both answers -- `T = a - 1` reaches `P0`, whose
stub rotates `P1` into `A` (`'1'`); `T = a` reaches `P1`, whose stub prints the
preloaded `'0'` -- and 24 all-1 cells send the 256 rows the first readout
leaves in 128 pairs to a second decoder at 29525, which reads a second mixer
cell that separates all of them. The 58 pointer cells and the residue cover
(every `h mod 94` must admit a character of each label) were found by
annealing and are pinned. `n > 11` is refused with `GeneratorCapError`: the
same search finds no schedule whose two cells separate twelve bits (2400
survivors, none resolved past level 1).

Counting bounds each family, independent of how good the mixer is. A stub
program needs three cells per row at pairwise distance at least three, so
`3 * 2**n <= 59049` and `n <= 14`; the cascade needs one table cell per row
per level above its ~14k cells of code, so `n <= 15`. Neither reaches the
seventeen-input target.

That construction gap ends before totality. Malbolge has 59,049 cells and
eight valid decoded instructions at each occupied source cell -- the
decipherment cycles with the cell index, and `_XLAT1` holds each instruction
character exactly once -- hence fewer than `sum(8**k for k in range(59050)) <
2**177151` programs. There are `2**262144` truth tables on 18 inputs, and one
program computes at most one table, so some 18-input tables have no Malbolge
program. Malbolge is therefore a language exception, not merely a ceiling.

The no-`i`/`j` model is still dead. Straight-line `c == d` from the reset
state gives a `p` its own cell's instruction character, one of 94 values in
33..126, and the input pair `(49, 48)` is unreachable, so NOT is not
expressible at any length.

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Malbolge | 11 | 11 | Stubs need gap-3 readouts (none at eleven bits). The cascade needs only distinct ones; the shipped one has two levels, and over two levels the best searched twelve-bit fold resolves 3,522 of 4,096 rows and leaves 515 after both. A third level is *not* blocked by the pointer region: a four-label cover coexisting with every helper home and five init cells is SAT, and the design space closes exactly — the cover is 82 cells, the 12 free cells are unique, and four init tuples remain. What is missing is a twelve-bit mixer for it; over all four tuples the closest chain still leaves 542. |
| Polynomial | 10 | ≥11 | 1,934-instruction guard; dense n=11 is priced at 267 s and >100 MB. Parity is routed through the state machine (two states per input, ~11 instructions per level), so the guard does not bind it at ten. |

Polynomial's block-incidence lemma forces `Omega(T/log T)` distinct real
instruction-root values even when roots repeat, and the slack certificate
prices every multiple of their distinct-root product. The routing lemma that
forces those values needs the program to consume its whole input, as the
generated machines do; under that model the language bound is
`Theta(T**2 / log T)` for every cofactor and operand sign. See
[polynomial](proofs/polynomial.md). Factor has a language floor
`Omega(T log T)`, a weighted exponent-vector count on D-digit integers
([factor](proofs/factor.md)); its worst-case generated encoding is `Theta(T log T)`.

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

## Curation

The collection has 64 languages; its floor is 31. All three classics carry
generators: Befunge and Whitespace loop-less O(T) lookups, Malbolge a
source-embedded mixer through eleven inputs. They are here for coverage, not for
a new construction axis. Ordinary
imperative entries with shared-shim generators and no consumer were removed. Nopstacle and
ZTOALC L left: the former cannot meet embed conventions, the
latter was a searched syntax-level lookup table. The 2D candidate screen is
kept because re-running it is expensive: 1,543 unimplemented pages intersected
with 567 two-dimensional-language pages, then filtered to 36 by implemented
verdicts, co-categories, I/O/branch vocabulary, and 1,500-character pages.
Super SNUSP and Alight were admitted; Pinyin was rejected.

## Specification decisions

- 6-5 accepts operands beyond its specification; generators use `0..35`.
- Bitdeque `GOTO n` is zero-based: it lands on command index `n`, where the
  wiki's "Nth operation" reads one-based.  The generator's labels match this.
- BrainIf ignores a guarded line naming no command (`if 0 frobnicate`), which
  the wiki errors on; only the six named commands act.
- Jaune dispatch to an undefined marker is unspecified.
- Alight expressions are infix and left-to-right; three-argument `at` mutates.
- Packlang literals are decimal; its cat cannot receive byte 10 under
  line-oriented input.
- Pinyin is rejected: its spelling rule contradicts its examples and its
  input-1 truth-machine example has no deterministic reading.

Generated programs are evidence only after execution through their interpreter.
