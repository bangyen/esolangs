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

### LaserFuck boolean generator (resolved: loop-free decision tree)
LaserFuck is brainfuck on a 2D grid: a laser (with a random initial heading)
travels the grid, `>`, `<`, `+`, `-`, `,` work on the tape, ``(``/``)`` and
``_``/``|`` bounce the laser when the tape cell is nonzero (or always), and
the whole tape is printed at the end.

The planned route was a general BF-to-LaserFuck layout compiler with loop
rings, but the boolean generator (`laserfuck` in `booleans/other.py`) took a
**loop-free** route instead: a mirror funnel (`|`/`^`/`_` plus two `}`)
sends every heading to the top row moving right, reads and normalizes the
inputs, and walks a decision tree.  Each node's `#` makes the following `v`
a one-way gate (skipped on approach, active on reflection), so `)` routes a
zero cell straight through to `\` (down one column) and a nonzero cell back
to `v` (down another column); each child row's `\` turns the beam right into
the child.  Leaves live at a dedicated high column so no `+` run crosses a
descent column, move the pointer to cell `n`, set it to 48+result, and hit
`x`.  No loops means no loop-ring geometry.  The output mode's whole-tape
dump prints the 0/1 inputs as NUL/SOH, so the verify harness's `01` filter
leaves exactly the result cell.

The generator verified exhaustively for every table at n <= 3 and sampled
at n = 4..6 through a Python interpreter that was differential-tested
against the Rust reference (`extra/rust/laserfuck.rs`) on structured
programs and every generated boolean grid.  A Python interpreter
(`interpreters/other/laserfuck.py`) was also added for the boolean tests; it
is not registered as the global runner because the reference's random
heading makes text-generator round-trips nondeterministic.

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

### Differential fuzzing for the interpreter/native pairs
The differential corpus (`scripts/verify_differential.py`) covers EXCON,
LaserFuck, and NoComment with a hand-written set of programs per language.
The corpora exercise every instruction plus known edge cases, but they are
fixed — they only catch divergences that were thought of.  A seeded
random-program fuzzer that feeds both the in-package interpreter and the
native cross-check the same generated programs (restricted to terminating
inputs) would catch the unexpected divergences, like the NoComment
back-jump loop and the EXCON pointer-fault case the fixed corpora surfaced
only by chance.  Where the native side is nondeterministic (LaserFuck's
random heading), compare against its output set as the corpus already does.

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
