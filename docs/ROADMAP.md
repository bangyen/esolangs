# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## Planned

### Decision-tree brainfuck boolean generator (resolved: bf_tree)
The brainfuck generator previously had only the branch-free `bf` minterm
evaluator, which grows with the minterm count (XOR-n measured 1.4K, 7.3K,
40K, 222K, 1.2M characters at n = 2..6).  The old docstring claimed BF "has
no branching that would let leaves skip siblings", but BF's `[`..`]` loop
*is* a conditional skip.  The new `bf_tree` generator builds a decision
tree: bit `i` lives at cell `2i` with its complement at `2i + 1`, a node
tests `[bit]` for the one-side and `[1 - bit]` for the zero-side (the
complements naturally exclude the sibling), each branch clears its guard
cell before its `]`, and a fired leaf clears the result cell so every `]`
on the way out sees zero.  It is total and O(2**n) characters — XOR-n
measures 225, 485, 910, 1.6K, 3.0K, 5.6K at n = 1..6, ~1000x smaller than
`bf` on dense tables.  Verified exhaustively for every table at n <= 3 and
sampled at n = 4..6.  The two generators are complementary — the minterm
wins on sparse tables (an all-zeros table is ~450 chars at n == 8, vs the
tree's 20K) — so `bf` returns whichever of `_bf_minterm` and `bf_tree` is
shorter for the given table.

The same decision-tree construction was ported to Dimensional
(`dimensional_tree`), which is brainfuck on a multidimensional tape and
also lacks a halt command: identical structure with every move pinned
`>0`/`<0`.  `dimensional` dispatches the same way — the survivor evaluator
wins on sparse tables (~4.4K for AND-8), the tree wins on dense (XOR-8 ~8x
smaller).

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

### Dimensional v3 migration (done: Python interpreter; deferred: C++ reference)
The wiki now documents Dimensional **v3.0** (an n-slot/n-pointer model with
`$AXIS`, `d`, `x`), while the old reference in `extra/c++/dimensional.cpp`
implements **v1.0** (a single pointer over a product-of-primes tape).  The
two are incompatible dialects, and the v1.0 reference's 32-bit `int` cell
addresses overflow past ~30 cells — which is why the boolean generator's
verification used to be capped at `n > 12`.

The Python migration is **complete**: a first-class Python v3.0 interpreter
(`src/esolangs/interpreters/tape_based/dimensional.py`) is registered and
verified by 24 unit tests covering the interpreter semantics, plus text
round-trips (`Hi`, `Hello, World!`, `\x00\x7f\xff`) and boolean truth-table
round-trips through real execution.  The generator itself never had an
`n` cap (it generates random tables at `n = 16`), so the `n > 12` limit was
a verification constraint of the old reference; Python `int`s make cell
addresses unbounded and retire it.  Defaults and ambiguities the v3.0 wiki
leaves open (default pointer axis, the descent model, `d`/`x` reading from
input) are resolved pragmatically and documented in the interpreter.

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
