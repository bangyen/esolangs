# FRACTRAN: the size wall, and where it stops

The shipped generator emits `Theta(T log T)` characters for a `T`-row truth
table. This document proves that no *row-addressing* program does better --
an unconditional `Omega(m log m)` in the fraction count and
`Omega(k log k)` in the prime count, from distinctness alone -- prices the
escape route that bound leaves open, and states precisely what is still
unproved. Two corrections to earlier prose come out of it, both recorded
below: the packing argument was notation-dependent and false under this
port's own rendering, and the Factor-style behaviour count *cannot* be
imported here, for a reason that is structural rather than a gap in effort.

The conclusion for the audit: FRACTRAN's output-size and generation-time
cells read `Open`, not `Language lower bound`. What is proved is an
obstruction covering every construction anyone has written, pinned by
execution in `tests/proofs/test_fractran_bound.py`, not a bound over every
program in the language.

## Setup

A FRACTRAN program is a starting value `v` and an ordered list of positive
rationals `q_1, ..., q_m`. A step replaces the value `x` by `q_i x` for the
least `i` with `q_i x` an integer; the run ends when no `i` qualifies, and
the value it ends on is the output. Write

- `a_i`, `b_i` for the numerator and denominator of `q_i` as written;
- `m` for the number of fractions and `k = |S|` for the number of distinct
  primes dividing any of `v`, `a_i`, `b_i`;
- `n` for the input count, `T = 2**n` for the table length;
- `D` for the rendered characters, the size the contract measures.

The language has no I/O, so the generator contract embeds: input bit `x_j`
is the exponent of a prime `p_j` in the starting value, the answer is the
halt value, `2` for a one and `1` for a zero. A rendered program is
decimal integers, `/`, and a separator, and this port also parses powers and
products (`2^3*5`, `_product`), so a power costs
`log10 p + log10 e + 1` characters rather than `e log10 p`. Both
renderings are priced below, because the wall differs between them.

## Guards

    Lemma 1. Fraction q_i fires at x if and only if g_i divides x, where
    g_i = b_i / gcd(a_i, b_i).

`q_i x` is an integer exactly when `b_i` divides `a_i x`, that is when
`b_i / gcd(a_i, b_i)` divides `x`. So `g_i` and not `b_i` is the fraction's
guard: `10/4` and `3/4` share a denominator and test different things.

    Lemma 2. If g_i = g_j with i < j, then q_j never fires, from any
    starting value, in any run.

Whenever `g_j` divides the value so does `g_i`, so the least matching index
is at most `i < j`. Dead fractions still cost characters, so the bounds
below are stated for the live ones and only improve when dead ones are
present. Exhaustively: over all ordered pairs with numerators and
denominators at most `6` that share a reduced guard, all 306 leave the second
fraction unfired for every starting value below 2000, while 108 of the 210
pairs sharing a raw denominator with different guards do fire both.

    Corollary 3. The live fractions have pairwise distinct guards, hence
    pairwise distinct rendered tokens.

## What a program can read

    Lemma 4 (observability). Write x = u y with u coprime to S. Then u is
    invariant under every step, and the whole run is a function of the
    exponent vector (e_p(x))_{p in S} alone.

Every guard and every multiplier is supported on `S`, so no step tests or
changes `u`. The consequence is the one that matters for encoding: the
*digits* of a written integer are not data. A `0.3T`-character decimal
constant carries `T` bits to a reader and almost nothing to the machine,
which can only ever see its exponents over `S`. A truth table cannot be
carried as a number.

    Lemma 5 (relabelling). Any injection of S into the primes, applied to v
    and to every q_i, yields a program with an identical run structure and
    the same computed table.

So a prime's identity carries nothing either. Only how many primes there
are, and which role each plays, can be read -- which is why the cost of a
prime is the cost of writing *some* prime of that rank.

    Lemma 6 (monotone guards). Fix two inputs whose runs have fired the
    same fractions for t steps. As a condition on the inputs, "g divides
    the state after t steps" is a conjunction of literals x_j = 1.

The fired product `Q_t` is the same for both, so the states are `v(x) Q_t`
and differ only in the input exponents. For a prime `p` outside the input
set, `e_p(g) <= e_p(v_0 Q_t)` is a condition free of `x`. For an input prime
`p_j` it reads `x_j >= c_j` with `c_j = e_{p_j}(g) - e_{p_j}(v_0 Q_t)`,
which for `x_j` in `{0, 1}` is vacuous when `c_j <= 0`, is `x_j = 1` when
`c_j = 1`, and is unsatisfiable when `c_j >= 2`. So a FRACTRAN program, read
as a Boolean device, is a decision list over monotone conjunctions of the
input bits, and *priority order is its only source of negation*. That is
the shape any construction has to work in, and the shape the open question
below is about.

## The address budget

    Theorem 7. D >= (1 + o(1)) m log_c m, where c is the rendering
    alphabet -- at most 14 symbols here, so D >= (1 + o(1)) m log_14 m.
    In plain fraction notation the sharper D >= log10(m!) holds.

By Corollary 3 the `m` live fractions are distinct strings. There are at
most `c**L` strings of length `L`, so the `m` shortest distinct ones have
total length at least `m log_c m - O(m)`; separators only add. For the
sharper form, each guard divides its written denominator, so
`digits(b_i) >= log10 g_i`, and `m` distinct positive integers give
`sum_i log10 g_i >= log10(m!) = (1 + o(1)) m log10 m`.

    Theorem 8. D >= sum_{p in S} log10 p = (1 + o(1)) k log10 k, in every
    rendering this port accepts.

Every `p` in `S` divides some written integer, or is written as the base of
some power. A plain decimal literal `N` has `log10 N = sum_p e_p log10 p`
digits, at least `sum_{p | N} log10 p`; a power product writes each base
literally. Either way digit cost is additive over distinct primes, so
summing over the text gives the first inequality, and
`sum_{i <= k} log10 p_i = theta(p_k) / ln 10 ~ p_k / ln 10 ~ k log10 k` by
the prime number theorem.

    Corollary 9. m and k are at most (1 + o(1)) D / log10 D. A program
    that gives each of the T rows its own guard, or its own prime, needs
    D = Omega(T log T) characters.

This is the wall, and it is where the earlier prose was pointing: not "the
`T`th prime costs `log10(T log T)` digits" -- true but paid once -- but that
digit cost is *additive*, so `T` addresses cost `T` of those logs however
they are packed into numbers. The shipped tree pays exactly this, and the
floor is not loose for it: measured on the unfoldable table (parity), it
emits `m = 3T + n - 2` fractions over `k = 2T + n` primes with all `m`
guards distinct, and `D / log10(m!)` falls to `3.00` by `n = 12`.

## Closing the packing route

The alternative to `T` addresses is to pack rows into one prime's exponent.

    Lemma 10. In plain fraction notation, exponent e on prime p costs
    e log10 p characters.

A table held as a `T`-bit exponent then costs about `2**T * 0.30`
characters, so packing trades the wrong way -- an exponent of `2**k` carries
`k` bits and costs `2**k` digits. **This is the claim that was previously
stated unconditionally, and it is false under this port's rendering**, which
parses `p^e` in starting values, numerators and denominators alike: there
the same exponent costs `log10 e + log10 p + 1`, so a `T`-bit exponent is
about `0.3T` characters and the size axis does not forbid it at all. What
forbids it is the clock.

    Lemma 11. Let M be the largest exponent appearing in the text. Each
    step changes each e_p by at most M, and the only predicates available on
    e_p are the at most m thresholds e_p(x) >= e_p(g_i). Resolving a datum
    held as one exponent of magnitude E beyond those thresholds therefore
    costs at least (E - max_i e_p(g_i)) / M steps.

Each step multiplies by a single `q_i`, which shifts every exponent by a
fixed bounded amount; Lemma 1 gives the predicates. So a run has to
*traverse* an exponent to read it. Executed: `2^E 3/2^2 1/3` is 14
characters for every `E` tried and runs `E` steps, `16` through `256`. A
table packed as a `T`-bit exponent costs `Omega(2**T / M)` steps, which no
polynomially-bounded run permits, let alone the registry's linear execution
contract. The packing route is closed on the time axis, not on the size
axis -- so the clock has to be part of the hypothesis, and for a size-only
claim it genuinely is not closed.

## Why shared machinery cannot escape

    Theorem 12. For every prime p,
    e_p(h(x)) = e_p(v(x)) + sum_i N_i(x) e_p(q_i), where h(x) is the halt
    value and N_i(x) the number of times q_i fires.

Immediately from `h(x) = v(x) * prod_i q_i**N_i(x)`. Since the contract puts
the answer in `e_2` of the halt value, **the table is an integer linear form
in the firing counts**, weighted by the program's own exponents. Executed
on every row of every sampled table for the shipped generator: the identity
holds exactly.

    Corollary 13. Suppose the trace fires one fraction per level, chosen by
    that level's bit alone -- fraction a_j when x_j = 1 and b_j when
    x_j = 0, plus a fixed tail. Then the computed table is a constant or a
    (possibly negated) dictator, and nothing else.

Theorem 12 gives `e_2(h) = const + sum_j x_j (e_2(a_j) - e_2(b_j))`, an
integer affine form. Requiring it to land in `{0, 1}` on all `2**n` inputs
forces at most one nonzero weight: from `x = 0` the constant is `0` or `1`;
each single-bit input forces every weight into `{-1, 0, 1}` with a sign
matching the constant; and two nonzero weights of that sign are attained
together, giving `2` or `-1`. So an arbitrary table cannot come from
per-level shared machinery. To compute anything but a dictator a program
must either branch at a level on more than that level's bit -- distinct
fractions per distinguished prefix, which Theorem 7 prices -- or fire a
fraction a number of times that varies with the input, which is a loop,
which Lemma 11 prices in steps. Every construction in this repo and in the
FRACTRAN literature takes the first horn.

## What is not proved

    Theorem 14 (floor). D >= T / log2(c) > 0.26 T.

There are `2**T` tables and at most `c**D` texts. That is the whole of what
counting gives, and the reason it gives no more is worth stating, because it
is exactly the asymmetry with Factor. A Factor program is a single integer
whose behaviour, by the analogue of Lemmas 4 and 5, is a function of
exponents indexed by prime *rank*; the number of behaviours of a
`D`-digit program is therefore `exp(O(D / log D))`, which is below `2**T`
until `D = Omega(T log T)`, and the bound is a language bound. A FRACTRAN
program is a *list*, and its order is behaviour: `m` fractions carry
`log2(m!)` bits of priority at `(1 + o(1)) m log_c m` characters, which is
`log2 c` bits per character -- the alphabet's full rate, with no log
damping. The number of behaviours of a `D`-character FRACTRAN program is
`2**Theta(D)`, so **no counting argument can reach `Omega(T log T)` here**.
That is not a gap to be filled by a better count; it closes the route.

What remains open is therefore sharp. An `O(T)`-character family would
have to

- use `m = o(T)` fractions and `k = o(T)` primes (Theorems 7 and 8);
- keep its data out of exponent magnitudes (Lemma 10 in plain notation,
  Lemma 11 under powers plus the execution contract); and
- so decode the table out of priority order alone, as a decision list over
  monotone conjunctions of the input bits (Lemma 6) whose leaf values are
  the linear form of Theorem 12.

Information permits it: `log2(m!) >= T` already at `m = Theta(T / log T)`,
which Theorem 7 prices at `Theta(T)` characters, not `Theta(T log T)`. No
decoder of that shape is known, and nothing above excludes one. A
construction would beat the shipped tree and close the row; a proof that
none exists would be the language lower bound this document does not have.

## Upper bound

The shipped generator is a decision tree with one prime per node, the bits
as exponents in the starting value, and FRACTRAN's first-match rule as the
else-branch. On the unfoldable table it emits

    m = 3T + n - 2  fractions,   k = 2T + n  primes,   D = Theta(T log T),

with pairwise distinct guards, `n + 1` to `2n + 1` steps a run, and a
measured successive-difference ratio of `4.61` against the size contract's
`4.4`. Corollary 9 is attained to within a constant, so the construction is
optimal among row-addressing programs up to that constant, and the measured
super-linearity is the language's arithmetic rather than a slack encoding.

    n     T      D       m      k    D / log10(m!)
    2     4      73      12     10   8.41
    4     16     336     50     36   5.21
    6     64     1477    196    134  4.04
    8     256    6830    774    520  3.59
    10    1024   30803   3080   2058 3.27
    12    4096   134840  12298  8204 3.00
