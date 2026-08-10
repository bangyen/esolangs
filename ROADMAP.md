# Roadmap

Planned work, in priority order. Completed ideas live in the commit history;
this file only tracks what is still on the table.

## Planned

### PyPI trusted-publishing release pipeline
Publish `esolangs` to PyPI using trusted publishing (an OIDC workflow rather
than a token). The package, public API, CLI, and typing are already in shape
for distribution; this is the remaining step to make it installable by
others.

### Boolean-table transpiler bridge
A dynamic transpiler across the boolean-capable languages — Sophie, Modulous,
BrainIf, Nevermind, and CircleFuck. These are genuinely different machines,
but each has a verified generator that builds a program for any truth table,
so a transpiler can lift a program from one to another:

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
for 6-5, n <= 5), Taglate is closed-form for n == 2, and the brainfuck
generator handles any n but is branch-free and grows with the minterm count.
Extending any of them to arbitrary `n` needs an arithmetic generator whose
program size and loop count are constant in `n` (e.g. encode the inputs as
one number and decode the table entry arithmetically); the BFStack encoder
hints at the shape but no such generator has been designed yet.  The
BF-to-6-5 transpiler cannot provide it: the brainfuck generator's loop count
already exceeds the transpiler's 18-loop cap at n == 2.

### Polynomial float64 root precision
The Polynomial generators emit exact integer polynomials, but the
interpreter finds roots with `numpy.roots`, whose float64 companion-matrix
computation loses the small imaginary parts when the roots span a wide
magnitude range.  That happens when consecutive characters differ by large
codepoint amounts (e.g. ASCII immediately followed by a CJK character), so
such text silently corrupts (documented under README "Known Issues").  The
natural fix is a higher-precision root finder (e.g. `mpmath.polyroots`) in
`src/esolangs/interpreters/register_based/polynomial.py`, which recovers the
exact-integer roots reliably.  A heuristic guard is *not* viable: OK and
FAIL cases overlap in both coefficient magnitude and max delta, and even the
same delta passes or fails depending on the surrounding pattern.

The same fix lifts the boolean generator's `n > 2` cap
(`src/esolangs/tools/booleans/register.py`): a depth-`n` decision tree emits
`2*2**n + ...` instructions, each consuming a fresh prime, so the expanded
coefficients grow to ~10**90 at n == 3 (1196 bits) and ~10**4900 at n == 6
(16309 bits) — far beyond float64's range, which is why the boolean generator
currently rejects `n > 2`.  Arbitrary-precision roots handle both the
precision loss and the range overflow, so this is one interpreter change with
two payoffs.  It needs a dependency decision (adding mpmath) and a focused
interpreter change with its own tests.
