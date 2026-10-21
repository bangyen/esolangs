"""SLOW ACV MAMMALIAN Boolean program generator: a weighted chain to a flat leaf table.

The default modulo-256 construction chains one read node per input.  Each
bit's whole effect is banked on array 16's non-head sum as a weight -- the
four lightest are banked blind, without ever reading the sum -- and the
dispatch jump lands on the non-head sum, so the banked total names the
leaf slot directly.  A leaf clears the accumulator, SPRINTs to a print
array, CONSUMEs its middle cell, and PRONOUNCEs it.  All inputs are read
unconditionally, and the merge equalities are asserted on every build.

Three identities carry the control flow, each proved where it is used:
``landing = rest - 15`` (:func:`_node`), ``target = nonhead + b``
(:func:`_trampoline`), ``leaf = nonhead of array 16`` (:func:`_weights`).
Every address is solved, none searched: the leaf table sits first, behind
a jump sized against its own end (:func:`_emit`); an arm merges at its
chunk window's end (:func:`_merge_address`); ballast is a division
(:func:`_ballast`).

Size:
    O(T) size and build.
    n=10 random 1847: 127,016 chars, n=12 random 1847: 327,178 chars.
    Executed evidence: every table through ``n == 3``, plus sampled rows of
    dense tables through ``n == 12``.

Decisions:
    The tree it replaced was super-linear, ``S(d) >= (2 + 1/m) S(d-1)`` for
    modulus ``m`` (see ``_CHAIN_MIN_INPUTS`` for where the tree still wins).
"""

from collections.abc import Sequence

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    same_token_layout,
)
from esolangs.languages.slow_acv_mammalian._mammalian255 import decision_tree
from esolangs.languages.slow_acv_mammalian._mammalian_compact import compact_chain
from esolangs.languages.slow_acv_mammalian._sums import (
    _IO_MODULUS,
    _J2,
    _MODULUS,
    _W,
    _leaf,
    _read_seeds,
    _replay,
    _seeds_onto,
    _Sums,
)
from esolangs.languages.slow_acv_mammalian.interpreter import (
    _ARRAYS,
    DEFAULT_MODULI,
    MODULI,
    MammalianModuli,
)
from esolangs.languages.slow_acv_mammalian.wrapping import (
    _balance_mammalian,
    _mammalian,
)
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

__all__ = ["slow_acv_mammalian"]

# The byte a stash chunk appends.  It is what raises the sum, and the sum is
# what puts a distant token index within a jump's reach, so the chunk buys
# the most reach per token by appending the largest byte there is.
_STASH_BYTE = _IO_MODULUS - 1

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

#: One leaf slot, in tokens.  The longest leaf is seven (the ``'1'`` arm
#: spends one SEED reaching the second print array), and the weights below
#: 256 have to be ``_LEAF_UNIT * 2**k``, so a power of two it is.
_LEAF_UNIT = 8

#: How many weights can sit under 256 at that unit: 8, 16, 32, 64 and 128.
#: One of them is banked by :func:`_w_raise` and the rest from pools, which
#: is why there is exactly one more of them than there are pools.
_FREE = len(_POOLS) + 1

#: Fewest inputs at which the cell-255 chain beats the tree, by I/O modulus:
#: parity 65757 vs 95678 characters at n=3 with I/O 255, 121547 vs 191028
#: with I/O 256.  One input fewer, the tree wins every table: 41949 vs 47427
#: at n=2 with I/O 255, 83749 vs 87642 with I/O 256.
_CHAIN_MIN_INPUTS = {255: 3, 256: 3}

#: Leaf slot of the I/O-255 chain above :data:`_FREE` inputs: the longest
#: leaf is seven tokens, and its weights step by 255 instead of 256, so 32
#: seven-token leaves pack into each 255-token block.
_COMPACT_UNIT = 7

#: A machine state as the generator tracks it: array 0 and the accumulator.
type _State = tuple[list[int], int]


def _seeded(array: Sequence[int], count: int) -> list[int]:
    """``array`` after ``count`` ``SEED``s, which only move the head."""
    out = list(array)
    out[0] = (out[0] + count) % _MODULUS
    return out


def _stash_chunk(
    array: list[int], acc: int, *, io_modulus: int = _IO_MODULUS
) -> tuple[list[str], list[int]]:
    """Append the maximum I/O residue and clear the accumulator.

    With modulo-256 I/O, the low byte advances by one per ``SEED`` across a head
    wrap, so the count solves in one step; from the third chunk on every
    count is 1, so a chunk is 3 tokens for 255 of reach.
    """
    if io_modulus == 255:
        if acc:
            raise AssertionError("the modulo-255 chunk starts from a clear accumulator")
        cur = list(array)
        tokens = []
        head = (io_modulus - 1 - sum(cur[1:])) % io_modulus
        tokens += ["SEED"] * ((head - cur[0]) % _MODULUS) + ["DIGEST", "EXCRETE"]
        return tokens, [head, *cur[1:], io_modulus - 1]
    count = (((acc % _MODULUS) ^ _STASH_BYTE) - sum(array)) % _MODULUS
    return (
        [*["SEED"] * count, "DIGEST", "EXCRETE"],
        [*_seeded(array, count), _STASH_BYTE],
    )


def _node(
    array: list[int], acc: int, *, io_modulus: int = _IO_MODULUS
) -> tuple[list[str], _State, _State, int]:
    """One read node: tokens, the 0-exit, the 1-exit, and the landing.

    The 0-branch falls through with ``acc == first``, the sum after the
    aiming seeds; the 1-branch jumps with ``acc == first + 1`` to that sum
    less the head, ``rest - 15``.  The head cancels, so it is only
    stepped through zero when the aim would wrap it mid-node, and the
    landing commits before the arm and merge exist.
    """
    opened = [*array, acc % io_modulus] if acc else list(array)
    rest = sum(opened[1:])
    count = _read_seeds(opened[0], rest, _MODULUS)
    first = (opened[0] + count) % _MODULUS + rest
    tokens = [
        *(["EXCRETE"] if acc else []),
        *["SEED"] * count,
        "DIGEST",
        *["SEED"] * _J2,
        "DIGEST",
        "ACCEPT",
        "DIGEST",
        "LEAPFROG",
    ]
    loaded = _seeded(opened, count + _J2)
    return tokens, ([*loaded, 0], first), ([*loaded, 1], first + 1), rest - 15


class _UnreachableError(Exception):
    """A trampoline target is not past its array's non-head sum."""


def _trampoline(
    array: list[int], acc: int, target: int, *, io_modulus: int = _IO_MODULUS
) -> tuple[list[str], list[int], int]:
    """Build an unconditional jump to token ``target``, plus its exit state.

    Chunks raise the non-head sum by 255 each until ``target`` is within a
    byte, then ``u`` is solved so the ``EXCRETE`` appends the closing
    ``b``.  ``b >= 1`` keeps the ``LEAPFROG`` firing; callers always aim
    past the sum they enter with.  ``rest_sum`` is ``sum(cur) - cur[0]``
    carried incrementally (each chunk appends exactly one
    ``_STASH_BYTE``); re-summing per iteration would be O(chunks**2).
    """
    # One trampoline for both I/O moduli: stash chunks raise the sum by
    # ``io_modulus - 1`` each, and only the closing hop's head solve differs
    # (an XOR solve at 256, a plain residue at 255, whose entry first banks
    # a nonzero accumulator so its chunks start from a clear one).
    byte = io_modulus - 1
    cur, val, tokens = list(array), acc, []
    if io_modulus == 255 and acc:
        cur.append(acc % io_modulus)
        tokens.append("EXCRETE")
        val = 0
    rest_sum = sum(cur[1:])
    if target <= rest_sum:
        raise _UnreachableError("trampoline target is not past the running sum")
    while rest_sum < target - byte:
        chunk, cur = _stash_chunk(cur, val, io_modulus=io_modulus)
        val = 0
        rest_sum += byte
        tokens += chunk
    hop = target - rest_sum
    if io_modulus == 255:
        head = (hop - rest_sum) % io_modulus
        tokens += ["SEED"] * ((head - cur[0]) % _MODULUS)
        out = [head, *cur[1:], hop]
    else:
        if not 1 <= hop <= byte:  # pragma: no cover - the window solve is exact
            raise AssertionError(f"trampoline byte {hop} escaped 1..{byte}")
        count = (((val % _MODULUS) ^ hop) - (cur[0] + rest_sum)) % _MODULUS
        tokens += ["SEED"] * count
        out = [(cur[0] + count) % _MODULUS, *cur[1:], hop]
    tokens += ["DIGEST", "EXCRETE", "DIGEST", "LEAPFROG"]
    return tokens, out, sum(out)


def _plant(st: _Sums) -> list[str]:
    """Replay and return the ``EXCRETE`` that plants the accumulator as a cell."""
    _replay(st, ["EXCRETE"])
    return ["EXCRETE"]


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
    return _digest_excrete(st, _greedy_step((st.hw + st.nw) % _MODULUS)[0])


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


def _greedy_step(r: int) -> tuple[int, int]:
    """Return the first 17-step hit in [239, 255], without wrapping."""
    count = max(0, -(-(_GREEDY_MIN - r) // _W_STEP))
    return count, r + _W_STEP * count


def _jump(st: _Sums, target: int) -> list[str]:
    """Emit an array-0 trampoline to ``target`` and replay it onto ``st``."""
    tokens, out_arr, out_acc = _trampoline(
        st.arr0(), st.acc, target, io_modulus=st.io_modulus
    )
    _replay(st, tokens)
    if (st.h0, st.n0, st.acc) != (out_arr[0], sum(out_arr[1:]), out_acc):
        raise AssertionError("sum replay diverged from the trampoline model")
    return tokens


def _weights(n: int, *, stride: int = _MODULUS, unit: int = _LEAF_UNIT) -> list[int]:
    """Return the weight each read node banks, in read order.

    The last ``_FREE`` bits carry the weights under 256 (the one a
    :func:`_w_raise` arm banks first, then one per pool); earlier bits
    carry ``256 * 2**k``.  Any weight a later arm's solve sees must be a
    multiple of 256, which forces the order: a ``_w_raise`` arm reads array
    16's sum, pool arms never do.  The set is ``_LEAF_UNIT`` times the
    powers of two, so the banked total is a leaf slot times the row.
    """
    free = min(n, _FREE)
    fixed = n - free
    weights = [stride * (1 << (fixed - 1 - i)) for i in range(fixed)]
    return weights + [unit * (1 << k) for k in range(free)]


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


def _dispatch_head(hw: int) -> int:
    """Seeds putting array 16's head on the class both print arrays need.

    A leaf SPRINTs with the head as written and the other leaf one SEED
    later, so the head has to land on ``_PRINT[0]``'s residue *and* stay
    below 239 -- past that the extra 17 wraps and the second leaf misses.
    """
    want = (_PRINT[0] - _W) % _ARRAYS
    return _seeds_onto(hw, _W_STEP, range(want, _GREEDY_MIN, _ARRAYS))


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
        tokens += _plant(st)
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
    stash chunk buys ``s`` of it (255, or 254 under I/O 255) for three
    tokens once the residue settles.  :func:`_ballast` counts the chunks.
    """
    tokens, pos = _node_prefix(st, weight, pool, pos)
    node_toks, _, _, landing = _node(st.arr0(), st.acc, io_modulus=st.io_modulus)
    node_end = pos + len(node_toks)
    zero, one = st.clone(), st.clone()
    _replay(zero, node_toks, bit=0)
    _replay(one, node_toks, bit=1)
    arm_toks, merged, cont = _settle(one, zero, weight, pool, landing)
    z = _laundered(zero)
    t0 = _lead(zero) + _jump(z, cont)
    if landing < node_end + len(t0):  # pragma: no cover - _ballast reserves it
        raise AssertionError(f"the 0-branch runs past the landing at {landing}")
    _check_merge(merged, z, weight)
    tokens += node_toks + t0
    tokens += ["SEED"] * (landing - node_end - len(t0))
    return tokens + arm_toks, z, cont


def _node_prefix(
    st: _Sums, weight: int, pool: int | None, pos: int
) -> tuple[list[str], int]:
    """Return a level's plant and ballast tokens, and the position after them."""
    tokens = _plant(st) if st.acc else []
    pos += len(tokens)
    for _ in range(_ballast(st, pos, _chain_bound(weight, pool, st.io_modulus))):
        chunk, _ = _stash_chunk(st.arr0(), 0, io_modulus=st.io_modulus)
        _replay(st, chunk)
        tokens += chunk
        pos += len(chunk)
    return tokens, pos


def _ballast(st: _Sums, pos: int, chain: int) -> int:
    """Stash chunks putting the landing past the node and the 0-branch.

    The 0-branch is its 2-token lead, its trampoline's first stash chunk,
    ``chain`` (the rest of its chunks, :func:`_chain_bound`), a closing run
    of at most 2 at a window end, and the 4-token close.  With no ballast
    that is checked directly.  After any chunk ``head + n0`` is ``s - 1``
    modulo ``s + 1``, so the 21-token node's aiming seeds (at most 115) and
    that chunk's residue sum to 193 (192 or 193 under I/O 255): the
    prefix is at most ``224 + chain``.  ``k`` chunks raise the landing ``n0
    - 15`` by ``k*s`` for ``seeds + 3k - 1`` tokens, so the count is a
    division, plus one when an I/O 255 head wrap adds a SEED.
    """
    io_modulus, rest = st.io_modulus, st.n0
    node, _, _, landing = _node(st.arr0(), 0, io_modulus=io_modulus)
    zero = st.clone()
    _replay(zero, node, bit=0)
    lead = _laundered(zero)
    first = _stash_run(lead.h0, lead.n0, 1, io_modulus)[0]
    if landing >= pos + len(node) + 2 + first + chain + 6:
        return 0
    byte = io_modulus - 1
    prefix = 224 + chain
    seeds = _stash_run(st.h0, rest, 1, io_modulus)[0] - 2
    chunks = max(1, -(-(pos - rest + 14 + seeds + prefix) // (byte - 3)))
    spent = _stash_run(st.h0, rest, chunks, io_modulus)[0]
    return chunks + (rest + byte * chunks - 15 < pos + spent + prefix)


def _chain_bound(weight: int, pool: int | None, io_modulus: int) -> int:
    """Bound the tokens the 0-branch trampoline spends past its first chunk.

    The arm's sum sits ``s`` past the 0-branch's (its launder appends 48
    after the 0-branch's, its tuning byte is ``s - 1``), so with ``m`` arm
    chunks the 0-branch takes ``m + 1``: ``3m`` more tokens, and under I/O
    255 a head wrap per 255.  :func:`_merge_address` takes the first window
    holding the arm, which starts ``63 + s`` short of its sum: its route
    out (at most 47), banking run, route back (256), tuning chunk (257),
    and its trampoline, whose first residue the tuning byte leaves at 3
    (or 4) and whose closing run at a window end is at most 2.
    """
    byte = io_modulus - 1
    # Greedy chunks bank at least 238 for at most 17 tokens; two exact
    # chunks of at most 257 close the raise.
    raise_ = 17 * -(-max(0, weight - 2 * byte) // 238) + 514
    body = 3 if pool is not None else raise_
    start = 47 + body + 256 + 257 - 63 - byte
    if start + 4 + 4 <= byte:
        return 0
    chunks = -(-(start + 4 + 3 + 2 - byte) // (byte - 3))
    if io_modulus == 255:
        # A head wrap may move the arm a window on, and costs a SEED.
        return 3 * (chunks + 1) + -(-(chunks + 2) // 255)
    return 3 * chunks


def _lead(st: _Sums) -> list[str]:
    """Return the tokens emptying a branch's accumulator before its trampoline.

    A trampoline's closing solve leaves ``head == (acc ^ hop) + hop -
    cont``, which is ``2 * hop - cont`` -- and so even, whatever the hop
    -- only when it enters with a cleared accumulator.  The 1-arm always
    does, because its tuning chunk ends in ``EXCRETE``; the 0-branch
    arrives holding the node's sum, and without this the two heads would
    differ by an odd number no tuning byte closes.
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
    """Build the arm at ``landing``: tokens padded to the merge, exit, merge.

    The merge is the arm's own end, reached by the arm's closing
    trampoline: a self reference.  A trampoline to ``cont`` leaves
    ``head0 == 2*hop - cont``, and its stash chunks each append ``s``
    (255, or 254 under I/O 255), so its ``hop`` is ``cont - sum`` folded
    into ``1..s``.  The tuning byte congruent to the 0-path's sum minus
    the arm's, modulo ``s``, gives both paths one ``hop`` whatever ``cont``
    is; so everything before the trampoline is fixed first, and
    :func:`_merge_address` closes the reference.
    """
    st = one.clone()
    tokens = _arm_core(st, weight, pool)
    z = _laundered(zero)
    beta = (z.n0 - st.n0) % (st.io_modulus - 1)
    if st.io_modulus == 255:
        tokens += _exact_append(st, beta)
    else:
        tokens += _digest_excrete(st, (beta - st.h0 - st.n0) % _MODULUS)
    cont = _merge_address(st.h0, st.n0, landing + len(tokens), st.io_modulus)
    tokens += _jump(st, cont)
    if len(tokens) > cont - landing:  # pragma: no cover - the solve reserves it
        raise AssertionError(f"the arm overran its merge at {cont}")
    return [*tokens, *["SEED"] * (cont - landing - len(tokens))], st, cont


def _stash_run(
    head: int, rest: int, chunks: int, io_modulus: int
) -> tuple[int, int, int]:
    """Tokens, head and non-head sum after ``chunks`` stash chunks, accumulator 0.

    The first chunk solves its residue; each later one is a single SEED,
    two under I/O 255 when the head steps from 254 past the unreachable 255.
    """
    if not chunks:
        return 0, head, rest
    if io_modulus == 255:
        first = (254 - rest) % 255
        wraps = (first + chunks - 1) // 255
        tokens = (first - head) % _MODULUS + 3 * chunks - 1 + wraps
        return tokens, (first + chunks - 1) % 255, rest + 254 * chunks
    count = (_STASH_BYTE - head - rest) % _MODULUS
    head = (head + count + chunks - 1) % _MODULUS
    return count + 3 * chunks - 1, head, rest + _STASH_BYTE * chunks


def _merge_address(head: int, rest: int, start: int, io_modulus: int) -> int:
    """Return a ``cont`` with ``cont - start`` holding the trampoline to ``cont``.

    The trampoline enters with ``head``, non-head sum ``rest`` and a clear
    accumulator.  ``m`` stash chunks reach the window ``rest + s*m``,
    exclusive, to ``rest + s*(m + 1)``; ``cont`` is the end of the first
    window holding the trampoline.  There the closing run is the first
    chunk's residue when ``m == 0`` and 1 past it (1 or 2 under I/O 255),
    and each window adds ``s - 3`` of slack, so the first is a division.
    Ending there, ``hop == s``: the merged accumulator ``2*hop`` makes the
    next level's ``EXCRETE`` append ``s - 1`` and its first stash chunk
    take 3 SEEDs, where a window's first address left 251.
    """
    byte = io_modulus - 1
    seeds = _stash_run(head, rest, 1, io_modulus)[0] - 2
    if start + seeds + 4 <= rest + byte:
        return rest + byte
    run = 1 if io_modulus == _IO_MODULUS else 2
    chunks = max(1, -(-(start + seeds + 3 + run - rest - byte) // (byte - 3)))
    # Under I/O 255 a head wrap adds a SEED and may need one window more.
    spent = _stash_run(head, rest, chunks, io_modulus)[0]
    chunks += start + spent + 4 + run > rest + byte * (chunks + 1)
    return rest + byte * (chunks + 1)


def _check_merge(merged: _Sums, zero: _Sums, weight: int) -> None:
    """Both branches must arrive with one state, up to the banked weight."""
    if merged.heads != zero.heads or merged.acc != zero.acc or merged.n0 != zero.n0:
        raise AssertionError("the branch paths did not merge")
    if merged.nw - zero.nw != weight or merged.ptr or zero.ptr:
        raise AssertionError(f"the banked weight drifted by {merged.nw - zero.nw}")


def slow_acv_mammalian(
    truth_table: str,
    *,
    cell_modulus: int = DEFAULT_MODULI.cell_modulus,
    io_modulus: int = DEFAULT_MODULI.io_modulus,
) -> str:
    """Build a SLOW ACV MAMMALIAN program evaluating ``truth_table``.

    Cell modulus 256 is the weighted chain; 255 dispatches in :func:`_program_255`.
    """
    return _program(truth_table, cell_modulus=cell_modulus, io_modulus=io_modulus)


def _program(
    truth_table: str,
    *,
    cell_modulus: int = DEFAULT_MODULI.cell_modulus,
    io_modulus: int = DEFAULT_MODULI.io_modulus,
) -> str:
    """Build the dispatch, optionally retaining constant-input weights."""
    moduli = MammalianModuli(cell_modulus, io_modulus)
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return _constant_read(truth_table[0], n, moduli.cell_modulus)
    if moduli.cell_modulus == 255:
        return _program_255(truth_table, n, moduli.io_modulus)
    return _program_256(truth_table, n, moduli.io_modulus)


def _unprojected_255(truth_table: str, n: int, io_modulus: int) -> str:
    """Cell modulus 255 over every input: the chain, or a tree below break-even."""
    if n >= _CHAIN_MIN_INPUTS[io_modulus]:
        return compact_chain(truth_table, n, modulus=255, io_modulus=io_modulus)
    return decision_tree(truth_table, n, io_modulus=io_modulus)


def _program_255(truth_table: str, n: int, io_modulus: int) -> str:
    """Cell modulus 255: a coprime-array chain, or a tree below its break-even.

    A table with ignored inputs also races the chain projected onto its
    essential inputs, keeping the shorter; one ignored input saves 4.6% at
    n=8 and 11.6% at n=10 (I/O 255).
    """
    legacy = _unprojected_255(truth_table, n, io_modulus)
    used = essential_inputs(truth_table, n)
    if not used or len(used) == n:
        return legacy
    projected = compact_chain(
        truth_table, n, modulus=255, io_modulus=io_modulus, project_inputs=True
    )
    return min(legacy, projected, key=len)


def _program_256(truth_table: str, n: int, io_modulus: int) -> str:
    """Cell modulus 256: the weighted chain into a flat leaf table."""
    # The weights and pools are laid out over the essential inputs; an
    # ignored one's node banks 0 with no pool, so it reads and the leaf rows
    # it would split coincide, holding equal entries.
    essential = essential_inputs(truth_table, n) or list(range(n))
    m = len(essential)
    unit, stride = _LEAF_UNIT, _MODULUS
    if io_modulus == 255 and m > _FREE:
        unit, stride = _COMPACT_UNIT, 255
    kept = _weights(m, stride=stride, unit=unit)
    free = min(m, _FREE)
    kept_pools: list[int | None] = [None] * (m - free + 1) + list(_POOLS[: free - 1])
    weights = [0] * n
    pools: list[int | None] = [None] * n
    for i, weight, pool in zip(essential, kept, kept_pools, strict=True):
        weights[i], pools[i] = weight, pool
    tokens, base = _emit(weights, pools, io_modulus=io_modulus, unit=unit)
    return " ".join(_with_leaves(tokens, base, truth_table, weights, unit=unit))


def _emit(
    weights: Sequence[int],
    pools: Sequence[int | None],
    *,
    io_modulus: int = _IO_MODULUS,
    unit: int = _LEAF_UNIT,
) -> tuple[list[str], int]:
    """Return everything but the leaf bodies, and where the leaf table starts.

    The table comes first, behind a jump from the empty machine that
    :func:`_merge_address` sizes against its own end; so its base is known
    before the prologue raises array 16 to it, and the chain after it has
    no length to wait for.
    """
    st = _Sums(io_modulus=io_modulus)
    table = sum(weights) + unit
    cont = _merge_address(st.h0, st.n0, table, io_modulus)
    base = cont - table
    tokens = _jump(st, cont)
    tokens += ["SEED"] * (cont - len(tokens))
    pairs = [(w, p) for w, p in zip(weights, pools, strict=True) if p is not None]
    tokens += _prologue(st, pairs, base)
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
        _W + (st.hw + _W_STEP) % _MODULUS
    ) % _ARRAYS != _PRINT[1]:  # pragma: no cover - _dispatch_head solves both
        raise AssertionError(f"head {st.hw} misses the print pair")
    return tokens, base


def _with_leaves(
    tokens: list[str],
    base: int,
    truth_table: str,
    weights: Sequence[int],
    *,
    unit: int = _LEAF_UNIT,
) -> list[str]:
    """Overwrite the padded table at ``base`` with one leaf per row, at its own slot."""
    out = tokens.copy()
    n = len(weights)
    for row, entry in enumerate(truth_table):
        banked = sum(w for i, w in enumerate(weights) if (row >> (n - 1 - i)) & 1)
        start = base + banked
        out[start : start + unit] = _leaf(int(entry), unit=unit)
    return out


def _constant_read(bit: str, inputs: int, modulus: int) -> str:
    """Read into array zero and print the constant from a coprime array."""
    # Array one's step is coprime to 255; array two's is coprime to 256.
    # ACCEPT only appends to array zero, leaving the print head intact.
    array = 1 + int(modulus % 2 == 0)
    seeds = ((_ASCII_ZERO + int(bit)) * pow(array + 1, -1, modulus) - array) % modulus
    return " ".join(
        [
            *["SEED"] * array,
            "SPRINT",
            *["SEED"] * seeds,
            *["ACCEPT"] * inputs,
            "DIGEST",
            "PRONOUNCE",
        ]
    )


LANGUAGE = Language(
    "SLOW ACV MAMMALIAN",
    "slow_acv_mammalian",
    category="tape_based",
    boolean=slow_acv_mammalian,
    dialect=MammalianModuli,
    dialect_values={"cell_modulus": MODULI, "io_modulus": MODULI},
    # Not a tree: a branch-free chain into a flat leaf table.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    # Four-character cells align the ``SEED`` runs; longer words span cells.
    wrap=_mammalian,
    wrap_balance=_balance_mammalian,
    same_layout=same_token_layout,
    slow_width_sweep=True,
)
