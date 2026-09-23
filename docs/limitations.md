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

Malbolge registers a generator through thirteen inputs, source-embedded with no
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
annealing and are pinned.

Twelve inputs ship without a twelve-bit mixer. The fold above runs over the
first eleven; then `/` reads the twelfth and `p` writes it into a selector
cell. The crazy operation and `*` act trit by trit, so the two values of a
selector differ in one trit, and ten searched ops park that trit at the top:
each selector's two values lie 19,683 apart. `i` through the first selector
runs one of two level-1 *paths* stored at those addresses -- code that is
jumped to, never walked. A path may rewrite the readout and picks its own
table offset, so the halves land on different cells: `x = 0` reads cell 0 as
the eleven-input build does, `x = 1` reads `neg(cell 0)` (`p` with
`A = all-2` negates every trit) 543 cells on, and 560 of the 4,096 rows
collide at level 1 against 512 at eleven inputs doubled. The decoder selects
through the second selector the same way, and each level-2 path runs its own
searched post-map that separates its half's colliding rows. The labels and
the `[P0, P1]`/NEXT layout are unchanged. Executed on all 4,096 rows of the
dense, parity, all-0 and all-1 tables.

Thirteen inputs keep that build and hand the last input to the answer stub.
A table cell now names one of four answers as a function of it -- `0`, `1`,
`x` or `not x` -- or `N`, so every residue needs five of its eight
characters. The `[P0, P1]` pairs and NEXT runs cannot afford that (CP-SAT:
infeasible with only the mixer blocked), so every label is a single pointer
cell and the decoder takes one more hop: `j` to the table cell, `j` to its
pointer cell `T + 1`, `j` to the *hub* `V + 1` that cell names, `i` through
the hub. `d` is then `V + 2` on every row, so a stub may read the source
characters after its hub. The pointer region holds only the 89 label cells
and the mixer; helpers, selectors and seeds move to walked cells above 127,
and navigation becomes a shortest path over `o` and `j` through every cell of
known value, which also brings the main code down from 15,398 cells to 9,677.
A label's cells are one chained `p` over all-1 cells from a rotated walked
seed, so they hold `s` and `f(s)` alternately and ten hubs serve five labels;
each hub holds a source character rotated until it names a free stub. The
`1` stub runs `p` over the two characters after its hub. No run of one to
three `p` over source characters swaps `'0'` and `'1'`, so the `not x` stub
runs two and then, through a third character that names a pointer cell, a
third over that cell's chain value. Executed on all 8,192 rows of the dense,
parity, all-0 and all-1 tables. `n > 13` is refused with `GeneratorCapError`:
fourteen needs sixteen two-input answers against a cell's eight characters,
or a second selector, and that is where splitting stalls.

Splitting a second input off stalls at level 2, not at the fold. Two inputs off
gives four level-1 copies (only identity, `neg`, `rot**2` and `neg rot**2`
clear the code), and 1,755 of 8,192 rows collide; but no searched level-2
post-map puts a half's 375-530 rows on distinct cells clear of the 8,192
level-1 ones (the one distinct readout found lands 270 of them on level-1
cells). A per-bit branching fold resolves more at level 1 (7,052 of 8,192)
but makes the level-1 cells random, which is worse for avoidance. Sharing
cells instead -- the decoder reading a character's label `k` cells further
on -- needs all four answer pairs at a shared cell's residue, and CP-SAT
proves at most 10 of 94 residues can offer them (0 at `k = 1`, 7 at 2 and
3, 10 at 5).

A third level needs no fourth label, which is what the layout could not
afford. A level-2 row whose table cell carries `N` re-enters the decoder at
29525 with `d = b + 1`, and the cells it already executed have been
re-enciphered: the first nine image to nops and the tenth to an `i`, so every
level-3 row shares one jump through `mem[b + 10]`. Executed on the shipped
build: row 800 of the all-zero table prints `0`, and the same row routed
through the `N` label for cell 95 reads `mem[105]` -- a shipped `[P0, P1]`
pair -- and prints `1`. Three labels plus an `M` block are SAT once the block
clears the pointer region (unsat at shift 10 through 20, sat from 40, 9 cells
free at shift 94), and a shift-104 prefix is spellable: of the first 103
re-entry cells only nine refuse a plain `o`, and each takes `j`, `p` or `*`.
What is missing is still a twelve-bit mixer. Three levels with free inits
leave 341 of 4,096 rows over ~7 CPU-hours (0 hits, control rediscovers the
shipped n=11 cascade), against 515 for two levels.

Counting bounds each family, independent of how good the mixer is. A stub
program needs three cells per row at pairwise distance at least three, so
`3 * 2**n <= 59049` and `n <= 14`; the cascade needs one table cell per row
per level above its ~14k cells of code, so `n <= 15`. Neither reaches the
seventeen-input target.

That construction gap ends before totality. Malbolge has 59,049 cells and
eight valid decoded instructions at each occupied source cell -- the
decipherment cycles with the cell index, and `_XLAT1` holds each instruction
character exactly once -- hence fewer than `sum(8**k for k in range(59050)) <
2**177148` programs. There are `2**262144` truth tables on 18 inputs, and one
program computes at most one table, so some 18-input tables have no Malbolge
program. Malbolge is therefore a language exception, not merely a ceiling.

Seventeen -- the registry target -- needs the count under `2**131072`, a
factor `2**46076` below it, and counting does not get there. A length cut
needs every answer to rest inside the first 43,690 cells, but cell 58,967
alone flips row 299 at ten inputs (`0` against `1`, both executed). An
alphabet cut needs 4 of the 8 characters at a cell to matter: single cells
realise 5 to 8 distinct behaviours (12 of 20 sampled walked-code cells at 5 or
more), and an every-line cap of `k` buys `log2(8/k)` bits in all -- one bit at
`k = 4`. What is left is a dependence cut: every table-computing program's
answer resting on at most 24,434 cells, the largest `K` with `C(59049, K) *
8**K < 2**131072`. That one is open.

The no-`i`/`j` model is still dead. Straight-line `c == d` from the reset
state gives a `p` its own cell's instruction character, one of 94 values in
33..126, and the input pair `(49, 48)` is unreachable, so NOT is not
expressible at any length.

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Malbolge | 13 | 13 | Stubs need gap-3 readouts (none at eleven bits). The cascade needs only distinct ones; twelve inputs split the last one off it through a selector, so no mixer ever folds twelve bits, and thirteen let the answer stub read the last input, so a table cell names one of four one-input answers. Fourteen needs sixteen answers against a cell's eight characters, or a second selector, whose four level-1 copies leave no level-2 post-map room. |
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
source-embedded mixer through thirteen inputs. They are here for coverage, not for
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
