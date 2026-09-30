# Factor: size and construction bounds

Worst-case Factor source length for a `T`-bit truth table is
`Theta(T log T)` digits, at the language level and for the generator.  The
upper bound uses a linear Brainfuck program and short prime windows; the
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

Dirichlet proves termination but does not bound the adaptive prime stream:
each run asks for a possibly different residue above the preceding prime.
[Koukoulopoulos, *Primes in short arithmetic progressions*](https://dms.umontreal.ca/~koukoulo/documents/publications/shortaps.pdf),
Int. J. Number Theory 11 (2015), 1499–1521, Theorem 1.3, gives an
unconditional averaged bound strong enough for this stream. For every
fixed `1/15 < beta < 1`, take `h = X**beta` and the theorem's modulus cutoff
11. Its hypotheses hold for sufficiently large `X`: choose
`0 < eps < beta - 1/15`, then `121 <= h/X**(1/15+eps)`.
The theorem bounds all failed `(q, j)` pairs with `q <= 11` and `j <= X`
by `O(X/log(X)**A)`. Thus all but `o(X)` integer starts for modulus 11
have a prime from every reduced residue class in `(j, j+h]`.

Put `X = Q`, the final selected prime, and consider starts `Q/2 <= j < Q`.
There are `Q/2 - o(Q)` complete windows there. For such a start, let `p_i`
be the next selected prime. The encoder chooses the first prime of its
requested class after `p_(i-1) <= j`, so completeness forces
`j < p_i <= j+h`. A selected prime covers at most `ceil(h)` integer
starts. Therefore `m*ceil(h) >= Q/2 - o(Q)`, even for an adversarial
sequence of commands. Since `beta` can decrease to `1/15`, for every
`eta > 0`, uniformly over all command streams,

    Q = O_eta(m**(15/14 + eta)).

This argument requires the first matching prime; arbitrary delayed prime
choices can skip complete windows. `tests/proofs/test_factor_prime_cover.py`
checks the covering implication against the actual greedy encoder, with a
nonempty-window control and a delayed-prime counterexample.

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
established. Table traversal can dominate for a pruned tree.

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
    limsup C_F(n)/(T*n) <= (435/448) log10 2.

The coefficients are 0.10034333 and 0.29229475; neither is claimed sharp.
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

For the upper bound, use the signed-ball block construction in
`tests/proofs/_factor_blocks.py`. For `n >= 5`, split the truth table into
`M = T/32` consecutive 32-bit words. Encode each word's integer rank as
an integer vector of dimension 14 and total absolute value at most 14.
The number of dimension-`a`, budget-`b` vectors is

    F(a,b) = sum_(j=0)^min(a,b) 2**j binom(a,j) binom(b,j).

Choose the `j` nonzero positions, their signs, and positive magnitudes
with total at most `b`; the latter have `binom(b,j)` choices. Thus
`F(14,14) = 7,923,848,253 > 2**32`. Use coordinate order
`0,+1,-1,+2,-2,...` and unrank by subtracting each preceding group's
`F(a-1,b-abs(digit))` count. This is a named enumerative code with exact
binomial counts, not a search over programs or a frozen syntax table.
All ranks below `2**32` have one such vector.

Place a zero control before each block's 14 payload cells. Initialize a
payload with its signed number of pluses or minuses; negative values use
byte wrap. Every block needs at most 14 arithmetic characters. Moving
through the blocks and returning to the last control costs `15M+13`, so
initialization costs at most `29M+13`.

The traveling binary counter in `tests/proofs/_factor_counter.py` reads
the first `w=n-5` inputs, storing their complements as a little-endian
distance from the last block. It decrements a positive counter, recomputes
a nonzero guard, and shifts its bits and guard one control cell left.
Its closing bracket tests the shifted guard, so the next iteration uses
the translated window. Control cells are 15 positions apart; payloads
are crossed but never changed. Ascending transfers leave destinations
zero before their successors move, and scratch is zero after each pass.
After `M-1-row` shifts the counter is zero and its base is at the selected
block. Each shift has positive remaining distance; local moves stay at or
to the right of the base, and the final return stops there. No left-edge
clamp is used. For stride `s`, counting the fixed macros gives

    K_s(0) = 0,
    K_s(w) = 12s*w**2 + (62s+103)w + 7s+14  (w >= 1).

In particular `K_15(w) = 180w**2 + 1033w + 119`. Runtime may traverse
exponentially many blocks, but source contains only one `O(w**2)` pass.
For `n<5`, use the earlier cyclic pair witness; these finite arities do
not affect the leading coefficient.

Move to the selected payload and clear neighboring scratch, since
addressing is complete. A fixed decoder reconstructs its rank in 32 binary
cells. For a coordinate `d` with remaining dimension `a` and budget `b`,
its contribution before descending to the next coordinate is zero if
`d=0`; otherwise it is

    F(a,b) + 2 sum_(k=1)^(abs(d)-1) F(a,b-k)
           + (F(a,b-abs(d)) if d<0 else 0).

Then reduce the budget by `abs(d)`. Adding 14 to a signed payload puts
it in `0..28`; a threshold counter recovers magnitude and sign. A bounded
loop visits the contribution terms, loading their exact binomial counts
into binary addend cells. A ripple adder consumes each rank bit and carry,
preserves the addend, and divides their sum (at most three) by two into
new parity and carry. Every subtotal is nonnegative and at most the final
rank, which is below `2**32`, so discarding overflow is harmless.
All loaded counts satisfy `F(a,b) <= F(13,14) = 3,256,957,317 < 2**32`.
The generated constants are re-derived from the displayed formula.

Read the final five inputs into a byte index `j=0..31`, select rank bit
`31-j`, add 48, and print once. Every input is read in order. The decoder
has fixed source length 147,967, independent of `n` and the truth table.
Consequently

    C <= (29/32)T + K_15(n-5) + 147981
       = (29/32)T + O(n**2)  (n >= 5).

Unranking each fixed-size block and emitting it takes `O(T)` time.
Encode the maximal runs with the same greedy prime-run encoder. The
rendered digits are at most `C log10 Q + O(1)`; complete-window covering
gives `ln Q <= (15/14 + eta) ln C + O_eta(1)` for every `eta > 0`.
Letting `eta` decrease to zero gives
`(29/32)*(15/14)*log10 2 = (435/448)*log10 2`.
Against the lower coefficient `log10(2)/3`, the asymptotic bracket has an
exact `1305/448`-fold gap (2.912946).

Tests exhaust the smaller signed balls through dimension and budget four,
check the counting recurrence through 14, and pin actual source lengths
through twelve inputs. The decoder executes 14 tables on 576 input rows
through Brainfuck, including every row of twelve 32-bit blocks and one
table each at six and seven inputs. All 15 prefix addresses through width
three preserve the stride-15 payloads, clear controls, and avoid clamping.
A real Factor encoding of the five-input table `0xA596B47C` contains
917,061 digits and executes on input `00000`, returning `1`; its decoded
source has 148,010 characters. This is a language-level witness with a
large fixed decoder, separate from the shipped compact-transfer generator.

Executed parity encodings at n=1..5 contain 135, 266, 501, 966, 1883 digits;
all 62 input rows return parity. Their normalized costs 67.5, 33.25,
20.875, 15.09375, 11.76875 are finite measurements, not a lower bound or
an asymptotic limit.
