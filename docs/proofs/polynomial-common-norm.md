# Coefficient mass for common norm Gaussian factors

The common-norm subproblem has a quadratic mass bound for its raw factor
and for scaled reciprocal or anti-reciprocal integer multiples. The bound
for arbitrary integer multiples remains a conjecture. This restriction
does not cover the arbitrary Gaussian register-root families in
[Polynomial](polynomial.tex), whose norms need not agree.

Let `K >= 2`, let `p_j` be distinct primes, and put `c_j = p_j^b_j`
with `b_j >= 2`. Suppose nonzero integers `a_j` satisfy
`a_j^2 + c_j^2 = R`, independently of `j`. Define

`Q(y) = product_j (y^2 - 2(a_j^2-c_j^2)y + R^2)`

and `Lambda(F) = sum_i log^+|f_i|` for an integer polynomial
`F = sum_i f_i y^i`. All logarithms below are natural unless a base
is specified. The conjecture asks for an absolute `c > 0` such that
every nonzero integer multiple `F` of `Q` satisfies
`Lambda(F) >= c K^2 log K`, independently of its degree.

## A principal disk support bound

An `s`-term polynomial over the completed algebraic closure of `Q_2`
has at most `B(s) = s-2+floor(log_2 s)` zeros, with multiplicity, in
any disk `u(1+4O)`, for `s >= 2` and `u != 0`.

To prove this, write the polynomial as `sum_j A_j x^n_j`, with distinct
nonnegative integer exponents. Substitution `x = u exp(4z)` gives
Taylor coefficients `4^m M_m/m!`, where
`M_m = sum_j A_j u^n_j n_j^m`. The moments obey an order-`s` recurrence
whose characteristic polynomial is `product_j(T-n_j)` and whose
coefficients are integers. Consequently every moment has valuation at
least `h = min_(0<=m<s) v_2(M_m)`. The minimum is finite by the
Vandermonde determinant and is attained by an initial moment.

Legendre's formula gives Taylor-coefficient valuation
`m+popcount(m)+v_2(M_m)`. Some initial coefficient has valuation at
most `h+s-1+floor(log_2 s)`. Every index
`m >= s-1+floor(log_2 s)` has strictly larger valuation. The Taylor
coefficients tend to zero, and Strassmann's theorem bounds the zeros
by the last least-valuation index, at most `B(s)`.

If `R` is odd, each odd-base leg has even `a_j` and odd `c_j`.
Both roots `(a_j +/- i c_j)^2` are `-1 modulo 4Z[i]`. There is at
most one base-two leg, so one principal disk contains at least
`2K-2 >= K` distinct roots.

If `R` is even, the existence of an odd-base leg forces `R = 2 modulo 4`.
Every leg then has odd `a_j,c_j`; a base-two leg is impossible.
The roots after division by two have real part divisible by four
and odd imaginary part. Each conjugate pair contributes one root
to each disk `+/-i(1+4O)`. Each disk therefore contains `K` roots.

The prescribed roots are distinct. A square root in the upper
half-plane of either member of the `j`th conjugate-square pair has
imaginary coordinate `c_j`. Equality between different pairs would
therefore force equal prime powers. Within a pair the two roots differ
because `a_j c_j != 0`.

Thus every nonzero multiple has support count
`s >= (K+3)/2`, since `K <= B(s) <= 2s-3`.

## Quadratic mass in reciprocal classes

For the raw degree-`2K` factor, coefficient reciprocity is
`q_i = R^(2(K-i)) q_(2K-i)`. More generally, suppose an integer
multiple, after removing its initial monomial, has degree `D` and
satisfies

`f_i = epsilon R^(D-2i) f_(D-i)`, with `epsilon` equal to `1` or `-1`.

Its support has at least `t >= (s-1)/2 >= K/4` nonzero reflected
pairs below the middle. Each pair pays at least
`(D-2i) log R`, because its upper coefficient is a nonzero integer.
These positive weights are distinct and have one parity, so their
sum is at least `t^2`. Consequently

`Lambda(F) >= K^2 log R/16 >= K^2 log K/4`.

The second inequality uses `R > c_max^2 >= p_K^4 >= K^4`.
The raw factor satisfies the required reciprocity, so it is included.
No restriction on quotient degree or coefficient signs is needed
within these reciprocal classes.

## The remaining transfer problem

Reciprocity of `Q` does not imply reciprocity of an arbitrary multiple.
The support bound also does not locate its nonzero coefficients at
indices where radius divisibility supplies a quadratic charge.
The missing result must control cancellation for arbitrary integer
quotients, rather than only prove that the raw factor is large.

Local half-factor approximations do not remove this difficulty. For
example, select one root `alpha_j` from each quadratic and let
`W = product_j(y-alpha_j)` in `Z[i][y]`. Rational interpolation gives
a real polynomial `B` of degree below `2K` with
`B(alpha_j) = -i alpha_j` and
`B(conjugate(alpha_j)) = i conjugate(alpha_j)`.
The interpolation nodes are distinct, and their conjugation symmetry
makes the unique interpolant rational. After clearing a positive
integer denominator `d`, the polynomial `dB + idy` is divisible by
`W`, but only its linear coefficient is nonreal. Monic division puts
the quotient in `Z[i][y]`. Thus a nonreal-density bound for a raw
half-factor cannot extend to unrestricted Gaussian quotients.
This is not a counterexample to the integer-multiplier conjecture.

Canonical integer-scaled tails can instead pay valuation height, but
rescaling back to rational approximants changes both sizes and
denominators. A bound before that rescaling is not an integer
height-transfer theorem. The common-norm conjecture remains open;
even its completion would not settle the general register-root case
or close Polynomial's factor-12.5 constant bracket.
