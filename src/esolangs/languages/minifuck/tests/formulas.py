"""Minifuck's emitted characters: the positional strip.

Execution, ``worst 71T/2 + 50 - n`` (B), n >= 3: a bound for every n, met up to
n = 12 (last bullet).  Steps are the emitted length minus the collapsed ``[``
(each skips the next command).  By shipped route:

* Ignored inputs: length <= Mx(k) + 18 per ignored input, k essential, Mx(k)
  the k-input maximum (269 at k = 2, M(k) = 81 2**k/2 + 59 - k above, 104 and
  99 below).  A leading input adds 8 (inert), a trailing one 2, an interior run
  of g adds 12g + 6e exactly (55,986 gap patterns, k = 2..7), e = max(0, g - a
  + 1) the pad extension, a the next weight, so e <= g (pad 2, relay 4 each):
  18, met by a gap before the last essential input.  k = n - 1 is the worst:
  M(n-1) + 18 <= B needs 15.25 T >= 28 (287 against 331 at n = 3), so under B.
* ``two_state``: length <= 89n + 34 (89 a level, 33 to finish and the dot, over
  all 16 value lists and all 128 lower-cell states), under B from n = 3.
* ``stored``: each ``[x<[x<[x<[x`` collapses exactly twice (its cell flips to
  not-a, a, not-a, a and a landing on 0 collapses) and no word ends in ``[``,
  so no skip crosses a word and steps <= L - 2R.  The other words are at most
  2R + 32 (per op 2R - 5, checked on a piecewise-linear grid), so
  steps <= (11L + 64)/13, and L <= the positional length <= M: under B from n = 3.
* The mux, every n >= 3 (tables <-> control vectors, so any controls occur).
  Row r = sum x_i a_i, a_i = 2**(n-1-i), ks = T - 1 - r, s the selected control.
  A ``[x`` pair costs 1 where the prefix XOR of the cells crossed is 1, else 2;
  a tile costs 1 (a one before the first zero), 3 (the first zero), 1 (a later
  zero), 3 (a later one).  A weight gadget from a ones context
  [p-k+2, p] takes 5k - 1 steps and ends at p + 1 (x = 0) or clears
  [p-k+3, p+1] and ends at p-k+1 (x = 1); its pad of a_i + a_{i+1} - 1 pairs
  takes 2(a_i + a_{i+1} - 1) - a_i x_i and leaves [p+2, p'] ones, the next
  context.  So the pads take 3T - 2n - 4 - (r - x_{n-1}), the pointer ends at
  pmax - r, and r + 6 - x_{n-1} zero cells trail the strip.  The field's best
  tiles and cross are 9T/2 + w, w = 6, 4, 2 (s = 0; ks = 0, 1, >= 2) or 3, 4,
  6 - 2[ks odd] (s = 1): with m the prefix XOR of the flipped controls,
  2 (changes of m) - (zeros of m) <= 3(T+1)/2 + 1/2 - psi(m_T), psi(0) = 1/2,
  psi(1) = 0, and the parity of the no-change steps fixes the rest.
  Input i adds 15 a_i/2 (x_i = 0, which flips the prefix parity q) or
  (13 - 2q_i) a_i/2.  With q_0 = s, P the final parity, y the last three bits:
  steps = B + c(s, q_{n-3}, y) - sum_{i<=n-4} a_i x_i (q_i + P), c free of n,
  c <= -1 but c(T - 1, s = 0) = 0.  Model = interpreter on random tables
  n = 3..11; the model's max is B at n = 3..16.
* B is met for n <= 12 only.  Its table (controls 1 but the last row's) is the
  unique maximiser (all 2**8, 2**16 control vectors at n = 3, 4) and ships as
  the mux through n = 12; from n = 13 its stored plan (~n**2: 235,887 characters
  at 13) undercuts the mux (331,822), so B bounds the shipped worst but is not
  met.
"""


def _chars(n: int, _: str) -> int:
    """81T/2 + 59 - n, n >= 3: the positional mux on its longest controls.

    The mux is built on every table and is the longest candidate, so every other
    form is at most it.  Past the table it is fixed: walk to the field 27, the
    field's init (4 a one after the first zero, 4 the first zero, 2 the end zero:
    4T + 6 at most), a 11-character crossing, a 3.5T - 24 walk, the setters
    9T - 10 - n (weights 6k - 1, pads 1.5k - 1 twice), the relay 24T + 33 + 16.
    The most init is a 0 control row then ones, so ones everywhere but the last
    row (the witness).  Ignoring an input swaps the strip for half its size.
    """
    return 81 * 2**n // 2 + 59 - n


def _steps(n: int, _: str) -> int:
    """B = 71T/2 + 50 - n, met to n = 12; the stored plan ships past it."""
    return 71 * 2**n // 2 + 50 - n


FORMULAS = {
    "scaling": (_chars, True, tuple(range(3, 13))),
    "execution": (_steps, frozenset(range(3, 13)), (3, 4, 5, 6, 7)),
}
