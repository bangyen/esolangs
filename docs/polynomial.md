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

**Total mass: no multiple is lighter than the product** (executed).  The
decisive measurement for the whole route: the least coefficient-digit
mass over *every* integer multiple `P * M`, `deg M <= D - L` (z3,
bisection on a digit budget, exact) is the product's own at every size
that finished -- `L = 3`: 7 digits, `D <= 12`; `L = 4`: 12, `D <= 12`
(`D = 14`: nothing at or under 10, 11 unknown); `L = 5`: 18, `D <= 11`
(`D = 13`: nothing at or under 14); `L = 6`: 25, `D <= 12`; `L = 7`: 36,
`D <= 11`.  The sequence 7, 12, 18, 25, 36, 47, 63, 78, 100, 118 (`L =
3..12`, the product's digits) has successive ratios 1.71, 1.50, 1.39,
1.44 at `L = 3..7` against 1.68, 1.45, 1.34, 1.27 for `L log L`, fitted
exponent 1.93 over `L = 3..7`, and is `Theta(L**2 log L)` exactly
(`e_k >= p_{L/2}**k` for `k <= L/2`, `e_k <= C(L, k) p_L**k`).  So the
minimum reads `L**2 log L`, not `L log L`: the iterated elimination's
target is the truth at every size measured, the route is alive, and no
`O(T)`-digit multiple exists to become a construction -- the roadmap's
"multiple with `O(T)` coefficient digits" has no member below `L = 7`
in any cofactor degree searched.  The minimal witness is the product
(or a shift of it), never a sparser cofactor.  On that witness the
assembled statement reads: at least `u + 1` coefficients below the top
reach `prod_{i>u} (p_i - 1)`, for every `u`, `L = 3..12`, tight at `u =
L-3, L-2`; `sum_u log10` of the thresholds is 0.75..0.81 of the
product's digits.  That count -- not "some coefficient is large" -- is
the statement the iteration must deliver, and it is what (a) has to be
proved as.  Pinned: the minima at `(L, D) = (3, 8), (4, 6), (5, 7), (6,
8), (7, 9)` and the count to `L = 12`.

**Real against integer: the bound does not live in integrality**
(executed).  The certificates and the two-root theorem are over real
cofactors; the program is integer.  Minimising the same digit mass over
*real* monic cofactors, a coefficient below 1 costing nothing (z3 over
the rationals, bisection): the product's mass less exactly one digit --
6 against 7 (`L = 3`, `D <= 10`), 11 against 12 (`L = 4`, `D <= 10`), 17
against 18 (`L = 5`, `D <= 11`), 24 against 25 (`L = 6`, `D <= 10`) --
the one digit being what the free sub-unit tail buys; the real
minimisers keep the product's shape with one coefficient traded.  So
the real relaxation is as heavy as the integer object up to a constant,
the linear-programming route can in principle deliver `Omega(L**2 log
L)`, and a proof does not need to pass through residues.  Pinned at
`(L, D) = (3, 5), (4, 6), (5, 7)`.

*The `p`-adic residue chain is residues only.*  `F(p_i) = 0` read
`p_i`-adically: the lowest nonzero coefficient is a multiple of the
primorial, and every later one is forced modulo `prod p_i` by the ones
below it (`f_{m+j+1} = -carry_j^{(i)} mod p_i`, all `i` at once by CRT), so
each coefficient is either the least residue of a determined value or
at least `prod p_i / 2`.  The count statements this suggests hold on
everything measured: at least `u + 1` coefficients below the top reach
`prod_{i>u} (p_i - 1)` (weak) and even `prod_{i>u} p_i / 2` (strong), on
20,000 random integer multiples per `L = 4..7` (cofactor degree to 8,
entries to 3; and to degree 12, entries to 50 at `L = 6`) and on every
adversarial minimiser of the earlier rounds -- the strong count is
exactly `u + 1` at `u = 0` on the tail-height minimisers and at `u = 1`
on the `L = 4` sparse-remainder one, so it is the sharp form.  What the
chain cannot do alone is force a *magnitude*: a least residue may be
small, and the tail-height floor (`0.36` of the primorial, above the
chain's `1/4`) is a magnitude fact that the real relaxation already
carries.  The proof of the count form therefore belongs to the linear
program, with residues at most as a bookkeeping device; the chain is
recorded so it is not rebuilt.

*The `c >= 3` boundary, two attacks that do not land.*  The truncated
Toeplitz matrix is the full rank-`c` matrix `V diag(A) W` with its
`r < k` entries zeroed -- a Hadamard mask, not a product with a
projection -- so Cauchy--Binet through the truncation is unavailable;
what the truncation does is remove path families from the
Jacobi--Trudi / Lindstrom--Gessel--Viennot count, so the boundary
inequality is "truncation lowers the `A`-minor by at least the factor
it lowers the `B`-minor", `A_trunc / A_full <= B_trunc / B_full`, which
holds in every case computed (`c = 3, 4`, roots `(2,3,5)`, `(5,7,11)`,
`(2,3,5,7)`, `n <= 12`, columns to 6, 720..806 cases each, maximum ratio
exactly 1) and would follow from a path-family injection of the
Lam--Postnikov--Pylyavskyy kind; not built.  Pinned: the `c = 3`
hypothesis with `psi_d = h_{d-2}(1/rho) / prod rho` to `n = 10`.

*Gap (a), what the slack buys and what it does not.*  Only `sum_u log
Theta_u = Omega(L**2 log L)` is needed, so `Theta_u` may lose constant
factors and even the top `u` primes: `prod_{i>2u+1} (p_i - 1)` still
sums to `(L**2 / 4) log L`.  Case `max(U) <= 2u` (`U` packed low): free
every position below `max(U)` and apply the lowest-position certificate
with `2u + 1` free positions -- sound, and the whole of (a) for such
`U`, once the `c >= 3` base holds.  Case `max(U) > 2u`: a certificate
cannot be confined to a window -- `F(p_i) = 0` is one global relation
and a nonzero `sum c_i r_i**m` has at most `L - 1` zeros -- so "the `u =
0` statement on the gap's window" is not a statement; that step fails
as written.  What a proof has to do instead, from the certificate's
own arithmetic: carry the certificate on the `L - 2u` largest roots and
correct each free position with one of the `u` smallest.  A free
position at distance `d` under the top costs a correction whose tail is
at most `C(d, c) (p_u / p_{2u+1})**d rho**c` times the main tail, with
`p_u / p_{2u+1} <= 1/2` -- negligible once `d >= c log2 rho + O(c)`,
i.e. for free positions more than about `c log L` below the top -- but
ruinous inside that window (`r_j**c` against `1`), where the free
positions must instead be absorbed as extra zeros of the main part on
more large roots, whose tail is then no longer the closed form `1 / prod
(rho - 1)`.  The exact optimum is largest for `U` in that window
(measured), so the truth is fine there; the certificate that shows it
is the remaining construction.  That, plus the `c >= 3` base, is (a).

*Desnanot--Jacobi does not lift `c = 2` to `c = 3`.*  The identity
writes each `3x3` minor as `(X1 Y1 - X2 Y2) / centre` in `2x2` minors of
the same matrix, verified exactly, but the two-root theorem bounds every
`2x2` ratio from one side only, and the target needs the other side on
the subtracted product: substituting the proved bounds (`X2 >= 0`, `X1
<= psi Y2`) leaves `A <= psi_{d-1} Y1 Y2 / centre`, which exceeds `psi_d
B` by up to x147 (`(2,3,5)`), x110, x61 over 515 boundary cases each,
and no two-sided form exists -- boundary `2x2` ratios fall to 0.004 of
`psi`.  Dead as a route.

**The slack certificate: one lemma is the whole bound** (measured,
stated exactly).  Only `sum_u log Theta_u = Omega(L**2 log L)` is
needed, so give up the `u` primes `p_{u+1}..p_{2u}`.  For a free set `U`
of size `u <= (L-1)/2` at *any* positions, take the pure certificate on
the `L - u` largest roots -- the `u` smallest unused, so no coupling, no
truncated Toeplitz, no `c >= 3` boundary at all -- with its `L - u - 1`
zeros at `U` and at the first `L - 2u - 1` distances under the top not
in `U`.  It vanishes on `U` and is in the row space.  Measured: its
threshold is at least `prod_{i>2u} (p_i - 1)`, ratio `1.0000..1.005`,
for `L = 5..10`, `u <= (L-1)/2`, every `U` inside distance 8 (`u <= 3`)
and 120 random `U` to distance 40 -- approached from above as `U` goes
deep, where the certificate tends to the pure one on the `L - 2u`
largest roots.  The general statement behind it, about pure exponential
sums only: **for `c` roots and `c - 1` prescribed zeros of which the
first `f` are the distances `1..f`, the tail is at most `1 / prod (rho -
1)` over the `f + 1` largest roots, with equality exactly when every zero
is a leading one** (exhaustive over zero sets inside distance 7 and 300
random ones to distance 30, for `(5,7,11)`, `(3,5,7,11)`, `(7,11,13,17)`,
`(5,7,11,13,17)`, `(3,5,7,11,13,17)`; maximum ratio 1.0000).  Each
leading zero buys one root; a displaced zero buys nothing but costs
nothing.  Sign structure for a proof: a `c`-term exponential sum has
no zeros besides the `c - 1` prescribed, so it alternates across them
and the tail is `S(1) + 2 sum_g (-1)**g S(z_g)` with `S(d) = sum_i
a_i y_i**d / (1 - y_i)` -- an explicit rational function of the roots;
the claim is that moving any zero deeper never lowers it and the limit
is the leading-zero product.  With this lemma: anchor `|f_D| >= 1`,
iterate `u = 0..(L-1)/2` over the `u` largest coefficients wherever
they sit, and every real multiple of `prod (x - p_i)` has `mass >=
sum_{u <= (L-1)/2} log prod_{i>2u} (p_i - 1) = (1/4 - o(1)) L**2 log L`,
i.e. every Polynomial program is `Omega(T**2 / log T)` characters.  The
lemma is pinned (`TestEachLeadingZeroBuysOneRoot`); the bound is not
written until it is proved.

**One displaced zero, proved; the lemma's shape, mapped.**  Write `y_i =
1/rho_i`, so `y_1 < ... < y_c <= 1/2`, `h'_s = h_s(y_1..y_{c-1})` (the
`c - 1` largest roots), `h_s = h_s(y_1..y_c)`, `P = y_1 ... y_{c-1}`.
*Not monotone.*  The tail is not a monotone function of the zero
positions, so no extremal-at-the-boundary theorem applies as such:
`(3,5,7,11)`, `Z = (1,2,3) -> (1,2,4)` drops it `1/480 -> 0.00162`
(changing `f`), and `(2,3,5,7)`, `Z = (1,2,4) -> (1,2,5)` drops
`0.011218 -> 0.011169` with `f` fixed; pointwise `|u_d|` is never
monotone.  Karlin--Studden's principal representations (min/max of a
functional over nodes) are therefore not the statement; the lemma is a
supremum over each fixed `f`, approached as the displaced zeros go to
infinity, not attained.  *Proved for `f = c - 2` (one displaced zero
`z >= c - 1`), every `c`, every root `>= 2`.*  Let `F` be the
leading-zero certificate on the `c - 1` largest roots (`F_d = (-1)**c P
h'_{d-c+1}` for `d >= c-1`, zero on `1..c-2`) and `G_d = h_{d-c+1}(y)`
for `d >= c-1`, zero below, the unique `c`-root sum vanishing at
`0..c-2`.  Then `u = F + lambda G` with `u_z = 0`, i.e. `u_d = (-1)**c P
(h'_d - r h_d)` with `r = h'_z / h_z` (indices shifted by `c - 1`), an
identity checked exactly.  `h'_s / h_s` is strictly decreasing in `s`
(`h_s / h'_s = sum_k y_c**k h'_{s-k} / h'_s` and each `h'_{s-k} / h'_s`
increases with `s` by log-concavity of the Polya-frequency sequence
`h'`), so `u` has the sign of `(-1)**c` below `z` and the opposite above,
and `tail = P [sum_{s<z'} (h'_s - r h_s) + sum_{s>z'} (r h_s - h'_s)]`.
Against `bound(c-2) = P sum_s h'_s`: `bound - tail = P [h'_{z'} + r
sum_{s<z'} h_s + 2 sum_{s>z'} h'_s - r sum_{s>z'} h_s]`, and splitting
the convolution `h = h' * (1, y_c, y_c**2, ...)` at `z'` gives exactly
`sum_{s>z'} h_s = (A + y_c h_{z'}) / (1 - y_c)` with `A = sum_{s>z'}
h'_s`, so the negative term is `r A / (1 - y_c) + h'_{z'} y_c / (1 -
y_c) <= 2A + h'_{z'}` because `r <= 1` (`h' <= h`) and `y_c <= 1/2`.
Hence `tail <= bound(c-2)`, with room `P [r sum_{s<z'} h_s + ...]`.
Pinned to `z < 30` on four root sets.  In the slack assembly this is
`u = 1`: **at least two coefficients of every real multiple reach
`prod_{i>2} (p_i - 1)`, wherever the first one sits** -- rigorous now,
on top of `u = 0`.  *What remains for general `f`.*  With `k = c - 1 -
f` displaced zeros, `u = F + lambda G` still holds with `F` the
certificate on the `c - 1` largest roots carrying the leading zeros and
the first `k - 1` displaced ones, and `G` the `c`-root sum vanishing at
`0`, the leading zeros and those `k - 1`; `tail(F) <= bound(f)` by
induction on `c`, but `F` and `G` now alternate across `k - 1` interior
zeros each, and the one-displaced argument's two ingredients -- one
sign change for `u`, one-signed `G` -- are gone.  The lemma is verified
to `c = 14` (roots `3..47`, `f` from `0` to `c - 2`, displaced zeros to
distance 35; ratio at most 0.99999), and the induction on the number of
displaced zeros, with the sign pattern of `F + lambda G` tracked through
the interlacing of `F`'s and `G`'s zeros, is the resumption point.

**The slack, spent: a lossy induction whose two sub-lemmas are measured.**
The assembly tolerates `tail <= K(c) bound(f)` with any `K(c) = 2**O(c)`
(the loss `sum_u log K(L - 2u)` is `O(L**2)`, below `L**2 log L`), so the
lemma need not be sharp.  With `k` displaced zeros, `u = F + lambda G`
(`F` on the `c - 1` largest roots carrying the leading zeros and the
first `k - 1` displaced ones, `F_0 = 1`; `G` the `c`-root sum vanishing
at `0`, the leading zeros and those `k - 1`; `lambda = -F_{z_k} /
G_{z_k}`), and the triangle inequality gives `tail(u) <= tail(F) +
|lambda| tail(G)`.  By induction on `c`, `tail(F) <= K(c-1) bound(f)`
(the top `f + 1` roots are the same).  Measured over every `Z` to
distance 9..30, `c = 3..8` (roots `3..23`): `|lambda| tail(G) / bound(f)`
is at most 0.53, 0.58, 0.61, 0.64, 0.66, 0.67, always worst at one
displaced zero just past the fill (`Z = (1..c-2, c)`), and at most 0.17
once `k >= 2`; so `K(c) <= K(c-1) + 0.7`, linear in `c`, while the true
`K` is 1.  What a proof needs, stated exactly: (ii-a) `|F_d / G_d|` is
decreasing in `d` past the last prescribed zero `z_{k-1}` (measured on
every case, 2320..5800 consecutive pairs per `c`), so the worst `z_k`
is `z_{k-1} + 1`; (ii-b) at that `z_k`, `|F_{z_k}| tail(G) / |G_{z_k}|
<= C bound(f)` for a constant or polynomial `C(c)`.  For `k = 1` both
are the proved one-displaced argument (`F/G = h'/h`, and the crude
`|lambda| tail(G) <= P (h'_{z'} / h_{z'}) sum_s h_s <= 2 bound(c-2)`).
For `k >= 2`, `F` and `G` each alternate across `k - 1` interior zeros
and (ii-a), (ii-b) are open; the pinned test carries both measurements
(`TestTriangleSlackIsBounded`).  The bound is not written: its proof
would rest on (ii-a) and (ii-b), which are numerical facts, not lemmas.

**The decomposition, and the one product it does not split** (THE
resumption point).  The `k = 1` mechanism was a convolution, `G = (F *
(1, y_c, ...) - y_c**d) / sigma P`, which needs `F`'s zeros to be one
consecutive run; for `k >= 2` no such relation holds (`G_d / (F *
geo)_d` constant in 0 of 270 cases).  What holds for every `k`, exactly:
`E_d := G_d - y_c G_{d-1}` is a `(c-1)`-root sum (the operator kills
`y_c`), it vanishes on the leading zeros `1..f` (both `d` and `d - 1`
are zeros of `G`), and `E_{z_j} = -y_c G_{z_j - 1}` at the displaced
ones.  The `(c-1)`-root sums vanishing on `1..f` form a `k`-dimensional
space with Lagrange basis `B_j` on the nodes `0, z_1..z_{k-1}` (`B_j`
vanishes at `0`, `1..f` and every `z_i`, `i != j`, with `B_j(z_j) = 1`),
and `E = mu F + sum_j E_{z_j} B_j` with `mu = E_0 = -y_c G_{-1}`, `G`
extended to `d = -1` as the exponential sum; then `G_d = sum_{i<d}
y_c**i E_{d-i}` recovers `G`.  Hence `|lambda| tail(G) <= |F_{z_k}| (y_c
/ (1 - y_c)) [ |G_{-1}| T(F) + sum_j |G_{z_j-1}| T(B_j) ] / |G_{z_k}|`
with `T` the full tail from `d = 1`.  Measured (`c = 4..7`, `k = 2..5`,
displaced zeros to distance 17): the whole right side is at most
`0.45 bound(f)`, so the accounting closes numerically with room.  The
pieces do not split: `|F_{z_k}| |G_{-1}| / |G_{z_k}|` is bounded (0.68,
1.60, 1.19, 1.96 at `c = 4..7`) and `T(F) <= K bound(f)` is the induction
hypothesis, so the `F`-piece is fine; but each `B`-piece is the product
of `T(B_j) / bound(f)`, which is astronomically large (`3 * 10**12 ..
10**18` -- `B_j` is normalised at `z_j`, where it is tiny against its
own bulk), and `|F_{z_k}| |G_{z_j-1}| / |G_{z_k}|`, which is
correspondingly small (`10**-3 .. 10**-6`), with a bounded product
(under 0.16).  So the open number is the product `Psi_j := |F_{z_k}|
|G_{z_j-1}| T(B_j) / (|G_{z_k}| bound(f))` -- the tail of the Lagrange
component `E_{z_j} B_j` of `E`, measured against `bound(f) |G_{z_k}| /
|F_{z_k}|` -- and a proof must bound it without separating the factors:
either through the induction itself, treating `E_{z_j} B_j` as a
`(c-1)`-root object whose normalisation is the value of the `c`-root `G`
one step before `z_j`, or by a Vandermonde-ratio estimate of the product
directly.  Pinned: the three identities and the bound-sum
(`TestPointADecomposition`).  Also measured and usable: `|F|` is
log-concave past its last prescribed zero (0 of 5940 triples), `|F/G|`
decreases there, and in the far zone `|F_z / G_z|` decays like `(y_{c-1}
/ y_c)**(z - z_{k-1})`, so only offsets within `O(p_c)` of `z_{k-1}`
need the bound, at a loss of `O(c log c)` per level.

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
