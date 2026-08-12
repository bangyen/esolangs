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

### Differential fuzzing for the interpreter/native pairs (done: seeded fuzzers)
The differential corpus (`scripts/verify_differential.py`) covers EXCON,
LaserFuck, and NoComment with a hand-written set of programs per language.
The corpora exercise every instruction plus known edge cases, but they are
fixed — they only catch divergences that were thought of.  The script now
also takes `--fuzz N --seed S`: a seeded random-program fuzzer that feeds
both the in-package interpreter and the native cross-check the same
generated programs and compares output **and error category** (exit code)
and, for NoComment, the termination verdict itself.  The seed makes the
explored programs reproducible, and CI runs it with a fixed seed.

- **EXCON**: random straight-line programs over `:^<!` (the only fault is
  the off-pool pointer, exit 3 on both sides).
- **NoComment**: random programs over the full 10-command alphabet.  A
  random `b`/`s` program may loop forever; both sides bound the run (the
  assembly via its instruction-count cap and its fixed tape/stack region,
  Python via SIGALRM) and a program that halts on one side but loops on the
  other is a divergence.
- **LaserFuck**: random truth tables through the boolean generator (raw
  random grids would hang the reference), comparing Python's four headings
  against the Rust output set as the corpus does.

The fuzzers immediately caught two real NoComment divergences the fixed
corpus had missed: the assembly's jump bounds check allowed a target on the
null terminator or the uninitialized gap byte the input loop leaves after
the last command (both fixed to reject targets outside the real command
range, matching Python's `0 <= target < len`), and it performed an empty
stack "jump" by reading the null as a zero amount (fixed to skip the jump
entirely, matching Python's `if tape[ptr] and stack`).  The fuzzer's
termination-mismatch logic re-checks a Python timeout with a longer budget
before reporting a divergence, so a slow-but-terminating program is not a
false positive.

### Polynomial float64 root precision (resolved: hybrid high-precision refine)
The Polynomial generators emit exact integer polynomials, but the
interpreter found roots with `numpy.roots`, whose float64 companion-matrix
computation loses the small imaginary parts when the roots span a wide
magnitude range.  The deeper cause is that the integer coefficients far
exceed float64's exact-integer range (2**53): `'Hello, World!'` has
coefficients up to 10**95, so numpy rounds them before building the
companion matrix and solves a different polynomial.  Text whose consecutive
characters differ by large codepoint amounts (e.g. ASCII immediately
followed by a CJK character) silently corrupted.

The interpreter now seeds numpy's fast result into a high-precision
`mp.polyroots` (Aberth) refinement (`interpreters/register_based/polynomial.py`),
with `extraprec` absorbing the coefficient magnitude.  This fixes the common
corruption: a 500-program mixed-unicode fuzz that corrupted 14 under numpy
is clean, and the previously-broken cases (`'😀t'`, `'a日a日'`, CJK
adjacent to ASCII, ...) round-trip.  `numpy` remains as the cheap seed; it
is never the final answer.

What does NOT work (verified empirically while implementing):

- A pure `mp.polyroots` swap is ~3000x slower per program (~0.7s vs
  numpy's 0.24ms) because its default initial guesses converge slowly on
  the wide-spread root sets.
- A change-of-variable scaling does not help: the scaled coefficients are
  still far beyond float64, and the rescaled roots of the (imprecise)
  scaled solve are wrong roots of the original polynomial.
- A residual-based gate cannot detect failure: because the polynomials are
  ill-conditioned (condition number ~1e16), even wildly wrong roots have
  tiny relative residuals (~1e-32) against the exact polynomial, at any
  precision.  So the interpreter never tries to "verify" a converged
  result — it trusts the seeded Aberth solve and lets `NoConvergence`
  propagate as a loud error instead of silently corrupting.

A pathological program whose roots span several orders of magnitude (e.g.
the same wide codepoint delta repeated several times, like
`'aあbいcう' * 3`) still defeats the Aberth solve and raises
`NoConvergence`; this is strictly better than the old silent corruption.

The boolean generator's `n > 2` cap is **retained**: at `n == 3` the
coefficients reach ~10**360, numpy overflows before seeding, and a seedless
solve of the degree-104 polynomial does not converge in practical time.
Lifting it would require a genuinely different seed strategy for the
overflow case, not just higher precision.

### Future direction: recover roots by factoring the integer polynomial
The conditioning problem is inherent to *root finding*: the polynomial is so
ill-conditioned that any floating-point solver (float64, mpmath Aberth, or
high-precision QR) either converges to wrong roots or not at all.  But the
interpreter does not need *approximate* roots — it needs the exact integer
instruction values `a`, `p`, `b`.  Those are recoverable **exactly** by
factoring the monic integer polynomial over `\mathbb{Z}` (Zassenhaus /
sympy's `factor`), because every instruction contributes a known factor
shape:

- a complex instruction ``[a, b]`` is the quadratic ``(x-a)^2 + p^(2b)`` =
  ``x^2 - 2a x + (a^2 + p^(2b))``, so the linear coefficient gives ``a``
  and the constant term minus ``a^2`` is an exact square ``p^(2b)``;
- a real instruction ``[v]`` is the linear factor ``x - p^v``.

Verified on the two cases that defeat every numeric solver: the
pathological text ``'aあbいcう' * 3`` (degree 72, 36 quadratics, ~0.6s,
exact) and a boolean ``n == 3`` program (degree 88, coefficients ~10**285,
58 instructions, ~1.2s).  This would fix both open gaps and replace the
fragile seed+refine path entirely.

Measured timing (sympy's `factor`): long text degree 104 -> ~1.7s; boolean
``n == 3`` (degree 88) -> ~1.1s; boolean ``n == 4`` (degree 184,
coefficients ~10**729) -> ~10.5s.  So the boolean cap could lift to ``n ==
4`` at a cost, and even ``n == 5`` is not obviously impossible.

Open questions before committing to it: sympy's import alone costs seconds
(so it would need to be imported lazily, and it changes the package's
dependency profile — numpy + mpmath + sympy); factorization cost grows with
degree, so the timing at ``n >= 5`` and very long texts should be measured;
and a hand-rolled factorer for just these two factor shapes (quadratic with
a perfect-square constant, and linear) might avoid the sympy dependency
entirely — the generator's polynomials are exactly products of those
shapes, so a targeted square-free/divisor search could recover them without
a general Zassenhaus implementation.

Dependency note: `numpy` (for the seed) and `mpmath` (for the refine) are
the only third-party imports, both hard dependencies used solely by the
polynomial interpreter's root finding.
