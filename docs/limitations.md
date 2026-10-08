# Limitations and contracts

Interpreter conventions, generator constraints, and proved limits.
See [Polynomial](proofs/polynomial.md) for its size lower bound.

## Interpreter conventions

- Empty input is a no-op unless a language requires a seed or grid.
- Exhausted input raises `EOFError`; malformed programs raise `ValueError`;
  runtime failure raises `HaltError`, unless the language says otherwise.
- Character input consumes Unicode characters, including newlines. Integer
  input consumes whitespace-delimited signed decimal tokens. Unsquare, Decleq,
  AddSubJump and Minifuck use Unicode character codes where input framing is
  unspecified; Decleq’s optional memory-mapped I/O is enabled.
- Explicit frame stacks are uncapped. Forbin expression calls retain their
  documented host-recursion limit.
- Streetcode's four-way junction is an implementation convention: the source
  specifies only a two-road choice.

<!-- RASTER-SOURCES:START -->

Line, Piet and Piet++ carry a raster source: `generate` returns an
`esolangs.raster.Raster`, `run` takes it or a PNG path through the shared
codec, and `describe` reports `source_kind="raster"`.

<!-- RASTER-SOURCES:END -->

Text and raster share VM and step contracts; `RUNNERS` describes text
bundling only. Line retains its graph for repeated generated rows, and
stepping parses pixels; the other raster languages emit and execute pixels.

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

Every path reads all n inputs in order; an ignored input is read and
discarded, never left unread. Leaving a trailing ignored input unread would
save 9-29% at n=7..8 on Sophie, Unlambda, Brainfuck and Factor, but would make
a program's input consumption depend on the table.

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
  2.1% gain misses the 10% bar, so plain order ships (d5bac32).
- Circuit Diagram's default path builds the identity order: four orders save
  8.48% of area at n=7, under the 10% bar. Width requests still try four.
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

Seventeen remains open. A prepared complete query and separate legal-source
initialization and handoff components pass exhaustive input controls, but no
source installs the query and relocates obstructed records around an arbitrary
full truth table. The handoff's existing continuation corrupts a saved parity
word. See [the controls](proofs/malbolge-scaling.md#native-input-and-prepared-query-controls-2026-10-08).
The shipped cap remains sixteen.

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
the generated program. A generator guarantees its size class, not its
constant; constant-factor tweaks beyond the canonical set ship only at 10% or
more where they run (`docs/CONTRIBUTING.md`). Execution measurements exclude loading and use the
worst sampled parity row. A sub-10 ms run does not establish an exponent.
Loading dominates Factor (integer factorization) and Circuit Diagram (parsing
super-linear area); it is intentionally excluded from execution time.

FRACTRAN's row-addressing tree costs `Theta(T log T)`, but that is not a
language floor. The shipped generator gives equal subtables one state, so
it names `O(T / log T)` primes of `O(log T)` digits: `Theta(T)` text, and at
most `n + 1` fractions fire a run. At n=12 it emits 3.81 characters per entry
versus 23.6 for the tree. The construction and the counting floor are in
[fractran](proofs/fractran.md) and `tests/proofs/deep/fractran_shared.py`.

The execution contract in `tests/proofs/deep/execution.py` holds every
generator's command count linear. Bracket matching is precomputed at load.
Persistent stores use shared 32-cell chunks; RAM0 also indexes addresses.
Those choices prevent repeated scans, but command cost and source size remain
separate axes.

`scripts/screens/resources.py` checks Sophie, BFStack and Subleq on 96 tables
and all 6,120 rows through eight inputs. The benchmark reports UTF-8 source
bits, hidden control stacks, signed integer widths and the simultaneous peak
of data, control, cursor and machine flags. Separate peaks need not coincide.
Python overhead, static parser indexes and I/O state are excluded. At eight
inputs the sampled peak machine payloads are 18, 756 and 3,066 bits respectively;
these are measurements, not language-wide space bounds. Construction bounds
are asserted in the screen and controlled by `tests/proofs/test_resource_bounds.py`.

### Malbolge sampling

`test_boolean_malbolge.py` checks stride samples (every 8th/16th/32nd row)
and every second-level cascade row. Both are needed: at eleven inputs,
corrupting `_cascade_program`’s level-0 answers fails 117 stride rows and
**0** second-level rows. Corrupting second-level answers fails 127
second-level rows and only 18 stride rows. Only the stride sample covers
the 1792 level-0 rows.

## Curation

<!-- COLLECTION-SIZE:START -->

The collection has 83 languages.

<!-- COLLECTION-SIZE:END -->

Its floor is 31, and all ten classics have generators. Removed: unused
ordinary imperative entries with shared-shim generators; Nopstacle for
incompatible embeds; ZTOALC L for a searched syntax-level lookup table. The 2D screen intersected
1,543 unimplemented with 567 two-dimensional pages, then filtered 36 by prior
verdicts, co-categories, I/O and branch vocabulary, and page length. It admitted
Super SNUSP and Alight and rejected Pinyin.

Fame admits languages with at least 60 unique esolangs linking pages. Resolve
title redirects, exhaust `list=backlinks` continuations, include redirect links
across all namespaces, and deduplicate by page ID. Pause at least three seconds
between requests.

The cutoff is policy, adopted 2026-10-01, not a measured popularity boundary.
Record resolved title, date and count; missing data means unassessed. Low
backlinks count against only old languages; Wikipedia pageviews are not a
gate.

Below 60, a language is admitted only as a first implementation: when the
repo adds it, no implementation exists but the maintainer's. Its page is in
the Unimplemented category, or the edit that first tagged it Implemented is
User:Bangyen's. An intrinsic axis can choose between such candidates; it
admits nothing alone and removes nothing. A stalled generator row moves to
the [roadmap](roadmap.md#parked)'s Parked section; the language stays.

Recognition sources checked 2026-10-01 supply selections, not admission gates
or popularity rankings:

- [Kneusel, *Strange Code* (2022)](https://nostarch.com/strange-code):
  named esolang chapters cover FRACTRAN, Piet, Brainfuck, and Befunge.
  Filska and Firefly are the author's own creations; Forth, SNOBOL, and CLIPS
  belong to the separate atypical-language section.
- [Morr, *Esoteric Programming Languages*](https://blinry.org/esolangs/esolangs.pdf):
  selects Brainfuck, INTERCAL, Befunge, Malbolge, and Shakespeare as iconic
  examples with different properties, not an exhaustive canon.
- [LMU teaching notes](https://cs.lmu.edu/~ray/notes/esolangs/): a brief themed,
  theoretical, golfing, multidimensional, and difficulty-oriented tour.
  Selects LOLCODE, Glowup Vibes, ArnoldC, Chef, Shakespeare, Rockstar,
  Brainfuck, Binaryfuck, Lenguage, GolfScript, Pyth, CJam, Jelly, 05AB1E,
  Vyxal, Befunge, AsciiDots, Piet, Whitespace, Unreadable, and Malbolge.
- [Esolang featured archive](https://esolangs.org/w/index.php?title=Esolang:Featured_languages&oldid=161213):
  administrator-selected features: Thue, Funciton, Brainfuck, Deadfish,
  Emmental, Malbolge, Glass, and ///. Features are not popularity endorsements.

The 2026-10-01 count gives Brainfuck 2,057 backlinks; 282 counted only the first
API batch. Brainfuck-relative gates and the indeterminate band are retired.

The classics score Befunge 381, Underload 167, Thue 155, Malbolge 129,
INTERCAL 103, FALSE 91, Fish 91, Unlambda 89, Smallfuck 66, and FRACTRAN 65;
rejected Brainloller and Braincopter score 26 and 14. Piet (65) clears the
fame gate; Whitespace (58),
Forth (57), Chicken (55), Shakespeare (54), and LOLCODE (47) do not.

Existing fame exceptions must still clear the bar. Whitespace was removed at
58 backlinks.

<!-- CURATION-CENSUS:START -->

The 2026-10-06 census (`tests/fixtures/curation.toml`) records each
language's backlinks and route: 21 clear the fame gate,
56 are first implementations and 6 are grandfathered.

<!-- CURATION-CENSUS:END -->

The grandfathered languages were implemented elsewhere when added, all
before the rule was written down on 2026-09-27: BIO (ais523), BF-PDA (Madk,
2010), 123 (a 2012 VB.NET interpreter), NoComment, Sophie (their authors')
and Jaune (two others'). Befunge-98 (Funge-98, 31, two
dozen implementations) came after and was removed on 2026-10-06.

A route admits a language only when its specification fixes the core
semantics. 3D Brainfuck was removed on 2026-10-06: its page never says how
a linear source places blocks in the grid or what the generation pointer
does, so its interpreter invented the core, the invented semantics the
大白话 deferral rules out. Transistor (2) was built and dropped on
2026-10-07 for the same reason: its page gives no grammar and no I/O, and
its one loop example calls an undefined `or`.

Piet++ (8) is a first implementation: the page is in the Unimplemented
category, and the only other code is a partial C# executor (Esolang-NET/Piet)
whose Read, Write and Roll-Context are no-ops, so it cannot arbitrate the
conventions below.

Bitwise Cyclic Tag (181) also adds the cyclic-schedule axis. Deadfish (315)
is interpreter-only because it has no input vocabulary.

[Cyclic tag](https://esolangs.org/w/index.php?title=Cyclic_tag_system&oldid=156412)
(94) clears the fame gate despite duplicating Bitwise Cyclic Tag's axis.
The 2026-10-01 audit pins consume-one-bit semantics: append the current
production iff the bit is one, then advance cyclically; empty data halts.
With no specified I/O, the package adopts BCT's initial-queue embed and
final-deleted-bit answer. Serialize productions with semicolons, then a comma
and the initial queue; preserve empty productions and require at least one.

For T = 2**n, productions i = 0..n-1 append 2**(n-i) zeros; production n
appends `1`. The remaining 2T productions alternate table bits with empty
productions. Initial data embeds the n ordered bits with uniform `0`/`1` fills,
then `1`. For row r, the inputs leave 2r zeros before a new sentinel; those
zeros skip 2r productions, and the sentinel appends table[r]. The next empty
production consumes the answer and halts.

Source is exactly 5T + 2n + 1 characters; execution takes n + 3 + 2r steps.
Emission writes 2(T-1) padding zeros and 2T table productions without search:
O(T) build work. Tests execute 309 tables and 3,352 rows, exhaustive through
three inputs, then constants, parity and eight seeded random tables per arity
four through six. Probes sampled through n=14: at most 81,949 characters and
32,783 steps. Published evolution, zero-no-append, empty-data, empty-rule and
nontermination controls passed.

Underload (167) and INTERCAL (103) also clear the backlink gate.
Emmental (43) and Prelude (13) are implemented elsewhere and fail the backlink
gate. Neither has established an intrinsic axis.

The 2026-10-01 fame audit covered eight census candidates:

- [Boolfuck](https://samuelhughes.com/boof/) (76): integrated with a
  native decision tree over single-bit cells. Each input byte's low bit is
  read onto its own cell and tested in place, with one flag interleaved
  beside each bit, so every node costs O(1) commands and rendered size
  stays linear in T. Little-endian bit I/O supplies zero at EOF and pads
  partial output bytes.
- [Subleq](https://esolangs.org/wiki/Subleq) (83): integrated with unbounded
  integers, direct jumps, `-1 B C` byte input (EOF raises), `A -1 C` byte
  output, and negative jumps halting. The shared packed decoder stores
  T/n chunks of n bits, with O(n) read instructions: O(T) rendered text.
- [///](https://esolangs.org/wiki////) (88): integrated with ordered
  one-character `a`/`b` embeds. Binary-to-unary substitutions form the row
  index; 2^m fixed sweeps, for the m inputs the table depends on, consume
  that many two-character table entries.
  Escaped future patterns prevent earlier sweeps corrupting later rules.
  The selected entry becomes 0/1 and the suffix is deleted. Source is
  exactly 20*2^m + n + 53 characters, plus k + 10 for k = n - m > 0
  ignored inputs; build work is O(T).

Each uses the same 309-table, 3,352-row corpus as Cyclic tag. Dense size-difference
ratios at n=8,10,12 are 3.997 (Cyclic tag), 3.903 (Boolfuck), 2.926 (Subleq)
and 4.000 (///). The constructions supply the bounds; these ratios are measurements.

- [HQ9+](https://esolangs.org/wiki/HQ9%2B) (136): interpreter-only.
  No instruction reads input. `H` and `9` emit fixed non-Boolean text; `Q`
  emits source containing `Q`; `+` emits nothing. No program emits a bare
  Boolean answer. Output formatting and case are pinned in the interpreter.
- [Nope.](https://esolangs.org/wiki/Nope.) (131, 2026-10-03): interpreter-only.
  `ConstantLanguage("Nope.")` ignores source and input, so neither runtime
  input nor source embeds can change its output. Accept arbitrary source,
  including empty source, under those constant semantics.
- [Unary](https://esolangs.org/wiki/Unary) (63): interpreter-only under the generator
  contracts. Valid sources encode only their zero count; whitespace formatting
  does not evade that bound. Runtime input exists through
  decoded Brainfuck, but sources of length at most L supply at most L+1
  functions. Covering all 2**T truth tables requires L >= 2**T - 1 somewhere,
  precluding an O(T) generator. Decoded Brainfuck uses wrapping bytes,
  a tape growing in both directions and zero at EOF, as its cat example
  requires.
- [大白话](https://esolangs.org/wiki/大白话) (134): deferred. The command table is
  explicitly partial; expression precedence, complete block grammar, library
  semantics, and embedded-language dispatch are unspecified. A restricted
  implementation would need a separately documented dialect, not invented semantics.
- [Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution)
  (112): excluded as a family, not a single language. Its backlink count
  does not establish fame for any particular member.

The 2026-09-27 audit closed these candidates:

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
- Unlambda's `@` reads a Unicode character, including newlines. At EOF,
  it hands its argument `v` and clears the current character; `?x` and `|`
  then take their no-character branch.
- Bitdeque `GOTO n` counts from 1, as the wiki's "the Nth operation" reads;
  a target past the last command halts and a taken `GOTO 0` raises, both
  unstated on the wiki. The generator's labels match this.
- Brainfuck uses wrapping bytes, a tape growing in both directions and EOF
  errors; its page allows cells left of the start, and two of its Hello
  Worlds need them. Its page describes implementation conventions rather than
  conflicting requirements. Factor retains these defaults: its cell range
  and right growth are explicit, while its left edge and EOF are unspecified.
- Line leaves cell width and tape boundaries unspecified: cells are unbounded
  integers and the sparse tape extends in both directions.
- Flowchart leaves path timing, cursor ownership and equal-distance junctions
  unspecified. Paths take no time, as the wiki's eight-pointer Hello World
  requires, so a step runs one node per pointer in the spec's order; cursors
  are per pointer; junctions prefer straight, right, then left. I/O is
  Boolfuck's bytes, low bit first, as the spec says; EOF reads empty, and the
  wiki cat's final empty pop pads to a trailing NUL.
- LaserFuck inherits Brainfuck commands without defining EOF: exhausted input
  raises `EOFError`.
- SStack's page has no example with a stated output; its brainfuck
  interpreter is marked untested. Popping an empty stack reads 0 and leaves it
  empty, `:x:` peeks and raises `HaltError` above 255, EOF raises, and
  whitespace is discarded anywhere, inside a token too.
- BrainIf rejects unknown commands, including those under a false guard.
  `inc`, `left` and `right` remain aliases for the canonical commands.
- SLOW ACV MAMMALIAN rejects unknown words; commands are uppercase and
  whitespace-delimited. The Hello World fixture omits prose annotations.
  Its storage range is `0..255`, but EXCRETE and PRONOUNCE say modulo 255;
  `cell_modulus` and `io_modulus` select 255 or 256; cells default to 256
  and I/O to the page's 255.
- Jaune leaves unresolved markers, cell bounds, tape bounds and EOF unspecified.
  Unresolved markers raise `HaltError`; cells are unbounded, the tape grows
  in both directions, and EOF raises. `v` reads signed integer tokens.
- Alight retains infix, left-to-right expressions for compatibility with
  existing programs and generators, despite the explicit postfix rule.
  Its cat examples use infix expressions; `expression_syntax="postfix"` follows
  the conflicting Operations section. Three-argument `at` defaults to
  `list_update="in_place"`, which the reversed cat needs (it discards the
  result); `"copy"` follows the prose's "return a copy".
- CV(N)(C) accepts ASCII `g` as an alias for `ɡ` to run the wiki greeting.
  CV(N)(C), Grapheme and NoComment discard LF to run line-wrapped generated
  programs; these are source-rule deviations, not specification gaps.
- Grapheme defaults to `integer_conversion="between_letters"`: `FAFY` prints
  1. `"after_each_letter"` includes the prose's final multiplication and prints
  10. Both integer mode and string conversion follow this setting; generators
  adapt their literals. The same page’s truth machine requires 1 rather than
  the prose’s 10. An unset variable reads as its own name, which the page’s
  variables example (`VARIABL`) requires.
- Packlang literals default to decimal; `literal_policy="binary_digits"`
  treats literals containing only `0` and `1` as binary. The same page uses
  decimal `101` in Hello World and binary digits in PlusOrMinus and dependency
  examples. Character input preserves newlines; EOF supplies newline to `charGet`.
- ROTfuck defaults to `rotation="backward"` (`+` turns into `]`): the wiki's
  one-character cat `,[` then echoes; `"forward"` follows the prose (`+` into
  `-`), under which the cat fires an unmatched `]`. A jump seeks its partner
  before the rotation ("after the instruction is executed"). The wiki Hello
  World prints no greeting under any direction or seek timing. The generator
  targets the default only.
- Smu reads an unset variable as empty, as the wiki cat needs at EOF.
  Bits ride bytes low bit first, as in Boolfuck, so the cat copies bytes;
  output `=` prints nothing, `(` or `)` halts, and an unbalanced program
  popped to run halts. The page's expanded cat drops the `=` after `(+=)`
  and forces a leading 1; the compact source fixes the repair.
- Piet++ settles its open conventions from the page text alone (the module
  docstring names each): Read and Write pop their x operand and offset from
  the codel just entered; a Write lands at once and may recolour the running
  block; invalid or ill-typed commands are ignored without popping, as the
  page recommends; a codel is one pixel.  XKCD Random Number (`4`) and
  User:Miui/Nah. (`Nah.`) pin the delta sign.
- Pinyin is rejected: its spelling rule contradicts its examples and its
  input-1 truth-machine example has no deterministic reading.
