# Limitations and contracts

This is the current boundary ledger.

## Interpreter conventions

- Empty input is a no-op unless the language requires a seed or grid.
- Exhausted input raises `EOFError`, except where the specification defines another sentinel.
- Character input is line-delimited: one line supplies one character.
- A blank line reads as `0`, and that `0` is **chosen** everywhere.
- Explicit frame stacks make supported recursion uncapped.
- Streetcode's **four-way junction is a convention**, and no example can make it anything else.

## Where a run can be shown on its source

`esolangs debug --tui` marks the command about to run.

A machine declares `ip_shape`, read by `getattr` like `self_halts`.

- **`offset` (48).** A plain int counting characters.
- **`grid` (11).** The first two parts are a row and a column, any rest a heading.
- **`line` (2).** Algebraic Programming Language and Interprogck8 start their position with a line number.
- **`opaque` (8).** 3D Brainfuck, Circuit Diagram, Eval, Forbin, Forþ, Grapheme, MyScript, function x(y).

Six of those eight were marked in the *wrong* place until the trait existed: a frame stack and a cell are both tuples of small ints landing inside the rectangle, so a fit-probe cannot separate them and the classification came from reading all twenty `ip` implementations.

`test_a_positional_ip_says_what_it_counts` is the living enforcement: a new machine reporting a tuple must declare a shape, and the shape must be one the reader knows.

A **breakpoint** is drawn only where it names a position.

## Generator boundaries

Boolean construction is parameterized for seventeen languages, listed and kept current in [`languages.md`](languages.md#parameterized-generators); no program reading its own inputs overcomes `%^2^-1`'s two-input wall.

The n=3 input-reordering screen (`scripts/screen_input_reorder.py`) closes eight unwired generators at exactly 0% upside without reading their code — A Painter Ant, Alight, Container, Grapheme, Home Row, Packlang, Point Break, Suptiftam — most sum-of-minterms, where the minterm count does not depend on split order.

Interprogck8's boolean generator reaches ten inputs.

The ten is now a cost call rather than an open question.

## Boolean generator caps

Current caps are deliberate:

Measured ceilings, from a sweep of all 69 boolean generators over n=1..10 against a dense pseudo-random table and parity (both shapes, since several generators cover one and refuse the other at the same arity):

| Generator | dense | parity | what stops it |
| --- | --- | --- | --- |
| Interprogck8 | 10 | 10 | held at 10 on cost, not capability: `_REPAIRS = 256` refuses dense n=11, and a raised budget builds it at 1445 additions -- priced under *Generator boundaries* above |
| Polynomial | 10 | 10 | caps at 1934 instructions, one per prime -- the analytic worst case over n=10 tables, so all of n=10 builds; dense n=11 needs 2910, now priced at 267s a table and a 124MB program -- see the paragraph below |
| WII2D | 9 | 10 | dense n=10 needs a 512-point decode, past the fold algebra's measured cliff (live count 512 -> 373 while bit length passes 670000, every candidate enumerated) -- a wall of the exactly-once embed convention, since a per-node re-embed tree does dense n=13, and raising the guard to 512 refuses the table anyway; n=9 is admitted but not total -- 37 of 64 sampled tables build, the rest refuse promptly |
| ZTOALC L | 10 | 10 | n=11 needs 587 command slots (545 parity) against the anchors' 386 under the 4.19M line ceiling |

Polynomial's guard is priced too, and it guards the *interpreter*: the question was never whether the generator can spell 2910 instructions but what they cost to run.

And 2910 is only the *fixture*, not the arity: the same formula at n=11 gives 3726, so even a cap sized to that price would leave n=11 partial.

6-5 leaves the table too.

Both older entries moved rather than vanished.

Factor was capped at 3 by CPython's 4300-digit `int`/`str` guard -- a DoS defence, not a Factor property -- which the generator and the interpreter now both raise to fit the program and restore, so n=5 parity (12565 digits) renders and runs, verified row by row.

What n=5 parity cost to *run* was a second, separate limit, and it is gone too.

These were 0.56s / 2.2s / 8.8s / 36s / 151s, on encodings of 454832 digits at n=10 and 952366 at n=11, until the decision tree stopped printing at every leaf and dropped its complement construction (`226a442b`, `4454cd9a`).

**These are single rows, not the row-by-row verification the n=5 claim above rests on** -- a full n=10 table is 1024 rows, about ten hours -- so the reach is where a row is affordable, not where a table is checked.

The other 65 generators build both shapes at n=10, and ZTOALC L and Interprogck8 now join them (both caps sit at n=11, so they stay in the table).

The sweep's bound was always cost rather than capability, and the cost has now been paid down.

Eight keeps the contest, and that is a deliberate choice rather than the edge of the technique: the rule works there and would save 3.8s, but it costs dense +11.6% (50653 to 56534), and 3.8s is affordable where nine's 35.8s was not.

- **Interprogck8:** a meadow-budget limit, not the 255-line reach.
- **`%^2^-1`:** generic samples build through thirteen inputs; a fourteen-input table would need a twelve-input prefix ladder, which is open research, not a wall.
- **NoComment:** a host/runtime configuration limit.
- **Polynomial:** a cost guard on the *interpreter*, not the generator, and now at 1934 instructions -- the analytic worst case over n=10 tables, so every n=10 table builds.
- **WII2D:** the cost guard now sits at 256 (was 128), backed by a magnitude abort (`_WII2D_MAX_MAGNITUDE`) that turns the doubling trap into a prompt refusal: successes never pass 14-bit live values, a ratchet doubles its bit length per step.
- **ZTOALC L:** was capped at 8 by the trajectory-prefix peak (n=9 peaked at 1.2e7 lines against the 4.19M ceiling).
- **Route hybrids:** CV(N)(C), Polynomial, Circlefuck, `%^2^-1`, and WII2D alternatives were rejected on the grounds that occasional smaller output did not repay slower generation — 1.25x, 1.08x, 29x, 3,100x, and 1.85x on their audit cases.

  Polynomial is the exception.

## Expensive but uncapped

The caps above are the generators that *refuse*.

That size used to be the warning.

So the numbers below are no longer a wall.

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

Every other generator is under 600KB at n=9; the largest of them is A Painter Ant at 517,452 -- which is now bigger than the bottom three rows above, so the table is a list of the fastest *growing* generators and not of the largest ones.

Two consequences worth having before you start:

- **Extrapolate with the ratio, not with hope.** COD is the one to watch now: 3.7MB at n=9 and ~3.9x puts its dense n=11 near 56MB, and nothing stops it.
- **Run time is the real wall, and it does not track generation.** It is a smaller wall than it was -- one dense n=8 Circuit Diagram row now takes 0.81 seconds where it took roughly 22, so a full 256-row table is about three and a half minutes rather than an hour and a half.

`test_the_expensive_generators_grow_as_documented` re-derives the sizes and the ratios rather than trusting this table -- sizes only, since a program's length is deterministic for a fixed generator and table while a timing on a shared machine is not.

There is deliberately no `estimate()` API.

## Assessed and rejected

- **Lowering to Streetcode** — retired, and recoverable.

- **Pinyin** ([wiki](https://esolangs.org/wiki/Pinyin)) — rejected: the command triples are not pinnable to any deterministic reading, and the wiki's own truth machine is unreachable under all of them.

  A command is a Chinese character; its tone picks the IP turn, its consonant a guard, its vowel a stack operation.

  Routing itself pins cleanly and was worth establishing: start at (0,0) facing right; the vowel effect runs, then the tone turns, and only when the consonant guard passes; the top and left edges deflect as in Nopfunge Solid; outside the written lines is blank, not Nopfunge Solid's infinite tiling; and escaping right or below halts.

  It does not fix the programs.

  | Example | Runs | Reproductions | Best | | --- | --- | --- | --- | | Truth machine, input 1 | 384 | **0** | 39/40 — `110111…`, a stray `0` third | | Truth machine, input 0 | 384 | 192 | exact | | Cat | 384 | 64 | exact, only where EOF halts |

  Input 1 is the falsifier, and it is exhaustive: the half that makes a truth machine a truth machine is one output character wrong under every one of its 384 readings, and no spec-gap choice moves it.

  The page also defines `ui` twice (`b**a` and `a^b`) and gives `h` and `j` the same condition, never corrected; the examples were added by a third party (Cleverxia, "fix yet again"), never confirmed by the author, who left the proofs "as an exercise to the reader"; the page is `Category:Unimplemented`.

  Cost is not the objection.

## Spec and engine boundaries

- 6-5's interpreter accepts operands outside the specification; generators must stay in `0..35`.
- Jaune's dispatch to an undefined marker is unspecified.
- Alight's prose contradicts its own examples twice, and the examples decide both.
- Packlang's wiki examples disagree on what base a numeric literal is in.
- Packlang's cat cannot reach its own terminator here.

All generator output claims require execution through the interpreter.
