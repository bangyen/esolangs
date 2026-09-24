# Factor: size and construction bounds

Worst-case Factor source length for a `T`-bit truth table is
`Theta(T log T)` digits, at the language level and for the generator.  The
upper bound is a linear Brainfuck program plus fixed-modulus Hoheisel; the
lower bound counts every integer encoding.  Constants are not tracked.

A Factor program is one decimal integer. Factoring it yields an ordered list
of prime powers; a prime's residue mod 11 selects a Brainfuck command and its
exponent is the run length. Put

- `C` for the decoded Brainfuck length, `m` for its maximal runs;
- `Q` for the largest selected prime; and
- `D` for the rendered decimal digits.

For a generated encoding, which has no ignored-residue factors, exactly

    log N = sum_i e_i log p_i,       D = floor(log10 N) + 1.

The Boolean generator emits a Brainfuck decision tree: a fixed 12-character
gadget per internal node, and a leaf at depth `i` costs `O(n - i)` to reach
the result cell and return.  Summed over the tree that is
`C <= 35T/2 + 55n + 25` for `n >= 2` inputs, parity attaining it, so
`C = O(T)` and `m <= C`.

## Generated text

Dirichlet proves termination but does not bound this adaptive prime sequence:
each run asks for a possibly different residue above the preceding prime. The
needed quantitative result is the fixed-modulus Hoheisel theorem (Thorner and
Zaman, Math. Z. 306 (2024), art. 54, Section 1.2: every `h >=
X**(7/12+eps)` works in each reduced class mod a fixed `q`). For each of
the eight classes mod 11 used, some `theta < 1` puts a prime in
`(x, x + x**theta]` for every sufficiently large `x`, and concavity of
`x**(1 - theta)` turns that into `p_i = O(i**(1/(1 - theta)))`. Thus

    p_(i+1) <= p_i + O(p_i**theta),   so Q = m**O(1).

Consequently `log Q = O(log(m + 1))` and

    D = O(C log(m + 1)) = O(T log(T + 1)).

The shipped generator emits a variant of the tree these bounds are stated for.
Digits are `sum(L_i log10 p_i)` over the runs -- weighted by position, since
the primes ascend -- so the shortest brainfuck program is not the cheapest
Factor one, and the `48(n + 1)` characters of ASCII offset are folded into one
multiply loop and one subtracting loop: -38.5% of the digits at `n = 2`, -0.2%
at `n = 13`. An `O(n)` saving against a doubling tree leaves the bound
`D = O(T log T)` untouched, and the folded program is never larger.

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
