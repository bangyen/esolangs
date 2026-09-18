# Polynomial: the open scaling row

The one row still open in the roadmap's scaling audit.  Program text is the
expanded coefficient digits of a polynomial whose roots encode instructions.
Everything below is either proved, executed, or a bounded search; what remains
open is exactly one question, stated at the end.  `tests/proofs/test_negatives.py`
executes the claims marked (executed).

## Instruction count is language-forced

The input instruction *overwrites* the register, so between reads every bit
about earlier inputs lives in the cursor alone: just before the k-th read the
reachable configurations number at most twice the instruction count, and a
maximal-width table needs Omega(T/log T) residual classes under every read
order.  Every Polynomial program for such a table carries `m = Omega(T/log T)`
instructions whatever its operands.  The step is sound here where it failed
under Interprogck8: a state is exactly `(register, cursor)`, the input arm
assigns rather than combines, and the instruction list is never rewritten.

## The text is not construction-forced

Negative operands are **legal**: `convert` puts no sign condition on a complex
root's real part, and `f(x) = 1x^6-130x^5+3563x^4+41030x^3+255186x^2+
1107000x^1+4168400` decodes to `[[70, 1], [-5, 1], [0, 1]]` and prints `A`.
A complex instruction `[a, b]` is `(x-a)^2 + p**(2b)`, so its linear
coefficient `-2a` flips sign with `a`.  The older builder-specific argument
(all factors sign-alternating, hence Omega(m^2) digits) had a FALSE premise
at n >= 4, and the current builder abandons the premise outright: it spells
every subtraction as `+=` with a negative operand and every chain park as a
negative operand at `b = 1`, because the digits an instruction costs are
`2b log p` (or `v log p` for a test) and `-=`, `if == 0` and `//=` are
`b = 2`, `v = 4`, `b = 4`.  That is a constant factor -- dense n=8..10
render 2.1x shorter (1.59, 5.02, 16.9 MB) -- and puts the shipped programs
in the sector the right-half-plane theorem below does not cover; their
growth is unchanged in kind (x3.2..3.4 per added input at n=8..10).

Sign freedom is measured near-empty.  On prefixes of the dense n=6 build
(187 instructions), minimising rendered digits over operand sign patterns
(exhaustive to 12 signs, hill-climbing above, one exhaustive minimum missed
by 0.4%) saves at most 5.2%, shrinking with `m` (ratio 0.96 at m=4, 0.998 at
m=40); the fitted growth exponent is 2.35 all-positive vs 2.37 minimised, and
2.12 vs 2.14 with operands replaced by large offsets `|a| ~ 2^10..2^12`.
Why: a factor's squared modulus at `x = iy` is `(q + a^2 - y^2)^2 + 4a^2y^2`,
a function of `a^2`, so `|F(iy)|` is identical under every sign pattern on
the whole imaginary axis (verified in exact integers).  Coordinate descent
over every complex operand -- positive, negative-only (the 90..135-degree
sector), mixed, with and without forced real factors, m <= 16, b = 1, range
twice the prime -- bottoms out at the pure-imaginary build in every class,
negatives buying under 4% with `mass/m^2` rising.  Operands alone do not
bend the growth.

Shipping the product form is not legal: the parser strips `*` and reads
summed `c*x^d` monomials keeping the last coefficient per degree, so
`f(x) = (x-2)(x-3)(x-5)` is silently read as `x - 5` (executed).

## Multiples

Extra roots that match no instruction code multiply the mandatory product
without changing execution (executed): `P*(x^2+x+1)` and `P*(x-6)` decode to
the base program and run identically on the `'A'` printer and on
`polynomial("0110")`; the control `P*(x-2)`, whose root is code `2**1`,
decodes differently and dies.  A multiple is legal exactly when every
cofactor root dodges the instruction encodings.

**Term floor, language-level.**  No two-term multiple: `x^N - D` vanishing
on `a + p**b i` forces a rational angle, Niven pins `a` to 0 or `p**b`, and
two factors would need `2*p1**(2*b1) = 2*p2**(2*b2)`.  Descartes: a `t`-term
real polynomial has at most `t-1` positive roots, so every multiple of a
product with `m_r` real instruction roots `p**v` has `t >= m_r + 1`.  Real
instructions cannot be shed -- the routing lemma is a proof: after a read the
future is a function of position alone, a bracket-free segment reaches one
destination for both bit values, so `N'(k+1) <= 2B + E(k)`, i.e.
`B >= (N'(k+1) - E(k))/2` at every level (`N'` non-constant subfunctions per
level, `E` those with equal halves).  Executed on machine- and tree-shaped
builds at n=3..5 over every input; the floor on the dense fixture runs 16,
52, 128 at n=8, 10, 12, 0.38..0.53 of `T/log2 T`.  The shipped machines put
the real share at 0.36 of the instruction list.  A loop changes
nothing: entries 7 and 10 leave `while (reg > 0) reg -= 3` in identical
state, so an exit on the register merges a residue class rather than storing
it.  Hence every multiple of every dense-table program carries
`Omega(T/log T)` monomials, `Omega(T)` characters.  Matching, not
separating: spelling `t` exponents costs `Omega(t log t)`, so O(T) text
forces `t = O(T/log T)` and the multiple the row needs has
`t = Theta(T/log T)`.

**Coefficient mass, right half-plane: `Omega(T^2/log T)`.**  If every root
has nonnegative real part, `x -> -x` makes every factor's coefficients
nonnegative (`(x-r) -> -(x+r)`; `(x-a)^2+q -> x^2+2ax+(a^2+q)`), products
cannot cancel, and `|[x^k] F| >= (prod of constants) / (c_1 ... c_k)` for
the `k` smallest linear constants (checked coefficientwise in integers on
emitted artifacts and executed right-half-plane multiples).  Summing
`k = 0..L` gives `(L+1) M / 2` digit mass, with `L = Omega(T/log T)` linears
by the routing floor and `M = Omega(m_r log m_r)` from the distinct primes.
A compensation lemma covered the previous builder's `a = -1..-3` operands: a
flipped `x^2 - 2bx + c` times an unused `x^2 + 2b'x + c'` is coefficientwise
nonnegative iff `b' >= b`, `c + c' >= 4bb'`, `b'c >= bc'` (middles at most 6
against constants at least 65; matching found and verified per build).  The
current builder's parks are negative operands in every block, so its
programs are not covered by this theorem; the bound is about the language.
Positivity forces every low coefficient at once, which Mahler measure, the
primorial, and Newton polygons -- norms one heavy coefficient absorbs -- do
not.  The hypothesis is load-bearing: `(x-2)(x-3)(x+2)(x+3) = x^4 - 13x^2 +
36` has `[x^1] = 0` where the floor demands 18.

**The primorial bound is linear.**  The lowest nonzero coefficient is
divisible by the primorial of `m`, `Omega(m log m)` digits; with
`m = T/log2 T` the forced digits over `T` run 0.153, 0.180, 0.198, 0.206,
0.220, ... 0.267 at n=6..20, toward `ln 2 / ln 10 = 0.301`.  Matching only;
cannot be promoted.

**Compensation cannot be forced from the semantics** (executed).  `[-c, 1]`
is `[c, 2]`, but `[-c, 3]` (reg *= -c) matches no nonnegative-operand map,
and a bracket that never fires guards dead code, so a program can carry
arbitrarily many negative operands against the routing floor's linears.  The
positivity method stops at the sector boundary.

**Exact-magnitude mirrors are mass-negative.**  One negated partner
`x + p**v` per real root (legal: `convert` reads real roots only as positive
prime powers; executed on a five-instruction printer) zeroes every odd
coefficient of the realified part while survivors roughly square: total
digits x1.51..1.58 on dense n=3..6, strictly monotone in partners added,
24/24 at n=4.  A working left-half-plane cofactor needs inexact magnitude
relations.

**The Descartes-minimal class is `Omega(T^2/log^2 T)` on the whole plane.**
Let a multiple `F` of a program with `L` real roots `x_1 > ... > x_L >= 2`
carry exactly `L + 1` terms at exponents `0 = c_0 < ... < c_L`.  Its
coefficients are forced up to one integer: `f_j = ±D_j / g`, `D_j` the
maximal minor of the root Vandermonde on the other `L` exponents (positive
by total positivity), `g` a common divisor, so `g <= min D` and
`mass(F) >= sum_j log(D_j / min D)` with no gcd control.  Deleting the `j`-th
exponent instead of the `(j+1)`-th adds `c_{j+1} - c_j` boxes to one row of
the minor's Schur shape, and the gain is bounded sharply:
`s_{mu + d e_rho}(x) * h_d(1/x_1, ..., 1/x_rho) >= s_mu(x)` for the `rho`
largest roots (branch on one variable; shapes failing the tightened
condition inject into those passing it; induct on the row).  Equality at the
column shape; the plain Pieri form `s_{mu + e_rho} >= r_rho s_mu` is false
once the reciprocal-root sum passes 1, which the first five primes do.  A row
with reciprocal-root sum at most 1/2 gains at least `ln 2` per box; a row
loses at most twice its reciprocal sum (Mertens product `prod (1-1/x)^-1`).
For powers of distinct primes the lossy rows number `L^0.61` and the sum
never exceeds `ln ln L + 1`, so `mass(F) >= (ln 2 / 2 - o(1)) L^2` nats, and
with `L = Omega(T/log T)` every `(L+1)`-term multiple of every dense-table
program is `Omega(T^2 / log^2 T)`, for every cofactor and operand sign.
Checked in exact integers on every support to degree 12..20 for two to six
prime powers: never above the true mass, tight in every box step, minimised
at the dense support `P`, where it reads 0.75..0.83 of `sum_i i log r_(i)`.

**LLL is blind** (bounded searches).  The multiples with cofactor degree
`<= k` are the lattice of shifts `x^i * P`; on prefixes to degree 40 with
`k` to the degree, reduction at `delta = 0.75` returns `±x^i * P` unchanged.
Rescaling column `j` by `2^(s0 - s_j)` to hunt the one-heavy-bottom profile
a linear program must have returns gain 1.000 or worse over cofactor degree
to 8; unstable cases (sympy's LLL on very wide entries) are reported as
unsearched.  Bounded by prefix size, cofactor degree, and envelope family.

**The modulus route fails.**  `x^3 - 7x + 6 = (x-1)(x-2)(x+3)` has three
terms and three distinct moduli; `x^N - 1` puts `N` roots on one circle from
two terms.  Sparsity bounds positive real roots (Descartes), not complex
moduli.

**Root-set term bounds do not map.**  Every bound on the term count of a
polynomial from a set it must vanish on -- Descartes on either real ray
(`x -> -x` counts the *cofactor's* negative roots, which the constructor
chooses), Khovanskii-type sector bounds, Lenstra's and Filaseta--Granville
--Schinzel's bounds on roots of unity of lacunary polynomials, the BCH /
Hartmann--Tzeng / van Lint--Wilson bounds on cyclic-code weight, and Tao's
`|supp f| + |supp f^| >= p + 1` for `Z/p` -- needs the forced roots on a
ray, a circle, or among the `N`-th roots of unity.  The forced roots are
positive prime powers and `a +- p**b i` with arbitrary integer `a`: on no
common circle or line through the origin, and the interpreter reduces
modulo nothing, so cyclotomic factors are the constructor's to add, never
required.  What remains of these is Descartes on the positive ray, `t >= L +
1`, and that count is compatible with `O(T)` text.  Plaisted's NP-hardness
of deciding sparse multiples is about the general instance, not a bound on
this family.  (Executed lower bound none; this paragraph is the mapping.)

**The tail is a primorial fraction** (executed).  Write a multiple with
`0` in its support as `f_0 + S(x)`; `S` takes one value at every real root
and `f_0` is minus that value.  Minimising the largest non-constant
coefficient over every `S` of degree `<= D` (z3, exact) gives, for the first
`L` primes: `L = 3`, floor 13 at every `D` from 6 to 16 (primorial 30);
`L = 4`, 82 at `D = 6..8` and 80 at `D = 10..16` (210); `L = 5`, 1234, 966,
855, 844 at `D = 7, 9, 11, 13` (2310).  LLL on the same lattice (reduced
basis, not exact) reaches 9972 at `L = 6, D = 18..22` (30030) and 187999
at `L = 7, D = 24` (510510).  The floor sits at `0.33..0.43` of the
primorial and stops falling once `D` passes about `2L`; the greedy multiple
(choose each cofactor coefficient to keep the running coefficient inside
`(-primorial/2, primorial/2]`) shows `1/2` is always reachable.  So the
profile "one primorial-sized coefficient, every other one polynomial" has
no member at any searched size, and a second coefficient at a constant
fraction of the primorial is the measured floor -- still `Theta(T)` digits,
so matching, not separating.  `tests/proofs/test_negatives.py` re-derives
the `L = 3, 4` floors at `D = 8`.

**Few large coefficients exist only with a dense tiny part** (executed).
Allowing `K` non-constant coefficients past `B` and the rest at most `B`:
`L = 3, B = 5` admits `K = 1` from `D = 6` on; `L = 4` admits `K = 1` at
`B = 49` from `D = 6` and `K = 2` at `B = 7` from `D = 8`, but no `K = 1`
at `B = 7` through `D = 24`; `L = 5` admits neither `K = 1` at `B = 11` or
`121` nor `K = 2` at `B = 11` through `D = 24`, and `L = 6` none of `K = 1`
at `13` or `169`, `K = 2` at `13` through `D = 26` (z3, every degree
proved).  The least `K` at `B = p_L**2` over `D` up to `18..20` is 1, 1,
2, 3 at `L = 3..6`, and every witness puts its large coefficients at the
lowest degrees, nearly proportional to the product of the smallest `K`
root factors (`L = 6, D = 20`: `f_0 : f_1 : f_2 : f_3` within 0.7% of
`(x-2)(x-3)(x-5)` scaled), so the large part grows with `L` and the tiny
part is left to absorb the large roots.  Where the profile exists, the
large coefficients are `~2**D` (`3540 - 1012x^2 + ...` at `L = 3, D = 8`,
the rest at most 5; `f_0 ~ 3 * 10**16` at `L = 6, D = 20`) and the tiny
part occupies every degree, so its text is `D log D` -- at `D >= L log2 L`
that is `T log T`, not `T`, and at `D ~ 3L` the `K ~ L/2` large
coefficients of `D` bits each are `L**2` on their own.  Exact minimum text
mass over every multiple of `(x-2)(x-3)(x-5)` of degree `<= 8` is the
product's own 11 digits (z3 optimise, 145 s); larger sizes did not finish.

**The sparse-remainder profile: the chain, one lemma, and the executed
minima.**  Write the profile as `F = G + tau`, `G` the `K + 1` lowest
coefficients (unbounded), `tau` supported above degree `K` with `t` terms
each at most `B`.  Real roots only: a multiple of the full product is a
multiple of `prod (x - p_i)`, so its bound is a bound.  The chain: with
support `s_0 < ... < s_{t-1}` and gaps `g_j = s_j - s_{j-1}`, `F(r) = 0
mod r**k` for every `k` gives, step by step, `G(r) = 0 mod r**s_0` and
`tau_{s_j} = -(G(r) + sum_{l<j} tau_{s_l} r**s_l) / r**s_j mod r**g_{j+1}`
for every root `r` at once, so each `tau_{s_j}` is a CRT residue mod
`primorial**g_{j+1}` fixed by `G` and the terms below it, and the top
carry must vanish exactly.  This is `F(r) = 0` rewritten, not a new
constraint: the residues are functions of `G`, and whether `K + 1`
integers can steer `t` residues into `[-B, B]` is the Diophantine question
itself.  Counting bits -- `sum log(2|g_k|+1) + t log(2B+1)` of freedom
against `(D - s_0) log primorial` of residue -- is the Gaussian heuristic
again; every witness below satisfies it with margin (`L = 6, D = 20`: 356
against 238 bits), as a heuristic must, and it proves nothing.  What does
prove: eliminate `G` by a `(K+1)`-th divided difference over any `K + 2`
roots `I`, `sum_j tau_j h_{j-K-1}(r_I) = 0` with `h` the complete
homogeneous symmetric polynomials, `h_{m+1} >= rho h_m` for `rho = max
r_I`, so the top term needs `|tau_top| h_m <= B sum_{m' < m} h_{m'} <= B
h_m / (rho - 1)`: **every remainder above `K <= L - 2` unbounded low
coefficients has a coefficient of at least `p_L - 1`.**  Tight: `L = 5, K
= 3, D = 18` is unsat at `B = 10` and sat at `B = 11`; `L = 6, K = 4` unsat
at 12.  That is `Omega(log T)` digits per remainder term, the profile's
own allowance, and nothing on `t`.  Executed minima of `t` (z3, 120 s
alarm per instance): at `B = p_L**2` the least `t` is reached by the
product itself or a cofactor of degree `<= 6` (`L = 3..5` with `K = L -
2`: `t = 2`; `L = 5, K = 2`: 5; `L = 6, K = 3`: 9 at `D = 20`, unknown at
6), because `P`'s own top coefficients are under `p_L**2` at these sizes;
`K = L - 1` is the `(L+1)`-term class (`x**D mod P`, `t = 1`, `G` of
`L * D` digits).  At `B = p_L`: `L = 5, K = 3` needs `t = 7` (degree 11,
`G ~ 10**9`); `L = 6, K = 3` has **no** multiple through `D = 26` for any
`t`, `K = 2` none through 26, `K = 4` unknown at `t = 8`.  The size reading:
digits are `sum log|g_k| + t (log B + log D)`; the lemma gives `t log L`,
the chain's count would give `0.3 (D - K) L log2 L` -- quadratic, the
product's order -- if it were a theorem, and it is not.  Bound on this
profile only; not a language lower bound.  `tests/proofs/test_negatives.py`
pins the lemma's threshold and the `L = 6, K = 3, B = 13` negative.

**The iterated elimination: `prod (p_i - 1)` over the largest primes.**  The
`p_L - 1` lemma is one row of a linear program, and the program's own
certificate is much stronger.  With real roots `r_1 < ... < r_L` and the
unbounded positions `U`, every constraint on the bounded coefficients is
`sum_m f_m w_m = 0` for a sequence `w_m = sum_i c_i r_i**m` with `w_m = 0`
on `U` (the coefficients of `Lambda(x) / prod (1 - r_i x)`, `deg Lambda <=
L - 1`, `Lambda` vanishing on `U`); for `U = {0..K}` the divided-difference
rows are the members with `c` supported on `K + 2` roots.  A multiple of
degree `D` has `|f_D| >= 1`, so if some `w` has `|w_D| > B * sum_{m not in U,
m < D} |w_m|` then some bounded coefficient exceeds `B`.  Read backwards
from the top, `u_d = w_{D-d} = sum_i a_i r_i**-d`.  Take `a` on the `c =
L - K - 1` largest roots `rho_1..rho_c` with `u_0 = 1`, `u_1 = ... =
u_{c-1} = 0`: the generating function is `1 - (-x)**c / (prod rho_i *
prod (1 - x/rho_i))`, so `u_d = -(-1)**c h_{d-c}(1/rho) / prod rho_i`
for `d >= c`, of one sign, and `sum_{d>=1} |u_d| = 1 / prod (rho_i - 1)`
**exactly**.  The `K + 1` conditions `w_0 = ... = w_K = 0` are met by a
correction on the `K + 1` smallest roots of relative size `O((p_{K+1} /
p_{K+2})**D)`.  Hence **every multiple with its `K + 1` lowest coefficients
free, `K <= L - 2`, has a coefficient above degree `K` of at least `(1 -
o(1)) prod_{i=K+2}^{L} (p_i - 1)` times its leading coefficient**, the
`o(1)` exponentially small in the degree.  Exact LP optima (z3 over the
rationals) converge to it from above: `L = 6, K = 3`: 216, 134, 122, 120.4,
120.0 at `D = 8, 12, 16, 20, 30` against `(11-1)(13-1) = 120`; `L = 5, K
= 2`: 244 at `D = 14` against `4 * 6 * 10 = 240`; `L = 4, K = 1`: 24.5
against 24.  Integer z3 on the profile itself, both sides: `L = 5, K = 2`
unsat at `B = 60`, sat at 80; `L = 6, K = 3` unsat at 120, sat at 160; `L
= 7, K = 4` unsat at 192, sat at 300 (`D = 14..16`).  Sweeping *every*
`U` of size 1..3 at `L = 4, 5` (`D = 8..14`), the least threshold is
always the lowest positions `{0..u-1}` and the largest is the positions
just under the top (`L = 5, |U| = 2, D = 14`: 244 at `{0,1}`, 939 at
`{12,13}`).

What this would assemble to, and what is missing.  Anchor at the top
(`|f_D| >= 1`), take `U` = the `u` largest coefficients below it, and the
program gives an `(u+1)`-th coefficient of at least `Theta_u = min_{|U|=u}
Theta_U(D)`; iterating `u = 0..L-2` yields `L - 1` distinct coefficients
with `mass(F) >= sum_u log Theta_u`.  If `Theta_u >= prod_{i>u} (p_i - 1)`
for every `U` -- what the sweep shows and the lowest-position certificate
proves -- that is `sum_i (i - 1) log p_i = Omega(L**2 log L) =
Omega(T**2 / log T)` for **every** multiple, the dense product's own order
and the right-half-plane bound without the half-plane.  Two gaps keep it
from being a theorem: the certificate is proved for `U = {0..K}` only, and
asymptotically in `D` (the exact optima sit above the limit at every
finite degree measured, but that is measured, not proved).  Until both
close the row stays open; the target is now exact.

Status of the two gaps, one round further.  (b) *Finite degree.*  The
exact-degree certificate (the row-space member with `c - 1` zeros just
under the top, low-position constraints included) is never below the
limit: every `K <= L - 2` at `L = 5, 6, 7`, every `D` from `L` to 40, in
exact rationals (`L = 7, K = 4`: 1349, 626, 424, ... 192.0 against 192;
pinned to `D = 40` in `tests/proofs/test_negatives.py`).  The
sequences involved are Polya-frequency: `1 / prod (1 - r_i x)` with `r_i >
0` is the generating function of a PF sequence (Aissen--Schoenberg--
Whitney), so `h_s(r)` is log-concave in `s`, the kernel `(a, s) ->
h_s(X, a)` is TP2 by composition, and the certificate's tail is
one-signed -- that part is proved.  For `c = 2` the whole inequality
reduces, through the 2x2 Cauchy--Binet expansion `Delta(s, t) = (b - a)
(Q_s Q_{t-1} - Q_{s-1} Q_t)` with `Q = h(all roots)` and `a < b` the two
largest, to the termwise statement `Q_{n-d} Q_{n-1} - Q_{n-d-1} Q_n <=
psi_d (Q_n**2 - Q_{n-1} Q_{n+1})`, `psi_d = (a**-d - b**-d) / (b - a)`,
which is an *identity* when only `a, b` are present (`h_n**2 - h_{n-1}
h_{n+1} = (ab)**n`) and strict below, ratio 0.9995..1.0000 at `L = 3..8`,
`n <= 40`.  Adding a root smaller than `a` must not raise that ratio;
that single inequality, and its `c > 2` analogue through the `c x c`
minors, is what (b) still needs.  A primal reduction does not work:
dividing out the small roots turns bounded coefficients into `B *
h_n(small)` ones, and the free low coefficients are `B r**D` large.  (a)
*Lowest positions.*  Every unbounded set of size 1..3 at `L = 4, 5` and
size 1..2 at `L = 6` (`D = 10, 14`) has its minimum at `{0..u-1}`, and
the optimum rises monotonically as any one position moves up (`L = 6,
|U| = 1, D = 14`: 8196, 8325, 8527, 8844 at positions 0, 1, 2, 3; 12270
at 13).  No exchange argument is proved: a primal move of one free
position needs a multiple supported on two degrees, which does not
exist, and the dual rows are not comparable position by position.

**The two largest roots, every degree (proved).**  Let `Q_m = h_m` of a
multiset of positive reals containing `a < b` (`Q_m = 0` for `m < 0`),
`T` its lower-triangular Toeplitz matrix `T[r][k] = Q_{r-k}`, and
`psi_d = h_{d-1}(a, b) / (ab)**d`.  Claim `(H)`: for all `n >= 1`, `d >= 1`,
`s >= 1`, `det T[{n-d, n}; {0, s}] <= psi_d * det T[{n, n+1}; {0, s}]`.
*Base*, the multiset `{a, b}`: `Q_m = (b**(m+1) - a**(m+1)) / (b - a)`
and `Q_p Q_q - Q_{p-t} Q_{q+t} = (ab)**(p-t+1) h_{t-1}(a,b) h_{q-p+t-1}(a,b)`
whenever every index is nonnegative, so both minors are explicit and
their ratio is `psi_d` exactly; where an index is negative the left
minor is `Q_{n-d} Q_{n-s}` or `0`, and `h_u h_v (ab)**e <= h_{v+e} h_{u+e}`
(from `h_{m+1} >= b h_m >= a h_m`) closes it.  *Step*, adjoining a root
`x > 0`: `Q' = Q * (1, x, x**2, ...)`, so `T' = T G` with `G[i][j] =
x**(i-j)`, and Cauchy--Binet on columns `{0, s}` gives `det T'[R; {0,s}]
= sum_{k1 < s <= k2} x**(k1+k2-s) det T[R; {k1, k2}]` -- every other
2x2 minor of `G` is `x**(k1+k2-s) - x**(k1+k2-s) = 0` -- with weights
that depend on the columns only, hence identical for `R = {n-d, n}` and
`R = {n, n+1}`.  Toeplitz shift moves `det T[R; {k1, k2}]` to `det T[R -
k1; {0, k2 - k1}]`, the same two row shapes at anchor `n - k1` and column
gap `k2 - k1`, where `(H)` applies (or the left minor is `0`).  Summing
with nonnegative weights gives `(H)` for `Q'`.  Executed: the expansion
and `(H)` in exact integers to `n = 24`, equality exactly in the pure
interior.  *Consequence.*  With `a, b = p_{L-1}, p_L` and the other
`L - 2` primes as the rest, the `c = 2` certificate (one zero under the
top, `K = L - 3` free low coefficients) has `E_s A_{S-1} = -Delta(s, S-1)`
and `E_S A_{S-1} = Delta(S-1, S)` with `Delta(s, t) = (b - a) det T[{s,
t}; {0, 1}]`, so its tail over the top is `sum_{d=1}^{n} det T[{n-d, n};
{0,1}] / det T[{n, n+1}; {0,1}] <= sum_d psi_d = 1 / ((a-1)(b-1))`.
**Every real multiple of `prod_{i<=L} (x - p_i)` of any degree `D >= L`,
monic, with its `L - 2` lowest coefficients free, has a coefficient in
degrees `[L-2, D)` of absolute value at least `(p_{L-1} - 1)(p_L - 1)`.**
Integer z3 agrees: `L = 5`: unsat at 60, sat at 80; `L = 6`: 120 / 160;
`L = 7`: 192 / 300.

*General `c`, what carries and what does not.*  The step carries
verbatim: `c x c` Cauchy--Binet, weights `det G[S; C] >= 0` (the geometric
sequence is Polya-frequency) depending on `(S, C)` only, Toeplitz shift.
The hypothesis must be stated for every column set `C = {0 < c_1 < ... <
c_{c-1}}`, rows `{n-d} + {n-c+2..n}` against `{n-c+2..n+1}`, with
`psi_d = h_{d-c+1}(1/rho) / prod rho` (`rho` the `c` designated roots,
`d >= c-1`); measured true at `c = 3, 4` for every `C` to column 6, `n <=
12`, roots `(2,3,5)`, `(5,7,11)`, `(2,3,5,7)` alone and with one to three
smaller roots adjoined (ratio to `psi_d` at most 1, below 1 once a root
is adjoined).  The base case, the `c` designated roots alone: in the
interior (every entry `Q_{r-k}` with `r >= k`) the truncated Toeplitz
matrix factors as `V diag(A) W` with `V[r][i] = rho_i**r`, `W[i][k] =
rho_i**-k`, so both minors are `det V[R] * const` and their ratio is
`s_lambda(rho) / s_mu(rho)` for `lambda = ((n-c+1)**(c-1), n-d)`, `mu =
((n-c+1)**c)`, which the rectangle-complement identity `s_{(k**(c-1))}(rho)
= (prod rho)**k h_k(1/rho)` evaluates to `psi_d` -- equality, for every
`C`.  At the boundary (some `r < k`) the minors are skew Schur functions
`s_{lambda/mu}(rho_1..rho_c)` by Jacobi--Trudi and the needed inequality
is `s_{((d-c+1)**(c-1))} * s_{lambda_B/mu} >= (prod rho)**(d-c+2)
s_{lambda_A/mu}`, measured, not proved, for `c >= 3` (`c = 2` is the
hand argument above).  That inequality is the whole of gap (b).

*Gap (a) is not a principal-representation theorem.*  The primal is
`min_B` over `f_D = 1`, `|f_m| <= B` off `U`, `f_U` free, `sum_m f_m v_m
= 0` with `v_m = (p_i**m)_i`: the gauge of `v_D` modulo `span(v_U)` in
the norm whose unit ball is the absolutely convex hull of `{v_m : m not
in U, m < D}`.  The nodes are distinct and positive and the `v_m` trace
a Descartes system, but the weights are signed and the object is a
quotient gauge, not a moment cone, so Karlin--Studden's lower principal
representation (nonnegative measures, index counted with endpoints) does
not apply as stated; no hypothesis of the LP fails, the theorem simply
does not cover it.  Measured at `L = 4, 5, 6`: the minimum over `U` of
fixed size is the lowest positions and rises as any position moves up.

## Literature

[Giesbrecht, Roche and Tilak][sparse-multiples] (Algorithmica 64:454-480,
2012) give an unconditional algorithm for binomial multiples (the `t = 2`
case Niven closes here) and, for each fixed `t >= 3`, one needing an a priori
height bound and no repeated cyclotomic factors.  The mandatory products are
cyclotomic-free (squared modulus at least 4, measured 58 at smallest over
dense n=3..6); what excludes them is `t = Theta(T/log T)` growing with the
degree -- the case the paper singles out: "Removing these restrictions is
desirable (though not necessarily possible)", and "we suspect that computing
t-sparse multiples is NP-complete over both Q and F_q, when t is a parameter
in the input".  Roche's 2018 survey ([arXiv:1807.08289][sparse-survey])
leaves sparse division and divisibility testing as Open Problems 2 and 3.

## What is open

A non-generic O(T)-digit multiple of the mandatory root product with *more*
terms than the Descartes minimum `L + 1`, so that the coefficient kernel has
rank two or more and no single minor pins a coefficient; its cofactor roots
must have substantially negative real part with inexact magnitude relations
to the prime-power instruction roots.  Every other route -- sign patterns,
operands, exact mirrors, the `(L+1)`-term class, small cofactor degree,
unbalanced profiles, norm bounds, root-set term bounds, the
one-large-coefficient profile -- is closed above.  Conjectured
NP-completeness would not forbid a bespoke family, so the row stays open
rather than closing as a wall.

The profile that survives is narrower than before: `O(1)` coefficients of
`O(T)` digits, a second one at a constant fraction of the primorial, and a
*sparse* remainder -- `O(T / log T)` terms of `O(log T)` digits, since a
remainder at every degree costs `D log D >= T log T`.  Whether the
remainder can be sparse is the question; every executed multiple with a
small remainder had it dense.  The heuristic against it is the Gaussian
count: multiples of cofactor degree `k` form a lattice of covolume about
`primorial**(k+1)`, and the box of the profile has volume `2**O(T)`, so
generic lattices give `k = O(1)` -- the small-cofactor class, closed.  A
proof would have to show this lattice has no unexpectedly short vector,
which is exactly what its algebraic structure does not grant -- or run the
iterated elimination above to its end: prove its certificate for every
unbounded set and every degree, and every multiple is `Omega(T**2 / log
T)`.

What such a multiple must look like, each a line and none a search.  Term
killing does not reach it: the Rolle operator `x d/dx - c` behind Descartes
deletes one term and loses at most one positive root, so the kernel rank
`t - L` is invariant and the `(L+1)`-term theorem does not extend by
reduction.  With `0` in the support (divide out `x^e_1`) every prime divides
`f_0`, so `f_0` is at least the primorial and an O(T)-digit multiple has O(1)
coefficients that large; `F(2) = 0` then puts the degree at or above
`log2 f_0 - log2(sum of the other coefficients)`, so either the other
coefficients sum to the primorial's square root or the degree is at least
`0.72 L log L`.  A gap `g` between consecutive exponents has `2^g` at most
the sum of the coefficients below it whenever the part above is nonzero at
some prime; otherwise both parts are multiples with fewer terms and the mass
adds, so the degree is at most `t log2(t H)`.  The `p`-adic Newton polygons
add nothing past the primorial: a slope `-1` segment at every `p_i` is met by
`p_i || f_0` and a term at `x^1`, as in `P` itself.  Checked on 48
constructed multiples to `L = 7` with a split control.

[sparse-multiples]: https://arxiv.org/abs/1009.3214
[sparse-survey]: https://arxiv.org/abs/1807.08289
