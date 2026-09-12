# Limitations and contracts

This is the current boundary ledger. Live work is in [the roadmap](roadmap.md);
structural arguments are in [walls](walls.md).

## Interpreter conventions

- Empty input is a no-op unless the language requires a seed or grid.
- Exhausted input raises `EOFError`, except where the specification defines
  another sentinel. Malformed programs raise `ValueError`; runtime failure
  raises `HaltError`.
- Character input is line-delimited: one line supplies one character.
- A blank line reads as `0`, and that `0` is **chosen** everywhere. Audited
  against the current page of all eight sites that reach it — the six
  guards `test_input_convention.py` finds by AST (Alight, DINAC, Jaune,
  LaserFuck, Streetcode, Suffolk), plus Dig, which zeroes its mole by
  leaving the read unset, and Packlang, which takes `io.input_char`
  directly. Two pages specify the opposite and are knowingly overridden:
  DINAC "Empty input returns \n", Packlang "Empty input returns a
  newline". Five say nothing about an empty read. Suffolk alone names the
  value — "At EOF, instead set the internal state integer to 0" — but that
  is EOF, which is a *stop* here rather than a state change, so it
  corroborates the number and not the rule. (Suffolk's `run` returns on
  that EOF instead of propagating it, which is the documented end of its
  run; the read still raises for a step-level caller.) Jaune's two linked implementations were checked as well and
  neither defines an empty read: the JavaScript one calls
  `Scanner.nextInt()`, the Common Lisp one bare `read`, and both error
  rather than yield 0. **No language's `0` comes from its own
  specification.**
- Explicit frame stacks make supported recursion uncapped. Forbin calls in
  expression position remain host-recursive and report their documented limit.
- Streetcode's **four-way junction is a convention**, and no example can make
  it anything else. Scanning every cell and heading of both of the wiki's
  junction-bearing grids, `_junction_kind` answers 3 wherever it fires and 4
  nowhere — the infinite-loop example fires at ten states, the infinite-cat
  example at ten, all of them three-way. The page cannot settle it in
  principle either: its ambiguous-turn rule names only "the leftmost road"
  and "the second-leftmost one", which is a choice between two, so a
  four-way's third road is outside what the rule spells. `docs/streetcode.md`
  stays the spec of record and the implementation's behaviour is the
  definition.

## Where a run can be shown on its source

`esolangs debug --tui` marks the command about to run. Which languages it
can mark is a boundary, not a bug list, and it follows from what `ip`
*is* rather than from effort spent on the screen.

A machine declares `ip_shape`, read by `getattr` like `self_halts`. The
census over the committed examples, at the current page:

- **`offset` (48).** A plain int counting characters. The default, which is
  why these declare nothing.
- **`grid` (11).** The first two parts are a row and a column, any rest a
  heading. COD flattens one four-tuple per live cod, so the width varies
  and only the first cursor is drawn.
- **`line` (2).** Algebraic Programming Language and Interprogck8 start
  their position with a line number. The **whole line** is marked, because a
  line is all they distinguish — no column is available to be right about.
- **`opaque` (8).** 3D Brainfuck, Circuit Diagram, Eval, Forbin, Forþ,
  Grapheme, MyScript, function x(y). These have a position that is not a
  place in the source: a frame stack of one cursor per frame, a call depth
  paired with a cursor, a 3-D point and heading, or — Circuit Diagram —
  nothing at all, since a generation advances the whole drawing. **Nothing
  is marked**, and the header's raw `ip` is what makes the absence legible.

Six of those eight were marked in the *wrong* place until the trait existed:
a frame stack and a cell are both tuples of small ints landing inside the
rectangle, so a fit-probe cannot separate them and the classification came
from reading all twenty `ip` implementations. **Being in range is not being
right.** An undeclared tuple is therefore refused rather than guessed at,
and `"opaque"` is a declaration so that "nobody has classified this" stays
distinct from "somebody did, and the answer is nowhere".

`test_a_positional_ip_says_what_it_counts` is the living enforcement: a new
machine reporting a tuple must declare a shape, and the shape must be one
the reader knows. Without it the breach is silent — forget `self_halts` and
a driving loop hangs, but forget this and a language just stops being
drawable.

A **breakpoint** is drawn only where it names a position. `--break-at` and
the screen's own `t` do; `--break-on-cell` and `--break-on-output` are facts
about state with nowhere to put a mark, so they stop a run without appearing
on the program. An `opaque` language can hold no drawn breakpoint at all.

## Generator boundaries

Boolean construction is parameterized for seventeen languages, listed and
kept current in [`languages.md`](languages.md#parameterized-generators);
no program reading its own inputs overcomes `%^2^-1`'s two-input wall.
That list is derived from the generators, not written down here: three
documents each named a different subset of it, and each was wrong.

The n=3 input-reordering screen (`scripts/screen_input_reorder.py`)
closes eight unwired generators at exactly 0% upside without reading
their code — A Painter Ant, Alight, Container, Grapheme, Home Row,
Packlang, Point Break, Suptiftam — most sum-of-minterms, where the
minterm count does not depend on split order. Suffolk, Circuit Diagram
and Collatz Multiverse improve a handful of tables each for under 0.05%.

Interprogck8's boolean generator reaches ten inputs. It was capped at
three by the reach of one `DownAccLines` — 255 lines, against a 456-line
n=4 crossing — lifted to seven by relay rungs (`77025aa7`), and lifted to
ten by the express: `DownAccLines` keeps the accumulator, so a chain
spells its stride once and rides one-line rungs parked in meadows, which
also retired the old router's patience knob and its 2031s n=8 price. See
the table below for the measured edge and the paragraph after it for the
mechanism.

The ten is now a cost call rather than an open question. `_REPAIRS` is a
budget on meadow additions, and dense n=11 closes when given more: at 4096
it builds in 20.9s spending 1445 additions, emits 1203786 characters over
279181 lines, and **all 2048 rows execute correctly**. The shipped 256
refuses it in 2.9s after 350 additions — re-measured, against the 30s this
ledger used to carry, which predates the router's recent perf work. Dense
n=10 spends 103, inside the 95-126 the entry already recorded. The budget
is unchanged: 1445 additions and a 1.2MB program for one arity is what the
cap is declining to spend, not something it cannot reach. Unlike WII2D's
analogous "raise the 256 guard" question, which measured *false*, this one
measured true.

## Boolean generator caps

Current caps are deliberate:

Measured ceilings, from a sweep of all 69 boolean generators over n=1..10
against a dense pseudo-random table and parity (both shapes, since several
generators cover one and refuse the other at the same arity):

| Generator | dense | parity | what stops it |
| --- | --- | --- | --- |
| Interprogck8 | 10 | 10 | held at 10 on cost, not capability: `_REPAIRS = 256` refuses dense n=11, and a raised budget builds it at 1445 additions -- priced under *Generator boundaries* above |
| Polynomial | 10 | 10 | caps at 1934 instructions, one per prime -- the analytic worst case over n=10 tables, so all of n=10 builds; dense n=11 needs 2910, now priced at 267s a table and a 124MB program -- see the paragraph below |
| WII2D | 9 | 10 | dense n=10 needs a 512-point decode, past the fold algebra's measured cliff (live count 512 -> 373 while bit length passes 670000, every candidate enumerated) -- a wall of the exactly-once embed convention, since a per-node re-embed tree does dense n=13, and raising the guard to 512 refuses the table anyway; n=9 is admitted but not total -- 37 of 64 sampled tables build, the rest refuse promptly |
| ZTOALC L | 10 | 10 | n=11 needs 587 command slots (545 parity) against the anchors' 386 under the 4.19M line ceiling |

Polynomial's guard is priced too, and it guards the *interpreter*: the
question was never whether the generator can spell 2910 instructions but
what they cost to run. Raised past the cap, dense n=11 builds in 14.7s and
emits 123609143 characters; **all 2048 rows execute correctly** in 267s.
Effectively all of that is one factorization -- 264.5s for the first row,
then 0.001s a row for the other 2047, which share it. Against the n=10
anchor re-measured on the same machine (1638 instructions, 36349164
characters, 56s a table, 55.7s of it the factorization), 1.78x the
instructions costs 4.7x the time and 3.4x the program. The cap stays at
1934: the policy is "admit what a suite can afford to check", and 267s
plus a 124MB artifact for one table is what that policy declines. What
moved is that the price is now measured rather than projected.

And 2910 is only the *fixture*, not the arity: the same formula at n=11
gives 3726, so even a cap sized to that price would leave n=11 partial.
Admitting the arity is a fresh derivation, not a constant bump.

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
and interpreting one row: n=7 0.2s, n=8 0.5s, n=9 1.4s, n=10 5.1s (104659
digits), n=11 20.1s (219455 digits), each answering correctly.  The cost is
still roughly 4x an input, so n=12 is near a minute and a half a row.

These were 0.56s / 2.2s / 8.8s / 36s / 151s, on encodings of 454832 digits
at n=10 and 952366 at n=11, until the decision tree stopped printing at
every leaf and dropped its complement construction (`226a442b`,
`4454cd9a`).  The time here is dominated by the number's width, so a 4.3x
smaller encoding is most of a 7x faster row -- and n=11 now renders under
the default digit budget, where it used to need `max_digits` raised past
500000 to render at all.

**These are single
rows, not the row-by-row verification the n=5 claim above rests on** -- a
full n=10 table is 1024 rows, about ten hours -- so the reach is where a row
is affordable, not where a table is checked.

The other 65 generators build both shapes at n=10, and ZTOALC L and
Interprogck8 now join them (both caps sit at n=11, so they stay in the
table). `tests/tools/test_boolean_contract.py` now
sweeps the full ten inputs, in two bands -- n<=5 in the default gate,
n=6..10 marked `slow`.  Minifuck was what held it lower, and no longer is:
the named accumulator starts at nine rather than ten, and the whole n=1..10
both-shapes build is 8.5s against 44s, n=9 alone 35.8s to 0.65s.  It is the
one generator here that bought that with length rather than for free, and
the price is a single dense entry -- below.  Four
have left, each byte-identical: ROTfuck (16s to 0.06s at n=10) once its
emitter stopped stepping moves and the final rotation one character at a
time; Forþ (61-68s to 0.20s dense / 0.08s parity) once its size contest
stopped building all 13,122 candidates and scored each order's length in
closed form; Circuit Diagram (73s to 0.09s at n=9) once its per-cell wire
tables -- quadratic in the drawing -- became intervals with a slice-painting
renderer, which also reaches n=10 at 0.31s for 306MB dense; and `%^2^-1`
(parity n=9 30s to 0.16s, n=10 254s to 0.38s) once its deep band stopped
paying for every zero-unit weighting the singleton diffs already refute.

The sweep's bound was always cost rather than capability, and the cost has
now been paid down.  A ten-input sweep of the whole registry cost 141s and
peaked at n=9 (53s of it); after five generators were rewritten it is 51.5s,
with n=8 at 5.9s, n=9 at 7.5s and n=10 at 23.9s.  Minifuck was 43s of the
old total and spent 34s at n=9 alone -- naming the accumulator from nine
leaves it 8.5s across n=1..10, and the nine-input spike is gone.
It did not go because the
frontier recurrence collapsed -- it measurably does not.  The composed
effect of m pending rounds on a
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
collapsed recurrence itself.  What nine inputs and up stopped paying is the
contest those numbers price: from `_MUX_RULE_ARITY` the accumulator is named
-- the largest legal one, whose combination builds iff any does -- so the
scout prices two orientations instead of ~3600 combinations at ten and
~1560 at nine, records the winner's
rewinds as it prices, and the build is spelled from them and accepted on its
own laws replay instead of sculpted.  With the weight gadget and the
sculpting round each a closed-form law (the separation fell 1.24s to 0.04s),
a cold ten-input build is 1.47s dense and 1.57s parity, 138x, and nine is
0.35s and 0.30s against 17.3s and 19.1s.  The corpus cost is one entry and
no more: dense +6.4% at nine (192801 to 205148), plus the +1.8% at ten the
rule already carried, with parity picking the rule's own combination at
both -- so nineteen of the twenty n=1..10 programs are byte-identical.
Every instantiated row of both shapes at nine (1024) answers correctly on
the shipped interpreter, as the 2048 ten-input rows did when the rule
landed.

Eight keeps the contest, and that is a deliberate choice rather than the
edge of the technique: the rule works there and would save 3.8s, but it
costs dense +11.6% (50653 to 56534), and 3.8s is affordable where nine's
35.8s was not.  The line is drawn where the contest stops being payable,
not where the trade is cheapest.  Below eight it stops being a trade at
all -- at seven dense already picks the top accumulator but parity pays
+11.0%, for a build that costs 0.38s cold.
The nearest entries to the one-second rule
are `laserfuck` at 1.377s and `%^2^-1`'s *dense* n=10 at 0.92s; Minifuck's
1.5s now sits beside them rather than three decades above.  Only the table's
rows are capability limits, and exactly one of them binds inside the sweep:
WII2D's dense row at n=9, which `_ARITY_CAPPED` pins.  The other three sit
at n=11, above the ceiling.

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
  total*: the deterministic witness builds in 1.1s (78362 characters, all
  512 rows executed), and of 64 sha256-seeded dense n=9 tables 37 build in
  0.85-2.93s while 27 refuse in 0.49-2.56s, none hanging.
  The abort is load-bearing: lifted, three sampled ratchets ran 136-214s
  without stopping, reaching 1.17M bits. Dense n=10 needs a 512-point
  decode and is a wall of the **exactly-once embed convention**, not of
  the machine and not of the guard's value: raised to 512 the witness
  still refuses, 0.22s per branch, and with the magnitude abort lifted too
  its live count crawls 512 -> 475 over 19 steps while the bit length
  doubles every step (9 -> 1089888 bits). Full enumeration is no better
  (512 -> 373, past 670000 bits). A per-node re-embed tree — which the
  convention forbids
  — does dense n=10 in 14432 characters and n=13 in 146540, every row
  executed. `docs/generators/wii2d_generator.md` has the audit. Structured n=10 is
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

## Expensive but uncapped

The caps above are the generators that *refuse*. The ones that do not are
the ones a cap table cannot answer for: asking "can I afford n=11 on
Circuit Diagram?" gets nothing back, because Circuit Diagram has no cap.
It builds, whatever the size turns out to be.

That size used to be the warning. Dense n=10 Circuit Diagram was
**306,424,058 characters at 674MB RSS**, produced in a third of a second --
fast enough to feel free, large enough to be the whole of a small machine.
Allocating a row's columns once per row rather than once per gate took it
to **4,036,596 characters**, and n=11 from an extrapolated 1.5GB to a
measured 9,840,720. The same round of work shrank bit~ by 32x, ROTfuck by
25x and COD by 4.3x.

So the numbers below are no longer a wall. They are still a growth law, and
that is what they are for: nothing here refuses, so extrapolating is the
only way to find out what an arity costs before paying for it. Program size
against arity, on the dense pseudo-random table the caps are stated
against:

| Generator | n=8 | n=9 | growth per input |
| --- | --- | --- | --- |
| Polynomial | 3,383,048 | 10,896,883 | ~3.2x |
| COD | 942,692 | 3,668,705 | ~3.9x |
| SLOW ACV MAMMALIAN | 1,672,368 | 3,380,418 | ~2.0x |
| Circuit Diagram | 609,526 | 1,609,864 | ~2.6x |
| 123 | 219,937 | 752,570 | ~3.4x |
| ROTfuck | 86,605 | 194,945 | ~2.3x |
| bit~ | 31,076 | 69,005 | ~2.2x |
| Factor | 17,613 | 36,339 | ~2.1x |

Every other generator is under 600KB at n=9; the largest of them is A
Painter Ant at 517,452 -- which is now bigger than the bottom three rows
above, so the table is a list of the fastest *growing* generators and not
of the largest ones.

Two consequences worth having before you start:

- **Extrapolate with the ratio, not with hope.** COD is the one to watch
  now: 3.7MB at n=9 and ~3.9x puts its dense n=11 near 56MB, and nothing
  stops it. Polynomial is larger still but capped, so it refuses at n=11
  rather than handing you the file -- the top row of this table is the one
  row you cannot actually reach.
- **Run time is the real wall, and it does not track generation.** It is a
  smaller wall than it was -- one dense n=8 Circuit Diagram row now takes
  0.81 seconds where it took roughly 22, so a full 256-row table is about
  three and a half minutes rather than an hour and a half. Nothing warns
  about it either way, and `evaluate` runs every row.

`test_the_expensive_generators_grow_as_documented` re-derives the sizes and
the ratios rather than trusting this table -- sizes only, since a program's
length is deterministic for a fixed generator and table while a timing on a
shared machine is not. The timings here are approximate and were taken idle.

There is deliberately no `estimate()` API. The suggestion that prompted this
section assumed "the cap logic already exists -- it's what raises
`GeneratorCapError`", and that is false for exactly the generators the
problem is about: Circuit Diagram, COD and ROTfuck have no cap arithmetic to
run, so an estimator for them would be a per-language size model fitted to
measurements -- a frozen table, kept by hand, drifting behind the
generators it claims to describe. The growth laws above answer the same
question and a test keeps them true.

## Assessed and rejected

- **Lowering to Streetcode** — retired, and recoverable. A compiler from
  Streetcode grids and printed-leaf decision trees was asked for, but
  `7c440f9e` deleted `src/esolangs/transpilers/` entire — the total
  brainfuck -> Streetcode transpiler included — because 2069 lines and 47s
  of suite time served nothing in the repo, following `58427732` on the
  compilers. Rebuilding a larger version of what was just removed needs a
  consumer first. The construction is recoverable at `7c440f9e^` if one
  appears.

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
