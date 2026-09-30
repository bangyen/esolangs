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
    limsup C_F(n)/(T*n) <= (45/28) log10 2.

The coefficients are 0.10034333 and 0.48379821; neither is claimed sharp.
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

For the upper bound, use the traveling-counter construction in
`tests/proofs/_factor_counter.py`. Write `M = T/2`, pack each consecutive
pair `(a,b)` as `v = 2a+b`, and choose one global phase `p = 0,1,2,3`.
Store `(v+p) mod 4` as the signed representative in `{-1,0,1,2}`; minus
one is byte 255 on the wrapping tape. Its literal increment/decrement
costs over the four phases are a permutation of `0,1,2,1`, summing to
four. Summed over all pairs, the four phase costs sum to `4M`.
Choose a minimum-cost phase, so payload initialization costs `s <= M`.
This is four linear sums, a named cyclic averaging rule without search.

Initialize odd cell `2j+1` to payload `j`, leaving even controls zero,
and end at control `2M-2`. The fill costs exactly `2M+s = T+s`.
Use `w = n-1` control cells, starting at this last-pair control and
extending rightward, for a little-endian binary counter. Read the first
`w` inputs in order, storing their complements in descending counter
positions. Thus the distance is `M-1-row`, where `row` is the prefix's
binary value. All payloads remain on odd cells, outside the counter.

Three further control cells are scratch; another holds a nonzero guard.
Copy each counter bit to scratch and back to compute the guard as their
logical OR. While the guard is one, decrement the positive counter using
a borrow bit: zero becomes one and propagates borrow; one becomes zero
and clears borrow. A separate next-borrow cell keeps the conditional
closing bracket on zero. Recompute the guard, then transfer the counter
bits and guard one control cell left, in ascending order. Every destination
has been cleared before its successor is shifted, and scratch is zero.
The outer closing bracket tests the shifted guard, so its next iteration
uses the translated window. Payload cells are crossed but never changed.

After exactly `M-1-row` iterations the counter and guard are zero.
The window base is at control `2row`, and moving right reaches the selected
payload. No left-edge clamp is used: each window shift occurs with positive
remaining distance, and movement within the window stays at or to the right
of its base. The final return stops at that base.
For `w=0` the counter code is empty. Each fixed counter pass has `O(w)`
macros spanning `O(w)` cells, independent of runtime iteration count;
its literal source is `O(w**2)`. Input setup, the two guard passes,
decrement, and shift/return cost respectively `6w**2+78w+2`,
`6w**2+30w+5`, `6w**2+30w+7`, `6w**2+75w+3`, and `14w+11`
characters. Their sum is

    K(0) = 0,       K(w) = 24w**2 + 227w + 28  (w >= 1).

Addressing is complete, so neighboring cells can now be cleared as scratch.
Add `4-p` to the signed payload; its value is between zero and six and
congruent to the original `2a+b` modulo four. Divide twice by two using
fixed remainder toggles, retaining the two low bits and discarding overflow.
Read the final input and print the high bit on zero or the low bit on one,
adding 48. Exactly one branch prints, and all inputs are read in order.
This decoder costs `290-p` characters, plus the move to the payload.
Consequently

    C = T + s + K(n-1) + 291-p
      <= (3/2)T + 24n**2 + 179n + 116.

Construction takes `O(T+n**2) = O(T)` time. Encode the maximal runs with
the same greedy prime-run encoder. The rendered digits are at most
`C log10 Q + O(1)`. The complete-window covering bound gives
`ln Q <= (15/14 + eta) ln C + O_eta(1)` for every `eta > 0`.
Letting `eta` decrease to zero gives
`(3/2)*(15/14)*log10 2 = (45/28)*log10 2`.
Against the lower coefficient `log10(2)/3`, the asymptotic bracket has an
exact `135/28`-fold gap (4.821429).

The witness executes through Factor on every table through three inputs
and eleven tables per arity at four through six: 309 programs, 3,352 input
rows. Counter tests check all 63 prefix addresses through six inputs,
payload preservation, cleared controls, and absence of clamped moves.
All 32 phase/payload/final-input combinations execute through Brainfuck;
exact source counts and the phase averaging identity are checked through
twelve inputs. This is a language-level witness, separate from the shipped
compact-transfer generator.

Executed parity encodings at n=1..5 contain 135, 266, 501, 966, 1883 digits;
all 62 input rows return parity. Their normalized costs 67.5, 33.25,
20.875, 15.09375, 11.76875 are finite measurements, not a lower bound or
an asymptotic limit.
