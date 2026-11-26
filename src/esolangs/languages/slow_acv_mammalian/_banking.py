"""Route arrays and bank print digits and lookup weights."""

from esolangs.languages.slow_acv_mammalian._sums import (
    _MODULUS,
    _W,
    _advance_heads,
    _print_chunk_seeds,
    _replay,
    _seeds_onto,
    _Sums,
)
from esolangs.languages.slow_acv_mammalian.dialect import ARRAYS as _ARRAYS

#: Per-``SEED`` advance of array 16's head (array ``k``'s head steps by
#: ``k + 1``); 17 is odd, so every residue is reachable.
_W_STEP = _W + 1
#: Low edge of the 17-wide high-residue window greedy chunks aim at.
_GREEDY_MIN = _MODULUS - _W_STEP
#: Seed counts a greedy chunk tries; 16 steps of 17 cover every residue.
_GREEDY_COUNTS = _W_STEP - 1
#: Inverse of the array-16 head step, for solving exact ``SEED`` counts.
_W_INV = pow(_W_STEP, -1, _MODULUS)

#: The print arrays, indexed by the digit their middle cell holds.  A leaf
#: SPRINTs from array 16 with head ``v``, landing on ``(16 + v) % 23``, and
#: one more SEED steps ``v`` by 17, so the pair has to be reachable 17
#: apart: ``(16 + v) % 23 == 18`` puts the next step on 12.  Both are even,
#: which :func:`_exact_append` needs to plant their cells.
_PRINT = (18, 12)

#: Arrays holding one planted weight each, for the bits :func:`_pool_bank`
#: banks.  Even, so their cells can be planted, and distinct from array 0,
#: array 16 and the print arrays.
_POOLS = (2, 4, 6, 8)


def _plant(st: _Sums) -> list[str]:
    """Replay and return the ``EXCRETE`` that plants the accumulator as a cell."""
    _replay(st, ["EXCRETE"])
    return ["EXCRETE"]


def _print_bank(st: _Sums, array: int, digit: int, target: int) -> list[str]:
    """Place the digit in the middle and make the non-head sum the target."""
    route = _route(st, array)
    digit_tokens = _exact_append(st, digit)
    rest = digit
    maximum = st.io_modulus - 1
    step = array + 1
    inverse = pow(step, -1, _MODULUS)
    ballast: list[str] = []

    def append(seeds: int) -> None:
        nonlocal rest
        _advance_heads(st, seeds)
        byte = (st.heads[array] + rest) % st.io_modulus
        st.append(array, byte)
        rest += byte
        ballast.extend(["SEED"] * seeds + ["DIGEST", "EXCRETE"])

    def exact(byte: int) -> None:
        head = (byte - rest) % st.io_modulus
        append((head - st.heads[array]) * inverse % _MODULUS)

    # Each bulk append adds at least 224 with at most 22 tokens. Keep
    # the running sum locally so planting does not rescan the bank.
    while target - rest > 2 * maximum:
        append(_print_chunk_seeds(st.heads[array], step, rest, _MODULUS, st.io_modulus))
    # The initial gap exceeds twice the byte limit. A bulk append adds
    # at most one byte, so the remaining gap still exceeds that limit.
    assert maximum < target - rest <= 2 * maximum
    exact(target - rest - maximum)
    exact(maximum)
    cells = st.cells[array]
    pad = len(cells) - 2
    assert pad >= 0
    assert cells[-1]
    assert rest == target
    # Zero cells before the digit shift it into the position CONSUME reads.
    cells[:0] = [0] * pad
    return [*route, *["EXCRETE"] * pad, *digit_tokens, *ballast]


def _route(st: _Sums, dest: int) -> list[str]:
    """Move the pointer to ``dest``, emitting the tokens that do it.

    ``SPRINT`` adds ``curr[0]`` -- the head -- with a zeroed accumulator,
    and only its residue mod 23 decides where the pointer lands, so the
    seed run is at most a couple of dozen tokens rather than the 255 an
    exact head would cost.  Array 0 is left with the accumulator laundered
    into it, which is where every route starts.
    """
    tokens: list[str] = []
    here = st.ptr
    if st.acc:
        tokens = ["DIGEST", "EXCRETE"]
        _replay(st, tokens)
    run = [*["SEED"] * (_route_len(st.heads[here], here, dest) - 1), "SPRINT"]
    _replay(st, run)
    if st.ptr != dest:  # pragma: no cover - the residue solve is exact
        raise AssertionError(f"route to {dest} landed on {st.ptr}")
    return tokens + run


def _route_len(head: int, here: int, dest: int) -> int:
    """Token count :func:`_route` spends from head ``head``, accumulator 0.

    Every routed array has an even index, so its step ``here + 1`` is odd.
    """
    want = (dest - here) % _ARRAYS
    return _seeds_onto(head, here + 1, range(want, _MODULUS, _ARRAYS)) + 1


def _exact_append(st: _Sums, value: int) -> list[str]:
    """Append exactly ``value`` to the current array, which must be even.

    ``SEED`` steps array ``k``'s head by ``k + 1``, so the solve needs that
    step to be invertible mod 256 -- true exactly for the even arrays.
    """
    arr = st.ptr
    if arr % 2:  # pragma: no cover - every planted array is even by choice
        raise AssertionError(f"array {arr} has an even seed step")
    before = st.rest(arr)
    head = (value - before) % st.io_modulus
    count = ((head - st.heads[arr]) * pow(arr + 1, -1, _MODULUS)) % _MODULUS
    tokens = _digest_excrete(st, count)
    if st.rest(arr) - before != value:  # pragma: no cover - the inverse is exact
        raise AssertionError(f"planted {st.rest(arr) - before}, wanted {value}")
    return tokens


def _digest_excrete(st: _Sums, count: int) -> list[str]:
    """Append ``count`` ``SEED``s, ``DIGEST`` and ``EXCRETE``, replayed onto ``st``."""
    tokens = [*["SEED"] * count, "DIGEST", "EXCRETE"]
    _replay(st, tokens)
    return tokens


def _w_exact_chunk(st: _Sums, value: int) -> list[str]:
    """Append exactly ``value`` to array 16's non-head sum."""
    if st.io_modulus == 255:
        return _exact_append(st, value)
    count = ((value - st.hw - st.nw) * _W_INV) % _MODULUS
    before = st.nw
    tokens = _digest_excrete(st, count)
    if st.nw - before != value:  # pragma: no cover - the inverse is exact
        raise AssertionError(f"chunk appended {st.nw - before}, wanted {value}")
    return tokens


def _w_greedy_chunk(st: _Sums) -> list[str]:
    """Append a high residue for at most 15 ``SEED``s.

    Head steps by 17, so 16 counts always hit the 17-wide window [239, 255].
    """
    if st.io_modulus == 255:
        # Folding 256 head positions into 255 residues leaves no gap over 17.
        heads = (
            head
            for byte in range(255 - _W_STEP, 255)
            for head in range((byte - st.nw) % 255, _MODULUS, 255)
        )
        count = _seeds_onto(st.hw, _W_STEP, heads)
        if count >= _GREEDY_COUNTS:  # pragma: no cover
            raise AssertionError("no 17-step residue in [238, 254]")
        return _digest_excrete(st, count)
    return _digest_excrete(st, _greedy_step((st.hw + st.nw) % _MODULUS))


def _w_raise(st: _Sums, amount: int) -> list[str]:
    """Raise array 16's non-head sum by exactly ``amount >= 0``.

    Greedy chunks close all but two maximum residues; exact chunks finish:
    about a token per 14 of weight, never overshot.
    """
    tokens: list[str] = []
    end = st.nw + amount
    maximum = st.io_modulus - 1
    while end - st.nw > 2 * maximum:
        tokens += _w_greedy_chunk(st)
    if end - st.nw > maximum:
        tokens += _w_exact_chunk(st, end - st.nw - maximum)
    if end - st.nw:
        tokens += _w_exact_chunk(st, end - st.nw)
    return tokens


def _greedy_step(r: int) -> int:
    """Return the steps to the first 17-step hit in [239, 255], without wrapping."""
    return max(0, -(-(_GREEDY_MIN - r) // _W_STEP))


def _pool_plan(delta: int, pool: int) -> list[int]:
    """Return the cells of ``pool`` whose CONSUME-then-SPRINT banks ``delta``.

    ``CONSUME`` takes the middle cell, so the middle holds ``delta``
    itself; the ``SPRINT`` that follows indexes the array *by that value*,
    so cell ``delta`` holds the hop to array 16.  Two cells and a bed of
    zeros: laid out at ``2 * delta + 2`` cells the middle lands one past
    ``delta``, which keeps the planted hop below the hole ``CONSUME``
    leaves and therefore still at index ``delta``.
    """
    cells = [0] * (2 * delta + 2)
    cells[delta - 1] = (_W - pool) % _ARRAYS
    cells[delta] = delta
    return cells


def _build_pool(st: _Sums, delta: int, pool: int) -> list[str]:
    """Emit the prologue that lays ``pool`` out for :func:`_pool_bank`."""
    tokens = _route(st, pool)
    for cell in _pool_plan(delta, pool):
        tokens += _exact_append(st, cell) if cell else _plant(st)
    tokens += _route(st, 0)
    return tokens


def _pool_bank(st: _Sums, delta: int, pool: int) -> list[str]:
    """Bank ``delta`` on array 16 without reading array 16's sum.

    ``CONSUME`` loads the planted ``delta`` into the accumulator,
    ``SPRINT`` rides the cell it indexes over to array 16, and ``EXCRETE``
    drops the same byte there.  Nothing in the run depends on what array
    16 already holds, which is the whole point: a weight banked this way
    may be any byte, so the leaf table's stride is a leaf and not the 256
    a solved chunk would force.
    """
    tokens = _route(st, pool)
    run = ["CONSUME", "SPRINT", "EXCRETE"]
    before = st.nw
    _replay(st, run)
    if st.ptr != _W or st.nw - before != delta:
        raise AssertionError(f"the pool banked {st.nw - before}, wanted {delta}")
    return tokens + run + _route(st, 0)


def _arm_core(st: _Sums, weight: int, pool: int | None) -> list[str]:
    """Return the 1-branch's banking run: out to the weight, back to array 0."""
    if pool is not None:
        return _pool_bank(st, weight, pool)
    tokens = _route(st, _W)
    tokens += _w_raise(st, weight)
    return tokens + _route(st, 0)


def _dispatch_head(st: _Sums) -> int:
    """Seeds putting array 16's head on the class both print arrays need.

    The second leaf adds one SEED, so the first head must leave room for
    the step of 17 without wrapping.
    """
    want = (_PRINT[0] - _W) % _ARRAYS
    return _seeds_onto(st.hw, _W_STEP, range(want, _GREEDY_MIN, _ARRAYS))
