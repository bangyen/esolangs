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

## Seventeen: three-cell orbit packing

The one-cell-per-row-pair architecture stops at sixteen, but it does not give
a language wall.  The raw capacity permits a different unbuilt design.  Use
fourteen inputs to select a block of eight rows and encode that block's eight
answer bits in three source characters.  Three legal characters carry nine
bits, so this needs `3 * 2**14 = 49,152` cells and leaves 9,897 for code.

The existing fourteen-bit positional map gives the address geometry.  Add
`0`, `1`, or `2` modulo three to every trit of each readout to obtain three
candidate cells.  Exhaustive evaluation of the 16,384 readouts gives 41,949
distinct cells.  Of the blocks, 11,582 own three cells outright.  The other
4,802 form 2,401 pairs; the two blocks in a pair share all three cells, and
different pairs share none.  Equivalently, the collision graph is 2,401
components of two vertices joined by three parallel edges.  The count is
structural: each of the four full two-trit digits has seven values common to
two translates, hence `7**4 = 2,401`; the partial digit fixes which pair of
translates meets.

Each colliding pair contains sixteen answer bits.  Its three shared cells and
three private cells carry eighteen bits, so one free three-cell orbit per pair
suffices.  The cyclic translates occupy 13,983 of the 19,683 three-cell
orbits and leave 5,700.  There is a loop-less assignment.  Normalize a
collision orbit so its top digit is `2`; its other four digits independently
range over seven fixed values, giving a base-7 rank `r` in `0..2400`.  For
`r < 1458`, write `r` in mixed radix `(9, 9, 9, 2)` with digit 0 fixed at 7.
Otherwise write `r - 1458` in `(8, 9, 9, 2)`, with digit 1 fixed at 8 and
digit 0 drawn from `{0,1,2,3,4,5,6,8}`.  Both Cartesian regions are outside
the occupied orbits and overlap only where the second excludes digit 7, so
all 2,401 targets are distinct.  `malbolge_packing.py` exhaustively certifies
the counts and the formula.

Storage is therefore closed at 49,152 cells, preserving 9,897 for code.  This
remains an unbuilt alternative to the executed decoder route below: its
missing piece is a six-cell encoder/decoder for each collision pair and an
interpreter run over all 131,072 rows.

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

Two later results narrow both sides. The automaton shrinks to **five**
shared states once each state may read a cell chosen by the row's select
bits (verified over all 256 answer vectors; two states provably cannot,
three and four were never found); since a group's three cells differ only in
trit 0, those per-row read pointers are a one-time per-trit selection. Five
states times two parities projects to roughly 7,300-9,000 cells against 7,506
free -- near the line but unbuilt. On the other side, an output-truncated
count sharpens the language bound: before its one output a run's first
fetch of a cell cannot decode to `v`, nor to `<` unless `A` already holds
`'0'` or `'1'`, so the tables are at most `2**21.85 * 6**a' * 7**a * 8**b` for
`a'`, `a`, `b` such first reads by kind. Seventeen falls if every program's
first reads weigh at most 131,050 bits (false as stated; see [the corrected
route](#seventeen-the-read-count-route-corrected)), and no bound on a single run's steps
or reads can reach that, since 2^17 leaves each need one.

The five-state code re-reads a cell on 462 of its 2,744 paths, and a read
that rewrites its cell cannot be repeated. Forbidding that, **six** shared
states suffice (all 256 vectors, no path reads a cell twice). Four do not:
an exhaustive search over all `C(120, 7)` = 59,487,568,920 transition tables
with seven distinct columns (two equal columns leave at most `6**3 = 216`
distinguishable contents, under 256) finds none, and three were already
excluded. **Five is the minimum**: a search that fixes the states other
states point to first (each has at most one level below it) and adds rows
while every output class keeps room finds 5-state codes
(`scripts/malbolge17/decoder_s5_norepeat.p`, all 256 vectors, no re-read).
Three start-only states feed a fourth, which feeds a print-only fifth, so
transitions still reach only four targets. Its transitions reach only four targets -- two states and the two
prints -- which is within what one pointer region routes: the shipped
`_T_LABELS` admit each of `0 1 x n` at every residue. That suggests an
unbuilt design in which a state reads its cell with `p` under its own
constant, lands in a block of plain source characters (no run-time writes),
and routes through the existing label and hub machinery; it is estimated at
about 8,400 of the 9,897 non-table cells, not measured.

Layout caps that design. A constant injective in `T` needs its low five
trits all 2, so `crazy(K, T) + 1` lands in one of only 32 fixed windows (the
cells whose trits 5..9 are all 0 or 1), each a 94-cell pattern. Enumerating
every digit-local tiling -- which trit is `t9`, all 105 pairings of the rest
into digits, every missing-value choice and every `t9` role -- frees at most
**8** of those windows from table cells: a window is free for nothing only
when its fixed top trits already supply the pinned digits, and the five top
trits hold at most two whole digits besides `t9`. Every landing cell in the
best tiling's 8 windows admits all four labels, leaving 9,049 cells for code.
The design needs one window per state and parity, so it fits only with at
most four states; six give twelve.

Rotating the landing escapes the cap. `rot^s(crazy(K, T)) + 1` -- the read's
`p`, then `s` more `*` on the same cell -- is still injective, and with
`s <= 3` twelve pairwise-disjoint blocks (1,128 cells, all at least 420, none
on the table) fit the best tiling, eight of them with `s = 0` and one, two
and one with `s = 1, 2, 3`; every landing cell again admits all four labels.
Each extra rotation needs `d` back on the table cell, one more navigation
hop (estimated at ~180 cells), and only the four rotated blocks pay it. Two
`p`s with a fresh constant between them reach at least nineteen blocks, but
reloading `A` mid-read is its own cost.

The state-tagged read works on real sources. A single state that loads `A`
from a prepared constant, reads its cell with `p` and lands at
`crazy(K, T) + 1` prints the right bit for all 8 characters admissible at its
cell. Two such states with different constants and opposite answer maps
share one table cell and one pair of answer hubs in the same program and
are right on all 16 cases (measured, interpreter). The cost per added state
is its constant plus its share of the routing: 8,357 code cells for one
view, 8,353 for two and 8,960 for three once each view's constant sits
below cell 300, against about 7,000 per state for the earlier per-state
decoders. A constant op costs about 20 cells near the pointer region and
about 180 above cell 300, so where constants live dominates; the one-time
constants here still sit above 300 (about 3,600 of the 8,357). These are
prototypes on one fixed cell, not the 17-input build. Moving the one-time
constants below 300 too brings one view to 3,185 cells; each further view
then pays its constant (about 130-750 cells, measured) plus its routing,
which here is built lazily as fresh low pointer cells but in the design comes
from the shared labelled region the shipped build already pays for. A
state's read routine -- load `K`, point at the cell, `p`, return, `j`, `j`,
`j`, `i` -- measures 47-123 cells. Summing measured parts (the compacted
main code less its sixteen-input fold, ten view constants, five read
routines, ten landing blocks) with estimates for the seventeen-input address
computation and the parity and per-row pointer work gives about 8,400 of the
9,897 non-table cells: inside, but resting on those two estimates.

Transitions work too. A two-state chain -- state A reads its cell under its
constant, and each character either prints directly or goes through a hub
into state B's code, which reads a second cell under its own constant and
prints -- is right on all 64 cases on real sources, in 5,367 code cells
against 14,871 for the same chain with the earlier `rot` reads.

**The whole five-state decoder works on one group.** Each state reads its cell
of a three-cell group under one of ten view constants (five states times two
parities, landing blocks pairwise disjoint), each landing cell holds a plain
character whose pointer cell carries the target's label, and routing goes
through the shipped `_T_LABELS` machinery: every label cell is cleared to
all-1 by `p p`, one seeded `p` chain per label writes alternating hub values
into all its cells, and each hub value is rotated to its own copy of the
target (a print stub or a state 3 or 4 block). Two fixes were needed and are
general: after the read's `p`, `2 - c` `o`s move `d` past the group, so the
next escape never jumps through another group cell's table character; and
every block must fit the room reserved for it, since a stub that runs into a
rotated hub cell halts. With both, for every row (8) and every meaning
triple of the group (343), the program prints the decoder's answer: **2,744
of 2,744 correct** on real sources, run through `msim`. One group's program
takes about 6,700-6,800 code cells, nearly all of it one-time: the view
constants, label clearing and seed chains, eight hub copies, stubs and state
blocks. What is still missing for seventeen inputs is the address
computation that selects the group and its per-row read pointers from the
inputs, the parity selection of view constants at run time, and the full
table.

In a dense table the cell after a group is the next group's first cell, so
the read's escape jumps through a table character that varies. It converges
anyway if every pointer cell but one, `E`, holds a hub value (the 26 cells
outside `0 1 x n` get a fifth, escape-only seed chain), every hub value's
cell `H + 2` holds `E - 1`, `E` holds `Z0 - 1` and `Z0 + 1` holds `E - 1`:
from any table character, `j j o j j` ends on `Z0` (through a label cell:
`H + 1`, `H + 2`, `E`, `Z0`; through `E`: `Z0`, `Z0 + 1`, `E`, `Z0`). Seeds
are chosen so every hub value admits `E - 1` at `H + 2`. With the neighbour
cell set to a different admissible character on every run, the five-state
group decoder is still right on 2,744 of 2,744 cases. The unoptimised program
now takes about 12,900 code cells, all but about 400 one-time: 2,055 to clear
the 94 pointer cells, 5,957 for 17 constant chains, 2,127 for five label
chains and 2,350 for hub rotations. That is over the 9,897 non-table cells;
the earlier compaction halved the same kinds of setup, so fitting is now a
placement problem.

Placement cuts it to about 7,460-7,540 code cells per row, still 2,744 of
2,744 correct: one ascending `p p` pass clears the pointer cells (2,055 to
962), constants are placed and ordered by the planner's exact cost, seeds
are scored by chain plus pass cost, and hubs take their fewest-turn rotation
from the nearest pointer cell (2,350 to 251). Cheaper view constants reach
about 5,900, but the ones found so far collide: over all 94 characters, six
of the ten land two characters with different targets on one cell (134
conflicts), which a single test group cannot show because only eight
characters are admissible at each of its cells. A full table needs
constants whose landings are injective, or collide only where the targets
agree, across all 94 characters. With the valid constants, decoding setup
and one group's decoders take about 7,500 of the 8,957 non-table cells left
after the ten landing blocks, before the seventeen-input address
computation. Those constants are valid over all 94 characters but not yet
for the layout: under the best tiling about 800 of their landing cells fall
on table cells, invisible in a one-group test. Table-free landings force the
rotated-read constants found above, whose setup cost has not been measured,
so the 7,500 is a lower-bound estimate for the real layout, not a
measurement of it.

No value-only build reaches seventeen, and no known parity-aware or
execution-decoded one does either; neither is a bound on Malbolge programs in general. Lowering the language bound
instead needs some 17-input table with no program; counting misses by a
factor `2**46076`, so no such proof is in sight. Seventeen is open in both
directions.

### Seventeen: the read-count route, corrected

The count above was stated as "seventeen falls if every program's first reads
weigh at most 131,050 bits". **That hypothesis is false**, so the route cannot
be finished in that form. What survives is a weaker, correct theorem whose
hypothesis is a statement about tables rather than about programs.

**Counterexample (measured).** `scripts/malbolge17/sweep17.py` builds a real
source string with `_char_for`. Every one of the 131,072 seventeen-input rows
prints exactly one character, input 2, and halts (msim over all rows; the
repo interpreter agrees on sampled rows). Before that output it executes
29,564 cells and reads 29,433 others as data (`trace.c`): 28,466 first
executions at `log2 6`, 1,098 at `log2 7` and 29,433 data reads at 3 bits.
That is **164,965 bits**, well over 131,050. The layout is nops from 0. Then
`*` at 114 turns that cell into 39403, and two `j`s put `d` on it. A lockstep
`p` sweep of 19,600 cells reads `39404..59003`. A 14-cell gadget uses `*` on
a data cell, a `j` into the low cells, `p` on cell 56 and two `j`s, which
leaves 29564 in cell 56 and moves `d` there. A second sweep reads
`29565..39395`, and `/ < v` ends the run. Only 52 cells stay unread. Getting
`d` anywhere in the store costs a handful of cells, so control flow ("only
`i`/`j` on memory values") forces almost nothing to be wasted: every jump
from an unwritten cell lands in `33..126`, but one `*` or `p` makes a large
pointer.

**Theorem (representatives).** Explore rows in a fixed order. Run each row
to its first output. Assign each cell when it is first read (executed or
read by `j i * p`), and record its kind: executed with `A mod 256` in
`{48, 49}` (7 admissible characters, since `v` halts with no output),
executed otherwise (6, since `<` would also print a wrong character), or
data (8). The canonical weight `wt(P)` is the sum of `log2` of these counts.
If every seventeen-input table that has a valid program has one with
`wt(P) <= 131,071`, then some seventeen-input table has no program.

*Proof.* Before its first read a cell holds its initial value. Every write
(`p`, `*` and the encipher after execution) happens in a step that reads the
cell. So each row's run up to its output depends only on the assigned
cells, and the next cell's kind is fixed by the cells assigned so far. The
exploration is therefore a tree, and each valid program `P` ends at one leaf
(its restriction to the cells it reads), which fixes its table. Pick children
uniformly among the admissible characters. A leaf is then reached with
probability `2**-wt`, and leaves are disjoint events. Leaves of
representatives of distinct tables are distinct, so there are at most
`2**131071 < 2**131072` of them. ∎ This version needs no 21.85-bit overhead.
The uniform form of the same argument (3 bits for every cell) says it is
enough that each realizable table has a program reading at most 43,690
cells.

**What the missing lemma is.** The counterexample shows the hypothesis
cannot come from any bound on individual programs. It has to come from
*minimality*: every valid program heavier than 131,071 bits must be
replaceable by a lighter one that prints the same table. That lemma is
strictly stronger than the conclusion, since it constrains every realizable
table and not just the count. The same counting also shows the lemma's
analogue fails at sixteen. All `2**65536` sixteen-input tables have programs,
so at least three quarters of them have no program lighter than 65,534 bits.
The shipped build weighs at most 112,769 bits (measured with `trace.c`, which
counts a cell executed with `A` in `{'0','1'}` in any row at `log2 7` and a
cell touched both ways at 3). Of that, 14,465 bits are its 5,553 shared code
cells and 98,304 are its 32,768 label cells. So any proof has to use the one
thing that separates seventeen from sixteen, the ceiling. The lemma says a
lightest program never uses more than 131,071 of the 177,147 bits of the
store, which means at least 46,076 bits (15,359 cells' worth) must always be
wasted. The sweep shows the waste cannot be in reaching cells. If the lemma
holds, the waste must be in making different rows read different cells and
decoding what they read. The sweep does neither: every row reads the same
cells. Nothing here proves or refutes that. Evidence either way is the
construction side: a working seventeen-input build with 49,152 table cells
and ~8,400 code cells would weigh roughly 169,000 bits (estimated), and for
most tables it would have to be near-lightest.

### Seventeen: code and data in the same cells

Every build keeps table and code in separate cells, which leaves about 9,897
non-table cells. Cells can do both jobs in three ways, and none frees
meaningful room.

- **Code whose character choice carries table bits.** An executed cell can
  hold a table bit only if another character at its address leaves every
  row's output unchanged. After running, the cell holds `xlat2` of its
  character, a bijection, so a later data read could recover the choice.
  This was measured on the shipped sixteen-input build (`slack.c`). Of the
  5,553 cells touched in every row (5,529 executed, 4,624 of them `o`),
  1,248 admit an alternative that passes 256 spread rows. There are 2,126
  such alternatives, almost all `*` or `p` in place of an `o`, and
  `sum log2(1 + alternatives)` is **1,760 bits**. That is an upper bound,
  since the screen is a superset. On cells `0..1585`, where every candidate
  was also run on all 65,536 rows, 113 of 184 survived. So the true figure is
  near 1,100 bits, and joint use can only lower it. 1,760 bits is at most 660
  table cells at `8/3` bits a cell (estimated conversion). Recovering those
  bits needs a read path to code addresses, which the positional fold does
  not map to, and one navigation hop costs 140-350 cells. There is a hard
  cap as well. Where `A` and `mem[d]` are dead, only `o`, `*` and `p` are
  harmless (`/` shifts the inputs later reads see), so an executed cell
  carries at most `log2 3` bits. Even if all 9,897 non-table cells were dead
  code, that would be 15,700 bits, or about 5,900 table cells.
- **Table cells on the main path.** Execution is contiguous, so every cell of
  an executed stretch must be harmless for every table value. That leaves
  `log2 3` bits a cell: eight rows need 6 executed cells where a plain group
  needs 3, and the stretch does no other work. That is a table at half
  density, not shared code.
- **The pointer and label region as data.** The `j`/`i` landing cells
  `34..127` hold at most `94 * 3 = 282` bits, about 106 table cells.

The only large slack is inside the table. A three-cell group uses 256 of its
512 triples, so 16,384 bits (5,461 cells' worth) are spare; the decoders
spend that freedom, since they read seven meanings a cell and need 256 of
the 343 meaning triples. Packing tighter is costed under "Seventeen: packing
and a stateless fold" below. With seven meanings it frees at most 2,463
cells, not the 4,096 an eight-meaning count suggests. So sharing cells
between code and data frees at most a few hundred cells on the measured
build, not the thousands a seventeen-input decoder would need if the
measured per-state costs hold.

### Seventeen: straight-line programs

The missing lemma was tried on a restricted class first. It is still open
there, but the attempt settles which decoders the class allows.

**The class.** Call a program *straight-line* if no row executes `i` before
its output and no cell runs after it has been written, including by the
encipher, so no cell runs twice.

**Fact 1 (one tape).** In a straight-line program `c` only increments, and
every cell it runs still holds its source character. So step `s` runs the
source instruction of cell `s` in every row. The output is the first `<` on
that tape, at the same step in every row, and every row makes the same number
of data reads at the same steps. Rows differ only in `A`, `d` and memory.

**Fact 2 (the counterexample is straight-line).** `sweep17.py`'s program
executes no `i` and runs no written cell (checked by simulation). So the
per-program bound fails inside the class too, and a class-restricted lemma
still has to come from minimality. The class keeps the whole pointer toolkit:
lockstep sweeps, and landing on a word written into a low cell, which is two
`j`s through a low cell that holds its neighbour's address, as at cells
114-116 and 56-57. So revisiting a row-dependent cell costs a few tape
cells. Reaching cells cannot be where the class loses.

**Fact 3 (the printed word; all programs).** In a valid run, let `y` be the
word printed by the one `<`. Because `256` is even and every `3**k` is odd,
the answer bit is `y mod 2`, the parity of `y`'s trit sum. The last
instruction to set `A` before the `<` was `/` (then `y` is an input), `*` or
`p`. Exhaustively over all 59,049 values of `A` (`outputs.py`):

- `*` of a plain character (33..126) never prints `0` or `1`.
- `p` with a plain operand prints a digit for at most 30 of the 94 operands,
  whatever `A` is.
- No `A` offers even one fixed digit among the admissible characters at every
  address: the best reaches 78 of 94 residues. Both digits are available at
  47 residues at best.
- Landing on a cell and printing through `p` at once (`A` is then the
  pointer, the cell's address minus one) offers both digits at only 202 of
  59,049 addresses.

A plain table cell used as the final operand therefore cannot carry an answer
at every address. A straight-line program has no label stubs, so its table
bits must reach `y` through written words.

**Fact 4 (lockstep readers; exhaustive).** Suppose a group `h, h+1, h+2` is
read in consecutive steps, each cell by `p`, by `*`, or not at all, starting
from any of the 59,049 values of `A`, and the result is printed. Then at
every residue (`readers.c`, whose all-`p` figure was cross-checked by brute
force):

- reading all three cells by `p` leaves at most **137** of the 512
  admissible triples printing a clean digit;
- any pattern containing `*` leaves at most 40;
- a pattern that skips a cell sees at most 64 distinct triples;
- a pattern ending on `*` prints nothing clean.

Eight rows need 256 triples that print cleanly for every row, and one row
already allows at most 137. So **no lockstep reader decodes a three-cell
group**, whatever `A` the rows bring. A straight-line decoder has to jump:
`j` on a table cell moves `d` into `34..127`, and landing on a word derived
from the values read moves it anywhere.

**What is left.** Within the class, the lemma reduces to decoders that use
landings. A row folds its group's values into a word (through low-cell
lookups and lockstep `p`s) and lands on prepared cells, where Fact 3 limits
the print. The honest next statement is a finite one. Bound the answer
region that a landing decoder needs per decoded group pattern. Each landing
target prints for only one pointer value, so a residue-independent 512-colour
code with eight rows needs up to 4,096 targets (estimated, not searched).
Then check whether main code, fold and targets exceed the 9,897 non-table
cells. The obstacle is computing a residue-independent colouring of the
admissible triples with `crazy`, `rot` and lookups alone. No such colouring
circuit is known, and none has been shown impossible. The class-restricted
lemma is open.

### Seventeen: packing and a stateless fold

Two cheaper alternatives to the five-state decoder were checked: packing
the table tighter, and a decoder with no states at all.

**Packing, at the decoder's real alphabet.** The working decoders read seven
meanings a cell, so `2**r` rows need `k` cells with `7**k >= 2**(2**r)`.
That gives `k/2**r` = 0.375 at 8, 16 and 32 rows (3, 6 and 12 cells): no gain
over three-cell groups. The first saving is at 64 rows in 23 cells, which
leaves 47,104 table cells and frees **2,048**. The limit `2**17 / log2 7` is
46,689 cells, freeing 2,463. The 4,096 quoted earlier for 11 cells per 32
rows assumed eight meanings, which no decoder reads.

Against that ceiling, a 23-cell decoder pays per state. From the measured
parts, one state costs about 500-1,800 cells (estimated): two view
constants at 130-750 each, a read routine of 47-123 and its landing blocks.
So it pays only if it needs at most about four more states than the five
already built. Its margin is `7**23 / 2**64` = 1.48, against 1.34 for the
three-cell code that needed five states. Checking any such decoder means
covering `2**64` answer vectors, beyond the exhaustive checks used so far.
Unless the seventeen-input budget ends up short by less than about 2,000
cells, packing is not worth it.

**A stateless fold (straight-line, measured).** The cheapest straight-line
decoder has no states. Each row `r` loads a constant, reads its group's
three cells by lockstep `p`, and so holds a word whose low five trits are
`L_r = crazy(crazy(crazy(a_r, v0), v1), v2) mod 243`. Plain operands never
touch the high trits. The row then lands in its own 243-cell window, shared
by every group, whose cell `L_r` prints a fixed bit. The eight windows would
cost 1,944 cells, and the design needs no view constants, hubs or states.
It fails:

- *Intrinsic loss (exhaustive, `fold_classes.py`).* At the worst residue,
  the 512 admissible triples fall into only **272** classes that no fold can
  separate: two triples in a class give equal `L` for all 243 constants. So
  the eight row bits must map 272 classes onto all 256 vectors, with each
  bit a function of its own row's view.
- *Search (measured, `fold.c`).* Choosing constants for distinct joint views
  plateaus at that 272 by the third constant. Annealing the window contents
  covers at most **20,364 of the 24,064** (residue, answer vector) pairs
  (84.6%, best of five runs, two of them with separate windows per parity).
  A decoder needs all of them.

So a straight-line decoder cannot fold a group once and look the answer up.
It has to land more than once, carrying information between landings, which
is what the states of the five-state decoder do. That is evidence, not
proof, for the class-restricted lemma: the class keeps cheap navigation but
seems to need staged decoding.

**The decoder itself** is being measured on the other line of work (five
states, 2,744 of 2,744 cases on real sources, setup about 7,500 of the
8,957 cells left after the landing blocks). What it still lacks is
table-free landings and the seventeen-input address computation.

### Seventeen: where the code can run

The budgets above count every non-table cell as room for code: 9,897
cells, or 8,957 after the landing blocks. Executed code, though, needs
*contiguous* table-free cells. The instruction pointer only steps forward,
so code that reaches a table cell executes table data, and leaving one free
run for another costs an `i` hop plus the navigation that sets it up (tens
to hundreds of cells). The one-group prototypes never met this, because
their table is a single group.

Under the six-slab tiling the free cells are
`(z = 0 and some digit missing) or (two or more digits missing)`. Only
the pieces where a *high* digit is missing are long. With `z` as the top
trit and the digits in order, the free set is:

- one 2,187-cell block (the top digit missing), which becomes a 2,460-cell run;
- eight 243-cell blocks, which become 273-cell runs;
- 64 blocks of 27 cells;
- 512 triples;
- about 2,500 scattered cells where `z != 0`.

That is 896 runs in all. Searching every choice of `z`, every cell-index
trit and all 105 pairings, with missing values `(0, 0)` or `(2, 2)`
(`tiling_runs.py`), the best tiling leaves **5,127** free cells in runs of
200 or more (measured). The rest can hold landing cells, pointer cells and
hubs, but not code.

So the code budget is about 5,100 cells, not 8,957. Against it:

- the compacted sixteen-input main code is 2,391 cells (measured);
- the five-state decoder's setup, measured on one group, is about 7,500,
  of which the ten view constants alone are roughly 4,000.

Together that is roughly 9,900 cells of code for about 5,100 cells of room,
before the six-slab address computation, which needs a separate case for
the pinned slabs. The five-state view-constant design does not fit the
tiling it assumes. It would fit only with a layout whose free space is
mostly contiguous. Among digit-local layouts that means covering the
low-digit holes with more slabs, and every extra slab is another case in
the address computation.

Decoders that spend data rather than code were checked for coverage and
fall short (measured, annealing over window labels; `fold.c` and variants):

| design | windows | best cover of 24,064 |
| --- | --- | --- |
| one `p p p` fold, 8 row windows, labels 0/1 | 8 | 20,364 (84.6%) |
| rows paired by the last input, labels `0 1 x n` | 4 | 19,227 (79.9%) |
| two stages: land on `W2`, then on `W1` or `W0` | 24 | 21,427 (89.0%) |

A fold of two adjacent cells, taken over all 243 constants, separates at
least 54 of the 64 admissible pairs at every residue, more than the 49 that
seven meanings give. A single constant separates at most 38 at the worst
residue, though, and a read destroys its cells. So no fold read beats seven
meanings a cell in practice, and the table stays at 49,152 cells.

**A seven-box tiling puts the free space at the bottom (measured).** Drop
the slab that pins the top digit, which is itself a contiguous block, and
spend its 1,024 groups on two `z = 0` boxes that pin a low digit instead:

- A: `z` in {1, 2}, all digits normal (8,192 groups);
- B: `z = 0`, all normal (4,096);
- C1-C3: `z` in {1, 2}, digit 1, 2 or 3 pinned (1,024 each);
- D1, D2: `z = 0`, digit 1 or 2 pinned (512 each).

That is 16,384 groups, pairwise disjoint (checked cell by cell). The top
digit is never pinned, so no group uses its missing value. Put that digit on
trits 8 and 9 with missing value `(0, 0)`, `z` on trit 7, the cell index on
trit 0 and the other digits on `(1, 2), (3, 4), (5, 6)`. Then cells
`0..6806` are one free run at the bottom of memory, the same shape as the
sixteen-input build's code region below 6,561. Eight more runs of 246 remain,
and **8,529** free cells lie in runs of 200 or more, against 5,127 for any
six-slab tiling.

The routing stays simple:

- the top digit always takes its own three input bits;
- digit 3 takes its own bits unless pinned;
- digit 2 takes its own bits unless pinned;
- only digit 1 changes source: its own bits in A and B, pinned in C1 and
  D1, digit 2's bits in C2 and D2, digit 3's bits in C3;
- `z` is `1 + x2` in A, 0 in B and D, and `1 + x5` in C.

With the combining steps shared as a prefix tree, the address computation is
about ten digit combines instead of four, plus the dispatch (estimated). The
code budget is then about 6,800 contiguous cells for the main line, with
the state blocks and stubs, which are entered by `i` anyway, in the 246-cell
runs.

**An address fold for the seven-box tiling (word-level, `address17.py`).**
Fourteen address bits fold into 16,384 distinct group words. Every step is
a `crazy`/`rot` that a source string executes, but this is checked as a
word model, not yet an emitted program. The table cells are pointer + 1:

- 49,152 table cells, the lowest at 6,562, so cells `0..6561` are one free
  run;
- eight free runs of 243 cells;
- 8,530 free cells in runs of 200 or more.

The steps:

- The shipped gadget runs on each input triple.
- The accumulator starts at all-2.
- Each digit enters with `A` = accumulator, as `p` over the gadget cell and
  then `*`. So the gadget runs first and its outputs combine later from
  their cells, which lets each case take its slots in its own order.
- `v` is pre-mapped through `crazy(all-2, ·)` so its high trits read 1.
- `z` is a single-trit step between the third digit and the top.
- A fixed tail follows, then one `crazy(Q, acc)` per decoder state. `Q` is
  all-2 except trit 0, which picks the cell.

Two constraints decided the details.

1. *No table cell may wrap to cell 0.* Cell 0 is the first instruction
   executed, and a group whose pointer word is all-2 would put a table cell
   there. Every per-trit bijection available from `crazy` with a constant is
   swap01 or swap12, applied to all information trits at once, so the
   all-2 group is excluded only if some digit misses an equal pair
   `(r, r)`. The top digit also has to miss an equal pair, a different one,
   for the bottom block.
2. *The shipped combine gives only one equal pair.* With every digit
   entering `v` then `u` in the same form, only `(2, 2)` is reachable (swap12
   variants on `u`, `v` or both, searched).

A trit-level solver that tracks each information trit's permutation from
entry found 53,613 configurations once the top digit enters `u` the other
way round (`acc = crazy(crazy(all-2, u), acc)`). The one used here has:

- lower gadgets from walked values `(33, 33, 78)`, swap12 on `u` in slots 0
  and 1, so both miss `(1, 1)`, and on `v` in slot 2, so it misses a pair
  that the tail sends into {0, 1}²;
- the top taking the same `(33, 33, 78)` gadget, since a triple is read
  only once, with `u` and `v` swapped, missing `(2, 2)`;
- the pinned slots on a gadget from `(38, 38, 38)` run on all-0 reads, which
  yields exactly the missing value;
- `z` base 29514 (A and C use two `z` codes, B and D the third);
- the tail swap01, swap12, `p` with all-1 and trit 0 = 2, after which trit 0
  of the per-state pointers takes all three values.

All seven boxes are disjoint, and no pointer is all-2. Because slot 2's
missing pair lands in {0, 1}², three of the eight 243-cell runs are landing
windows (their top five trits are all 0 or 1), which with seven in the
bottom block gives exactly the ten the five-state decoder's views need:
blocks 1, 3, 4, 9, 10, 12, 13, 28, 82 and 109. The routing is the
one above: the top digit takes the pinned digit's triple in C and D, the
case selector and C's `z` bit come from the top triple, and B, D share
the third `z` code.

**The budget with this layout (partly measured).** Code room is:

- the bottom run of 6,562 cells;
- less the startup, pointer and walked region below 420;
- less the seven landing windows inside it (1,701 cells);

which leaves about 4,440 cells for the main line. The five spare 243-cell
runs add about 1,200 for blocks entered by jumps (state blocks, stubs,
case blocks).

Against that room:

- *Setup and decoder.* The other line of work measured about 7,500 cells
  for setup plus a compacted one-group five-state decoder, excluding
  address and per-row work. About 4,000 of those are the ten view
  constants. A per-row parity word, where each state's view is
  `crazy(rot^k(P), base_q)`, needs five base words and one parity
  computation. The parity XOR can be accumulated as a trit in {1, 2},
  since `crazy(0, ·)` fixes 1 and 2 and `crazy(2, ·)` swaps them. That
  should bring the ten views to about 1,500 (estimated).
- *Address computation.* Emitted with the shipped planner but not yet
  placed for cost (measured):
  - the captures of `x1`, `x2` and the five gadgets take 4,117 cells;
  - one case's combine sequence takes 3,802.

  The cost is navigation. The planner reaches a walked cell by landing in
  the pointer region and stepping up, so cells near 400 cost about 300 steps
  per op. The shipped build keeps its gadgets just above 128 and pays 113-314
  per gadget. None of the 79 consecutive walked triples above 128 with an
  injective trit 0 matches the solved gadget pattern, so a placed version
  needs the fold re-solved per slot over the patterns that occur. At the
  shipped build's rates the address computation would be about 2,000 cells
  or more (estimated).

The sum is roughly 7,000 cells of code against about 5,650, some 25% over.
That estimate rests on the unbuilt parity word and on a placement not yet
done. Closing it needs savings on the label and hub setup, which is about
2,000 of the 7,500, or on the case structure, beyond everything above.

**Routing through plain characters (checked, fails).** Every build executes
the low region at startup, so the pointer cells `34..127` hold fixed
enciphered values. That is why routing needs run-time hub values, and label
setup costs about 2,000 cells. The low region need not run:

- A startup `j` from a cell below 34 lands on a pointer cell. Two to four
  `*`/`p` ops there, each followed by a `j` back through its neighbour,
  build a word, and an `i` jumps past the region. For example, a `j` at
  cell 10 lands on cell 125, and three ops there make a word that jumps
  to 3,272.
- The pointer cells then keep their source characters, with eight
  choices each.

Routing a landing to one of the four targets through those characters,
with no run-time labels, would need each label's pointer cells to meet
every translate of the admissible set `I`:

- In one hop (landing character to pointer cell to a target-word cell),
  each word cell `W` admits exactly the eight pointer cells where `W - 1` is
  admissible, a single translate of `I`. No union of two translates hits
  every translate (checked for all pairs).
- In two hops, a label's first-level cells lie in a union of translates, one
  per second-level cell. Unions of three translates never hit every
  translate (all 4,278 checked with one fixed at 0), and unions of four
  rarely do (21 of 8,529 sampled). So each label needs about 24-32
  first-level cells, and four labels do not fit in the 74 cells left after
  the word and second-level cells.

So run-time label values stay. The startup jump would still let the walked
constants start from chosen characters rather than fixed enciphered ones,
which shortens their chains (not measured).

### Seventeen: the one-group build, measured, and where the cost really is

The five-state decoder on one 3-cell group was built on **real source** and
run through `msim`: `scripts/malbolge17/prototype/five_esc.py` emits one
program per startup row `s`, patches the three table characters for every
meaning triple in `7^3`, and checks the printed answer. It is green:
**2,744 / 2,744** correct across the eight rows. So the mechanism — value
decode, per-state view constant, land, trampoline to one of four shared hubs
(print0, print1, state 3, state 4) — works end to end on the interpreter, not
just at the trit level. The full single-group program is about **12,900 code
cells** (12,897 for row 0), and instrumenting the build shows where they go:

| phase | cells |
| --- | --- |
| constants + priming the 94 pointer cells | 1,635 |
| chains: `z`-cells, `C0`/`C1`, the ten views, escape | 5,957 |
| label chains (5 seeds + per-label pointer ops) | 2,127 |
| hub rotations | 2,350 |
| landing characters + decoder block | 828 |

**Navigation, not op count, is the cost (measured).** The program is only 24
hubs, 679 raw ops and 525 `op` calls, yet 12,897 cells: reaching a walked
cell means walking the pointer up from the pointer region, so each op there
costs tens of cells. Two spot measurements make it concrete:

- The ten view cells are chains of 8, 6, 8, 5, 8, 6, 8, 4, 8, 6 ops — only
  **67 ops** — but emitted they are about **3,561 cells**, because each op
  on a cell near address 160 costs ~30-70 cells of navigation. This
  confirms the earlier "about 4,000 for the ten views"; the op count alone
  badly understates it.
- Hardcoded addressing of one group (three `z`-cells holding `Gb-1+k`) is
  about **230 cells**. That is small, and it is exactly what the address
  fold replaces per invocation — so the fold is worth its own cost only once
  the ~16,384 groups are counted, and the single-group figure above is not
  where the fold pays off.

So the gap-closing lever is cutting **ops-at-distance**: fewer distinct
high-address chain targets and a tighter working band. The ten view constants
factor exactly as `crazy(A[parity], B[state])`, with
`A = (39122, 39365)` and `B = (364, 1093, 2551, 3280, 6925)`. The two `A`
words differ only at trit 5. Operationally, a cell holds their inverse
rotations `(58318, 59047)`; `crazy(1458, cell)` swaps them,
`crazy(0, cell)` fixes them, and `*` loads the selected `A`. A subsequent
`p` over one of five state bases produces the view. Loading the parity cell
rotates it, so it is consumable; the decoder's maximum path length is three,
and three copies cover every path.

All five bases, three initial parity words, and the toggle operand have explicit
chains at distinct cells in `131..165`. `scripts/malbolge17/parity_views.py` executes
the identities and chains through the interpreter's word operations, then
emits them through the generator's real planner. In ascending-address order,
the five bases cost **937 cells**; adding the parity words, toggle operand and
three reducer masks costs **2,757 cells** total. This replaces the ten
scattered views' measured 3,561-cell setup with an 804-cell reduction before
wiring parity production.

### Seventeen: navigation is linear in address, so packing helps (measured)

The per-op navigation cost was measured directly. A three-op chain emitted
at a walked cell costs, by the cell's address:

| cell | 3-op chain |
| --- | --- |
| 135 | 48 |
| 200 | 241 |
| 300 | 537 |
| 410 | 869 |

So the cost is roughly linear in `(address - 128)`: an op on a cell near 135
costs ~16 cells, one near 410 costs ~290. `five_esc` lets its walked cells
drift up to ~420 (the allocator takes the first free cell that can produce a
value), which is why the setup is ~12,900.

The build needs about **26 distinct walked value-cells** after replacing ten
views by five bases, three parity words, and their shared toggle operand. The
exact factorization above supersedes the direct ten-view assignment: its
twelve constants fit at cells `131..197` and emit in 2,757 cells.

The factorized reads were also substituted into the real-source one-group
prototype. Every row and meaning triple remains green (**2,744 / 2,744**),
so consuming one base per state and one parity cell per decoder depth works
through actual Malbolge execution. Row 0 first fell from 12,897 to 10,687
code cells. A backlink then cuts hub setup: `H+2` points through the label
cell back to `H+1`, so every rotation after the first costs two `j`s rather
than fresh navigation; the dense-table escape uses `H+3` instead. Finally,
the escape-only label carries the convergence word itself, so no separate
escape constants are built. A label-specific seed followed by two `p`s at
each pointer cell maps the whole label directly to one hub. Each `H+3` may
then point through any escape-label cell; all such cells converge on the same
escape hub. Only five escape-label cells are needed: the unused pointer cells
reachable from the next table cell, plus the four hub backlinks. The prefix
`o j j` therefore gives each label one shared block. The executed row sizes
are now **5,420**, 5,472, 5,317, 5,607, 5,664, 5,607, 5,461 and 5,306.
These fixed-group builds initialize the known parity
directly, so they exclude the full address reducer.

Row 0 now splits into 549 cells for constant setup, 2,315 for value chains,
2,095 for two-pass label assignment, 77 for hub rotations and 384 for
landing/decoder blocks. All 2,744 real-source executions pass.

This quantifies the lever. The one-group setup is navigation-bound, and its
cost is not fixed. Address parity has a straight-line reducer: applying
`crazy(all-2, ·)` then `crazy(all-1, ·)` maps each pointer trit to 2 exactly
when it was 1. Ten rotate/folds into an all-2 accumulator XOR those ten
indicators; folding the result over a mask with only trit 6 equal to 1 yields
1458 exactly when the group base cell is odd, otherwise 0. Three mask copies
toggle the three consumable parity cells. `address_parity.py` checks all
16,384 group pointers and all 49,152 cell parities, including the fixed
within-group offset. The reducer is now wired into `five_esc`: it derives the
indicator destructively from a group pointer, folds all ten rotations into an
all-2 cell, reloads that accumulator through zero and applies three mask
copies to offset-initialized parity cells. All 2,744 real-source executions
still pass. Scheduling the even-offset cells before the odd-offset cell lets
each completed parity word feed the next mask without reloading the
accumulator; two-read rows also omit the third mask. The dynamic-parity row
sizes are **7,145**, 7,152, 7,529, 7,894, 7,906, 7,894, 7,142 and 7,519;
the reducer phase itself costs 1,082--1,159
cells. What remains is address-fold integration and roughly 2,350 cells of
setup reduction against the ~5,650-cell tiling budget.

The address emitter now runs every fixed A/B/C/D path as real source.
`address_gadget.py` jumps over the pointer region, resets the resulting
accumulator, captures four triples, pre-maps their `u`/`v` words, streams the
three lower slots, folds fixed `z`, applies the reversed top slot and finishes
the tail. The B path and A's two `z` paths match the word model on all 12,288
suffixes in **2,368**, 2,368 and 2,297 code cells. C/D consume the selector
triple, substitute a constant-input PIN gadget into one lower slot and reuse
the selected normal triple on top; all 4,096 special addresses pass in
1,621--1,714 cells. Thus all 16,384 fixed paths execute correctly. The
first dispatch is also emitted: rotating a `48/49` encoding separates A's two
branches by 19,683 cells; both write their `z` word into one cell and `i`
through a shared reunion pointer. The combined **2,501-cell** A program passes
all 8,192 rows. A second nested dispatch now separates A from B, consumes
`x2` on both sides and feeds all three ordinary `z` words into the same
reunion. The combined **2,786-cell** A/B program passes all 12,288 covered
rows. Its `x1x2 = 00` block captures the three normal triples, builds the
constant PIN triple and dispatches `x12..x14` to eight C/D leaves. Each leaf
writes `z` and enters one of three pre-rotated reunion pointers, sharing the
verified suffix for that selected slot. Packing the PIN triple into the
ordinary walked band, while withholding those mutable cells from ordinary
navigation, cuts the combined program from 11,883 to **7,888 cells**. It
executes all 16,384 group addresses correctly. A shared continuation then
constructs the group pointer and runs the straight-line parity reducer. The
Reuniting all four top folds before their identical final tail cuts the
parity build further. The **11,241-cell** combined source returns the exact
0/1,458 operand on all
16,384 rows and initializes the three consumable parity words; all 49,152
address-plus-offset parities execute correctly. Decoder and table integration
remain. This source is an execution certificate, not a placed table build:
8,746 of its 11,233 distinct instruction cells overlap table cells, leaving
only 2,487 already in the complement. The next construction step is therefore
relocating and reuniting these paths into the bottom run and spare windows,
not appending the decoder at their current addresses.
