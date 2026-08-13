# Limitations and ruled-out ideas

What the generators cannot do, and the assessments that concluded an
approach is not viable (or only partially viable).  Completed work lives in
the commit history; this file records the walls, the negative results, and
the reasoning behind them.  Genuine future work is in `docs/roadmap.md`.

## 6-5 (built; the decision tree stays primary)
The arithmetic-kernel generator (`six_five_arithmetic`) was built: it packs
the inputs into `x` and the table into `T = sum table[i] * 2**i` and
computes `f(x) = (T >> x) & 1` by halving `T` x times, with 8 loop
constructs and 27 markers both constant in `n`.  It verified exhaustively
for every table at `n <= 3` and sampled through `n = 16`.  But **constant
program size is impossible**: a program that must work for any table has to
embed the table, and the single-integer representation 6-5 requires (the
pointer cannot net-advance, so there is no computed array indexing) costs
O(`2**(2**n)`) characters for dense tables.  A ~2 MB setup guard rejects
the `n > 5` and large-`T` region (AND-n is the pathological case), and
runtime is O(x*T) — minutes at the size guard.

The decision tree therefore stays primary: for `n <= 5` it generates every
table with no rejection, ~µs runtime, and a flat 44-914 chars, while the
kernel is the fallback for `n > 5` (small-`T` tables only).  Measured at
`n = 4` the tree runs ~46,000x faster and generates programs 13x smaller
for the same table.  (The `T <= 2**20` guard and the complement fallback
for mostly-ones tables are part of the kernel's design.)

This closes the "constant-loop boolean generator" goal entirely: the
constant *loop-count* half is met (8 loops, 27 markers, both constant in
`n`), the constant *size* half is impossible (any table needs its `2**n`
bits embedded), and no other language needs the design to lift a cap —
CircleFuck's decision tree is total (verified exhaustively to n = 3,
sampled to n = 16), so the label-cap motivation is gone.

## ZTOALC (built; dense non-symmetric n > 3 wall)
The generator (`ztoalc_boolean`) lays a decision tree on `p * 2**k`
descents: branching at an even root lets a zero bit continue the descent
(the Collatz step halves it) while a one bit jumps to `root + 1`, whose
Collatz step lands on `4 * q`, so every branch gets a predictable,
non-revisiting path.  It verified exhaustively for every table at `n <= 3`
and for structured tables at `n == 4`.

The wall: all trajectories converge to the `16, 8, 4, 2, 1` tail, so a
dense full tree like XOR4 has every leaf's tail sweep through another leaf,
and no `b1` works.  For **popcount-symmetric** tables (XOR = parity, AND,
majority) the generator falls back to a branch-free *linear* program: sum
the normalized input bits with `s += x_i`, look the result up in a small
`n + 1`-entry array, and print.  Every line sits on the pure power-of-two
descent from `2**L`, so it is guaranteed collision-free — but it is `2**L`
lines (XOR4 is 524,288; gated at `2**22`).  Only dense, non-symmetric
tables past `n == 3` still raise `ValueError`; those need a full `2**n`
result table, which would be `2**(2**n)` lines and cannot be materialized.

Two notes: the interpreter was brought in line with the wiki spec so that
`lhs = rhs` / `+=` / `-=` write an `array[index]` element (previously they
created a variable named literally `"arr[i]"`), which is what makes the
linear fallback possible.  And further optimization is marginal: the
tree's `b1` search and the linear program's command count are both near
their structural minimums.

## 3x (built; the constant-bit guard skip is unsafe)
The generator builds one shared decision tree (rows sharing a bit prefix
share the prefix's guards), roughly halving structured tables at `n >= 5`
and never making one worse.  A constant-bit guard skip was considered but
is not safe: a guard also separates differing rows from default rows that
share the prefix, so a "redundant" bit test cannot be dropped without
checking the default rows too.  The sibling idea (pre-negating stored
input bits to halve `not_bit`) remains open but is marginal.

## Minifuck (limited to 0-preserving functions, n <= 3)
`[` followed by `<` is a conditional pointer move: `[` moves right, flips
that bit, and skips the following instruction *and* flips the next bit only
when the flipped bit is zero, so after `[<` one input state executes `<`
while the other skips it.  The tested bit's value thus survives in the
*pointer displacement* while the pool can be re-zeroed for another read.

Every working program fits one read-prefix plus a tiny decode suffix.  The
shared n == 2 prefix `<[<.[<[<[<[<[<[<[<` reads b1 (`<[<.`), then a `[<`
run walks the pointer right while clearing the pool, and the next `.` reads
b2; the pointer ends at 8 (b1 == 0) or 7 (b1 == 1).  Exhaustive suffix
search over `{<,.[}` reaches *exactly* the 0-preserving two-input tables
(f(0, 0) == 0): AND, OR, XOR, both echoes, and const-0 — 8 of 16.  A
three-input function reuses the same prefix, adds a second walker, and uses
the same `<.` suffix (`b3 XOR (b1 AND b2)`, verified 49 chars).

The limitation is structural: the decode suffix flips the pool LSB only
when the pointer sits at cell 7, and `[`'s skip always maps bit 0 to the
higher pointer position.  So the pointer orientation is fixed and the
genuinely two-input functions are forced to f(0, 0) == 0: XNOR, NAND, NOR,
and NOT-b2 are unreachable — no complemented read-prefix exists (searched
to length 11) and full-program search to length 14 finds none.  The n == 4
walker stage additionally cannot reach the 8 distinct pointer positions a
third bit needs.  A generator is therefore limited to 0-preserving tables
with n <= 3 at most, and not to arbitrary boolean functions.

## RAM0, BitDeque, Minsky Swap (not viable for the template model)
These three have value-testable branches and clean setters, but their jumps
are *absolute token indices*: RAM0's digit-`GOTO`, BitDeque's `GOTO N`, and
Minsky Swap's `~` targets are all fixed positions in the token/command
stream.  The parameterized template's bit setter has variable length (e.g.
RAM0's `Z` for a zero bit vs `Z A` for a one bit; BitDeque's `INVERT` vs
nothing), so substitution changes the token count and every jump target
shifts — a fixed template cannot be correct for all instantiations.  Only
Back avoids token-index jumps (its `+`-advance condition is positional), and
its decision tree was built as a mirror tree on the 2D beam grid
(`booleans/parameterized.py`), so the template class is now complete: BIO
and Back built, these three and Eval blocked.

## Eval (not viable for nested parameterized trees)
Eval was surveyed as capable for input-by-substitution boolean generators
(it has output, constant construction, and a `?` skip-if-zero branch), but
building a decision tree requires nesting: each subtree must be a string
evaluated with `!`.  This is a **spec** limitation, not an interpreter bug
(the interpreter matches the wiki exactly): the wiki defines stringmode as
"the backquote character appends the `"` double quote character to res, the
`"` double quote character exits stringmode", with no way to escape a
backtick or include a literal one.  So a pushed string can never contain a
backtick, and a nested `!`-evaluated subtree (whose own string-literal
delimiters need escaping at multiple levels) cannot survive more than one
wrap.  The wiki's examples only ever use single-level `!`.  Eval is
therefore not viable for the parameterized class.

## MAMMALIAN (branch-free core built; general n-bit functions open)

A *branch-free* approach works, verified against the real interpreter — no
`LEAPFROG` needed.  `DIGEST` is `acc ^= sum(curr)`, a free XOR over GF(2),
and `SPRINT` moves the pointer by `curr[acc]`, so a bit can index a cell.

- Normalizing an input to a clean 0/1 bit: `48 SEEDs DIGEST ACCEPT DIGEST`
  leaves `acc = ord(bit) ^ 48` in `{0, 1}` and `lst[0] = [48, m]` (48 is
  special because `48^48 = 0` and `48^49 = 1`).
- 1-bit identity (verified): `48 SEEDs DIGEST ACCEPT DIGEST CONSUME DIGEST
  PRONOUNCE` — the `CONSUME DIGEST` tail turns `m` into `48 ^ m`.
- 1-bit NOT (verified): `48 SEEDs DIGEST ACCEPT DIGEST SEED CONSUME DIGEST
  PRONOUNCE` — `SEED CONSUME DIGEST` turns `m` into `49 ^ m`.
- 2-bit XOR (verified): `48 SEEDs DIGEST ACCEPT DIGEST CONSUME CONSUME ACCEPT
  CONSUME PRONOUNCE` — the second read normalizes against the running parity,
  and the input byte itself carries the 48 base, so no branch fires.
- AND gadget (derived, not yet integrated): `CONSUME SPRINT CONSUME` on
  `lst[0] = [x, y]` computes `x AND y`; with the bits in separate arrays,
  `SPRINT CONSUME` suffices.

The old `LEAPFROG`-dispatch barrier (forward targets need negative cells) is
real but moot: the promising path is arithmetic plus pointer selection, not
control flow.  The n-bit case, however, is blocked by three mutually
conflicting constraints:

- `ACCEPT` unconditionally appends the normalized bit to `lst[0]`, and
  consuming that bit needs `ptr == 0`, but routing `SPRINT`s move the
  pointer to a node — so the bit cannot be both read and routed without a
  way to return the pointer to 0.
- The read's clean normalization needs `lst[0][0] == 48` (the `^ 48` base),
  and `SEED` skips empty arrays, so the only constant source is `K SEEDs
  CONSUME` starting from `lst[0] = [0]` — which empties the array, so every
  later constant **accumulates** on the previous one (`42 + 5 = 47`, never a
  clean `5`).  The `[48, C, m]` triple a branch needs therefore cannot be
  assembled in one array.
- `DIGEST` normalizes by XORing the *sum* of `lst[ptr]`, so a bit buried
  among previous bits is only recoverable as part of a sum, and `48 ^ (48 +
  m1 + m2)` is not `m1 ^ m2` when both bits are set.

A verified generator is thus a hard wall, not just a slow build; the 1-bit
and 2-bit pieces are proven, and the AND gadget (`CONSUME SPRINT CONSUME`)
works on clean separate arrays that the read flow cannot produce.

## Dotlang (not viable)
Dotlang's only input-dependent branch is the `W~` warp, which reads a line
and teleports the dot to the *first* `W<bit>`s` marker in the grid (the
interpreter's `find` scans rows top-to-bottom).  A single-bit program works,
but every deeper level of a decision tree re-enters those same first-match
markers, so the branch history is lost: the second `W~` lands back on the
first `W0`s`/`W1`s` and loops.  The type conditionals (`!?:`) cannot help —
input digits are converted to `int` 0/1 by `dot.new`, so both bits share the
same type — and there is no value comparison or arithmetic.  Only a fragile
direction-routing trick could express more, and it caps at three inputs
before the eight (marker, heading) states run out, below the verification
bar.

## Polynomial numeric root-finding (ruled out; instruction recovery is exact)
The Polynomial interpreter used to find a program's roots numerically, and
every floating-point solver was defeated by the root geometry.  The
generator emits exact integer polynomials whose coefficients far exceed
float64's exact-integer range (2**53) once a few instructions accumulate —
`'Hello, World!'` has coefficients up to 10**95 — so `numpy.roots` silently
rounded them and solved a different polynomial, losing the small imaginary
parts that encode instructions.  The interpreter now factors the monic
integer polynomial over Z with sympy instead (every instruction is a known
factor shape, so the values come out exactly, with no floating point); the
numeric routes are recorded here as ruled out:

- A pure high-precision `mp.polyroots` (Aberth) swap is correct but ~3000x
  slower per program on the common path, and still does not converge on the
  pathological root spreads.
- A custom high-precision companion-matrix QR (`mp.eig`) produces garbage
  even on `'Hello, World!'` (degree 50) and hangs on modest degrees, because
  the companion matrix is badly scaled.
- A change-of-variable scaling still solves the wrong (imprecise) polynomial.
- A residual-based correctness gate cannot work: the ill-conditioning (~1e16)
  makes even wildly wrong roots look right at any precision.

The factor-based recovery also defines the boolean generator's practical
bound: `n == 4` (degree 184, coefficients ~10**729) factors in ~10s, while
`n == 5` (degree 376, ~10**1746) does not factor in practical time, so the
boolean generator is capped at `n <= 4`.

## Text generators: exhausted
Every language whose interpreter can emit arbitrary bytes already has a text
generator.  The remaining interpreter-only languages cannot, so no text
generator is possible for them: ArrowQueue has no output at all, Back prints
the tape as a number list, BitDeque and Minsky Swap print their registers as
numbers, Movesum prints `n ` (numbers with a trailing space), RAM0 prints a
state dump, Keys prints only "Accept."/"Reject.", and Lightlang prints only
the single bit as a number.  None can spell arbitrary text.

## Assessed boolean candidates that fell through
- **Temporary**: the auto-drain is the only output, and it prints `front - 1`
  for the *oldest* stack element when `sum(rest) / 2 > front`.  An
  input-dependent `'0'`/`'1'` (48/49) output therefore needs the input to
  select a 49/50 constant, but the only value-to-length conversion — the
  front element popping — requires `front < input / 2 < 24`, so the front is
  at most 24 and prints garbage (`chr(23)`/`"23"`), while the raw input at
  the front prints `input - 1` (47/48).  Neither is a `'0'`/`'1'`.  Exhaustive
  search to length 5 finds no identity or NOT program, and `\` (while
  nonempty) never terminates except via the fixed 15-command stack reset, so
  there is no input-dependent branch either.  A boolean generator is not
  feasible for the standard harness.
- **Movesum**: only `move` (copy) and `sum` (add), with no conditional — the
  loop repeats commands until the array stops changing.  The numeric output
  (always a trailing space) and the addition-only arithmetic cannot express a
  general boolean function.
- **WII2D**: the accumulator never affects control flow (`^v<>` set the
  direction, `@` jumps unconditionally to the closest `@`), so there is no
  value-testable branch to route a decision tree on.
- **EXCON / Huf**: straight-line with no input and no branch, so neither an
  input-reading nor a parameterized generator can route on a bit.
- **Lightlang**: `?` sets the bit to ``not line`` — every non-empty line,
  including `'0'` and `'1'`, collapses to bit 0, so it cannot read bit values
  at all; its only output is the bit as a number.
- **DSDLAI**: a Dig variant whose dig commands carry a random 20-90% death
  chance (printing "You died." and halting), so a generated program's output
  is non-deterministic and cannot round-trip text or a truth table.
