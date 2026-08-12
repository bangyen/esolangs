# Limitations and ruled-out ideas

What the boolean generators cannot do, and the language assessments that
concluded a generator is not viable (or only partially viable).  Completed
work lives in the commit history; this file records the walls, the negative
results, and the reasoning behind them.  Genuine future work is in
`docs/ROADMAP.md`.

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

## MAMMALIAN (viable in principle, but the dispatch layout is hard)
MAMMALIAN has the primitives a decision tree needs, confirmed through the
interpreter: `ACCEPT` reads a byte, `PRONOUNCE` prints the accumulator, and
`LEAPFROG` is a *data-dependent* jump (`ind = acc - curr[0] - 1` when the
current array's last element is nonzero).  A deeper assessment verified the
concrete mechanics:

- Normalizing an input to a clean 0/1 bit works: `48 SEEDs` then
  `DIGEST ACCEPT DIGEST` makes `acc = ord(bit) ^ 48` in `{0, 1}` (48 is
  special because `48^48 = 0` and `48^49 = 1`).
- `LEAPFROG` then branches: bit 0 falls through linearly, bit 1 takes the
  computed jump.  Constants are created with `SEEDs + DIGEST` (~1 token per
  unit), and halting works by making the jump target negative.
- A clean 1-bit *identity* program is ~55 tokens (normalization + one
  print + halt).

The assembly barrier is the jump target.  From the natural state after
normalization (`acc = 48`, `lst[0][0] = 1` for a one bit) the bit-1 target
is `48 - 1 - 1 = 46`, which is *backward* into the normalization stream;
a forward dispatch needs `lst[0][0] = acc - T < 0`, which the cell ops
cannot easily produce.  So every subtree must be interleaved into the
shared normalization code with back-patched absolute targets, the halt
mechanism (negative target) conflicts with forward dispatch, the 23 arrays
are shared and `SEED` mutates every array at once, and the accumulator does
not stay clean across reads.  Each bit costs ~50 tokens to normalize and
each leaf ~50 to emit, so the size is brainif-like.  A verified generator
is a multi-session assembly project, harder than ZTOALC's (which had the
clean `p * 2**k` descent); none has been built.

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
