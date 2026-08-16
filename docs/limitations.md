# Limitations and ruled-out ideas

What the generators cannot do, and the assessments that concluded an
approach is not viable (or only partially viable).  Completed work lives in
the commit history; this file records the walls, the negative results, and
the reasoning behind them.  Genuine future work is in `docs/roadmap.md`, and
the criteria for assessing a candidate language are in `CONTRIBUTING.md`.

## Interpreter conventions

The interpreters share a few behavioral conventions, so `esolangs.run` is
predictable across languages:

- **Empty programs are a no-op by default.**  An empty (or blank-only)
  program produces no output, unless the language structurally requires
  content to start — an initial direction (2dFish), a Collatz seed line
  (ZTOALC L), or a program grid (Circlefuck, BF-PDA, Suffolk, Dig, Back,
  Clockwise) — in which case it is rejected with a clear `ValueError`
  (usually ``"... cannot be empty"``, or 2dFish's
  ``"program does not set an initial direction"``).
- **Exhausted input raises :class:`EOFError` by default.**  A program that
  reads past the end of `stdin` is almost always a bug, and the loud error
  surfaces it (and lets `,[.,]`-style cat loops terminate).  Languages whose
  spec defines EOF behavior follow the spec instead and document it: S*bleq
  and Movesum read `0` at EOF (both per the wiki), and every other
  interpreter raises `EOFError`.  Malformed programs raise `ValueError` and
  runtime halts raise :class:`HaltError`, never a raw Python exception.
- **Byte input is line-delimited.**  ``io.input_char`` reads a whole input
  line and returns its first character (the rest of the line is discarded),
  so a byte-oriented program needs one line per byte: `,.,.` on ``"A\nB"``
  echoes ``"AB"``, while ``"AB"`` on one line supplies only ``A`` and the
  second `,` raises `EOFError`.
- **Execution is unbounded through the public API.**  `esolangs.run` has no
  step limit: interpreters run until the program halts naturally or loops
  forever.  Suffolk is the sole interpreter that ships with a fixed
  instruction limit, and callers cannot set one through the public API.

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
Circlefuck's decision tree is total (verified exhaustively to n = 3,
sampled to n = 16), so the label-cap motivation is gone.

## ZTOALC L (built; dense non-symmetric n > 3 wall)
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

The *two-input* limitation is structural: the decode suffix flips the pool
LSB only when the pointer sits at cell 7, and `[`'s skip always maps bit 0
to the higher pointer position.  So the pointer orientation is fixed and the
genuinely two-input functions are forced to f(0, 0) == 0: XNOR, NAND, NOR,
NOT-b0, NOT-b1, and const-1 were not reachable in the original analysis
(no complemented read-prefix exists to length 11, full-program search to
length 14 finds none, and a re-verification search to length 34 still finds
none).  The n == 4 walker stage additionally cannot reach the 8 distinct
pointer positions a third bit needs.

The single-input case, however, is *not* 0-preserving-bound: a re-verification
found NOT (`<<[<[<[.[[[<[[..[`) and const-1 (`[<[<[<[.[<[[.[.[.`) at lengths
17-18, past the original search's length-14 cap, so all four one-input
functions (const-0, identity, NOT, const-1) are reachable.  A generator is
therefore limited to the 0-preserving two-input tables plus all four
one-input tables (n <= 3 at most), and not to arbitrary boolean functions.

## 123 (limited to the four one-input functions)
A decision tree needs the ``3`` jump, which on a TRUE/FALSE bit jumps to the
*nearest* preceding/following ``3`` (not bracket-matched), so the only
constructible pattern is "repeat the region before the ``3`` while TRUE" —
no ``3``-based branch exists (a random search finds no NOT even at n == 1),
and the single data byte makes multi-bit state impossible (every read
overwrites it).  The one-input functions are pure bit arithmetic, however:
const-0/const-1 build the byte, identity reads and echoes it, and NOT flips
its least significant bit.  This is why no ``3``-based boolean generator
exists; the four one-input programs were too trivial to keep, so the boolean
generator was removed.

## Boolean generator caps (audited)
A sweep of the remaining input caps on the shipped generators, and whether
each is liftable:

- **NoComment: ``n <= 8`` is a genuine language wall, not a liftable cap.**
  The template computes the input's numeric index and does one ``s`` skip
  into the answer staircase, but ``s`` skips a *byte* (the stack top, read
  off the current cell), so the index and every jump are capped at 255.
  Lifting needs a conditional jump over a region > 255 commands, which is
  inexpressible: the region must be split with ``s`` commands, but each
  split-``s`` has to be gated on the tested bit while the pointer is
  mid-region, and the only way to reach the bit cell (a move) resets the
  pointer and undoes the region.  The decision-tree and binary-selection
  rewrites both hit this same wall.
- **Polynomial: ``n <= 4`` is a performance cap.**  Each instruction consumes
  a fresh prime, so the coefficients reach ~10**1746 at ``n == 5`` and the
  interpreter's exact factorization no longer completes in practical time.
  Lifting needs a faster factoring path, not a construction.
- **Home Row: ``n <= 2`` is a language cap.**  The grid is *fixed* at 5x5
  (25 cells); an exhaustive search shows no ``j``-guarded routing separates
  2**n combinations onto distinct cells past ``n == 2``.
- **Minifuck: ``n <= 3``, 0-preserving two-input tables only** (a re-verified
  structural wall: the decode suffix fixes the pointer orientation).
- **123: one input only** (single data byte; every read overwrites it).
- **Already total (no cap):** Circlefuck (decision tree, sampled to
  ``n == 16``), ROTfuck (phantom-block minterm sum, sampled to ``n == 4``),
  ABCDirection and BF-PDA (arbitrary ``n``, exhaustive to ``n <= 3``).

## RAM0, Bitdeque, Minsky Swap (not viable for the template model)
These three have value-testable branches and clean setters, but their jumps
are *absolute token indices*: RAM0's digit-`GOTO`, Bitdeque's `GOTO N`, and
Minsky Swap's `~` targets are all fixed positions in the token/command
stream.  The parameterized template's bit setter has variable length (e.g.
RAM0's `Z` for a zero bit vs `Z A` for a one bit; Bitdeque's `INVERT` vs
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

## SLOW ACV MAMMALIAN (branch-free core built; general n-bit functions open)

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

Re-verified against the interpreter (unlike Minifuck, this wall holds): a
search over the branch-free tails after the `b1`-normalize prefix reaches
only the 0-preserving two-input tables (const-0, both echoes, XOR, and
`NOT b0 AND b1` confirmed; no non-0-preserving table appears), matching the
structural argument above.

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

## ROTfuck (built; straight-line generator and phantom-block boolean generator)
Every executed command rotates all source characters one step along
`+-><,.[]`, so the character at position ``i`` at time ``t`` is
``rot^t(source[i])``.  Brackets are matched dynamically: when a ``[`` or
``]`` fires, the program is rotated first and the partner is then sought in
the rotated program with the standard nesting count, so an executed bracket
needs a partner in the current code, not in the source.  The text generator
therefore emits straight-line programs (``source[i]`` is the ``i``-fold
inverse rotation of the desired command), which fully covers arbitrary text.

The rotation defeats a brainfuck decision tree outright: a ``[ body ]``
whose body is a rotation-encoded loop cannot work, because when the ``]``
fires its ``[`` has rotated away (the ``]`` seeks the partner at a rotation
state that depends on the step count, and the body path and skip path arrive
with conflicting mod-8 alignment requirements — the skip-path seek needs
``q ≡ p+1`` while re-convergence needs ``q ≡ p``).  The boolean generator
sidesteps the wall by never looping: every ``[`` opens a block whose body is
straight-line ``+-><`` (no brackets), and the closing ``]`` is a *phantom*
encoded as the inverse rotation of ``]`` at the ``[``-fire seek state, so the
skip path (tested cell 0) seeks it and jumps past the block while the body
path (tested cell nonzero) sees a non-firing ``[``.  Because every body
length is 7 (mod 8), the two paths reach the position after the phantom in
the same rotation state and the rest of the program is position-encoded.
The table is a minterm sum: mismatch counters guarded by the bits and their
complements, one block per minterm zeroing it iff its counter is nonzero
(idempotent — the cell goes 1 to 0 exactly once), and ``1``-row blocks
accumulating into the printed result.  The programs are long (O(``n·2**n``)
blocks, ~1.4s/execution at ``n == 4``), verified exhaustively at
``n <= 2`` and sampled through ``n = 4``.

## Home Row (built; j-guarded-move boolean generator, n <= 2)
Home Row's ``l`` loops pair strictly by order (the first and second ``l``
form a loop, the third and fourth another), so loops cannot nest and a
bf-style decision tree is inexpressible.  But ``j`` skips the next
instruction when the current cell is zero, making ``jf``/``jd`` *guarded
moves*: a beam at a nonzero cell moves right/down, at a zero cell stays put.
The boolean generator routes a tree with these instead of loops.  The
template bakes the answer bytes (48/49) into leaf cells, then the ``{Xi}``
bit placeholders at cells ``0..n-1``, then a routing of ``j``-guarded moves
that sends each input combination to a distinct leaf, then ``k`` prints it.

The one-input routing ``jfd`` sends 0 -> cell 5, 1 -> cell 6; the two-input
routing ``jfjffjdd`` sends 00 -> 6, 01 -> 11, 10 -> 7, 11 -> 8, and every
``j`` in it tests a cell holding only baked bits (never an answer cell), so
the answers can be baked before routing without corrupting the branches.
Verified exhaustively for every one- and two-input table.  ``n >= 3``
raises: an exhaustive search over ``j``-guarded sequences shows no routing
separates ``2**n`` combinations onto distinct cells of the 5x5 torus past
``n == 2`` (the search caps at 6 of 8 combinations).

## Text generators: exhausted
Every language whose interpreter can emit arbitrary bytes already has a text
generator.  The remaining interpreter-only languages cannot, so no text
generator is possible for them: ArrowQueue has no output at all, Back prints
the tape as a number list, Bitdeque and Minsky Swap print their registers as
numbers, Movesum prints `n ` (numbers with a trailing space), RAM0 prints a
state dump, Keys prints only "Accept."/"Reject.", and Lightlang prints only
the single bit as a number.  None can spell arbitrary text.

Grapheme joins that list: its only output channels are a string of
uppercase Latin letters and an integer's decimal digits.  A string cannot
contain `E` (which terminates stringmode), so even "HELLO" is unspellable,
and there is no string-concatenation command to assemble text from parts;
a text generator therefore cannot produce "Hello, World!".  (Grapheme also
cannot read its inputs as clean bits: `W` yields the string `"0"`/`"1"`,
`J` maps those to -160/-150, both truthy, and string constants cannot spell
`"0"`, so a boolean generator is not feasible for the standard harness.)

## Category:Unimplemented candidates that fell through
Assessments of unimplemented languages from the wiki that did not make the
roadmap.  The viable candidates are in `docs/roadmap.md`.

- **Gravity**: particle-collision simulation whose evolution is in general
  non-computable, so no interpreter can be verified against expected output.
- **Earfuck**: a trivial brainfuck reskin that renames each instruction to a
  pentatonic-scale note; too easy to be worth a dedicated interpreter.
- **Conveyor**: multi-worker language with belts, stacks, and a hand, but no
  input command and only stderr output, so it cannot support the repo's
  file-based I/O protocol.
- **Chainlang**: an AI-generated graph-based spec whose own author warns it is
  unfinished ("don't expect it to be perfect").
- **Binary ///**: a stub with no usable specification beyond "only uses `1`
  and `0`".
- **Fourfuck**: an incomplete language whose spec is a stub with only a couple
  of core commands documented.
- **Aaargh++**: a 4D work-in-progress with a partial spec.
- **Bitwise Cyclic Teast**: a work-in-progress with a still-in-development
  interpreter definition.

## User:PythonshellDebugwindow candidates that fell through
Assessments of the unimplemented languages on PythonshellDebugwindow's user
page that did not make the roadmap (the actual Category:Unimplemented gaps —
Procedure, Lamfunc, Point Break, State and Main, Your Time Is Up, COD — are
in `docs/roadmap.md`).

- **N Refine**: probabilistic self-rewriting OISC with no I/O; also already
  implemented per its wiki page, so it is not a gap either way.
- **something positive**: explicitly uncomputable (its halting depends on
  program equivalence), so no interpreter can be verified.
- **LogicF---**: a joke language whose commands are non-deterministic and
  non-functional (a 2% chance to increment, a 67% chance to throw a
  KeyError, and so on), with no usable protocol.
- **Vandevelo**: input-only, with no output at all.
- **Varigen**: an explicitly "uncomputable" joke language.
- **Not Python**, **2001: An Esolang Odyssey**, **Stu**, **Bias**,
  **Writeover**: joke or vaguely specified languages with no usable
  specification or I/O protocol.
- **Objects In Mirror Are Heavier Than They Appear**, **OpenStreetCode**,
  **Streetcode**, **Unary Filesystem**, **Phile**: particle/map/file- or
  OS-based languages with no portable file-based I/O protocol.
- **Welcome To...**: a work-in-progress.

## Assessed boolean candidates that fell through
- **123**: its single 8-bit data byte and pointer that flips the bit as it
  moves (``1`` XORs the mask *and* advances) corrupt any value being built
  while the pointer navigates to the write position, and writing needs mask
  512 whose ``1``-path toggles masks 2..256.  The ``3``-jump (nearest
  preceding/following ``3``) and loop-from-start restart (reaching the end
  with the pointer at a data position resumes from index 0 without resetting
  data) provide real control flow, but an exhaustive search over every
  program up to length 13 (1.6M programs) shows input ``'0'`` (48) can only
  ever print the even bytes ``{0, 4, 6, 8, ..., 248}`` — the odd byte 49
  (``'1'``) is unreachable, so NOT and const-1 are inexpressible.  Only
  identity (``1112121121``) and const-0 (``1111132231``) work, both verified
  against the interpreter.  A boolean generator is not feasible for the
  standard harness.
- **%^2^-1**: its only control flow is ``t`` — rewind to the program start
  when the accumulator is nonzero — with the accumulator preserved across the
  rewind.  A program is therefore a whole-program ``while`` loop, and each
  ``n`` in the body consumes one input line, so a ``t`` loop iterates over
  the input bits.  It cannot count them: there is no increment-by-1 for an
  arbitrary value, and a ``m``/``s``-style counter in the rewind path grows
  without bound (the ``acc > 3003`` reset only fires on huge magnitudes, and
  the re-run re-applies the growth), so the loop stops only when a body pass
  ends with ``acc == 0`` — a uniform predicate that cannot tell pass 1 from
  pass n.  The all-ones row of any truth table therefore either stops the
  loop early or rewinds past the input (``StopIteration`` in the harness).
  Exhaustive search: of the four one-input functions only identity and the
  two constants are expressible (``ne`` and ``n`` + 24×``s`` + ``l`` for
  identity, ``l`` for const-0, ``ipsl`` for const-1); NOT and every two-input
  table fail even at length 8.  A boolean generator is not feasible for the
  standard harness.
- **Brainpocalypse**: its only control flow is ``-`` on a zero cell rewinding
  the instruction pointer to the program start (the tape stays intact), so a
  branch always restarts the whole prefix.  The output constraint closes the
  case: a bare boolean means only cell 0 may print (the ``right`` bound stays
  0), leaving just cell 0 and the wrap scratch cell 255 usable, and of the
  four one-input functions an exhaustive template search finds only identity
  (bake the bit into cell 0 and move to cell 255) — const-0, const-1, and
  NOT all need to branch on cell 0's value, which the ``-``-on-zero rewind
  consumes while re-running the bit-baking prefix (unbounded cell growth
  across restarts).  A boolean generator is not feasible for the standard
  harness.
- **The Temporary Stack**: the auto-drain is the only output, and it prints `front - 1`
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
- **Trash**: its only output is a prime-advanced number — a non-prime start
  prints ``0``, a prime start prints the next prime (3, 5, 7, ...), and no
  leading ``t`` prints nothing — so it can never print a boolean ``"1"`` and
  cannot return a truth-table result even parameterized.

## Transpiler walls

Transpilers exist where languages share a semantic core (through brainfuck,
and the one direct pair `Decleq → S*bleq`).  Direct transpilation between
languages with no shared core is a full runtime-in-a-language, not a program
rewrite:

- **OISC-to-OISC (S*bleq → Decleq; Decleq ↔ AddSubJump).**  Both
  self-modifying-memory OISCs share the "≤ 0 branch", and `Decleq → S*bleq`
  ships, but neither has dynamic instruction dispatch in general: S*bleq
  cannot express Decleq code that re-reads a written cell as an operand
  (self-modifying code; rejected), and ASJ's only conditional is
  ``dest = dest ± op`` by a fixed operand.  A general total transpiler is
  therefore not expressible; the partial classes would be silent-droppers.
  Documented as research-level future work in `docs/roadmap.md`.
- **2D-to-2D.**  No two 2D languages share a model: 2dFish is a deadfish
  accumulator, Dimensional a pointer-hierarchy tape, LaserFuck mirror-driven
  control, ABCDrection a Boolfuck bit tape with a queue, EXCON a straight-line
  bit pool.  Even the two bf-tape ones (Dimensional, LaserFuck) differ in
  control flow.
- **Dropped transpilers.**  `nocomment_to_bf` silently dropped NoComment's
  stack/jump/pointer commands (a silent mistranslation); the `6-5 → bf` and
  `Circlefuck → bf` decoders only reversed the forward transpilers' canonical
  form (round-trip-only).
## ABCDirection (built; scales to arbitrary n)
- The boolean generator ships and works for any ``n``.  A read staircase
  fills the queue, a corridor routes the pointer around the tree, each node
  dequeues a bit and tests it with ``C up``, and the fired leaf prints
  ``48 + f`` as a byte before running off the terminator row (``EOFError``,
  which the harness treats as termination).  The tree is laid out on absolute
  columns (each node sits at the midpoint of its leaf range, so the crossing
  subtrees can never meet), the ``D``-left cells are spaced so no six-``D``
  run fools the grid reader, each leaf routes DOWN at a clear column to its
  own escape row before the serpentine, and each leaf's EOF sink column is
  distinct so no turn cell sits on another leaf's upward path.
- Verified for every table at ``n <= 3`` (4 + 16 + 256 functions) and sampled
  through ``n = 6``.  The grid grows as ``O(4^n)`` cells (roughly ``60*2^n``
  wide by ``52*2^n`` tall), so exhaustive checks are only practical for small
  ``n``.

## BF-PDA (built; parameterized)
- The boolean generator ships and works for any ``n``.  BF-PDA has no input,
  so it is a parameterized generator: the harness instantiates the template
  once per input combination, and each ``{Xi}``/``{Ci}`` placeholder becomes a
  push of the bit or its complement onto the bit stack.
- The earlier wall was wrong: a decision tree *does* get two independent guard
  cells per bit from the stack.  A node pushes the complement then the bit
  (bit on top), runs the one-side loop ``[ sub1 @ ]`` when the bit is one,
  pops the bit, runs the zero-side loop ``[ sub0 @ ]`` when the complement is
  one, and pops the complement.  Every subtree is stack-balanced (leaves push
  the answer bit, print it with ``.``, and pop it), so each ``]`` re-tests its
  own guard and the if/else separates cleanly.
- Verified for every table at ``n <= 4`` (4 + 16 + 256 + 65536 functions);
  the programs are tiny and terminate immediately, so exhaustive checks stay
  cheap.

## Lean proofs (kept set)
The Lean project keeps only the proofs of facts the tests cannot establish:
SLOW ACV MAMMALIAN's generator search totality and Factor's Dirichlet-based
prime-search totality plus the encode/decode round-trip
(`extra/lean/esolangs/Esolangs.lean`, `FactorCorrect.lean`), and the
self-contained brainfuck-minterm boolean proof (`BfMintermCorrect.lean`).
Every other proof (the ported interpreters, their equivalence proofs, and
the generator/boolean correctness proofs) was dropped as redundant with the
round-trip test suite.  The one open theorem, if more Lean work is ever
wanted, is the Minifuck boolean reachability characterization above: it is
a language-power statement (exactly the four one-input functions plus the
eight 0-preserving two-input tables), not a generator-correctness proof.
