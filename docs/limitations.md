# Limitations and contracts

Interpreter conventions, generator constraints, and proved limits.
See [Polynomial](proofs/polynomial.md) for its size lower bound.

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
character is build work. The input text must have:

- one ordered, constant-width run per input;
- one embed with no padded spaces;
- one uniform `(zero, one)` pair.

The template constructor enforces the shape. `tests/proofs/test_conventions.py`
checks filled programs at n=2, 3, 5.

Add a relaxed-width option only if it produces a smaller, executed build.
A space option has no remaining use. Input reordering counts toward generation
cost: at most four named candidates, with the generic greedy scorer stopping
at n=10. Generators may not use BFS or DFS; test-only oracles may.

The screen script measures permuted tables, not admissible reorders under a
fixed template and fill mapping. Dig, Flowchart, BrainIf, Sophie, and SLOW ACV
MAMMALIAN must read in order; BF-PDA uses fixed stack order. No instruction-only
wire is derived for 123 or Minifuck.

- ArrowQueue's rotations cost 19, 39, and 63 characters at k=1, 2, 3. Their
  2.1% gain misses the 5% bar, so plain order ships (d5bac32).
- Circuit Diagram gains 3.5% over four orders on the seeded five-input sample.
  A fifth, sharing-scored order reaches 5.6% but violates the cap.
- Factor subtree dispatch loses 1.0% at three inputs and gains 3.4% at five.
  Brainfuck lacks a cheaper jump, call, or label.
- 123 has one straight-line stream per row. Its table-dependent paint sweep is
  fixed by the separation laws.

Malbolge's source-embedded generator covers sixteen inputs. Through ten, a
five-cell mixer maps rows to gap-3 addresses with three-cell answer stubs.
Eleven through fourteen use collision-resolving pointer cascades; fifteen and
sixteen use positional readouts, one cell per row pair. The representative
dense, parity, constant tables were executed exhaustively at each shipped
arity. Construction details and measurements are in
[malbolge-scaling](proofs/malbolge-scaling.md).

Seventeen remains open. Executed decoder and instruction-reuse controls exist,
but no source joins the address fold, row selector and complete decoder around
an arbitrary full truth table. The shipped cap remains sixteen.

Counting bounds each family independently of mixer quality:

- stubs need three gap-3 cells per row: `3 * 2**n <= 59049`, hence `n <= 14`;
- cascades need one cell per row per level above ~9k code cells: `n <= 15`;
- last-input cells need `2**(n-1) <= 59049`: `n <= 16`.

The positional build meets the last bound. A cell answering the final two
inputs would need sixteen labels, but its address admits eight characters.
Seventeen inputs need more than two table bits per cell across almost the
whole store.

The language itself has a separate limit. Malbolge has 59,049 cells and
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
8**K < 2**131072`. Per program it is false: `'o'*59046 + '/<v'` computes
the one-input identity and every cell flips it, so only a cut over one
normal-form program per table remains open.

The no-`i`/`j` model cannot express NOT. Straight-line `c == d` from the reset
state gives a `p` its own cell's instruction character, one of 94 values in
33..126, and the input pair `(49, 48)` is unreachable, so NOT is not
expressible at any length.

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Malbolge | 16 | 16 | Stubs need gap-3 readouts (none at eleven bits); the hashed cascade through fourteen resolves collisions over up to three levels and stops where their depth outruns the decoder. Fifteen and sixteen address positionally, three bits per two-trit digit, so no row collides; that positional readout needs 65,536 row-pair cells at seventeen in a 59,049-cell store. Three-cell packing remains unintegrated ([scaling](proofs/malbolge-scaling.md)). |
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

### Malbolge sampling

`test_boolean_malbolge.py` checks stride samples (every 8th/16th/32nd row)
and every second-level cascade row. Both are needed: at eleven inputs,
corrupting `_cascade_program`’s level-0 answers fails 117 stride rows and
**0** second-level rows. Corrupting second-level answers fails 127
second-level rows and only 18 stride rows. Only the stride sample covers
the 1792 level-0 rows.

## Curation

The collection has 68 languages; its floor is 31. All seven classics carry
generators. Ordinary imperative entries with shared-shim generators and no
consumer were removed. Nopstacle could not meet the embed conventions; ZTOALC
L was a searched syntax-level lookup table. The retained 2D screen intersected
1,543 unimplemented with 567 two-dimensional pages, then filtered 36 by prior
verdicts, co-categories, I/O and branch vocabulary, and page length. It admitted
Super SNUSP and Alight and rejected Pinyin.

The alternative admission route is fame: at least 50 unique esolangs linking
pages. Resolve the candidate's title redirects, follow every `list=backlinks`
continuation, include links through redirects across all namespaces, and
deduplicate by linking page ID. Pause at least three seconds between requests.

This fixed cutoff was adopted 2026-10-01 as a prospective policy choice,
not an empirically established popularity boundary. Record the resolved title,
measurement date, and count. Missing data leaves fame unassessed, not failed.
Below 50, fame supplies no exception; intrinsic axes still apply. Low backlinks
count against only old languages. Wikipedia pageviews are not an admission gate.

Backlinks were remeasured 2026-10-01. Brainfuck scores 2,057; the former 282
counted only the first API batch. The Brainfuck-relative gates and the
indeterminate band are retired.

The seven classics score Befunge 381, Thue 155, Malbolge 129, FALSE 91,
Unlambda 89, FRACTRAN 65, and Whitespace 58; rejected Brainloller and
Braincopter score 26 and 14. Piet (65), Forth (57), Chicken (55), and
Shakespeare (54) clear the fame gate; LOLCODE (47) does not.

The fame bar is forward-only; past admissions are audited on the intrinsic
axis test.

Bitwise Cyclic Tag (181) also earned the cyclic-schedule axis. Deadfish (314)
has no input vocabulary and is therefore interpreter-only: fame can admit a
language, but cannot create a generator interface.

[Cyclic tag](https://esolangs.org/w/index.php?title=Cyclic_tag_system&oldid=156412)
(94) clears the fame gate despite duplicating Bitwise Cyclic Tag's axis.
The 2026-10-01 audit found deterministic semantics: consume one queue bit,
append the current production iff that bit is one, and advance the production
pointer cyclically. Empty data halts. No stdin or output operation is specified;
adopt BCT's initial-queue embed and final-deleted-bit answer, explicitly as
package conventions. Serialize productions with semicolons, then a comma and
the initial queue; preserve empty productions and require at least one.

A direct padding construction meets the generator contracts. For a table of
T = 2**n bits, the first n productions append 2**(n-i) zeros for input i,
numbered from zero. Production n appends `1`; the remaining 2T productions
alternate each table answer with an empty production. Initial data is the n
ordered input bits followed by `1`, with uniform one-character fills `0`/`1`.
After the inputs, the sentinel appends another sentinel behind 2r padding
zeros, where r is the input row. Those zeros skip 2r productions; the next
sentinel appends table[r], and the following empty production consumes it and
halts. This makes the final deletion the answer.

Rendered source measures exactly 5T + 2n + 1 characters; execution takes
n + 3 + 2r steps. Emission writes 2(T-1) padding zeros and 2T table productions
without search, so build work is O(T). The probe executed 309 tables and 3,352
rows (exhaustive through three inputs; constants, parity, and eight seeded
random tables at each of four through six), then sampled rows through n=14.
The largest measured source was 81,949 characters; its worst-row execution
was 32,783 steps. Published evolution, zero-no-append, empty-data, empty-rule,
and nontermination controls passed. [Roadmap](roadmap.md) queues integration.

Underload (167) and INTERCAL (103) also clear the backlink gate.
Emmental (43) and Prelude (13) are implemented elsewhere and fail the backlink
gate. Neither has established an intrinsic axis.

The 2026-10-01 fame audit covered eight absent census entries:

- [Boolfuck](https://samuelhughes.com/boof/) (76): generator follow-up.
  Bit I/O is little-endian, EOF supplies zero, and partial output bytes pad
  with zeros. Author-specified Brainfuck lowering passed 309 tables and 3,352
  rows: exhaustive through three inputs, constants, parity, and eight seeded
  random tables at each of four through six inputs. Reads consumed eight bits
  per input. Full integration and rendered linearity remain open.
- [Subleq](https://esolangs.org/wiki/Subleq) (83): generator follow-up.
  Fix a dialect with unbounded integers, direct jumps, `-1 B C` input,
  `A -1 C` byte output, and negative jumps halting. A hoisted-read decision-tree
  probe passed the same 309 tables and 3,352 rows. Its decimal addresses do
  not establish O(T) rendered size; derive a linear construction before admission.
- [///](https://esolangs.org/wiki////) (88): generator follow-up, construction
  open. There is no stdin, but `/a/$/a` with uniform one-character fills
  `0` and `1` executed identity. Escaping, truncated-rule halt, and a divergent
  replacement control were checked. This is not evidence for arbitrary tables.
- [HQ9+](https://esolangs.org/wiki/HQ9%2B) (136): interpreter-only candidate.
  No instruction reads input. `H` and `9` emit fixed non-Boolean text; `Q`
  emits source containing `Q`; `+` emits nothing. No program emits a bare
  Boolean answer. Pin greeting, lyric formatting, and case handling before integration.
- [Nope.](https://esolangs.org/wiki/Nope.) (132): interpreter-only candidate.
  `ConstantLanguage("Nope.")` ignores source and input, so neither runtime
  input nor source embeds can change its output. Accept arbitrary source,
  including empty source, under those constant semantics.
- [Unary](https://esolangs.org/wiki/Unary) (63): interpreter-only candidate
  under the generator contracts. Valid sources encode only their zero count;
  equal-width valid fill pairs are identical. Runtime input exists through
  decoded Brainfuck, but sources of length at most L supply at most L+1
  functions. Covering all 2**T truth tables requires L >= 2**T - 1 somewhere,
  precluding an O(T) generator. Pin decoded Brainfuck cell and EOF semantics.
- [大白话](https://esolangs.org/wiki/大白话) (134): deferred. The command table is
  explicitly partial; expression precedence, complete block grammar, library
  semantics, and embedded-language dispatch are unspecified. A restricted
  implementation would need a separately documented dialect, not invented semantics.
- [Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution)
  (112): excluded as a family, not a single language. Its backlink count
  does not establish fame for any particular member.

The 2026-09-27 spec read closed the other candidates:

- Self-replicating marbles leaves section order and collision timing undefined.
- Wirefunge leaves initialization open and duplicates thisthat's gates.
- Bytemap leaves byte order, division faults, and optional 8bpp undefined.
- Gifunk defines motion through APNG/GIF frames but no instructions.
- Turing Paint and Befunk are obscure but already implemented.

The 2026-10-01 non-text screen deferred [BOOMOP](https://esolangs.org/wiki/BOOMOP):
its entry/termination brightness metric, face selection at ray-edge hits, and
equal-distance teleport anchors are unspecified. Character I/O is explicit;
generator feasibility remains unaudited pending routing clarification.

HuePrism, BitCode, PicCode, Brainloller, Braincopter, and the game-save
languages remain rejected from the same image-source screen.

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
  Prime-power products (`2^3*5` is 40) abbreviate starting values that would
  otherwise need thousands of decimal digits.
- Thue is nondeterministic by specification -- the rule *and* the position are
  drawn at random through the shared `randomness` hook. A fixed tie-break
  would change overlapping-rule programs; `--seed` makes the draws repeatable.
  The generator writes rules that never overlap,
  so each state it reaches has exactly one rewrite and the draw cannot change
  the answer; `tests/tools/test_boolean_classics.py` asserts that over every
  table to three inputs, and checks the answer under three seeds and the
  unseeded draw.
- Unlambda's `@` reads a line and takes its first character, an empty line
  giving a newline, since the package has no character stream.
  At EOF, `@` catches the port’s `EOFError` (also caught by nine other
  interpreters), hands its argument `v`, and leaves the current character
  unchanged. `v` absorbs its arguments, so the failure arm cannot execute
  its own code.
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
