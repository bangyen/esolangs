# Factor: size and construction bounds

Worst-case Factor source length for a `T`-bit truth table is
`Theta(T log T)` digits, at the language level and for the generator.  The
upper bound is a linear Brainfuck program plus fixed-modulus Hoheisel; the
lower bound counts every integer encoding.

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

## Leading constants

Let `C_F(n)` be the worst-case minimum rendered digits over all `T = 2**n`
tables. The existing witnesses and counting argument can be made explicit:

    (ln 2)**2 / (ln 8 * ln 10) <= liminf C_F(n)/(T*n)
    limsup C_F(n)/(T*n) <= 24 log10 2.

The coefficients are 0.10034333 and 7.22471990; neither is claimed sharp.
For the lower bound put `L = D ln 10` and `r = floor(L/(ln L)**2)`.
The first `r` useful-prime exponents have total at most `L/ln 2`. Counting
positive compositions and eight command choices bounds these prefixes by
`exp(O(r ln(L/r))) = exp(o(L/ln L))`. Every later exponent costs at least
`ln(r+1)`, so their total is at most `N = floor(L/ln(r+1))`.
Merge adjacent equal decoded commands into maximal runs; this only lowers
the weighted exponent cost, since later run ranks decrease. Given a nonempty
prefix, each later command has at most seven choices. For `k` later runs,
positive exponent sequences of total at most `N` number `binom(N,k)`.
Summing `7**k binom(N,k)` gives `8**N`. Programs shorter than `r` runs
are already counted among the prefixes. Thus behaviours number at most
`exp((ln 8 + o(1)) L/ln L)`. Comparing with `2**T` and using the already
proved `C_F(n) = Theta(T ln T)` gives the lower coefficient above.

For the upper bound, use the full decision tree in
`tests/proofs/_factor_print.py`. Read every input, subtract 48 from all but
the last, and initialize an adjacent complement cell to 97 and a constant
output cell to 48. A `01` terminal prints the raw final input; a `10`
terminal uses `[->-<]>.` to print 97 minus it. Constant pairs print the
constant cell, incrementing it only for `11`. Exactly one terminal runs,
so these output cells need not be restored. All earlier branch bits and
flags are consumed, and the program reads exactly `n` lines.

The second fixed variant replaces the final input byte `c` by `97 - c`
and swaps each truth-table pair. Its prelude
`[->-<]>[-<+>]` transfers the reflected byte back and clears the complement
cell; 97 pluses restore it. This costs 111 characters, independently of
`n`, and exchanges the raw and complemented terminal cases.

Prepare every earlier input's zero-branch flag once, before the tree.
For bit `b`, start its adjacent flag at one, subtract `b` while copying it
to a shared scratch cell, then transfer the scratch value back to `b`.
The result is `(b, 1-b)` with scratch zero. Exactly one node at each depth
executes, so this pair is consumed only once along any input path. Every
node can replace its ordinary one-branch prefix `>+<[->->` by `[->>`:
both reach the next input with the active bit cleared and its flag zero,
but the prepared prefix is four characters shorter.

Charge the terminal branches with their connecting moves and average the
two reflection variants. Before this substitution, the depth-two skeleton
costs 12; nonconstant one/zero branches average 8/7, and constant branches
cost at most 9/8. Removing four characters gives
`H_2 <= 12 + 9 + 8 - 4 = 25`. Higher levels previously cost 19 around
two children and now cost 15, so `H_d <= 2 H_(d-1) + 15` and
`H_n <= 10T - 15` for `n >= 2`.

The shared scratch cell is at `2n + 3`. Preparing all `n-1` flags costs
`6n**2 + 34n - 45` characters and leaves the pointer there. Initial setup
costs `12n + 60`, moving into the root costs `2n + 3`, and averaging the
reflection prelude adds `111/2`. The shorter fixed variant therefore has
`C <= 10T + 6n**2 + 48n + 59`. The quadratic setup is `o(T)`;
construction and choosing the shorter source take `O(T)` time.
The emitted Factor integer is obtained with the same prime-run encoder.
Its digits are at most `C log10 Q + O(1)`, with
`ln Q <= (1/(1-theta)) ln C + O(1)` for every fixed `theta > 7/12`.
Letting `theta` decrease to `7/12` gives
`10*(12/5)*log10 2 = 24*log10 2`. Against the lower coefficient
`log10(2)/3`, the asymptotic bracket has an exact 72-fold gap.

Both variants execute through Factor on every table through three inputs
and eleven tables per arity at four through six: 618 programs, 6,704 input
rows. The tests also check the averaged character bound through twelve
inputs. This is a language-level witness, separate from the shipped
compact-transfer generator; its quadratic preparation is paid before any
branch executes.

Executed parity encodings at n=1..5 contain 135, 266, 501, 966, 1883 digits;
all 62 input rows return parity. Their normalized costs 67.5, 33.25,
20.875, 15.09375, 11.76875 are finite measurements, not a lower bound or
an asymptotic limit.
