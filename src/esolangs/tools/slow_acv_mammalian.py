"""Boolean-function generator for SLOW ACV MAMMALIAN.

A *chain* of ``n`` read nodes and one dispatch jump into a table of
eight-token leaf slots: O(T) size and build, where the tree it replaced was
super-linear (``S(d) >= (2 + 1/255) S(d-1)``).  Three identities carry the
control flow, machine-verified end to end over every table through
``n == 3``:

``landing = start - 15``
    A read node is ``SEED*wrap EXCRETE SEED*j1 DIGEST SEED*16 DIGEST
    ACCEPT DIGEST LEAPFROG``; on :func:`_aim`'s class the 1-branch resumes
    15 tokens short and ``j1`` cancels (see :func:`_node`).

``target = nonhead + b``
    ``LEAPFROG`` targets ``acc - head - 1`` and a fresh ``DIGEST`` folds
    the head in, so an unconditional jump lands on the non-head sum plus
    its own appended byte.

``leaf = nonhead of array 16``
    The same identity with nothing appended: the dispatch raises array
    16's non-head sum to the leaf table's own address before a bit is
    read, so ``DIGEST LEAPFROG`` alone lands run ``row`` on
    ``base + sum of the weights its ones banked``.  Nothing after the
    weights solves against that sum, which is what lets a weight be a
    value other than a multiple of 256 (:func:`_weights`).

A bit's whole effect is banked on array 16's non-head sum; both branches
leave through trampolines aimed at one merge address (so array 0's sums
agree exactly) and the 1-arm's tuning chunk (:func:`_arm`) zeroes the even
head residue at slope -2.  The five lightest weights are banked without
reading the sum at all -- :func:`_pool_bank` CONSUMEs a planted cell and
rides it to array 16 -- so they may be any byte, and the leaf slot rather
than 256 sets the table's stride.

The leaf itself never reads the sum either: it clears the accumulator,
SPRINTs to a print array whose middle cell holds ``'0'`` or ``'1'``, and
CONSUMEs it.  Six or seven tokens, the same for every row.

Everything is closed-form; the bounded fixed points raise if they do not
settle, and the merge equalities are asserted on every build.  Executed
evidence: every table through ``n == 3``, plus sampled rows of dense
tables through ``n == 12``.  All ``n`` inputs are read unconditionally.
"""

from collections.abc import Sequence

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["slow_acv_mammalian"]

#: How many arrays the machine has; ``SPRINT`` moves the pointer mod this.
_ARRAYS = 23

# The byte a stash chunk appends.  It is what raises the sum, and the sum is
# what puts a distant token index within a jump's reach, so the chunk buys
# the most reach per token by appending the largest byte there is.
_STASH_BYTE = 255

# The read node's second seed run.  The aim class fixes ``first & 48 == 16``,
# and XORing bits 4-5 from ``01`` to ``10`` is ``+16``, so this run is what
# lands the accumulator on the clean digit 48 -- it is not a free knob.
_J2 = 16

# The weight array.  It is one of the construction's free arrays, and SEED
# steps its head by 17 -- odd, so every residue is reachable.
_W = 16
_W_STEP = _W + 1
_W_INV = pow(_W_STEP, -1, 256)

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

#: One leaf slot, in tokens.  The longest leaf is seven (the ``'1'`` arm
#: spends one SEED reaching the second print array), and the weights below
#: 256 have to be ``_LEAF_UNIT * 2**k``, so a power of two it is.
_LEAF_UNIT = 8

#: How many weights can sit under 256 at that unit: 8, 16, 32, 64 and 128.
#: One of them is banked by :func:`_w_raise` and the rest from pools, which
#: is why there is exactly one more of them than there are pools.
_FREE = len(_POOLS) + 1

#: A machine state as the generator tracks it: array 0 and the accumulator.
type _State = tuple[list[int], int]


def _seeded(array: Sequence[int], count: int) -> list[int]:
    """``array`` after ``count`` ``SEED``s, which only move the head."""
    out = list(array)
    out[0] = (out[0] + count) % 256
    return out


def _stash_chunk(array: list[int], acc: int) -> tuple[list[str], list[int], int]:
    """``SEED*k DIGEST EXCRETE``, appending exactly ``_STASH_BYTE``.

    The sum's low byte advances by one per ``SEED`` even across a head
    wrap, so the count solves in one step; from the third chunk on every
    count is 1, so a chunk is 3 tokens for 255 of reach.
    """
    count = (((acc % 256) ^ _STASH_BYTE) - sum(array)) % 256
    return (
        [*["SEED"] * count, "DIGEST", "EXCRETE"],
        [*_seeded(array, count), _STASH_BYTE],
        0,
    )


def _aim(start: int) -> int:
    """Return the seed count putting ``start + j1`` on the aim class.

    Even values whose bits 4-5 are ``01``: 16 residues per 256, at most 49
    apart, so the head stays far under the 255 a mid-run wrap needs.
    """
    offset = (start - _J2) % 64
    if offset <= 14:
        # Inside a class block; an odd ``start`` steps to the next even.
        return start % 2
    return 64 - offset


def _node(array: list[int], acc: int) -> tuple[list[str], _State, _State, int]:
    """One read node: tokens, the 0-exit, the 1-exit, and the landing.

    The 0-branch falls through with ``acc == first``; the 1-branch jumps
    to ``start - 15`` with ``acc == first + 1``.  Neither exit depends on
    ``j1``, so the landing commits before the arm and merge exist.
    """
    wrap = (256 - array[0]) % 256
    opened = [*_seeded(array, wrap), acc % 256]
    start = sum(opened)
    j1 = _aim(start)
    first = start + j1
    tokens = [
        *["SEED"] * wrap,
        "EXCRETE",
        *["SEED"] * j1,
        "DIGEST",
        *["SEED"] * _J2,
        "DIGEST",
        "ACCEPT",
        "DIGEST",
        "LEAPFROG",
    ]
    loaded = _seeded(opened, j1 + _J2)
    return tokens, ([*loaded, 0], first), ([*loaded, 1], first + 1), start - 15


def _trampoline(
    array: list[int], acc: int, target: int
) -> tuple[list[str], list[int], int]:
    """Build an unconditional jump to token ``target``, plus its exit state.

    Chunks raise the non-head sum by 255 each until ``target`` is within a
    byte, then ``u`` is solved so the ``EXCRETE`` appends the closing
    ``b``.  ``b >= 1`` keeps the ``LEAPFROG`` firing; callers always aim
    past the sum they enter with.  ``rest_sum`` is ``sum(cur) - cur[0]``
    carried incrementally: each chunk appends exactly one new element
    (``_STASH_BYTE``) and touches no other, so re-summing the growing
    list every iteration -- as a naive read of the loop condition would
    -- costs O(chunks**2) for no reason.
    """
    cur, val, tokens = list(array), acc, []
    rest_sum = sum(cur[1:])
    while rest_sum < target - 255:
        chunk, cur, val = _stash_chunk(cur, val)
        rest_sum += _STASH_BYTE
        tokens += chunk
    hop = target - rest_sum
    if not 1 <= hop <= 255:  # pragma: no cover - the window solve is exact
        raise AssertionError(f"trampoline byte {hop} escaped 1..255")
    count = (((val % 256) ^ hop) - (cur[0] + rest_sum)) % 256
    tokens += [*["SEED"] * count, "DIGEST", "EXCRETE", "DIGEST", "LEAPFROG"]
    out = [(cur[0] + count) % 256, *cur[1:], hop]
    return tokens, out, sum(out)


def _trampoline_len(array: list[int], acc: int, target: int) -> int:
    """Token count :func:`_trampoline` would emit reaching ``target``, O(1).

    The first two chunks solve a residue from ``acc``; every chunk after
    that always spends exactly one ``SEED`` (verified against
    :func:`_stash_chunk` directly), so the tail is closed by division
    instead of walked -- what lets the per-node retry search check a
    candidate landing without paying for the trampoline it would build.
    """
    cur, val = list(array), acc
    tokens = 0
    rest_sum = sum(cur[1:])
    for _ in range(2):
        if rest_sum >= target - 255:
            break
        chunk, cur, val = _stash_chunk(cur, val)
        rest_sum += _STASH_BYTE
        tokens += len(chunk)
    if rest_sum < target - 255:
        more = -(-(target - 255 - rest_sum) // _STASH_BYTE)
        tokens += 3 * more
        rest_sum += _STASH_BYTE * more
        cur = [(cur[0] + more) % 256, *cur[1:]]
    hop = target - rest_sum
    count = (((val % 256) ^ hop) - (cur[0] + rest_sum)) % 256
    return tokens + count + 4


class _Sums:
    """Build-time machine state: heads, the two big sums, the small cells.

    Arrays 0 and 16 are only ever read through ``DIGEST`` and through
    ``SPRINT``'s ``curr[0]``, so a head and a non-head sum say everything
    about them.  The pool and print arrays *are* indexed, by ``CONSUME``
    and by ``SPRINT``'s ``curr[acc]``, so those carry their cells.
    """

    __slots__ = ("acc", "cells", "heads", "n0", "nw", "ptr")

    def __init__(self) -> None:
        self.heads = [0] * _ARRAYS
        self.cells: dict[int, list[int]] = {}
        self.n0 = self.nw = self.acc = self.ptr = 0

    def clone(self) -> "_Sums":
        out = _Sums.__new__(_Sums)
        out.heads = list(self.heads)
        out.cells = {key: list(val) for key, val in self.cells.items()}
        out.n0, out.nw, out.acc, out.ptr = self.n0, self.nw, self.acc, self.ptr
        return out

    @property
    def h0(self) -> int:
        """Return array 0's head."""
        return self.heads[0]

    @property
    def hw(self) -> int:
        """Return array 16's head."""
        return self.heads[_W]

    @hw.setter
    def hw(self, value: int) -> None:
        self.heads[_W] = value

    def arr0(self) -> list[int]:
        """Array 0 as the two-cell stand-in the sum arithmetic works on."""
        return [self.heads[0], self.n0]

    def rest(self, arr: int) -> int:
        """Return the non-head sum of array ``arr``."""
        if arr == 0:
            return self.n0
        if arr == _W:
            return self.nw
        return sum(self.cells.get(arr, ()))

    def append(self, arr: int, byte: int) -> None:
        """Append ``byte`` to array ``arr``, as ``EXCRETE`` does."""
        if arr == 0:
            self.n0 += byte
        elif arr == _W:
            self.nw += byte
        else:
            self.cells.setdefault(arr, []).append(byte)

    def full(self, arr: int) -> list[int]:
        """Return array ``arr`` cell by cell; only small arrays have cells."""
        return [self.heads[arr], *self.cells.get(arr, ())]


def _replay(st: _Sums, tokens: Sequence[str], bit: int = 0) -> None:
    """Apply a token run to ``st``.  ``LEAPFROG`` moves only the cursor."""
    seeds = 0
    for tok in tokens:
        if tok == "SEED":
            seeds += 1
            continue
        if seeds:
            for arr in range(_ARRAYS):
                st.heads[arr] = (st.heads[arr] + (arr + 1) * seeds) % 256
            seeds = 0
        _apply(st, tok, bit)
    for arr in range(_ARRAYS):
        st.heads[arr] = (st.heads[arr] + (arr + 1) * seeds) % 256


def _apply(st: _Sums, tok: str, bit: int) -> None:
    """Apply one non-``SEED`` token to ``st``."""
    if tok == "DIGEST":
        st.acc ^= st.heads[st.ptr] + st.rest(st.ptr)
    elif tok == "EXCRETE":
        st.append(st.ptr, st.acc % 256)
        st.acc = 0
    elif tok == "ACCEPT":
        if st.acc % 256 != 48:
            raise AssertionError(f"ACCEPT entered with acc % 256 == {st.acc % 256}")
        st.n0 += bit
    elif tok == "CONSUME":
        cells = st.cells[st.ptr]
        mid = len(cells) // 2
        if mid < 1:  # pragma: no cover - the pools are built long enough
            raise AssertionError("CONSUME would take the head")
        st.acc = cells.pop(mid - 1)
    elif tok == "SPRINT":
        cells = st.full(st.ptr)
        if not 0 <= st.acc < len(cells):
            raise AssertionError(f"SPRINT index {st.acc} outside array {st.ptr}")
        st.ptr = (st.ptr + cells[st.acc]) % _ARRAYS


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
    want = (dest - here) % _ARRAYS
    step = here + 1
    for count in range(256):
        if ((st.heads[here] + step * count) % 256) % _ARRAYS == want:
            run = [*["SEED"] * count, "SPRINT"]
            _replay(st, run)
            if st.ptr != dest:  # pragma: no cover - the residue solve is exact
                raise AssertionError(f"route to {dest} landed on {st.ptr}")
            return tokens + run
    raise AssertionError(f"no seed count routes {here} to {dest}")  # pragma: no cover


def _route_len(head: int, here: int, dest: int) -> int:
    """Token count :func:`_route` spends from head ``head``, accumulator 0."""
    want = (dest - here) % _ARRAYS
    step = here + 1
    for count in range(256):
        if ((head + step * count) % 256) % _ARRAYS == want:
            return count + 1
    raise AssertionError(f"no seed count routes {here} to {dest}")  # pragma: no cover


def _exact_append(st: _Sums, value: int) -> list[str]:
    """Append exactly ``value`` to the current array, which must be even.

    ``SEED`` steps array ``k``'s head by ``k + 1``, so the solve needs that
    step to be invertible mod 256 -- true exactly for the even arrays.
    """
    arr = st.ptr
    if arr % 2:  # pragma: no cover - every planted array is even by choice
        raise AssertionError(f"array {arr} has an even seed step")
    count = ((value - st.heads[arr] - st.rest(arr)) * pow(arr + 1, -1, 256)) % 256
    tokens = [*["SEED"] * count, "DIGEST", "EXCRETE"]
    before = st.rest(arr)
    _replay(st, tokens)
    if st.rest(arr) - before != value:  # pragma: no cover - the inverse is exact
        raise AssertionError(f"planted {st.rest(arr) - before}, wanted {value}")
    return tokens


def _w_exact_chunk(st: _Sums, value: int) -> list[str]:
    """Append exactly ``value`` (1..255) to array 16's non-head sum."""
    count = ((value - st.hw - st.nw) * _W_INV) % 256
    tokens = [*["SEED"] * count, "DIGEST", "EXCRETE"]
    before = st.nw
    _replay(st, tokens)
    if st.nw - before != value:  # pragma: no cover - the inverse is exact
        raise AssertionError(f"chunk appended {st.nw - before}, wanted {value}")
    return tokens


def _w_greedy_chunk(st: _Sums) -> list[str]:
    """Append a byte of at least 239 for at most 15 ``SEED``s.

    Head steps by 17, so 16 counts always hit the 17-wide window [239, 255].
    """
    for count in range(16):
        if (st.hw + st.nw + _W_STEP * count) % 256 >= 239:
            tokens = [*["SEED"] * count, "DIGEST", "EXCRETE"]
            _replay(st, tokens)
            return tokens
    raise AssertionError("no 17-step residue in [239, 255]")  # pragma: no cover


def _w_raise(st: _Sums, amount: int) -> list[str]:
    """Raise array 16's non-head sum by exactly ``amount >= 0``.

    Greedy chunks close all but the last 510, two exact chunks finish:
    about a token per 14 of weight, never overshot.
    """
    tokens: list[str] = []
    end = st.nw + amount
    while end - st.nw > 510:
        tokens += _w_greedy_chunk(st)
    if end - st.nw > 255:
        tokens += _w_exact_chunk(st, end - st.nw - 255)
    if end - st.nw:
        tokens += _w_exact_chunk(st, end - st.nw)
    return tokens


def _greedy_step_table() -> tuple[tuple[int, int], ...]:
    """For each residue ``r``, the greedy chunk's ``(seed count, added byte)``.

    Derived directly from :func:`_w_greedy_chunk`'s own search, not fit to
    any table of programs -- 256 residues, once, at import time.
    """
    table = []
    for r in range(256):
        for count in range(16):
            added = (r + _W_STEP * count) % 256
            if added >= 239:
                table.append((count, added))
                break
        else:  # pragma: no cover - argued in _w_greedy_chunk's docstring
            raise AssertionError(f"no 17-step residue in [239, 255] from {r}")
    return tuple(table)


_GREEDY_STEP = _greedy_step_table()


def _greedy_advance(r: int, target: int) -> tuple[int, int, int, int]:
    """Fast-forward the greedy phase: total SEEDs and advance past ``target``.

    A chunk's added byte depends only on the residue ``r = (hw + nw) %
    256`` (:func:`_greedy_step_table`), and the next residue is always
    ``2 * added % 256`` -- multiply out ``r' = (r + 17*count + added) %
    256`` where ``added = (r + 17*count) % 256`` and the ``17*count``
    terms cancel mod 256.  That orbit lives in 256 states, so simulating
    it must repeat a residue within 256 steps; once it does, the repeat's
    span is a cycle whose whole-multiples are skipped by multiplication
    instead of being walked, which is what makes this O(1) in ``target``
    rather than O(target / 247) like :func:`_w_raise`'s direct loop.
    Returns ``(seed count, chunk count, byte advance, final residue)``.
    """
    if target <= 0:
        return 0, 0, 0, r
    seen: dict[int, tuple[int, int, int]] = {}
    steps = seed_count = advance = 0
    while advance < target:
        if r in seen:
            prev_steps, prev_seeds, prev_advance = seen[r]
            cyc_steps = steps - prev_steps
            cyc_seeds = seed_count - prev_seeds
            cyc_advance = advance - prev_advance
            full = (target - advance - 1) // cyc_advance
            if full > 0:
                steps += full * cyc_steps
                seed_count += full * cyc_seeds
                advance += full * cyc_advance
            seen = {}  # landed back on the same r; walk the remainder plainly
            continue
        seen[r] = (steps, seed_count, advance)
        count, added = _GREEDY_STEP[r]
        seed_count += count
        steps += 1
        advance += added
        r = (2 * added) % 256
    return seed_count, steps, advance, r


def _w_raise_len(hw: int, nw: int, amount: int) -> tuple[int, int]:
    """``(token count, final hw)`` for :func:`_w_raise`'s effect, in O(1).

    Mirrors ``_w_raise`` exactly -- same chunk boundaries, same byte
    values -- but the greedy phase is closed by :func:`_greedy_advance`
    instead of walked chunk by chunk.  Sizing an arm's slot only needs
    this length and the resulting head, never the token text itself.
    """
    r = (hw + nw) % 256
    target = max(0, amount - 510)
    total_seeds, chunks, greedy_advance_amt, r = _greedy_advance(r, target)
    remaining = amount - greedy_advance_amt
    if remaining > 255:
        value = remaining - 255
        count = ((value - r) * _W_INV) % 256
        total_seeds += count
        chunks += 1
        r = (2 * value) % 256
        remaining = 255
    if remaining:
        value = remaining
        count = ((value - r) * _W_INV) % 256
        total_seeds += count
        chunks += 1
    tokens = total_seeds + 2 * chunks
    final_hw = (hw + _W_STEP * total_seeds) % 256
    return tokens, final_hw


def _jump(st: _Sums, target: int) -> list[str]:
    """Emit an array-0 trampoline to ``target`` and replay it onto ``st``."""
    tokens, out_arr, out_acc = _trampoline(st.arr0(), st.acc, target)
    _replay(st, tokens)
    if (st.h0, st.n0, st.acc) != (out_arr[0], sum(out_arr[1:]), out_acc):
        raise AssertionError("sum replay diverged from the trampoline model")
    return tokens


def _weights(n: int) -> list[int]:
    """Return the weight each read node banks, in read order.

    The last ``_FREE`` bits carry the weights under 256 -- the one a
    :func:`_w_raise` arm banks first, then one per pool -- and the bits
    before them carry ``256 * 2**k``.  Any weight a later arm's solve
    would see has to be a multiple of 256, so the order is forced: a
    ``_w_raise`` arm reads array 16's sum, and the pool arms never do.
    The whole set is ``_LEAF_UNIT`` times the powers of two, so the banked
    total is a leaf slot times the row.
    """
    free = min(n, _FREE)
    fixed = n - free
    weights = [256 * (1 << (fixed - 1 - i)) for i in range(fixed)]
    return weights + [_LEAF_UNIT * (1 << k) for k in range(free)]


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
        if cell:
            tokens += _exact_append(st, cell)
            continue
        _replay(st, ["EXCRETE"])
        tokens += ["EXCRETE"]
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


def _arm(
    one: _Sums, weight: int, pool: int | None, beta: int, cont: int
) -> tuple[list[str], _Sums]:
    """Build the 1-branch: bank ``weight`` and merge at ``cont``.

    The tuning chunk's ``beta`` shifts this path's SEED count at slope -2,
    the knob that matches the 0-path's heads.
    """
    st = one.clone()
    tokens = _arm_core(st, weight, pool)
    run = [*["SEED"] * ((beta - st.h0 - st.n0) % 256), "DIGEST", "EXCRETE"]
    _replay(st, run)
    tokens += run
    tokens += _jump(st, cont)
    return tokens, st


def _arm_core_len(st: _Sums, weight: int, pool: int | None) -> int:
    """Token count :func:`_arm_core` would spend, without building it."""
    launder = 2 if st.acc else 0
    out = _route_len(st.heads[0], 0, pool if pool is not None else _W)
    if pool is not None:
        return launder + out + 3 + _route_len(st.heads[pool], pool, 0)
    hw = (st.hw + _W_STEP * (out - 1)) % 256
    raise_len, final_hw = _w_raise_len(hw, st.nw, weight)
    return launder + out + raise_len + _route_len(final_hw, _W, 0)


def _leaf(digit: int) -> list[str]:
    """Return the tokens run ``digit`` executes, padded to one slot.

    ``EXCRETE`` clears the accumulator the dispatch left, the ``SPRINT``
    rides array 16's head to a print array, ``CONSUME`` lifts its middle
    cell -- ``'0'`` or ``'1'`` -- and ``PRONOUNCE`` writes it.  The
    closing ``EXCRETE`` leaves a nonzero cell so the ``LEAPFROG`` fires,
    and with a zero accumulator it can only aim before the program, which
    halts the run.  One SEED separates the two print arrays
    (:func:`_dispatch_head`), so the digit *is* the step count, and
    nothing here reads array 16's sum: every leaf is the same length
    whatever row reached it.
    """
    body = [
        "EXCRETE",
        *["SEED"] * digit,
        "SPRINT",
        "CONSUME",
        "PRONOUNCE",
        "EXCRETE",
        "LEAPFROG",
    ]
    return [*body, *["SEED"] * (_LEAF_UNIT - len(body))]


def _dispatch_head(hw: int) -> int:
    """Seeds putting array 16's head on the class both print arrays need.

    A leaf SPRINTs with the head as written and the other leaf one SEED
    later, so the head has to land on ``_PRINT[0]``'s residue *and* stay
    below 239 -- past that the extra 17 wraps and the second leaf misses.
    """
    want = (_PRINT[0] - _W) % _ARRAYS
    for count in range(256):
        value = (hw + _W_STEP * count) % 256
        if value % _ARRAYS == want and value <= 238:
            return count
    raise AssertionError("no seed count aims the leaf pair")  # pragma: no cover


def _prologue(st: _Sums, pairs: Sequence[tuple[int, int]], base: int) -> list[str]:
    """Plant the print arrays and pools, then raise array 16 to ``base``.

    The raise happens *before* the first read, which is what leaves the
    dispatch with nothing to solve: array 16's non-head sum already names
    the leaf table, and the weights only push it along.
    """
    tokens: list[str] = []
    for digit, arr in enumerate(_PRINT):
        tokens += _route(st, arr)
        tokens += _exact_append(st, _ASCII_ZERO + digit)
        _replay(st, ["EXCRETE"])
        tokens += ["EXCRETE"]
        tokens += _route(st, 0)
    for weight, pool in pairs:
        tokens += _build_pool(st, weight, pool)
    tokens += _route(st, _W)
    tokens += _w_raise(st, base - st.nw)
    return tokens + _route(st, 0)


def _level(
    st: _Sums, weight: int, pool: int | None, pos: int
) -> tuple[list[str], _Sums, int]:
    """Emit one read node with both of its branches, merged at ``cont``.

    The node is preceded by as much ballast as its landing needs to clear
    the 0-branch's trampoline: the landing is array 0's own sum, so a
    stash chunk buys 255 of it for three tokens once the residue settles.
    """
    tokens: list[str] = []
    while True:
        node_toks, _, _, landing = _node(st.arr0(), st.acc)
        node_end = pos + len(node_toks)
        zero, one = st.clone(), st.clone()
        _replay(zero, node_toks, bit=0)
        _replay(one, node_toks, bit=1)
        arm_toks, merged, cont = _settle(one, zero, weight, pool, landing)
        reach = len(_lead(zero)) + _trampoline_len(_laundered(zero).arr0(), 0, cont)
        if landing >= node_end + reach:
            break
        chunk, _, _ = _stash_chunk(st.arr0(), st.acc)
        _replay(st, chunk)
        tokens += chunk
        pos += len(chunk)

    z = _laundered(zero)
    t0 = _lead(zero) + _jump(z, cont)
    _check_merge(merged, z, weight)
    tokens += node_toks + t0
    tokens += ["SEED"] * (landing - node_end - len(t0))
    return tokens + arm_toks, z, cont


def _lead(st: _Sums) -> list[str]:
    """Return the tokens emptying a branch's accumulator before its trampoline.

    A trampoline's closing solve leaves ``head == (acc ^ hop) + hop -
    cont``, which is ``2 * hop - cont`` -- and so even, whatever the hop
    -- only when it enters with a cleared accumulator.  The 1-arm always
    does, because its tuning chunk ends in ``EXCRETE``; the 0-branch
    arrives holding the node's sum, and without this the two heads differ
    by an odd number that :func:`_tune`'s slope of -2 can never close.
    """
    return ["DIGEST", "EXCRETE"] if st.acc else []


def _laundered(st: _Sums) -> _Sums:
    """``st`` after :func:`_lead`, which is ``st`` itself when it is clear."""
    out = st.clone()
    _replay(out, _lead(st))
    return out


def _settle(
    one: _Sums, zero: _Sums, weight: int, pool: int | None, landing: int
) -> tuple[list[str], _Sums, int]:
    """Build the arm and let its own length name the merge address.

    Both branches have to leave through one address, and the arm sits at
    the landing, so the merge is ``landing + len(arm)`` -- a self
    reference, since the arm's closing trampoline is what reaches it.
    The search walks that reference instead of reserving a bound: a bound
    wide enough for the worst tuning chunk and the worst trampoline is
    twice what a level actually spends, and the difference was emitted as
    dead SEEDs on every level.  Aiming too close is what fails, since a
    trampoline can only reach *past* array 0's running sum, so a failed
    build widens the slot and the narrowest arm that fits is kept.
    """
    slot = _arm_core_len(one, weight, pool) + 300
    for _ in range(24):
        built = _try_arm(one, zero, weight, pool, landing + slot)
        if built is not None and len(built[0]) <= slot:
            break
        slot = max(slot + 128, len(built[0]) if built else 0)
    else:  # pragma: no cover - widening always reaches a fit
        raise AssertionError("the arm slot did not settle")
    arm_toks, merged = built
    tight = _try_arm(one, zero, weight, pool, landing + len(arm_toks))
    if tight is not None and len(tight[0]) == len(arm_toks):
        return tight[0], tight[1], landing + len(arm_toks)
    return (
        [*arm_toks, *["SEED"] * (slot - len(arm_toks))],
        merged,
        landing + slot,
    )


def _try_arm(
    one: _Sums, zero: _Sums, weight: int, pool: int | None, cont: int
) -> tuple[list[str], _Sums] | None:
    """Build the arm merging at ``cont``, or ``None`` if it cannot reach it.

    A trampoline only aims past array 0's running sum, and the tuning
    chunk's own byte raises that sum, so a merge address too close to the
    landing has no solution at all.  That is a question about ``cont``,
    not an error, so the search reads it as one.
    """
    try:
        return _tune(one, zero, weight, pool, cont)
    except AssertionError:
        return None


def _tune(
    one: _Sums, zero: _Sums, weight: int, pool: int | None, cont: int
) -> tuple[list[str], _Sums]:
    """Build the arm, moving ``beta`` until the two branches' heads agree.

    The delta is always even (both paths' final solves leave ``head0 ==
    2*hop - cont``) and beta moves it at slope -2; a chunk-count boundary
    can shift the structure under the solve, which the loop absorbs.
    """
    z = _laundered(zero)
    _jump(z, cont)
    beta = _STASH_BYTE
    for _ in range(8):
        arm_toks, merged = _arm(one, weight, pool, beta, cont)
        delta = (merged.h0 - z.h0) % 256
        if delta == 0:
            return arm_toks, merged
        if delta % 2:  # pragma: no cover - see the evenness argument
            raise AssertionError(f"odd head delta {delta}")
        beta = (beta + delta // 2) % 256
    raise AssertionError("the tuning byte did not settle")  # pragma: no cover


def _check_merge(merged: _Sums, zero: _Sums, weight: int) -> None:
    """Both branches must arrive with one state, up to the banked weight."""
    if merged.heads != zero.heads or merged.acc != zero.acc or merged.n0 != zero.n0:
        raise AssertionError("the branch paths did not merge")
    if merged.nw - zero.nw != weight or merged.ptr or zero.ptr:
        raise AssertionError(f"the banked weight drifted by {merged.nw - zero.nw}")


def slow_acv_mammalian(truth_table: str) -> str:
    """Build a SLOW ACV MAMMALIAN program evaluating ``truth_table``.

    One read node per input (``ACCEPT``), one dispatch jump, one
    eight-token leaf slot per entry: O(T) text.
    """
    n = _validate_truth_table(truth_table)
    weights = _weights(n)
    free = min(n, _FREE)
    pools: list[int | None] = [None] * (n - free + 1) + list(_POOLS[: free - 1])
    base = 0
    for _ in range(12):
        tokens = _emit(truth_table, weights, pools, base)
        leaf_start = len(tokens) - _LEAF_UNIT * len(truth_table)
        if leaf_start == base:
            return " ".join(_with_leaves(tokens, truth_table, weights))
        base = max(leaf_start, base)
    raise AssertionError("the leaf base did not settle")  # pragma: no cover


def _emit(
    truth_table: str, weights: Sequence[int], pools: Sequence[int | None], base: int
) -> list[str]:
    """Return everything but the leaf bodies: prologue, chain, dispatch, pad."""
    st = _Sums()
    pairs = [(w, p) for w, p in zip(weights, pools, strict=True) if p is not None]
    tokens = _prologue(st, pairs, base)
    pos = len(tokens)
    for weight, pool in zip(weights, pools, strict=True):
        level, st, pos = _level(st, weight, pool, pos)
        tokens += level
        if len(tokens) != pos:  # pragma: no cover - the merge address is the length
            raise AssertionError(f"level ended at {len(tokens)}, merged at {pos}")
    tokens += _route(st, _W)
    tail = [*["SEED"] * _dispatch_head(st.hw), "DIGEST", "LEAPFROG"]
    _replay(st, tail)
    tokens += tail
    if st.nw != base:  # pragma: no cover - the prologue raise is exact
        raise AssertionError(f"the dispatch sum is {st.nw}, not {base}")
    if (_W + st.hw) % _ARRAYS != _PRINT[0] or (
        _W + (st.hw + _W_STEP) % 256
    ) % _ARRAYS != _PRINT[1]:  # pragma: no cover - _dispatch_head solves both
        raise AssertionError(f"head {st.hw} misses the print pair")
    tokens += ["SEED"] * max(0, base - len(tokens))
    return tokens + ["SEED"] * (_LEAF_UNIT * len(truth_table))


def _with_leaves(
    tokens: list[str], truth_table: str, weights: Sequence[int]
) -> list[str]:
    """Overwrite the padded tail with one leaf per row, at its own slot."""
    out = tokens[: len(tokens) - _LEAF_UNIT * len(truth_table)]
    slots = [""] * len(truth_table)
    n = len(weights)
    for row, entry in enumerate(truth_table):
        banked = sum(w for i, w in enumerate(weights) if (row >> (n - 1 - i)) & 1)
        slots[banked // _LEAF_UNIT] = entry
    for entry in slots:
        out += _leaf(int(entry))
    return out
