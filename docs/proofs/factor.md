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

The language lower bound below supplies a table on which every generator must
spend `Omega(T log T)`, so this generated upper bound is tight in the worst
case. This is not a per-table claim: constant subtrees fold and can be much
smaller.

## Generation time

Prime discovery now uses exact segmented Eratosthenes enumeration, not
`isprime`: above `2**64` SymPy's latter is BPSW and is not a proof of
primality, while SymPy's own sieve stores machine words. The local sieve keeps
arbitrary Python integers through `sqrt(Q)`. Segments grow to `sqrt(start)`,
so composite marking costs `O(Q log log Q)`, revisiting base primes costs
`O(Q/log Q)`, and extending them by trial division is smaller. Cold prime
enumeration is therefore `Theta(Q log log Q)` RAM/byte work and `O(sqrt(Q))`
memory; this treats arithmetic on its `O(log Q)`-bit indices as one RAM
operation. Hoheisel makes both polynomial in `T`.

Let `alpha = log_2 3`. CPython's balanced integer products use Karatsuba at
scale, and Python 3.14's large decimal render passes through `_pylong` and
libmpdec. As with Polynomial, a fixed libmpdec eventually exceeds its maximum
direct transform and recurses with three half-size products. The render's top
conversion product has balanced `Theta(D)`-digit operands, hence an
`Omega(D**alpha)` arithmetic term. The encoder combines the two smallest
bit-width products first. Superlinearity charges powers and merges to the
final `D` bits geometrically; CPython's lopsided path splits a large operand
into small-width chunks. Smallest-first merging costs `O(D**alpha)`; rendering
itself supplies the matching `Theta(D**alpha)`, giving the cold bound

    sum_merge cost(a, b) = O((sum_i leaf_bits_i)**alpha).

For the charging lemma, comparable merges spend the increase of the
`alpha`-power potential. A lopsided heap item waits while all smaller items
combine, so it has only one lopsided merge at that scale; its sliced cost
`O(b * a**(alpha - 1))` is at most the final scale's `O(D**alpha)`.

    generation = Theta(T + Q log log Q + D**alpha) = T**O(1).

This is tight in the implementation parameters `Q,D`. Replacing `Q` by
`Theta(T log T)` would assume an unproved
uniform bound on the changing residue word; measurements are not that lemma.

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
