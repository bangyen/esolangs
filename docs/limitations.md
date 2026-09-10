# Limitations and contracts

This is the current boundary ledger. Live work is in [the roadmap](roadmap.md);
structural arguments are in [walls](walls.md).

## Interpreter conventions

- Empty input is a no-op unless the language requires a seed or grid.
- Exhausted input raises `EOFError`, except where the specification defines
  another sentinel. Malformed programs raise `ValueError`; runtime failure
  raises `HaltError`.
- Character input is line-delimited: one line supplies one character.
- Explicit frame stacks make supported recursion uncapped. Forbin calls in
  expression position remain host-recursive and report their documented limit.

## Generator boundaries

Text generators are absent where the language has no output, only a binary or
numeric output alphabet, or cannot emit arbitrary byte sequences. Boolean
construction is parameterized for 123 and `%^2^-1`; no program reading its
own inputs overcomes the latter's two-input wall.

Interprogck8's boolean generator reaches ten inputs. It was capped at
three by the reach of one `DownAccLines` — 255 lines, against a 456-line
n=4 crossing — lifted to seven by relay rungs (`77025aa7`), and lifted to
ten by the express: `DownAccLines` keeps the accumulator, so a chain
spells its stride once and rides one-line rungs parked in meadows, which
also retired the old router's patience knob and its 2031s n=8 price. See
the table below for the measured edge and the paragraph after it for the
mechanism.

## Text generator blockers

| Language | Why it cannot emit arbitrary text |
| --- | --- |
| A Painter Ant | No I/O, so the interpreter dumps state when it proves the ant's routine repeats; that grid raster is limited to its symbols. |
| Algebraic Programming Language | Executed lines print numeric results only. |
| ArrowQueue | No I/O, so the interpreter dumps the queue at halt; those headings are numeric. |
| Back | No I/O, so the interpreter dumps the tape at halt; that has only `0`, `1`, and spaces. |
| BF-PDA | Output is one bit at a time. |
| Bitdeque | No I/O, so the interpreter dumps the deque at halt; that dump is numeric. |
| COD | Its sink prints decimal integers only. |
| Circuit Diagram | Output is a bit string only. |
| Fargo | `$` prints the output register as a number. |
| Flowchart | Its output node emits one bit; the spec's truth machine fixes that convention. |
| Grapheme | String mode cannot contain `E`, and strings cannot be concatenated. |
| Inject | `send` appends a newline to every emitted line, so texts without a final newline are unreachable. |
| Jaune | `^` prints cells as decimal integers only. |
| Lamfunc | Whitespace tokenization and no concatenation prevent arbitrary text. |
| Minsky Swap | No I/O, so the interpreter dumps the registers at halt; that dump is numeric. |
| Point Break | No output command, so the interpreter dumps the variables at halt; that dump is numeric. |
| RAM0 | No I/O, so the interpreter dumps state at halt; that fixed format cannot address arbitrary text. |

Current caps are deliberate:

Measured ceilings, from a sweep of all 69 boolean generators over n=1..10
against a dense pseudo-random table and parity (both shapes, since several
generators cover one and refuse the other at the same arity):

| Generator | dense | parity | what stops it |
| --- | --- | --- | --- |
| Interprogck8 | 10 | 10 | n=11 dense exhausts the `_REPAIRS = 256` meadow budget after 30s; whether more budget closes it is unmeasured |
| Polynomial | 10 | 10 | caps at 1934 instructions, one per prime -- the analytic worst case over n=10 tables, so all of n=10 builds; dense n=11 needs 2910 |
| WII2D | 9 | 10 | dense n=10 needs a 512-point decode, past the fold algebra's measured cliff (live count 512 -> 373 while bit length passes 670000, every candidate enumerated) -- a wall of the exactly-once embed convention, since a per-node re-embed tree does dense n=13; n=9 is admitted but not total -- 6 of 10 sampled tables build, the rest refuse promptly |
| ZTOALC L | 10 | 10 | n=11 needs 587 command slots (545 parity) against the anchors' 386 under the 4.19M line ceiling |

6-5 leaves the table too.  Its 35 branch labels are the language's
(operands are `0-9A-Z`), and the tree constructions spend them per subtree:
sharing duplicates as a DAG bought parity n=14, but a dense table has
genuinely *different* subtrees -- 47 distinct at n=7 against 35 -- and was
refused under every input order.  The walk construction spends one label
per input instead: the table is preloaded onto the tape a row per stride
(`1` moves two cells), and each read then either falls into a run of
`2^(n-1-i)` strides or jumps past it, so after n bits the pointer stands on
the row the inputs index.  Dense n=10 is 10 labels and 5319 chars, all
1024 rows executed correctly in 12s.  What remains is n<=35 -- a label per
input -- with program size doubling per input long before that binds.

Both older entries moved rather than vanished.  Interprogck8 was capped at 3 by
the 255-line reach of one `DownAccLines` against a 452-line n=4 crossing,
then at 7 by relay interference: every rung respelled its distance (~25
lines) into shared dead space, and rungs repairing one chain broke
others, an iterative chase that cost 2031s at n=8.  The express replaced
that.  `DownAccLines` does not consume the accumulator, so a chain loads
its stride once at its own jump slot and every waypoint after is a bare
one-line `DownAccLines` -- plus a few `@nd`/`@id` adjusters where the
stride changes -- parked in *meadows*, dead-line banks emitted between
gadgets and sized to the chains crossing them.  Meadows are placed after
widths settle and a rung replaces a placeholder line in place, so routing
runs once against frozen coordinates and chains cannot interfere; a
shortfall names its stranded window, a repair adds one meadow inside it,
and the route is retried from clean placeholders (`_REPAIRS = 256`
additions, against 95-126 spent across four n=10 dense seeds).  n=10
builds in about 10s (91684 lines dense, 116330 parity) and **every row of
dense and parity executed correctly at n=8, 9 and 10**; n=7 dropped from
3.5s to 0.05s and 12985 lines to 9499.  n=11 dense is refused when the
repair budget runs out, 30s in -- a cost policy again, and whether more
budget would close it is unmeasured.

Factor was capped at 3 by CPython's 4300-digit `int`/`str` guard -- a DoS
defence, not a Factor property -- which the generator and the interpreter
now both raise to fit the program and restore, so n=5 parity (12565 digits)
renders and runs, verified row by row.  Its ceiling is program size against
`max_digits`, not an arity, so it leaves this table.  Both caps were the
construction's rather than the language's, which is what made them
liftable.

What n=5 parity cost to *run* was a second, separate limit, and it is gone
too.  `_factorint` asked `sympy.isprime` once per sieve chunk, and BPSW is
two modular exponentiations priced by the full width of the argument: three
calls were 60.02s of a 60.06s factorization, while the sieve that finds
every factor measured 0.000s and the divisions 0.04s.  Gating the test on a
*barren* chunk -- one that divided nothing out, the only point its answer is
worth paying for -- puts n=5 parity at 0.041s a row.  Numbers of this shape
reach 1 without a barren chunk ever occurring.  Reach past n=5, generating
and interpreting one row: n=7 0.56s, n=8 2.2s, n=9 8.8s, n=10 36s (454832
digits), n=11 151s (952366 digits), each answering correctly.  The cost is
roughly 4x an input, so n=12 is near ten minutes a row.  **These are single
rows, not the row-by-row verification the n=5 claim above rests on** -- a
full n=10 table is 1024 rows, about ten hours -- so the reach is where a row
is affordable, not where a table is checked.

The other 65 generators build both shapes at n=10, and ZTOALC L and
Interprogck8 now join them (both caps sit at n=11, so they stay in the
table). One is slow rather
than capped, and its cost is the reason `tests/tools/test_boolean_contract.py`
sweeps to five inputs rather than ten: Minifuck, 19s at n=9 and 203s at n=10
(was 187s at n=8 -- the sculpt sweep now prices every candidate in closed
form and builds only the winner, 95x, byte-identical through n=9).  Four
have left, each byte-identical: ROTfuck (16s to 0.06s at n=10) once its
emitter stopped stepping moves and the final rotation one character at a
time; Forþ (61-68s to 0.20s dense / 0.08s parity) once its size contest
stopped building all 13,122 candidates and scored each order's length in
closed form; Circuit Diagram (73s to 0.09s at n=9) once its per-cell wire
tables -- quadratic in the drawing -- became intervals with a slice-painting
renderer, which also reaches n=10 at 0.31s for 306MB dense; and `%^2^-1`
(parity n=9 30s to 0.16s, n=10 254s to 0.38s) once its deep band stopped
paying for every zero-unit weighting the singleton diffs already refute.

So the sweep's five-input bound is now Minifuck alone: a seven-input sweep
costs about 13s across the whole registry (12.6s of it the 64 generators
none of this touched), and ten stays out of reach: the frontier recurrence
measurably does not collapse.  The composed effect of m pending rounds on a
row is one affine GF(2) map, but each round appends one independent rank-one
correction to its binomial-Toeplitz bulk -- rank exactly m-1 and displacement
rank exactly m, measured to m=128 at width 400 and on 60 random width
sequences -- and each correction's per-row scalar is one bit of truncation
feedback, a parity of the row's evolved tape above that round's width, so
pricing a combination keeps one term per examined row per pending round.
Pruning cannot absorb the cost either: seeding the strict abort with the
true optimum saves 3.4% of the 1.58M
window-walks at n=8, and a clairvoyant abort that skips every doomed
combination for free leaves 0.5-0.9%, information available only through the
collapsed recurrence itself.  Nor is the scout the whole ceiling: at n=10
dense the separation costs 1.2s and the winner's real sculpt and acceptance
1.5s against 201s of scout, so a zero-cost scout still builds the row in
about 2.7s.  The nearest entries to the one-second rule
are `laserfuck` at 1.377s and `%^2^-1`'s *dense* n=10 at 0.92s, neither of
them changed here.  Only the table's rows are
capability limits, and only WII2D's dense row binds inside the sweep (the
other three caps sit at n=11); the rest of the gap between five and ten is
wall-clock.

- **Interprogck8:** a meadow-budget limit, not the 255-line reach.  The
  express routes against frozen coordinates, so the old relay
  interference is gone; what runs out at n=11 is the repair budget that
  adds meadows at stranded windows, and the refusal names the window.
- **`%^2^-1`:** generic samples build through thirteen inputs; a
  fourteen-input table would need a twelve-input prefix ladder, which is
  open research, not a wall.
- **NoComment:** a host/runtime configuration limit.  Factor used to sit
  here and no longer does: its limit was CPython's digit guard, which is
  raised and restored around the conversion rather than reported.
- **Polynomial:** a cost guard on the *interpreter*, not the generator,
  and now at 1934 instructions -- the analytic worst case over n=10
  tables, so every n=10 table builds.  Two interpreter changes moved it
  from 328: recovery is cached per program, so the rows of a table share
  one factorization instead of paying it each (the old six-hour estimate
  for dense n=8 was per-row arithmetic against an already-amortized
  cost), and past degree 100 the peels take their candidates from the
  polynomial's roots over two fixed NTT fields -- found by evaluating it
  at every field point -- rather than enumerating prime powers and
  factoring over a 64-bit field.  Acceptance stays exact division, so
  only the search cost moved.  Measured, every row against its table:
  dense n=8 (541 instructions) 3.5s for all 256 rows where the old path
  took 115s for the first alone, dense n=10 (1638) 44s for all 1024.
  Dense n=11 (2910) is refused.  Still an instruction count and not an
  arity -- a table that collapses renders far past n=10.
- **WII2D:** the cost guard now sits at 256 (was 128), backed by a
  magnitude abort (`_WII2D_MAX_MAGNITUDE`) that turns the doubling trap
  into a prompt refusal: successes never pass 14-bit live values, a
  ratchet doubles its bit length per step. Dense n=9 is *admitted but not
  total*: the deterministic witness builds in 6.6s (78362 characters, all
  512 rows executed), 45 of 50 sampled domain-256 patterns decode in ~3s,
  6 of 10 sampled tables build; every sampled failure returns in 0.7-9.4s.
  The abort is load-bearing: lifted, three sampled ratchets ran 136-214s
  without stopping, reaching 1.17M bits. Dense n=10 needs a 512-point
  decode and is a wall of the **exactly-once embed convention**, not of
  the machine: within a single-embed layout the fold algebra ratchets
  (live count 512 -> 373, bit length past 670000, every candidate
  enumerated), but a per-node re-embed tree — which the convention forbids
  — does dense n=10 in 14432 characters and n=13 in 146540, every row
  executed. `docs/wii2d_generator.md` has the audit. Structured n=10 is
  unaffected: parity, majority, AND, OR, an xor-of-a-subset and a
  threshold all build and execute all 1024 rows; the 3-to-8 mux builds in
  only 3 of its 1680 spellings (0.18%), all with the selects read last.
- **ZTOALC L:** was capped at 8 by the trajectory-prefix peak (n=9 peaked
  at 1.2e7 lines against the 4.19M ceiling).  Two changes cleared 10/10:
  commands now sit on the *L smallest* trajectory values under the ceiling
  (a visited line past the code's end reads as a blank no-op, so the peak
  stopped mattering), and the table is stored as four-row chunk codes
  decoded through one shared 16-entry array, cutting dense n=10 from 555
  commands to at most 329.  All 1024 rows of dense pseudo-random and of
  parity verified against the interpreter (1.62M / 1.17M lines, ~2s a
  table).  The wall is now slot capacity: the committed anchors keep at
  most 386 values under the ceiling (start 511935), a sieve of *every*
  start to 2**22 finds at most 395, and n=11 needs 587 dense / 545
  parity -- so the next arity requires a higher line ceiling, not a better
  anchor or placement.
- **Route hybrids:** CV(N)(C), Polynomial, Circlefuck, `%^2^-1`, and WII2D
  alternatives were rejected on the grounds that occasional smaller output
  did not repay slower generation — 1.25x, 1.08x, 29x, 3,100x, and 1.85x on
  their audit cases. **Treat those five numbers as unverified**: the harness
  was not kept, and no measurement here reproduces one. Polynomial's figure is
  known wrong — its hybrid was reimplemented and ships (below), which was
  possible only because the bullet named the construction. CV(N)(C) and
  Circlefuck still build competing routes in-tree and were re-priced from
  that code: direct wins 202 of 256 at n=3 against stored's 54, and
  Circlefuck's greedy route never wins on size while costing about twice as
  much to build. Both verdicts stand on those measurements, not on the
  ratios. WII2D and `%^2^-1` both had a *committed* predecessor, recoverable
  from the commit that retired it: `ea65a170` removed WII2D's beam decode
  and `56c0d850` removed `%^2^-1`'s `_fold_search`, `_fold_beam` and
  `_fold_to_cofactors`. The current sources say those constructions keep no
  alternative and never backtrack, which describes what they are now, not
  what was tried. Both were recovered and re-measured, and neither ships.
  WII2D's beam does shorten output — as an optional second decode it shrank
  19,864 of 66,108 tables, none grown, median 5.2% — but it costs 9.8x
  generation at n=5 and reintroduces into a deterministic construction the
  search `ea65a170` removed; the size is not worth that. `%^2^-1`'s descent
  loses outright: over 40 five-input fold states the shipped rules plan all
  40 while the descent plans 5 at width 1 and 13 at width 4, slower at both.
  Recovering a predecessor does not re-derive the recorded ratio — the
  audited variants
  lived in a worktree and may differ — but it does mean these were never
  guesswork to retry.

  Polynomial is the exception. Its tree and state machine are the endpoints
  of one family — `k` tree levels above one machine per residual — and the
  interior wins where both lose: a table whose residuals merge within a
  top-level split but not across it. Shipping the whole family shortens 36
  of 256 three-input tables (median 3.6%, best 30.3%) and 3,846 of 65,536
  four-input ones (median 6.5%, best 39.8%); none grow, and none previously
  refused becomes renderable. Selection is on rendered characters, since
  instruction count disagrees with them; the count screens which candidates
  are worth rendering, costing 2.54x at n=3 (0.3s across 256 programs) and
  1.09x at n=4. The screen's slack is arity-dependent and measured, not
  derived — 6 at n<=3 but 9 at n=4 — so the counts are lower bounds.

## Assessed and rejected

- **Pinyin** ([wiki](https://esolangs.org/wiki/Pinyin)) — rejected: the
  command triples are not pinnable to any deterministic reading, and the
  wiki's own truth machine is unreachable under all of them.

  A command is a Chinese character; its tone picks the IP turn, its consonant
  a guard, its vowel a stack operation. Nothing in the repo or the page maps a
  character to a reading, so the table has to come from a pronunciation
  database, and the page's selection rule — smallest tone, then
  lexicographically smallest pinyin — **contradicts its own examples**.
  Applied over the full heteronym set it changes the tone, hence the routing,
  on 8 of the 23 Hello, world! characters: 邓 becomes `shan1` (turn) where the
  program needs `deng4` (straight, push stack size), and 但 兑 兔 待 淡 漏 道
  likewise. The rule reproduces the page's own five-row worked example
  perfectly (一 二 的 我 人, 5/5), so it is the *rule* that is example-hostile,
  not the reading source.

  Routing itself pins cleanly and was worth establishing: start at (0,0)
  facing right; the vowel effect runs, then the tone turns, and only when the
  consonant guard passes; the top and left edges deflect as in Nopfunge Solid;
  outside the written lines is blank, not Nopfunge Solid's infinite tiling;
  and escaping right or below halts. Under that model with common readings,
  Hello, world! emits `Qᮓ\t\tᮟè World!`, whose tail is exact up to the capital
  `W`; the page never states its output string, so that scores 7/13 against
  `Hello, World!` and 6/13 against its own lowercase section title. The tail is
  what fixes the model, and it also settles the duplicated `ui` row in favour
  of `b**a` over `a^b`, since `a^b` breaks it.

  It does not fix the programs. Searching every dictionary reading of every
  character crossed with the five open spec-gap choices (`ui` as power or
  xor, `iu` literal or reduced, EOF halts or pushes 0, division by zero halts
  or pushes 0, tone applied on a failed guard or not) reproduces the cat and
  the trivial half of the truth machine, and nothing else:

  | Example | Runs | Reproductions | Best |
  | --- | --- | --- | --- |
  | Truth machine, input 1 | 384 | **0** | 39/40 — `110111…`, a stray `0` third |
  | Truth machine, input 0 | 384 | 192 | exact |
  | Cat | 384 | 64 | exact, only where EOF halts |

  Input 1 is the falsifier, and it is exhaustive: the half that makes a truth
  machine a truth machine is one output character wrong under every one of its
  384 readings, and no spec-gap choice moves it. Hello, world! reproduces no
  better — its common-reading assignment, the only one matching the author's
  evident intent, is the 7/13 above, tail right and prefix wrong — but
  its 1,327,104-run sweep was not carried to completion, so no exhaustive
  claim is made for it.

  The page also defines `ui` twice (`b**a` and `a^b`) and gives `h` and `j`
  the same condition, never corrected; the examples were added by a third party
  (Cleverxia, "fix yet again"), never confirmed by the author, who left the
  proofs "as an exercise to the reader"; the page is `Category:Unimplemented`.

  Cost is not the objection. A two-input boolean program is **4 characters,
  12 bytes** — `业业但乍` (`ye4` read integer, twice; `dan4` multiply; `zha4`
  print integer), straight-line at tone 4, halting by escaping the right edge.
  Executed over the full truth table it is correct 4/4 for AND, and `业业令乍`
  4/4 for OR, under common readings; AND also holds under the spec's own
  selection rule. The language would price well. It fails CONTRIBUTING's
  "stable, deterministic, verifiable" bar on the spec, not on the generator.

## Spec and engine boundaries

- 6-5's interpreter accepts operands outside the specification; generators
  must stay in `0..35`.
- Jaune's dispatch to an undefined marker is unspecified.
- Alight's prose contradicts its own examples twice, and the examples decide
  both. It calls all operators postfix, but every example is infix
  (`turn c = eof`, `len{l}-0.5`), so expressions evaluate infix left to right
  with no precedence. It says three-argument `at` returns a copy, but the
  reversed cat runs `at{l, len{l}-0.5, c}` as a bare command and discards the
  result: under copy semantics that is a no-op and the example crashes on its
  own first `out`, so `at` sets in place. Both readings are pinned by running
  all three wiki programs.
- Packlang's wiki examples disagree on what base a numeric literal is in.
  Literals are read as **decimal**: Hello World, truth-machine and cat only
  work that way, while PlusOrMinus's `101011`/`101101` and the dependency
  example's `110000`/`101`/`011`/`001` were written as binary character
  codes and are declared wrong. A pure binary reading is refuted outright --
  four of the five examples contain non-binary digits, PlusOrMinus's own
  `Integer(0, 255, 255, 0)` among them. The tie against a hybrid reading
  breaks on the author's error markers: the comment `48 (1100000)`
  mis-writes 48 (`110000`), and `equals(101, 011)` uses leading zeros.
  Rebasing the dependency example's literals reproduces the `0110` its
  comments claim, so its logic is right and only its base is wrong.
- Packlang's cat cannot reach its own terminator here. `While c ^ 10 Do`
  waits for a newline *byte* from `charGet`, but input is line-delimited
  (`splitlines`), so no line begins with byte 10 and a blank line reads as
  the package-wide 0. The program parses and accumulates but never exits
  the loop; this is the line-IO convention, not an interpreter defect.

All generator output claims require execution through the interpreter. Do not
use permissive interpreter behavior or a bounded search as a new capability.
