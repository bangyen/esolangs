"""Minifuck's emitted characters: the positional strip.

Execution, ``worst 71T/2 + 50 - n`` (B), n >= 3: steps are the emitted length
minus the collapsed ``[`` (each skips the next command).  By shipped route:

* Ignored inputs: length <= Mx(k) + 25 per ignored input (inert 8, trailing 2,
  gap 12 plus 5 per pad extension), Mx(k) the k-input mux maximum (269 at k = 2,
  M(k) = 81 2**k/2 + 59 - k above, 104 and 99 below); under B for n >= 3
  (observed at most 18 per input, n = 3..8).
* ``two_state``: length <= 90n + 36 (89 a level, 33 to finish, over all 16 value
  lists and all 128 lower-cell states), under B from n = 3.
* ``stored``: each ``[x<[x<[x<[x`` collapses exactly twice (its cell flips to
  not-a, a, not-a, a and a landing on 0 collapses) and no word ends in ``[``,
  so no skip crosses a word and steps <= L - 2R.  The other words are at most
  2R + 32 (per op 2R - 5, checked on a piecewise-linear grid), so
  steps <= (11L + 64)/13, and L <= the positional length <= M: under B from n = 3.
* The mux: the field init, the lookup and the long ``[x`` walk across the field
  are the only table-dependent steps.  A tile costs 1 (a one before the first
  zero), 3 (the first zero), 1 (a later zero), 3 (a later one) steps; the walk
  collapses at cell j when its prefix XOR is 1; the lookup flips the selected
  cell and, on a one, the next.  So steps = U(row, s) + W(controls, row), with s
  the selected control, W a two-state sum and U the table-independent rest.
  Matched on every table and row at n = 3 and on random tables at n = 4..9; the
  maximum of U + max W over rows and bits equals B at n = 3..11 (row T - 1,
  selected control 0, ones elsewhere), so no table exceeds B there.
* Not proved for n > 11: U has no closed form (not additive in the row bits,
  not maximal at one row), so its maximum over 2**n rows is unbounded here.
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


FORMULAS = {"scaling": (_chars, True, tuple(range(3, 13)))}
