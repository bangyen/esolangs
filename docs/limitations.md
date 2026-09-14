# Limitations and contracts

## Interpreter conventions

- Empty input is a no-op unless a language requires a seed or grid.
- Exhausted input raises `EOFError` unless the language specifies a sentinel.
  Malformed programs raise `ValueError`; runtime failure raises `HaltError`.
- Character input is line-delimited. A blank line is the package convention
  for `0`; it is not inferred from any language specification.
- Explicit frame stacks are uncapped. Forbin expression-position calls retain
  their documented host-recursion limit.
- Streetcode's four-way junction is an implementation convention: the wiki
  only specifies a choice between two roads, and its examples exercise none.

## Source positions

`esolangs debug --tui` marks only a source position. `ip_shape` is `offset`
(45 languages), `grid` (11), `line` (2), or `opaque` (7); undeclared tuple
positions are refused. `opaque` positions have no program mark.

Line extraction accepts anti-aliased PNGs while strokes retain a connected dark
core; the 3px scan fixture executes addition correctly. A one-third-pixel shift
of a 1px stroke followed by resampling erases that core and is rejected with 921
unaccounted pixels rather than returning a different program.

## Boolean generators

Parameterized generators embed inputs in the program. `%^2^-1` cannot compute
a two-input function from runtime input. Its screened reorder requires a
permuted template or fill mapping; with both fixed, interleaving only lengthens
the identity template. Input reordering has no useful effect on Alight,
Container, Grapheme, Home Row, or Packlang; do not reopen this with a
blind search.

`scripts/screen_input_reorder.py` measures the size of permuted-table builds,
not an admissible reorder under the fixed input-template and fill contract.
Interprogck8, Dig, Flowchart, BrainIf, Sophie, and SLOW ACV MAMMALIAN must test
stream inputs in read order; BF-PDA must consume its fixed stack order. No
instruction-only wire is derived for 123, Minifuck, WII2D, or COD. ArrowQueue's
conditional re-enqueue route remains open.

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Interprogck8 | 10 | 10 | Cost policy: dense n=11 builds only with 1,445 repairs and a 1.2 MB program. |
| Polynomial | 10 | 10 | 1,934-instruction guard; dense n=11 is 124 MB and runs in 267 s. |
| WII2D | 9 | 10 | Dense n=10 conflicts with the exactly-once embedding convention. |
| ZTOALC L | 10 | 10 | n=11 needs 545–587 command slots; the line ceiling admits at most 395. |

WII2D n=9 is partial: 37 of 64 sampled dense tables build and the rest refuse
promptly. Its magnitude guard is load-bearing. A per-node re-embed tree can
build dense n=13, but is outside the generator contract.

Uncapped dense-program sizes at n=8/n=9: Polynomial 3.38/10.90 MB, COD
0.94/3.67 MB, SLOW ACV MAMMALIAN 1.67/3.38 MB, Circuit Diagram 0.15/0.32 MB,
123 0.09/0.23 MB, ROTfuck 0.02/0.03 MB, bit~ 0.03/0.06 MB, Factor
0.02/0.04 MB. Run generated programs before claiming size or equivalence.

Two current constructions are structurally super-linear.  On A Painter Ant
parity every subtree is live.  At each of `n` depths, `_head` traverses
`2**(d+1)` child edges of length `2**(n-d)` out and back: `4T` movement
characters per depth, hence Theta(T log T).  In 123, `_phase_a` uses the tight
marks `(i+1)*2T+1` and emits Theta(mark) movement four times for every input;
their sum is Theta(T (log T)^2).  These prove bounds on the shipped
constructions, not on either language; a different geometry could evade them.
Circuit Diagram's current layout is likewise Theta(T log T) on parity: all
`n` selector rails remain live across Theta(T) columns.  Localizing each rail
to its mux level remains an open route around that construction bound.
COD's leaf cascade is Theta(T^2): each of T leaf rows contains a prefix of
length `3(k+1)` and a gate tail of length `2(T-k-1)`, so every row is
Theta(T) and rotation cannot change the number of cells.  A non-cascade
decoder is required for linear output.
Minifuck's fixed mux has a quadratic spelling mechanism: row `i`, when fired,
rewinds across Theta(T-i) cells and spells both `<` and `[x` for that distance.
Its derived parity plans fire 131/247/497 rows with rewind sums
17,192/63,473/261,565 at n=8/9/10.  Dense n=8/9 measures 58,594/221,305
characters and parity 57,601/203,089.  These executed measurements expose the
mechanism but are not an asymptotic proof; a shared or packed sculpt remains
open.

## Curation

The collection has 60 languages. The floor is 31: the languages that own a
generator construction, Polynomial and Modulous for their walls, and
brainfuck for Factor's decoder. The 69→65 cut removed DINAC, MyScript,
Basicfuck, and Nevermind: ordinary imperative languages with shared-shim
generators and no downstream consumer. The second band removed Suptiftam,
Lamfunc, `function x(y)`, Between, and Point Break on the same criterion.

## Specification decisions

- 6-5 accepts operands beyond its specification; generators use `0..35`.
- Jaune's dispatch to an undefined marker is unspecified.
- Alight expressions are infix, left-to-right; three-argument `at` mutates.
- Packlang numeric literals are decimal. Its cat cannot receive byte 10 under
  this package's line-oriented input model.
- Pinyin is rejected: its spelling-to-pronunciation rule contradicts its own
  examples, and its truth-machine input-1 example has no deterministic reading.

Generated programs are evidence only after execution through their interpreter.
