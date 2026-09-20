# Factor: size and construction bounds

A Factor program is one decimal integer. Factoring it yields an ordered list
of prime powers; a prime's residue mod 11 selects a Brainfuck command and its
exponent is the run length. Put

- `C` for the decoded Brainfuck length, `m` for its maximal runs;
- `Q` for the largest selected prime; and
- `D` for the rendered decimal digits.

If run `i` has exponent `e_i` and prime `p_i`, then exactly

    log N = sum_i e_i log p_i,       D = floor(log10 N) + 1.

The Boolean generator has `C = O(T)` and `m <= C`, where `T` is the table
length. Parity leaves its folded tree with `C,m = Theta(T)`.

## Generated text

Dirichlet proves termination but does not bound this adaptive prime sequence:
each run asks for a possibly different residue above the preceding prime. The
needed quantitative result is the fixed-modulus Hoheisel theorem. For each of
the eight reduced classes mod 11, some `theta < 1` puts a prime in
`(x, x + x**theta]` for every sufficiently large `x`. Thus

    p_(i+1) <= p_i + O(p_i**theta),   so Q = m**O(1).

Consequently `log Q = O(log(m + 1))` and

    D = O(C log(m + 1)) = O(T log(T + 1)).

For parity the selected primes are distinct, so
`log N >= log(p_1 ... p_m) >= log(m!) = Omega(T log T)`. The generator's
worst-case output is therefore `Theta(T log T)`. This is not a per-table
claim: constant subtrees fold and can be much smaller.

## Generation time

Prime discovery now uses exact segmented Eratosthenes enumeration, not
`isprime`: above `2**64` SymPy's latter is BPSW and is not a proof of
primality, while SymPy's own sieve stores machine words. The local sieve keeps
arbitrary Python integers through `sqrt(Q)`. With fixed-width segments it
revisits at most `O(sqrt(Q))` base primes per segment, so a cold sieve through
`Q` costs the conservative `O(Q**(3/2))` work and `O(sqrt(Q))` memory.
Hoheisel makes both polynomial in `T`.

Let `alpha = log_2 3`. CPython's balanced integer products use Karatsuba at
scale, and Python 3.14's large decimal render passes through `_pylong` and
libmpdec. As with Polynomial, a fixed libmpdec eventually exceeds its maximum
direct transform and recurses with three half-size products. Dense trees give
the top product and render balanced `Theta(D)`-digit operands, hence an
`Omega(D**alpha)` arithmetic term. Count-balancing can repeat a skewed
`D`-bit multiplication at only `O(log m)` levels, giving the conservative
cold bound

    Omega(T + Q + D**alpha)
      <= generation
      <= O(T + Q**(3/2) + D**2 log(C + 1)) = T**O(1).

This is tight in the implementation parameters `Q,D` up to the stated
arithmetic gap. Replacing `Q` by `Theta(T log T)` would assume an unproved
uniform bound on the changing residue word; measurements are not that lemma.

## Cold parsing

For generated programs, `_factorint` uses the same exact prime stream, bounded
by `Q`, tests each fixed-width chunk with a gcd, and performs `C` successful
prime divisions. Decimal parsing, sieving, gcds and divisions are all
polynomial in `Q,D,C`; with `Q=T**O(1)`, cold parsing and its
`O(sqrt(Q) + D + C)` live storage are polynomial in `T`.

That statement cannot cover arbitrary Factor programs. A balanced `D`-digit
semiprime can force the trial sieve toward `sqrt(N) = 10**Theta(D)`. There is
no polynomial bound in source digits, and no fallback claim is made.

## Language lower bound

Fix a digit count `D`, so `log N = Theta(D)`. If `N` has `m` distinct prime
factors, `log N >= log(m!)`, hence `m = O(D/log D)`. Also
`sum e_i = O(D)`. Positive exponent vectors contribute at most
`binom(O(D), m) = exp(O(D log log D / log D))` possibilities, and residues
contribute `8**m`, which is smaller. Thus only

    exp(O(D log log D / log D)) = 2**o(D)

behaviours have at most `D` digits. Covering all `2**T` Boolean tables forces

    D = Omega(T log T / log log T).

The count covers every encoding: decoding retains only each distinct prime's
residue and exponent. The generated upper and this language lower differ by
one `log log T` factor.
