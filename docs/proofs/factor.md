# Factor: size and construction bounds

The standalone theorem is [factor.tex](factor.tex).  This companion retains
implementation bounds and the executable evidence behind them.

A Factor program is one decimal integer. Factoring it yields an ordered list
of prime powers; a prime's residue mod 11 selects a Brainfuck command and its
exponent is the run length. Put

- `C` for the decoded Brainfuck length, `m` for its maximal runs;
- `Q` for the largest selected prime; and
- `D` for the rendered decimal digits.

For a generated encoding, which has no ignored-residue factors, exactly

    log N = sum_i e_i log p_i,       D = floor(log10 N) + 1.

The Boolean generator has `C = O(T)` and `m <= C`, where `T` is the table
length.

## Generated text

Dirichlet proves termination but does not bound this adaptive prime sequence:
each run asks for a possibly different residue above the preceding prime. The
needed quantitative result is the fixed-modulus Hoheisel theorem. For each of
the eight reduced classes mod 11, some `theta < 1` puts a prime in
`(x, x + x**theta]` for every sufficiently large `x`. Thus

    p_(i+1) <= p_i + O(p_i**theta),   so Q = m**O(1).

Consequently `log Q = O(log(m + 1))` and

    D = O(C log(m + 1)) = O(T log(T + 1)).

## Explicit constants

The tree is exact: for `n >= 2`, `C <= 35T/2 + 55n + 25`, and parity attains
it (each non-root node costs 12 own characters plus 4 or 3 to enter and leave
a child, or `4(n - i)` for a one-leaf, so `F(k) + 19 = 35 * 2**(k - 1)`).
The walk's leading constant is explicit though its threshold is not: from
`p_i**(1 - theta) <= p_(i0)**(1 - theta) + (1 - theta) i`,

    limsup D / (T ln T) <= 35 / (2 (1 - theta) ln 10) <= 42 / ln 10 < 18.25

for every admissible `theta > 7/12`.  That `x_0` is ineffective only because
the quoted theorem is uniform in `q`.  At the fixed modulus 11 the sole
ineffective ingredient is Siegel's bound for `L(1, chi)` at a real character,
and the only real character mod 11 is the Legendre symbol, odd since
`11 = 3 mod 4`; `Q(sqrt(-11))` has class number 1 and two units, so
`L(1, chi) = 2 pi h / (w sqrt 11) = pi / sqrt 11 = 0.94722...`.  No
exceptional zero, so the threshold is effective in principle -- what is
missing is a value.

For practical arities a sieve replaces it.  `scripts/factor_class_gaps.c` ran
through `10**11` (14 minutes): every class `1..8` has a prime in
`(x, x + 8.62 ln**2 max(x, 37)]` for `x <= 10**11 - 10**4`, the maximum ratio
8.6184 being class 2 at 4,160,719.  Any `y` with
`37 + (C - 1) 8.62 ln**2 y <= y <= 10**11 - 10**4` then bounds `Q`, and
`D <= floor(C log10 y) + 1`.  With the tree bound this is a proven ceiling
over all tables through `n = 19`:

| n | ceiling D/(T ln T) | parity D/(T ln T) |
| --- | --- | --- |
| 8 | 24.56 | 16.99 |
| 10 | 20.06 | 14.75 |
| 13 | 16.98 | 13.09 |
| 16 | 15.31 | |
| 19 | 14.19 | |

`tests/proofs/deep/factor_constants.py` re-checks the tree bound, the gap
constant on a sieved prefix holding its maximum, the end window, and the
ceiling against parity.

## A value for the threshold, on GRH

Dudek, Grenie and Molteni (IJNT 15 (2019) 825-862, Thm 1.1) prove on GRH that
`h >= phi(q)(a ln x + d ln q + r) sqrt x` and `x >= (m phi(q) ln q)**2` put a
prime `= a mod q` within `h` of `x`.  Their row `(1/2, 1, 12, 23)` at `q = 11`
has threshold `(230 ln 11)**2 < 3.05e5` -- five orders of magnitude *below*
the sieved `10**11`, so the two overlap and no `x` is uncovered.  Recentring
at `c = x + h(2x)` (legal since `h(2x)/x` falls to `1.2e-3` by `10**11`) turns
the two-sided statement one-sided:

    p_(i+1) <= p_i + 2 h(2 p_i),   h(t) = 10(ln t / 2 + ln 11 + 12) sqrt t.

Concavity in `u = sqrt p` gives `u_(i+1) <= u_i + 10 sqrt 2 ln u_i + 208.52`,
so `Q = O(m**2 ln**2 m)` and `ln Q <= 2 ln m + O(ln ln m)`: the walk is
quadratic rather than Hoheisel's `m**2.4`.  The first
`K = floor((X - 37) / (8.62 ln**2 X)) = 18,083,227` runs are spent climbing to
`10**11` under the sieve rule, so for `C > K` any `U >= sqrt(10**11)` with
`sqrt(10**11) + (C - K)(10 sqrt 2 ln U + 208.52) <= U` bounds `Q <= U**2` and
`D <= floor(2 C log10 U) + 1`.  Hence, on GRH,

    D <= 24.6 T ln T for every n >= 8,   limsup D/(T ln T) <= 35 / ln 10 < 15.21

-- an explicit ceiling at every arity, and a better constant than the
ineffective 18.25, since a square-root gap is `theta = 1/2` and
`35/(2(1 - theta)) = 35`.  The two rules cross exactly at the sieve's edge:

| n | 13 | 16 | 19 | 20 | 22 | 25 | 30 | 60 | 10**3 | 10**6 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D/(T ln T) | 16.98 | 15.31 | 14.19 | 20.46 | 24.06 | 23.27 | 22.01 | 18.75 | 15.47 | 15.20 |

Through `n = 19` the sieve is stronger; the GRH ceiling peaks at 24.06 at
`n = 22` and falls from there.

## The walk pays one logarithm a run

The ceilings above charge the walk `ln Q = 2 ln U` a run on GRH, twice what
a prime walked past every `ln p` would cost, because the short-interval
theorem is applied at every step at its worst case.  The walk crosses each
gap between consecutive class primes at most once, so `m` steps advance at
most `m` typical gaps plus the total length of the atypical ones, and a
second moment makes that total `o(x)`.

Call `x` bad for the class `a` and the length `h` if `(x, x + h]` has no
prime `= a mod 11`.  On GRH, with `h(X) = ceil(ln**3 (2X))`, the integers of
`[X, 2X)` bad for some class number `O(X/ln X)`: Prachar's generalization of
Selberg's theorem (Topics in Number Theory, Debrecen 1974, 267-280), in
Harm's form (arXiv:2507.15334, Cor 2.10), gives
`sum_a int_X^(2X) |Delta pi(u, h', 11, a)|**2 du << h' X` for
`h' >= 11 ln**(2+eps)(11X)`, and a bad `x` makes `|Delta pi| >= h'/(10 ln 3X)`
on a unit window of `u`, so the bad `x` number `<< X ln**2 X / h' << X/ln X`.
Unconditionally, with `h(X) = ceil(121 (2X)**(1/15 + eps))`, they number
`O_eps(X/ln X)` with an ineffective constant: Koukoulopoulos (IJNT 11 (2015)
1499-1521, Thm 1.3) gives, for `Q**2 <= h/x**(1/15 + eps)`, all but
`O(Qx/ln**A x)` pairs `(q, n)` with `q <= Q`, `n <= x` a weight
`>= c h/phi(q)` of class primes in `(n, n + h]` for every class.

The encoder makes `p_(i+1)` the least class prime above `p_i`, so every `x`
in `[p_i, p_(i+1) - h(x))` is bad for that class, and

    p_(i+1) - p_i <= h(p_m) + 1 + #{x in [p_i, p_(i+1)) bad},
    p_m <= m (h(p_m) + 1) + O(p_m/ln p_m) <= 3 m h(p_m)

for large `m`, uniformly in the classes.  Hence

    p_m <= m ln**4 m   on GRH,      p_m <= m**(15/14 + eps)   unconditionally,

that is `ln Q <= (1 + o(1)) ln m` on GRH and `(15/14 + o(1)) ln m` without
it.  With the enumerative lookup below, `C <= (1/log2(1 + sqrt 2) + o(1)) T`
and `m <= C`, so

    limsup D/(T ln T) <= 1/(log2(1 + sqrt 2) ln 10) = 0.34155   on GRH
                      <= 15/14 of that              = 0.36595   unconditionally

(the latter ineffective).  The same lemma halves the earlier limits: the
tree's `35/ln 10 = 15.20` becomes `35/(2 ln 10) = 7.60` on GRH and packing's
`0.874` becomes `0.437`.  It says nothing about thresholds; the per-arity
ceilings above stand as the explicit statement.  L11 in
`tests/proofs/deep/factor_drawing.py` pins `0.34155`.

## Without GRH

Assembled, unconditionally (Lemma "Unconditional explicit short intervals"
and Corollary after it in the paper).  Dudek-Grenie-Molteni's smoothed
formula (their Lemmas 3.1-3.2, Fejer kernel of width `h`) is unconditional;
it needs the zero sum over `zeta` and the nine `L(s, chi)` mod 11 below
`h**2/10`.  Zeros with `|gamma| <= T` cost `h**2 X**(beta - 1)` each:
Thorner-Zaman (Forum Math 36 (2024), Thm 1.2) count those near `sigma = 1`,
`N(sigma) <= 10**88 (10**421 T**99)**(1 - sigma)`, and Kadiri's regions
(`R = 5.60` for `L`, `5.70` for `zeta`) cut them off at
`1 - 1/(5.70 ln 11T)`.  Zeros above `T` cost `4X**2/gamma**2` each, summed
by the explicit counts of Bennett-Martin-O'Bryant-Rechnitzer and
Hasanalizade-Shen-Wong; that `1/gamma**2` tail forces `T ~ x**(2/A)`, which
is where the leading `2` comes from.  Result: with

    A_0 = 2 (99 + 5.70 ln(4 * 10**88)) = 2523.75...

every `A > A_0` and every `x` with
`(1 - A_0/A) ln x >= 1262 ln ln x + 3758` and `ln x >= A/5` has a prime of
every class mod 11 within `x**(1 - 1/A)` of `x`.  Nine tenths of `A_0` is
the `10**88` through the `5.70`.  The walk then gives
`Q <= ((2 x_0)**(1/A) + 4C/A)**A`, hence

    D <= 3.05e4 T ln T for every n >= 8,   limsup D/(T ln T) <= 35 A_0/(2 ln 10) < 19181

and, per arity with the best `A`:

| n | 20 | 22 | 25 | 30 | 60 | 10**3 | 10**6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D/(T ln T) | 24500 | 24050 | 23480 | 22800 | 21060 | 19330 | 19200 |
| A | 4339 | 4170 | 3879 | 3638 | 3035 | 2556 | 2525 |

The threshold is `x_0 > e**15900` at every `A`, and the constant is three
orders of magnitude above GRH's 24.6, so the practical statement stays on
GRH; what closed is that `x_0` and `theta` have values.  A sharper cutoff
than the Fejer kernel would halve `A_0`; Khale's explicit Vinogradov-Korobov
region (arXiv:2210.06457) would let `A` approach `198`, limsup below 1505,
at a larger threshold.  `tests/proofs/deep/factor_constants.py` evaluates
the full inequality, not just the sufficient condition, at every `A` in the
table and on a sweep above each threshold.

The language lower bound below supplies a table on which every generator must
spend `Omega(T log T)`, so this generated upper bound is tight in the worst
case. This is not a per-table claim: constant subtrees fold and can be much
smaller.

## Generation time

Prime discovery during generation uses exact segmented Eratosthenes
enumeration, not `isprime` (`_factorint` below still calls the deterministic
Miller--Rabin `_isprime64` under `2**64`): above `2**64` SymPy's latter is BPSW
and is not a proof of primality, while SymPy's own sieve stores machine words. The local sieve keeps
arbitrary Python integers through `sqrt(Q)`. Segments grow to `sqrt(start)`,
so composite marking costs `O(Q log log Q)`, revisiting base primes costs
`O(Q/log Q)`, and extending them by trial division is smaller. Cold prime
enumeration is therefore `Theta(Q log log Q)` RAM/byte work and `O(sqrt(Q))`
memory; this treats arithmetic on its `O(log Q)`-bit indices as one RAM
operation. Hoheisel makes both polynomial in `T`.

Let `alpha = log_2 3`. CPython's balanced integer products use Karatsuba at
scale, so the encoder's balanced `D`-bit product carries a `Theta(D**alpha)`
arithmetic term. Python 3.14's large decimal render passes through `_pylong`
and libmpdec, but libmpdec only recurses with three half-size products above
`3 * 2**32` machine words (about `2.5 * 10**11` decimal digits), so up to that
`D` -- far past any generated table -- rendering stays in its quasi-linear FNT
range and adds `O(M(D) log D) = O(D log**2 D)`. Above it the three-way
recurrence is itself
`Theta(D**alpha)`, so the cold bound is unchanged either way. The encoder
combines the two smallest bit-width products first.
Superlinearity charges powers and merges to the final `D` bits geometrically;
CPython's lopsided path splits a large operand into small-width chunks.  Both
regimes fit `cost(a, b) <= max(a, b) * min(a, b)**(alpha - 1)`, under which
smallest-first merging gives the cold bound

    sum_merge cost(a, b) = O((sum_i leaf_bits_i)**alpha).

Write `s = a + b`.  Since `min <= s/2` and `max <= s`, one merge costs at most
`2**(1 - alpha) * s**alpha`, which absorbs the lopsided split, so no case
analysis follows.  Smallest-first makes the merged totals `s_t` nondecreasing,
so the merges with `s_t >= 2**k` are a suffix in time; at the first of them
every live item but at most one has size `>= 2**(k - 1)`, leaving at most
`2 + D * 2**(1 - k)` items and hence that many later merges.  Summing over
scales,

    sum_t s_t**alpha <= 2**alpha * (2 * sum_k 2**(k*alpha)
                                    + 2D * sum_k 2**(k*(alpha - 1)))
                      = O(D**alpha) + O(D * D**(alpha - 1)),

both geometric sums dominated by their `k = log2 D` term since `alpha > 1` and
`alpha - 1 > 0`.  The argument uses only `cost <= s**alpha`, so it is
indifferent to which multiplication CPython picks.  Equal leaves attain it: in
this cost model `cost / D**alpha` rises to 0.9985 at `D = 65536` and never
exceeded 1.027 over 4000 random leaf families, so `D**alpha` is the merge
term's order and not just a ceiling.  An `alpha`-power potential does not reach
this: for `a << b` the ratio
`cost(a, b) / ((a + b)**alpha - a**alpha - b**alpha)` grows like
`(b/a)**(2 - alpha)`, so lopsided merges outrun the potential.  What is proved
is the upper bound

    generation = O(T + Q log log Q + D**alpha) = T**O(1).

Only the upper bound is claimed: the terms need not balance, so `Theta` is not
established, and the sieve term can exceed `D**alpha` for the largest `Q` the
Hoheisel bound permits.

Hoheisel is far from tight here, and the gap is measurable.  Walking `m` runs
and recording the largest selected prime, `Q / (m ln m)` is flat over
`m = 50..1600`: 12.4 to 12.0 when the requested residues are random, 17.6 to
14.9 when they are all one class, and 40.0 to 37.0 when an adversary picks, at
each step, the class whose next prime is farthest.  All three are
`Theta(m log m)`, differing only in the constant, against the `m**O(1)` the
Hoheisel route yields.  The one-class row is the positive control: it is the
case the prime number theorem in arithmetic progressions settles outright, and
it grows no slower than the other two.  `10 m ln(10 m)` predicts
`Q/(m ln m) -> 10 + 23/ln m`, which is 12.9 at `m = 3200` against 12.0
measured.

Hoheisel per step is the wrong tool: only the *sum* of the `m` gaps matters,
and the walk crosses each gap once.  The almost-all lemma above makes that
`Q <= m ln**4 m` on GRH; the measurement says the true order is `m ln m`.

## Cold parsing

For generated programs, `_factorint` uses the same exact prime stream, bounded
by `Q`, tests a sieve segment with one gcd once the residue is wide
(`_BATCH_BITS`, and a remainder per prime below it), and performs `C`
successful prime divisions. Decimal parsing, sieving, gcds and divisions are all
polynomial in `Q,D,C`; with `Q=T**O(1)`, cold parsing and its
`O(sqrt(Q) + D + C)` live storage are polynomial in `T`.

That statement cannot cover arbitrary Factor programs. A balanced `D`-digit
semiprime can force the trial sieve toward `sqrt(N) = 10**Theta(D)`. There is
no polynomial bound in source digits, and no fallback claim is made.

## Language lower bound

Put `L = O(D)` for the log of a `D`-character source's digit integer. If its
decoded behaviour uses `k` useful primes, its `i`-th one is at least `i + 1`, so

    sum_i e_i log(i + 1) <= L,       k = O(L/log L).

For fixed `k`, put `f_i = e_i - 1` and `s = 1/log(L + 2)`. The exponential
generating bound for these nonnegative vectors is

    exp(sL) product_i (1 - (i + 1)**(-s))**(-1).

Its log is `O(L/log L)`: the first `sqrt(L)` factors contribute only
`O(sqrt(L) log log L)`, and every later factor contributes `O(1)`, across
`k = O(L/log L)` positions. Summing over `k` and choosing each useful prime's
eight command residues preserves `exp(O(D/log D))` behaviours. Hence covering
all `2**T` tables forces

    D = Omega(T log T).

The count covers every encoding: ignored-residue primes, comments and leading
zeros do not add behaviours. The exceptional integer zero adds only the empty
behaviour. It matches the generated `Theta(T log T)` upper.

## A value for the floor

The `Omega` above hides its constant in the Markov parameter `s`, which was
picked only to make the exponent `O(L/log L)`. Put it at the saddle instead.
Write `q_i` for the `i`-th prime with residue `1..8` mod 11 -- `2, 3, 5, 7,
13, ...`, and `q_i = (5/4) i ln i (1 + o(1))`. A behaviour is a string over
the eight instruction letters, its runs carried by increasing useful primes,
so `L >= sum_i e_i ln q_i`. With at most `8 * 7**(k-1)` class words and
`s = ln 8/ln q_K`, where `K` is the largest affordable run count, every
`q_i**s <= 8`, so each factor `7/(q_i**s - 1)` is at least 1 and the sum over
`k` is at most `K` times its last term:

    ln #behaviours <= ln(8K/7) + sL + sum_(i<=K) (ln 7 - ln(q_i**s - 1)).

`K = (1 + o(1)) L/ln L` and `ln q_K = (1 + o(1)) ln L`, so the middle term is
`(ln 8 + o(1)) L/ln L`; the sum is `o(L/ln L)`, since past `i = K**(1-eps)`
each term is below `ln(7/(8**(1-eps) - 1))`. So the count is
`exp((ln 8 + o(1)) L/ln L)` -- one instruction letter per unit of run length,
which is what `ln 8` says. Since `2**T <= 10**D` already gives `ln D = ln T +
O(1)`,

    D >= (1 - o(1)) T ln T / (3 ln 10) = 0.14476 T ln T.

`ln 2/ln 8 = 1/3` is the whole constant. The crude `p_i >= i + 1` gives the
same one -- `ln(i+1)` and `ln q_i` agree to leading order -- but approaches it
more slowly: at `L = 10**5` the real primes give 2.2958 and the crude bound
2.9147, against `ln 8 = 2.0794`.

The convergence is slow either way, the correction being of order
`lnln L/ln L`. On a real prime table the exponent reads 2.5566, 2.3788,
2.2958 at `L = 10**3, 10**4, 10**5` (L5 in
`tests/proofs/deep/factor_constants.py`); continuing with the asymptotic for
`q_i` in place of a table, it reads 2.1547 at `10**12`, 2.1153 at `10**24`
and 2.0899 at `10**80`, with the saddle `s ln q_K` sitting on `ln 8` to four
places throughout.

### Reduced words

`ln 8` is right for spellings: there are `8**l` strings of length `l`, and by
the walk lemma each is spelled for `(1 + o(1)) l ln l` on GRH, so the count
is tight to `1 + o(1)`.  The floor moves only by counting behaviours rather
than spellings, and the first step is free: a shortest source contains none
of the adjacent pairs `+-`, `-+`, `><`, `][`, `[]`.  The first three are
identities (`><` because a move right always succeeds; `<>` is not one at
the leftmost cell); a `]` is left on a zero cell, so a `[` after it skips its
bracket, dead with its body; an entered `[]` never terminates, so in a
program that terminates on every input it is never entered and dead too.
Deleting never raises the cost: each surviving run is a union of consecutive
old runs, and the prime of its first old run keeps the primes increasing and
in class.  The class words are then walks in the graph on the eight
instructions without loops and without those five arcs, `O(k**8 lambda**k)`
of them at length `k - 1`, `lambda` the Perron root of the adjacency matrix,
whose characteristic polynomial is

    x**2 (x + 1)**2 (x + 2) (x**3 - 4x**2 - 14x - 8),    lambda = 6.38776.

With `s = ln(1 + lambda)/ln q_K` every factor `lambda/(q_i**s - 1)` is at
least 1 and the saddle argument goes through with `ln(1 + lambda)` for
`ln 8`:

    D >= (1 - o(1)) T ln T / (log2(1 + lambda) ln 10) = 0.15053 T ln T.

L12 in `tests/proofs/deep/factor_drawing.py` finds `lambda` by power
iteration, checks it against the cubic, and pins the floor.

## The chained lookup

The tree's `17.5` characters an entry is not the language's price. Carry the
table as tape data and index it: `C_F(T)` minimizes over all programs, so
paying execution time for length is free here.

The obstacle is that a brainfuck cell holds a byte, so an index into `T`
cells stops fitting at `n = 8`. Measured, not guessed: a single-cell index is
right for every index below 256 and wrong for every index at or above it.
**Chaining removes the cap** -- split the index into chunks of at most eight
bits, one per level of a tree of blocks, and read each chunk from the input
at the place its level needs it, so no counter is ever carried.

Blocks are `B[-1] = 2` and `B[j] = 256 B[j-1] + 2`; a block is 256
sub-blocks then two scratch cells, its *anchor*, and a leaf block is 256
pairs of a walk cell and a data cell. From an anchor, two cells left is the
last sub-block's anchor and

    [[- <*B[j-1] + >*B[j-1] ] <*B[j-1] -]

hops one sub-block left per unit, landing on sub-block `255 - digit`. The hop
only ever touches anchors, which are scratch, so the data survives it, and
the landing cell is left zero -- which is why the data is laid out reversed
at every level.

Cost, with the complement stored when ones are in the majority:

    span      (2 + 2/255) T      the data pass, one move per cell
    ones              T/2        one '+' per set entry, capped by the flip
    hops           6T/255        3 characters per stride, summed over levels
                  ------------
                  2.5314 T

so `limsup D/(T ln T) <= 2 * 2.5315/ln 10 = 2.1989 < 2.20` on GRH, against
the tree's `15.2003`. The short chunk goes *second from the top*: a hop loop
is `3 * stride` characters and the top stride is the span over the top radix,
so a small radix on top costs three times what it costs at the leaf, where it
only wastes scratch. Getting that wrong put `n = 18` at 4.03 characters an
entry instead of 2.55.

Measured against the tree, on parity:

    n       T           tree        chain   ratio   chain/T
    12      4,096      72,365      11,808    6.13     2.883
    16     65,536   1,147,785     167,136    6.87     2.550
    18    262,144   4,588,535     667,039    6.88     2.545
    20  1,048,576  18,351,205   2,657,911    6.90     2.535

L6 in `tests/proofs/deep/factor_constants.py` pins the closed form against
what is emitted for `n = 1..14`, runs every input of every table at
`n = 1..6` (378 executions) and samples `n = 9, 10, 12` around the byte
boundary that broke the single-cell version.

The walk is quadratic in `T` where the tree is linear, so this is a statement
about the language and not a replacement generator; the shipped generator
keeps the tree, and Section 4's per-arity ceilings describe that tree.

## Grouping: one walk cell per k entries

Two cells an entry is more than the hop needs. The hop wants a zero cell
beside what it addresses -- but only at the granularity it *addresses*. So
address groups:

    [W][S0][S1][d_0] ... [d_(k-1)]     k + 3 cells for k entries

The chain runs on the top `n - g` bits with groups as its leaf level, hop
stride `k + 3`. Its seat step there moves by the stride, not by 2: above the
leaf an anchor sits two cells before its block's end, but a group's anchor is
its *first* cell. That off-by-a-stride is the one thing that has to change.

The last `g = log2 k` bits are then resolved by a decision tree over the
group, **emitted once after the walk rather than once per group**, so its
`O(k**2)` characters are a constant. Each node reads its bit into `S0`,
raises a flag in `S1`, and runs one of

    [->-<< HIGH >]      >[-<< LOW >>]<<

with each subtree returning to `W` and both scratch cells zero, so the
brackets close on a zero. A leaf steps right to its data cell, adds 48,
prints, clears and steps back -- the program is over, but the brackets above
it still have to read zero.

Cost:

    span   (1 + 3/k)(1 + 1/255) T    one move per cell
    ones                    T/2      one '+' per set entry, capped by the flip
    hops        3/255 of the span
    selector          O(k**2)        once, not per group
                 -----------
                 1.5157 T   as k grows

Taking `k = log T` kills both the `3/k` and the selector, so

    C_F(T) <= 1.516 T + o(T),   limsup D/(T ln T) <= 1.3165 < 1.317 on GRH

against the ungrouped `2.1989`. Measured chars an entry on parity:

    n       T          tree     chain     g=4     g=6     g=8
    16     65,536   17.5138    2.5503  1.7587  1.7710  3.0433
    18    262,144   17.5039    2.5446  1.7163  1.6127  1.9091
    20  1,048,576   17.5011    2.5348  1.7053  1.5727  1.6201

Larger `k` is better asymptotically and worse at small `n`, exactly as the
`O(k**2)` selector says. L7 pins the closed form for `k = 4, 16, 256`, runs
every input of every table at `n = 1..6` for `k = 2, 4, 16` (1134
executions), and samples `n = 9, 10, 12` at `k = 256`.

Of the `1.516`, one unit is the move onto each entry's cell and a half is the
mark on each set entry; nothing else reaches a fiftieth. So the span is the
thing to attack.

## Packing: two entries to a byte

A cell is a byte, and `-` from zero writes 255. Read that as `-1` and the
unary write is no longer monotone in the bit pattern: the four patterns of a
pair can be spelled by any injection into `{-1, 0, 1, 2}`, whose costs are
`{1, 0, 1, 2}`. Pick the injection by frequency -- commonest pattern to `0`,
next two to `+-1`, rarest to `2`. With `f1 >= f2 >= f3 >= f4` the cost is
`f2 + f3 + 2 f4`, which under that ordering peaks when all four are equally
common, so **one character a cell, worst case**. That also subsumes the
complement trick: complementing the table permutes the patterns and leaves
the frequencies alone.

So the span halves and the writes stay at `T/2`, and the two halves of the
old cost trade places:

    span   (1/2)(1 + 3/k)(1 + o(1)) T   one move per cell, k+3 cells for 2k entries
    pairs                      T/2      worst case, one character a cell
    hops           3/255 of the span
    selector             O(k**2)        once, not per group
                    -----------
                    1.0059 T   as k grows

    C_F(T) <= 1.006 T + o(T),   limsup D/(T ln T) <= 0.437 on GRH

(`0.874` with the square-root gap bound applied at every step).

The `(1 + 1/255)` that rode along in the grouped count is gone: each level
adds two cells to a block of `256(k+3)`, and `k` now grows.

Selecting within a cell needs arithmetic, not the static branch the group
tree uses -- but only one branch's worth, because the tree can be made to
*park* rather than print. Each leaf moves its cell's byte onto `W`:

    >^(3+i) [- <^(3+i) + >^(3+i) ] <^(3+i)

The tree's two arms already reunite on `W` with both scratch cells zero, and
none of its brackets tests `W`, so after the tree the pointer sits on `W`
holding the selected byte -- and the decode is emitted **once**, not per
leaf. Raise `W` by one so `v` arrives as `u = v + 1` in `0..3`, read the last
index bit, and switch:

    s_j = >+<[->-< s_(j+1) ]>[-< e_j >]<        s_3 = e_3

Entering the bracket means `u != 0`; the body decrements `u` once and
`s_(j+1)` drives it to zero, so the body runs exactly once and the bracket
closes. `e_j` prints and then clears `W` -- every enclosing bracket has to
retest a zero on the way out.

Worst-case chars an entry:

    n         T          g=5     g=6     g=7     g=8     g=9
    16    65,536      1.1593  1.1564  1.2698  1.7066  3.3773
    20 1,048,576      1.1046  1.0600  1.0449  1.0619  1.1608
    24    1.7e7       1.1021  1.0554  1.0337  1.0205  1.0211
    32    4.3e9       1.1018  1.0550  1.0327  1.0178  1.0119

Parity is cheaper than the bound, since it uses only two of the four
patterns: `0.7949` an entry at `n = 20`, against `1.5727` grouped. L8 pins
the closed form over `n = 2..12` and `k = 2..32`, runs every input of every
table at `n = 1..6` for `k = 1, 2, 4` (1480 executions), and samples
`n = 9, 10, 12` at `k = 128`.

### The packing family bottoms out

`m` entries a cell need `2**m` distinct values, and the cheapest `2**m` of
them cost `2**(2m-2)` characters in total, so the price per entry is

    (1 + 2**(m-2)) / m     m=1: 1.500  m=2: 1.000  m=3: 1.000  m=4: 1.250

Note `m = 1` gives `1.500`, which is the grouped constant less its walk
overhead -- the two cost models agree where they overlap. The minimum is
`1.0`, attained twice, and there is nothing further down this road.

Packing stops at one character an entry because a cell spells its value
alone.

## The enumerative lookup

Spell a whole group of `k = 2**bits` entries as one integer vector of `S`
cells with L1 norm at most `M`.  There are `D(S, M)` of them, the Delannoy
numbers

    D(S, M) = D(S-1, M) + D(S, M-1) + D(S-1, M-1),   D(S, 0) = D(0, M) = 1,

with `D(n, n) = (3 + 2 sqrt 2)**(n - o(n))`.  Rank the vectors position by
position, the values at a position in the order `0, 1, -1, 2, -2, ...`; a
group's `k` bits are one integer `b`, and the group is laid out as
`[W][c_1] ... [c_S]`, a walk cell and the vector of rank `b`, a negative
entry stored as `256 - |v|`.  Drawing a group is `S + 1` moves and at most
`M` marks, so the table costs `(S + 1 + M)/k` an entry, for any `(S, M)` with
`D(S, M) >= 2**k`:

    k = 16    (S, M) = (6, 9)     D = 75,517      1.000 an entry
    k = 32    (12, 16)                            0.906
    k = 64    (25, 28)                            0.844
    limit     1/log2(1 + sqrt 2)                  0.7864

The chain selects the group on the top `n - bits` bits with stride `S + 1`.
The last `bits` are read by a decoder entered on `W`, which re-ranks the
vector to its right by the recurrence and prints the selected bit of the
rank.  Ours is 18,385 characters at `(S, M, k) = (6, 9, 16)`: two-byte
arithmetic, the tables `D(s, m) mod 2**16` spelled into a workspace to the
right of the group -- cells of other groups, which this run does not need
(`tests/proofs/deep/_delannoy_decoder.py`).

The chain's hop at level `j` is `3 B[j-1]` characters of runs, `3T/255` over
all levels -- `Theta(T)`, more than the code saves.  Replace each run by a
scan.  After its anchor pair every block above the groups gets one rail cell
per level, `z_1 .. z_L`, `L = O(log T)`; the rail `z_l` of a level-`l` block
is 1 unless the block is last among its siblings, and every other rail is 0.
A leftward move by one level-`l` block, from its `z_l`: step to the
`z_(l-1)` of its last sub-block, move left by one level-`(l-1)` block, repeat
that move while the cell reached is nonzero, then step to `z_l`.  The loop
runs over the sub-blocks, whose `z_(l-1)` are 1 except on the last, which it
never tests, and on into the parent's left neighbour, whose `z_(l-1)` is 0;
the moves nested inside that last crossing land on the neighbour's lower
rails, 0 too.  The rightward move mirrors this and stops on the last
sub-block, whose `z_(l-1)` is 0.  A level-`l` move is two level-`(l-1)` moves
and `O(L)` characters, so all hops together cost `O(2**L B_1) =
O(T**(1/8) log T)` instead of `3T/255`.

Count: groups `(S + 1 + M) T/k`; the `O(T/(256k))` blocks above them at
`L + 3` cells and at most one mark each; the decoder `O(k**3)`; hops and
chunk reads `o(T)`.  With `k` the largest power of two below `ln**2 T`
everything but the groups is `O(T/ln T)`, so

    C_F(T) <= (1/log2(1 + sqrt 2) + o(1)) T = (0.7865 + o(1)) T.

L10 in `tests/proofs/deep/factor_drawing.py` runs the layout exhaustively at
radix 4, so that four nested scan levels execute (6102 executions with a
tree decoder, 400 with the rank decoder at `k = 8, 16`), pins the emitted
length to the closed form for `n <= 12` at radix 4 and 256, and evaluates
the closed form at `n = 40`, radix 256: `1.002` an entry at `(6, 9, 16)`,
`0.907` at `(12, 16, 32)`, `0.844` at `(25, 28, 64)`, the excess over the
table being the rails.  L11 pins the best `(S, M)` per `k` and the limit.

## Drawing floor

The enumerative lookup is as short as any program of its kind.  Let a family
computing every `T`-bit table be a table-dependent word `X` over `><+-`
followed by one of at most `2**o(T)` decoders.  `X` reads and prints
nothing and leaves cells `0..c` holding `u_0..u_c`, zeros beyond, the
pointer at most `|X|` in; the state and the decoder fix the behaviour.
Reaching the state costs at least `c` moves and
`|u_j| = min(u_j, 256 - u_j)` marks a cell, so `c + sum_j |u_j| <= C`.  For
`0 < z < 1`, `sum_(u mod 256) z**|u| <= (1 + z)/(1 - z)`, so the states of
cost at most `C` number at most

    (C + 1) z**(-C) (1 + z)/(1 - z) sum_c (z (1 + z)/(1 - z))**c,

convergent when `z (1 + z) < 1 - z`, that is `z < sqrt 2 - 1`.  Hence
`2**T <= 2**o(T) K_delta (sqrt 2 - 1 - delta)**(-C)` and some table needs

    |X| >= (1 - o(1)) T / log2(1 + sqrt 2) = 0.7864 T.

Within this model the character constant is exact.  The digit constant is
not quite: a run of length `e` on `q_i` costs `e ln q_i`, less than `e ln T`
for small `i`, and the count with the four drawing letters has exponent
`ln 4`, a digit floor of `1/(2 ln 10) = 0.217` in the model.

## What the bracket says

    floor    1/(log2(1 + lambda) ln 10)   = 0.1505
    ceiling  1/(log2(1 + sqrt 2) ln 10)   = 0.3416   on GRH,  0.3660 unconditional

a ratio of `2.27`.  Number theory no longer separates the two: the walk pays
one logarithm a run, which is what the count charges, and the unconditional
`15/14` is the exponent `1/15` of the best almost-all result in
progressions.  Nor does the tape: a program that carries the table as data
behind a fixed decoder spends `T/log2(1 + sqrt 2)` characters on it, and the
enumerative lookup spends no more.

What is left is a question about Brainfuck.  The behaviours of programs of
`C` characters number between `(1 + sqrt 2)**C`, the tapes a drawing
reaches, and `(1 + lambda)**C`, the reduced words; the floor rises exactly
as far as that count falls.  The ceiling falls only if control flow carries
data denser than a drawing, more than `log2(1 + sqrt 2) = 1.27` bits a
character, where the decision tree carries `1/17.5`.
