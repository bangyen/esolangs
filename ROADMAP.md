# Roadmap

Planned work, in priority order. Completed ideas live in the commit history;
this file only tracks what is still on the table.

## Planned

### Shared decision tree for the 3x boolean generator
The 3x generator (`src/esolangs/tools/booleans/other.py`) emits one
independent nested guard chain per table row that differs from the majority
default, and each chain's scaffolding (`read + ( + trash + sentinel + ) +
trash`, ~19 chars) is duplicated across rows.  Grouping rows by common bit
prefixes into a shared tree would amortize that scaffolding, roughly halving
program size for `n >= 4`; a sibling idea is pre-negating the stored input
bits to halve the `not_bit` cost on tables where one bit value dominates.
Both are structural rewrites of the generator, still verified against the
Ruby reference.

### Boolean-table transpiler bridge
A dynamic transpiler across the boolean-capable languages — Sophie, Modulous,
BrainIf, Nevermind, CircleFuck, Clockwise, Dimensional, and Basicfuck. These
are genuinely different machines, but each has a verified generator that
builds a program for any truth table, so a transpiler can lift a program from
one to another:

1. run the source program on all `2**n` inputs to extract its truth table;
2. regenerate in the target with its boolean generator.

It is nontrivial (a real transformation between machines, with the truth
table as the intermediate), bounded (the boolean-program class the
generators already produce), and verified exactly like every other
transpiler — the source and target must agree on every input. It needs a
design decision first: how to detect or take `n` (the input count) and how
to reject programs outside the class loudly.

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

### Minifuck boolean generator (assessed: viable for n == 2, n >= 3 open)
`[` followed by `<` is a conditional pointer move: `[` moves right, flips
that bit, and skips the following instruction *and* flips the next bit only
when the flipped bit is zero, so after `[<` one input state executes `<`
while the other skips it.  The tested bit's value thus survives in the
*pointer displacement* while the pool can be re-zeroed for another read —
a genuine branch primitive.

A two-input XOR is verified against the interpreter
(`<[<.[<[<[<[<[<[<[<.<.`), along with AND, OR, and several other
two-input tables: `<[<.` reads the first byte, a `[<` run walks the pointer
right while clearing the 8-cell pool, the next `.` reads the second byte,
and the pointer ends at 8 or 7 depending on the first bit — so the first
bit is carried in the pointer position while the second sits in the pool.
The walker doubles the reachable positions per read.

Open question: whether the pointer displacement composes to n == 3 (a
second walker would need 4 distinct end positions to carry two prior bits)
and beyond, up to the n <= 4 verification bar.

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
