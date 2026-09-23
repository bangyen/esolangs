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

## Removing GRH

The ingredients are in print, unassembled.  Thorner-Zaman (arXiv:2208.11123,
Thm 1.2) give the explicit log-free density estimate
`N(sigma, Q) <= 10**88 (10**421 Q**99)**(1 - sigma)` for `Q >= 3`,
`sigma >= 39/40`; `Q = max(T, 11)` bounds our ten characters, wastefully.
Kadiri (Mathematika 64 (2018) 445-474) has the explicit zero-free region over
`3 <= q <= 400000`, and `q = 11` has no exceptional zero.  Ingham's argument
turns a density exponent `A` into `theta > 1 - 1/A`, so

    limsup D/(T ln T) <= 35 A / (2 ln 10)

-- checked against both shipped constants: `A = 12/5` (Huxley) is the
ineffective `42/ln 10 = 18.24`, `A = 2` (GRH) is `35/ln 10 = 15.20`.  At
`A = 99` that is `theta = 98/99` and `752.4`.  The constant is not the whole
cost: `10**88` and `10**421` put `x_0` far above `10**11`, so the sieve cannot
bridge to it and the assembled result would be a limsup past an astronomical
arity, not a ceiling at every arity.  The practical range would still rest on
the sieve and GRH.

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

So the missing lemma is narrower than "a uniform bound on the changing residue
word".  Only the *sum* of the `m` gaps is needed, not each one, and since the
walk's step from `p` costs the largest next-prime-in-class gap at `p`, what
would give `Q = Theta(T log T)` is that every reduced class mod 11 meets
`(p, p + C log p]` for almost all `p`, with a crude bound on the exceptional
set.  That is a short-interval statement in progressions, weaker than
Hoheisel per step but not implied by the prime number theorem in progressions.
Measurements are still not that lemma.

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
