
# Generator and transpiler walls

The full wall arguments behind the blocker tables in
[`docs/limitations.md`](limitations.md) — the negative result and the
structural reason it cannot be lifted.  Completed constructions (the
working generators, and how they work) live in the commit history, not
here.

## 6-5 (constant program size is impossible)

A generator that must work for any table has to embed the table, and the
single-integer representation 6-5 requires (the pointer cannot net-advance,
so there is no computed array indexing) costs O(`2**(2**n)`) characters for
dense tables.  A ~2 MB setup guard rejects the `n > 5` and large-`T` region
(AND-n is the pathological case), and runtime is O(x*T) — minutes at the
size guard.  The shipped decision tree stays primary (total through
`n <= 5`); the arithmetic kernel is the fallback for small-`T` tables past
that.

## ZTOALC L (dense non-symmetric n > 3 wall)

All Collatz trajectories converge to the `16, 8, 4, 2, 1` tail, so a dense
full tree like XOR4 has every leaf's tail sweep through another leaf.  For
**popcount-symmetric** tables the generator falls back to a branch-free
*linear* program, which is `2**L` lines (XOR4 is 524,288; gated at `2**22`).
Only dense, non-symmetric tables past `n == 3` still raise `ValueError`;
those need a full `2**n` result table, which would be `2**(2**n)` lines.

## 3x (constant-bit guard skip is unsafe)

A guard that separates differing rows from default rows sharing the same bit
prefix cannot have a "redundant" bit test dropped, because the default rows
share the prefix too — dropping the test would misclassify them.  The sibling
idea (pre-negating stored input bits to halve `not_bit`) remains open but is
marginal.

## Minifuck (0-preserving functions, n <= 3)

The two-input limitation is structural: the decode suffix flips the pool LSB
only when the pointer sits at cell 7, and `[`'s skip always maps bit 0 to
the higher pointer position, fixing the pointer orientation.  XNOR, NAND,
NOR, NOT-b0, NOT-b1, and const-1 were not reachable in the original analysis
(no complemented read-prefix exists to length 11, full-program search to
length 14 finds none, and a re-verification search to length 34 still finds
none).  The n == 4 walker stage additionally cannot reach the 8 distinct
pointer positions a third bit needs.  The single-input case is *not*
0-preserving-bound (a re-verification found NOT and const-1 at lengths
17-18), so the generator covers the four one-input functions plus the
0-preserving two-input tables, and nothing past `n == 3`.

## 123 (four one-input functions)

A decision tree needs the `3` jump, which on a TRUE/FALSE bit jumps to the
*nearest* preceding/following `3` (not bracket-matched), so the only
constructible pattern is "repeat the region before the `3` while TRUE" — no
`3`-based branch exists (a random search finds no NOT even at n == 1), and
the single data byte makes multi-bit state impossible (every read overwrites
it).  The four one-input programs were too trivial to keep, so the boolean
generator was removed.

## RAM0, Bitdeque, Minsky Swap (parameterized template blocked)

These three have value-testable branches and clean setters, but their jumps
are *absolute token indices*: RAM0's digit-`GOTO`, Bitdeque's `GOTO N`, and
Minsky Swap's `~` targets are all fixed positions in the token/command
stream.  The parameterized template's bit setter has variable length (e.g.
RAM0's `Z` for a zero bit vs `Z A` for a one bit; Bitdeque's `INVERT` vs
nothing), so substitution changes the token count and every jump target
shifts — a fixed template cannot be correct for all instantiations.  Only
Back avoids token-index jumps (its `+`-advance condition is positional).

## Eval (nested parameterized trees)

Building a decision tree requires nesting: each subtree must be a string
evaluated with `!`.  This is a **spec** limitation (the interpreter matches
the wiki exactly): the wiki defines stringmode with no way to escape a
backtick or include a literal one, so a pushed string can never contain a
backtick and a nested `!`-evaluated subtree cannot survive more than one
wrap.  The wiki's examples only ever use single-level `!`.

## SLOW ACV MAMMALIAN (general n-bit open)

The n-bit case is blocked by three mutually conflicting constraints:

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

Re-verified against the interpreter: a search over the branch-free tails
after the `b1`-normalize prefix reaches only the 0-preserving two-input
tables, matching the structural argument.  (Unlike Minifuck, this wall
holds.)

## Dotlang (not viable)

The `W~` warp reads a line and teleports the dot to the *first* `W<bit>`s`
marker in the grid.  A single-bit program works, but every deeper level of a
decision tree re-enters those same first-match markers, so the branch
history is lost: the second `W~` lands back on the first markers and loops.
The type conditionals (`!?:`) cannot help — input digits are converted to
`int` 0/1, so both bits share the same type — and there is no value
comparison or arithmetic.  Only a fragile direction-routing trick could
express more, and it caps at three inputs before the eight (marker, heading)
states run out.

## Polynomial (numeric root-finding ruled out; caps at n <= 4)

The generator emits exact integer polynomials whose coefficients far exceed
float64's exact-integer range (2**53) once a few instructions accumulate —
`'Hello, World!'` has coefficients up to 10**95 — so every floating-point
solver (high-precision `mp.polyroots`, companion-matrix QR, change-of-scale)
silently solves the wrong polynomial, and a residual-based gate cannot work
(the ill-conditioning ~1e16 makes wildly wrong roots look right).  The
interpreter factors the monic integer polynomial over Z with sympy instead.
That exact factorization defines the boolean generator's practical bound:
`n == 4` (degree 184) factors in ~10s, while `n == 5` (degree 376) does not.

## ROTfuck (rotation defeats a decision tree)

The rotation defeats a brainfuck decision tree outright: a `[ body ]` whose
body is a rotation-encoded loop cannot work, because when the `]` fires its
`[` has rotated away (the skip-path seek needs `q ≡ p+1` while
re-convergence needs `q ≡ p`).  The shipped boolean generator sidesteps the
wall by never looping (a phantom-`]` block whose straight-line body is
position-encoded), which keeps the generator total but makes the programs
long (O(`n·2**n`) blocks, ~1.4s/execution at `n == 4`).

## Home Row (j-guarded-move boolean generator, n <= 2)

`l` loops pair strictly by order, so loops cannot nest and a bf-style
decision tree is inexpressible.  The shipped generator routes with `j`
(guarded moves) instead of loops, which works through `n == 2`.  `n >= 3`
raises: an exhaustive search over `j`-guarded sequences shows no routing
separates `2**n` combinations onto distinct cells of the fixed 5x5 torus
past `n == 2` (the search caps at 6 of 8 combinations).

## Assessed boolean candidates that fell through

- **%^2^-1**: its only control flow is `t` — rewind to the program start
  when the accumulator is nonzero — with the accumulator preserved across
  the rewind.  A program is therefore a whole-program `while` loop, and each
  `n` in the body consumes one input line, so a `t` loop iterates over the
  input bits.  It cannot count them: there is no increment-by-1 for an
  arbitrary value, and a counter in the rewind path grows without bound (the
  `acc > 3003` reset only fires on huge magnitudes), so the loop stops only
  when a body pass ends with `acc == 0` — a uniform predicate that cannot
  tell pass 1 from pass n.  The all-ones row of any truth table therefore
  either stops the loop early or rewinds past the input.  Exhaustive search:
  of the four one-input functions only identity and the two constants are
  expressible; NOT and every two-input table fail even at length 8.
- **The Temporary Stack**: the auto-drain is the only output, and it prints
  `front - 1` for the *oldest* stack element when `sum(rest) / 2 > front`.
  An input-dependent `'0'`/`'1'` (48/49) output therefore needs the input to
  select a 49/50 constant, but the only value-to-length conversion — the
  front element popping — requires `front < input / 2 < 24`, so the front is
  at most 24 and prints garbage, while the raw input at the front prints
  `input - 1` (47/48).  Neither is a `'0'`/`'1'`.  Exhaustive search to
  length 5 finds no identity or NOT program, and `\` (while nonempty) never
  terminates except via the fixed 15-command stack reset, so there is no
  input-dependent branch either.
- **WII2D**: the accumulator never affects control flow (`^v<>` set the
  direction, `@` jumps unconditionally to the closest `@`), so there is no
  value-testable branch to route a decision tree on.
- **Movesum**: only `move` (copy) and `sum` (add), with no conditional — the
  loop repeats commands until the array stops changing.  The numeric output
  (always a trailing space) and the addition-only arithmetic cannot express a
  general boolean function.
- **Trash**: its only output is a prime-advanced number — a non-prime start
  prints ``0``, a prime start prints the next prime (3, 5, 7, ...), and no
  leading ``t`` prints nothing — so it can never print a boolean ``"1"`` and
  cannot return a truth-table result even parameterized.
- **Lightlang**: `?` reads a bit (an empty line gives 1, any non-empty line
  gives 0), so a bit is readable — but `&` (skip the next instruction when
  the bit is 1) skips exactly one character, so a decision-tree node cannot
  route to a multi-character subtree.  Only a one-sided AND-like cascade is
  expressible (each level's zero-branch is the fixed ``!&#`` "print 0,
  halt"), not a general truth table; XOR and OR were both searched and
  rejected.  Its ``@`` command is also non-deterministic (a random bit).

## Termination-based convention (partial, not a boolean generator)

A "halt vs. loop forever" convention — the program halts iff the embedded
input bits satisfy the function — was explored for the three languages with
a built-in infinite-loop branch.  It expresses the one-input functions but
no multi-input tree:

- **Brainpocalypse**: `-`-on-zero rewinds and loops, so `-` loops for bit 0
  and `+-` halts for bit 1; but the rewind restarts the prefix and re-running
  `+` increments already-set cells, so multi-input bakes corrupt.
- **Stun Step**: the machine halts iff the current cell is 0 at a pass
  boundary, so `>` (moves only when the cell is nonzero) gives
  halt-for-0/loop-for-1; but the loop-back re-runs the code with a shifted
  pointer, corrupting multi-bit bakes.
- **Number Seventy-Four**: the pass-restart checks the accumulated output
  string (not corrupted by restart), so `0H` halts and `1H` loops; but the
  halt depends only on the front-most output character, so multi-bit trees
  still fail.

No existing boolean generator uses this convention; it would require a new
harness contract (termination as the answer) and still does not unlock a
multi-input generator in any of the three.

## Multiply capability (Jaune realizes it)

A *multiply* program reads two decimal operands (most-significant first, one
digit per input line) and prints their product as a decimal number (no
leading zeros).  It tests a distinct capability from the boolean criterion
(digit input + arithmetic + decimal output, vs. bit input + branching) and
from the text criterion (arbitrary byte output).

Unlike the boolean criterion, this is **not a generator family**: a boolean
truth table's length ``2**n`` *is* the input count (so the boolean
generators infer ``n`` from the table and take only the table), but
multiplication is a single function ``a * b`` whose operand lengths are a
property of the input, not of the function.  So there is no
``multiply(language, n)`` class to build across the registry — a language
either reads until a delimiter (``*`` between the operands, ``#`` at the
end) and needs one sentinel construction for any digit count, or it cannot.
Jaune is the first language found with the capability; the rest of
the registry's languages are not known to have it (their generators are
text-only or absent), so this records the criterion and the one realized
construction rather than a family of generators.

A brainfuck prototype was built and verified: read+normalize each digit
(ASCII minus 48), multiply via a nested loop, and print the product with the
itchyny 8-bit decimal printer.  **n = 1 works exhaustively (all 100
single-digit pairs 0-9 × 0-9).**

For n > 1 the right construction is grade-school long multiplication:
allocate 2n cells for the 2n operand digits (each 0-9, fitting a byte) and
carry over between result cells, so no single cell ever holds the full
product.  This avoids the single-cell overflow that blocks accumulating the
product in one cell.  But the per-digit *carry* needs a "while >= 10"
operation, and with the interpreter's documented 8-bit wrapping cells (mod
256) the standard divmod/carry algorithms assume non-wrapping cells and do
not transfer directly — the itchyny decimal printer embeds a working divmod,
but it is tied to the printer's cell layout, not reusable as a standalone
carry.  So n = 1 is proven; n > 1 needs a wrapping-safe carry, which is a
genuine brainfuck-algorithms construction rather than a quick extension.

**Jaune realizes the capability:** its cells do not wrap (the author's
reference implementation stores each cell as a JavaScript number with plain
``+=``/``-=``, no modulo or bitmask, and this interpreter uses Python
``int``) and ``^`` prints the current cell as a decimal number, so each
operand fits in a single cell and the product accumulates without a
digit-per-cell carry.  The
program (:func:`esolangs.tools.boolean.jaune_multiply`) runs each read on a
dedicated always-one cell (the ``?``/``!`` jumps are conditional, so a cell
permanently set to 1 gives the loop-back jump an unconditional trigger),
folds each digit with ``v+`` plus a run of nine ``&`` after a ``#``
(multiply by 10), detects a sentinel by adding its offset from a digit
(``*`` is 42, ``6+`` zeroes it; ``#`` is 35, ``13+`` zeroes it) and jumping
on zero, then loops the repeated addition of the first operand over the
second.  Verified exhaustively for single-digit operands (all 100 pairs)
and spot-checked through ten-digit operands.
