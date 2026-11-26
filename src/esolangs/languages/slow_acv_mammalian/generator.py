"""SLOW ACV MAMMALIAN Boolean program generator: a weighted chain to a flat leaf table.

The default modulo-256 construction chains one read node per input.  Each
bit's whole effect is banked on array 16's non-head sum as a weight -- the
pooled weights are banked blind, without ever reading the sum -- and the
dispatch jump lands on the non-head sum, so the banked total names the
leaf slot directly.  A leaf clears the accumulator, SPRINTs to a print
array, and jumps to a shared tail that prints its middle cell.  All inputs are read
unconditionally, and the merge equalities are asserted on every build.

Three identities carry the control flow, each proved where it is used:
``landing = rest - 15`` (:func:`_node`), ``target = nonhead + b``
(:func:`_trampoline`), ``leaf = nonhead of array 16`` (:func:`_weights`).
A SPRINT guards each jump target (the token before it, never executed in
sequence), so a LEAPFROG that resumes at its target runs the same; it is a
no-op because the accumulator, a token address, exceeds every array here.
Every address is solved, none searched: the leaf table sits first, behind
a jump sized against its own end (:func:`_emit`); an arm merges at its
chunk window's end (:func:`_merge_address`); ballast is a division
(:func:`_ballast`).

Size:
    O(T) size and build; n=8 zero: 119 chars.
    n=10 random 1847: 260,455 chars, n=12 random 1847: 583,406 chars.
    Executed evidence: every table through ``n == 3``, plus sampled rows of
    dense tables through ``n == 12``.

Decisions:
    The tree it replaced was super-linear, ``S(d) >= (2 + 1/m) S(d-1)`` for
    modulus ``m`` (see ``_CHAIN_MIN_INPUTS`` for where the tree still wins).
"""

from collections.abc import Sequence

from esolangs.generation.helpers import _ASCII_ZERO, _validate_truth_table
from esolangs.generation.lookup import constant_output
from esolangs.generation.projection import essential_inputs
from esolangs.generation.requests import GenerationRequest
from esolangs.languages.slow_acv_mammalian._banking import (
    _POOLS,
    _PRINT,
    _W_STEP,
    _arm_core,
    _build_pool,
    _digest_excrete,
    _dispatch_head,
    _exact_append,
    _plant,
    _print_bank,
    _route,
    _w_raise,
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
    _Sums,
)
from esolangs.languages.slow_acv_mammalian.dialect import ARRAYS as _ARRAYS
from esolangs.languages.slow_acv_mammalian.dialect import (
    DEFAULT_MODULI,
    MammalianModuli,
)
from esolangs.runtime._program import Program

__all__ = ["slow_acv_mammalian"]

# The byte a stash chunk appends.  It is what raises the sum, and the sum is
# what puts a distant token index within a jump's reach, so the chunk buys
# the most reach per token by appending the largest byte there is.
_STASH_BYTE = _IO_MODULUS - 1

#: One leaf slot, in tokens.  The longest leaf is seven (the ``'1'`` arm
#: spends one SEED reaching the second print array), and the weights below
#: 256 have to be ``_LEAF_UNIT * 2**k``, so a power of two it is.
_LEAF_UNIT = 8

#: How many weights can sit under 256 at that unit: 8, 16, 32, 64 and 128.
#: One of them is banked by :func:`_w_raise` and the rest from pools, which
#: is why there is exactly one more of them than there are pools.
_FREE = len(_POOLS) + 1

#: The tree is smaller for both one-bit tables. The chain is smaller
#: for all 14 nonconstant two-bit tables, at either I/O modulus.
_CHAIN_MIN_INPUTS = 2

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
        head = (io_modulus - 1 - sum(array[1:])) % io_modulus
        tokens = ["SEED"] * ((head - array[0]) % _MODULUS) + ["DIGEST", "EXCRETE"]
        return tokens, [head, *array[1:], io_modulus - 1]
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


def _prologue(st: _Sums, pairs: Sequence[tuple[int, int]], base: int) -> list[str]:
    """Plant the pools, then raise array 16 to ``base``.

    The raise happens *before* the first read, which is what leaves the
    dispatch with nothing to solve: array 16's non-head sum already names
    the leaf table, and the weights only push it along.
    """
    tokens: list[str] = []
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
    if landing <= node_end + len(t0):  # pragma: no cover - _ballast reserves it
        raise AssertionError(f"the 0-branch leaves no guard before landing {landing}")
    _check_merge(merged, z, weight)
    tokens += node_toks + t0
    tokens += ["SEED"] * (landing - node_end - len(t0) - 1)
    return [*tokens, "SPRINT", *arm_toks], z, cont


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
    if landing > pos + len(node) + 2 + first + chain + 6:
        return 0
    byte = io_modulus - 1
    prefix = 225 + chain
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
    if len(tokens) >= cont - landing:  # pragma: no cover - the solve reserves it
        raise AssertionError(f"the arm leaves no guard before its merge at {cont}")
    pad = ["SEED"] * (cont - landing - len(tokens) - 1)
    return [*tokens, *pad, "SPRINT"], st, cont


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
    if start + seeds + 5 <= rest + byte:
        return rest + byte
    run = 1 if io_modulus == _IO_MODULUS else 2
    chunks = max(1, -(-(start + seeds + 4 + run - rest - byte) // (byte - 3)))
    # Under I/O 255 a head wrap adds a SEED and may need one window more.
    spent = _stash_run(head, rest, chunks, io_modulus)[0]
    chunks += start + spent + 5 + run > rest + byte * (chunks + 1)
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
    leapfrog_resume: str = DEFAULT_MODULI.leapfrog_resume,
) -> str:
    """Build a SLOW ACV MAMMALIAN program evaluating ``truth_table``.

    Cell modulus 256 is the weighted chain; 255 dispatches in :func:`_program_255`.
    ``leapfrog_resume`` is accepted and validated as a dialect setting but
    changes nothing built: the SPRINT guards before every jump target make
    the emitted programs read the same under both resume readings.
    """
    return _program(
        truth_table,
        cell_modulus=cell_modulus,
        io_modulus=io_modulus,
        leapfrog_resume=leapfrog_resume,
    )


def _program(
    truth_table: str,
    *,
    cell_modulus: int = DEFAULT_MODULI.cell_modulus,
    io_modulus: int = DEFAULT_MODULI.io_modulus,
    leapfrog_resume: str = DEFAULT_MODULI.leapfrog_resume,
) -> str:
    """Build the dispatch and its leaf bank."""
    moduli = MammalianModuli(cell_modulus, io_modulus, leapfrog_resume)
    n = _validate_truth_table(truth_table)
    if (constant := constant_output(truth_table)) is not None:
        return _constant_read(constant, n)
    if moduli.cell_modulus == 255:
        return _program_255(truth_table, n, moduli.io_modulus)
    return _program_256(truth_table, n, moduli.io_modulus)


def _unprojected_255(truth_table: str, n: int, io_modulus: int) -> str:
    """Cell modulus 255 over every input: the chain, or a tree below break-even."""
    if n >= _CHAIN_MIN_INPUTS:
        return compact_chain(truth_table, n, modulus=255, io_modulus=io_modulus)
    return decision_tree(truth_table, n, io_modulus=io_modulus)


def _program_255(truth_table: str, n: int, io_modulus: int) -> str:
    """Cell modulus 255: a coprime-array chain, or a tree below its break-even.

    A table with ignored inputs also races the chain projected onto its
    essential inputs, keeping the shorter while preserving every input read.
    """
    legacy = _unprojected_255(truth_table, n, io_modulus)
    used = essential_inputs(truth_table, n)
    if not used or len(used) == n:
        return legacy
    projected = compact_chain(
        truth_table, n, modulus=255, io_modulus=io_modulus, essential=used
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
    if len(tokens) >= base:  # pragma: no cover - _merge_address reserves it
        raise AssertionError("the table jump leaves no guard before the table")
    tokens += ["SEED"] * (cont - len(tokens))
    pairs = [(w, p) for w, p in zip(weights, pools, strict=True) if p is not None]
    tokens += _prologue(st, pairs, base)
    pos = len(tokens)
    for weight, pool in zip(weights, pools, strict=True):
        level, st, pos = _level(st, weight, pool, pos)
        tokens += level
        if len(tokens) != pos:  # pragma: no cover - the merge address is the length
            raise AssertionError(f"level ended at {len(tokens)}, merged at {pos}")
    # Both print banks together take less than a quarter of this target,
    # plus fixed routing and final-appends overhead.
    target = 2 * len(tokens) + 8192
    for digit, array in enumerate(_PRINT):
        tokens += _print_bank(st, array, _ASCII_ZERO + digit, target)
    tokens += _route(st, _W)
    tail = [*["SEED"] * _dispatch_head(st), "DIGEST", "LEAPFROG"]
    _replay(st, tail)
    tokens += tail
    if st.nw != base:  # pragma: no cover - the prologue raise is exact
        raise AssertionError(f"the dispatch sum is {st.nw}, not {base}")
    if (_W + st.hw) % _ARRAYS != _PRINT[0] or (
        _W + (st.hw + _W_STEP) % _MODULUS
    ) % _ARRAYS != _PRINT[1]:  # pragma: no cover - _dispatch_head solves both
        raise AssertionError(f"head {st.hw} misses the print pair")
    assert len(tokens) < target
    tokens += ["SEED"] * (target - 1 - len(tokens))
    tokens += ["SPRINT", "CONSUME", "PRONOUNCE"]
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
    # Incrementing a binary row adds one weight and clears its suffix.
    # Precompute those carry deltas instead of scanning n weights per leaf.
    deltas = [0] * n
    suffix = 0
    for i in range(n - 1, -1, -1):
        weight = weights[i]
        deltas[i] = weight - suffix
        suffix += weight
    banked = 0
    for row, entry in enumerate(truth_table):
        if row:
            banked += deltas[n - (row & -row).bit_length()]
        start = base + banked
        out[start : start + unit] = _leaf(int(entry), unit=unit)
        if out[start - 1] == "SEED":
            out[start - 1] = "SPRINT"
    return out


def _constant_read(bit: str, inputs: int) -> str:
    """Seed an untouched print head using 48=6*8 or 49=7*7, then drain inputs."""
    # [ablations.constant_table_audit_20261101]: no head wraps in either dialect.
    value = int(bit)
    array = 5 + value
    seeds = 3 - 2 * value
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


def slow_acv_mammalian_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return slow_acv_mammalian(
        request.table,
        cell_modulus=request.options.integer("cell_modulus"),
        io_modulus=request.options.integer("io_modulus"),
        leapfrog_resume=request.options.text("leapfrog_resume"),
    )
