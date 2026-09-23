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

### What the bracket says

    floor   1/(3 ln 10) = 0.14476
    ceiling 35/ln 10    = 15.2003   (GRH, Section 4)

a ratio of exactly **105**, in any base. It factors, and the factors say
where to work:

- **52.5x is the decision tree.** There are only `8**l` programs of length
  `l`, so a `T`-bit table needs at least `T/3` instructions. The tree emits
  `35T/2`. That is the whole of `(35/2)/(1/3) = 52.5`.
- **2x is number theory.** The GRH walk pays `ln Q = 2 ln U` per run, because
  a square-root gap squares the last prime; gaps of size `ln p` would pay
  `ln U`.

So the number theory -- the part this paper's Sections 3 and 4 spent -- is
worth at most a factor of 2 more. The order of magnitude is in the
construction, and the next section spends most of it.

### The counting route is nearly exhausted

`ln 8` is not loose. There are `8**l` strings of length `l`, and the adaptive
walk spells any of them with at most `l` runs and largest prime
`O(l**(1/(1-theta)))`, so each costs at most `(1 + o(1)) l ln l/(1 - theta)`.
At least `exp((1 - theta + o(1)) ln 8 * L/ln L)` strings therefore fit in `L`,
so the count is tight up to the factor `1 - theta`, and any argument that
bounds behaviours by counting spellings is capped at

    1/(3(1 - theta) ln 10)  =  0.2895 on GRH,  0.3474 at theta = 7/12.

Still fifty times under the ceiling. Moving the floor further means counting
*behaviours* rather than spellings -- that is, using the fact that many
distinct Brainfuck programs compute the same function. That is a semantic
argument, not a counting one.

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

    C_F(T) <= 1.006 T + o(T),   limsup D/(T ln T) <= 0.8737 on GRH

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

**The bracket is now 6.04x**, factoring as `3.02` construction against `2`
number theory.

### The packing family bottoms out

`m` entries a cell need `2**m` distinct values, and the cheapest `2**m` of
them cost `2**(2m-2)` characters in total, so the price per entry is

    (1 + 2**(m-2)) / m     m=1: 1.500  m=2: 1.000  m=3: 1.000  m=4: 1.250

Note `m = 1` gives `1.500`, which is the grouped constant less its walk
overhead -- the two cost models agree where they overlap. The minimum is
`1.0`, attained twice, and there is nothing further down this road.

What the remaining `3.02` is, stated plainly: the counting floor allows three
bits a character, because a character picks one of eight instructions, and
this construction extracts one. Half its characters step the pointer, which
carries no table data at all; the other half carry two bits between them.
Closing that factor means a layout in which every character is data.
