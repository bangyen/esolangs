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
character is build work. Reordering is optional around a construction, but
its selection cost counts; named candidates are capped at four and the generic
greedy scorer stops at n=10. Generator constructions may not use BFS or DFS;
test-only oracles may.

The screen script measures permuted-table builds, not an admissible reorder
under a fixed input template and fill mapping. Dig, Flowchart,
BrainIf, Sophie, and SLOW ACV MAMMALIAN must read streams in order; BF-PDA uses
its fixed stack order. No instruction-only wire is derived for 123 or Minifuck.
ArrowQueue re-enqueue remains open.

Malbolge registers a generator through nine inputs, source-embedded with no
initializer. A branch-free four-cell mixer (`p,p,p,p,p,p,p,p,r`, inits
52/88/34/77) folds the row index into a distinct address `h(row)` in
`[9828, 59034]` with pairwise gap at least three, and a three-cell source stub
at `h(row)` prints the answer: `p` then `<` for a 1 row, `o` then `<` for a 0
row, with `A` preloaded to `'0'`.

The store is the program. `i`/`j` let the pointer revisit a cell, and a cell
whose content is the unique NOP character `f(a) = 33 + ((35 - a) % 94)` at its
address is walked over harmlessly, so the mixer inits, the navigation
constants and the stubs all live in the source. Malbolge re-enciphers every
cell it executes, so a walked-over cell's value is not `f(a)` but
`g(a) = XLAT2[f(a) - 33]`; the generator places each state and navigation cell
at the address whose `g` value it wants and computes `h` against those values.

The generator caps at nine inputs. A ten-input map needs a depth-one branch on
one bit, and the two branch values `crazy(48, V)` and `crazy(49, V)` differ
only in di-trit 0; every `p` chain preserves that difference, so the targets
stay adjacent and cannot address two separated code copies. Lifting the
difference into a high di-trit needs a rotation of `A`, but `*` rotates
`memory[d]`, not `A`: rotating `A` needs the store the old note called the
operand builder. `n > 9` is refused with `GeneratorCapError`.

The no-`i`/`j` model is still dead. Straight-line `c == d` from the reset
state gives a `p` its own cell's instruction character, one of 94 values in
33..126, and the input pair `(49, 48)` is unreachable, so NOT is not
expressible at any length.

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Malbolge | 9 | 9 | The ten-input branch's two targets stay adjacent; separating them needs a run-time store. |
| Polynomial | 10 | 10 | 1,934-instruction guard; dense n=11 is priced at 267 s and >100 MB. |

Polynomial's mandatory root product has minimum mass at the product itself;
for programs whose real instruction roots are distinct the slack certificate
proves `Theta(L**2 log L) = Theta(T**2 / log T)` digits for every multiple,
cofactor, and operand sign. Repeated real roots are legal (`(x-2)^3` decodes to
three `[1]` instructions) and that theorem does not cover them, so the general
language bound is open -- the one missing lemma is named in
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

The collection has 62 languages; its floor is 31. All three classics carry
generators: Befunge and Whitespace loop-less O(T) lookups, Malbolge a
source-embedded mixer through nine inputs. They are here for coverage, not for
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
- Jaune dispatch to an undefined marker is unspecified.
- Alight expressions are infix and left-to-right; three-argument `at` mutates.
- Packlang literals are decimal; its cat cannot receive byte 10 under
  line-oriented input.
- Pinyin is rejected: its spelling rule contradicts its examples and its
  input-1 truth-machine example has no deterministic reading.

Generated programs are evidence only after execution through their interpreter.
