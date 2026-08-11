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

### Constant-loop boolean generator for arbitrary n
The boolean generators cover every table up to a small input count: 6-5 and
CircleFuck build decision trees capped at about 5 inputs (35 branch labels
for 6-5, n <= 5), Taglate is closed-form for n == 2, the brainfuck
generator handles any n but is branch-free and grows with the minterm count,
and Clockwise builds an uncapped decision-tree ring (three `R` in an L
pattern provide the counter-clockwise turn that closes it).  A generator
whose program size and loop count are *constant* in `n` (e.g. encode the
inputs as one number and decode the table entry arithmetically) is still
open; the BFStack encoder hints at the shape but no such generator has been
designed yet.  The BF-to-6-5 transpiler cannot provide it: the brainfuck
generator's loop count already exceeds the transpiler's 18-loop cap at
n == 2.

### Minifuck boolean generator (assessed: not viable)
Minifuck's tape is an 8-cell I/O register that every right move (`.`, `[`)
toggles on the way past, so positioning the pointer mangles the data it
crosses and a second input read overwrites the first.  The `[` conditional
skips one instruction with a side-effect toggle.  There is no way to keep
the input bits intact, so a decision tree is not expressible; no hidden
primitive equivalent to Clockwise's three-`R` turn exists.

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
