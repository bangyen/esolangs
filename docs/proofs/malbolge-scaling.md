# Malbolge boolean generator: the hashed wall, and the build past it

Why the hashed cascade stopped at fourteen inputs, the positional build that
now covers fifteen and sixteen, and why seventeen is out of reach for any
build that spends a cell per pair of rows. Companion to the narrative in
[../limitations.md](../limitations.md). Everything here is measured or
verified against the interpreter's `crazy`/`rot`, or marked as an unbuilt
design. The sections on the load law and the two fifteen-input cascade
attempts are kept as the record of why the hash had to go.

## The load law

An answer cell carries a label from `{0, 1, x, n, N}`: the four answers as a
function of the last input, or `N` (not final, cascade deeper). So one cell
resolves exactly the two rows that differ in the last input -- **two rows per
cell is the hard maximum**, since a function of the last two inputs would need
sixteen labels and the pointer region admits about six. An `n`-input table
therefore needs `2**(n-1)` answer cells, all distinct and decoder-reachable,
in the roughly 39,366 cells the readout can address above the code. That is a
floor, and the optimum of this architecture rather than a description of every
build: thirteen through sixteen attain it, while eleven and twelve resolve one
row per cell and spend `2**n` ([the emitted-size law](#the-emitted-size-law)).

Collisions resolve by cascade *tiers*; the decoder reaches tier `k` by being
re-entered and re-enciphered `k` times, so the tier budget is the number of
decoder passes (the shipped build affords two passes = three tiers). The
finite-cell cascade -- all tiers competing for one shared window, uniform
placement, the best a fixed fold can hope for -- needs tiers that climb
steeply with load `L = cells / window`:

| inputs | answer cells | `L` | tiers to fully resolve |
| --- | --- | --- | --- |
| 14 | 8,192 | 0.21 | 3 (matches the shipped 7427/685/80) |
| 15 | 16,384 | 0.42 | ~10-12 |
| 16 | 32,768 | 0.83 | >20 |

The model reproduces the shipped fourteen-input build, so the wall is real:
past load ~0.3 the required depth outruns any decoder pass count.

## The emitted-size law

`len(program)` is 59,049 at every arity: the whole store is the source, so the
load limit *is* the emitted length rather than a bound on it, and reading
linearity off `len()` measures the padding. What the construction spends is
its **set cells** -- those differing from `f(a) = 33 + ((35 - a) % 94)`, the
unique nop character for a cell's own address, which is what every untouched
cell holds. Unwritten cells decode as op `o`, so a set cell is exactly a
non-`o` cell.

Through ten inputs that count is not fitted but exact:

```
set_cells(n, table) = 46 + 28*n + 2*T + popcount(table)        n <= 10
```

Zero residual on every table measured, all-zero and all-one included. The
terms are the build: a row writes `'p'`/`'o'` at `+1`, `'<'` at `+2`, `'v'` at
`+3`, and a **0-row's `+1` cell is the nop character**, so the per-row cost is
`2 + bit`, not three. `28*n` is the per-input mixer fold, `46` the fixed
navigation. Worst case is all-ones at `46 + 28n + 3T`, best all-zeros at
`46 + 28n + 2T` -- linear in `T` with a known constant, the `28n` being the
`log T` term.

Above ten, size stops depending on the table at all: it is spent per *resolved
readout*, not per row, and the spread across all-zero, all-one and random
tables is 0.1-2.0% where popcount moved it by `T/2` below ten. The hashed
cascade spends `2**11 * 2**selectors`, the positional build one cell a row
pair:

| inputs | build | answer cells | rows per cell | set cells | overhead |
| --- | --- | --- | --- | --- | --- |
| 11 | cascade, 1 copy | 2,048 = `T` | 1 | 2,524-2,532 | ~480 |
| 12 | cascade, 2 copies | 4,096 = `T` | 1 | 4,667-4,670 | ~572 |
| 13 | cascade, 2 + stub read | 4,096 = `T/2` | 2 | 5,237 | ~1,200 |
| 14 | cascade, 4 + stub read | 8,192 = `T/2` | 2 | 10,108 | ~1,900 |
| 15 | positional | 16,384 = `T/2` | 2 | 16,473 | 89 |
| 16 | positional | 32,768 = `T/2` | 2 | 32,034 | -734 |

In the cascade an input spent as a copy-selector doubles storage while one read
directly by the answer stub doubles `T` for free, so its coefficient alternates
between `1` and `1/2` -- the whole content of its lumpy per-input size factors
(x1.82, x1.13, x1.93), which are an alternation rather than a growth rate. The
positional build sits at `T/2` throughout and carries almost no overhead, the
decoder and hub machinery being what the cascade paid for. At sixteen it is
*below* `T/2`: 734 of the 32,768 pair cells want the nop character for their own
address anyway, the same coincidence that makes a 0-row free below ten.

So size is linear in `T` in all three regimes, and counting the construction is
what settles that -- six arities of a table-independent quantity cannot separate
`T/log T` from `T log T` by sampling.

Where it matters: the load law's `2**(n-1)` is a floor and the optimum of the
architecture, not a description of every build. Thirteen through sixteen attain
it; eleven and twelve resolve one row per cell and spend `2**n`, a factor two
above what the architecture admits. That never weakened the wall -- a build
that misses the floor needs *more* cells -- but it does mean the factor two at
eleven and twelve is spent head-room that no later arity inherits.

## Generation time

The build is `plan(n)` then `fill(table)`. Every layout planner -- `_skeleton`,
`_cascade`, `_wide`, `_thirteen`, `_fourteen` for the hashed builds and
`_digits` for the positional one -- takes **no truth table** and is memoized, so
all table-dependent work is in `fill`, which is one pass over the rows and one
pass over the store. `fill` calls `_table_char` at most 1.14 times a row
(measured 1.125, 1.137, 0.568, 0.552 at eleven to fourteen and exactly 0.5 at
fifteen and sixteen, tracking the rows-per-cell column above), each call bounded
by eight ops over a 94-character table, so `fill` is `Theta(T + W)` with
`W = 59,049`. This is a shape every arity shares, the positional build
included, not a property of one construction.

`plan` was the super-linear half. The address map refolded the mixer from
`_INITS` for every row -- `n` steps a row, `Theta(T log T)` -- which is a
structural count, not a measurement artifact, and the measured growth per added
input agreed: x2.19 twice at the top of the stub regime against the `2(n+1)/n`
that `T log T` predicts (x2.22 at nine to ten) and the x2.00 that linear does.

The fold is a prefix computation, so rows sharing their first `i` inputs share
every state to level `i`. Expanding the levels breadth first computes each
distinct prefix once, `2**(n+1) - 2` steps against `n * 2**n`, and the address
map is now `Theta(T)`. The emitted program is byte-identical at every arity
through ten, on random and all-zero/all-one tables. Measured growth per added
input fell to x1.75, x1.71, x1.88, x1.93, x1.95 -- under x2 and rising toward
it, the linear signature in the one direction the convention reads -- and cold
planning at ten inputs went 73.9 ms to 19.3 ms.

So generation is `Theta(T + W)` for `n <= 10`, by structure and not only by
measurement. Above ten each arity is a separate layout, and cold planning grows
x1.08, x1.08, x1.53 across the cascade; the regime change at eleven is excluded
rather than smoothed. Warm fill keeps reading linear to the cap -- 15.9, 20.2,
23.4, 38.4 ms at thirteen to sixteen, so x1.27, x1.16, x1.63 per added input,
all under x2.

The positional plan does not grow either, once its shared part is separated.
`_digits(n)` calls the nullary `_readouts_cells()`, so whichever arity builds
first pays that search and the other finds it cached; timed apart in a fresh
process per arity it is 0.402 s at both, arity-independent, while `_digits(n)`
itself costs 0.263 s at fifteen and 0.048 s at sixteen -- *falling* as `T`
doubles, because sixteen is the natural base of one cell per row pair over the
whole digit space and fifteen derives a layout from it. Cold generation is
therefore dominated by a constant: 60% of the build at fifteen, 89% at sixteen.
Two arities give one ratio rather than a scaling read, so the positional verdict
rests on the plan/fill structure -- memoized, table-free, exactly 0.500
`_table_char` calls a row -- with the measurements consistent with it, not on a
fitted growth.

What stays open is not the shape of the curve but its domain: the planners are
searches whose cost is proved for no arity, and since the generator refuses past
its cap the input set is finite, so no measurement over it can establish an
asymptotic claim in either direction. That is the reachable gap the roadmap's
generation-time cell names, and it is a coverage gap rather than a growth one.

## Sixteen: no known construction

Sixteen needs 32,768 answer cells (load 0.83). Three routes, all closed:

- **Deeper cascade.** >20 tiers; a decoder affords a handful of passes.
- **Injective fold** (place cells collision-free, no cascade). No searched
  mixer is injective past ~11 bits; 12-bit folds top out near 60% distinct.
- **Disjoint copy-blocks** (below). The clean version needs the fold bounded
  below `3**7 = 2187` for eight copies; boundedness reaches only ~8% at that
  width, so ~92% spills into a load-0.5 overflow -- the wall again.

Sixteen is therefore not shippable with the label/cascade architecture. This
is a strong negative from measurement, not a formal impossibility theorem.

## Fifteen: a verified mechanism, an unbuilt build

Fifteen (load 0.42) is out of reach for the direct cascade (~12 tiers) but
within reach of a **disjoint-block** scheme that cascades only the overflow.
Both gadgets below are verified against the interpreter's `crazy`.

- **Disjoint blocks.** With `V` the fold readout of a copy and `C_c` a
  per-copy constant whose low seven trits are all `1` and whose top three
  trits tag the copy in `{1, 2}`, `crazy(V, C_c)` maps the eight copies to
  eight perfectly disjoint 2187-cell blocks (17,496 cells, zero overlap): the
  low trits are an injective permutation of `V`, the top trits a fixed tag.
- **Clamp.** `crazy` has no identity and cannot zero a trit in one step, but
  two do: `CT[2]` sends every trit to `{1, 2}`, then `CT[0]` sends `{1, 2}` to
  `0`. So `crazy(crazy(V, K1), K2)` with `K1` top-trits `2` / low `1` and `K2`
  top-trits `0` / low `1` forces the readout below 2187 for *every* `V` while
  keeping it an injective function of `V`'s low seven trits. This defeats the
  "cannot bound the fold" obstacle.

With the clamp, fifteen needs the 11-bit fold injective in its low seven trits
(mod 2187) over the 2048 prefixes. A cleanly-placed row needs no cascade; only
mod-2187 collisions overflow into the free region, resolved by a shallow
cascade. The gate is the fraction placed uniquely:

- Reheating simulated annealing over five-cell schedules plateaus at ~46%
  rows-uniquely-placed (best genome pinned in the scaling scratch: inits
  37300/23791/56010/39488/57716). ~54% overflow, ~8,800 instances at load
  ~0.27 -> ~5 tiers -> a **four-to-five-pass decoder**.
- At ~75% rows-unique the overflow would drop to load ~0.10 and the shipped
  two-pass decoder would suffice. The fold does not reach it: 2048 distinct
  values in 2187 slots is near-perfect hashing.

So fifteen is feasible but unbuilt: the disjoint-block gadget cuts the cascade
from ~12 tiers to ~5, and the remaining work is a four-to-five-pass decoder
(third- and fourth-pass building blocks exist at 73-77 of the 94 residues),
the overflow cascade, and interpreter verification across all 32,768 rows
before the cap moves. (Superseded: the positional build below needs no
cascade at all.)

## Fifteen: the eight-copy cascade, measured

A second attempt built the multi-level version: eight copies selected by
inputs twelve to fourteen through a selector cell `Q`, a shared decoder per
level entered through the all-1 `N` hub, and per-level readouts in three
region types -- shared (`>= 19683`), private (`13122 + a % 6561`, two
constants), and a single 2187-cell block (three-constant clamp to top trits
`(0, 1, 2)`). Annealed level schedules resolve every row: `SSSSPP` followed by
three per-copy-prep levels in an empty block goes
7622/2803/1584/1721/1480/683 then 491 -> 87 -> 5 -> 0 unresolved. The table
side is solved. The build is not, because memory runs out:

- **Main code ~10,300-11,200 cells.** Constants and mixer 567; high-cell resets
  ~60 per cell (every reset walks up from the `N` hub); private and clamp
  preparation ~1,500; selector and per-copy preps 250-1,000; nine segments
  ~1,800-2,200; label resets and chains ~2,400-2,800; hub turns ~640.
- **Band.** Per-copy tails (offset dispatch), decoders (~50-120 cells each,
  dominated by walks to the high `G` constant cells) and answer stubs need
  ~1,300-1,900 free cells. Tails of level `k` sit at `Q_k(c) + 1`, and the
  selector puts the eight copies on 81-cell tiles (input bits at trits 4-6),
  so each tile holds at most about four levels of ~20-cell tails. Six tail
  levels never packed: the planner reaches level 6 and fails there on every
  seed.
- **The squeeze.** Below `19683` the only free space is `[0, 13122)` minus the
  private region's needs: main code, band and the empty block for the last
  levels do not all fit. Moving the answer hubs into free shared cells
  (seeds `(73,1) (91,1) (107,1) (113,2)`), lifting `Q` above them with one
  main-code `G` op, and sharing a few rotating `G` cells across decoders each
  bought a few hundred cells, not enough.
- **Per-copy preps instead of tails** remove the tile limit but resolve less:
  a prep `rot^u(char)` is mostly zero trits and loses information (25% of
  2,654 keys resolved at level 5); `f01(rot^u(char))` is nearly bijective and
  resolves 65% (1,725 vs 1,693 for private offsets), yet in the private
  region successive levels only halve the remainder (929 -> 491 -> 275),
  where an empty block finishes in three.

The unbuilt remainder is a layout with the band inside the private region
(annealed around) and the last levels in the empty `(0, 1, 2)` block, with
main code under 10,935. Nothing in it was verified in the interpreter; the
positional build below replaced it.

## Fifteen and sixteen: a positional address

Every wall above is a *collision* wall: a hashed readout puts two rows on one
cell, and resolving them costs levels. A positional readout has no
collisions, and the store is big enough for one: a word has five two-trit
digits, a digit has nine values, and three input bits need eight. Fifteen
address bits therefore fit one word with every row pair on its own cell, at
load 32,768 / 59,049 -- far past the ~0.3 the cascade tolerated, because
nothing has to be resolved.

`crazy` works trit by trit, which is what makes this cheap. A 16-op gadget
over three fresh walked cells (`/ p0 / p1 K2 p0 K2 p1 / p2 p0 p1 p0 K1 p0 p2`,
found by breadth-first search over trit 0 alone) leaves the three inputs
injective in trit 0 of cells 1 and 2; trits 1..9 of every cell see only
constants and stay constant. Folding a group into the accumulator `S` is
`p` over `S` with `A = v`, `*`, `p` over the `u` cell with `A = S`, `*`. Each
`p` is bijective in the new trit because `S`'s arriving trit is 1 for the
first (the `y = 1` row of `crazy` permutes `x`) and 2 for the second (`x = 2`
permutes `y`), and bijective in every digit already folded because the
cells' constants there are 2 and 1. Those constants and the arriving trits
are fixed by the cells' walked `g` values: trits 4..9 of a small `g` are 0 or
1, which gives `(u, v) = (1, 2)`, and trits 1..3 were solved so that every
untouched trit of an all-1 `S` arrives holding the 1 or 2 it needs. Ten folds
are ten rotations, so digit `k` of the final word is group `k`.

Each digit misses one value. `swap12` on group 4's `v` and group 1's `u`
(`p` with `A = 2`: trit 0 swaps 1 and 2, and the constants 1 and 2 at the
other trits stay put), and `swap01` of the final word, make the top digit miss
`(0, 0)` and digit 1 miss `(2, 2)`: every readout lies in 6,561..59,039, the
main code (under 5,800 cells) fits below the table, and no `S + 1` wraps past the
store. Fifteen inputs replace group 4's first read with the constant `'0'`;
their 16,384 cells are a subset of sixteen's.

The answer side is the thirteen-input stub reading the last input, with the
four labels `0 1 x n` and no `N`. At 55% occupancy the hubs are the hard
part: their seed chains (`rot` and the three constant `p`s, up to five long)
are searched so that both values a label's chain alternates between land in
the table's holes, and the `not x` stub, which flips `'0'` and `'1'` only
over a large operand, `j`s to a dedicated pointer-region cell prepared for
it instead of a hub value. Both arities run on every row of a dense (seeded
random) and the parity table.

## Seventeen

Any build whose answer cell names a function of the last input needs
`2**(n - 1)` cells: 65,536 at seventeen, more than the store. A cell naming
a function of the last two inputs needs sixteen labels, and its address
admits eight characters. Information is tighter still: a 17-input table
carries 131,072 bits and a Malbolge source at most `59049 * 3 = 177,147`, so
the table needs 2.2 bits of every cell in the machine before any addressing
code, where the label builds store at most 2 bits in the cells they use.

### Five meanings per cell, at most

Joint decoding across several cells does not escape this if a cell is read
by its *value*. At address `h` the eight admissible characters are
`33 + ((i - h) mod 94)` for the eight instruction indices
`I = {6, 7, 29, 35, 48, 65, 66, 84}` of `_XLAT1`, so as `h` varies the
character sets are exactly the 94 translates of `I` in `Z_94`. Suppose a
build gives each character value one meaning (a label, a hub, anything its
decoder does next that depends only on the value), and every meaning must
be writable at every table address. Each meaning's set of values then meets
every translate of `I`: it is a hitting set. The smallest hitting set has 16
values (as character minus 33, one is `{11, 15, 17, 22, 24, 29, 31, 38, 44,
62, 64, 71, 76, 78, 85, 91}`). None has 15: CP-SAT proves it infeasible in about 200 s,
with one member fixed at 0, which loses nothing because translating a
hitting set gives another. Six disjoint hitting sets would need 96 of the
94 values, so **a value-decoded cell carries at most five meanings**, and
the thirteen- and fourteen-input builds already use all five.

That caps every value-decoded build at `log2 5 = 2.32` bits a cell: `k`
cells jointly name at most `5**k` behaviours, so a group of `2**r` rows needs
`5**k >= 2**(2**r)` and the best rate is `1 / log2 5 = 0.43` cells a row.
Seventeen inputs then need at least 56,450 table cells, leaving under 2,600
for all code, hubs and stubs, against a positional main code of ~5,700.
Executing the table cells instead escapes the proof but not the rate. The
decoded instruction depends on `(t + h) mod 94`, so all eight are available
at every address, and a group's cells run as one straight-line program
shared by its rows. `<` and `v` act on every row at once. `i` jumps through
`mem[d]`, and `d` differs per row, but a row can only fall through it if
`mem[d]` holds that `i` cell's own address, which differs per group and
would have to be computed as `S + k` -- addition, which `crazy` and `*` do
not give. So `i` ends the group for every row, and the letters left are `o
j * p /`: again about `log2 5` bits a cell.

### Seven meanings, once the decoder knows the address's parity

The hitting-set bound assumes a meaning is writable at *every* address. A
decoder that also knows `h mod 2` escapes it, because `94` is even: an
address of one parity only sees the 47 translates `I - h` with `h` of that
parity. Each value lies in 4 of them, and exhaustive search finds no
hitting set of 12, so a meaning needs at least 13 values and eight would need
104: **at most seven**, and seven are attained. As character minus 33, for even
`h` (odd `h` adds 1 to every value, since `(I - h) + 1 = I - (h - 1)`):

```
{0,2,4,6,9,11,14,26,51,72,84,91,93}
{7,16,25,30,37,40,49,54,60,63,67,70,81}
{10,17,19,20,22,24,29,31,34,44,46,71,92}
{5,13,15,23,33,38,47,57,62,65,75,86,89}
{1,12,21,28,35,39,42,53,61,68,74,77,79,82}
{3,18,27,32,41,43,45,48,50,52,56,59,83,88}
{8,36,55,58,64,66,69,73,76,78,80,85,87,90}
```

The seven partition all 94 values and each meets every translate of its class. Parity is cheap to
reach: `9**k` is odd, so `h mod 2` is the parity of the digit sum, a
function of the input bits. `log2 7 = 2.81` bits a cell clears the 2.47
seventeen needs once a positional main code is paid for, so the
value-decoded cap no longer excludes seventeen. What remains is cost, not
rate: a parity-aware decoder must rewrite its hubs per class, and a joint
code over several cells multiplies that per decoded state. A 2+1 layout
(two 15-bit cells and one 14-bit cell per four row pairs, `7**3 >= 4**4`)
fails at seven meanings: each pair of labels needs a common `B` value,
which forces the Fano plane, and no multiplicity of its lines keeps every
value within seven labels.

Reading two adjacent cells removes the phase altogether: `v_{h+1} - v_h =
i_{h+1} - i_h - 1 (mod 94)` does not involve `h`, the eight sets `I - i - 1`
hit only 43 differences, and a colouring of those with eight colours rainbow
on every set exists, so a chain of cells carries the full 3 bits a cell after
its first. Malbolge cannot subtract, though, and the obvious substitute --
two `p`s, `crazy(crazy(K, v_h), v_{h+1})` -- is not injective in `v_{h+1}`
for any of the 243 low-trit constants `K`, so no decoder for it is known.

### Seventeen: what a build would need, measured

A design that meets the rate was taken as far as real sources allow; every
figure here is from a source string run through the interpreter unless it
says estimated.

- **Joint codes are lossless.** Two adjacent cells admit a 64-colouring and
  three a 512-colouring rainbow on every product of admissible sets, so a
  group decoded together carries the full 3 bits a cell with no phase.
- **Layout.** Groups of three cells `3q..3q+2`, eight rows each: 16,384
  groups, 49,152 table cells. No single product of 8-of-9 digits reaches
  16,384, but six digit-local slabs do -- all digits normal with `t9` in
  `{1,2}` (8,192), `t9 = 0` (4,096), and four slabs pinning one digit to its
  missing value (1,024 each) -- disjoint by enumeration, with `[0, 243)` and
  a 2,430-cell run at `[2187, 4616]` left free.
- **Automaton.** A 13-state decoder (states shared across rows) maps a
  group's three meanings to its eight answer bits; simulated annealing finds
  none at 12, and counting gives at least 9.
- **Main code.** The sixteen-input main code compacts from 5,085 to 2,391
  cells (sampled rows green), leaving 7,506 cells for all 17-input decoding.
- **The wall is setup, not rate.** A source cell holds only one of 8
  characters, so every large word the decoder needs -- hub pointers, landing
  targets -- is written by the program at run time, and navigation dominates:
  an independently placed word costs 350-450 cells, an ascending sweep 1 cell
  a cell. One convergent decoder state reads, converges and prints correctly
  for all 8 admissible characters (7,880 code cells); two states chained
  through a hub are correct on all 32 chain paths (14,871). Each added state
  costs about 7,000 cells, so thirteen are about 90,000 against 7,506. Sweeping
  the trampolines still leaves about 2,600 a state (estimated). A fit needs
  under about 200 a state: one read routine per cell position shared by all
  states, with the state carried as data. That is designed, not built.

No value-only build reaches seventeen, and no known parity-aware or
execution-decoded one does either; neither is a bound on Malbolge programs in general. Lowering the language bound
instead needs some 17-input table with no program; counting misses by a
factor `2**46076`, so no such proof is in sight. Seventeen is open in both
directions.
