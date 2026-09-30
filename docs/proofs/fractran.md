# FRACTRAN: whose wall it is

A program that gives each of a table's `T` rows its own address needs
`Theta(T log T)` characters. This document proves that -- an unconditional
`Omega(m log m)` in the fraction count and `Omega(k log k)` in the prime
count, from distinctness alone -- and then shows that the language is not
bounded by it, because a program need not address rows. The generator
shipped here does not, and costs `Theta(T)`.

So the headline is a negative one. **FRACTRAN has no `Omega(T log T)`
language lower bound; its boolean size complexity is `Theta(T)`.** The
floor is the counting floor, `D >= T / log2(c) > 0.26 T` (Theorem 14), and
Theorem 15 is within a constant of it. It is also what the generator now
emits: `8.93` characters an entry at `n = 12` and falling, against a
prime-per-row tree's `23.6` and climbing. The `log T` the generator used to
carry was the construction's, not the language's.

What the wall really prices is the clock. A packed program holds `w` table
entries in one exponent, so it buys those characters with a value of
`Theta(2**w)` bits and a run that has to traverse them -- `O(2**w)` steps,
against the tree's `2n + 1` on a value of `O(n log n)` bits. Linearity asks
only `w = Omega(n)`, so `w` is held near `n / 3` and the run stays
a fractional power of `T`; both ends are executed in
`tests/proofs/deep/fractran_packed.py`.

Three corrections to earlier prose come out of this, all recorded below:
the packing argument was notation-dependent and false under this port's own
rendering; the Factor-style behaviour count *cannot* be imported here, for
a reason that is structural rather than a gap in effort; and the address
budget was being read as a statement about the language when it is a
statement about a class of constructions -- a class nothing established was
exhaustive, and which is not.

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
they are packed into numbers. A prime-per-node tree pays exactly this, and the
floor is not loose for it: measured on the unfoldable table (parity), it
emits `m = 3T + n - 2` fractions over `k = 2T + n` primes with all `m`
guards distinct, and `D / log10(m!)` falls to `3.00` by `n = 12`.

Read the hypothesis. It is a wall for programs that address rows, and a
program is under no obligation to address rows: Theorem 15 addresses
`3T / w` of them for a block width `w = Theta(n)`, and pays this same
budget for those, which comes to `Theta(T)`.

## Pricing the packing route

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

Read Lemma 11 the other way and it is a recipe rather than a refutation.
Packing the *whole* table is what costs `2**T` steps; packing `w` entries
costs `Theta(2**w)`, and at `w = Theta(log T)` that is `Theta(T)` steps --
inside the linear execution contract, not outside it. Theorem 15 is
exactly that reading, and it is why the size cell cannot be closed by any
of the work above.

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

## The counting floor, and why it is the only one

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

Counting is therefore the only lower-bound technique available, and it
stops at `Omega(T)`. An `O(T)`-character family would have to

- use `m = o(T)` fractions and `k = o(T)` primes (Theorems 7 and 8); and
- carry the rest of the table somewhere those do not count it -- which
  leaves exactly two places, priority order and exponent magnitude.

The order route is open and unused. The magnitude route is the one taken
below, and it was available all along: Lemma 11 prices a magnitude in
*steps*, and steps are a different axis from characters. This document
previously read that lemma as closing the route. It closes it on the
clock, and the cell it was being used to justify measures text.

## Where the wall stops

    Theorem 15 (packed construction). For every block width w = 2**v <= T
    there is a FRACTRAN program family computing any T-row table under the
    generator contract, with

        m, k = Theta(T / w)  fractions and primes,
        D    = O((T / w) log(T / w)) + T log10(2) + O(n log T)  characters,

    running O(w * 2**w) steps on a value of O(2**w + log T) bits.
    Any w = Omega(n) gives D = Theta(T), and w = O(n) keeps the run
    polylogarithmic in T; the generator takes w near n / 3.

*Construction.* Stop the decision tree `v` levels early. Its `T / w`
leaves are blocks of `w` consecutive table entries, and the high `n - v`
input bits reach the right one exactly as a plain tree does: a node owns
two fractions, the first dividing by the node's input prime, the second
serving as FRACTRAN's own else. A leaf fires

    carry**c * ready / state

where `c` is its block read as a `w`-bit integer, low entry first. That is
`w` bits of table for `log10 c + O(1)` characters, because this port parses
`p^e` (Lemma 10's plain-notation pricing is what would forbid it).

The inputs the tree did not read are the offset inside the block. One
fraction each, `count**(2**(v-r)) / p`, places them in unary as the exponent
of `count`. Their position in the list is the whole argument for them: they
sit *after* the tree's fractions and before the decoder's, and a descending
tree always has a fraction of its own to fire, so they take their turn
exactly once a block is loaded. Put them at the top instead and they would
steal an input the tree still had to read -- which is a mistake this
construction made and the execution check caught.

The decoder is one fixed list of twelve fractions, independent of the
table. It shifts the block right once per unit of the counter -- halving
the exponent by moving two `carry` to one `work`, discarding the bit
shifted out, moving `work` back -- and then answers with the parity of what
is left: `1 / carry**2` casts out pairs and `2 / carry` answers a unit that
remains. Each loop alternates between two state primes, which is what keeps
a guard from being shared; by Lemma 2 a fraction that tried to hold its own
state prime in both numerator and denominator would have that prime cancel
out of its guard and fire everywhere. The last two fractions need no state
prime at all: every earlier state holds a tree state or a phase prime whose
unguarded fraction comes first, so they fire only once the last phase prime
is gone. The trailing `1 / p` clears exist only when a folded leaf leaves
the inputs below it, and the offset, unread: a block's path spends both.

*Two widths.* A power of two is too coarse a setting for `w`: it would
double where the target crossed it, and the characters an entry would saw
between the two settings rather than settle -- measured, that sawtooth
pushes the size contract's difference ratio to `6.19` against its `4.4`,
while the mixture holds every same-parity triple from `n = 6` to `n = 14`
inside `3.93`. So blocks come in both `2**v` and `2**(v+1)`, mixed to
average a target of about `n / 3`. The wider ones stop a level above the
rest, which leaves them one more unread input; the offset fraction carrying
weight `2**v` is exactly that level's, and under a narrow block that prime
is already gone, so the two widths need no marker to tell them apart.

*Small tables.* The decoder's twelve fractions and ten reserved primes are
a constant, and below four inputs they outweigh what blocks save on every
table. So through four inputs the generator also builds the plain tree --
every level read, a leaf per answer, only `2` reserved -- and ships the
shorter text, the tree on a tie. The tree never runs longer: past the
shared levels it spends a step a level and one on its leaf, where a block
spends its load, an offset fraction a level, and the decoder. Over the 256
three-input tables this takes the text from 41,010 characters to 27,842
and the benchmark's steps from 34,314 to 9,592, no table growing on either.
At four inputs the tree ships for 37,984 of the 65,536 tables, taking the
text down 5.0% and the steps 41.7%, again with no table growing; from five
on it is all but never shorter, so it is not built there and the
asymptotics above are untouched.

*Correctness* is the loop invariant that after `j` units are spent the
`carry` exponent is `c >> j`, and the offset is exactly the row's index
inside its block. It is checked by execution rather than asserted: every
row of every table, at every arity from one to nine, over random, constant,
parity and half-split tables, in `tests/proofs/deep/fractran_packed.py`
(10,220 rows at the pinned seed) and in
`tests/proofs/test_fractran_bound.py`.

*Cost.* The tree addresses `T / w` blocks, so Theorems 7 and 8 price it at
`Theta((T/w) log(T/w))` -- the budget is paid, for fewer addresses. The
block literals cost `sum log10 c_j <= (T/w)(w log10 2 + 1)`, which is
`0.302 T + T/w`, and digit additivity (Theorem 8's engine) says no rendering
does better. The decoder is `O(log T)` and the `n` clears `O(n log T)`.
With `w = Omega(n)` the first term is `O(T)`, and

    Corollary 16 (language size complexity). The worst-case rendered size
    of a FRACTRAN boolean program is Theta(T): Omega(T) by Theorem 14,
    O(T) by Theorem 15.

Measured, at the seed pinned in the deep proof -- `m` fractions, `k` primes,
and characters an entry for the shipped builder and for the tree:

    n     T       w    D        D/T     tree      tree/T   m       k
    8     256     2    2217     8.66    4696      18.34    242     246
    9     512     2    4621     9.03    9914      19.36    469     475
    10    1024    2    8892     8.68    21514     21.01    844     851
    11    2048    2    16889    8.25    45429     22.18    1547    1554
    12    4096    4    35900    8.76    96624     23.59    3080    3088
    13    8192    4    69429    8.48    199542    24.36    5657    5666
    14    16384   4    132844   8.11    426120    26.01    10508   10518

`D/T` declines while the tree's climbs, and the successive-difference ratio
sits between `3.50` and `4.28` against the size contract's `4.4` at every
same-parity triple from `n = 6` up -- which is the mixture doing its work,
since a single power-of-two width reads `6.19` there. The `w` column is the
narrow width; about a third of the table sits in blocks of `2w`.

`m` and `k` are `3T / w`, so they are below `T` and fall as `w` grows:
nothing here contradicts the address budget, which is paid in full for the
addresses that exist. At these arities `w` is small and the margin is a
constant factor; it is the `w = Theta(n)` growth that makes the product
`Theta(T)`.

## Size-time frontier

The width is a knob, and what it trades is sharp. Writing `alpha` for the
tree's per-address constant,

    D ~ (0.302 + alpha (n - log2 w) / w) T     characters
    S ~ 4 * 2**w                              steps

so every `w = Omega(n)` gives `D = Theta(T)`, and buying the constant down
by a factor costs exponentially in steps. At `w = Theta(n)` the run is
`2**Theta(n) = T**Theta(1)` -- the shipped width near `n / 3` measures
`T**(1/3)` steps on values of `O(T**(1/3))` bits, so its bit cost is
`O(T**(2/3))`, sublinear, which is why the execution axis stays linear while
the text does too. The two ends built here are

    tree     D = Theta(T log T)   2n + 1 steps          O(log T)-bit values
    packed   D = Theta(T)         Theta(T**(1/3))       O(T**(1/3))-bit values

The fraction-firing version of the joint question has a constructive answer.
The literal-scan bit-work version has a counting obstruction below.

### Shared threshold dictionaries

Let `n = log2 T`, and choose a power-of-two block width `w` with
`n/4 < w <= n/2` for `n >= 2`. Route the high inputs through the ordinary
tree, stopping at blocks of `w` rows. Intern equal block bit strings: there
are at most `2**w <= sqrt(T)` distinct patterns. A block leaf replaces its
state prime by its pattern prime. The low inputs load their offset `r` into
one counter-prime exponent, using one fraction per input.

For each pattern, emit descending threshold guards `pattern * counter**j`
only at bit changes, including `j = 0`. The highest applicable threshold is
exactly the start of the run containing `r`; its numerator is `1` or `2`.
It consumes the pattern prime and `j` counter units. Trailing cleanup
fractions remove the residual offset and unread input primes. Tree rules
precede offset loading, which precedes dispatch and cleanup. Constant leaves
use their own direct answer rule. No pattern is found by search.

The tree has `O(T/w)` nodes; their primes have `O(n)` decimal digits, so
routing costs `O(T)` text. The shared dictionary has at most `2**w * w`
thresholds, each costing `O(n + log w)` characters. Its text is therefore
`O(sqrt(T) * n**2) = o(T)`. Input loading and cleanup add `O(n log n)`.
Thus every table has `O(T)` rendered text. This is a text bound; the prime
sieve's build time has not been proved linear.

A run uses at most `n-v` routing firings, one pattern load, `v = log2 w`
offset loads, one dispatch, `w-1` counter clears, and `n` input clears:
`O(n) = O(log T)` firings. Values have `O(n log n)` bits: each input prime
has polynomial size in `n`, the active state or pattern prime has `O(n)`
bits, and the counter exponent is at most `w-1`. Constant leaves obey the
same bound.

`tests/proofs/deep/fractran_shared.py` executes all tables through three
inputs, then constants, parity, and twelve seeded tables per arity four
through six: 3,800 rows, all correct. Maximum firings by arity are
`2, 3, 4, 6, 7, 8`. Rendered seeded dense-table lengths are:

    n       shared      shipped
    8         1948         2210
    10        7937         9057
    12       34663        35705
    14      149045       132259
    16      342464       512956

Four rows of each wider program and its shipped counterpart were also
executed correctly. At sixteen inputs, the shared sample needed at most
21 firings but 544,733 guard inspections, including the final halt scan.
The three-input aggregate grows from 27,842 to 31,322, so this is a research construction,
not a replacement for the shipped generator.

### Literal-scan execution tradeoff

The cost model matters. A mathematical FRACTRAN transition selects the first
applicable fraction as one step. This port instead inspects the list in
order, materializing `x * a_i` and testing divisibility by `b_i`. Parsing is
excluded. Let `I` be the maximum number of fraction inspections over all
input rows, including the final unsuccessful scan. Let `W` be the maximum
binary width of any initial value or inspected product `x * a_i`. These
parameters describe the loaded numeric machine, independent of whether the
source spells an integer literally or as a product of powers.

    Theorem 16 (inspection-width tradeoff). The number of n-input tables
    computable by total programs with inspection bound I and product-width
    bound W is at most (I + 1) 2**((2I + n + 1)W).

**Proof.** Write the input convention as
`v(x) = v_0 * prod_j p_j**x_j`. For a particular program, let `P` be the
largest initial value or inspected product over all input runs. Totality
makes this maximum finite, and `P < 2**W`.

Every terminating run ends with a full unsuccessful scan, so `m <= I`.
Every numerator satisfies `a_i <= P`: even a never-fired fraction is
inspected during that scan, and the current value is positive. A denominator
`b_i > P` can never divide an inspected positive product. Delete all such
fractions. Induction on the original runs shows that the remaining ordered
list takes exactly the same transitions and halts at exactly the same
values: only failed inspections were removed. The remaining numerators and
denominators are all positive integers below `2**W`.

The all-one input has value `v_0 * prod_j p_j <= P`, so each of the `n + 1`
input components is also below `2**W`. Encode these components and the
ordered numerator-denominator pairs as fixed-width `W`-bit integers. For
fixed remaining length `r <= I`, there are at most
`2**((2r + n + 1)W)` descriptions. Summing over `r = 0, ..., I` gives the
claimed bound. Allowing non-prime input bases and invalid or non-total
descriptions only enlarges it. Fraction order is encoded, not quotiented
away. Source length and coefficient magnitudes before deleting dead
fractions are unrestricted. QED.

Consequently, a family covering all `2**T` tables must satisfy

    (2I + n + 1) W + log2(I + 1) >= T.

Both `I` and `W` cannot be polynomial in `n = log2 T`. This excludes
polylogarithmic inspections together with polylogarithmic explicit integer
bit work, even without a linear-text restriction. In the explicit bit-cost
model used for the packed construction, materializing a `b`-bit product
costs at least `b` bit operations. With any fractions present, the first
inspection already charges the initial width; a zero-fraction program only
returns `1` or `2`, whose output width is charged. If every run has bit work
at most `R`, then
`I <= R` and `W <= R`, hence

    (2R + n + 1) R + log2(R + 1) >= T,

and some table needs `R >= (1 - o(1)) sqrt(T/2)`. This is an existential
worst-case bound, not a claim about every table or every evaluator. An
indexed or factorized implementation has a different cost model; the
unit-cost fraction-firing model already has the shared construction above.

`tests/proofs/test_fractran_bound.py` executes small total programs against
the compacting lemma, checks their answers with the real chooser before and
after deletion, and requires an oversized-guard positive control. A second
finite check includes the zero-fraction projection and the ordered numeric
description count. These checks exercise the proof's semantic premises;
the universal counting inequality is the argument above.

The roadmap question is therefore closed in both cost models: `O(T)` text
and `O(log T)` fraction firings are constructible, while linear-list
inspection with explicit integer bit work cannot be polylogarithmic for
every table.

## The other end: the row-addressing tree

The generator that shipped before this was a decision tree with one prime
per node, the bits
as exponents in the starting value, and FRACTRAN's first-match rule as the
else-branch. On the unfoldable table it emits

    m = 3T + n - 2  fractions,   k = 2T + n  primes,   D = Theta(T log T),

with pairwise distinct guards, `n + 1` to `2n + 1` steps a run, and a
measured successive-difference ratio of `4.61` against the size contract's
`4.4`. Corollary 9 is attained to within a constant, so the construction is
optimal among row-addressing programs up to that constant. Its measured
super-linearity is therefore not slack in the encoding and not the
language's arithmetic either: it is the price of the `2n + 1`-step run,
which is what a row-addressed table buys.

    n     T      D       m      k    D / log10(m!)
    2     4      73      12     10   8.41
    4     16     336     50     36   5.21
    6     64     1477    196    134  4.04
    8     256    6830    774    520  3.59
    10    1024   30803   3080   2058 3.27
    12    4096   134840  12298  8204 3.00
