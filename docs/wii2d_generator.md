# WII2D boolean generator: the cost policies and what they were measured against

Why each of the three width constants sits where it does, and the measurements
behind them.  The construction is in
`src/esolangs/tools/boolean/wii2d.py`, whose docstring is authoritative and
not restated here; this file keeps the numbers a future change to those
constants would otherwise have to re-measure.

All three are **cost policies, not capability bounds**.  Nothing here says a
table cannot be built — only that the program would be too wide to be worth
emitting.  Raising a constant does build the refused tables.

## `_WII2D_SHORTLIST = 4` — how many candidate folds get compressed

Compression is the expensive half of a candidate (a halving loop over the
whole domain, rebuilding the live map at every step) and the decode takes only
the head, so compressing every candidate is work thrown away.  Before this
screen the count rose with the domain: **7** compressions per fold actually
used at `D == 16`, **15** at `D == 32` and **50** at `D == 64`, all but one
discarded.

Measured over the same random tables, median/worst emitted characters and
build time for the whole sweep:

| shortlist | n6 median / worst | build time |
|---|---|---|
| eager (all candidates) | 832 / 1182 | 366 ms |
| 2 | 884 / 1976 | 215 ms |
| 3 | 750 / 1404 | 201 ms |
| **4 (shipped)** | **714 / 1242** | **194 ms** |
| 6 | 740 / 1024 | 207 ms |

Four is both smaller and faster than compressing everything, which is not the
trade one expects from a cut: the eager ranking is not better here, it merely
ranks more candidates that the screen was right to drop.

The screen **cannot be a bound**.  Compression is a contraction, so the
uncompressed magnitude says almost nothing about the compressed one — **529
collapsing to 17** is a measured case — and over **80 sampled states** there
was always a candidate whose uncompressed magnitude exceeded the eventual
winner's compressed magnitude.  Any early exit justified that way changes the
answer, so this is an admitted approximation.

## `_WII2D_MAX_INDEX_DOMAIN = 64` — the widest decode the general path attempts

Charged against `_wii2d_cost`, the smaller of `2 ** (n - 1)` and the domain
the chain actually leaves.  That distinction is what makes structured tables
reachable at any arity: an `n == 8` xor-of-a-subset collapses to a 4-point
decode and builds in **217 characters**, which the old worst-case-only check
refused without ever looking at it.

What the constant buys is bounded *width*, which still grows as the domain
doubles.  Measured through `_wii2d_decode`, 25 random patterns each:

| domain | median cells | worst | time |
|---|---|---|---|
| `D == 16` (n == 5) | 60 | 155 | under 0.01s |
| `D == 32` (n == 6) | 204 | 389 | under 0.01s |
| `D == 64` (n == 7) | 1213 | 1878 | under 0.06s |

64 admits dense `n == 7`.  Whole programs at that width, 25 random
non-symmetric tables each, end to end:

| arity | median chars | worst | time |
|---|---|---|---|
| n == 5 | 312 | 412 | 1.3 ms |
| n == 6 | 758 | 1054 | 7.8 ms |
| n == 7 | 2776 | 4270 | 65.1 ms |

So the price of `n == 7` is size, not time; the emitted programs were run
through the interpreter on **all 128 input combinations**.  The old note that
this "never established that anything fails" was right: nothing did.

Symmetric tables never reach this check — they decode over `n` points via the
popcount chain, so majority-of-12 is **397 characters** and instant.

## `_WII2D_MAX_REAL_DOMAIN = 256` — the runaway guard

The two constants bound different things.  `_WII2D_MAX_INDEX_DOMAIN` is
charged the *minimum* of the worst case and the real domain, so a table whose
chain collapses is judged on what it actually costs.  But the minimum also
means a table can be admitted on its worst case while its real domain runs
away: with no merge available the walk falls through to Horner, and a
non-merging pair can leave a domain far *above* `2 ** (n - 1)`.

That overshoot is rare but unbounded.  Random tables overshoot in **0.5%** of
cases at `n == 5` (domain 37 against a worst case of 16) and **0.2%** at
`n == 6` (domain 197 against 32); those still decode, but the 197-point one
emits **8808 characters in 694 ms**, twelve times the `n == 6` median.
Structured tables reach further: `(b0|b1)&(b2|b3)&(b4|b5)` leaves 17 at
`n == 5` and 34 at `n == 6`, but **1025** at `n == 7`, and that decode did not
return within minutes.

256 sits above every overshoot measured to decode (197) and below the one that
does not (1025).  Refusing the latter is not a regression — at the old
constant of 32 it was refused anyway, since its worst case of 64 exceeded it.
The cap only trims what raising the constant to 64 would newly have let in.

## `_WII2D_MAX_CENTRE = 4096` — the widest fold centre worth emitting

A centre costs `abs(c)` cells (`'-' * c` is spelled out in the grid), so this
bounds program width, not the arithmetic: a fold at `10**6` is perfectly
correct and utterly useless, since the row it lands on is a million columns
long.  Compression normally keeps the centres tiny — the medians below 100
columns come out of it — and this only rejects outliers where a fold sequence
has drifted somewhere it cannot come back from.

## Rejected: ranking folds by what they emit

The ranking lives in `_wii2d_folds`.  Ranking by emitted length instead of by
magnitude was tried and is much worse.
Ranking by live count instead — merging as hard as possible at each step —
reaches the same two-value state but through much larger numbers: measured
over the same random tables at `n == 6`, live-count-first gives a median
**2124** cells and a worst case of **19594**, where magnitude-first gives
**832** and **1182**.

Magnitude first is therefore the honest price rather than an artifact of the
ranking: a fold centre is spelled out as `'-' * c`, so the live values *are*
the program's width, and keeping them small also steers away from the squaring
blow-up, since every later fold squares whatever this one leaves.

## Exhaustiveness of the single-candidate rule

Every 0/1 pattern through `D == 16` — **65536 of 65536**, the widest domain
the general path asks for at `n == 5` — is realized by the single-candidate
rule, verified by applying the emitted op string back over the domain.
`D == 8` is likewise exhaustive at **256 of 256**, and the
maximally-alternating patterns (needing the most folds, since a fold at best
halves the block count) are among the successes rather than the exceptions.
