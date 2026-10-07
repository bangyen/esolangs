# FRACTRAN: whose wall it is

Assigning a separate address to each of a truth table’s `T` rows costs
`Theta(T log T)` characters. Distinctness alone gives the address bounds
`Omega(m log m)` in the fraction count and `Omega(k log k)` in the prime
count. These bounds apply to that construction, not to all FRACTRAN programs.

**FRACTRAN’s Boolean source complexity is `Theta(T)`.** The counting floor is
`D >= T / log2(15) - O(1)` (Theorem 14); the shared decision diagram in
Theorem 15 matches it within a constant. At `n = 12`, the shipped generator
emits `3.90` characters per entry, decreasing with arity, versus `23.6` and
increasing for the prime-per-row tree.

Sharing costs no execution. The diagram gives every distinct subtable one
state, so it names `O(T / log T)` primes, and a run still fires at most a
fraction a level, one for the leaf, and a clear a set input left unread:
`n + 1` fractions on `O(n log n)`-bit values. Both constructions are executed
in `tests/proofs/deep/fractran_shared.py`.

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
decimal integers, `/`, and a separator; templates also carry `$` input
markers. This port also parses powers and
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

Every guard and multiplier is supported on `S`, so no step tests or changes
`u`. A `0.3T`-character decimal constant carries `T` bits to a reader, but the
machine sees only its exponents over `S`, not its decimal digits.

    Lemma 5 (relabelling). Any injection of S into the primes, applied to v
    and to every q_i, yields a program with an identical run structure and
    the same computed table.

Prime identities therefore carry no information beyond their number and
roles; charge the cost of writing some prime of that rank.

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

The `T`th prime's `log10(T log T)`-digit cost is paid once, but distinct
prime costs add: `T` addresses require `T` such charges, however packed.
A prime-per-node tree attains this order. On the unfoldable parity table it
emits `m = 3T + n - 2` fractions over `k = 2T + n` primes with all `m`
guards distinct, and `D / log10(m!)` falls to `3.00` by `n = 12`.

Programs need not address individual rows. Theorem 15 addresses only the
`O(T / log T)` distinct subtables, and pays this same budget for those,
which comes to `Theta(T)`.

## Pricing the packing route

The alternative to `T` addresses is to pack rows into one prime's exponent.

    Lemma 10. In plain fraction notation, exponent e on prime p costs
    e log10 p characters.

A table held as a `T`-bit exponent then costs about `2**T * 0.30`
characters: an exponent of `2**k` carries `k` bits but costs `2**k` digits.
This bound does not apply to the port's `p^e` notation, accepted in starting
values, numerators and denominators: there
the same exponent costs `log10 e + log10 p + 1`, so a `T`-bit exponent is
about `0.3T` characters. Execution cost supplies the remaining constraint.

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
inside the linear execution contract, not outside it. The generator once
shipped exactly that reading, blocks of `w = Theta(n)` entries under a tree;
Theorem 15 needs no packing at all.

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
fractions per distinguished residual table, which Theorem 7 prices -- or fire a
fraction a number of times that varies with the input, which is a loop,
which Lemma 11 prices in steps. Every construction in this repo and in the
FRACTRAN literature takes the first horn.

## The counting floor, and why it is the only one

    Theorem 14 (worst-case floor). If every T-row table has a total
    template of length at most D under the fixed (0,1) input fill, then
    15**(D+1) >= 14*2**T + 1. Thus some table needs
    D >= T / log2(15) - O(1) characters, with no execution restriction.

Normalize decimal digits to ASCII and all token separators to one space;
this preserves semantics without increasing length. The template alphabet
is `0123456789/*^ $`, including the input marker: fifteen symbols. A fixed
fill convention makes each total template compute at most one table. There
are at most `sum_{ell=0}^D 15**ell = (15**(D+1)-1)/14` such texts, including
invalid ones. Covering all `2**T` tables gives the stated inequality. This
is an existential worst-case bound: constant tables can have much shorter
programs. Counting cannot give the
stronger Factor bound here. A Factor program is a single integer
whose behaviour, by the analogue of Lemmas 4 and 5, is a function of
exponents indexed by prime *rank*; the number of behaviours of a
`D`-digit program is therefore `exp(O(D / log D))`, which is below `2**T`
until `D = Omega(T log T)`, and the bound is a language bound. A FRACTRAN
program is a *list*, and its order is behaviour: `m` fractions carry
`log2(m!)` bits of priority at `(1 + o(1)) m log_c m` characters, which is
`log2 c` bits per character -- the alphabet's full rate, with no log
damping. The number of behaviours of a `D`-character FRACTRAN program is
`2**Theta(D)`, so **no counting argument can reach `Omega(T log T)` here**.

The matching construction below makes `Omega(T)` the sharp worst-case
size floor. An `O(T)`-character family must

- use `m = o(T)` fractions and `k = o(T)` primes (Theorems 7 and 8); and
- carry the rest of the table somewhere those do not count it -- priority
  order, exponent magnitude, or the wiring: which state each numerator
  names, `log2 k` bits a fraction.

The shipped construction takes the wiring route: `O(T / log T)` fractions
each name one of `O(T / log T)` states, `Theta(T)` bits in all. The stateful
order construction below also attains linear text. The earlier magnitude
route remains valid; Lemma 11 prices it in steps rather than characters.

## Where the wall stops

    Theorem 15 (shared construction). Every T-row table has a FRACTRAN
    program under the generator contract with

        k <= C + n + 1 primes,  m <= 2C + n fractions,
        C = sum_{d <= n} min(2**d, 2**2**(n-d)) = O(T / log T),
        D = O(T) characters,

    firing at most n + 1 fractions a run on values of O(n log n) bits.

*Construction.* Build the decision tree over the inputs in order, and give
equal subtables at one depth one state prime: a node many prefixes reach is
written once, so the tree becomes a decision diagram. A node whose halves
agree is not written at all: its parent points past it. A node owns two
fractions, `one / (state * p_d)` dividing by its depth's input prime, then
`zero / state` serving as FRACTRAN's own else. A constant subtable is a leaf,
`2 / state` or `1 / state`, and trailing `1 / p` fractions clear the inputs a
path left unread, below a folded leaf or at a skipped node. Only `2` is
reserved: the inputs take the next `n` primes and the states the ones after,
in post-order, root last.

*Correctness.* The value holds exactly one state prime, and every state
fraction's guard is that state times at most one input prime, so only the
current node's fractions can fire, the first exactly when its input is set,
which it consumes. Sharing merges states whose subtables, and so whose every
continuation, agree. The clears come after every state fraction, so they
fire only once the leaf has spent the last state. It is checked by
execution: every row of every table at every arity from one to nine, over
random, constant, parity and half-split tables, in
`tests/proofs/deep/fractran_shared.py` (10,220 rows at the pinned seed) and
in `tests/proofs/test_fractran_bound.py`.

*Cost.* Depth `d` holds at most `2**d` prefixes and at most `2**2**(n-d)`
distinct subtables, so the states number at most `C`. The two terms cross
where `2**(n-d)` is about `d`, and each falls geometrically away from the
crossing, so `C = O(2**d*) = O(T / log T)`. Every fraction names at most
three primes, each `O(log T)` digits by the prime number theorem, so
`D = O(C log T) = O(T)`. A run descends a level a firing, fires its leaf,
and clears each set input it skipped: each depth costs one read or at most
one clear, so a run fires at most `n + 1` fractions. Its value is one state prime and at most `n` input primes,
`O(log T + n log n)` bits.

    Corollary 16 (language size complexity). Let C_n(f) be the minimum
    template length among all total FRACTRAN programs computing f under
    the fixed input and answer contract. Then max_f C_n(f) = Theta(T):
    Omega(T) by Theorem 14, O(T) by Theorem 15. No bound on fractions,
    consultations, state changes, or runtime is assumed.

Measured, at the seed pinned in the deep proof -- characters an entry for
the shipped builder and for the row-addressing tree, and the states built
against `C`:

    n     T       D        D/T     tree      tree/T   states   C
    8     256     1391     5.43    4696      18.34    80       85
    10    1024    4697     4.59    21514     21.01    242      277
    12    4096    15622    3.81    96624     23.59    733      789
    14    16384   54374    3.32    426120    26.01    2298     2325

`D/T` declines while the tree's climbs. A random table builds within 6%
of `C` at `n = 8` and within 1.2% at `n = 14`.

## Size-time frontier

The generator shipped a packed construction before this one: blocks of
`w = Theta(n)` entries carried as one exponent and read by a fixed decoder,
`Theta(T)` text for `O(2**w)` steps, so buying the text constant down cost
exponentially in steps. Sharing removes the trade:

    tree     D = Theta(T log T)   at most 2n + 1 firings   O(n log n)-bit values
    shared   D = Theta(T)         at most n + 1 firings    O(n log n)-bit values

What a firing costs depends on the evaluator. The literal scan has a
counting obstruction (Theorem 16), and the indexed evaluator makes a firing
`O(n)` word operations (Theorem 17).

### Literal-scan execution tradeoff

The cost model matters. A mathematical FRACTRAN transition selects the first
applicable fraction as one step. The literal `_choose` evaluator inspects the list in
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
model, materializing a `b`-bit product
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

### Indexed execution

The numeric scan is not required by FRACTRAN semantics. The interpreter
keeps exact prime-exponent vectors for sources whose bases are at most
`max(256, S)` for source length `S`, factoring them with one sieve to the
largest such base, and falls back to the literal integer evaluator
otherwise; a larger base costs more digits than the source holds.
Numerator and denominator exponents cancel to give the exact reduced guard
and multiplier. Each guard is filed under its largest prime, the most
selective; source indices retain priority. For a bucket whose anchor
exponents decrease in source order, binary search skips impossible
thresholds; otherwise that bucket is scanned in source order. The least
applicable source index over all active buckets and unconditional fractions
is exactly FRACTRAN's first match. No generator recognition or
Boolean-specific semantics are involved. Debug numeric values and fractions
retain their original meaning.

    Theorem 17 (indexed execution). In the indexed evaluator, a run of the
    shipped program costs O(n**2) word operations after loading, and
    loading costs O(S log log S) for the sieve and O(S) to parse.

**Proof.** Every base is a prime at most `p_k`, or a product of two at most
`256`. Every state but the at most `2(n + 1)` constant leaves is spelled at
least three times -- in its two denominators, and in a parent's numerator
or the start -- so `S >= 3 sum_{j <= k} log10 p_j - O(n log T)`, which is
`(3 / ln 10 - o(1)) p_k > p_k`, and the sieve reaches every base. States follow the inputs, so a node's guard
`state * p_d` is filed under the state: a state's bucket holds its own one
or two fractions, and an input's holds its clear. The value carries one
state prime and at most `n` input primes, so a selection inspects `O(n)`
buckets of `O(1)` rules on `O(n log n)`-bit exponent vectors, and a run
makes at most `n + 1` selections and one final failed one. Parsing reads
each character a bounded number of times. QED.

`tests/tools/test_boolean_fractran.py` checks that every generated program
through ten inputs compiles to the index. Executed on six rows of one seeded
dense table per arity, the slowest loaded run stays flat while loading
follows the text:

    n     text      load ms    run ms
    10    4905      2.9        0.038
    12    16122     13.1       0.051
    14    54908     36.2       0.081
    16    210465    135.6      0.165

Before the sieve the index factored bases by trial division under a cap of
`max(256, (log2 S)**2)`, which the shared program's state primes exceed
from four inputs; its literal scan then took `O(T / log T)` inspections a
firing, 4.32 ms a row at `n = 14`.

### Order-only decoding with one priority consultation

Fix a table-independent router, a multiset of `d` distinct fractions,
and a table-independent decoder. The router maps each row to a state;
the first applicable fraction is selected once, and the decoder returns
its bit without consulting the permuted list again. A fixed default
handles rows on which none applies. Permuting this multiset cannot
cover every `T`-row table unless `d >= T-1`.

For each row, form a `d+1`-dimensional signed feature vector: coordinate
`i` is zero when fraction `i` is inapplicable, otherwise `+1` or `-1`
according to the fixed decoder's answer after that fraction. Assign
arbitrary signs to invalid outcomes; total Boolean programs never select
them. The final coordinate is the default answer's sign. Give the rules
weights `2**d, ..., 2`, in priority order, and the default weight one.
The first nonzero coordinate outweighs every later coordinate together,
so the sign of the weighted sum is exactly the program's answer.
This is the dominant-weight encoding used for lexicographic strategies
([Schmitt–Martignon, Theorem 14](https://www.jmlr.org/papers/volume7/schmitt06a/schmitt06a.pdf)).

If `T>d+1`, the row feature vectors have a nonzero linear dependence
`sum alpha_x*v_x=0`. Label each row with nonzero `alpha_x` by its sign.
Any weight vector realizing that labeling strictly would make
`sum alpha_x*(w dot v_x)>0`, contradicting the dependence. Thus even
arbitrary real weights cannot realize every labeling, and neither can
priority weights. Identical fractions have identical applicability and
effects, so extra copies do not increase `d`.

Distinct fraction spellings over a fixed alphabet cost `Omega(d log d)`
characters in total: only `O(c**l)` different tokens have length at most
`l`, so a fixed fraction of `d` tokens must have length `Omega(log d)`.
Consequently this entire one-consultation family has a worst-case text
floor `Omega(T log T)`, even with uniform embeds, arbitrary fixed routing
and prime-power notation. This is not a language floor for FRACTRAN;
multiple consultations change the feature vectors between selections.

The executed control uses positive guards 3/5 and negative guards 7/11,
with the four rows carrying one guard of each sign. All 24 orders of the
same four fractions execute on all rows. Exactly 14 of 16 tables occur;
XOR and XNOR are missing because the four feature rows are dependent.
The eight-fraction independent-pair control realizes all sixteen tables.
Both controls live in `tests/proofs/test_research_tracks.py`.

### Order-only decoding with two priority consultations

Repeating the consultation breaks the one-consultation argument: the second
selection sees a different feature set. A seven-fraction
router executes all sixteen four-row tables for one fixed multiset. Phase 13
is consumed by round one, which also consumes one feature and produces 17;
the run then consults the same priority list again and round two consumes 17
and a remaining feature. Table-independent seeds carry the feature sets
`3*11`, `3*7*11`, `5*7*11`, `5*11`, and the router

    17/39 17/65 17/91 17/143 2/51 2/85 1/187

with cleanup `1/3 1/5 1/7 1/11 1/17` (40 and 21 characters) realizes all
sixteen; every run selects exactly one round-one and one round-two rule. The
control is `test_two_priority_consultations_shatter_a_guard_cycle`.

The escape is bounded. The family spells `m+|S|` fractions over `m`
features and, with a fixed decoder reading only the second selection, no
exhaustive or randomized search up to `m=6` shatters more rows than there
are features. Exhaustion gives 16 of 16 at `m=4,T=4`, 7 of 16 at `m=3,T=4` and
28 of 32 at `m=4,T=5`; randomized search gives 58 of 64 at `m=5,T=6` and 112
of 128 at `m=6,T=7`. The `m`-th prime costs `Theta(log m)` characters, so a
`T=Theta(m)`-row table costs `Theta(m log m)=Theta(T log T)`. The text floor
survives; the linear-dependence obstruction moves from the first selection's
feature vectors to a decoder that reads only the second.

The pair-decoded construction below makes the decoder depend on both
selections. Its arbitrary-row bound closes the dense-row escape.

### Pair-decoded two priority consultations

Giving round one distinct marker primes makes the final value depend on both
selections. With distinct primes `A_f`, `B_g` the router

    round one:  17*A_f/(13*f)   for each feature f
    round two:  B_g/(17*g)      for each feature g
    cleanup:    1/f, 1/17

emits `17*A_f` then `B_g`, so the run ends at `A_{f*}*B_{g*}`. Squaring the
seed features (`13*prod f**2`) lets round two reselect the round-one feature,
so the two selections are independent: `f* = min_S pi1` and `g* = min_S pi2`
for the round-one and round-two block orders. A fixed decoder `h(A_f*B_g)`
reads the pair. The router is `2k` fractions for `k` features.

All orderings of the router, every row run through the interpreter
(`test_pair_decoded_router_reads_both_selections`,
`test_pair_decoded_router_reaches_one_row_per_fraction`):

    k   d=2k   C(k,2)   realized
    3    6       3       8/8
    4    8       6      64/64
    5   10      10    1024/1024
    6   12      15    8192/8192 at T=13; T=14 16096/16384; T=15 30644/32768

Router text is `Theta(k log k)` (2k tokens, primes to `O(k log k)`), and at
`k=6` the realized `T=13` exceeds `d=12`, breaking the one-consultation
`d >= T-1` cap.

The escape is still bounded. The pair map has at most `(k!)**2` entries, so
full shattering of `T` rows needs `2**T <= (k!)**2`, i.e.
`T <= 2 log2(k!) ~ 2k log2(k/e)`. A checked sweep over pair rows gives
`T_max(k) = 3,6,10,13` for `k=3..6`. `T=14,15` at `k=6` are unattained in
long searches but not excluded.

On pair rows the cap is linear, proved. Write `pi1`, `pi2` as generic
points of `R**k`. The selection on row `{u,v}` is the side of the
hyperplane `x_u = x_v`, so one order's selection vector is constant on each
region of an arrangement of `T` central hyperplanes of rank at most `k-1`,
and these regions number at most `R = sum_{i<k} C(T,i) <= (e*T/(k-1))**(k-1)`
(Zaslavsky; the vectors are the graph's acyclic orientations). Every label is
a function of the two selection vectors, so shattering needs `2**T <= R**2`.
With `c = T/(k-1)` this is `c <= 2 log2(e*c)`, so `T <= 9.33*(k-1)`. The
argument depends on row size only through the hyperplane count: rows of at
most `s` features give `T*C(s,2)` hyperplanes and `T = O(k log s)`. A
`Theta(k log k)`-row shattering family therefore needs rows of `k**Omega(1)`
features, where the region bound meets the pigeonhole's `Theta(k log k)` and
separates nothing. The sparse-graph candidate is dead.

The pair cap is attained up to a constant. On disjoint feature blocks the
two orders restrict independently, and an edge row's selections stay inside
its block, so a block-diagonal decoder shatters the union: `T_max(k) >=
13*floor(k/6)`. Hence pair rows give `Theta(k) = Theta(d)` rows and text
`Theta(T log T)`. Controls, executed: the shipped `k=4` and `k=5` decoders
realize 64/64 and 1024/1024; two disjoint `K4` blocks at `k=8` realize
4096/4096 from 576 selection vectors; annealing a 6-by-6 decoder (12,000
evaluations, about 75 s) on `K6` minus two disjoint edges reproduces
8192/8192 from 504 selection vectors, where plain hill-climbing stalled at
7552 and 6856. Each selection-vector count is under its region bound (24 of
42, 120 of 386, 576 of 3302, 504 of 2380). The `T=13` decoder
is pinned with 40 executed order pairs in
`test_pair_decoded_router_shatters_thirteen_rows_at_six_features`.

Dense complements have a separate prefix obstruction. If every row omits
at most `r < k` features, its minimum lies among the first `r+1` features
of either order: otherwise the row would omit all of that prefix. Hence
both selections depend only on two ordered prefixes, giving at most
`(k!/(k-r-1)!)**2` label vectors for every fixed decoder. Shattering requires
`T <= 2 log2(k!/(k-r-1)!) <= 2(r+1) log2 k`. In particular, rows omitting
`o(k)` features cannot shatter `Theta(k log k)` rows. Large row size alone
is insufficient; any candidate must include a row omitting `Omega(k)`
features as well as a row containing `k**Omega(1)` features.

The complement-of-pairs control at `k=6` has fifteen four-feature rows and
exactly 120 selection vectors, determined by the first three features.
Thus every decoder realizes at most 14,400 tables, below 32,768. The known
six-feature decoder realizes 845; on its original thirteen pair rows it
still realizes 8,192 as a positive control. Forty order pairs on all fifteen
dense rows execute through the interpreter (600 runs), checking both
selected markers. These checks are pinned in
`test_pair_router_dense_complements_have_a_prefix_obstruction`.

### Arbitrary rows: the quadratic sign bound

The pair-decoded router cannot shatter `Theta(k log k)` rows, regardless of
row size. Fix any nonempty feature subsets `S_x` and any decoder
`h(i,j) in {-1,+1}`. For two priority orders, assign weights
`u_i = 4**(k-1-rank1(i))` and `v_j = 4**(k-1-rank2(j))`, where rank zero
is first. On a row with selected pair `(a,b)`, geometric tails give

    sum_{i in S_x, i != a} u_i < u_a/3,
    sum_{j in S_x, j != b} v_j < v_b/3.

Consequently all products except `u_a*v_b` sum to less than
`((4/3)**2-1)*u_a*v_b = (7/9)*u_a*v_b`. The selected product dominates
even when every other decoder sign opposes it. Thus the output is exactly

    sign P_x(u,v),   P_x = sum_{i,j in S_x} h(i,j)*u_i*v_j.

Each `P_x` has degree two in `2k` real variables; its coefficients are
fixed by the row and decoder. Allowing arbitrary real weights only enlarges
the class. For `T >= 2k`, Warren's strict-sign theorem bounds its label
vectors by `(4e*T/k)**(2k)` ([Ronyai, Babai and Ganapathy, Theorem
2.2](https://people.cs.uchicago.edu/~laci/papers/zero.pdf)).
This application uses strict signs: the dominance inequality excludes zero
at every priority-weight witness. Shattering therefore requires

    2**T <= (4e*T/k)**(2k).

Put `c=T/(2k)`. Then `2**c <= 8e*c`, which fails for `c >= 8`: at eight,
`256 > 64e`, and `2**c/c` increases thereafter. Hence `T < 16k`; when
`T < 2k` the same bound already holds. Empty rows have a fixed default and
cannot belong to a shattered family. The proof also permits different
fixed applicability sets in the two rounds and row-dependent fixed decoder
signs, since these only change polynomial coefficients.

Together with the disjoint six-feature controls, this gives maximum
shattering size `Theta(k)` for arbitrary rows. A fixed two-selection router
needs `k = Omega(T)` features and `Omega(T log T)` fraction text to cover
every table; the block construction attains that order. This is a bound
for this router family, not for FRACTRAN programs with state-dependent
second-round applicability or more consultations. It uses quadratic
sign-pattern counting rather than a non-counting obstruction, but closes
the proposed dense-row escape.

The executed control checks every pair of four-feature orders on all
fifteen nonempty subsets (8,640 runs). It verifies the selected marker
product, the decoder's quadratic sign, and the decoder-independent
`7/9` remainder bound; its six pair rows still realize all 64 labelings.
See `test_pair_router_is_a_quadratic_sign_family`.

### Stateful order encoding

Repeated, state-dependent consultations attain the full permutation channel:
a fixed multiset with `k + n + 746` fractions computes every `T`-row table
whenever `k! >= 2**T`. Only the order of `k` router fractions depends on the
table. All coefficients, the starting template, input loaders and decoder
are table-independent at fixed `k,n`. Rendered source is
`O(k log k + n**2) + O(1)` characters in the port's power-product notation.
Thus `k = Theta(T/log T)` gives linear text using priority order alone.
This settles the broader order route without extending the pair-decoder
bound beyond its hypotheses.

Choose distinct feature primes `f_0,...,f_{k-1}` outside the fixed control
and input primes. Start with phase `3` and one copy of every feature. Place
these `k` rules in the desired permutation order:

    13*5**(i+1) / (3*f_i).

The selected rule removes its feature and phase `3`, then records digit
`i+1` in register `5`. A fixed nine-rule append routine updates the exponent
`E` of register `7` to `(k+1)*E + i+1` and restores phase `3`. Its three
phases multiply `E` by `k+1` through register `11`, move it back, and add
the digit; separate bridge primes prevent guard cancellation. Each loop
consumes its source counter, so the append terminates. No router rule is
enabled until phase `3` returns. Consequently the router repeatedly selects
the first remaining feature and consumes the whole permutation in order.
After `k` consultations the tenth fixed rule enters the decoder. The final
word is the base-`k+1` number with digits `pi(0)+1,...,pi(k-1)+1`, an
injective encoding of all `k!` orders.

The fixed decoder computes the lexicographic factorial rank. It extracts
the word's digits from right to left. After processing `t` digits, a binary
used-feature mask records that suffix, `F=t!`, and the rank accumulator
contains its completed contributions. For the next digit `d`, count used
features below `d-1` and add their count times `F`. Mark `d-1` used and
advance the factorial. These are precisely the Lehmer-code contributions,
so the result is a bijection onto `0,...,k!-1`. Divide it by two once per
unit of the input-row counter, then take parity. Cleanup leaves exactly
`2**bit`, satisfying the ordinary `1/2` answer contract.

This algorithm is compiled from 259 fixed counter instructions to 736
FRACTRAN fractions. State and bridge registers are separate primes; their
threshold rules are sorted in descending state order. Every active
instruction or bridge enables its own rule before any lower threshold or
cleanup rule. The compilation therefore preserves increment, conditional
decrement and control flow, including backward jumps. Its size is constant
in `k,n`; these counts describe a named construction, not a searched table.
The remaining `n` fractions load the row index from the usual prime-exponent
inputs before the router starts. Their exponent literals cost `O(n**2)`
characters. Feature primes and router digit literals cost `O(k log k)`.

For a table, interpret its entries, low row first, as an integer `R`.
Successive factorial quotients unrank `R` into a permutation; no permutation
search is used. At `n >= 4`, the explicit choice `k=ceil(4T/n)` suffices:
`k! >= (k/2)**(k/2)` and `log2(k/2) >= n+1-log2 n >= n/2` give
`log2(k!) >= T`. For the finitely many smaller arities, `k=T+2` suffices.
The asymptotic source cost is therefore `O(T)`, matching the language floor.

Executed controls in `test_fractran_order.py`: the reader recovers all six
three-feature and 24 four-feature permutations (119 and 134 characters).
The full Boolean programs realize all four two-row and sixteen four-row
tables, executing all 72 rows and checking that their starting templates
and fraction multisets stay identical. Their measured lengths are 11,794
and 11,827 characters, with 750 and 752 fractions. The independent counter
execution checks rank bits for all six and 24 permutations as well.

This is a source-size construction, not a production-generator replacement.
The unary word reader already takes `2**Omega(k log k)` firings; for
`k=Theta(T/log T)` this is exponential in `T`. Factorial unranking and list
deletions have not been shown to take linear generation work either. The
shipped indexed generator supplies the efficient magnitude route. The
streaming construction below avoids the unary word and factorial rank.

### Streaming independent Lehmer digits

The order channel also admits `O(T)` source, `O(T)` generation word work,
and `O(T/log T)` fraction firings per query. The construction uses independent
power-of-two subsets of the Lehmer digits rather than the whole factorial
rank. It has `7k+n+258` fractions; only the order of `k` adjacent selector
pairs depends on the table. Its initial template and fraction multiset
are identical for all tables at fixed `k,n`.

At position `p`, let `m=k-p`, `b_p=floor(log2 m)`, and
`A_p=sum_{q<p} b_q`. Interpret the table block starting at `A_p` as a
little-endian integer `a_p`, padding the last block with zeros. Since
`a_p<2**b_p<=m`, it is a valid rank among the remaining symbols. Select
and delete that symbol. The resulting permutation uniquely encodes the
blocks, with capacity

    S_k = sum_{m=1}^k floor(log2 m)
        = b*k - 2**(b+1) + b + 2,   b=floor(log2 k).

Here `S_k=Theta(k log k)`. For `n>=4`, `k=ceil(4T/n)` suffices:
`S_k >= (k/2)*(log2(k/2)-1) >= (k/2)*(n-log2 n) >= T`.
For smaller arities, `k=3,4,6` supplies `2,4,8` bits respectively.
The zero-input case is covered by `k=2`.

Load the row index `r` into register `107`. Descending threshold rules
select the unique block with `A_p<=r<A_{p+1}`:

    3*23*11**p / (29*107**A_p).

They leave local bit index `j=r-A_p`, prefix counter `p`, ready phase `3`,
and end flag `23`. Each symbol `i` has this adjacent selector pair, placed
in permutation order:

    17 / (3*f_i*11),
    13*5**i / (3*f_i).

While the prefix counter is positive the first rule consumes it and the
first live feature; bridge `3/17` restores ready phase. After exactly `p`
skips, the second rule consumes the target feature and sets countdown `i`.
The live features now represent the suffix. Their count below `i` equals
`a_p`, because removing the selected symbol does not change its rank.

Scan identities `q=0,...,i-1` using phase exponents. For each `q`, put the
live rule before its absent fallback, and order identity thresholds in
descending `q`:

    19**(q+1)*7 / (13**(q+1)*f_q*5),
    19**(q+1)   / (13**(q+1)*5).

Descending bridge rules `13**(q+2)/19**(q+1)` advance the identity. Each
iteration removes one countdown unit and adds one to register `7` exactly
when that feature is live. Induction maintains identity phase `q+1`,
countdown `i-q`, and the count of live identities below `q`. Once the
countdown vanishes, `1/13` clears the phase and `109/23` enters the fixed
bit decoder. All active rules precede final feature cleanup.

The decoder divides `a_p` by two `j` times and takes parity. Its 90 counter
instructions compile to 256 fractions using the same separate state and
bridge registers as the factorial decoder. Cleanup leaves exactly `2**bit`.
The prefix costs `2p` firings, the scan and phase cleanup cost `O(i+1)`,
and unused feature cleanup costs at most `k`. Unary divisions cost
`O(a_p+j+1)=O(k+log k)`: their successively halved arguments sum to less
than `2a_p`. Including at most `n` input-loader firings, a query therefore
uses `O(k+n)` fraction firings. Integer width is `O(T)` bits. This is a
unit-firing bound; guard inspection and integer arithmetic in an evaluator
are additional work.

Rank selection and deletion use a Fenwick tree in `O(k log k)` word
operations. An Euler sieve supplies the feature primes in the same bound,
assigning each composite once. With `c=40+n+k`, its limit is
`4*c*bit_length(c)`: [Rosser and Schoenfeld (1962), (3.13), p. 69](https://doi.org/10.1215/ijm/1255631807)
gives `p_c<c*(ln c+ln ln c)` for `c>=6`, below this limit. Source emission
and table-block parsing also cost `O(k log k+n**2+T)` word operations,
using words of `Theta(log T)` bits. Thus generation takes `O(T)` word
work; this does not claim linear bit complexity. All literals have
`O(log k)` characters except the input exponents, whose total is `O(n**2)`.
Source length is consequently `O(k log k+n**2)+O(1)=O(T)`.

Executed controls cover all 276 tables through three inputs, checking all
2,120 rows, identical initial templates and fraction multisets, and exact
answers. At `k=3,4,6`, measured source lengths are 4,065, 4,175 and 4,379
characters; worst fraction-firing counts are 89, 254 and 265. Seeded tables
at four, six, eight and ten inputs also pass first, interior and last-row
queries. These programs establish the construction, not a production size
improvement: the fixed decoder overhead remains substantial.

### Reference evaluator cost and the shipped generator

Linear generation word work and sublinear fraction counts do not give a
linear evaluator. For the streaming source, the reference indexed evaluator
copies the live prime-exponent tuple into a dictionary on every guard
selection and every state update. All `k` feature primes are eventually
removed, one per firing. Immediately before these removals their counts
are `k,k-1,...,1`, so the updates alone copy at least `k(k+1)/2` entries.
This gives an unconditional `Omega(k**2)` execution word-work lower bound
for every query in this construction on the reference evaluator. It is an implementation bound,
not a FRACTRAN language lower bound.

There are `O(k+n)` firings and `O(k+n)` live factors. Each selection checks
at most `O(k+n)` candidate guards, each of bounded support; each update
sorts at most `O(k+n)` factors. With `k=Theta(T/log T)`, already-compiled
execution therefore takes between `Omega(k**2)` and `O(k**2 log k)` word
work. A straightforward bit-operation upper bound adds `O(log T)` per
word operation. The selection cache avoids repeated scans of the same
state; it does not remove the factor-copy lower bound.

The selector bucket illustrates a separate inspection cost. For the
all-zero table the permutation is the identity. At each prefix skip,
selection starts at the beginning of the ready-phase bucket and tests
the already-deleted features again. Reaching position `p` inspects
`Omega(p**2)` candidates. Choosing the middle block gives `p=Theta(k)`
when `k` is the least sufficient capacity. Executed all-zero controls at
`k=9,23,63,182`, querying block `p=floor(k/2)`, give exactly
`p**2+2p+2` ready-phase inspections, including the target selection. This
positive control rules out reading a small firing count as a small
guard-inspection count.

Executed comparisons use one random table at each arity, seed `20261007`,
the least `k` with `S_k>=T`, and rows `0,T//3,T-1`. Every answer is checked.
Source lengths count the emitted templates in characters. Each cost column
is the maximum over those three queries; maxima need not occur on the same
row. Inspections count indexed candidates, or fractions tested by the
literal fallback. Factor visits sum the live support before each VM
transition, including the final print; they measure state volume rather
than all work in the evaluator.

| n | k | Stream chars | Shipped chars | Stream firings | Shipped firings | Stream inspections | Shipped inspections | Stream factor visits |
|---|---|---|---|---|---|---|---|---|
| 4 | 9 | 4,682 | 215 | 500 | 5 | 8,806 | 183 | 3,515 |
| 6 | 23 | 6,156 | 617 | 650 | 16 | 9,919 | 869 | 9,206 |
| 8 | 63 | 10,354 | 3,154 | 1,120 | 36 | 22,637 | 108 | 34,090 |
| 10 | 182 | 23,739 | 12,164 | 10,767 | 12 | 308,605 | 19 | 357,107 |

The shipped four- and six-input controls use the literal fallback; the
others use indexed evaluation. These controls establish no size or query
advantage for replacing the production generator. The order construction
settles the source and generation route, while the shipped magnitude
construction remains the practical implementation on these measurements.

### Incremental eligibility for dense factor states

The dense-state evaluator avoids the preceding copy and rescan bounds.
It keeps exponents in a mutable dictionary and chooses one anchor prime
per guard: the most frequent guarded prime, breaking ties by smaller
prime. A group contains all guards with the same anchor, sorted by anchor
threshold. Its leaves store the source index of each rule when all
secondary conditions hold, or infinity otherwise. A minimum tree answers
the prefix whose anchor thresholds fit the current exponent. A second
minimum tree selects the earliest eligible rule across all groups and
compares it with the earliest unconditional rule. Thus selection preserves
FRACTRAN's exact first-match priority, including repeated thresholds and
nonmonotone source order.

For each secondary prime, sorted watchers record its thresholds and rule
leaves. Changing an exponent from `a` to `b` updates exactly those watchers
with thresholds in `(min(a,b),max(a,b)]`. Each leaf tracks its number of
failed secondary conditions; it is eligible precisely at zero. After all
changed exponents are applied, refresh only affected groups. Induction on
transitions preserves the exponent dictionary, failure counts, group
minima and global minimum. Separate revision caching preserves repeated
pointer reads without repeating selection. Canonical tuples are produced
only for explicit debug views or snapshots; final integer output is still exact.

Let `F` be firings, `D` changed exponent entries and `H` crossed secondary
watchers. After index compilation and cursor initialization, normal
execution costs `O((F+D+H)*log(m+2))` word operations. Cursor initialization
costs `O((m+G+I)*log(m+2))` for `G` guarded prime occurrences and initial
support `I`. This bound
includes guard maintenance; reporting one selected candidate per firing
alone would omit it.

For the streaming construction, the scan's anchor is phase `13`, because
it occurs in `2k+1` guards versus `2k` for countdown `5`. Its changing
identity thresholds therefore use prefix queries instead of watcher sweeps.
Each feature deletion affects only three secondary leaves. Prefix and
countdown counters cross their repeated threshold once on entry and once
on exit; the query mapping's phase changes once. The fixed decoder adds
bounded dependencies per firing. Hence `D,H=O(k+n+F)`, and `F=O(k+n)`
gives `O(k log k)=O(T)` execution word work. This excludes source parsing,
prime factorization, explicit debug snapshots and integer materialization;
it does not assert linear bit complexity.

Sparse threshold programs can fare worse with eager secondary updates:
the ten-input shipped last-row control needs 296 watcher updates where
the reference selector needs only 14 candidate inspections. Use the cursor
only when `m<=16*max(1,initial_support)`; otherwise keep the reference
selector. All sufficiently large streaming sources meet this criterion,
while the eight- and ten-input shipped controls retain their original path.
This is an implementation choice, not a language restriction.

Executed streaming controls at eight and ten inputs, with the same seed
and rows as above, give the following independent maxima. Exponent updates
count changed entries; watcher updates count crossed secondary conditions.

| n | Firings | Reference inspections | Cursor inspections | Exponent updates | Watcher updates |
|---|---|---|---|---|---|
| 8 | 1,120 | 22,637 | 1,120 | 2,571 | 1,394 |
| 10 | 10,767 | 308,605 | 10,767 | 25,016 | 30,046 |

The before/after corpus has 4,260 executions and 321,470 fraction firings:
all streaming and shipped tables through three inputs, streaming constants,
and wider seeded queries. Complete per-execution hashes of selected
fractions and states agree. An independent literal-arithmetic test also
checks 200 sources with multiple simultaneous threshold crossings for up
to 64 firings each. Normal stepping is tested with canonical snapshot
materialization forbidden. Source lengths and the production comparison
above remain unchanged; this improves the evaluator rather than replacing
the shipped generator.

### Loading and end-to-end bit cost for streamed order

The loader first validates and caches prime-power atoms, retaining the
previous base-admission bound. Let `S` be source characters and `B` the
largest admitted base. When `B<=8S`, an Euler least-prime-factor sieve
runs through `B`, assigning each composite once. Cached factorization
then follows least-prime factors instead of trying candidate divisors.
When `B>8S`, cached trial division remains available. The allocation uses
actual bases rather than the initial product's quadratic admission bound;
its scratch space is always `O(S)` words. No integer prime power is
materialized during index compilation.

For streaming sources, `c=40+n+k` bounds the feature-prime index. The
prime estimate used above gives `B=O(k log k)=O(T)`. The sieve branch is
eventually guaranteed, not assumed: for sufficiently large `k`, `c<=2k`
and `B<4k*ln(2k)`. Each feature base appears five times (initial product,
two selectors, live scan and cleanup), so
`S>=5*floor(k/2)*log10(k/2)`. These inequalities imply `B<=8S` for all
sufficiently large `k`. The finitely many smaller sources do not change
the asymptotic bound.

All generated bases are primes, with `O(k+n)` distinct bases. Their cached
factorizations therefore need one least-prime lookup and division each.
There are `O(k+n)` bounded-support fractions and one `O(k+n)`-support
initial product. Atom conversion, sparse normalization, guard bucketing
and the initial sort cost `O(S+k log k+n**2)=O(T)` word operations.
Together with the `O(B)` sieve and cursor initialization, loading takes
`O(T)` word work. One normal query also takes `O(T)` word work by the
incremental-eligibility bound. Words have `w=Theta(log T)` bits; the
claim uses the same table/index word model as the generation proof.

In a bit-cost RAM with logarithmic addressing, charge a word comparison,
copy or address
`O(w)`, and multiplication or division conservatively `O(w**2)`.
Decimal conversion costs `O(l**2)` for an `l`-digit literal; since the
maximum literal length is `O(w)` and total digits are `O(S)`, conversions
cost `O(S*w)`. Sieve products and cached divisions fit `w` bits, giving
`O(B*w**2)` bit work. The remaining loading and cursor operations fit
`O(T*w**2)` as well. Generation has the same `O(T)` word count and
`w`-bit fields: its prime sieve, Fenwick operations and decimal rendering
also fit `O(T*w**2)`. Final output is only `1` or `2`. Thus generation,
source loading, cursor initialization and one normal query satisfy

    Omega(T) <= end-to-end bit work <= O(T*log(T)**2).

The lower bound is this loader's complete source read, since `S=Theta(T)`;
it is not a language-wide query lower bound. Peak loading scratch is
`O(T log T)` bits, dominated by the sieve; the persistent compiled index
and cursor need `O(k log T+n**2)=O(T)` bits. Explicit debug snapshots or
requests to materialize the large initial integer are outside the normal
query contract. This schoolbook estimate is conservative; the following
amortized bound closes its gap for the materialized pipeline.

Executed loading controls use seeded tables at six through sixteen inputs,
three trials per loader, and first/interior/last-row queries. Every answer
is checked; old and new compiled factors, rules and offsets agree. Counts
below are independent of timing: trial candidates count the reference
factorizer's divisor loop, while sieve assignments count composites; the
sieve additionally visits each integer through `B` once.

| n | k | Source chars | B | Trial candidates | Sieve assignments |
|---|---|---|---|---|---|
| 6 | 23 | 6,156 | 311 | 472 | 246 |
| 8 | 63 | 10,354 | 577 | 1,289 | 470 |
| 10 | 182 | 23,739 | 1,433 | 4,886 | 1,205 |
| 12 | 568 | 69,390 | 4,523 | 25,104 | 3,907 |
| 14 | 1,842 | 230,663 | 16,273 | 150,841 | 14,381 |
| 16 | 6,143 | 798,659 | 61,561 | 975,857 | 55,366 |

Best-of-three index compilation at sixteen inputs measured 0.330 seconds
with trial division and 0.296 seconds with the sieve; cursor initialization
measured 0.085 seconds separately. These timings do not establish an
exponent. The 4,260-execution, 321,470-firing trace corpus also agrees with
the pre-change loader. Literal-arithmetic checks cover bases `1..512`,
and allocation controls verify both a repeated-factor dense product and
the sparse trial fallback. The wider regression executes last-row queries
through sixteen inputs and checks the actual sieve limits.

### Matched bit cost for the materialized pipeline

Generation, loading and one streaming query take `Theta(T log T)` bit
work in the stated bit-cost RAM, using materialized word arrays and
asymmetric Karatsuba multiplication. This is the cost of this pipeline,
not a FRACTRAN language lower bound or a lower bound for other sieve
representations. The linear word-work bounds remain unchanged.

**Arithmetic bound.** Let `a>=b>=1` be operand bit lengths.
[CPython 3.14's integer multiplication](https://github.com/python/cpython/blob/v3.14.0/Objects/longobject.c#L3750)
uses three half-width recursive products above a fixed cutoff. Its balanced
cost is `O(b**alpha)`, `alpha=log2 3`. For unequal operands,
`k_lopsided_mul` splits the larger operand into smaller-width blocks and
combines their products with linear total copying and addition. The cost
is therefore `O(a*b**(alpha-1))`; the fixed schoolbook cutoff changes only
the constant. Since `alpha-1<2/3`, we may use the simpler upper bound
`O(a*b**(2/3))`. For a sieve product, `a=O(log B)`.

**Fractional least-prime moment.** Write `p(v)` for the least prime divisor
of `v>=2`, and `Phi(B,y)` for integers at most `B` with no prime divisor
at most `y`. [Fan (2022), Theorem (4)](https://math.colgate.edu/~integers/w26/w26.pdf)
gives `Phi(B,y)<B/ln y` uniformly for `1<y<=B`.
Let `beta=2/3` and `h(v)=log2 p(v)`. Layer-cake summation gives

    sum_{v=2}^B h(v)**beta
      = beta * integral_0^log2(B) t**(beta-1) * #{v>=2: h(v)>t} dt
      <= B + (beta*B/ln 2) * integral_1^infinity t**(beta-2) dt
      = B * (1 + 2/ln 2).

Because `bit_length(p)<=1+h` and `beta<1`, the ceiling weight satisfies

    sum_{v=2}^B ceil(bit_length(p(v))**(2/3))
      <= B * (3 + 2/ln 2) < 6B.

This bounds all successful Euler products: each composite `v` is produced
once, by multiplying `p(v)` with `v/p(v)`. Both generator and loader now
reject `prime>least[candidate]` before multiplication, so a product either
assigns that composite or is the first product exceeding `B` for its
candidate. No discarded nonleast product is charged.

**Overflow products.** For candidate `c`, the first overflowing prime
satisfies `prime<=2B/c`: if it is `2` this is immediate; otherwise the
previous prime has product at most `B`, and Bertrand's postulate bounds
the next prime by twice its predecessor. Thus its bit length is below
`2+log2(B/c)`. There is at most one overflow per candidate. Concavity and
`sum_{c=1}^B ln(B/c)<=B` give

    sum_c ceil(bit_length(overflow_prime(c))**(2/3))
      < 3B + B*(1/ln 2)**(2/3) < 5B.

The successful and overflowing products therefore have total fractional
weight below `11B`. Their asymmetric multiplication cost is `O(B log B)`;
all other sieve operations have the same upper bound. Early termination
of the generation sieve only removes products from this accounting.

**Remaining stages.** Here `B=O(T)` and `w=Theta(log T)`. Cached prime
factorizations involve `O(k+n)` divisions, even the schoolbook bound for
which is `O(k*w**2+n*w**2)=O(Tw)`. There are `O(k+n)` numeric atoms, with
`O(w)` digits each; parsing and rendering likewise cost `O(Tw)`.
Fenwick selection, sparse normalization, sorting, cursor initialization
and execution use `O(T)` word operations on `w`-bit fields, with only
comparisons, copying, addition, shifts and bounded-support updates apart
from the already charged arithmetic. They also cost `O(Tw)` bits.
Consequently the whole pipeline is `O(T log T)`.

For the matching implementation lower bound, the generator explicitly
initializes `L=4*c*bit_length(c)=Theta(k log k)=Theta(T)` least-prime
word cells. In the materialized-word model, each initialization writes
`Theta(w)` bits, so generation alone costs `Omega(Tw)`. This does not
charge a succinct representation or lazy zero allocation the same way.
It does not rule out a bit-linear alternative pipeline.

The Fenwick selector gives an independent implementation lower bound,
even if sieve initialization becomes lazy or succinct. Cell `j` counts
the interval `j-lowbit(j)+1,...,j`; deleting every symbol updates that
cell exactly `lowbit(j)` times, regardless of deletion order. For
`k=2**b`, the total is

    sum_{j=1}^k lowbit(j) = k + b*k/2.

For arbitrary `k`, retain the largest power-of-two prefix, of length at
least `k/2`, to obtain `Omega(k log k)` updates. Each materialized-word
update costs `Theta(w)` bits in this model, so rank deletion alone costs
`Omega(k log k*w)=Omega(T log T)`. First-rank, last-rank and seeded
deletions at `k=64,256,1024,4096` execute exactly 256, 1,280, 6,144 and
28,672 updates respectively; controls also cover non-power-of-two sizes
and verify every cell's count. A bit-linear alternative therefore needs
to replace this selector or its word representation as well as the sieve.
No lower bound for other order encodings follows from these counts.

A bit-local counter representation remains a possible escape. A cell of
initial count `s=lowbit(j)` decreases through every integer to zero;
its decrements flip exactly `2s-1` bits in total. Summing gives
`2*sum_j lowbit(j)-k`, or `k*(b+1)` for `k=2**b`: only `Theta(T)` flips.
Those power-of-two cells also need just `sum_j bit_length(lowbit(j))
=2k-1` counter bits. The same executed controls check the flip identity
cell by cell. These are storage and bit-change counts, not a running-time
bound: rank comparisons, subtraction, locating packed cells and generating
primes still need accounting. The next construction question is whether
rank selection can use this bit-local representation without reintroducing
the logarithmic factor elsewhere.

**Packed-counter selector control.** `tests/proofs/_fractran_bit_order.py`
implements this local arithmetic with packed counter bits and active-width
metadata. Cell `j` begins at bit offset
`2*(j-1)-popcount(j-1)`, because
`sum_{i=1}^{j-1} v2(i)=(j-1)-popcount(j-1)`. Its reserved width is
`v2(j)+1`, giving `2k-popcount(k)` counter bits. Decrement flips only the
borrow chain; comparison first checks active widths, and subtraction
normalizes the mutable rank's width. Metadata remains in word arrays;
reported counter storage excludes it and the rank buffer.

Controls realize every permutation through six symbols, and first,
last-valid-digit and seeded-valid-digit rank sequences through 4,096
symbols. The packed and reference selectors return the same symbol on
every step. Substitution in the streaming generator gives identical source
and correct executed first/interior/last-row answers for zero, one and
seeded tables at zero, one, two, four, six and eight inputs.
At `k=4,096`, the seeded control reads 47,872 bits in comparisons and
287,704 in subtraction, writes 121,645 rank bits, and reads and writes
53,248 counter bits in decrement. Counter storage is 8,191 bits. The
first-rank control performs no comparison or subtraction bit accesses,
so the mixed-rank controls positively exercise both arithmetic paths.
These counts exclude metadata arithmetic and address computation.

Packing does not change the access schedule. For `k=2**b`, each valid
selection examines the root and all `b` lower levels: the root count is
the number remaining, so a valid rank never advances beyond it. Together
with initialization and deletion, the prototype computes

    k + k*(b+1) + k*(1+b/2) = k*(3+3b/2)

cell locations, or 86,016 at `k=4,096`. Under the stated materialized-word
accounting, paying a full `Theta(log k)`-bit address per cell visit alone
retains `Omega(T log T)` cost. This is a schedule-and-accounting bound,
not a lower bound for amortized local addressing or other selectors.
A bit-linear replacement must also change the access schedule or justify
cheaper addressing, and bound rank arithmetic; packed counters alone do
not close that gap.

Executed arithmetic controls observe the actual sieve multiplications,
checking unique composite assignment and absence of nonleast products.
At `B=61,561`, moving the least-prime guard removes 20,269 unused products:
116,873 become 96,604. The sum of exact integer ceiling weights falls
from 261,788 to 216,359, below `11B`; at generation count 6,199 and
allocation 322,348, its weight is 485,711. Balanced and lopsided integer
multiplication controls at 3,000-by-3,500 and 3,000-by-10,000 bits match
independent all-ones product identities, exercising sizes above the
Karatsuba cutoff. The complete 4,260-execution, 321,470-firing trace corpus
still agrees, and wider output regressions retain the sixteen-input checks.
These controls support the implementation invariants; the asymptotic
bound follows from the arithmetic and rough-number estimates above.

### Direct chunks with exact cleanup

Rank selection is unnecessary if table data may appear in the starting
exponents and cleanup guards. `tests/proofs/_fractran_chunks.py` gives a
named construction under the normal sparse-factor execution contract.
Let `b=max(1,n-bit_length(n))` and `k=ceil(T/b)`. Each consecutive block
of at most `b` table entries gives a little-endian binary value `a_i`.
Initialize feature prime `f_i` with exponent `a_i+1`, alongside the input
primes, mapping flag `29` and decoder constant `103**2`. The extra unit
keeps every feature present even for a zero table.

The input loaders put row `r` in register `107`. Descending mapping rules

    13**(i+1) / (29*107**(b*i))

choose block `i=floor(r/b)` and leave local bit index `j=r-b*i`. For each
`i` in descending order, place its transfer before its exit:

    17**(i+1)*7 / (13**(i+1)*f_i),
    23 / 13**(i+1).

Descending bridges `13**(i+1)/17**(i+1)` restore the selected phase after
each transfer. Priority therefore drains exactly the selected feature
into register `7`, then exits. The shared rule `109/(23*7)` removes its
marker and enters the fixed bit decoder with value `a_i` and index `j`.
Putting the marker guard on every block exit instead would attach `k`
secondary guards to register `7`; the shared rule avoids waking them
during the decoder's repeated divisions. The executed controls retain
exactly four secondary watchers on register `7`.

After decoding, append `1/f_i**(a_i+1)` for every feature. Unselected
features still have their exact initial exponents and disappear in one
firing each; the selected feature is already absent. Every cleanup guard
is positive, including on a zero block, so none becomes an unconditional
`1/1` rule. The halt value is precisely `1` or `2`.

Here `b=Theta(n)`, `k=Theta(T/log T)` and `2**b=O(k)`. Transfer, decoding
and cleanup use `O(k+n)` firings, and the source has exactly
`5k+n+257` fractions. Its literals have `O(n)` digits, apart from the
input-exponent total `O(n**2)`, giving `O(T)` characters. Generation
parses blocks and emits rules directly, with no permutation selector;
the retained prime sieve and rendering still give `O(T)` word work.
Loading has the earlier `O(T)` word bound: each feature base occurs three
times, which already guarantees the actual-base sieve branch eventually.
All sufficiently large sources use the cursor even on a zero table,
because initial support is at least `k+2`.

For cursor execution, phase changes use their frequent primary anchors.
Each feature's secondary live guard crosses once; the mapping flag's
secondary guards cross once, and decoder register watchers are fixed in
number. Hence `D+H=O(k+n+F)` and normal execution has `O(T)` word work.
Generation, loading and execution still fit `O(T log T)` bit work in the
materialized-word model. The retained generation sieve supplies the same
matching lower bound. Removing rank selection therefore removes one
bottleneck, without proving a bit-linear pipeline.

The sparse state occupies `O(T)` bits. The mathematical initial integer
can instead have `Theta(T**2/log T)` bits on an all-one table: feature
exponents are `Theta(T/n)` and their primes have `Theta(n)` bits. This
construction therefore relies on sparse factors; materializing that
integer is outside its bound. It also does not preserve the earlier
table-independent starting value or fraction-multiset invariant.

Executed controls cover all 2,122 queries through three inputs, with 74
independent literal-arithmetic queries through two inputs. Seeded
first/interior/last-row queries execute through sixteen inputs, with
zero- and one-table cleanup controls at eight. At sixteen inputs,
`b=11`, `k=5,958`, the source has 558,000 characters and 30,063 fractions;
the three queries use 84,912, 103,704 and 31,060 firings. These are
construction controls, not a claim that it is the practical generator.

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
language's arithmetic either: it is the price of addressing rows, and
Theorem 15 keeps the short run while addressing only distinct subtables.

    n     T      D       m      k    D / log10(m!)
    2     4      73      12     10   8.41
    4     16     336     50     36   5.21
    6     64     1477    196    134  4.04
    8     256    6830    774    520  3.59
    10    1024   30803   3080   2058 3.27
    12    4096   134840  12298  8204 3.00
