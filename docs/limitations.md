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

Malbolge registers a source-embedded generator through fourteen inputs. A
five-cell mixer and gap-three stubs cover ten; pointer cascades and selected
inputs extend it to fourteen. All rows of the dense, parity, all-zero, and
all-one tables were executed at each shipped arity. Larger inputs raise
`GeneratorCapError`; the measured fifteen-input cascade does not fit. See
[malbolge-scaling](proofs/malbolge-scaling.md) for the construction and failed
routes.

Malbolge is a language exception, not just a generator cap. Its 59,049 cells
and eight decoded instructions give fewer than `2**177148` programs, versus
`2**262144` truth tables at eighteen inputs. Seventeen remains open: counting
misses by `2**46076`, while executed counterexamples kill the simple length,
alphabet, and per-program dependence cuts. The live route is a normal-form
dependence bound, recorded in [roadmap](roadmap.md).

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Malbolge | 14 | 14 | Fifteen's eight-copy cascade resolves every row but does not fit ([measured](proofs/malbolge-scaling.md#fifteen-the-eight-copy-cascade-measured)). |
| Polynomial | 10 | ≥11 | 1,934-instruction guard; dense n=11 is priced at 267 s and >100 MB. Parity is routed through the state machine (two states per input, ~11 instructions per level), so the guard does not bind it at ten. |

Polynomial's block-incidence lemma forces `Omega(T/log T)` distinct real
instruction-root values even when roots repeat, and the slack certificate
prices every multiple of their distinct-root product. The routing lemma that
forces those values holds for every read count, so the language bound is
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

FRACTRAN's row-addressing tree costs `Theta(T log T)`, but that is not a
language floor. The shipped generator packs `w = Theta(n)` entries into an
exponent and pays for `3T / w` addresses, giving `Theta(T)` text and
`O(2**w)` execution. At n=12 it emits 8.93 characters per entry versus 23.6
for the tree; same-parity difference ratios satisfy the contract from n=6.
The construction, counting floor, and time tradeoff are in
[fractran](proofs/fractran.md) and `tests/proofs/deep/fractran_packed.py`.

The execution contract in `tests/proofs/deep/execution.py` holds every
generator's command count linear. Bracket matching is precomputed at load.
Persistent stores use shared 32-cell chunks; RAM0 also indexes addresses.
Those choices prevent repeated scans, but command cost and source size remain
separate axes.

## Curation

The collection has 68 languages; its floor is 31. All seven classics carry
generators. Ordinary imperative entries with shared-shim generators and no
consumer were removed. Nopstacle could not meet the embed conventions; ZTOALC
L was a searched syntax-level lookup table. The retained 2D screen intersected
1,543 unimplemented with 567 two-dimensional pages, then filtered 36 by prior
verdicts, co-categories, I/O and branch vocabulary, and page length. It admitted
Super SNUSP and Alight and rejected Pinyin.

The alternative route measures fame by esolangs backlinks and by an English
Wikipedia article with 90-day pageviews, sampled 2026-09-27. A candidate may
clear either proxy; low backlinks count against only old languages.

Brainfuck anchors the backlink bar at 282: `bf/5` (56) is sufficient, `bf/10`
(28) carries nothing, and the axis test decides between them. The decided
classics score 58--271; rejected Brainloller and Braincopter score 26 and 14.
The band is intentionally indeterminate: Chicken 0.199, Shakespeare 0.195,
and LOLCODE 0.167 fall inside it. A population percentile cannot replace the
ratio: a fixed sample of 150 language pages had p99=20, below both rejected
image languages.

The fame bar is forward-only; past admissions are audited on the intrinsic
axis test.

Bitwise Cyclic Tag (0.66) also earned the cyclic-schedule axis. Deadfish (0.89)
has no input vocabulary and is therefore interpreter-only: fame can admit a
language, but cannot create a generator interface.

Cyclic tag 0.35 duplicates the Bitwise Cyclic Tag axis.
Emmental 0.15 and Prelude 0.05 are implemented elsewhere but do not clear the
fame bar, so neither admission route applies.

The 2026-09-27 spec read closed the other candidates. Self-replicating marbles
does not define which section is next or when collisions occur. Wirefunge's
draft leaves element initialization open, and its gates duplicate thisthat.
Bytemap leaves byte order,
division faults, and its optional 8bpp encoding undefined. Gifunk specifies no
instructions beyond moving through APNG/GIF frames. Turing Paint has a complete
reference implementation, and Befunk implements Befunge-98 in PNG; both are
obscure but already implemented, so neither admission route applies. HuePrism,
BitCode, PicCode, Brainloller, Braincopter, and the game-save languages remain
rejected from the same image-source screen.

## Specification decisions

- 6-5 accepts operands beyond its specification; generators use `0..35`.
- FALSE's `ø` pick counts from zero, so `0ø` is `$`; the description ("dup
  the nth stack item") does not say where the count starts.  Reading a
  variable before storing it raises rather than inventing a value, and a
  character that is no command is ignored the way whitespace is -- the spec
  states neither.  Integers wrap to signed 32 bits (the spec's width) and `/`
  truncates toward zero, and `O` is accepted as an ASCII spelling of the
  non-ASCII `ø`.  `^` answers the spec's `-1` at end of input, which
  the shell reaches by catching the port's `EOFError`: raising instead made
  the reference's own cat loop, which tests `^` against `-1`, a crash.
- FRACTRAN has no I/O in the language, so this package reads the starting
  value from the source's first token and prints the value the run stops on.
  A token may be written as a product of prime powers (`2^3*5` is 40), which
  is notation only: it is how a generated starting value spells thousands of
  digits without spelling them.
- Thue is nondeterministic by specification -- the rule *and* the position are
  drawn at random -- and the interpreter draws, through the shared
  `randomness` hook, rather than pinning a tie-break: a pinned one would make
  every overlapping-rule program compute whatever this package preferred.
  `--seed` fixes it.  The generator instead writes rules that never overlap,
  so each state it reaches has exactly one rewrite and the draw cannot change
  the answer; `tests/tools/test_boolean_classics.py` asserts that over every
  table to three inputs, and checks the answer under three seeds and the
  unseeded draw.
- Unlambda's `@` reads a line and takes its first character, an empty line
  giving a newline, since the package has no character stream.  Both spec
  branches are live: at end of input `@` hands its argument `v`, reached by
  catching the port's `EOFError` as nine other interpreters here catch it, and
  the current character is left as it was.  `v` absorbs its arguments, so the
  failure arm can run nothing of its own -- that is the language, not this
  port.
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
