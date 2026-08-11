# Roadmap

Planned work, in priority order. Completed ideas live in the commit history;
this file only tracks what is still on the table.

## Planned

### Shared decision tree for the 3x boolean generator (resolved)
The 3x generator (`src/esolangs/tools/booleans/other.py`) now builds one
decision tree: rows that share a bit prefix share the prefix's guards,
amortizing the ~19-char scaffolding (`read + ( + trash + sentinel + ) +
trash`) instead of emitting an independent nested chain per row that
differs from the majority default.  Verified against the Ruby reference
for every table at n <= 3 and sampled at n = 4, 5.  Measured size
(old -> shared tree):

- XOR-n (all combos differ, little prefix structure): 81% (n=4), 70% (n=5), 61% (n=6);
- top-half table (rows cluster by MSB): 62% (n=4), 51% (n=5), 44% (n=6);
- AND-n (single differing row): unchanged (no prefix to share).

So the win tracks the table's prefix structure and roughly halves
structured tables at n >= 5, and is never worse.  A constant-bit guard
skip was considered but is not safe: a guard also separates differing
rows from default rows that share the prefix, so a "redundant" bit test
cannot be dropped without checking the default rows too.  The sibling
idea (pre-negating stored input bits to halve `not_bit`) remains open but
is marginal.

### Constant-loop boolean generator for arbitrary n (resolved: 6-5)
The boolean generators cover every table up to a small input count: 6-5 and
CircleFuck build decision trees capped at about 5 inputs (35 branch labels
for 6-5, n <= 5), Taglate is closed-form for n == 2, the brainfuck
generator handles any n but is branch-free and grows with the minterm count,
and Clockwise builds an uncapped decision-tree ring.  The open goal was a
generator whose program size and loop count are constant in n (encode the
inputs as one number and decode the table entry arithmetically).

**6-5 closes the loop-count half.**  `six_five_arithmetic`
(`src/esolangs/tools/booleans/tape.py`) packs the inputs into `x` and the
table into `T = sum table[i] * 2**i`, then computes `f(x) = (T >> x) & 1`
by halving `T` x times and reading the final parity.  The kernel uses 8
loop constructs and 27 markers, both constant in n, so the 35-label cap no
longer bounds the input count (verified exhaustively for every table at
n <= 3 and sampled through n = 16).  `x` is built by a read loop that folds
each normalized 8/9 bit with `x = 2x + (b - 8)`; each halving is a parity
pass (a copy loop toggling a flag once per unit) that selects a
`while r2 != 0` or `while r2 != 1` count-down loop writing the quotient
back into `T`.

Two optimizations keep programs small: the table constant is built with
`+6` runs (~`T/6` chars, 12x under the old `62` pairs), and when the
table's complement `T' = 2**(2**n) - 1 - T` is cheaper the complement is
evaluated with the output inverted, so mostly-ones tables are generated
instead of rejected.

**Constant program size stays impossible.**  A program that must work for
any table has to embed the table, and the single-integer representation
6-5 requires (the pointer cannot net-advance, so there is no computed array
indexing) costs O(`2**(2**n)`) characters for dense tables.  A ~2 MB setup
guard therefore rejects the `n > 5` and large-T region (AND-n is the
pathological case), and runtime is O(x*T) — microseconds for tiny-T tables
up to ~2 s at n = 16, but minutes at the size guard.

The decision tree stays, and the two are not in competition: for n <= 5 the
tree generates every table with no rejection, ~µs runtime, and a flat
44-914 chars, while the kernel is the fallback for n > 5 (small-T tables
only).  Measured at n = 4 the tree runs ~46,000x faster and generates
programs 13x smaller than the kernel for the same table, so the kernel's
role is strictly to cover the region the tree's labels cannot.

### Minifuck boolean generator (assessed: 0-preserving functions only, n <= 3)
`[` followed by `<` is a conditional pointer move: `[` moves right, flips
that bit, and skips the following instruction *and* flips the next bit only
when the flipped bit is zero, so after `[<` one input state executes `<`
while the other skips it.  The tested bit's value thus survives in the
*pointer displacement* while the pool can be re-zeroed for another read.

Every working program fits one read-prefix plus a tiny decode suffix.
The shared n == 2 prefix `<[<.[<[<[<[<[<[<[<` reads b1 (`<[<.`), then a
`[<` run walks the pointer right while clearing the pool, and the next
`.` reads b2; the pointer ends at 8 (b1 == 0) or 7 (b1 == 1).  Exhaustive
suffix search over `{<,.[}` reaches *exactly* the 0-preserving two-input
tables (f(0, 0) == 0): AND, OR, XOR, both echoes, and const-0 — 8 of 16.
A three-input function reuses the same prefix, adds a second walker, and
uses the same `<.` suffix (`b3 XOR (b1 AND b2)`, verified 49 chars).

The limitation is structural: the decode suffix flips the pool LSB only
when the pointer sits at cell 7 (the `.` after one `<` from cell 6 flips
the LSB, from cell 7 it flips a scratch cell instead), and `[`'s skip
always maps bit 0 to the higher pointer position.  So the pointer
orientation is fixed and the genuinely two-input functions are forced to
f(0, 0) == 0: XNOR, NAND, NOR, and NOT-b2 are unreachable — no
complemented read-prefix exists (searched to length 11) and full-program
search to length 14 finds none.  (NOT-b1 and const-1 are reachable but
degenerate, reading only the first input or none.)  The n == 4 walker
stage additionally cannot reach the 8 distinct pointer positions a third
bit needs: re-zeroing the pool requires the pointer to return to cell <= 1,
which collapses the 7..11 displacement.  A generator is therefore limited
to 0-preserving tables with n <= 3 at most, and not to arbitrary boolean
functions.

### ZTOALC boolean generator (resolved: generator built, n <= 3 exhaustive)
ZTOALC's control flow is the Collatz trajectory of line 1, so the generator
(`ztoalc_boolean`, `src/esolangs/tools/booleans/other.py`) lays out a
decision tree on `p * 2**k` descents: branching at an even root lets a zero
bit continue the descent (the Collatz step halves it) while a one bit jumps
to `root + 1`, whose Collatz step lands on `4 * q` — so every branch gets a
predictable, non-revisiting path.  Reads and normalizations ride the initial
`b1 * 4**n` descent, leaves print on disjoint trajectory prefixes, and a
small `b1` is searched until a fast simulator confirms every input prints
exactly its table entry once with no command line revisited.

Verified exhaustively for every table at `n <= 3` and for structured tables
at `n == 4` (top-half, AND4); all tests run the real interpreter.  The
built-in text generator's trajectory machinery was not needed for the
routing — the `p * 2**k` descent replaces it.  Program size is O(b1) lines:
the `b1` search starts at the minimum `2**(n+1)` (the all-zeros leaf needs
`b1 / 2**n >= 2`), so the n=4 structured tables use `b1 = 36` and 9216
lines rather than the 16384 the earlier search start found.

The limitation: all trajectories converge to the `16, 8, 4, 2, 1` tail, so
a dense full tree like XOR4 has every leaf's tail sweep through another
leaf, and no `b1` works.  For **popcount-symmetric** tables (XOR = parity,
AND, majority) the generator now falls back to a branch-free *linear*
program: sum the normalized input bits with `s += x_i`, look the result up
in a small `n + 1`-entry table, and print.  Every line sits on the pure
power-of-two descent from `2**L`, so the trajectory never revisits a line
and the program is guaranteed collision-free — but it is `2**L` lines
(XOR4 is 524,288; gated at `2**22`).  Only dense, non-symmetric tables
past `n == 3` still raise `ValueError`; those need a full `2**n` result
table, which would be `2**(2**n)` lines and cannot be materialized.

The interpreter was also brought in line with the wiki spec: `lhs = rhs` /
`+=` / `-=` now write an `array[index]` element instead of a variable named
literally `"arr[i]"`.  With the fix, runtime-indexed tables work, which is
what makes the linear fallback (and mod-2 as a small parity-table
primitive) possible.

### MAMMALIAN boolean generator (assessed: viable in principle, hard)
MAMMALIAN has the three primitives a decision tree needs, and they are
confirmed working through the interpreter: `ACCEPT` reads a byte into array
0, `PRONOUNCE` prints the accumulator, and `LEAPFROG` is a *data-dependent*
jump (`ind = acc - curr[0] - 1` when the current array's last element is
nonzero, then the interpreter's trailing `ind += 1` makes the effective
target `acc - curr[0]`).  A 2-way branch is demonstrable: `ACCEPT DIGEST`
folds the input byte into the accumulator (48 for '0', 49 for '1'), and
`LEAPFROG` then dispatches to instructions 48/49 (the two values differ by
one), verified to route '0' and '1' to different code.

The difficulty is the assembly, not the primitives.  The effective jump
target is an *absolute instruction index*, so every tree node must be
back-patched into the instruction stream; the accumulator does not stay
clean across reads (each `ACCEPT` XORs with the current `acc` and each
`DIGEST` XORs the running array sum, so node targets depend on prior
state); the 23 arrays are shared and `SEED`/`CONFLAGRATE` mutate every
array at once; and there is no halt command, so leaves must terminate by
falling off the program or jumping to a negative target.  Building a
verified generator here is a real project, not a quick win.

### Dotlang boolean generator (assessed: not viable)
Dotlang's only input-dependent branch is the `W~` warp, which reads a line
and teleports the dot to the *first* `W<bit>`s` marker in the grid (the
interpreter's `find` scans rows top-to-bottom).  A single-bit program works
(a `W~` sends the dot to the `W0`s`/`W1`s` marker that prints the result),
but every deeper level of a decision tree re-enters those same first-match
markers, so the branch history is lost: the second `W~` lands back on the
first `W0`s`/`W1`s` and loops.  The type conditionals (`!?:`) cannot help —
input digits are converted to `int` 0/1 by `dot.new`, so both bits share the
same type — and there is no value comparison or arithmetic.  Only a fragile
direction-routing trick (each bit selects the dot's heading through the
shared markers) could express more, and it caps at three inputs before the
eight (marker, heading) states run out, below the `n <= 4` verification bar.

### LaserFuck boolean generator (in progress: general BF layout compiler)
LaserFuck is brainfuck on a 2D grid: a laser (with a random initial heading)
travels the grid, `>`, `<`, `+`, `-`, `,` work on the tape, ``(``/``)`` and
``_``/``|`` bounce the laser when the tape cell is nonzero (or always), and
the whole tape is printed at the end.  A faithful emulator exists
(`scripts/laserfuck_emu.py` in the boolean-generator scratch work).

The existing text generator's loop layout (`src/esolangs/tools/generators/
other.py`) is a fragile special case: it lays out exactly one `+[>+...+<-]`
loop on a two-track serpentine and falls back to a *linear* layout (loops
ignored) for short bodies like `[-]`, multiple loops, or nested loops.  The
branch-free `_bf_minterm` evaluator has many nested loops, so a boolean
generator needs a **general BF-to-LaserFuck layout compiler**:

- Linear commands lay out fine on a single right-going track (verified in
  the emulator, robust to all four random headings).
- The output mode (first grid char `\xff`) prints every touched nonnegative
  cell as a byte; inputs normalized to 0/1 and scratch cells fall out of the
  verify harness's `01` filter, leaving only the 48/49 result cell — so the
  result survives the whole-tape dump.
- Loops need a physical ring: a ``)`` cell bounces the laser back through a
  return lane while the tape cell is nonzero.  The `[-]`, copy, NOT, and sum
  loops of `_bf_minterm` are do-while safe (their bodies are identity modulo
  256 when rerun on a zero cell), but the AND `t1[ t2[ newp+ t2- ] t1- ]` is
  not, so the loop entry must check the tape before entering the body.
- The reference's random initial heading and `*` spawns make verification
  require every generated grid to behave identically under all four headings.

A working generator is not yet achieved; the loop-ring geometry (entry
check, return lane, exit routing) is still under construction.

### Dimensional v3 migration (in progress: Python interpreter first)
The wiki now documents Dimensional **v3.0** (an n-slot/n-pointer model with
`$AXIS`, `d`, `x`), while the reference in `extra/c++/dimensional.cpp`
implements **v1.0** (a single pointer over a product-of-primes tape).  The
two are incompatible dialects, and the v1.0 reference's 32-bit `int` cell
addresses overflow past ~30 cells — which is why the boolean generator
(`src/esolangs/tools/booleans/tape.py`) used a fixed `2n + 6`-cell layout
and refused `n > 12`.

The plan, decided: **replace v1.0 with v3.0**, migrating the text and boolean
generators (whose outputs — `=hex.` and `>0`/`<0`/`,+ -[].` — are valid in
both dialects) to be verified against the new implementation.

- **Doing now: a first-class Python v3.0 interpreter.**  It goes in
  `src/esolangs/interpreters/tape_based/dimensional.py`, joins the registry,
  and verifies the generators by real execution in unit tests (the standard
  lane for the BF-family tape languages).  Python `int`s make cell addresses
  unbounded, retiring the `n > 12` cap.  Defaults and ambiguities the v3.0
  wiki leaves open (default pointer axis, the descent model, `d`/`x` reading
  from input) are resolved pragmatically and documented in the interpreter.
  The v1.0 C++ reference leaves the verification pipeline (the generator
  round-trips it used to gate now run through the Python interpreter).
- **Deferred: a v3.0 C++ reference.**  With the Python interpreter as the
  only implementation, generator verification is circular (same author,
  same codebase, shared reading of the under-specified spec).  A fresh
  `extra/c++/dimensional.cpp` implementing v3.0 would restore the independent
  differential cross-check and keep Dimensional in the C++ reference family.
  It must handle the addressing itself (a `long long` key covers `n <= 28`; a
  small bignum for unbounded) — the very overflow that motivates the change.

### Polynomial float64 root precision
The Polynomial generators emit exact integer polynomials, but the
interpreter finds roots with `numpy.roots`, whose float64 companion-matrix
computation loses the small imaginary parts when the roots span a wide
magnitude range.  That happens when consecutive characters differ by large
codepoint amounts (e.g. ASCII immediately followed by a CJK character), so
such text silently corrupts (documented under README "Known Issues").  A
heuristic guard is *not* viable: OK and FAIL cases overlap in both coefficient
magnitude and max delta, and even the same delta passes or fails depending on
the surrounding pattern.

Higher-precision replacements have been tried and ruled out empirically:

- `mpmath.polyroots` (Durand-Kerner): fails to converge even on
  `'Hello, World!'` — a program `numpy.roots` handles correctly in ~0.5ms —
  at any tested precision (30-80 digits) or `maxsteps`.
- `sympy.nroots` (also Durand-Kerner based): recovers short inputs correctly,
  but fails to converge on a random 20-character ASCII text (degree ~80), and
  is ~10,000x slower than numpy on `'Hello, World!'`.
- Companion matrix + `mpmath.eig` (Hessenberg + QR): recovers `Hi`, but still
  corrupts the wide-spread roots (imaginary parts 71/115 instead of 5/17/121)
  and precision increases do not help.

The root geometry — roots spanning several orders of magnitude — defeats
every Durand-Kerner/QR variant tried.  A working fix would need a custom
arbitrary-precision companion-matrix eigenvalue solver (high-precision QR) or
a fundamentally different algorithm, not a drop-in library swap.

The same fix would lift the boolean generator's `n > 2` cap
(`src/esolangs/tools/booleans/register.py`): a depth-`n` decision tree emits
`2*2**n + ...` instructions, each consuming a fresh prime, so the expanded
coefficients grow to ~10**90 at n == 3 (1196 bits) and ~10**4900 at n == 6
(16309 bits) — far beyond float64's range, which is why the boolean generator
currently rejects `n > 2`.  Arbitrary-precision roots handle both the
precision loss and the range overflow, so this is one interpreter change with
two payoffs.

Dependency note: `numpy` is the *only* third-party import in the whole
package, and it is used solely by the polynomial interpreter for root
finding.  Any replacement should remove it in favour of the new solver, and
as a hard dependency, not an optional fallback: an optional numpy fallback
would keep the buggy float64 path alive for anyone without the new solver and
split the interpreter's behavior across environments (plus leave a branch
untested against the 100% coverage rule).
